import tempfile
import unittest
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

from scripts.experiment_rf import evaluate, pipeline


class ExperimentTests(unittest.TestCase):
    def test_pipeline_ignores_outcomes_and_serializes(self):
        data = pd.read_csv("data/ai4i2020_train.csv").head(200)
        model = pipeline("rf", True, "balanced", trees=5).fit(
            data, data.machine_failure
        )
        scores = model.predict_proba(data)[:, 1]
        changed = data.copy()
        changed["machine_failure"] = 1 - changed.machine_failure
        changed["failure_TWF"] = 1
        np.testing.assert_array_equal(scores, model.predict_proba(changed)[:, 1])
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "model.pkl"
            joblib.dump(model, path)
            np.testing.assert_array_equal(
                scores, joblib.load(path).predict_proba(data)[:, 1]
            )

    def test_confusion_and_f2(self):
        result = evaluate([0, 0, 1, 1], [0.1, 0.8, 0.2, 0.9], 0.5)
        self.assertEqual(result["confusion_matrix"], [[1, 1], [1, 1]])
        self.assertEqual(result["recall"], 0.5)
        self.assertEqual(result["f2"], 0.5)
