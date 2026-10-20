import json
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from scoring.scope import (
    APPROVED_SOURCE_SHA256,
    INPUT_FEATURES,
    load_training_source,
    validate_bundle_scope,
)
from scoring.score_api import create_app


class CurrentStateScopeTests(unittest.TestCase):
    def test_only_original_reduced_training_source_is_accepted(self):
        frame = load_training_source()
        self.assertEqual(len(frame), 8000)
        self.assertEqual(len(INPUT_FEATURES), 6)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "other.csv"
            path.write_text("machine_failure,rpm\n1,100\n")
            with self.assertRaises(ValueError):
                load_training_source(path)

    def test_bundle_must_explicitly_disable_temporal_scope(self):
        good = {
            "prediction_scope": "AI4I_CURRENT_STATE_ONLY",
            "temporal_prediction_enabled": False,
            "training_source_sha256": APPROVED_SOURCE_SHA256,
            "input_features": INPUT_FEATURES,
            "score_semantics": "uncalibrated_current_state_score",
        }
        validate_bundle_scope(good)
        for key, value in [
            ("training_source_sha256", "other"),
            ("temporal_prediction_enabled", True),
            ("input_features", [*INPUT_FEATURES, "machine_failure"]),
        ]:
            with self.assertRaises(ValueError):
                validate_bundle_scope({**good, key: value})
        with self.assertRaises(ValueError):
            validate_bundle_scope({})

    def test_raw_source_and_all_labels_are_rejected_before_model_readiness(self):
        payload = json.loads(
            Path("contracts/examples/valid/telemetry.json").read_text()
        )
        payload["source"].pop("raw_record", None)
        with (
            tempfile.TemporaryDirectory() as directory,
            TestClient(create_app(Path(directory) / "missing")) as client,
        ):
            for label in [
                "machine_failure",
                "failure_TWF",
                "failure_HDF",
                "failure_PWF",
                "failure_OSF",
                "failure_RNF",
                "eta_minutes",
                "rul_minutes",
            ]:
                self.assertEqual(
                    client.post("/predict", json={**payload, label: 1}).status_code, 422
                )
            unsafe = {
                **payload,
                "source": {
                    **payload["source"],
                    "raw_record": "timestamp,machine,features,1,1,1",
                },
            }
            self.assertEqual(client.post("/predict", json=unsafe).status_code, 422)

    def test_inference_ignores_identity_and_observation_time(self):
        if not Path("outputs/api/manifest.json").exists():
            self.skipTest("Run the controlled training and package_model first")
        payload = json.loads(
            Path("contracts/examples/valid/telemetry.json").read_text()
        )
        with TestClient(create_app("outputs/api/manifest.json")) as client:
            first = client.post("/predict", json=payload)
            self.assertEqual(first.status_code, 200)
            changed = {
                **payload,
                "machine_id": "CNC-099",
                "timestamp": "2000-01-01T00:00:00Z",
            }
            second = client.post("/predict", json=changed)
            self.assertEqual(second.status_code, 200)
            self.assertEqual(
                first.json()["failure_score"], second.json()["failure_score"]
            )
            self.assertEqual(
                first.json()["anomaly_score"], second.json()["anomaly_score"]
            )
            self.assertFalse(first.json()["temporal_prediction_enabled"])
            self.assertEqual(
                first.json()["score_semantics"], "uncalibrated_current_state_score"
            )
            self.assertEqual(
                client.get("/health").json()["prediction_scope"],
                "AI4I_CURRENT_STATE_ONLY",
            )

    def test_deployable_nifi_snapshot_contains_the_verified_script(self):
        snapshot = json.loads(Path("nifi-flows/cnc_lab_completed.json").read_text())
        matches = []

        def visit(value):
            if isinstance(value, dict):
                for item in value.values():
                    if (
                        isinstance(item, str)
                        and "event.source" in item
                        and "names.eachWithIndex" in item
                    ):
                        matches.append(item)
                    else:
                        visit(item)
            elif isinstance(value, list):
                for item in value:
                    visit(item)

        visit(snapshot)
        self.assertEqual(len(matches), 1)
        self.assertEqual(
            matches[0].strip(),
            Path("nifi-flows/normalize_csv.groovy").read_text().strip(),
        )

    def test_preflight_rejects_legacy_bundle_even_with_matching_hashes(self):
        import hashlib

        from scripts.integration_preflight import inspect_checkout

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            models = root / "outputs/api"
            models.mkdir(parents=True)
            files = {}
            for name in ["rf.pkl", "if.pkl"]:
                (models / name).write_bytes(b"fixture-not-loaded")
                files[name] = hashlib.sha256(b"fixture-not-loaded").hexdigest()
            (models / "manifest.json").write_text(json.dumps({"files": files}))
            checks = inspect_checkout(root)
            self.assertTrue(checks["model_bundle_hashes_match"])
            self.assertFalse(checks["model_scope_valid"])

    def test_training_uses_the_same_bytes_that_were_verified(self):
        from unittest.mock import patch

        original = Path("data/ai4i2020_train.csv").read_bytes()
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "training.csv"
            source.write_bytes(original)
            read = Path.read_bytes

            def swapped(path):
                value = read(path)
                if path == source:
                    source.write_text("machine_failure,rpm\n1,100\n")
                return value

            with patch.object(Path, "read_bytes", swapped):
                self.assertEqual(len(load_training_source(source)), 8000)
