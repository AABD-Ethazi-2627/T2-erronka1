"""Exercise actual curl retries using the upstream installer's calling convention."""

import http.server
import subprocess
import threading
from pathlib import Path

WRAPPER = Path(__file__).resolve().parents[1] / "scripts/trivy-download-curl.sh"


def test_installer_download_recovers_and_keeps_status_and_bytes(tmp_path):
    requests = []

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            requests.append(self.path)
            self.send_response(503 if len(requests) < 3 else 200)
            self.end_headers()
            self.wfile.write(b"temporary failure" if len(requests) < 3 else b"artifact")

        def log_message(self, *_):
            pass

    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        output = tmp_path / "artifact"
        result = subprocess.run(
            [
                "sh",
                str(WRAPPER),
                "-w",
                "%{http_code}",
                "-sL",
                "-o",
                str(output),
                f"http://127.0.0.1:{server.server_port}/release?client=setup-trivy",
            ],
            check=False,
            capture_output=True,
            text=True,
            timeout=20,
        )
        assert result.returncode == 0, result.stderr
        assert result.stdout == "200"
        assert requests == ["/release?client=setup-trivy"] * 3
        assert output.read_bytes() == b"artifact"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
