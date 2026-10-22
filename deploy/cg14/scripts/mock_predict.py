"""Local-only mock for CG14 integration tests; never a production predictor."""

from __future__ import annotations

import json
import os
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse


class MockPredictHandler(BaseHTTPRequestHandler):
    server_version = "CG14-Integration-Mock/1.0"

    def do_GET(self) -> None:
        if urlparse(self.path).path == "/healthz":
            self._reply(200, {"mock": True, "status": "ready"})
        else:
            self._reply(404, {"mock": True, "error": "not_found"})

    def do_POST(self) -> None:
        scenario = urlparse(self.path).path.removeprefix("/predict/")
        if scenario == "timeout":
            time.sleep(float(os.environ.get("CG14_MOCK_TIMEOUT_SECONDS", "10")))
        statuses = {"2xx": 200, "422": 422, "5xx": 503, "timeout": 200}
        if scenario not in statuses:
            self._reply(404, {"mock": True, "error": "unknown_scenario"})
            return

        length = int(self.headers.get("Content-Length", "0"))
        if length > 1_048_576:
            self._reply(413, {"mock": True, "error": "request_too_large"})
            return
        payload = self.rfile.read(length)
        event_id = None
        try:
            decoded = json.loads(payload)
            if isinstance(decoded, dict):
                event_id = decoded.get("event_id")
        except (UnicodeDecodeError, json.JSONDecodeError):
            self._reply(400, {"mock": True, "error": "invalid_json"})
            return

        self._reply(
            statuses[scenario],
            {"mock": True, "scenario": scenario, "event_id": event_id},
        )

    def _reply(self, status: int, body: dict[str, object]) -> None:
        encoded = json.dumps(body, separators=(",", ":")).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def log_message(self, fmt: str, *args: object) -> None:
        # Avoid logging request bodies or user data; keep only the test path/status.
        if self.command == "POST":
            super().log_message(fmt, *args)


if __name__ == "__main__":
    ThreadingHTTPServer(("0.0.0.0", 8080), MockPredictHandler).serve_forever()
