"""Timing survives failed cycles; run receipts retain effective NiFi periods."""

import json
import tempfile
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from scripts import cg32_lab as lab
from scripts import run_automatic_graph as automatic
from scripts.build_automatic_graph_flow import build


class Clock:
    def __init__(self):
        self.value = 100.0

    def __call__(self):
        return self.value

    def advance(self, seconds):
        self.value += seconds


class CycleTimingTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.config = json.loads(
            (lab.REPO / "deploy/cg14/automatic-graph.example.json").read_bytes()
        )
        self.config["root"] = str(self.root / "worker")

    def receipt(self):
        files = list((Path(self.config["root"]) / "automatic-cycles").glob("*.json"))
        self.assertEqual(len(files), 1)
        return json.loads(files[0].read_bytes())

    def test_success_separates_destination_preflight_from_worker_lifetime(self):
        clock = Clock()

        def preflight(config):
            clock.advance(0.25)

        def worker(args):
            clock.advance(1.5)
            return 0

        with (
            patch.object(time, "monotonic", clock),
            patch.object(automatic, "check_es", side_effect=preflight),
            patch.object(automatic, "run_worker", side_effect=worker),
        ):
            self.assertEqual(automatic.cycle(self.config), 0)
        report = self.receipt()
        self.assertEqual(report["status"], "completed")
        self.assertEqual(report["source_ack"], "worker-only")
        timing = report["timing"]
        self.assertEqual(timing["clock"], "monotonic")
        self.assertEqual(timing["check_es_ms"], 250.0)
        self.assertEqual(timing["worker_ms"], 1500.0)
        self.assertEqual(timing["elapsed_ms"], 1750.0)
        self.assertEqual(timing["finished_mono"] - timing["started_mono"], 1.75)

    def test_preflight_failure_records_time_without_fabricating_worker_duration(self):
        clock = Clock()
        error = ValueError("synthetic guard missing")

        def blocked(config):
            clock.advance(0.5)
            raise error

        with (
            patch.object(time, "monotonic", clock),
            patch.object(automatic, "check_es", side_effect=blocked),
            patch.object(automatic, "run_worker") as worker,
            self.assertRaises(ValueError) as raised,
        ):
            automatic.cycle(self.config)
        self.assertIs(raised.exception, error)
        worker.assert_not_called()
        report = self.receipt()
        self.assertEqual(report["status"], "blocked")
        self.assertEqual(report["error_type"], "ValueError")
        self.assertEqual(report["timing"]["check_es_ms"], 500.0)
        self.assertIsNone(report["timing"]["worker_ms"])
        self.assertEqual(report["timing"]["elapsed_ms"], 500.0)

    def test_worker_failure_keeps_original_exception_and_both_measured_stages(self):
        clock = Clock()
        error = RuntimeError("synthetic destination failure")

        def preflight(config):
            clock.advance(0.125)

        def blocked(args):
            clock.advance(0.75)
            raise error

        with (
            patch.object(time, "monotonic", clock),
            patch.object(automatic, "check_es", side_effect=preflight),
            patch.object(automatic, "run_worker", side_effect=blocked),
            self.assertRaises(RuntimeError) as raised,
        ):
            automatic.cycle(self.config)
        self.assertIs(raised.exception, error)
        report = self.receipt()
        self.assertEqual(report["status"], "blocked")
        self.assertEqual(report["timing"]["check_es_ms"], 125.0)
        self.assertEqual(report["timing"]["worker_ms"], 750.0)
        self.assertEqual(report["timing"]["elapsed_ms"], 875.0)
        self.assertEqual(report["accounting"]["pending"], 0)


class RunSchedulingReceiptTests(unittest.TestCase):
    def test_receipt_uses_exported_worker_period_instead_of_trigger_argument(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            instance = lab.Lab(root)
            instance.state = {
                "project": "cg32-test",
                "runs": [],
                "python": "unused",
                "es_url": "http://unused",
                "nifi_port": 1,
            }
            manifest = root / "manifest.json"
            manifest.write_text("{}")
            args = SimpleNamespace(
                manifest=manifest,
                rate=1,
                duration=1,
                label="fixture",
                max_records=1,
                max_polls=3,
                attempts=1,
                timeout=0.5,
                period="2 sec",
                pause_at=None,
                pause_for=0,
                kill_at=None,
            )
            definition = build()
            owner = next(
                p
                for p in definition["flowContents"]["processors"]
                if p["name"] == "Single Kafka owner"
            )
            self.assertEqual(owner["schedulingPeriod"], "5 sec")

            def upload(directory, period):
                for processor in definition["flowContents"]["processors"]:
                    if processor["name"] == lab.TRIGGER:
                        processor["schedulingPeriod"] = period
                # A changed lab export must be visible even when CLI is unchanged.
                owner["schedulingPeriod"] = "7 sec"
                (directory / "nifi-flow.json").write_text(json.dumps(definition))
                return "group-id", {lab.TRIGGER: "trigger-id"}

            command = SimpleNamespace(stdout="127.0.0.1:1", stderr="")
            with (
                patch.object(
                    lab,
                    "verify_bundle",
                    return_value={
                        "path": manifest,
                        "sha256": "test-hash",
                        "model_version": "test",
                    },
                ),
                patch.object(lab, "create_index"),
                patch.object(lab, "wait"),
                patch.object(lab.httpx, "get") as health,
                patch.object(instance, "compose", return_value=command),
                patch.object(instance, "kafka_topic"),
                patch.object(instance, "stop_previous_groups"),
                patch.object(instance, "upload_graph", side_effect=upload),
                patch.object(instance, "processor_state"),
                patch.object(instance, "measure", return_value={}),
                patch.object(instance, "collect", return_value={"metrics": {}}),
            ):
                health.return_value.json.return_value = {"status": "ready"}
                receipt = instance.run(args)
            saved = json.loads(
                (root / "runs" / receipt["name"] / "run.json").read_bytes()
            )
            self.assertEqual(saved["nifi"]["period"], "2 sec")
            self.assertEqual(saved["nifi"]["processor_periods"][lab.TRIGGER], "2 sec")
            self.assertEqual(
                saved["nifi"]["processor_periods"]["Single Kafka owner"], "7 sec"
            )


if __name__ == "__main__":
    unittest.main()
