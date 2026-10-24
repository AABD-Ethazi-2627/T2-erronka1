"""Small REST client for the isolated local TLS NiFi laboratory."""

import json
import os
import ssl
import urllib.request
from pathlib import Path

from scripts.private_files import open_private_text

BASE = "https://localhost:18080/nifi-api"


def private_token():
    configured = os.environ.get("CNC_NIFI_TOKEN_FILE")
    if not configured or not Path(configured).is_absolute():
        raise ValueError("CNC_NIFI_TOKEN_FILE must name an absolute private file")
    with open_private_text(configured) as handle:
        token = handle.read(8193).strip()
    if not token or len(token) > 8192 or "\n" in token or "\r" in token:
        raise ValueError("NiFi token file is empty or malformed")
    return token


def request(method, path, payload=None):
    token = private_token()
    ca_file = os.environ.get("CNC_NIFI_CA_FILE")
    if not ca_file:
        raise ValueError("CNC_NIFI_CA_FILE must name the trusted NiFi CA certificate")
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
        req, context=ssl.create_default_context(cafile=ca_file), timeout=30
    ) as response:
        data = response.read()
        return (
            json.loads(data)
            if data
            and response.headers.get("Content-Type", "").startswith("application/json")
            else data.decode()
        )
