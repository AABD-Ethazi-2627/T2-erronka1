"""A failed destination must not prevent local shutdown or hide the run error."""

import json
import tempfile
import unittest
from contextlib import ExitStack
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from scripts import cg32_lab as lab
from scripts.build_automatic_graph_flow import build


class CleanupTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.instance = lab.Lab(self.root)
        self.instance.state = {
            "project": "cg32-test",
            "runs": [],
            "python": "unused",
            "es_url": "http://unused",
            "nifi_port": 1,
        }
        self.manifest = self.root / "manifest.json"
        self.manifest.write_text("{}")
        self.args = SimpleNamespace(
            manifest=self.manifest,
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
        self.commands = []
        self.failed_stops = False

    def compose(self, *arguments, **kwargs):
        self.commands.append(arguments)
        if self.failed_stops and arguments == ("stop", "filebeat"):
            raise OSError("synthetic stop failure")
        return SimpleNamespace(returncode=0, stdout="127.0.0.1:1", stderr="")

    def upload(self, directory, period):
        (directory / "nifi-flow.json").write_text(json.dumps(build()))
        return "group", {lab.TRIGGER: "trigger", "Single Kafka owner": "worker"}

    def processor(self, identifier, state):
        if state == "STOPPED":
            # Exercise the actual absent-token path during cleanup, inertly.
            self.instance.nifi("GET", "/processors/" + identifier)

    def prepared(self, *, error=None):
        stack = ExitStack()
        self.addCleanup(stack.close)
        for name in ("create_index", "wait"):
            stack.enter_context(patch.object(lab, name))
        stack.enter_context(
            patch.object(
                lab,
                "verify_bundle",
                return_value={
                    "path": self.manifest,
                    "sha256": "fixture",
                    "model_version": "fixture",
                    "identity_kind": "historical_CG26_delivery",
                    "identity_record_sha256": "fixture",
                },
            )
        )
        health = stack.enter_context(patch.object(lab.httpx, "get"))
        health.return_value.json.return_value = {"status": "ready"}
        stack.enter_context(
            patch.object(self.instance, "compose", side_effect=self.compose)
        )
        stack.enter_context(patch.object(self.instance, "kafka_topic"))
        stack.enter_context(patch.object(self.instance, "stop_previous_groups"))
        stack.enter_context(
            patch.object(self.instance, "upload_graph", side_effect=self.upload)
        )
        stack.enter_context(
            patch.object(self.instance, "processor_state", side_effect=self.processor)
        )
        stack.enter_context(
            patch.object(self.instance, "nifi_token", return_value=None)
        )
        stack.enter_context(
            patch.object(self.instance, "measure", side_effect=error, return_value={})
        )
        return stack.enter_context(
            patch.object(self.instance, "collect", return_value={"metrics": {}})
        )

    def receipt(self):
        return json.loads(next((self.root / "runs").glob("*/run.json")).read_bytes())

    def test_missing_token_fails_explicitly_before_an_authenticated_request(self):
        with (
            patch.object(self.instance, "nifi_token", return_value=None),
            patch.object(lab.httpx, "request") as request,
        ):
            with self.assertRaisesRegex(RuntimeError, "authentication unavailable"):
                self.instance.nifi("GET", "/processors/fixture")
            request.assert_not_called()

    def test_failed_nifi_and_source_stops_preserve_primary_and_still_stop_api(self):
        primary = ValueError("synthetic measurement failure")
        self.failed_stops = True
        collect = self.prepared(error=primary)
        with self.assertRaises(ValueError) as raised:
            self.instance.run(self.args)
        self.assertIs(raised.exception, primary)
        self.assertIn(("stop", "filebeat"), self.commands)
        self.assertIn(("stop", "api"), self.commands)
        receipt = self.receipt()
        self.assertEqual(receipt["status"], "failed")
        self.assertEqual(receipt["failure"], {"error_type": "ValueError"})
        self.assertEqual(
            [error["stage"] for error in receipt["cleanup_errors"]],
            ["nifi_stop", "nifi_stop", "filebeat_stop"],
        )
        collect.assert_not_called()

    def test_failed_cleanup_after_success_cannot_report_success(self):
        collect = self.prepared()
        with self.assertRaisesRegex(RuntimeError, "cleanup or collection failed"):
            self.instance.run(self.args)
        self.assertIn(("stop", "api"), self.commands)
        self.assertEqual(self.receipt()["status"], "failed")
        collect.assert_not_called()

    def test_unwritable_receipt_does_not_replace_primary_measurement_error(self):
        primary = ValueError("synthetic measurement failure")
        self.prepared(error=primary)
        with (
            patch.object(
                lab.load, "write_new", side_effect=OSError("disk unavailable")
            ),
            self.assertRaises(ValueError) as raised,
        ):
            self.instance.run(self.args)
        self.assertIs(raised.exception, primary)
        self.assertIn(("stop", "api"), self.commands)
        self.assertIn("CG32 run receipt persistence failed: OSError", primary.__notes__)

    def test_nonzero_stop_is_recorded_and_remaining_cleanup_runs(self):
        self.instance.processor_state = Mock()
        self.instance.compose = Mock(
            side_effect=[
                SimpleNamespace(returncode=1),
                SimpleNamespace(returncode=0, stdout="", stderr=""),
                SimpleNamespace(returncode=0),
            ]
        )
        record = {"name": "fixture"}
        with self.assertRaisesRegex(RuntimeError, "cleanup or collection failed"):
            self.instance.finalize_run(self.root, {}, record, {}, self.root, None)
        self.assertEqual(
            record["cleanup_errors"],
            [{"stage": "filebeat_stop", "error_type": "RuntimeError"}],
        )
        self.assertEqual(self.instance.compose.call_args.args, ("stop", "api"))
        self.assertEqual(
            json.loads((self.root / "run.json").read_bytes())["status"], "failed"
        )
