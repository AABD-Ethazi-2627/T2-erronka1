"""Export/contract regressions without training, inference or services."""

import json
import unittest

from scripts.build_es_ingest_pipeline import EXPORT, PIPELINE_ID, ROOT, build, render
from scripts.validate_contracts import validators


def synthetic_prediction():
    """Contract fixture with published v4 metadata; NOT an inference result."""
    doc = json.loads((ROOT / "contracts/examples/valid/prediction.json").read_text())
    scope = json.loads(
        (ROOT / "docs/evidence/CG17_CURRENT_STATE_SCOPE.json").read_text()
    )["active_scope"]
    for key in ("model_version", "policy", "risk_threshold", "anomaly_threshold"):
        doc[key] = scope[key]
    doc["model_artifact_sha256"] = scope["files"]["rf.pkl"]
    doc["source"] = {
        "kind": "lab_fixture",
        "uri": "fixture://cg18/synthetic-v4-contract",
        "record_ref": "constructed-contract-fixture-no-inference",
    }
    return doc


class IngestExportTests(unittest.TestCase):
    def test_export_is_current_and_reproducible(self):
        self.assertEqual(EXPORT.read_text(encoding="utf-8"), render())
        self.assertEqual(build(), build())
        self.assertEqual(build()["version"], 1)

    def test_final_pipeline_matches_export(self):
        template = json.loads((ROOT / "elasticsearch/index-template.json").read_text())
        self.assertEqual(
            template["template"]["settings"]["index.final_pipeline"], PIPELINE_ID
        )
        self.assertEqual(template["template"]["mappings"]["dynamic"], "strict")

    def test_guard_rules_follow_contract_types_bounds_and_required_fields(self):
        prediction = json.loads((ROOT / "contracts/prediction.schema.json").read_text())
        root, source = build()["processors"][0]["script"]["params"]["sections"]
        self.assertEqual(root["required"], prediction["required"])
        self.assertEqual(set(root["rules"]), set(prediction["properties"]))
        self.assertEqual(root["rules"]["failure_score"]["maximum"], 1)
        self.assertEqual(root["rules"]["temporal_prediction_enabled"]["const"], False)
        self.assertNotIn("raw_record", source["rules"])
        self.assertNotIn("machine_failure", root["rules"])

    def test_v4_fixture_is_contract_valid_and_contains_no_labels(self):
        doc = synthetic_prediction()
        validators(ROOT / "contracts")["prediction"].validate(doc)
        self.assertEqual(doc["model_version"], "ai4i-current-state-v4")
        self.assertEqual(doc["source"]["kind"], "lab_fixture")
        self.assertNotIn("machine_failure", doc)


if __name__ == "__main__":
    unittest.main()
