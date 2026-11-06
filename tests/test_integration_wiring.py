import asyncio
import copy
import json

import pytest

from scripts.integration_fixture import run
from scripts.integration_verify import check_wiring, same_event


@pytest.fixture
def config(tmp_path):
    manifest = {"files": {"rf.pkl": "a" * 64}, "policy": "f2", "risk_threshold": 0.5}
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(manifest))
    graph = {
        "manifest": str(path),
        "root": str(tmp_path / "worker"),
        "source_namespace": "own",
        "topic": "own",
        "scoring_url": "http://api:8000/predict",
        "es_url": "http://elasticsearch:9200",
        "bootstrap_servers": "kafka:19092",
        "es_index": "cnc-alerts-own",
    }
    read = {
        "scope": {
            "source_uri": "kafka://own/own",
            "model_artifact_sha256": "a" * 64,
            "policy": "f2",
            "risk_threshold": 0.5,
        },
        "elasticsearch": {"url": graph["es_url"], "index": "cnc-alerts-own-read"},
        "archive_root": "/archive",
    }
    services = {
        "api": {"volumes": [f"{graph['root']}/archive:/archive:ro"]},
        "nifi": {"volumes": ["/runtime:/runtime:ro"]},
    }
    return graph, read, manifest, services, {"imports_ok": True, "duckdb": "2.0.0"}


def test_positive_static(config):
    assert check_wiring(*config)


@pytest.mark.parametrize(
    "fault", ["hostname", "port", "index", "mount", "dependency", "manifest"]
)
def test_negative_wiring(config, fault):
    graph, read, manifest, services, image = copy.deepcopy(config)
    if fault == "hostname":
        graph["scoring_url"] = "http://scoring:8000/predict"
    elif fault == "port":
        graph["bootstrap_servers"] = "kafka:9092"
    elif fault == "index":
        read["elasticsearch"]["index"] = "historical"
    elif fault == "mount":
        services["api"]["volumes"] = []
    elif fault == "dependency":
        image["imports_ok"] = False
    else:
        graph["manifest"] += "-absent"
    with pytest.raises(ValueError):
        check_wiring(graph, read, manifest, services, image)


def test_fixture_and_tampered_same_event(tmp_path):
    root = tmp_path / "fixture"
    result = asyncio.run(run(root))
    assert len(result["scenarios"]) == 6
    assert result["reconciliation_before_corruption"]["same_event_storage_get"]
    assert result["reconciliation_before_corruption"]["ui"] == "pending_browser"
    raw = (root / "canonical.json").read_bytes()
    es = json.loads((root / "es-double.json").read_text())
    snapshot = json.loads((root / "get-snapshot.json").read_text())[0]
    history = json.loads((root / "get-history.json").read_text())["metadata"]["events"][
        0
    ]
    assert same_event(raw, root / "pristine-archive", es, snapshot, history)[
        "same_event_storage_get"
    ]
    for field in ("event_key", "rpm", "torque", "higadura", "tenperatura"):
        with pytest.raises(ValueError):
            same_event(
                raw,
                root / "pristine-archive",
                es,
                {**snapshot, field: "tampered"},
                history,
            )
    # Post-run corruption is deliberately retained and fails mechanical verification.
    with pytest.raises(ValueError, match="Parquet mismatch"):
        same_event(
            (root / "canonical.json").read_bytes(),
            root / "archive",
            json.loads((root / "es-double.json").read_text()),
            json.loads((root / "get-snapshot.json").read_text())[0],
            json.loads((root / "get-history.json").read_text())["metadata"]["events"][
                0
            ],
        )


def test_resolved_compose_without_starting_docker(tmp_path):
    import os
    import shutil
    import sys
    from pathlib import Path

    from scripts.integration_lab import IntegrationLab
    from scripts.integration_verify import check_compose

    if not shutil.which("docker"):
        pytest.skip("Docker CLI unavailable; no Compose verification")
    root = tmp_path / "lab"
    directory = root / "runs" / "own"
    directory.mkdir(parents=True)
    worker = directory / "worker"
    worker.mkdir()
    manifest = directory / "manifest.json"
    manifest.write_text(
        json.dumps(
            {"files": {"rf.pkl": "a" * 64}, "policy": "f2", "risk_threshold": 0.5}
        )
    )
    graph = {
        "root": str(worker),
        "manifest": str(manifest),
        "source_namespace": "own",
        "topic": "own",
        "es_index": "cnc-alerts-own",
        "es_url": "http://elasticsearch:9200",
    }
    (directory / "graph.json").write_text(json.dumps(graph))
    (root / ".env").write_text(
        "NIFI_SENSITIVE_PROPS_KEY=fixture-only\nSINGLE_USER_CREDENTIALS_USERNAME=fixture\nSINGLE_USER_CREDENTIALS_PASSWORD=fixture-only\n"
    )
    instance = IntegrationLab(root)
    instance.state = {
        "project": "cnc-test-config-only",
        "python": sys.executable,
        "uv_python": str(Path(os.path.realpath(sys.executable)).parents[2]),
        "nifi_port": 18443,
        "kafka_port": 19092,
        "runs": ["own"],
    }
    result = instance.compose(
        "--profile",
        "run",
        "--profile",
        "dashboard",
        "config",
        "--format",
        "json",
        run="own",
    )
    config = json.loads(result.stdout)
    assert check_compose(config, graph, sys.executable, str(Path.cwd()))
    config["services"]["api"]["volumes"][0]["read_only"] = False
    # Find the actual archive target rather than assuming Compose ordering.
    for volume in config["services"]["api"]["volumes"]:
        if volume["target"] == "/archive":
            volume["read_only"] = False
    with pytest.raises(ValueError, match="archive writable"):
        check_compose(config, graph, sys.executable, str(Path.cwd()))


