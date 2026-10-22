import unittest

import numpy as np
import pandas as pd
from threadpoolctl import threadpool_limits

from scripts.seasonal_v2 import future_labels, generate, predictor_columns


class SeasonalV2Tests(unittest.TestCase):
    def test_label_excludes_current_and_censors_unobserved_future(self):
        onset = np.zeros(60, dtype=int)
        onset[24] = 1
        labels = future_labels(onset)
        self.assertEqual(labels[0], 1)
        self.assertEqual(labels[24], 0)
        self.assertTrue(np.isnan(labels[-24:]).all())

    def test_reproducible_causal_history_and_no_label_predictors(self):
        a = generate(start="2024-01-01", days=8, machines=2, seed=7)
        b = generate(start="2024-01-01", days=8, machines=2, seed=7)
        pd.testing.assert_frame_equal(a, b)
        self.assertEqual(len(a), 8 * 24 * 2)
        for _, machine in a.groupby("machine_id"):
            self.assertTrue(np.isnan(machine.iloc[0].torque_mean_24h))
            self.assertAlmostEqual(
                machine.iloc[1].torque_mean_24h, machine.iloc[0].torque_Nm
            )
            self.assertTrue(machine.tail(24).failure_next_24h.isna().all())
        columns = predictor_columns(temporal=True)
        self.assertFalse(
            {
                "machine_id",
                "failure_next_24h",
                "simulated_fault_onset",
                "latent_damage",
                "seed",
                "source_kind",
                "season",
            }
            & set(columns)
        )
        self.assertTrue(
            np.isfinite(a[["air_temp_K", "rpm", "torque_Nm", "tool_wear_min"]])
            .all()
            .all()
        )
        self.assertTrue(a.source_kind.eq("synthetic_seasonal_v2").all())

    def test_summer_warmer_and_separate_seed_machine_identity(self):
        a = generate(start="2024-01-01", days=366, machines=1, seed=7)
        summer = a.loc[a.timestamp.dt.month.isin([6, 7, 8]), "air_temp_K"].mean()
        winter = a.loc[a.timestamp.dt.month.isin([12, 1, 2]), "air_temp_K"].mean()
        self.assertGreater(summer, winter + 5)
        b = generate(start="2024-01-01", days=3, machines=1, seed=8)
        self.assertFalse(set(a.machine_id) & set(b.machine_id))

    @threadpool_limits.wrap(limits=1)
    def test_model_ignores_outcomes_and_identity(self):
        from scripts.train_seasonal_v2 import make_model

        data = generate(days=45, machines=2, seed=42).dropna(
            subset=["failure_next_24h"]
        )
        model = make_model("seasonal", iterations=5).fit(data, data.failure_next_24h)
        scores = model.predict_proba(data)[:, 1]
        changed = data.copy()
        changed["failure_next_24h"] = 1 - changed.failure_next_24h
        changed["simulated_fault_onset"] = 10000
        changed["latent_damage"] = -999
        changed["machine_id"] = "OTHER"
        np.testing.assert_array_equal(scores, model.predict_proba(changed)[:, 1])

    def test_event_audit_counts_onsets_not_overlapping_positive_hours(self):
        from scripts.report_seasonal_v2 import event_audit

        times = pd.date_range("2025-01-01", periods=72, freq="h", tz="UTC")
        frame = pd.DataFrame(
            {"timestamp": times, "machine_id": "SIM-X", "simulated_fault_onset": 0}
        )
        frame.loc[30, "simulated_fault_onset"] = 1
        predictions = frame.iloc[:48][["timestamp", "machine_id"]].copy()
        predictions["score"] = 0.0
        predictions.loc[10, "score"] = 0.9
        audit = event_audit(frame, predictions, 0.5)
        self.assertEqual(audit["eligible_onsets"], 1)
        self.assertEqual(audit["detected_onsets"], 1)
        self.assertEqual(audit["median_first_alert_lead_hours"], 20)
        self.assertEqual(audit["alert_hours"], 1)

    def test_dataset_packaging_rejects_changed_partition(self):
        import hashlib
        import json
        import tempfile
        from pathlib import Path

        from scripts.package_seasonal_v2 import package

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            datasets = {}
            for name in ["train", "validation", "evaluation", "stress"]:
                path = root / f"{name}.parquet"
                path.write_bytes(b"controlled-fixture")
                datasets[name] = {
                    "sha256": hashlib.sha256(path.read_bytes()).hexdigest()
                }
            report = {
                "scenario": {},
                "datasets": datasets,
                "ai4i_source_sha256": "test",
                "selection": {"selected_by_validation_ap": "test-model"},
            }
            (root / "report.json").write_text(json.dumps(report))
            bundle = package(root)
            original = bundle.read_bytes()
            (root / "train.parquet").write_bytes(b"corrupt")
            with self.assertRaises(ValueError):
                package(root)
            self.assertEqual(original, bundle.read_bytes())
