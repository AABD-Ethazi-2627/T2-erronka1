"""Four-cell economic cost and marginal break-even fixtures."""

import unittest

import pandas as pd

from scripts.business_ml_study import curve, economic_cut, economic_metrics

COSTS = {"fn": 5000, "fp": 200, "tp": 300, "tn": 0}


class BusinessCostTests(unittest.TestCase):
    def test_all_four_confusion_cells_are_charged(self):
        rows = pd.DataFrame({"label": [1, 1, 0, 0], "score": [0.9, 0.1, 0.8, 0.1]})
        result = economic_metrics(rows, 0.5, COSTS)
        self.assertEqual(result["cost_total_eur"], 5500)
        self.assertEqual(result["hypothetical_saving_vs_no_alert_eur"], 4500)

    def test_tp_cost_changes_marginal_break_even_at_23_point_5_fp(self):
        for false_alarms, expected in [(23, 0.1), (24, 0.9)]:
            rows = pd.DataFrame(
                {
                    "label": [1] * 5 + [0] * false_alarms,
                    "score": [0.9] * 4 + [0.1] + [0.2] * false_alarms,
                }
            )
            self.assertEqual(economic_cut(rows, "rf_fixture", COSTS), expected)

    def test_curve_preserves_ties_and_matches_direct_cost(self):
        rows = pd.DataFrame({"label": [1, 0, 1, 0], "score": [0.9, 0.9, 0.1, 0.05]})
        points = curve(rows, COSTS)
        self.assertEqual(len(points), 3)
        for point in points.itertuples():
            direct = economic_metrics(rows, point.threshold, COSTS)
            self.assertEqual(point.cost_per_1000, direct["cost_per_1000"])


if __name__ == "__main__":
    unittest.main()
