import unittest

import pandas as pd

from scripts.experiment_anomaly import fit_normal, signals


class AnomalyTests(unittest.TestCase):
    def test_only_normal_fit_and_no_rf_alarm_suppression(self):
        data = pd.read_csv("data/ai4i2020_train.csv").head(250)
        model, count = fit_normal(data, trees=10)
        self.assertEqual(count, int((data.machine_failure == 0).sum()))
        self.assertEqual(
            signals(0.8, 0.1, 0.5), {"risk": True, "anomaly": False, "any_alert": True}
        )
        self.assertEqual(
            signals(0.1, 0.6, 0.5), {"risk": False, "anomaly": True, "any_alert": True}
        )
        self.assertEqual(len(model.score_samples(data)), 250)
