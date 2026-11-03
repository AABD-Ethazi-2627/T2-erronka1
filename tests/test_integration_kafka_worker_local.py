"""Offline guard/helper tests with declared Kafka and subprocess doubles."""

import hashlib
import json
import subprocess
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from kafka import TopicPartition
from kafka.errors import KafkaTimeoutError

from scripts import integration_kafka_worker_local as lab

TOPIC = "cnc-local-raw-unit"
NAMESPACE = "local-kafka-unit"
BOOTSTRAP = "127.0.0.1:19094"
ES = "http://127.0.0.1:18272"


@pytest.mark.parametrize(
    "bootstrap",
    [
        "remote.example:9092",
        "127.0.0.1:9092,127.0.0.1:9093",
        "http://127.0.0.1:9092",
        "user:pass@localhost:9092",
        "127.0.0.1:9092/",
        "127.0.0.1:70000",
    ],
)
def test_bootstrap_rejected_before_files_or_network(tmp_path, bootstrap):
    with pytest.raises(ValueError):
        lab.run(tmp_path / "new", tmp_path / "missing", ES, bootstrap, NAMESPACE, TOPIC)
    assert not (tmp_path / "new").exists()


@pytest.mark.parametrize(
    "namespace,topic",
    [("shared", TOPIC), (NAMESPACE, "shared"), (NAMESPACE + "/bad", TOPIC)],
)
def test_owned_names_required(namespace, topic):
    with pytest.raises(ValueError, match="Own"):
        lab.scope_guards(BOOTSTRAP, namespace, topic, ES)


def test_reader_never_autocommits(monkeypatch):
    constructor = Mock(return_value="reader")
    monkeypatch.setattr(lab, "KafkaConsumer", constructor)
    assert lab.consumer(BOOTSTRAP) == "reader"
    kwargs = constructor.call_args.kwargs
    assert kwargs["enable_auto_commit"] is False
    assert kwargs["group_id"] is None
    assert kwargs["allow_auto_create_topics"] is False
    assert kwargs["isolation_level"] == "read_committed"


def fake_reader(*, end=43, host="127.0.0.1", offset=42):
    tp = TopicPartition(TOPIC, 0)
    record = SimpleNamespace(
        topic=TOPIC,
        partition=0,
        offset=offset,
        timestamp=1234,
        value=b"fixture-csv",
        key=b"producer-key",
    )
    reader = Mock()
    reader.partitions_for_topic.return_value = {0}
    reader.beginning_offsets.return_value = {tp: 42}
    reader.end_offsets.return_value = {tp: end}
    reader.poll.return_value = {tp: [record]}
    reader._client.cluster.brokers.return_value = [
        SimpleNamespace(host=host, port=19094)
    ]
    return reader


def test_capture_retains_real_coordinates_key_and_bytes_without_commit():
    reader = fake_reader()
    raw, key, meta = lab.capture_record(reader, TOPIC)
    assert raw == b"fixture-csv" and key == b"producer-key"
    assert meta["offset"] == 42 and meta["end"] == 43
    assert meta["raw_sha256"] == hashlib.sha256(raw).hexdigest()
    reader.seek.assert_called_once_with(TopicPartition(TOPIC, 0), 42)
    reader.beginning_offsets.assert_called_once_with(
        [TopicPartition(TOPIC, 0)], timeout_ms=15000
    )
    reader.end_offsets.assert_called_once_with(
        [TopicPartition(TOPIC, 0)], timeout_ms=15000
    )
    reader.commit.assert_not_called()
    reader.subscribe.assert_not_called()


@pytest.mark.parametrize("end", [42, 44])
def test_capture_rejects_empty_or_multiple_records(end):
    with pytest.raises(ValueError, match="exactly one"):
        lab.capture_record(fake_reader(end=end), TOPIC)


def test_capture_rejects_advertised_external_broker():
    with pytest.raises(ValueError, match="non-loopback"):
        lab.capture_record(fake_reader(host="broker.example"), TOPIC)


def test_capture_rejects_changed_coordinates():
    with pytest.raises(ValueError, match="coordinates"):
        lab.capture_record(fake_reader(offset=43), TOPIC)


