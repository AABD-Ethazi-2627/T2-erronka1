import unittest
from scripts.cg23_capacity import estimates, percentile, run


class CapacityTests(unittest.TestCase):
    def test_units_and_replicas(self):
        result = estimates(machines=1, hz=1, event_bytes=1, days=1, replicas=1, overhead=1)
        self.assertEqual(result['raw_bytes'], 86400)
        self.assertEqual(result['provisioned_bytes'], 172800)
        self.assertEqual(result['expected_cost_eur'], 13100)

    def test_bad_assumptions(self):
        for value in (-1, float('nan'), float('inf')):
            with self.assertRaises(ValueError):
                estimates(hz=value)

    def test_percentile(self):
        self.assertEqual(percentile([4, 1, 3, 2], .95), 4)
        self.assertIsNone(percentile([], .5))

    def test_bounded_failure_and_replay(self):
        result = run(1000, .05, 1, capacity=1, service_ms=5, fail_every=2)
        self.assertGreater(result['rejected'], 0)
        self.assertGreater(result['initial_failure'], 0)
        self.assertEqual(result['offered'], result['initial_success'] + result['initial_failure'] + result['rejected'])
        self.assertEqual(result['final_missing'], 0)
        self.assertEqual(result['final_duplicate_rows'], 0)
        self.assertLessEqual(result['max_queue_events'], 1)

    def test_safety_bounds(self):
        with self.assertRaises(ValueError):
            run(1001, 1, 1)
