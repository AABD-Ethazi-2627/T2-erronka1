import json
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from scoring.score_api import create_app
from scripts.failure_harness import Harness, run


class FailureHarnessTests(unittest.TestCase):
    def test_restart_replay_backpressure_and_durable_counts(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result = run(root)["snapshots"]
            self.assertEqual(result["outage"]["pending"], 5)
            self.assertEqual(result["stored_before_ack"]["stored_unique"], 1)
            self.assertEqual(result["stored_before_ack"]["offset_acknowledged"], 0)
            self.assertEqual(result["restart"], result["stored_before_ack"])
            self.assertEqual(result["backpressure_batch"]["pending"], 3)
            self.assertEqual(
                result["recovered"],
                dict(
                    sent=5,
                    accepted=3,
                    rejected=2,
                    pending=0,
                    stored_unique=2,
                    duplicates=1,
                    offset_acknowledged=5,
                ),
            )
            self.assertEqual(result["recovered"], result["replay_noop"])
            h = Harness(root / "journal.sqlite")
            self.assertEqual(h.report(), result["recovered"])
            h.close()
            with self.assertRaises(ValueError):
                run(root)

    def test_existing_report_is_preserved_without_creating_journal(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            report = root / "report.json"
            original = b"existing evidence\n"
            report.write_bytes(original)
            with self.assertRaisesRegex(ValueError, "existing evidence"):
                run(root)
            self.assertEqual(report.read_bytes(), original)
            self.assertFalse((root / "journal.sqlite").exists())

    def test_real_api_fails_closed_for_missing_and_corrupt_manifest(self):
        payload = json.loads(
            Path("contracts/examples/valid/telemetry.json").read_text()
        )
        with tempfile.TemporaryDirectory() as tmp:
            manifest = Path(tmp) / "manifest.json"
            for content in (None, "{invalid json", "{}"):
                with self.subTest(content=content):
                    if content is not None:
                        manifest.write_text(content)
                    with TestClient(create_app(manifest)) as client:
                        self.assertEqual(client.get("/health").status_code, 503)
                        response = client.post("/predict", json=payload)
                        self.assertEqual(response.status_code, 503)
                        self.assertNotIn("failure_score", response.json())

    def test_missing_and_tampered_model_artifact_before_deserialization(self):
        import hashlib
        from unittest.mock import patch

        import sklearn

        from scoring.scope import SCOPE

        payload = json.loads(
            Path("contracts/examples/valid/telemetry.json").read_text()
        )
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest = {
                **SCOPE,
                "versions": {"sklearn": sklearn.__version__},
                "files": {
                    "rf.pkl": hashlib.sha256(b"expected").hexdigest(),
                    "if.pkl": hashlib.sha256(b"expected").hexdigest(),
                },
            }
            (root / "manifest.json").write_text(json.dumps(manifest))
            for tampered in (False, True):
                with self.subTest(tampered=tampered):
                    if tampered:
                        (root / "rf.pkl").write_bytes(
                            b"corrupted fixture, never pickle"
                        )
                    with patch("scoring.score_api.joblib.load") as load:
                        with TestClient(create_app(root / "manifest.json")) as client:
                            self.assertEqual(client.get("/health").status_code, 503)
                            self.assertEqual(
                                client.post("/predict", json=payload).status_code, 503
                            )
                        load.assert_not_called()