@pytest.mark.parametrize(
    "state",
    [
        {"committed": None, "end": 43},
        {"committed": 42, "end": 43},
        {"committed": 43, "end": 44},
    ],
)
def test_ack_requires_expected_committed_offset_and_stable_log_end(state):
    with pytest.raises(ValueError, match="ACK"):
        lab.require_ack(state, {"offset": 42, "end": 43})


def test_ack_observer_does_not_join_or_commit():
    observer = fake_reader()
    observer.committed.return_value = 43
    observer.end_offsets.return_value = {TopicPartition(TOPIC, 0): 43}
    record = {"topic": TOPIC, "partition": 0, "offset": 42, "end": 43}
    state = lab.broker_state(observer, record)
    lab.require_ack(state, record)
    observer.committed.assert_called_once_with(
        TopicPartition(TOPIC, 0), timeout_ms=15000
    )
    observer.end_offsets.assert_called_once_with(
        [TopicPartition(TOPIC, 0)], timeout_ms=15000
    )
    observer.subscribe.assert_not_called()
    observer.assign.assert_not_called()
    observer.poll.assert_not_called()
    observer.commit.assert_not_called()


def test_ack_observer_rechecks_advertised_brokers():
    observer = fake_reader(host="external.example")
    observer.committed.return_value = 43
    with pytest.raises(ValueError, match="non-loopback"):
        lab.broker_state(observer, {"topic": TOPIC, "partition": 0})


@pytest.mark.parametrize(
    "failure",
    ["old_commit", "offset_timeout", "worker_failure", "replay_commit_changed"],
)
def test_run_failures_retain_result_and_stop_api(tmp_path, monkeypatch, failure):
    """Declared socket/HTTP/process/broker doubles; no service or network."""
    manifest = tmp_path / "manifest.json"
    manifest.write_text(
        json.dumps({"files": {"rf.pkl": "unit"}, "policy": "f2", "risk_threshold": 0.2})
    )
    monkeypatch.setattr(
        lab, "source_identity", lambda: {"revision": "unit", "dirty": True}
    )
    reader, observer = fake_reader(), fake_reader()
    committed = {
        "old_commit": [42],
        "offset_timeout": [None, KafkaTimeoutError("offline injected timeout")],
        "worker_failure": [None],
        "replay_commit_changed": [None, 43, 44],
    }
    observer.committed.side_effect = committed[failure]
    monkeypatch.setattr(lab, "consumer", Mock(side_effect=[reader, observer]))
    client = Mock()
    client.get.return_value.status_code = 200
    context = Mock(
        __enter__=Mock(return_value=client), __exit__=Mock(return_value=False)
    )
    monkeypatch.setattr(lab.httpx, "Client", Mock(return_value=context))
    listener = Mock()
    listener.getsockname.return_value = ("127.0.0.1", 18271)
    socket_context = Mock(
        __enter__=Mock(return_value=listener), __exit__=Mock(return_value=False)
    )
    monkeypatch.setattr(lab.socket, "socket", Mock(return_value=socket_context))
    monkeypatch.setattr(lab, "prepare_es", Mock())
    process = Mock()
    process.poll.return_value = None
    start = Mock(return_value=process)
    monkeypatch.setattr(lab.subprocess, "Popen", start)
    stop = Mock(side_effect=lambda p: setattr(p.poll, "return_value", 0))
    monkeypatch.setattr(lab, "stop", stop)
    execute = Mock(return_value={"completed": 1, "rejected": 0, "replay": 0})
    if failure == "worker_failure":
        execute.side_effect = RuntimeError(
            "offline injected worker failure after possible commit"
        )
    monkeypatch.setattr(lab, "execute_kafka", execute)
    monkeypatch.setattr(
        lab, "execute_worker", Mock(return_value={"replay": 1, "source_ack": False})
    )
    monkeypatch.setattr(lab, "journal_state", Mock(return_value=(b"{}", {})))
    monkeypatch.setattr(lab, "verify_replay", Mock())
    output = tmp_path / "new"
    with pytest.raises((ValueError, RuntimeError, KafkaTimeoutError)):
        lab.run(output, manifest, ES, BOOTSTRAP, NAMESPACE, TOPIC)
    result = json.loads((output / "result.json").read_text())
    assert result["status"] == "failed" and result["api_stopped"]
    assert result["source_ack_verified"] is (failure == "replay_commit_changed")
    observer.close.assert_called_once_with(autocommit=False)
    if failure == "old_commit":
        start.assert_not_called()
    else:
        stop.assert_called_once_with(process)


