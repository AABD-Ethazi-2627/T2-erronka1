"""Synthetic protocol regressions; never train or score the AI4I source."""

import unittest

import numpy as np
import pandas as pd

from scoring.preparation import SENSORS
from scripts.ml_study import choose_threshold, folds, metrics
from scripts.ml_study_models import CORE, StudyModel, catalog


class StudyProtocolTests(unittest.TestCase):
    def test_catalog_and_core_are_fixed(self):
        specs = catalog()
        self.assertEqual(len(specs), 50)
        self.assertEqual(sum(not s["anomaly"] for s in specs), 40)
        self.assertEqual(len({s["name"] for s in specs}), 50)
        self.assertEqual(len(CORE), 10)
        self.assertTrue(set(CORE) <= {s["name"] for s in specs})

    def test_threshold_matches_exhaustive_rule_and_boundary(self):
        rng = np.random.default_rng(8)
        for _ in range(20):
            y = np.resize([1, 0, 0, 0, 0], 55)
            scores = rng.integers(0, 10, len(y)) / 10
            eligible = [(metrics(y, scores, cut), cut) for cut in np.unique(scores)]
            expected = min(
                (r for r in eligible if r[0]["recall"] >= 0.76),
                key=lambda r: (r[0]["cost_per_1000"], r[0]["fn"], -r[1]),
            )[1]
            self.assertEqual(choose_threshold(y, scores), expected)
        self.assertEqual(metrics([1, 0], [0.15, np.nextafter(0.15, 0)], 0.15)["tp"], 1)
        self.assertEqual(metrics([1, 0], [0.15, np.nextafter(0.15, 0)], 0.15)["fp"], 0)

    def test_folds_cover_only_training_with_no_overlap(self):
        frame = pd.DataFrame(
            {"machine_failure": np.resize([1, 0, 0, 0], 120)}, index=np.arange(200, 320)
        )
        outer = folds(frame, 43)
        self.assertEqual(
            sorted(v for f in outer for v in f["held"]), frame.index.tolist()
        )
        for f in outer:
            self.assertFalse(set(f["fit"]) & set(f["held"]))
            for g in folds(frame.loc[f["fit"]], 42):
                self.assertTrue(set(g["fit"] + g["held"]) <= set(f["fit"]))
                self.assertFalse(set(g["fit"]) & set(f["held"]))

    def test_labels_ids_and_type_cannot_enter_anomaly_design(self):
        frame = pd.DataFrame({name: [1.0, 2.0] for name in SENSORS})
        frame["machine_type"] = ["L", "H"]
        spec = catalog()[0]
        expected = StudyModel(spec).design(frame)
        frame["machine_failure"] = [1, 0]
        frame["failure_fake"] = [1, 1]
        frame["machine_id"] = ["a", "b"]
        frame["raw_record"] = ["secret", "label"]
        pd.testing.assert_frame_equal(expected, StudyModel(spec).design(frame))
        rare = next(s for s in catalog() if s["anomaly"])
        self.assertEqual(StudyModel(rare).design(frame).columns.tolist(), SENSORS)

    def test_preprocessing_and_class_ratio_fit_only_training(self):
        frame = pd.DataFrame({name: np.arange(30, dtype=float) for name in SENSORS})
        frame["machine_type"] = np.resize(["L", "M", "H"], 30)
        y = np.resize([1, 0, 0], 30)
        spec = next(s for s in catalog() if s["name"] == "xgb_d3_True")
        model = StudyModel(spec).fit(frame.iloc[:18], y[:18])
        self.assertEqual(model.model_.get_params()["scale_pos_weight"], 2)
        original = (
            model.prep_.named_transformers_["numeric"].named_steps["scale"].mean_.copy()
        )
        held = frame.iloc[18:].copy()
        held[SENSORS] = 1e6
        model.score(held)
        np.testing.assert_array_equal(
            original,
            model.prep_.named_transformers_["numeric"].named_steps["scale"].mean_,
        )


if __name__ == "__main__":
    unittest.main()
