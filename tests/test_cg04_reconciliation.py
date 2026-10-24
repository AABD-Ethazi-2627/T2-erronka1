import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
from contextlib import AsyncExitStack
from pathlib import Path
from unittest.mock import Mock, patch

import numpy as np
import pandas as pd
from httpx import ASGITransport, AsyncClient
from sklearn.model_selection import train_test_split

from cnc_guard.data import load_dataset, load_training_partitions
from cnc_guard.features import (
    FEATURE_COLUMNS,
    prepare_features,
    prepare_inference_features,
)
from cnc_guard.train import train_model
from scoring.preparation import SEED, features, split_development
from scoring.scope import INPUT_FEATURES
from scoring.score_api import create_app
from scripts.cg04_preparation import inspect_partitions
from scripts.package_model import package, validate_rf_partitions

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "data/ai4i2020_train.csv"


def fixture():
    """Synthetic sensors and labels; no row from the delivery dataset is fitted."""
    rows = 100
    return pd.DataFrame(
        {
            "machine_type": ["H", "M", "L", "M"] * 25,
            "air_temp_K": np.linspace(295, 305, rows),
            "process_temp_K": np.linspace(308, 318, rows),
            "rpm": np.arange(rows) * 10 + 1000,
            "torque_Nm": np.arange(rows) % 20 + 30,
            "tool_wear_min": np.arange(rows),
            "machine_failure": [0, 1] * 50,
            "failure_TWF": [0, 1] * 50,
        },
        index=np.arange(10000, 10100),
    )


