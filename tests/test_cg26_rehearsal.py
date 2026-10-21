import gc
import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
import warnings
from contextlib import asynccontextmanager
from pathlib import Path
from unittest.mock import patch

import joblib
import pandas as pd
import sklearn
from fastapi import FastAPI

from scoring.scope import INPUT_FEATURES, SCOPE
from scoring.score_api import create_app
from scripts.experiment_anomaly import fit_normal
from scripts.experiment_rf import pipeline
from scripts.rehearse_cg26 import _rehearsal, _rehearsal_client


class RehearsalCliTests(unittest.TestCase):
    def run_cli(self, manifest, output):
        return subprocess.run(
            [
                sys.executable,
                "-m",
                "scripts.rehearse_cg26",
                "--manifest",
                str(manifest),
                "--output",
                str(output),
            ],
            check=False,
            capture_output=True,
            text=True,
            timeout=30,
        )

    def test_missing_bundle_does_not_publish_success(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            output = root / "result.json"
            process = self.run_cli(root / "missing.json", output)
            self.assertNotEqual(process.returncode, 0)
            self.assertFalse(output.exists())
            self.assertNotIn("PASS", process.stdout)

    def test_existing_evidence_is_preserved_before_loading_models(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            output = root / "result.json"
            previous = b'{"prior_run": true}\n'
            output.write_bytes(previous)
            process = self.run_cli(root / "missing.json", output)
            self.assertNotEqual(process.returncode, 0)
            self.assertIn("FileExistsError", process.stderr)
            self.assertEqual(output.read_bytes(), previous)

    def test_gc_guard_detects_deliberate_own_leak(self):
        probe = """
import sys
import unittest
from pathlib import Path
import anyio
sys.path.insert(0, str(Path.cwd() / "tests"))
from test_cg26_rehearsal import RehearsalTransportTests

class LeakingProbe(RehearsalTransportTests):
    async def leak(self):
        send, receive = anyio.create_memory_object_stream()
        cycle = [send, receive]
        cycle.append(cycle)

result = unittest.TextTestRunner().run(
    unittest.TestSuite([LeakingProbe("leak")])
)
sys.exit(not result.wasSuccessful())
"""
        process = subprocess.run(
            [sys.executable, "-c", probe],
            check=False,
            capture_output=True,
            text=True,
            timeout=30,
        )
        self.assertEqual(process.returncode, 1, process.stderr)
        self.assertIn(
            "ResourceWarning: Unclosed <MemoryObjectSendStream", process.stderr
        )
        self.assertIn(
            "ResourceWarning: Unclosed <MemoryObjectReceiveStream", process.stderr
        )
        self.assertIn("FAILED", process.stderr)


class RehearsalTransportTests(unittest.IsolatedAsyncioTestCase):
    @classmethod
    def setUpClass(cls):
        # Drain earlier tests before attributing resources to this class. This
        # leaves their warnings/hook untouched and visible to a global checker.
        gc.collect(2)
        gc.collect(2)
        cls.unraisables = []
        cls.original_hook = sys.unraisablehook
        cls.warning_context = warnings.catch_warnings()
        cls.warning_context.__enter__()
        warnings.simplefilter("error", ResourceWarning)

        def capture(info):
            cls.unraisables.append(f"{info.exc_type.__name__}: {info.exc_value}")
            cls.original_hook(info)

        sys.unraisablehook = capture

    def setUp(self):
        # Capture remains active between methods and event-loop shutdowns, so
        # delayed resources from an earlier CG26 test cannot escape attribution.
        gc.collect(2)

    def tearDown(self):
        gc.collect(2)
        gc.collect(2)
        self.assertEqual(self.unraisables, [])

    @classmethod
    def tearDownClass(cls):
        try:
            gc.collect(2)
            gc.collect(2)
        finally:
            sys.unraisablehook = cls.original_hook
            cls.warning_context.__exit__(None, None, None)
        if cls.unraisables:
            raise AssertionError(f"CG26 unclosed resources: {cls.unraisables}")

    async def check_lifecycle(self, failure):
        events = []

        @asynccontextmanager
        async def lifespan(app):
            events.append("startup")
            yield
            # Deliberately after yield, like scoring.score_api's cleanup.
            events.append("shutdown")

        app = FastAPI(lifespan=lifespan)

        @app.get("/")
        async def root():
            if failure == "request":
                raise ValueError("request failed")
            return {"ready": events == ["startup"]}

        async def request():
            async with _rehearsal_client(app) as client:
                self.client = client
                response = await client.get("/")
                self.assertEqual(response.json(), {"ready": True})
                if failure == "body":
                    raise ValueError("body failed")

        if failure:
            with self.assertRaisesRegex(ValueError, f"{failure} failed"):
                await request()
        else:
            await request()
        self.assertTrue(self.client.is_closed)
        self.assertEqual(events, ["startup", "shutdown"])
        del self.client

    async def test_success_closes_client_and_lifespan(self):
        await self.check_lifecycle(None)

    async def test_request_error_propagates_and_closes_client_and_lifespan(self):
        await self.check_lifecycle("request")

    async def test_body_error_propagates_and_closes_client_and_lifespan(self):
        await self.check_lifecycle("body")

    async def test_startup_error_propagates(self):
        @asynccontextmanager
        async def lifespan(app):
            raise ValueError("startup failed")
            yield

        with self.assertRaisesRegex(ValueError, "startup failed"):
            async with _rehearsal_client(FastAPI(lifespan=lifespan)):
                self.fail("Startup failure must prevent the request context")

    async def test_empty_manifest_rejects_before_loading_and_gc_is_clean(self):
        with tempfile.TemporaryDirectory() as directory:
            manifest = Path(directory) / "manifest.json"
            manifest.write_text("{}")
            app = create_app(manifest)
            with (
                patch("scripts.rehearse_cg26.create_app", return_value=app),
                patch("scoring.score_api.joblib.load") as load,
                self.assertRaisesRegex(ValueError, "Bundle not ready: 503"),
            ):
                await _rehearsal(manifest)
            load.assert_not_called()
            self.assertIsNone(app.state.models)

    async def test_complete_rehearsal_with_small_synthetic_bundle(self):
        # Only 24 synthetic rows and three trees; never train delivery data.
        frame = pd.DataFrame(
            [
                {
                    "machine_id": "CNC-001",
                    "machine_type": "M",
                    "air_temp_K": 300.0,
                    "process_temp_K": 310.0,
                    "rpm": 500.0 if i % 2 else 1500.0,
                    "torque_Nm": 80.0 if i % 2 else 30.0,
                    "tool_wear_min": float(i),
                    "machine_failure": i % 2,
                }
                for i in range(24)
            ]
        )
        rf = pipeline("rf", trees=3)
        rf.fit(frame[INPUT_FEATURES], frame.machine_failure)
        anomaly, _ = fit_normal(frame, trees=3)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            hashes = {}
            for name, model in {"rf.pkl": rf, "if.pkl": anomaly}.items():
                joblib.dump(model, root / name)
                hashes[name] = hashlib.sha256((root / name).read_bytes()).hexdigest()
            manifest = root / "manifest.json"
            manifest.write_text(
                json.dumps(
                    {
                        **SCOPE,
                        "model_version": "synthetic-cg26-test-only",
                        "versions": {"sklearn": sklearn.__version__},
                        "files": hashes,
                        "policy": "f2",
                        "risk_threshold": 0.5,
                        "anomaly_threshold": 2.0,
                    }
                )
            )
            with (
                patch("scripts.rehearse_cg26.load_training_source", return_value=frame),
                patch(
                    "scripts.rehearse_cg26.split_development",
                    return_value=(frame, frame.iloc[:0], frame.iloc[:0]),
                ),
                patch(
                    "scripts.rehearse_cg26.CASES",
                    {"normal_fit_example": 0, "failure_fit_example": 1},
                ),
            ):
                result = await _rehearsal(manifest)
            self.assertEqual(result["status"], "isolated_rehearsal_passed")
            self.assertEqual(result["missing_bundle"], {"health": 503, "predict": 503})
            self.assertEqual(set(result["rejected_422"].values()), {422})
            self.assertTrue(result["trace_invariance"])
