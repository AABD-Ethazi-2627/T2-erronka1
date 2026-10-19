import unittest

import numpy as np
import pandas as pd

from scripts.experiment_smotenc import make_smotenc


class SmotencTests(unittest.TestCase):
    def test_categorical_and_label_safety_through_real_fit(self):
        frame = pd.read_csv("data/ai4i2020_train.csv").head(500)
        model = make_smotenc(trees=5).fit(frame, frame.machine_failure)
        before = model.predict_proba(frame.head(20))
        changed = frame.head(20).copy()
        changed["machine_failure"] = 1 - changed.machine_failure
        changed["failure_TWF"] = 1
        np.testing.assert_array_equal(before, model.predict_proba(changed))
        self.assertEqual(before.shape, (20, 2))
        self.assertGreater(model.named_steps["sampler"].sampling_strategy_[1], 0)
        prepared = model.named_steps["impute"].transform(frame)
        resampled, _ = model.named_steps["sampler"].fit_resample(
            prepared, frame.machine_failure
        )
        self.assertTrue(set(resampled.machine_type) <= set("HML"))
