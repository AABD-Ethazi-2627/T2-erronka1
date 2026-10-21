import json
import statistics
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.cg23_capacity import estimates, main, percentile, protocol, run, summaries


class CapacityTests(unittest.TestCase):
    def test_units_and_replicas(self):
        result = estimates(
            machines=1, hz=1, event_bytes=1, days=1, replicas=1, overhead=1
        )
        self.assertEqual(result["raw_bytes"], 86400)
        self.assertEqual(result["provisioned_bytes"], 172800)
        self.assertEqual(result["expected_cost_eur"], 13100)

    def test_bad_assumptions(self):
        for value in (-1, float("nan"), float("inf")):
            with self.assertRaises(ValueError):
                estimates(hz=value)

    def test_percentile(self):
        self.assertEqual(percentile([4, 1, 3, 2], 0.95), 4)
        self.assertIsNone(percentile([], 0.5))

    def test_bounded_failure_and_replay(self):
        result = run(1000, 0.05, 1, capacity=1, service_ms=5, fail_every=2)
        self.assertGreater(result["rejected"], 0)
        self.assertGreater(result["initial_failure"], 0)
        self.assertEqual(
            result["offered"],
            result["initial_success"] + result["initial_failure"] + result["rejected"],
        )
        self.assertEqual(result["final_missing"], 0)
        self.assertEqual(result["final_unexpected"], 0)
        self.assertEqual(result["final_duplicate_rows"], 0)
        self.assertEqual(
            result["duplicate_attempts_blocked"], result["replay_candidates"]
        )
        self.assertLessEqual(result["max_queue_events"], 1)
        self.assertGreater(result["sink_bytes"], 0)

    def test_safety_bounds(self):
        for args in (
            (1001, 1, 1),
            (True, 1, 1),
            (1, float("nan"), 1),
            (1, 0, 1),
            (1, 6, 1),
            (1, 1, 2),
            (1, 0.01, 1),
        ):
            with self.subTest(args=args), self.assertRaises(ValueError):
                run(*args)
        for options in (
            {"capacity": -1},
            {"capacity": 65},
            {"service_ms": float("inf")},
            {"fail_every": 0.5},
        ):
            with self.subTest(options=options), self.assertRaises(ValueError):
                run(25, 1, 1, **options)

    def test_sink_worker_failure_propagates_without_join_deadlock(self):
        with (
            patch(
                "scripts.cg23_capacity.json.dumps", side_effect=OSError("disk fixture")
            ),
            self.assertRaisesRegex(RuntimeError, "local sink worker failed") as caught,
            self.assertLogs("scripts.cg23_capacity", level="ERROR"),
        ):
            run(25, 0.08, 1, service_ms=0, fail_every=0)
        self.assertIsInstance(caught.exception.__cause__, OSError)

    def test_three_real_repetitions_and_summary_consistency(self):
        result = protocol(rates=(100,), duration=0.02)
        self.assertEqual(len(result["runs"]), 6)
        self.assertEqual([r["workers"] for r in result["runs"]], [1, 4, 4, 1, 1, 4])
        self.assertEqual(len({r["workload_sha256"] for r in result["runs"]}), 1)
        self.assertIn("fresh child", result["environment"]["rss_scope"])
        for group in result["summaries"]:
            samples = [
                r["throughput_success_s"]
                for r in result["runs"]
                if r["workers"] == group["workers"]
            ]
            self.assertEqual(group["repetitions"], 3)
            self.assertEqual(
                group["metrics"]["throughput_success_s"]["mean"],
                statistics.mean(samples),
            )
            self.assertEqual(
                group["metrics"]["throughput_success_s"]["sample_stdev"],
                statistics.stdev(samples),
            )
        self.assertEqual(json.loads(json.dumps(result, allow_nan=False)), result)

    def test_protocol_bounds(self):
        for options in (
            {"repetitions": 2},
            {"repetitions": 6},
            {"repetitions": True},
            {"rates": ()},
            {"rates": (25, 25)},
            {"rates": (1001,)},
            {"duration": float("nan")},
        ):
            with self.subTest(options=options), self.assertRaises(ValueError):
                protocol(**options)

    def test_existing_output_rejected_before_measurement(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "result.json"
            path.write_bytes(b"existing evidence")
            with patch("scripts.cg23_capacity.protocol") as measure:
                with self.assertRaises(FileExistsError):
                    main(["--output", str(path)])
                measure.assert_not_called()
            self.assertEqual(path.read_bytes(), b"existing evidence")

    def test_empty_summaries(self):
        self.assertEqual(summaries([]), [])
