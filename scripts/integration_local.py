"""Dependency-free guards shared by the bounded local rehearsal tools."""

from urllib.parse import urlsplit


def local_url(value):
    parsed = urlsplit(value)
    if (
        parsed.scheme != "http"
        or parsed.hostname not in {"127.0.0.1", "localhost", "::1"}
        or not parsed.port
        or parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
        or parsed.path not in {"", "/"}
    ):
        raise ValueError("An explicit owned loopback HTTP endpoint is required")
    return value.rstrip("/")
