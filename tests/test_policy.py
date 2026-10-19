import unittest

from scoring.alert_policy import alert_level, cost


class PolicyTests(unittest.TestCase):
    def test_classroom_boundaries(self):
        self.assertEqual(
            [alert_level(p) for p in [0.1499, 0.15, 0.6999, 0.70]],
            ["OK", "AVISO", "AVISO", "CRITICA"],
        )
        for invalid in [-0.1, 1.1, float("nan")]:
            with self.assertRaises(ValueError):
                alert_level(invalid)

    def test_cost_uses_explicit_scenario_not_invented_savings(self):
        self.assertEqual(cost(fp=2, fn=3, inspection_eur=50, downtime_hours=2), 7300)
