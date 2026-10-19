"""Small REST client for the isolated local TLS NiFi laboratory.
Token file is private and never printed; self-signed TLS exception only for localhost.
"""

import json
import ssl
import urllib.request
from pathlib import Path

BASE = "https://localhost:18080/nifi-api"


def request(method, path, payload=None):
    token = Path("/tmp/cnc-lab-nifi-token").read_text().strip()
    body = None if payload is None else json.dumps(payload).encode()
    req = urllib.request.Request(
        BASE + path,
        data=body,
        method=method,
        headers={
            "Authorization": "Bearer " + token,
            "Content-Type": "application/json",
        },
    )
    with urllib.request.urlopen(
        req, context=ssl._create_unverified_context(), timeout=30
    ) as response:
        data = response.read()
        return (
            json.loads(data)
            if data
            and response.headers.get("Content-Type", "").startswith("application/json")
            else data.decode()
        )