def test_commands_preserve_namespace_and_actual_replay_offset(tmp_path):
    args = (
        tmp_path,
        tmp_path / "manifest",
        NAMESPACE,
        TOPIC,
        "http://127.0.0.1:18271",
        ES,
        "cnc-local-kafka-" + "a" * 32,
        BOOTSTRAP,
        "cnc-local-worker-" + "b" * 32,
    )
    kafka = lab.command(*args)
    staged = lab.command(*args, record={"topic": TOPIC, "partition": 0, "offset": 42})
    assert kafka[kafka.index("--source-namespace") + 1] == NAMESPACE
    assert "kafka" in kafka and "--group-id" in kafka
    assert staged[-7:] == [
        "stdin",
        "--topic",
        TOPIC,
        "--partition",
        "0",
        "--offset",
        "42",
    ]
    assert "--group-id" not in staged
    assert kafka[: kafka.index("kafka")] == staged[: staged.index("stdin")]


def test_kafka_report_and_logs_are_retained(tmp_path, monkeypatch):
    payload = b'{"completed":1,"rejected":0,"replay":0}\n'
    monkeypatch.setattr(
        lab.subprocess,
        "run",
        lambda *a, **k: SimpleNamespace(
            returncode=0, stdout=payload, stderr=b"diagnostic"
        ),
    )
    assert lab.execute_kafka(["not-executed"], tmp_path, {})["completed"] == 1
    assert (tmp_path / "kafka.stdout").read_bytes() == payload
    assert (tmp_path / "kafka.stderr").read_bytes() == b"diagnostic"


def test_kafka_timeout_retains_partial_logs(tmp_path, monkeypatch):
    def timeout(*args, **kwargs):
        raise subprocess.TimeoutExpired(
            "not-executed", 90, output=b"partial", stderr=b"pending"
        )

    monkeypatch.setattr(lab.subprocess, "run", timeout)
    with pytest.raises(RuntimeError, match="90 seconds"):
        lab.execute_kafka(["not-executed"], tmp_path, {})
    assert (tmp_path / "kafka.stdout").read_bytes() == b"partial"
    assert (tmp_path / "kafka.stderr").read_bytes() == b"pending"


def test_kafka_empty_run_is_not_success(tmp_path, monkeypatch):
    monkeypatch.setattr(
        lab.subprocess,
        "run",
        lambda *a, **k: SimpleNamespace(returncode=0, stdout=b"", stderr=b""),
    )
    with pytest.raises(ValueError, match="one completed"):
        lab.execute_kafka(["not-executed"], tmp_path, {})


def test_existing_output_preserved(tmp_path, monkeypatch):
    manifest = tmp_path / "manifest.json"
    manifest.write_text("{}")
    output = tmp_path / "existing"
    output.mkdir()
    (output / "keep").write_text("retained")
    monkeypatch.setattr(lab, "source_identity", lambda: {"dirty": True})
    with pytest.raises(FileExistsError):
        lab.run(output, manifest, ES, BOOTSTRAP, NAMESPACE, TOPIC)
    assert (output / "keep").read_text() == "retained"


def test_capture_failure_retains_result_and_closes_without_commit(
    tmp_path, monkeypatch
):
    manifest = tmp_path / "manifest.json"
    manifest.write_text("{}")
    reader = fake_reader(end=42)
    monkeypatch.setattr(
        lab, "source_identity", lambda: {"dirty": True, "revision": "unit"}
    )
    monkeypatch.setattr(lab, "consumer", lambda *a: reader)
    output = tmp_path / "new"
    with pytest.raises(ValueError, match="exactly one"):
        lab.run(output, manifest, ES, BOOTSTRAP, NAMESPACE, TOPIC)
    result = json.loads((output / "result.json").read_text())
    assert result["status"] == "failed" and result["api_stopped"]
    assert result["source_ack_verified"] is False
    reader.close.assert_called_once_with(autocommit=False)
