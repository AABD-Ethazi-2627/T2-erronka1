"""Guard the resource cleanup that Starlette TestClient performs on exit."""

import gc
import sys
import unittest
import warnings

from fastapi import FastAPI
from starlette.testclient import TestClient


class TestClientCleanupTests(unittest.TestCase):
    def test_context_closes_anyio_memory_streams(self):
        unraisables = []
        previous_hook = sys.unraisablehook

        def record_unraisable(info):
            unraisables.append(f"{info.exc_type.__name__}: {info.exc_value}")

        app = FastAPI()

        @app.get("/")
        def root():
            return {"ok": True}

        try:
            sys.unraisablehook = record_unraisable
            with warnings.catch_warnings(record=True) as observed:
                warnings.simplefilter("always", ResourceWarning)
                for _ in range(3):
                    with TestClient(app) as client:
                        self.assertEqual(client.get("/").json(), {"ok": True})
                    del client
                    gc.collect(2)
                gc.collect(2)
            resource_warnings = [
                str(warning.message)
                for warning in observed
                if issubclass(warning.category, ResourceWarning)
            ]
            self.assertEqual(resource_warnings, [])
            self.assertEqual(unraisables, [])
        finally:
            sys.unraisablehook = previous_hook
