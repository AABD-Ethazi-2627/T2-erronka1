"""Regressions for leakage, split overlap and artifact/inference parity."""

import tempfile
import unittest
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

from scripts import train_model as training

ROOT = Path(__file__).resolve().parents[1]


class TrainingTests(unittest.TestCase):
    def test_splits_are_disjoint_and_repeatable(self):
        df = pd.read_csv(ROOT / "data/ai4i2020_train.csv")
        parts = training.split_data(df)
        self.assertEqual([len(p) for p in parts], [5600, 1200, 1200])
        self.assertEqual(len(set.union(*(set(p.index) for p in parts))), 8000)
        for a, b in [(0, 1), (0, 2), (1, 2)]:
            self.assertFalse(set(parts[a].index) & set(parts[b].index))
        for a, b in zip(parts, training.split_data(df)):
            self.assertEqual(list(a.index), list(b.index))

    def test_pipeline_ignores_labels_and_imputes_from_training_only(self):
        df = pd.read_csv(ROOT / "data/ai4i2020_train.csv").iloc[:300].copy()
        model = training.make_models()["random_forest"]
        model.fit(df, df.machine_failure)
        sample = df.iloc[:4].copy()
        before = model.predict_proba(sample)
        sample["machine_failure"] = 1 - sample.machine_failure
        sample.loc[:, [c for c in sample if c.startswith("failure_")]] = 999
        sample["machine_id"] = "UNSEEN"
        np.testing.assert_array_equal(before, model.predict_proba(sample))
        sample.loc[:, "air_temp_K"] = np.nan
        self.assertTrue(np.isfinite(model.predict_proba(sample)).all())
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "model.pkl"
            joblib.dump(model, p)
            np.testing.assert_array_equal(
                model.predict_proba(sample), joblib.load(p).predict_proba(sample)
            )

    def test_threshold_uses_f1_and_deterministic_tie_break(self):
        self.assertAlmostEqual(
            training.select_threshold([0, 0, 1, 1], [0.1, 0.4, 0.35, 0.8]), 0.35
        )


if __name__ == "__main__":
    unittest.main()
