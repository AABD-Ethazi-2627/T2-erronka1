import unittest

import pandas as pd

from scripts.seasonal_lab import simulate, temporal_split


class SeasonalLabTests(unittest.TestCase):
    def test_causal_features_and_censoring(self):
        data = simulate(days=60, machines=2)
        self.assertEqual(len(data), 60 * 24 * 2)
        first = data.groupby("machine_id").head(1)
        self.assertTrue(first.past_torque_mean.isna().all())
        tail = data.groupby("machine_id").tail(24)
        self.assertTrue(tail.failure_next_24h.isna().all())
        machine = data[data.machine_id.eq("SIM-000")]
        self.assertAlmostEqual(
            machine.iloc[1].past_torque_mean, machine.iloc[0].torque_Nm
        )
        train, valid, test = temporal_split(data)
        self.assertLess(
            train.timestamp.max() + pd.Timedelta(hours=24), valid.timestamp.min()
        )
        self.assertLess(
            valid.timestamp.max() + pd.Timedelta(hours=24), test.timestamp.min()
        )
        self.assertFalse(test.failure_next_24h.isna().any())

    def test_repeatable(self):
        pd.testing.assert_frame_equal(
            simulate(days=3, machines=1), simulate(days=3, machines=1)
        )
