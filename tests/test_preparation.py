import unittest

import numpy as np
import pandas as pd

from scoring.preparation import features, split_development


class PreparationTests(unittest.TestCase):
    def test_physics_and_label_exclusion(self):
        frame = pd.DataFrame(
            [
                dict(
                    air_temp_K=300,
                    process_temp_K=310,
                    rpm=60,
                    torque_Nm=10,
                    tool_wear_min=5,
                    machine_type="M",
                    machine_failure=1,
                    failure_TWF=1,
                    machine_id="CNC-001",
                )
            ]
        )
        result = features(frame)
        self.assertEqual(result.temp_diff.iloc[0], 10)
        self.assertAlmostEqual(result.power_W.iloc[0], 20 * np.pi)
        self.assertEqual(result.wear_torque.iloc[0], 50)
        self.assertFalse(set(result) & {"machine_failure", "failure_TWF", "machine_id"})
        frame["failure_TWF"] = 0
        pd.testing.assert_frame_equal(features(frame), result)

    def test_original_holdout_is_excluded_and_repeatable(self):
        frame = pd.read_csv("data/ai4i2020_train.csv")
        train, validation, excluded = split_development(frame)
        self.assertEqual(len(excluded), 1200)
        self.assertEqual(len(validation), 1200)
        self.assertFalse(set(train.index) & set(excluded.index))
        self.assertFalse(set(validation.index) & set(excluded.index))
        again = split_development(frame)
        self.assertEqual(train.index.tolist(), again[0].index.tolist())
        self.assertEqual(len(train) + len(validation) + len(excluded), 8000)

    def test_nonbinary_target_is_rejected(self):
        frame = pd.read_csv("data/ai4i2020_train.csv").head(100).copy()
        frame.loc[0, "machine_failure"] = 2
        with self.assertRaises(ValueError):
            split_development(frame)
