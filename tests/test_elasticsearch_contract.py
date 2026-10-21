"""API-to-mapping regression; exported NiFi routing is inspected, not executed."""

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

import joblib
import pandas as pd
import sklearn
from api_client import api_client

from scoring.scope import INPUT_FEATURES, SCOPE
from scoring.score_api import create_app
from scripts.experiment_anomaly import fit_normal
from scripts.experiment_rf import pipeline
from scripts.validate_contracts import validators

ROOT = Path(__file__).resolve().parents[1]


def fixture_bundle(root):
    """Small synthetic models, never a delivery bundle or dataset evaluation."""
    frame = pd.DataFrame(
        [
            {
                "machine_type": "HML"[i % 3],
                "air_temp_K": 295.0 + i / 10,
                "process_temp_K": 305.0 + i / 5,
                "rpm": 1200.0 + i * 10,
                "torque_Nm": 30.0 + i,
                "tool_wear_min": float(i * 5),
                "machine_failure": i % 2,
            }
            for i in range(24)
        ]
    )
    risk = pipeline("rf", physical=True, trees=3).fit(
        frame[INPUT_FEATURES], frame.machine_failure
    )
    anomaly, _ = fit_normal(frame, trees=3)
    files = {}
    for name, model in [("rf.pkl", risk), ("if.pkl", anomaly)]:
        artifact = root / name
        joblib.dump(model, artifact)
        files[name] = hashlib.sha256(artifact.read_bytes()).hexdigest()
    manifest = {
        **SCOPE,
        "model_version": "synthetic-es-contract-test-only",
        "versions": {"sklearn": sklearn.__version__},
        "files": files,
        "risk_threshold": 0.15,
        # Ensure this fixture also exercises the alerts branch, regardless of RF score.
        "anomaly_threshold": 0.0,
        "policy": "f2",
    }
    path = root / "manifest.json"
    path.write_text(json.dumps(manifest))
    return path