class ReconciliationTests(unittest.IsolatedAsyncioTestCase):
    def test_real_source_membership_only_matches_active_and_reproduces_F3(self):
        frame = load_dataset(SOURCE)
        expected = split_development(frame)
        actual = load_training_partitions(SOURCE)
        for left, right in zip(expected, actual):
            self.assertEqual(left.index.tolist(), right.index.tolist())
        self.assertEqual([len(part) for part in actual], [5600, 1200, 1200])
        result = inspect_partitions(SOURCE)
        self.assertTrue(result["active"]["pairwise_disjoint"])
        self.assertTrue(result["active"]["complete_coverage"])
        self.assertEqual(result["active"]["excluded_rows_in_fit"], 0)
        for partition, digest in {
            "fit": "cdc6374b1a6e9c614f0c9f76b493a09109f125ae57f5fef66e2db9e078744c51",
            "development_validation": (
                "a5e9678ec3f4705d85eab6910cf3510685672b01075589df542a9dcfc42a3c53"
            ),
            "excluded_previously_inspected_test": (
                "b2c31c3b3f893f6d94b8e4bd1779f816f21652220028bfbd4efb6b2cedb8e07b"
            ),
        }.items():
            self.assertEqual(
                result["active"][partition]["ordered_index_sha256"], digest
            )
        self.assertEqual(
            result["PR43_exercise_80_20"]["previously_excluded_rows_in_fit"], 394
        )

    def test_unauthorized_source_is_rejected_before_fit(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "synthetic.csv"
            fixture().to_csv(path, index=False)
            with patch("cnc_guard.train.pipeline") as factory:
                with self.assertRaisesRegex(ValueError, "approved"):
                    train_model(path)
                factory.assert_not_called()

    def test_fit_and_score_never_receive_excluded_indices(self):
        frame = fixture()
        train, validation, excluded = split_development(frame)
        estimator = Mock()
        estimator.score.return_value = 0.5
        with (
            patch("cnc_guard.data.load_dataset", return_value=frame),
            patch("cnc_guard.train.pipeline", return_value=estimator),
        ):
            model, report = train_model("fixture-only")
        self.assertIs(model, estimator)
        fit_X, fit_y = estimator.fit.call_args.args
        score_X, score_y = estimator.score.call_args.args
        self.assertEqual(fit_X.index.tolist(), train.index.tolist())
        self.assertEqual(fit_y.index.tolist(), train.index.tolist())
        self.assertEqual(score_X.index.tolist(), validation.index.tolist())
        self.assertEqual(score_y.index.tolist(), validation.index.tolist())
        self.assertFalse(set(excluded.index) & (set(fit_X.index) | set(score_X.index)))
        self.assertEqual(report["artifact_role"], "CG04_DEVELOPMENT_ONLY")

    def test_real_pipeline_on_small_synthetic_fixture_only(self):
        frame = fixture()
        with patch("cnc_guard.data.load_dataset", return_value=frame):
            model, report = train_model("fixture-only")
        self.assertEqual(report["train_rows"], 70)
        self.assertEqual(report["validation_rows"], 15)
        self.assertEqual(report["excluded_rows"], 15)
        self.assertTrue(0 <= report["development_accuracy"] <= 1)
        train, _, _ = split_development(frame)
        X, _ = prepare_features(train.iloc[:3])
        inference = prepare_inference_features(train.iloc[:3][FEATURE_COLUMNS])
        pd.testing.assert_frame_equal(X, inference)
        pd.testing.assert_frame_equal(model["physics"].transform(X), features(X))
        np.testing.assert_array_equal(model.predict(X), model.predict(inference))

    def test_label_exclusion_and_sensor_contract(self):
        frame = fixture().iloc[:1]
        X, y = prepare_features(frame)
        self.assertEqual(list(X), INPUT_FEATURES)
        self.assertEqual(y.index.tolist(), frame.index.tolist())
        for field, value in [
            ("machine_failure", 1),
            ("failure_TWF", 0),
            ("raw_record", "csv"),
            ("timestamp", "2026-10-21"),
            ("rpm", -1),
            ("rpm", "1000"),
            ("air_temp_K", 0),
            ("process_temp_K", float("nan")),
            ("torque_Nm", float("inf")),
            ("machine_type", "X"),
        ]:
            invalid = X.copy()
            invalid[field] = value
            with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                prepare_inference_features(invalid)
        for invalid in (X.drop(columns="rpm"), X.iloc[:0]):
            with self.assertRaises(ValueError):
                prepare_inference_features(invalid)

    def test_active_report_accepted_exercise_and_missing_splits_rejected(self):
        frame = fixture()
        train, validation, excluded = split_development(frame)
        active = {
            "splits": {
                "train": train.index.tolist(),
                "validation": validation.index.tolist(),
                "excluded_previously_inspected_test": excluded.index.tolist(),
            }
        }
        validate_rf_partitions(active, frame)
        exercise_train, exercise_held = train_test_split(
            frame, test_size=0.2, random_state=SEED, stratify=frame.machine_failure
        )
        for invalid in (
            {},
            {**active, "artifact_role": "CG04_DEVELOPMENT_ONLY"},
            {
                "splits": {
                    "train": exercise_train.index.tolist(),
                    "validation": exercise_held.index.tolist(),
                }
            },
            {"splits": {**active["splits"], "train": excluded.index.tolist()}},
        ):
            with self.assertRaises(ValueError):
                validate_rf_partitions(invalid, frame)

    def test_packager_rejects_exercise_before_reading_artifacts(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "report.json").write_text(
                json.dumps({"artifact_role": "CG04_DEVELOPMENT_ONLY"})
            )
            # No RF/IF files or anomaly report: rejection must precede their reads.
            with self.assertRaisesRegex(ValueError, "exercises"):
                package(root / "bundle", root, root / "missing-anomaly")
            self.assertFalse((root / "bundle").exists())

    def test_packager_preserves_active_path_with_inert_fixture(self):
        from scoring.scope import APPROVED_SOURCE_SHA256, SCOPE

        frame = fixture()
        train, validation, excluded = split_development(frame)
        splits = {
            "train": train.index.tolist(),
            "validation": validation.index.tolist(),
            "excluded_previously_inspected_test": excluded.index.tolist(),
        }
        inert = b"synthetic inert bytes, never deserialized"
        digest = hashlib.sha256(inert).hexdigest()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            rf = root / "rf"
            anomaly = root / "anomaly"
            rf.mkdir()
            anomaly.mkdir()
            (rf / "rf.pkl").write_bytes(inert)
            (anomaly / "if.pkl").write_bytes(inert)
            common = {"source_sha256": APPROVED_SOURCE_SHA256, "model_sha256": digest}
            (rf / "report.json").write_text(
                json.dumps(
                    {
                        **common,
                        "splits": splits,
                        "versions": {"fixture": "inert"},
                        "validation_tuning_metrics": {"threshold": 0.5},
                    }
                )
            )
            (anomaly / "report.json").write_text(
                json.dumps({**common, "threshold": 0.6})
            )
            with patch(
                "scripts.package_model.load_training_source", return_value=frame
            ):
                manifest = package(root / "bundle", rf, anomaly)
            for name in ("rf.pkl", "if.pkl"):
                self.assertEqual((root / "bundle" / name).read_bytes(), inert)
                self.assertEqual(manifest["files"][name], digest)
            self.assertEqual(manifest["input_features"], SCOPE["input_features"])
            self.assertEqual(manifest["model_version"], "ai4i-current-state-v4")

    async def test_api_rejects_incomplete_scope_before_any_deserialization(self):
        with tempfile.TemporaryDirectory() as directory:
            manifest = Path(directory) / "manifest.json"
            manifest.write_text(json.dumps({"artifact_role": "CG04_DEVELOPMENT_ONLY"}))
            # This incomplete manifest fails scope validation, not a role guard.
            # The packager's separate tests above cover rejection by artifact_role.
            app = create_app(manifest)
            with patch("scoring.score_api.joblib.load") as load:
                lifespan = AsyncExitStack()
                try:
                    await lifespan.enter_async_context(app.router.lifespan_context(app))
                    async with AsyncClient(
                        transport=ASGITransport(app=app), base_url="http://testserver"
                    ) as client:
                        response = await client.get("/health")
                        self.assertEqual(response.status_code, 503)
                finally:
                    # Normal shutdown also runs if an assertion/request raises.
                    await lifespan.aclose()
                load.assert_not_called()

    def test_notebook_invokes_module_from_repo_root_without_pythonpath(self):
        notebook = json.loads(
            (ROOT / "notebooks/02_training_TEMPLATE.ipynb").read_text()
        )
        code = "\n".join(
            "".join(cell["source"])
            for cell in notebook["cells"]
            if cell["cell_type"] == "code"
        )
        env = os.environ.copy()
        env.pop("PYTHONPATH", None)
        result = subprocess.run(
            [sys.executable, "-I", "-c", code],
            cwd=ROOT / "notebooks",
            capture_output=True,
            text=True,
            check=False,
            env=env,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('"excluded_rows_in_fit": 0', result.stdout)


if __name__ == "__main__":
    unittest.main()
