"""Bounded rehearsal guards; these tests do not claim a live Elasticsearch run."""

import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import httpx
import pytest

from scripts.integration_dashboard_probe import run as probe_run
from scripts.integration_dashboard_probe import unavailable_report
from scripts.integration_http import local_url, prepare_es


@pytest.mark.parametrize(
    "url", ["http://127.0.0.1:19200", "http://localhost:19200/", "http://[::1]:19200"]
)
def test_explicit_loopback(url):
    assert local_url(url) == url.rstrip("/")


@pytest.mark.parametrize(
    "url",
    [
        "http://example.com:9200",
        "http://127.0.0.1",
        "https://localhost:9200",
        "http://user:pass@localhost:9200",
        "http://localhost:9200/shared",
        "http://localhost:9200/?token=x",
    ],
)
def test_reject_shared_or_ambiguous_endpoints(url):
    with pytest.raises(ValueError):
        local_url(url)
    # Validation happens before Streamlit imports, file reads or any requests.
    with pytest.raises(ValueError):
        probe_run(url, "unused", "unused")


@pytest.mark.parametrize("component", ["ES", "API"])
def test_outage_display_check_without_services(component):
    app = SimpleNamespace(
        exception=[],
        error=[SimpleNamespace(value="DEGRADATUTA")],
        metric=[],
        toggle=Mock(return_value=SimpleNamespace(value=True)),
    )
    assert unavailable_report(app, component)["degraded_without_demo"]
    app.metric = [SimpleNamespace(value="1801")]
    with pytest.raises(AssertionError):
        unavailable_report(app, component)
    app.metric = []
    app.error = []
    with pytest.raises(AssertionError):
        unavailable_report(app, component)


def test_fresh_index_uses_pinned_guard_and_mapping(monkeypatch):
    calls = []
    checked = []

    def handle(request):
        calls.append(request)
        if request.method == "GET":
            return httpx.Response(404)
        return httpx.Response(200, json={"acknowledged": True})

    monkeypatch.setattr("scripts.integration_http.check_es", checked.append)
    with httpx.Client(transport=httpx.MockTransport(handle)) as client:
        prepare_es(client, "http://localhost:9200", "cnc-local-fixture")
    assert [r.method for r in calls] == ["GET", "PUT", "PUT"]
    body = json.loads(calls[-1].content)
    assert (
        body
        == json.loads(Path("elasticsearch/index-template.json").read_text())["template"]
    )
    assert checked[0]["es_index"] == "cnc-local-fixture"


def test_different_existing_guard_never_overwritten():
    calls = []

    def handle(request):
        calls.append(request)
        return httpx.Response(200, json={"cnc-prediction-v1": {"version": "wrong"}})

    with (
        httpx.Client(transport=httpx.MockTransport(handle)) as client,
        pytest.raises(ValueError, match="refusing to overwrite"),
    ):
        prepare_es(client, "http://localhost:9200", "cnc-local-fixture")
    assert len(calls) == 1 and calls[0].method == "GET"
