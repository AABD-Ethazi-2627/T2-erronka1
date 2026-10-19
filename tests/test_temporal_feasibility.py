import unittest

import pandas as pd

from scripts.audit_temporal_feasibility import audit


class TemporalFeasibilityTests(unittest.TestCase):
    def frame(self):
        return pd.DataFrame(
            {
                "timestamp": pd.to_datetime(
                    [
                        "2026-01-01T00:00:00Z",
                        "2026-01-01T00:00:00Z",
                        "2026-01-01T00:00:30Z",
                        "2026-01-01T00:01:00Z",
                    ]
                ),
                "machine_id": ["A"] * 4,
                "machine_type": ["L", "H", "L", "L"],
                "air_temp_K": [300.0, 301.0, 300.0, 300.0],
                "process_temp_K": [310.0] * 4,
                "rpm": [1500.0] * 4,
                "torque_Nm": [40.0, 50.0, 40.0, 40.0],
                "tool_wear_min": [100.0, 200.0, 20.0, 30.0],
                "machine_failure": [0, 1, 0, 1],
            }
        )

    def test_conflicts_and_unknown_provenance_block_eta_labels(self):
        result = audit(self.frame())
        self.assertEqual(result["conflicting_machine_timestamp_groups"], 1)
        self.assertEqual(result["machines_with_multiple_types"], 1)
        self.assertFalse(result["eta_training_ready"])
        self.assertIsNone(result["eta_minutes"])
        self.assertEqual(result["temporal_criticality"], "UNKNOWN")
        self.assertGreater(result["next_positive_diagnostic"]["censored_rows"], 0)

    def test_consistent_sampling_does_not_prove_physical_onsets(self):
        frame = self.frame().iloc[[0, 2, 3]].copy()
        result = audit(frame)
        self.assertEqual(result["conflicting_machine_timestamp_groups"], 0)
        self.assertFalse(result["eta_training_ready"])
        self.assertIn("No verified physical machine identity", result["blockers"])
        self.assertIn(
            "No verified failure onset and maintenance/cycle log", result["blockers"]
        )

    def test_timestamped_replay_blocks_eta_even_with_attested_provenance(self):
        import numpy as np

        base = self.frame().iloc[[0]].copy()
        data = pd.concat([base] * 4000, ignore_index=True)
        data["timestamp"] = pd.date_range(
            "2026-01-01", periods=4000, freq="30s", tz="UTC"
        )
        data["torque_Nm"] = 40 + np.tile(np.arange(2000), 2) / 1000
        result = audit(data, verified_identity=True, verified_onsets=True)
        self.assertTrue(result["ordered_rows_repeat_every_2000_excluding_timestamp"])
        self.assertFalse(result["eta_training_ready"])
        self.assertIn(
            "Exactly repeated 2000-row sequence with new timestamps", result["blockers"]
        )
