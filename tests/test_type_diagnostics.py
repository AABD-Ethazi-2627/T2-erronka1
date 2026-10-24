import json
import tempfile
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

from scoring.preparation import SEED, split_development
from scoring.scope import APPROVED_SOURCE_SHA256, load_training_source
from scripts.report_type_diagnostics import build_report, diagnostic, run

SOURCE = Path(__file__).resolve().parents[1] / "data/ai4i2020_train.csv"


class TypeDiagnosticsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.frame = load_training_source(SOURCE)
        cls.train, cls.validation, cls.excluded = split_development(cls.frame)

    def setUp(self):
        self.scores = pd.DataFrame(
            {
                "source_row_index": self.validation.index,
                "label": self.validation.machine_failure.to_numpy(),
                "rf_score": np.full(len(self.validation), 0.25),
            }
        )
        self.experiment = {
            "source_sha256": APPROVED_SOURCE_SHA256,
            "task": "contemporaneous_state_classification",
            "seed": SEED,
            "splits": {
                "train": self.train.index.tolist(),
                "validation": self.validation.index.tolist(),
                "excluded_previously_inspected_test": self.excluded.index.tolist(),
            },
            "validation_tuning_metrics": {"threshold": 0.25},
        }

    def report(self):
        return build_report(
            SOURCE,
            self.scores.to_csv(index=False).encode(),
            json.dumps(self.experiment).encode(),
        )

    def test_hand_computed_counts_and_threshold_equality(self):
        result = diagnostic([0, 0, 1, 1], [0.1, 0.5, 0.5, 0.2], 0.5)
        for key in ("tp", "fn", "fp", "tn"):
            self.assertEqual(result[key], 1)
        self.assertEqual(result["false_positive_rate"], 0.5)
        self.assertEqual(result["false_negative_rate"], 0.5)

    def test_csv_preserves_real_threshold_boundary_for_source_row_7763(self):
        cutoff = 0.19082281465428477
        self.experiment["validation_tuning_metrics"]["threshold"] = cutoff
        self.assertEqual(self.validation.loc[7763, "machine_failure"], 1)
        self.assertEqual(self.validation.loc[7763, "machine_type"], "L")
        self.scores["rf_score"] = 0.0
        for score, tp in (
            (np.nextafter(cutoff, -np.inf), 0),
            (cutoff, 1),
            (np.nextafter(cutoff, np.inf), 1),
        ):
            with self.subTest(score=score):
                self.scores.loc[self.scores.source_row_index == 7763, "rf_score"] = (
                    score
                )
                validation_raw = self.scores.to_csv(index=False).encode()
                self.assertIn(f"7763,1,{score!r}".encode(), validation_raw)
                result = build_report(
                    SOURCE, validation_raw, json.dumps(self.experiment).encode()
                )
                for group, positives in (
                    (result["overall"], 41),
                    (result["by_machine_type"]["L"], 31),
                ):
                    self.assertEqual(group["tp"], tp)
                    self.assertEqual(group["fn"], positives - tp)
                    self.assertEqual(group["alerts"], tp)
                    self.assertEqual(group["fp"], 0)
                    self.assertEqual(group["tn"], group["negatives"])
                    self.assertEqual(
                        group["false_negative_rate"], (positives - tp) / positives
                    )

    def test_undefined_rates_are_null(self):
        for labels, scores in [([], []), ([0, 0], [0.1, 0.2])]:
            with self.subTest(labels=labels):
                result = diagnostic(labels, scores, 0.5)
                self.assertIsNone(result["false_negative_rate"])
                self.assertIsNone(result["recall"])
                self.assertIsNone(result["precision"])
                json.dumps(result, allow_nan=False)
        self.assertIsNone(diagnostic([1], [0.9], 0.5)["false_positive_rate"])

    def test_subgroups_reconcile_to_overall_and_order_is_irrelevant(self):
        result = self.report()
        self.scores = self.scores.sample(frac=1, random_state=9)
        shuffled = self.report()
        self.assertEqual(result["by_machine_type"], shuffled["by_machine_type"])
        for key in ("rows", "positives", "negatives", "alerts", "tp", "fn", "fp", "tn"):
            self.assertEqual(
                sum(g[key] for g in result["by_machine_type"].values()),
                result["overall"][key],
            )
        self.assertEqual(result["overall"]["rows"], 1200)
        self.assertEqual(result["overall"]["positives"], 41)
        self.assertFalse(result["scope"]["temporal_prediction_enabled"])

    def test_reject_wrong_source_task_or_seed(self):
        for key, value in (
            ("source_sha256", "0" * 64),
            ("task", "forecast24h"),
            ("seed", 99),
        ):
            with self.subTest(key=key):
                old = self.experiment[key]
                self.experiment[key] = value
                with self.assertRaisesRegex(ValueError, "source, task or seed"):
                    self.report()
                self.experiment[key] = old

    def test_reject_modified_source_bytes(self):
        with tempfile.TemporaryDirectory() as directory:
            changed = Path(directory) / "changed.csv"
            changed.write_bytes(SOURCE.read_bytes() + b"\n")
            with self.assertRaisesRegex(ValueError, "approved reduced AI4I"):
                build_report(changed, b"", b"{}")

    def test_reject_changed_split_including_excluded_test(self):
        for key in self.experiment["splits"]:
            with self.subTest(key=key):
                old = self.experiment["splits"][key]
                self.experiment["splits"][key] = old[1:]
                with self.assertRaisesRegex(ValueError, "partitions"):
                    self.report()
                self.experiment["splits"][key] = old

    def test_reject_duplicates_missing_rows_and_excluded_test_row(self):
        original = self.scores.copy()
        for replacement in (
            original.iloc[1:],
            pd.concat([original, original.iloc[:1]]),
        ):
            self.scores = replacement
            with self.assertRaisesRegex(ValueError, "indices"):
                self.report()
        self.scores = original.copy()
        self.scores.loc[0, "source_row_index"] = self.excluded.index[0]
        with self.assertRaisesRegex(ValueError, "indices"):
            self.report()

    def test_reject_fractional_index(self):
        self.scores["source_row_index"] = self.scores.source_row_index.astype(float)
        self.scores.loc[0, "source_row_index"] += 0.5
        with self.assertRaisesRegex(ValueError, "indices"):
            self.report()

    def test_reject_wrong_labels_and_bad_scores(self):
        self.scores.loc[0, "label"] = 1 - self.scores.loc[0, "label"]
        with self.assertRaisesRegex(ValueError, "labels do not match"):
            self.report()
        self.scores.loc[0, "label"] = self.validation.machine_failure.iloc[0]
        for value in (np.nan, np.inf, -0.1, 1.1, "bad"):
            with self.subTest(score=value):
                self.scores["rf_score"] = value
                with self.assertRaisesRegex(ValueError, "labels or RF scores"):
                    self.report()

    def test_reject_invalid_cutoffs_and_extra_column(self):
        for value in (None, True, "0.25", float("nan"), -1, 2):
            with self.subTest(cutoff=value):
                self.experiment["validation_tuning_metrics"]["threshold"] = value
                with self.assertRaisesRegex(ValueError, "threshold"):
                    self.report()
        self.experiment["validation_tuning_metrics"]["threshold"] = 0.25
        self.scores["operator_id"] = "not permitted in this evidence"
        with self.assertRaisesRegex(ValueError, "columns"):
            self.report()

    def test_writer_preserves_prior_evidence(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            self.scores.to_csv(folder / "validation.csv", index=False)
            (folder / "report.json").write_text(json.dumps(self.experiment))
            output = folder / "result.json"
            run(SOURCE, folder, output)
            before = output.read_bytes()
            with self.assertRaises(FileExistsError):
                run(SOURCE, folder, output)
            self.assertEqual(before, output.read_bytes())
            self.assertEqual(json.loads(before)["overall"]["rows"], 1200)


if __name__ == "__main__":
    unittest.main()