class ElasticsearchContractTests(unittest.IsolatedAsyncioTestCase):
    def test_entire_prediction_contract_has_explicit_compatible_mappings(self):
        schema = json.loads((ROOT / "contracts/prediction.schema.json").read_text())
        common = json.loads((ROOT / "contracts/common.schema.json").read_text())
        mapping = json.loads((ROOT / "elasticsearch/index-template.json").read_text())
        mapping = mapping["template"]["mappings"]
        self.assertEqual(mapping["dynamic"], "strict")

        def check(properties, mapped, prefix=""):
            for name, definition in properties.items():
                field = prefix + name
                with self.subTest(field=field):
                    self.assertIn(name, mapped, f"Unmapped prediction field: {field}")
                    if "$ref" in definition:
                        reference = definition["$ref"]
                        expected = common["$id"] + "#/$defs/"
                        self.assertTrue(reference.startswith(expected), reference)
                        definition = common["$defs"][reference.removeprefix(expected)]
                    kind = definition.get("type")
                    if "const" in definition:
                        kind = (
                            "boolean"
                            if isinstance(definition["const"], bool)
                            else "string"
                        )
                    if "enum" in definition:
                        self.assertTrue(
                            all(isinstance(v, str) for v in definition["enum"])
                        )
                        kind = "string"
                    if kind == "object":
                        # source inherits strict from the root mapping.
                        self.assertEqual(
                            mapped[name].get("dynamic", "strict"), "strict"
                        )
                        check(
                            definition["properties"],
                            mapped[name]["properties"],
                            field + ".",
                        )
                    else:
                        expected_type = {
                            "boolean": "boolean",
                            "number": "double",
                            "string": "date"
                            if definition.get("format") == "date-time"
                            else "keyword",
                        }[kind]
                        self.assertEqual(mapped[name]["type"], expected_type, field)

        check(schema["properties"], mapping["properties"])

    async def test_real_api_response_and_exported_nifi_paths_preserve_contract(self):
        flow = json.loads((ROOT / "nifi-flows/cnc_lab_completed.json").read_text())[
            "flowContents"
        ]
        processors = {p["name"]: p for p in flow["processors"]}
        connections = {
            (c["source"]["id"], relation, c["destination"]["id"])
            for c in flow["connections"]
            for relation in c["selectedRelationships"]
        }
        for source, relation, destination in [
            ("InvokeHTTP", "Response", "EvaluateJsonPath"),
            ("EvaluateJsonPath", "matched", "PutElasticsearchJson"),
            ("EvaluateJsonPath", "matched", "RouteOnAttribute"),
            ("RouteOnAttribute", "alert", "Put alerts"),
        ]:
            self.assertIn(
                (
                    processors[source]["identifier"],
                    relation,
                    processors[destination]["identifier"],
                ),
                connections,
            )
        invoke = processors["InvokeHTTP"]["properties"]
        self.assertEqual(invoke["HTTP Method"], "POST")
        self.assertTrue(invoke["HTTP URL"].endswith("/predict"))
        self.assertEqual(invoke["Response Body Ignored"], "false")
        self.assertIsNone(invoke["Response Body Attribute Name"])
        extract = processors["EvaluateJsonPath"]["properties"]
        self.assertEqual(extract["Destination"], "flowfile-attribute")
        for attribute, path in {
            "cnc.event_id": "$.event_id",
            "cnc.source_kind": "$.source.kind",
            "cnc.alert_level": "$.alert_level",
            "cnc.anomaly_alert": "$.anomaly_alert",
        }.items():
            self.assertEqual(extract[attribute], path)
        self.assertEqual(
            processors["RouteOnAttribute"]["properties"]["alert"],
            "${cnc.alert_level:equals('OK'):not():or(${cnc.anomaly_alert:equals('true')})}",
        )
        for name, family in [
            ("PutElasticsearchJson", "telemetry"),
            ("Put alerts", "alerts"),
        ]:
            sink = processors[name]
            self.assertTrue(sink["type"].endswith(".PutElasticsearchJson"))
            props = sink["properties"]
            self.assertEqual(props["put-es-json-id-attr"], "cnc.event_id")
            self.assertEqual(props["put-es-record-index-op"], "index")
            self.assertIsNone(props["put-es-json-script"])
            self.assertEqual(props["put-es-json-scripted-upsert"], "false")
            self.assertEqual(
                props["el-rest-fetch-index"],
                "${cnc.source_kind:equals('smb_csv'):ifElse('cnc-"
                + family
                + "-smb-v1','cnc-"
                + family
                + "-lab-v2')}",
            )

        checks = validators(ROOT / "contracts")
        mapped = json.loads((ROOT / "elasticsearch/index-template.json").read_text())[
            "template"
        ]["mappings"]["properties"]
        with tempfile.TemporaryDirectory() as directory:
            manifest = fixture_bundle(Path(directory))
            app = create_app(manifest)
            async with api_client(app) as client:
                self.assertEqual((await client.get("/health")).status_code, 200)
                for kind in ["lab_fixture", "smb_csv"]:
                    with self.subTest(source=kind):
                        payload = json.loads(
                            (
                                ROOT / "contracts/examples/valid/telemetry.json"
                            ).read_text()
                        )
                        payload["source"] = {
                            "kind": kind,
                            "uri": "fixture://es-contract",
                            "record_ref": "synthetic-row-1",
                        }
                        response = await client.post("/predict", json=payload)
                        self.assertEqual(response.status_code, 200, response.text)
                        document = response.json()
                        checks["prediction"].validate(document)
                        self.assertEqual(document["event_id"], payload["event_id"])
                        self.assertEqual(document["source"], payload["source"])
                        self.assertEqual(
                            document["model_artifact_sha256"],
                            json.loads(manifest.read_text())["files"]["rf.pkl"],
                        )
                        self.assertTrue(document["anomaly_alert"])
                        for field in [
                            "prediction_scope",
                            "temporal_prediction_enabled",
                            "score_semantics",
                        ]:
                            self.assertEqual(document[field], SCOPE[field])
                        self.assertFalse(set(document) - set(mapped))
                        self.assertFalse(
                            set(document["source"])
                            - set(mapped["source"]["properties"])
                        )
                        self.assertFalse(
                            set(document)
                            & {
                                "machine_failure",
                                "failure_TWF",
                                "eta_minutes",
                                "rul_minutes",
                            }
                        )
            self.assertIsNone(app.state.models)
