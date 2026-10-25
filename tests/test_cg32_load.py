import argparse
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scripts import cg32_lab as lab
from scripts import cg32_load as load

SOURCE = Path(__file__).resolve().parents[1] / "data/ai4i2020_train.csv"


class FixtureTest(unittest.TestCase):
    def test_run_label_rejects_path_and_topic_escapes(self):
        self.assertEqual(lab.validate_run_label("steady-01"), "steady-01")
        for label in ("../../escape", "UPPER", "bad space", "-edge", "edge-"):
            with self.subTest(label=label), self.assertRaises(argparse.ArgumentTypeError):
                lab.validate_run_label(label)

    def test_fixture_is_nominal_unique_and_stable(self):
        first = load.fixture_lines(SOURCE, 50)
        self.assertEqual(first, load.fixture_lines(SOURCE, 50))
        self.assertEqual(len(set(first)), 50)
        for line in first:
            fields = line.split(",")
            self.assertEqual(len(fields), 14)
            self.assertIn(fields[2], ("H", "M", "L"))
            self.assertEqual(fields[8:], ["0"] * 6)
        self.assertEqual(
            load.fixture_hash(first[:10]),
            load.fixture_hash(load.fixture_lines(SOURCE, 10)),
        )

    def test_plan_bounds(self):
        self.assertEqual(load.validate_plan(10, 60), 600)
        for rate, duration in ((0, 1), (51, 1), (1, 61), (1.5, 1)):
            with self.assertRaises(ValueError):
                load.validate_plan(rate, duration)


class OfferTest(unittest.TestCase):
    def test_offer_writes_header_once_and_never_overwrites(self):
        ticks = iter(range(100))
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "load.csv"
            lines = load.fixture_lines(SOURCE, 3)
            records = load.offer(
                path,
                lines,
                10,
                clock=lambda: next(ticks) * 0.01,
                wall=lambda: 0.0,
                sleep=lambda _: None,
            )
            text = path.read_text().splitlines()
            self.assertEqual(text, [load.HEADER, *lines])
            self.assertGreater(len((load.HEADER + "\n" + lines[0]).encode()), 228)
            self.assertEqual(
                [r["key"] for r in records], [load.line_key(x) for x in lines]
            )
            with self.assertRaises(FileExistsError):
                load.offer(path, lines, 10)


class ReconcileTest(unittest.TestCase):
    def setUp(self):
        self.lines = load.fixture_lines(SOURCE, 3)
        self.offered = [{"key": load.line_key(x)} for x in self.lines]
        self.records = [
            {"topic": "t", "partition": 0, "offset": i, "key": load.line_key(x)}
            for i, x in enumerate(self.lines)
        ]

    def test_clean_run(self):
        jobs = {f"t/0/{i}": "completed" for i in range(3)}
        docs = {f"t/0/{i}": f"e{i}" for i in range(3)}
        result = load.reconcile(self.offered, self.records, jobs, docs)
        self.assertEqual(result["saved"], 3)
        self.assertTrue(result["balance_ok"])
        self.assertEqual(result["valid_lost"], 0)
        self.assertEqual(result["kafka_repeated_lines"], 0)

    def test_detects_pending_loss_and_repeated_delivery(self):
        records = self.records + [
            {"topic": "t", "partition": 0, "offset": 3, "key": self.offered[0]["key"]}
        ]
        jobs = {"t/0/0": "completed", "t/0/1": None, "t/0/3": "completed"}
        docs = {"t/0/0": "e0", "t/0/3": "e3"}
        result = load.reconcile(self.offered, records, jobs, docs)
        self.assertEqual(result["pending"], 1)
        self.assertEqual(result["kafka_repeated_lines"], 1)
        self.assertEqual(result["kafka_not_observed"], 1)  # offset 2 never observed
        self.assertEqual(result["valid_lost"], 1)  # committed unknown: counted lost
        backlog = load.reconcile(self.offered, records, jobs, docs, committed=2)
        self.assertEqual(backlog["backlog_uncommitted"], 1)
        self.assertEqual(backlog["valid_lost"], 0)


class StatsTest(unittest.TestCase):
    def test_nearest_rank_and_dispersion(self):
        values = list(range(1, 101))
        self.assertEqual(load.percentiles(values)["p95"], 95)
        self.assertEqual(load.percentiles(values)["p50"], 50)
        self.assertIsNone(load.percentiles([])["p95"])
        self.assertIsNone(load.dispersion([1.0])["stdev"])

    def test_summary_keeps_percentiles_per_run(self):
        runs = [
            {"rate": 10, "fixture_sha256": "a", "metrics": {"e2e_p95_ms": v}}
            for v in (100.0, 200.0, 300.0)
        ]
        summary = load.summarize(runs)["10"]
        self.assertEqual(summary["runs"], 3)
        self.assertEqual(summary["e2e_p95_ms"]["median"], 200.0)
        self.assertEqual(summary["fixture_hashes"], ["a"])

    def test_write_new_refuses_overwrite(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "x.json"
            load.write_new(path, {"a": 1})
            self.assertEqual(json.loads(path.read_text()), {"a": 1})
            with self.assertRaises(FileExistsError):
                load.write_new(path, {})


class NifiTlsTest(unittest.TestCase):
    def test_all_lab_images_use_reviewed_build_targets(self):
        root = Path(lab.__file__).parents[1]
        compose = (root / "deploy/cg32/compose.yaml").read_text()
        dockerfiles = {
            line.split(":", 1)[1].strip()
            for line in compose.splitlines()
            if "dockerfile:" in line
        }
        targets = json.loads((root / "deploy/build-targets.json").read_text())
        self.assertEqual(
            dockerfiles,
            {
                targets[key]
                for key in (
                    "api",
                    "elasticsearch",
                    "filebeat",
                    "kafka",
                    "kibana",
                    "nifi",
                )
            },
        )

    def test_missing_or_changed_certificate_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "state.json").write_text(json.dumps({"nifi_ca_sha256": "expected"}))
            instance = lab.Lab(root)
            with self.assertRaisesRegex(RuntimeError, "absent or has changed"):
                instance.nifi_ssl_context()
            (root / "nifi-ca.pem").write_text("different")
            with self.assertRaisesRegex(RuntimeError, "absent or has changed"):
                instance.nifi_ssl_context()

    def test_token_uses_pinned_context_and_localhost(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".env").write_text(
                "SINGLE_USER_CREDENTIALS_USERNAME=user\n"
                "SINGLE_USER_CREDENTIALS_PASSWORD=password\n"
            )
            (root / "state.json").write_text(
                json.dumps(
                    {
                        "project": "cg32-test",
                        "uv_python": str(root),
                        "nifi_port": 18443,
                        "kafka_port": 19092,
                    }
                )
            )
            instance = lab.Lab(root)
            context = object()
            instance._nifi_ssl_context = context
            response = mock.Mock(status_code=201, text="token")
            with mock.patch.object(lab.httpx, "post", return_value=response) as post:
                self.assertEqual(instance.nifi_token(), "token")
            self.assertEqual(
                post.call_args.args[0], "https://localhost:18443/nifi-api/access/token"
            )
            self.assertIs(post.call_args.kwargs["verify"], context)

    def test_source_contains_no_tls_verification_bypass(self):
        source = Path(lab.__file__).read_text()
        self.assertNotIn("verify=False", source)


if __name__ == "__main__":
    unittest.main()
