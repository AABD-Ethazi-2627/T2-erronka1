"""Independent report arithmetic on fixtures; no model fitting."""

import tempfile
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

from scripts.audit_ml_study import average_precision, counts
from scripts.ml_study import digest, write_json
from scripts.report_ml_study import load_rows, paired_bootstrap


class ReportAuditTests(unittest.TestCase):
    def test_xgboost_csv_restores_native_float32_before_thresholds(self):
        native = np.array(
            [0.7, np.nextafter(np.float32(0.7), np.float32(1)), 0.15], dtype=np.float32
        )
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            task = {"model": "xgb_fixture", "held": [1, 2, 3]}
            write_json(root / "task.json", task)
            pd.DataFrame(
                {"source_row_index": [1, 2, 3], "label": [1, 0, 1], "score": native}
            ).to_csv(root / "scores.csv", index=False)
            write_json(
                root / "result.json",
                {
                    "scores_sha256": digest(root / "scores.csv"),
                    "task_sha256": digest(root / "task.json"),
                },
            )
            decoded = load_rows([(task, root)])
            np.testing.assert_array_equal(
                decoded.score.to_numpy(), native.astype(np.float64)
            )
            self.assertFalse(bool(decoded.score.iloc[0] >= 0.70))
            self.assertTrue(bool(decoded.score.iloc[1] >= 0.70))

    def test_independent_counts_preserve_inclusive_boundaries(self):
        rows = [
            {"label": "1", "score": "0.15", "threshold": "0.15"},
            {"label": "0", "score": str(np.nextafter(0.15, 0)), "threshold": "0.15"},
            {"label": "1", "score": "0.7", "threshold": "0.7"},
            {"label": "0", "score": "0.8", "threshold": "0.9"},
        ]
        self.assertEqual(
            counts(rows, None), {"tp": 2, "fp": 0, "fn": 0, "tn": 2, "cost_per_1000": 0}
        )
        self.assertEqual(counts(rows, 0.15)["fp"], 1)

    def test_independent_ap_handles_ties_and_constant_scores(self):
        rows = [
            {"label": y, "score": p}
            for y, p in zip([1, 0, 1, 0], [0.9, 0.9, 0.3, 0.1], strict=True)
        ]
        self.assertAlmostEqual(average_precision(rows), 7 / 12)
        self.assertEqual(
            average_precision([{"label": y, "score": 0.2} for y in [1, 0, 1, 0]]), 0.5
        )

    def test_bootstrap_pairs_rows_and_does_not_invent_independence(self):
        rows = pd.DataFrame(
            {
                "source_row_index": [4, 5, 6, 7],
                "label": [0, 1, 0, 1],
                "prediction": [False, True, True, False],
            }
        )
        result = paired_bootstrap(rows, rows.iloc[::-1], "prediction")
        self.assertEqual(result["cost_delta_per_1000_95"], [0, 0])
        self.assertEqual(result["recall_delta_95"], [0, 0])
        self.assertTrue(result["conditional_only"])
        with self.assertRaisesRegex(ValueError, "identical rows"):
            paired_bootstrap(rows, rows.iloc[:3], "prediction")


if __name__ == "__main__":
    unittest.main()
