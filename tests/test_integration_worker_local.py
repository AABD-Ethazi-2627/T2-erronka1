"""Offline helper/guard tests; no HTTP, Docker, model inference or broker claims."""

import hashlib
import json
import sqlite3
import subprocess
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from cg14_validation.validator import parse_csv_event
from scripts import integration_worker_local as lab


def test_fixture_preserves_sensors_and_labels():
    raw = lab.fixture_row("2026-11-03T10:00:00.123Z")
    original = lab.FIXTURE.read_bytes().strip().split(b",")
    assert raw.strip().split(b",")[2:] == original[2:]
    parsed = parse_csv_event(
        raw.decode(),
        source_kind="cg14-lab-kafka",
        source_uri="kafka://local-worker-unit/cnc-local-raw-unit",
        record_ref="cnc-local-raw-unit/0/0",
    )
    assert parsed.valid
    assert parsed.normalized_event["machine_id"] == "CNC-004"
    assert parsed.normalized_event["timestamp"] == "2026-11-03T10:00:00.123Z"
    assert raw.endswith(b"\n")


@pytest.mark.parametrize("stamp", ["2026-11-03T10:00:00", "2026-11-03T10:00:00+01:00"])
def test_fixture_requires_utc(stamp):
    with pytest.raises(ValueError, match="UTC"):
        lab.fixture_row(stamp)


@pytest.mark.parametrize(
    "url",
    [
        "http://example.com:9200",
        "http://user:secret@localhost:9200",
        "http://localhost:9200/shared",
        "http://localhost:9200/?x=1",
    ],
)
def test_invalid_endpoint_fails_before_files_or_processes(tmp_path, url):
    target = tmp_path / "new"
    with pytest.raises(ValueError, match="loopback"):
        lab.run(target, tmp_path / "absent-manifest", url)
    assert not target.exists()


def test_owned_command_uses_stdin_and_exact_coordinates(tmp_path):
    command = lab.worker_command(
        tmp_path,
        tmp_path / "manifest.json",
        "local-worker-unit",
        "cnc-local-raw-unit",
        "http://127.0.0.1:18271",
        "http://localhost:18272",
        "cnc-local-worker-unit",
    )
    assert command[-7:] == [
        "stdin",
        "--topic",
        "cnc-local-raw-unit",
        "--partition",
        "0",
        "--offset",
        "0",
    ]
    assert "http://127.0.0.1:18271/predict" in command
    with pytest.raises(ValueError, match="namespace"):
        lab.worker_command(
            tmp_path,
            tmp_path / "manifest.json",
            "shared",
            "cnc-local-raw-unit",
            "http://127.0.0.1:18271",
            "http://localhost:18272",
            "cnc-local-worker-unit",
        )


def test_existing_output_never_reused(tmp_path, monkeypatch):
    manifest = tmp_path / "manifest.json"
    manifest.write_text("{}")
    output = tmp_path / "existing"
    output.mkdir()
    (output / "keep").write_text("retained")
    monkeypatch.setattr(lab, "source_identity", lambda: {"dirty": True})
    with pytest.raises(FileExistsError):
        lab.run(output, manifest, "http://127.0.0.1:18272")
    assert (output / "keep").read_text() == "retained"


def test_worker_nonzero_retains_both_streams(tmp_path, monkeypatch):
    monkeypatch.setattr(
        lab.subprocess,
        "run",
        lambda *a, **k: SimpleNamespace(
            returncode=2, stdout=b"partial", stderr=b"failure"
        ),
    )
    with pytest.raises(RuntimeError, match="exited 2"):
        lab.execute_worker(["not-executed"], b"row", tmp_path, "initial", {})
    assert (tmp_path / "initial.stdout").read_bytes() == b"partial"
    assert (tmp_path / "initial.stderr").read_bytes() == b"failure"


def test_worker_timeout_retains_partial_output(tmp_path, monkeypatch):
    def timeout(*args, **kwargs):
        raise subprocess.TimeoutExpired(
            "not-executed", 90, output=b"partial", stderr=b"pending"
        )

    monkeypatch.setattr(lab.subprocess, "run", timeout)
    with pytest.raises(RuntimeError, match="90 seconds"):
        lab.execute_worker(["not-executed"], b"row", tmp_path, "replay", {})
    assert (tmp_path / "replay.stdout").read_bytes() == b"partial"
    assert (tmp_path / "replay.stderr").read_bytes() == b"pending"


def test_worker_accounting_rejects_source_ack(tmp_path, monkeypatch):
    report = {
        "transport": "staged-stdin",
        "source_ack": True,
        "completed": 1,
        "replay": 0,
        "rejected": 0,
    }
    monkeypatch.setattr(
        lab.subprocess,
        "run",
        lambda *a, **k: SimpleNamespace(
            returncode=0, stdout=json.dumps(report).encode(), stderr=b""
        ),
    )
    with pytest.raises(ValueError, match="accounting"):
        lab.execute_worker(["not-executed"], b"row", tmp_path, "initial", {})


