"""Validate the proposed CG03 contracts against positive and negative fixtures."""

import csv
import hashlib
import json
import unittest
from datetime import datetime
from pathlib import Path

import pandas as pd
from jsonschema import Draft202012Validator, FormatChecker
from referencing import Registry, Resource

from scoring.inference import load_bundle, predict_signals

ROOT = Path(__file__).resolve().parents[1] / "contracts"
FORMATS = FormatChecker()


@FORMATS.checks("date-time", raises=(ValueError, TypeError))
def utc_datetime(value):
    if not isinstance(value, str):
        return True
    if not value.endswith("Z"):
        return False
    datetime.fromisoformat(value)
    return True


class ContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.schemas = {}
        registry = Registry()
        for path in ROOT.glob("*.schema.json"):
            schema = json.loads(path.read_text())
            Draft202012Validator.check_schema(schema)
            cls.schemas[path.stem.replace(".schema", "")] = schema
            registry = registry.with_resource(
                schema["$id"], Resource.from_contents(schema)
            )
        cls.registry = registry

    def validator(self, name):
        return Draft202012Validator(
            self.schemas[name], registry=self.registry, format_checker=FORMATS
        )

    def test_all_four_domain_contracts_exist(self):
        self.assertTrue(
            {"telemetry", "maintenance", "log", "prediction"} <= self.schemas.keys()
        )

    def test_valid_examples(self):
        for path in (ROOT / "examples/valid").glob("*.json"):
            with self.subTest(path=path.name):
                self.validator(path.stem).validate(json.loads(path.read_text()))
        self.assertEqual(len(list((ROOT / "examples/valid").glob("*.json"))), 4)

    def test_invalid_examples(self):
        manifest = json.loads((ROOT / "examples/invalid/manifest.json").read_text())
        self.assertGreaterEqual(len(manifest), 4)
        for case in manifest:
            with self.subTest(case=case["file"]):
                payload = json.loads(
                    (ROOT / "examples/invalid" / case["file"]).read_text()
                )
                self.assertTrue(
                    list(self.validator(case["schema"]).iter_errors(payload)),
                    case["reason"],
                )

    def test_smb_samples_conform_without_training_labels(self):
        samples = sorted((ROOT.parent / "data/stream_samples").glob("*.csv"))
        self.assertTrue(samples)
        for path in samples:
            lines = path.read_text().splitlines()
            for row, raw in zip(csv.DictReader(lines), lines[1:], strict=True):
                payload = {
                    "event_id": hashlib.sha256(
                        ("cnc.telemetry.v0.1.0\ncnc-simulator-v1\n" + raw).encode()
                    ).hexdigest(),
                    "machine_id": row["machine_id"],
                    "timestamp": row["timestamp"],
                    "schema_version": "0.1.0",
                    "quality_flag": "OK",
                    "source": {
                        "kind": "smb_csv",
                        "uri": "smb://192.168.75.222/cnc-stream",
                        "record_ref": path.name,
                        "raw_record": raw,
                    },
                    "machine_type": row["machine_type"],
                    **{
                        key: float(row[key])
                        for key in [
                            "air_temp_K",
                            "process_temp_K",
                            "rpm",
                            "torque_Nm",
                            "tool_wear_min",
                        ]
                    },
                }
                with self.subTest(sample=path.name, machine=row["machine_id"]):
                    self.validator("telemetry").validate(payload)

    def test_prediction_fixture_keeps_identity_and_matches_saved_model(self):
        telemetry = json.loads((ROOT / "examples/valid/telemetry.json").read_text())
        prediction = json.loads((ROOT / "examples/valid/prediction.json").read_text())
        for key in ["event_id", "machine_id", "timestamp", "source"]:
            self.assertEqual(prediction[key], telemetry[key])
        bundle = load_bundle(ROOT.parent / "models/offline-ai4i-v2")
        result = predict_signals(
            bundle, pd.DataFrame([telemetry]), prediction["policy"]
        )[0]
        for key, value in result.items():
            self.assertEqual(prediction[key], value)

    def test_training_labels_cannot_enter_telemetry(self):
        payload = json.loads((ROOT / "examples/valid/telemetry.json").read_text())
        for key in ["machine_failure", "failure_TWF", "failure_RNF", "vibration"]:
            with self.subTest(key=key):
                bad = {**payload, key: 1}
                self.assertTrue(list(self.validator("telemetry").iter_errors(bad)))

    def test_impossible_date_and_offset_are_rejected(self):
        payload = json.loads((ROOT / "examples/valid/telemetry.json").read_text())
        for timestamp in [
            "2026-02-30T12:00:00Z",
            "2026-10-15T12:00:00+02:00",
            "2026-10-15T12:00:00",
        ]:
            self.assertTrue(
                list(
                    self.validator("telemetry").iter_errors(
                        {**payload, "timestamp": timestamp}
                    )
                )
            )
