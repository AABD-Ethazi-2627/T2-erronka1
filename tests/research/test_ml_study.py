"""Research-only synthetic regressions; never train or score the AI4I source."""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pandas as pd

from scoring.preparation import SENSORS
from scripts.ml_study import (
    choose_threshold,
    folds,
    metrics,
    seal,
    verify,
    write_json,
)
from scripts.ml_study_models import CORE, StudyCalibrated, StudyModel, catalog


class StudyProtocolTests(unittest.TestCase):
    def test_seal_binds_folds_environment_and_rejects_corruption(self):
        frame = pd.DataFrame({"machine_failure": np.resize([1, 0, 0, 0], 120)})
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            smoke = root / "smoke.json"
            write_json(smoke, [{"status": "complete"}] * 50)
            output = root / "sealed"
            with patch("scripts.ml_study.source_train", return_value=(frame, {})):
                seal(output, smoke)
            manifest = verify(output)
            self.assertEqual(len(manifest["outer"]), 3)
            self.assertEqual(len(manifest["outer"][0]["inner"]), 3)
            self.assertEqual(
                manifest["pilot"]["fit_rows"],
                manifest["outer"][0]["inner"][0]["fit"],
            )
            with self.assertRaises(FileExistsError):
                with patch("scripts.ml_study.source_train", return_value=(frame, {})):
                    seal(output, smoke)
            (output / "manifest.json").write_text("{}")
            with self.assertRaisesRegex(ValueError, "seal changed"):
                verify(output)

    def test_calibrator_reserves_only_its_own_training_rows(self):
        rng = np.random.default_rng(14)
        frame = pd.DataFrame(rng.normal(size=(120, 5)), columns=SENSORS)
        frame["machine_type"] = np.resize(["L", "M", "H"], 120)
        y = np.resize([1, 0, 0, 0], 120)
        spec = next(s for s in catalog() if s["name"] == "cart_depth5")
        for method in ("raw75", "sigmoid", "isotonic"):
            model = StudyCalibrated(spec, method).fit(frame, y)
            self.assertEqual(
                model.fit_positive_support_ + model.calibration_positive_support_,
                int(y.sum()),
            )
            self.assertLessEqual(
                abs(model.calibration_positive_support_ - int(y.sum()) * 0.25), 0.5
            )
            self.assertTrue(np.isfinite(model.score(frame.iloc[:3])).all())

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
