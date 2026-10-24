import unittest

import numpy as np
import pandas as pd
from sklearn.model_selection import StratifiedKFold

from scoring.preparation import SENSORS
from scripts.experiment_alternatives import blend, candidates, fit_oof


class AlternativesTests(unittest.TestCase):
    def test_real_fold_fits_ignore_ids_and_all_label_columns(self):
        rng = np.random.default_rng(42)
        frame = pd.DataFrame(rng.uniform(1, 20, (80, 5)), columns=SENSORS)
        frame["machine_type"] = np.tile(["H", "M", "L", "L"], 20)
        frame["machine_failure"] = np.tile([0, 0, 0, 1], 20)
        frame["machine_id"] = frame.machine_failure.astype(str)
        frame["failure_TWF"] = frame.machine_failure
        folds = list(StratifiedKFold(2).split(frame, frame.machine_failure))
        model = candidates(quick=True)["rf_reference"]
        first = fit_oof(model, frame, folds)
        changed = frame.copy()
        changed["machine_id"] = "UNSEEN"
        changed["failure_TWF"] = 10000
        np.testing.assert_array_equal(first, fit_oof(model, changed, folds))
        self.assertEqual(first.shape, (80,))
        self.assertTrue(np.isfinite(first).all())

    def test_blend_rejects_invalid_weights_and_preserves_rows(self):
        scores = {"a": np.array([0.2, 0.8]), "b": np.array([0.6, 0.4])}
        np.testing.assert_allclose(blend(scores, ["a", "b"]), [0.4, 0.6])
        with self.assertRaises(ValueError):
            blend(scores, [])
        with self.assertRaises(ValueError):
            blend({"a": np.array([0.1]), "b": np.array([0.2, 0.4])}, ["a", "b"])

    def test_nested_selection_has_disjoint_outer_evaluation_rows(self):
        from scripts.experiment_alternatives_nested import nested_compare

        rng = np.random.default_rng(7)
        frame = pd.DataFrame(rng.uniform(1, 20, (80, 5)), columns=SENSORS)
        frame["machine_type"] = "L"
        frame["machine_failure"] = np.tile([0, 0, 0, 1], 20)
        pool = candidates(quick=True)
        result, predictions = nested_compare(
            frame, pool, outer_splits=2, inner_splits=2
        )
        self.assertTrue(predictions.groupby("model").size().eq(80).all())
        self.assertTrue(np.isfinite(predictions.score).all())
        held = []
        for fold in result["outer_folds"]:
            self.assertFalse(set(fold["fit"]) & set(fold["held"]))
            held.extend(fold["held"])
            for inner in fold["inner_folds"]:
                self.assertTrue(set(inner["fit"]).issubset(fold["fit"]))
                self.assertTrue(set(inner["held"]).issubset(fold["fit"]))
                self.assertFalse(set(inner["fit"]) & set(inner["held"]))
            self.assertEqual(fold["selected"], "rf_reference")
        self.assertEqual(sorted(held), sorted(frame.index))

    def test_cost_cutoff_changes_with_false_negative_cost(self):
        from scripts.report_alternatives import cost_cutoff

        y = np.array([0, 0, 1, 1])
        scores = np.array([0.1, 0.8, 0.2, 0.9])
        self.assertEqual(cost_cutoff(y, scores, 100, 1200), 0.2)
        self.assertEqual(cost_cutoff(y, scores, 2000, 10), 0.9)
