"""Exercise the API contract across the FastAPI and Starlette upgrade."""

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from api_client import api_client
from test_elasticsearch_contract import fixture_bundle

from scoring.score_api import create_app
from scripts.validate_contracts import validators

ROOT = Path(__file__).resolve().parents[1]


class FrameworkUpgradeContractTests(unittest.IsolatedAsyncioTestCase):
    async def test_fragmented_json_at_body_size_boundary(self):
        with tempfile.TemporaryDirectory() as directory:
            app = create_app(fixture_bundle(Path(directory)))
            payload = (ROOT / "contracts/examples/valid/telemetry.json").read_bytes()

            requests = []
            for size, expected in ((32768, 200), (32769, 413)):
                body = payload + b" " * (size - len(payload))

                async def fragments(body=body):
                    for offset in range(0, len(body), 4096):
                        yield body[offset : offset + 4096]

                requests.append((size, expected, fragments))

            async with api_client(app) as client:
                for size, expected, fragments in requests:
                    with self.subTest(size=size):
                        response = await client.post(
                            "/predict",
                            content=fragments(),
                            headers={"Content-Type": "application/json"},
                        )
                        self.assertEqual(response.status_code, expected, response.text)
                        if expected == 413:
                            self.assertEqual(
                                response.json(), {"detail": "Request too large"}
                            )

    async def test_real_asgi_responses_and_schema_with_synthetic_models(self):
        with tempfile.TemporaryDirectory() as directory:
            app = create_app(fixture_bundle(Path(directory)))
            payload = json.loads(
                (ROOT / "contracts/examples/valid/telemetry.json").read_text()
            )
            checks = validators(ROOT / "contracts")

            async with api_client(app) as client:
                self.assertIsNotNone(app.state.models)
                health = await client.get("/health")
                self.assertEqual(health.status_code, 200, health.text)
                self.assertEqual(health.json()["status"], "ready")

                prediction = await client.post("/predict", json=payload)
                self.assertEqual(prediction.status_code, 200, prediction.text)
                checks["prediction"].validate(prediction.json())

                invalid = {**payload, "rpm": -1}
                response = await client.post("/predict", json=invalid)
                self.assertEqual(response.status_code, 422, response.text)
                self.assertEqual(response.json()["detail"][0]["loc"], ["body", "rpm"])

                no_content_type = await client.post(
                    "/predict", content=json.dumps(payload).encode()
                )
                self.assertEqual(no_content_type.status_code, 422, no_content_type.text)
                flow = json.loads(
                    (ROOT / "nifi-flows/cnc_lab_completed.json").read_text()
                )
                invoke = next(
                    processor
                    for processor in flow["flowContents"]["processors"]
                    if processor["name"] == "InvokeHTTP"
                )
                self.assertEqual(
                    invoke["properties"]["Request Content-Type"], "application/json"
                )

                oversized = await client.post("/predict", content=b"x" * 32769)
                self.assertEqual(oversized.status_code, 413, oversized.text)
                self.assertEqual(oversized.json(), {"detail": "Request too large"})

                with (
                    patch.object(
                        app.state.models["rf.pkl"],
                        "predict_proba",
                        side_effect=RuntimeError("synthetic scoring fault"),
                    ),
                    patch("scoring.score_api.log"),
                ):
                    failure = await client.post("/predict", json=payload)
                self.assertEqual(failure.status_code, 500, failure.text)
                self.assertEqual(failure.json(), {"detail": "Scoring failed"})

                openapi = (await client.get("/openapi.json")).json()
                self.assertEqual(openapi["openapi"], "3.1.0")
                self.assertIn("/predict", openapi["paths"])
                self.assertIn("Telemetry", openapi["components"]["schemas"])
                telemetry = openapi["components"]["schemas"]["Telemetry"]
                self.assertIn("rpm", telemetry["required"])
                self.assertEqual(telemetry["additionalProperties"], False)
            self.assertIsNone(app.state.models)

    async def test_invalid_bundle_stays_unready(self):
        with tempfile.TemporaryDirectory() as directory:
            manifest = Path(directory) / "manifest.json"
            manifest.write_text("{}")
            app = create_app(manifest)
            payload = json.loads(
                (ROOT / "contracts/examples/valid/telemetry.json").read_text()
            )
            async with api_client(app) as client:
                self.assertEqual((await client.get("/health")).status_code, 503)
                self.assertEqual(
                    (await client.post("/predict", json=payload)).status_code, 503
                )