def journal(tmp_path):
    raw, response = b"row\n", b'{"canonical":true}'
    (tmp_path / "raw.bin").write_bytes(raw)
    digest = hashlib.sha256(raw).hexdigest()
    with sqlite3.connect(tmp_path / "pipeline.sqlite3") as db:
        db.executescript(
            "CREATE TABLE jobs (id TEXT, fingerprint TEXT, response BLOB, outcome TEXT); CREATE TABLE attempts (id INTEGER, target TEXT, result TEXT); CREATE TABLE objects (path TEXT, hash TEXT);"
        )
        db.execute(
            "INSERT INTO jobs VALUES (?, ?, ?, ?)",
            ("delivery", digest, response, "completed"),
        )
        db.execute(
            "INSERT INTO attempts VALUES (1, ?, '200')",
            ("http://localhost:18271/predict",),
        )
        db.execute("INSERT INTO objects VALUES (?, ?)", ("raw.bin", digest))
    return raw, response


def test_journal_read_and_replay_guards(tmp_path):
    raw, response = journal(tmp_path)
    actual, before = lab.journal_state(
        tmp_path, "delivery", "http://localhost:18271/predict"
    )
    assert actual == response
    after = {
        **before,
        "attempts": [
            *before["attempts"],
            ("http://localhost:18272/index/_create/key", "409"),
        ],
    }
    lab.verify_replay(raw, response, before, response, after)
    with pytest.raises(ValueError, match="one scoring request"):
        lab.verify_replay(
            raw, response, before, response, {**after, "scoring_requests": 2}
        )
    with pytest.raises(ValueError, match="canonical"):
        lab.verify_replay(raw, response, before, b"different", after)
    with pytest.raises(ValueError, match="replay was not observed"):
        lab.verify_replay(raw, response, before, response, before)
    (tmp_path / "raw.bin").write_bytes(b"corruption")
    with pytest.raises(ValueError, match="hash/path"):
        lab.journal_state(tmp_path, "delivery", "http://localhost:18271/predict")


def test_early_run_failure_retains_result_without_starting_api(tmp_path, monkeypatch):
    manifest = tmp_path / "manifest.json"
    manifest.write_text(
        json.dumps(
            {"files": {"rf.pkl": "test-only"}, "policy": "f2", "risk_threshold": 0.2}
        )
    )
    monkeypatch.setattr(
        lab, "source_identity", lambda: {"revision": "unit", "dirty": True}
    )

    def fail(*args):
        raise ValueError("offline injected prepare failure")

    monkeypatch.setattr(lab, "prepare_es", fail)
    output = tmp_path / "new"
    with pytest.raises(ValueError, match="injected"):
        lab.run(output, manifest, "http://127.0.0.1:18272")
    result = json.loads((output / "result.json").read_text())
    assert result["status"] == "failed" and result["api_stopped"]
    assert result["source_ack"] is False and result["source_identity"]["dirty"]
    assert result["error"] == "offline injected prepare failure"
    assert (output / "input.csv").is_file()


def test_cleanup_failure_still_writes_result(tmp_path, monkeypatch):
    """No sockets/services: fail the worker, then also fail process cleanup."""
    manifest = tmp_path / "manifest.json"
    manifest.write_text(
        json.dumps({"files": {"rf.pkl": "unit"}, "policy": "f2", "risk_threshold": 0.2})
    )
    monkeypatch.setattr(lab, "source_identity", lambda: {"revision": "unit"})
    client = Mock()
    client.get.return_value.status_code = 200
    monkeypatch.setattr(
        lab.httpx,
        "Client",
        Mock(
            return_value=Mock(
                __enter__=Mock(return_value=client), __exit__=Mock(return_value=False)
            )
        ),
    )
    listener = Mock()
    listener.getsockname.return_value = ("127.0.0.1", 18271)
    monkeypatch.setattr(
        lab.socket,
        "socket",
        Mock(
            return_value=Mock(
                __enter__=Mock(return_value=listener), __exit__=Mock(return_value=False)
            )
        ),
    )
    monkeypatch.setattr(lab, "prepare_es", Mock())
    process = Mock()
    process.poll.return_value = None
    monkeypatch.setattr(lab.subprocess, "Popen", Mock(return_value=process))
    monkeypatch.setattr(
        lab, "execute_worker", Mock(side_effect=ValueError("offline worker failure"))
    )
    monkeypatch.setattr(
        lab, "stop", Mock(side_effect=subprocess.TimeoutExpired("offline-process", 5))
    )
    output = tmp_path / "new"
    with pytest.raises(RuntimeError, match="cleanup failed"):
        lab.run(output, manifest, "http://127.0.0.1:18272")
    result = json.loads((output / "result.json").read_text())
    assert result["status"] == "failed"
    assert result["error"] == "offline worker failure"
    assert result["cleanup_errors"] == ["TimeoutExpired"]
    assert result["api_stopped"] is False
