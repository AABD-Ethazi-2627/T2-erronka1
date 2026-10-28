"""Inert run control regressions: no services, sockets, models or campaigns."""

import json
import tempfile
import threading
import time
import unittest
from contextlib import ExitStack
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from scripts import cg32_lab as lab
from scripts import cg32_load as load


class MeasureControlTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        (self.root / "input").mkdir()
        self.instance = lab.Lab(self.root)
        self.instance.state = {
            "project": "cg32-inert",
            "es_url": "http://unused",
            "kafka_port": 1,
        }
        self.args = SimpleNamespace(rate=50, kill_at=None, pause_at=None, pause_for=0)
        self.graph = {
            "es_index": "unused",
            "topic": "unused",
            "group_id": "unused",
            "root": str(self.root / "worker"),
        }
        self.record = {}
        stack = ExitStack()
        self.addCleanup(stack.close)
        self.observer = Mock()
        self.observer.lag.return_value = {"lag": 0}
        stack.enter_context(
            patch.object(lab, "KafkaObserver", return_value=self.observer)
        )
        self.disk = stack.enter_context(patch.object(lab, "du", return_value=0))
        stack.enter_context(patch.object(lab, "docker_stats", return_value={}))
        stack.enter_context(
            patch.object(lab, "worker_jobs", return_value={"t/0/0": "completed"})
        )
        client = stack.enter_context(patch.object(lab.httpx, "Client"))
        client.return_value.__enter__.return_value.post.return_value.json.return_value = {
            "hits": {"hits": []},
        }
        sleep = time.sleep
        self.real_sleep = sleep
        stack.enter_context(
            patch.object(lab.time, "sleep", side_effect=lambda n: sleep(min(n, 0.001)))
        )
        self.processor = stack.enter_context(
            patch.object(self.instance, "processor_state")
        )
        self.compose = stack.enter_context(
            patch.object(
                self.instance,
                "compose",
                return_value=SimpleNamespace(returncode=0),
            )
        )

    def measure(self, count=1):
        return self.instance.measure(
            self.args,
            self.root,
            ["fixture-" + str(i) for i in range(count)],
            self.graph,
            {lab.TRIGGER: "trigger"},
            record=self.record,
        )

    def offered(self):
        return [
            json.loads(row)
            for row in (self.root / "offered.jsonl").read_text().splitlines()
        ]

    def test_stopped_failure_reaches_main_and_retains_failed_control_evidence(self):
        primary = RuntimeError("synthetic STOPPED failure")
        self.args.pause_at = 0
        self.processor.side_effect = primary
        with self.assertRaises(RuntimeError) as raised:
            self.measure()
        self.assertIs(raised.exception, primary)
        self.assertIsNone(self.record["pause_observed"])
        self.assertEqual(self.record["controller_errors"], ["RuntimeError"])
        self.observer.close.assert_called_once()
        self.assertTrue((self.root / "samples.jsonl").exists())

    def test_running_failure_does_not_claim_resume(self):
        primary = RuntimeError("synthetic RUNNING failure")
        self.args.pause_at = 0
        self.processor.side_effect = [None, primary]
        with self.assertRaises(RuntimeError) as raised:
            self.measure()
        self.assertIs(raised.exception, primary)
        self.assertIn("stop_mono", self.record["pause_observed"])
        self.assertNotIn("resume_mono", self.record["pause_observed"])

    def test_docker_failure_reaches_main(self):
        primary = OSError("synthetic Docker failure")
        self.args.kill_at = 0
        self.compose.side_effect = primary
        with self.assertRaises(OSError) as raised:
            self.measure()
        self.assertIs(raised.exception, primary)
        self.assertIsNone(self.record["pause_observed"])

    def test_observer_cleanup_error_does_not_hide_controller_failure(self):
        primary = RuntimeError("synthetic STOPPED failure")
        self.args.pause_at = 0
        self.processor.side_effect = primary
        self.observer.close.side_effect = OSError("synthetic close failure")
        with self.assertRaises(RuntimeError) as raised:
            self.measure()
        self.assertIs(raised.exception, primary)
        self.assertIn("CG32 observer close failed: OSError", primary.__notes__)

    def test_exhausted_kill_deadline_fails_instead_of_succeeding(self):
        self.args.kill_at = 0
        clock = [100.0]

        def no_worker(*args, **kwargs):
            clock[0] += 31
            return SimpleNamespace(returncode=1)

        self.compose.side_effect = no_worker
        with (
            patch.object(lab.time, "monotonic", side_effect=lambda: clock[0]),
            self.assertRaisesRegex(TimeoutError, "SIGKILL was not confirmed"),
        ):
            self.measure()
        self.assertEqual(self.record["controller_errors"], ["TimeoutError"])
        self.assertIsNone(self.record["pause_observed"])

    def test_confirmed_pause_and_kill_are_required_and_recorded(self):
        self.args.pause_at = self.args.kill_at = 0
        result = self.measure()
        self.assertEqual(
            set(result["pause_observed"]), {"killed_mono", "stop_mono", "resume_mono"}
        )
        self.assertEqual(result["controller_errors"], [])
        self.assertEqual(result["offered"], 1)
        self.assertEqual(len(self.offered()), 1)

    def test_preexisting_disk_excess_offers_zero_and_collectable_empty_evidence(self):
        self.disk.return_value = 5 * 2**30
        result = self.measure(count=600)
        self.assertEqual(result["stopped_by_budget"], "max_lab_disk")
        self.assertEqual(result["offered"], 0)
        self.assertIsNone(result["first_offer_mono"])
        self.assertEqual(self.offered(), [])
        self.assertEqual((self.root / "input/load.csv").stat().st_size, 0)
        (self.root / "api-timing.jsonl").write_text("")
        with (
            patch.object(lab, "dump_topic", return_value=[]),
            patch.object(lab, "worker_jobs", return_value={}),
            patch.object(lab, "es_all", return_value={}),
            patch.object(lab, "es_store", return_value=0),
            patch.object(lab, "dump_committed", return_value={"committed": 0}),
        ):
            collected = self.instance.collect(self.root, self.graph, result)
        self.assertEqual(collected["reconciliation"]["offered"], 0)
        self.assertIsNone(collected["metrics"]["producer_lag_max_ms"])
        self.assertIsNone(collected["metrics"]["throughput_eps"])
        self.assertIn("container_mem_usage_max_mib", collected["metrics"])
        self.assertNotIn("rss_max_mib", collected["metrics"])

    def test_preexisting_lag_excess_offers_zero(self):
        self.observer.lag.return_value = {"lag": lab.BUDGET["max_lag"] + 1}
        result = self.measure(count=600)
        self.assertEqual(result["stopped_by_budget"], "max_lag")
        self.assertEqual(result["offered"], 0)

    def test_sampler_failure_preserves_excess_lag_and_cancels_offer(self):
        primary = ValueError("synthetic malformed Docker stats")
        self.observer.lag.side_effect = [
            {"lag": 0},
            {"lag": lab.BUDGET["max_lag"] + 1},
        ]
        with (
            patch.object(lab, "docker_stats", side_effect=primary),
            self.assertRaises(ValueError) as raised,
        ):
            self.measure(count=50)
        self.assertIs(raised.exception, primary)
        self.assertLess(self.record["offered"], 50)
        self.assertEqual(self.record["stopped_by_budget"], "max_lag")
        self.assertIn("sampler ValueError", self.record["observer_errors"])
        samples = [
            json.loads(row)
            for row in (self.root / "samples.jsonl").read_text().splitlines()
        ]
        self.assertEqual(samples[-1]["kafka"]["lag"], lab.BUDGET["max_lag"] + 1)
        self.observer.close.assert_called_once()

    def test_sampler_failure_without_budget_excess_still_fails_measurement(self):
        with (
            patch.object(lab, "docker_stats", side_effect=OSError("Docker failed")),
            self.assertRaises(OSError),
        ):
            self.measure(count=50)
        self.assertLess(self.record["offered"], 50)
        self.assertIn("sampler OSError", self.record["observer_errors"])

    def test_sampler_failure_during_final_drain_cannot_return_success(self):
        release = threading.Event()
        self.addCleanup(release.set)

        def fail_after_offer(project):
            if not release.wait(5):
                raise TimeoutError("fixture did not enter drain")
            raise ValueError("late Docker failure")

        def drained(root):
            release.set()
            return {"t/0/0": "completed"}

        with (
            patch.object(lab, "docker_stats", side_effect=fail_after_offer),
            patch.object(lab, "worker_jobs", side_effect=drained),
            self.assertRaisesRegex(ValueError, "late Docker failure"),
        ):
            self.measure()
        self.assertEqual(self.record["offered"], 1)
        self.assertIn("sampler ValueError", self.record["observer_errors"])
        self.assertTrue((self.root / "samples.jsonl").exists())

    def test_budget_cancellation_cannot_claim_unperformed_fault_injection(self):
        self.args.kill_at = 60
        self.disk.return_value = 5 * 2**30
        with self.assertRaisesRegex(RuntimeError, "SIGKILL was not confirmed"):
            self.measure(count=600)
        self.compose.assert_not_called()
        self.assertEqual(self.record["stopped_by_budget"], "max_lab_disk")
        self.assertEqual(self.record["offered"], 0)
        self.assertIsNone(self.record["pause_observed"])

    def test_disk_excess_during_offer_stops_with_actual_count(self):
        # Advance only on writes, avoiding races with the observation threads.
        clock = [100.0]
        original_fsync = load.os.fsync

        def written(fd):
            original_fsync(fd)
            clock[0] += 1
            self.disk.return_value = 5 * 2**30

        with (
            patch.object(lab.time, "monotonic", side_effect=lambda: clock[0]),
            patch.object(load.os, "fsync", side_effect=written),
        ):
            result = self.measure(count=600)
        self.assertEqual(result["stopped_by_budget"], "max_lab_disk")
        self.assertEqual(result["offered"], 1)
        self.assertEqual(len(self.offered()), 1)

    def test_lag_excess_during_offer_stops_with_actual_count(self):
        # Initial lag is zero, then the regular sampling thread sees excess.
        self.observer.lag.side_effect = lambda: {
            "lag": 0 if self.observer.lag.call_count == 1 else lab.BUDGET["max_lag"] + 1
        }
        with patch.object(lab.time, "sleep", side_effect=self.real_sleep):
            result = self.measure(count=600)
        self.assertEqual(result["stopped_by_budget"], "max_lag")
        self.assertGreater(result["offered"], 0)
        self.assertLess(result["offered"], 600)
        self.assertEqual(len(self.offered()), result["offered"])


class ContainerMemoryTests(unittest.TestCase):
    def test_sampled_docker_memusage_peak_is_named_without_rss_claim(self):
        samples = [
            {"containers": {"nifi": {"mem": "1GiB"}}},
            {"containers": {"nifi": {"mem": "900MiB"}, "api": {"mem": "512KiB"}}},
        ]
        self.assertEqual(
            lab.container_mem_usage_by_container(samples), {"nifi": 1024, "api": 0.5}
        )


class ProcessorConfirmationTests(unittest.TestCase):
    def test_successful_put_requires_observed_state(self):
        instance = lab.Lab(Path(tempfile.gettempdir()) / "cg32-inert-unused")
        with (
            patch.object(
                instance,
                "nifi",
                side_effect=[
                    {"revision": {"version": 0}},
                    {},
                    {"component": {"state": "RUNNING"}},
                    {"component": {"state": "STOPPED"}},
                ],
            ) as nifi,
            patch.object(lab.time, "sleep"),
        ):
            instance.processor_state("processor", "STOPPED")
        self.assertEqual(nifi.call_count, 4)
