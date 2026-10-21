"""Contract regression only: synthetic events, ASGI transport, no trained model."""

import copy
import io
import json
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

import numpy as np
from api_client import api_client

from scoring.score_api import create_app
from scripts.cg14_scoring_bridge import main, to_telemetry
from scripts.validate_contracts import validators


def cg14_event():
    event = json.loads(Path("contracts/examples/valid/telemetry.json").read_text())
    event["source"].update(
        kind="cg14-kafka-lab",
        uri="fixture://cg14/offline",
        record_ref="offline:1",
        raw_record="2026-10-15T08:09:06Z,CNC-049,L,300.5,309.8,1345,62.7,153,1,1,0,0,0,0",
    )
    return event


def bridge(event):
    return to_telemetry(
        event, expected_source_kind="cg14-kafka-lab", source_kind="lab_fixture"
    )


class Cg14BridgeTests(unittest.TestCase):
    def test_explicit_mapping_retains_identity_and_original_audit_event(self):
        event = cg14_event()
        original = copy.deepcopy(event)
        payload = bridge(event)
        validators()["telemetry"].validate(payload)
        self.assertEqual(event, original)
        self.assertEqual(payload["event_id"], event["event_id"])
        self.assertEqual(payload["source"]["record_ref"], event["source"]["record_ref"])
        self.assertEqual(payload["source"]["kind"], "lab_fixture")
        self.assertNotIn("raw_record", payload["source"])
        self.assertNotIn("machine_failure", payload)

    def test_canonical_event_needs_no_alias_and_replays_identically(self):
        event = cg14_event()
        event["source"]["kind"] = "lab_fixture"
        first = to_telemetry(event)
        self.assertEqual(first, to_telemetry(event))
        self.assertEqual(first, to_telemetry(first))

    def test_alias_is_exact_and_never_implicit(self):
        event = cg14_event()
        for options in (
            {},
            {"source_kind": "lab_fixture"},
            {"expected_source_kind": "cg14-kafka-lab"},
            {"expected_source_kind": "other", "source_kind": "lab_fixture"},
            {"expected_source_kind": "cg14-kafka-lab", "source_kind": "unknown"},
        ):
            with self.subTest(options=options), self.assertRaises(ValueError):
                to_telemetry(event, **options)

    def test_forbidden_fields_and_invalid_measurements_are_not_repaired(self):
        changes = [
            ("machine_failure", 1),
            ("failure_TWF", 0),
            ("eta_minutes", 10),
            ("air_temp_K", 0.0),
            ("process_temp_K", -1.0),
            ("rpm", -1.0),
            ("rpm", True),
            ("rpm", float("nan")),
            ("rpm", float("inf")),
            ("timestamp", "2026-02-30T00:00:00Z"),
            ("schema_version", "unknown"),
            ("event_id", "invalid"),
        ]
        for field, value in changes:
            with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                bridge({**cg14_event(), field: value})
        for field, value in (("raw_record", None), ("unknown", "no")):
            event = cg14_event()
            event["source"][field] = value
            with self.subTest(source_field=field), self.assertRaises(ValueError):
                bridge(event)

    def test_cli_outputs_only_request_and_fails_without_payload_leak(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "event.json"
            path.write_text(json.dumps(cg14_event()))
            output = io.StringIO()
            with redirect_stdout(output):
                code = main(
                    [
                        str(path),
                        "--expected-source-kind",
                        "cg14-kafka-lab",
                        "--source-kind",
                        "lab_fixture",
                    ]
                )
            self.assertEqual(code, 0)
            self.assertEqual(json.loads(output.getvalue()), bridge(cg14_event()))
            for raw in (b"invalid-json-private-content", b"x" * 32769):
                path.write_bytes(raw)
                output, errors = io.StringIO(), io.StringIO()
                with redirect_stdout(output), redirect_stderr(errors):
                    self.assertEqual(main([str(path)]), 1)
                self.assertEqual(output.getvalue(), "")
                self.assertNotIn("private-content", errors.getvalue())


class Cg14BridgeApiTests(unittest.IsolatedAsyncioTestCase):
    async def test_projected_request_scores_with_deterministic_model_doubles(self):
        class RiskDouble:
            def predict_proba(self, frame):
                self.frame = frame
                return np.array([[0.2, 0.8]])

        class AnomalyDouble:
            def score_samples(self, frame):
                return np.array([-0.5])

        prediction = json.loads(
            Path("contracts/examples/valid/prediction.json").read_text()
        )
        with tempfile.TemporaryDirectory() as directory:
            app = create_app(Path(directory) / "missing.json")
            async with api_client(app) as client:
                # Test doubles exercise response construction, not model quality.
                risk = RiskDouble()
                app.state.models = {"rf.pkl": risk, "if.pkl": AnomalyDouble()}
                app.state.manifest = {
                    key: prediction[key]
                    for key in (
                        "risk_threshold",
                        "anomaly_threshold",
                        "policy",
                        "model_version",
                    )
                }
                app.state.manifest["files"] = {
                    "rf.pkl": prediction["model_artifact_sha256"]
                }
                payload = bridge(cg14_event())
                response = await client.post("/predict", json=payload)
                self.assertEqual(response.status_code, 200, response.text)
                result = response.json()
                validators()["prediction"].validate(result)
                self.assertEqual(result["event_id"], payload["event_id"])
                self.assertEqual(result["failure_score"], 0.8)
                self.assertFalse(result["temporal_prediction_enabled"])
                self.assertNotIn("raw_record", result["source"])
                self.assertEqual(len(risk.frame.columns), 6)
                self.assertNotIn("machine_failure", risk.frame.columns)

    async def test_real_asgi_validation_accepts_bridge_but_stays_unready_without_models(
        self,
    ):
        with tempfile.TemporaryDirectory() as directory:
            app = create_app(Path(directory) / "missing.json")
            async with api_client(app) as client:
                event = cg14_event()
                self.assertEqual(
                    (await client.post("/predict", json=event)).status_code, 422
                )
                payload = bridge(event)
                # 503 proves request validation passed, not successful scoring.
                self.assertEqual(
                    (await client.post("/predict", json=payload)).status_code, 503
                )
                self.assertEqual((await client.get("/health")).status_code, 503)