def test_history_reconciliation_follows_cursor_and_reports_absence():
    import httpx

    from scripts.integration_lab import find_history_event

    calls = []
    stamp = "2026-10-23T00:00:00Z"

    def handle(request):
        calls.append(dict(request.url.params))
        page = (
            {"metadata": {"events": [{"event_key": "old"}]}, "next_cursor": "page-2"}
            if "cursor" not in request.url.params
            else {
                "metadata": {"events": [{"event_key": "target"}]},
                "next_cursor": None,
            }
        )
        return httpx.Response(200, json=page)

    with httpx.Client(transport=httpx.MockTransport(handle)) as client:
        row, response = find_history_event(
            client, "http://fixture/history", {"event_key": "target", "timestamp": stamp}, "cutoff"
        )
        assert row["event_key"] == "target" and response.status_code == 200
        assert calls == [{"desde": stamp, "hasta": "cutoff"}, {"cursor": "page-2"}]
        with pytest.raises(ValueError, match="absent from complete history"):
            find_history_event(
                client, "http://fixture/history", {"event_key": "absent", "timestamp": stamp}, "cutoff"
            )
        with pytest.raises(ValueError, match="page budget"):
            find_history_event(
                client,
                "http://fixture/history",
                {"event_key": "target", "timestamp": stamp},
                "cutoff",
                max_pages=1,
            )


def test_history_reconciliation_includes_selected_event_older_than_default_day():
    from datetime import UTC, datetime, timedelta

    import httpx

    from scripts.integration_lab import find_history_event

    end = datetime(2026, 11, 6, tzinfo=UTC)
    stamp = datetime(2026, 10, 23, tzinfo=UTC)
    selected = {"event_key": "actual-archived-event", "timestamp": stamp.isoformat()}

    def handle(request):
        start = datetime.fromisoformat(request.url.params["desde"]) if "desde" in request.url.params else end - timedelta(days=1)
        rows = [selected] if start <= stamp < end else []
        return httpx.Response(200, json={"metadata": {"events": rows}, "next_cursor": None})

    with httpx.Client(transport=httpx.MockTransport(handle)) as client:
        row, _ = find_history_event(client, "http://fixture/history", selected, end.isoformat())
    assert row == selected


def test_bundle_preserves_build_inputs_and_detects_extracted_tampering(
    tmp_path, monkeypatch
):
    import zipfile
    from pathlib import Path

    from scripts import integration_bundle, integration_fixture

    evidence = tmp_path / "fixture"
    asyncio.run(run(evidence))
    bundle = tmp_path / "bundle.zip"
    integration_bundle.build(bundle, evidence)
    restored = tmp_path / "restored"
    with zipfile.ZipFile(bundle) as archive:
        archive.extractall(restored)
    for name in (
        "scoring/Dockerfile",
        "dashboard_laneki/Dockerfile",
        "deploy/images/uv-rustls.patch",
        "deploy/images/elasticsearch-patches/pom.xml",
        "tests/fixtures/cg14/valid_event.csv",
        "docker-compose.yml",
        "kibana/acceptance-export.ndjson",
        "nifi-flows/cg14_validate.groovy",
        "cg14_validation/validator.py",
        "deploy/cg14/scripts/kafka-volume.properties",
        "lan/haproxy.cfg",
        "deploy/images/kibana-patches/del-fault-injection.c",
        "scripts/nifi_candidate_context.py",
        "deploy/images/nifi-patches/parquet-jackson/ParquetProbe.java",
    ):
        assert (restored / name).read_bytes() == (Path.cwd() / name).read_bytes()
    monkeypatch.setattr(
        integration_fixture,
        "__file__",
        str(restored / "scripts/integration_fixture.py"),
    )
    assert (
        integration_fixture.source_identity()["member_hashes"]
        == "verified_not_authenticated"
    )
    extra = restored / "scripts/planted_extra.py"
    extra.write_text("# unexpected module")
    with pytest.raises(ValueError, match="Unexpected file"):
        integration_fixture.source_identity()
    extra.unlink()
    target = restored / "scoring/Dockerfile"
    target.write_text(target.read_text() + "\n# changed after restore\n")
    with pytest.raises(ValueError, match="hash mismatch: scoring/Dockerfile"):
        integration_fixture.source_identity()
