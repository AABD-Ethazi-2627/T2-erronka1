"""Guard against leakage, reversed anomaly scores and suppression of risk alerts."""

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.dummy import DummyClassifier

from scoring.inference import load_bundle, predict_signals
from scoring.model_features import engineer_features
from scripts import refine_model as refine


class RefinementTests(unittest.TestCase):
    def test_f2_favors_recall_and_counts_errors(self):
        y = [0, 0, 0, 1, 1]
        s = [0.1, 0.2, 0.6, 0.4, 0.9]
        # Recovering both failures at .4 gives F2=10/11 despite one false alarm.
        self.assertAlmostEqual(refine.best_threshold(y, s, beta=2), 0.4)
        result = refine.metrics(y, s, 0.4)
        self.assertEqual((result["fp"], result["fn"], result["tp"]), (1, 0, 2))
        self.assertAlmostEqual(result["f1"], 0.8)
        self.assertAlmostEqual(result["f2"], 10 / 11)
        self.assertAlmostEqual(
            refine.best_threshold([0, 0, 1], [0.1, 0.6, 0.9], beta=1), 0.9
        )

    def test_features_do_not_use_labels_or_machine_id(self):
        df = pd.DataFrame(
            {
                "air_temp_K": [300.0],
                "process_temp_K": [310.0],
                "rpm": [1500.0],
                "torque_Nm": [40.0],
                "tool_wear_min": [100.0],
                "machine_type": ["L"],
                "machine_id": ["CNC-001"],
                "machine_failure": [1],
                "failure_PWF": [1],
            }
        )
        x = engineer_features(df)
        self.assertAlmostEqual(x["temp_diff"].iloc[0], 10.0)
        self.assertAlmostEqual(x["power_W"].iloc[0], 2000 * np.pi)
        df["machine_failure"] = 0
        df["failure_PWF"] = 0
        df["machine_id"] = "OTHER"
        pd.testing.assert_frame_equal(x, engineer_features(df))
        self.assertNotIn("machine_failure", x)

    def test_anomaly_training_uses_only_normal_training_rows(self):
        df = pd.read_csv(refine.ROOT / "data/ai4i2020_train.csv").iloc[:400]
        anomaly, provenance = refine.fit_anomaly(df)
        self.assertEqual(
            provenance["fit_row_indices"], df.index[df.machine_failure.eq(0)].tolist()
        )
        scores = refine.anomaly_scores(anomaly, df.iloc[:5])
        np.testing.assert_array_equal(scores, -anomaly.score_samples(df.iloc[:5]))

    def test_loader_rejects_corruption_before_unpickling(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp)
            (p / "bundle.pkl").write_bytes(b"not a pickle")
            (p / "report.json").write_text(
                json.dumps({"artifacts": {"bundle.pkl": "wrong"}})
            )
            with self.assertRaisesRegex(ValueError, "hash"):
                load_bundle(p)

    def test_loader_rejects_incompatible_versions_before_unpickling(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp)
            content = b"not a pickle"
            (p / "bundle.pkl").write_bytes(content)
            (p / "report.json").write_text(
                json.dumps(
                    {
                        "artifacts": {
                            "bundle.pkl": hashlib.sha256(content).hexdigest()
                        },
                        "versions": {
                            "sklearn": "0.0.0",
                            "numpy": "0.0.0",
                            "pandas": "0.0.0",
                            "joblib": "0.0.0",
                        },
                    }
                )
            )
            with self.assertRaisesRegex(ValueError, "version"):
                load_bundle(p)

    def test_risk_and_anomaly_are_independent_and_threshold_equality_alerts(self):
        from sklearn.ensemble import IsolationForest

        x = pd.DataFrame({"x": [0.0, 1.0, 2.0, 3.0]})
        rf = DummyClassifier(strategy="prior").fit(x, [0, 0, 1, 1])
        anomaly = IsolationForest(random_state=42).fit(x)
        bundle = {
            "rf_models": {"f1": rf, "f2": rf},
            "risk_thresholds": {"f1": 0.5, "f2": 0.5},
            "isolation_forest": anomaly,
            "anomaly_threshold": 100.0,
            "model_version": "test",
        }
        result = predict_signals(bundle, x, policy="f2")[0]
        self.assertTrue(result["risk_alert"])
        self.assertFalse(result["anomaly_alert"])
        self.assertEqual(result["policy"], "f2")
        bundle["risk_thresholds"]["f2"] = 0.6
        bundle["anomaly_threshold"] = -100.0
        result = predict_signals(bundle, x, policy="f2")[0]
        self.assertFalse(result["risk_alert"])
        self.assertTrue(result["anomaly_alert"])
        with self.assertRaises(ValueError):
            predict_signals(bundle, x, policy="unknown")


if __name__ == "__main__":
    unittest.main()
