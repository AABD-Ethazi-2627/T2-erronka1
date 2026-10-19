import unittest
from copy import deepcopy

from planning.adaptive import evaluate_stream


def manifest():
    return {
        "dataset_id": "fixture-v1",
        "provenance": "synthetic",
        "timestamp_role": "observation",
        "physical_identity_verified": False,
        "columns": {"asset": "machine", "timestamp": "at", "lifecycle": "run"},
        "sensors": {"wear": {"column": "wear", "unit": "min"}},
        "max_gap_minutes": 10,
    }


def rows():
    return [
        {
            "machine": "A",
            "run": "one",
            "at": f"2026-10-19T10:{i:02}:00Z",
            "wear": float(10 + 2 * i),
        }
        for i in range(12)
    ]


class AdaptiveTests(unittest.TestCase):
    def test_incremental_drift_beats_persistence_on_known_fixture(self):
        report = evaluate_stream(rows(), manifest(), warmup=2)
        sensor = report["metrics"]["wear"]
        self.assertLess(sensor["online_drift_mae"], sensor["persistence_mae"])
        self.assertFalse(report["promotion_allowed"])
        self.assertIsNone(report["failure_eta_minutes"])

    def test_future_change_cannot_change_earlier_predictions(self):
        source = rows()
        modified = deepcopy(source)
        modified[-1]["wear"] = 10000
        a = evaluate_stream(source, manifest())["predictions"]
        b = evaluate_stream(modified, manifest())["predictions"]
        self.assertEqual(a[-1]["online_drift"], b[-1]["online_drift"])
        self.assertEqual(a[:-1], b[:-1])

    def test_missing_timestamp_and_same_time_conflict_fail_closed(self):
        source = rows()
        del source[0]["at"]
        with self.assertRaises(ValueError):
            evaluate_stream(source, manifest())
        source = rows()
        duplicate = dict(source[0], wear=99)
        with self.assertRaises(ValueError):
            evaluate_stream([*source, duplicate], manifest())

    def test_lifecycles_do_not_share_state_and_input_order_is_irrelevant(self):
        source = rows()
        source[6:] = [dict(r, run="two", wear=r["wear"] - 22) for r in source[6:]]
        report = evaluate_stream(source, manifest(), warmup=0)
        self.assertEqual(len(report["predictions"]), 10)
        reset = next(p for p in report["predictions"] if p["lifecycle"] == "two")
        self.assertEqual(reset["online_drift"], reset["persistence"])
        self.assertEqual(
            report, evaluate_stream(list(reversed(source)), manifest(), warmup=0)
        )

    def test_actual_elapsed_time_and_long_gap_reset(self):
        source = [
            dict(
                rows()[0],
                at=f"2026-10-19T10:{minute:02}:00Z",
                wear=float(10 + 2 * minute),
            )
            for minute in [0, 2, 5, 30, 32]
        ]
        report = evaluate_stream(source, manifest(), warmup=0)
        predictions = report["predictions"]
        self.assertEqual([p["horizon_minutes"] for p in predictions], [2.0, 3.0, 2.0])
        self.assertEqual(predictions[1]["online_drift"], 20.0)
        self.assertEqual(
            predictions[-1]["online_drift"], predictions[-1]["persistence"]
        )
        self.assertEqual(report["segments"][0]["gap_resets"], 1)

    def test_duplicate_is_removed_without_extra_learning(self):
        report = evaluate_stream([*rows(), rows()[3]], manifest())
        self.assertEqual(report["duplicate_rows_removed"], 1)
        self.assertEqual(
            report["metrics"], evaluate_stream(rows(), manifest())["metrics"]
        )

    def test_provenance_units_and_observation_time_are_explicit(self):
        for field, value in [
            ("timestamp_role", "ingestion"),
            ("provenance", None),
            ("physical_identity_verified", "yes"),
        ]:
            config = manifest()
            config[field] = value
            with self.assertRaises(ValueError):
                evaluate_stream(rows(), config)
        config = manifest()
        config["sensors"]["wear"]["unit"] = ""
        with self.assertRaises(ValueError):
            evaluate_stream(rows(), config)
        source = rows()
        source[0]["at"] = "2026-10-19T10:00:00"
        with self.assertRaises(ValueError):
            evaluate_stream(source, manifest())

    def test_multiple_assets_do_not_contaminate_each_other(self):
        a = rows()
        b = [dict(r, machine="B", wear=-r["wear"]) for r in rows()]
        combined = evaluate_stream([*a, *b], manifest())
        only_a = [p for p in combined["predictions"] if p["asset"] == "A"]
        self.assertEqual(only_a, evaluate_stream(a, manifest())["predictions"])

    def test_cli_provenance_hashes_and_no_overwrite(self):
        import contextlib
        import csv
        import io
        import json
        import tempfile
        from pathlib import Path
        from unittest.mock import patch

        from scripts.evaluate_adaptive import main

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config = root / "manifest.json"
            config.write_text(json.dumps(manifest()))
            source = root / "source.csv"
            with source.open("w") as handle:
                writer = csv.DictWriter(handle, fieldnames=list(rows()[0]))
                writer.writeheader()
                writer.writerows(rows())
            argv = [
                "evaluate",
                "--data",
                str(source),
                "--manifest",
                str(config),
                "--output",
                str(root / "report"),
            ]
            with patch("sys.argv", argv), contextlib.redirect_stdout(io.StringIO()):
                main()
            report = json.loads((root / "report/report.json").read_text())
            self.assertEqual(len(report["source_sha256"]), 64)
            self.assertFalse(report["promotion_allowed"])
            with patch("sys.argv", argv), self.assertRaises(FileExistsError):
                main()

    def test_cli_runs_outside_repo_and_rejects_ambiguous_csv_headers(self):
        import contextlib
        import io
        import json
        import os
        import tempfile
        from pathlib import Path
        from unittest.mock import patch

        from scripts.evaluate_adaptive import main

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config = root / "manifest.json"
            config.write_text(json.dumps(manifest()))
            source = root / "source.csv"
            source.write_text(
                "machine,run,at,wear\nA,one,2026-10-19T10:00:00Z,10\nA,one,2026-10-19T10:01:00Z,12\n"
            )
            argv = [
                "evaluate",
                "--data",
                str(source),
                "--manifest",
                str(config),
                "--output",
                str(root / "report"),
            ]
            original = Path.cwd()
            try:
                os.chdir(root)
                with patch("sys.argv", argv), contextlib.redirect_stdout(io.StringIO()):
                    main()
            finally:
                os.chdir(original)
            source.write_text(
                "machine,run,at,wear,wear\nA,one,2026-10-19T10:00:00Z,10,999\n"
            )
            argv[-1] = str(root / "ambiguous")
            with patch("sys.argv", argv), self.assertRaises(ValueError):
                main()
            self.assertFalse((root / "ambiguous").exists())
