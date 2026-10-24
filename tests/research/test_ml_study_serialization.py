"""End-to-end worker CSV regression with a float32 scorer, without any fit."""

import csv
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pandas as pd

from scoring.scope import INPUT_FEATURES
from scripts.ml_study import read_json, worker, write_json
from scripts.ml_study_models import catalog


class Float32Scorer:
    preparation_seconds_ = 0.0

    def fit(self, X, y):
        return self

    def score(self, X):
        return np.array(
            [0.7, np.nextafter(np.float32(0.7), np.float32(1))], dtype=np.float32
        )


class ScoreSerializationTests(unittest.TestCase):
    def test_worker_csv_preserves_native_decisions_without_dtype_knowledge(self):
        frame = pd.DataFrame({f: np.arange(6, dtype=float) for f in INPUT_FEATURES})
        frame["machine_type"] = "L"
        frame["machine_failure"] = [0, 1, 0, 1, 1, 0]
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            task = {
                "model": "xgb_d3_True",
                "fit": [0, 1, 2, 3],
                "held": [4, 5],
                "phase": "fixture",
                "fold": 0,
            }
            write_json(root / "task.json", task)
            with (
                patch(
                    "scripts.ml_study.verify",
                    return_value={"catalog": catalog(), "reload_atol": 1e-12},
                ),
                patch("scripts.ml_study.source_train", return_value=(frame, {})),
                patch("scripts.ml_study.StudyModel", return_value=Float32Scorer()),
            ):
                worker(root, root / "task.json")
            with (root / "scores.csv").open(newline="") as stream:
                rows = list(csv.DictReader(stream))
            self.assertEqual(float(rows[0]["score"]), float(np.float32(0.7)))
            self.assertLess(float(rows[0]["score"]), 0.7)
            self.assertGreater(float(rows[1]["score"]), 0.7)
            self.assertEqual(
                read_json(root / "result.json")["native_score_dtype"], "float32"
            )


if __name__ == "__main__":
    unittest.main()
