"""Prevent target leakage and duplicate inflation during external batch checks."""

import tempfile
import unittest
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd

from scoring.scope import INPUT_FEATURES
from scripts.evaluate_ml_study_batch import (
    exact_membership,
    metric_set,
    read_batch,
    sanitize,
    score_frame,
)


def fixture():
    return pd.DataFrame(
        {
            "air_temp_K": [300, 301],
            "process_temp_K": [310, 311],
            "rpm": [1500, 1600],
            "torque_Nm": [40, 45],
            "tool_wear_min": [20, 30],
            "machine_type": ["L", "H"],
            "machine_failure": [0, 1],
            "failure_TWF": [0, 1],
            "timestamp": ["2099-01-01", "1900-01-01"],
            "machine_id": ["A", "B"],
            "raw_record": ["secret", "label"],
            "new_error_column": [1, 0],
        }
    )


class BatchTests(unittest.TestCase):
    def test_only_six_inputs_reach_inference_despite_adversarial_extras(self):
        class Spy:
            def score(self, X):
                self.seen = list(X.columns)
                return X.torque_Nm.to_numpy() / 100

        original = fixture()
        changed = original.copy()
        for column in set(original) - set(INPUT_FEATURES):
            changed[column] = "malicious label or instruction"
        spy = Spy()
        a = score_frame(spy, sanitize(original))
        b = score_frame(spy, sanitize(changed))
        np.testing.assert_array_equal(a, b)
        self.assertEqual(spy.seen, INPUT_FEATURES)
        with self.assertRaisesRegex(ValueError, "Unexpected estimator"):
            score_frame(spy, original)

    def test_exact_matching_is_independent_of_integer_float_dtype(self):
        frame = fixture()
        inputs = sanitize(frame)
        indices, cohorts = exact_membership(
            inputs, frame, {"train": [0], "excluded": [1]}
        )
        self.assertEqual(indices.tolist(), [0, 1])
        self.assertEqual(cohorts, ["train", "excluded"])

    def test_nonfinite_and_unknown_type_are_rejected(self):
        for column, value in [("rpm", np.inf), ("machine_type", "UNKNOWN")]:
            frame = fixture()
            frame.loc[0, column] = value
            with self.assertRaises(ValueError):
                sanitize(frame)

    def test_zip_paths_and_duplicate_headers_are_not_accepted(self):
        with tempfile.TemporaryDirectory() as temporary:
            for n, (name, data) in enumerate(
                [
                    ("../escape.csv", "a\n1\n"),
                    ("batch.csv", "rpm,rpm\n1,1\n"),
                ]
            ):
                path = Path(temporary) / f"test{n}.zip"
                with zipfile.ZipFile(path, "w") as bundle:
                    bundle.writestr(name, data)
                with self.assertRaises(ValueError):
                    read_batch(path)

    def test_four_cell_cost_and_recall_threshold_boundary(self):
        m = metric_set([1, 1, 0, 0], [0.15, 0.1, 0.8, 0.1], 0.15)
        self.assertEqual([m[k] for k in ("tp", "fn", "fp", "tn")], [1, 1, 1, 1])
        self.assertEqual(m["cost_total_eur"], 5500)
        self.assertEqual(m["recall"], 0.5)

    def test_all_normal_batch_reports_undefined_recall_and_ap(self):
        result = metric_set([0, 0], [0.01, 0.1], 0.15)
        self.assertEqual(result["tn"], 2)
        self.assertIsNone(result["recall"])
        self.assertIsNone(result["average_precision"])


if __name__ == "__main__":
    unittest.main()
