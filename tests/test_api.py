import json
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from scoring.score_api import create_app


class ApiTests(unittest.TestCase):
    def test_missing_and_corrupt_models_are_unhealthy(self):
        with tempfile.TemporaryDirectory() as tmp:
            manifest = Path(tmp) / "manifest.json"
            manifest.write_text("{}")
            with TestClient(create_app(manifest)) as client:
                self.assertEqual(client.get("/health").status_code, 503)
                self.assertEqual(
                    client.post(
                        "/predict",
                        json=json.loads(
                            Path("contracts/examples/valid/telemetry.json").read_text()
                        ),
                    ).status_code,
                    503,
                )

    def test_real_pipeline_contract_and_invalid_input(self):
        manifest = Path("outputs/api/manifest.json")
        if not manifest.exists():
            self.skipTest("Run python -m scripts.package_model first")
        app = create_app(manifest)
        payload = json.loads(
            Path("contracts/examples/valid/telemetry.json").read_text()
        )
        with TestClient(app) as client:
            self.assertEqual(client.get("/health").status_code, 200)
            loaded = app.state.models
            response = client.post("/predict", json=payload)
            self.assertEqual(response.status_code, 200, response.text)
            self.assertEqual(response.json()["event_id"], payload["event_id"])
            self.assertIn(response.json()["alert_level"], ["OK", "AVISO", "CRITICA"])
            payload["failure_TWF"] = 1
            self.assertEqual(client.post("/predict", json=payload).status_code, 422)
            payload.pop("failure_TWF")
            payload["rpm"] = -1
            self.assertEqual(client.post("/predict", json=payload).status_code, 422)
            self.assertIs(app.state.models, loaded)

    def test_tampered_model_and_oversized_body(self):
        import shutil

        source = Path("outputs/api")
        if not source.exists():
            self.skipTest("Run package_model first")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for file in source.iterdir():
                shutil.copyfile(file, root / file.name)
            with (root / "rf.pkl").open("ab") as handle:
                handle.write(b"corrupt")
            with TestClient(create_app(root / "manifest.json")) as client:
                self.assertEqual(client.get("/health").status_code, 503)
                self.assertEqual(
                    client.post("/predict", content=b"x" * 33000).status_code, 413
                )
