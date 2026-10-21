import json
import tempfile
import unittest
from hashlib import sha256
from pathlib import Path
from unittest.mock import patch

import pandas as pd

from scripts.build_cg19_evaluation import build, describe
from scripts.create_lab_dashboard import (
    ROOT,
    build_objects,
    generate,
    summary_spec,
    temperature_spec,
)


def fixture():
    source = pd.DataFrame(
        {"machine_type": ["H", "H", "L", "L"], "tool_wear_min": [49, 50, 250, 100]}
    )
    scores = pd.DataFrame(
        {
            "source_row_index": [0, 1, 2, 3],
            "label": [0, 1, 1, 0],
            "rf_score": [0.7, 0.1, 0.5, 0.0],
        }
    )
    return describe(scores, source, 0.5)


class DashboardTests(unittest.TestCase):
    def test_export_has_unique_ids_resolved_references_and_expected_views(self):
        objects = build_objects(fixture())
        ids = {(o["type"], o["id"]) for o in objects}
        self.assertEqual(len(ids), len(objects))
        for obj in objects:
            for ref in obj["references"]:
                self.assertIn((ref["type"], ref["id"]), ids)
        dashboard = objects[-1]
        panels = json.loads(dashboard["attributes"]["panelsJSON"])
        self.assertEqual(len(panels), 5)
        self.assertFalse(dashboard["attributes"]["timeRestore"])
        self.assertIn("no responde a filtros", objects[3]["attributes"]["title"])

    def test_online_queries_keep_dashboard_context_and_contain_no_ground_truth(self):
        for spec in [summary_spec(), temperature_spec()]:
            url = spec["data"][0]["url"]
            self.assertTrue(url["%context%"])
            self.assertEqual(url["%timefield%"], "timestamp")
            self.assertNotIn("query", url["body"])
            self.assertNotIn("machine_failure", json.dumps(spec))
            self.assertNotIn("label", json.dumps(url["body"]))
        summary = summary_spec()["data"][0]["url"]["body"]["aggs"]["summary"]["aggs"]
        self.assertEqual(
            summary["alerts"]["filter"]["terms"]["alert_level"], ["AVISO", "CRITICA"]
        )
        self.assertIn("classified", summary)
        self.assertEqual(summary["machines"]["cardinality"]["field"], "machine_id")
        self.assertEqual(summary["latest"]["max"]["field"], "timestamp")

    def test_temperatures_group_by_id_source_hour_and_preserve_gaps(self):
        spec = temperature_spec()
        groups = spec["data"][0]["url"]["body"]["aggs"]["groups"]
        self.assertEqual(
            groups["multi_terms"]["terms"],
            [{"field": "machine_id"}, {"field": "source.kind"}],
        )
        self.assertEqual(groups["aggs"]["series"]["date_histogram"]["min_doc_count"], 0)
        self.assertEqual(
            groups["aggs"]["series"]["date_histogram"]["fixed_interval"], "1h"
        )
        line = spec["marks"][0]["marks"][0]
        self.assertEqual(line["type"], "line")
        self.assertIn("doc_count > 0", line["encode"]["update"]["defined"]["signal"])

    def test_recent_table_sort_identity_and_50_rows(self):
        search = next(o for o in build_objects(fixture()) if o["type"] == "search")
        attrs = search["attributes"]
        self.assertEqual(attrs["rowsPerPage"], 50)
        self.assertEqual(attrs["sampleSize"], 50)
        self.assertEqual(attrs["sort"], [["timestamp", "desc"], ["event_id", "asc"]])
        self.assertIn("event_id", attrs["columns"])
        self.assertIn("source.kind", attrs["columns"])
        self.assertEqual(
            json.loads(attrs["kibanaSavedObjectMeta"]["searchSourceJSON"])["size"], 50
        )

    def test_bin_boundaries_counts_and_absence_differ_from_zero(self):
        report = fixture()
        bins = {(b["machine_type"], b["wear_bin"]): b for b in report["wear_bins"]}
        self.assertEqual(bins[("H", "0–49")]["failure_rate"], 0)
        self.assertEqual(bins[("H", "50–99")]["failure_rate"], 1)
        self.assertEqual(bins[("L", "250+")]["positives"], 1)
        self.assertNotIn(("M", "0–49"), bins)
        self.assertEqual(sum(b["rows"] for b in bins.values()), 4)
        self.assertEqual(
            report["overall"],
            {
                "rows": 4,
                "positives": 2,
                "negatives": 2,
                "alerts": 2,
                "tp": 1,
                "fn": 1,
                "fp": 1,
                "tn": 1,
            },
        )
        self.assertEqual(report["cases"]["FP"]["label"], 0)
        self.assertEqual(report["cases"]["FN"]["label"], 1)

    def test_equality_at_threshold_stays_tp_not_fn(self):
        source = pd.DataFrame({"machine_type": ["L"], "tool_wear_min": [0]})
        cutoff = 0.19082281465428477
        scores = pd.DataFrame(
            {"source_row_index": [0], "label": [1], "rf_score": [cutoff]}
        )
        self.assertEqual(describe(scores, source, cutoff)["overall"]["tp"], 1)

    def test_empty_offline_sample_has_no_fabricated_cases(self):
        report = fixture()
        report["cases"] = {}
        objects = build_objects(report)
        decision = json.loads(objects[-2]["attributes"]["visState"])["params"][
            "markdown"
        ]
        self.assertNotIn("**FP offline**", decision)
        self.assertIn("N/D", decision)

    def test_generator_is_offline_deterministic_and_detects_drift(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "objects.ndjson"
            offline = Path(directory) / "offline.json"
            offline.write_text(json.dumps(fixture()), encoding="utf-8")
            with patch(
                "socket.socket", side_effect=AssertionError("Network forbidden")
            ):
                first = generate(offline, output)
                self.assertEqual(generate(offline, output, check=True), first)
                self.assertEqual(generate(offline, output), first)
            output.write_text("drift", encoding="utf-8")
            with self.assertRaises(ValueError):
                generate(offline, output, check=True)

    def test_committed_objects_match_generator(self):
        generate(ROOT / "kibana/cg19-offline.json", check=True)

    def test_invalid_reference_rejected_before_source_or_csv_read(self):
        with self.assertRaisesRegex(ValueError, "corrected PR49"):
            build(Path("does-not-exist.csv"), b"test", b"{}")

    def test_csv_round_trip_and_evidence_guards_with_small_fixture(self):
        cutoff = 0.19082281465428477
        source = pd.DataFrame(
            {"machine_type": ["L"], "tool_wear_min": [0], "machine_failure": [1]}
        )
        raw = b"source_row_index,label,rf_score\n0,1,0.19082281465428477\n"
        reference = {
            "provenance": {
                "validation_csv_sha256": sha256(raw).hexdigest(),
                "partition": "reused_validation_for_threshold_tuning",
            },
            "alert_rule": {"threshold": cutoff},
            "overall": {
                "rows": 1,
                "positives": 1,
                "negatives": 0,
                "alerts": 1,
                "tp": 1,
                "fn": 0,
                "fp": 0,
                "tn": 0,
            },
        }
        ref_raw = json.dumps(reference).encode()
        with (
            patch(
                "scripts.build_cg19_evaluation.REFERENCE_SHA256",
                sha256(ref_raw).hexdigest(),
            ),
            patch(
                "scripts.build_cg19_evaluation.load_training_source",
                return_value=source,
            ),
            patch(
                "scripts.build_cg19_evaluation.split_development",
                return_value=(None, source, None),
            ),
        ):
            self.assertEqual(build(Path("fixture"), raw, ref_raw)["overall"]["tp"], 1)
            with self.assertRaisesRegex(ValueError, "differs"):
                build(Path("fixture"), raw + b"0,1,0.1\n", ref_raw)
            with (
                patch(
                    "scripts.build_cg19_evaluation.split_development",
                    return_value=(None, pd.DataFrame(index=[1]), None),
                ),
                self.assertRaisesRegex(ValueError, "preserved split"),
            ):
                build(Path("fixture"), raw, ref_raw)
            source.loc[0, "machine_failure"] = 0
            with self.assertRaisesRegex(ValueError, "source labels"):
                build(Path("fixture"), raw, ref_raw)

    def test_no_overlaps_in_panel_layout(self):
        panels = json.loads(build_objects(fixture())[-1]["attributes"]["panelsJSON"])
        for i, panel in enumerate(panels):
            a = panel["gridData"]
            for other in panels[i + 1 :]:
                b = other["gridData"]
                self.assertTrue(
                    a["x"] + a["w"] <= b["x"]
                    or b["x"] + b["w"] <= a["x"]
                    or a["y"] + a["h"] <= b["y"]
                    or b["y"] + b["h"] <= a["y"]
                )


if __name__ == "__main__":
    unittest.main()
