"""Owned Kafka record -> real durable worker/API/CG15/ES/GET, then staged replay.

The producer is external; this runner creates no topic and publishes no message.
"""

import argparse
import hashlib
import json
import os
import re
import socket
import subprocess
import sys
import time
import uuid
from datetime import UTC, datetime
from pathlib import Path

import httpx
from kafka import KafkaConsumer, TopicPartition
from kafka.errors import KafkaError

from scripts.archive_consumer import event_key
from scripts.integration_fixture import source_identity
from scripts.integration_http import prepare_es, stop
from scripts.integration_local import local_url
from scripts.integration_verify import same_event
from scripts.integration_worker_local import (
    execute_worker,
    journal_state,
    verify_replay,
)
from scripts.kafka_archive import delivery_id

ROOT = Path(__file__).resolve().parents[1]
OFFSET_TIMEOUT_MS = 15000


def scope_guards(bootstrap, namespace, topic, es_url):
    """Exactly one loopback bootstrap and explicit rehearsal namespaces."""
    if not re.fullmatch(
        r"(?:127[.]0[.]0[.]1|localhost|\[::1\]):[1-9][0-9]{0,4}", bootstrap
    ):
        raise ValueError("One owned loopback Kafka host:port required")
    local_url("http://" + bootstrap)
    if not re.fullmatch(r"local-kafka-[a-z0-9][a-z0-9-]{0,95}", namespace):
        raise ValueError("Own local-kafka namespace required")
    if not re.fullmatch(r"cnc-local-raw-[a-z0-9][a-z0-9-]{0,95}", topic):
        raise ValueError("Own cnc-local-raw topic required")
    return local_url(es_url)


def consumer(bootstrap, group=None):
    return KafkaConsumer(
        bootstrap_servers=bootstrap,
        group_id=group,
        api_version=(3, 7),
        enable_auto_commit=False,
        allow_auto_create_topics=False,
        isolation_level="read_committed",
        request_timeout_ms=15000,
        bootstrap_timeout_ms=15000,
        max_poll_records=1,
    )


def require_loopback_metadata(reader):
    """Pinned kafka-python fork metadata interface; checked on every observation."""
    brokers = reader._client.cluster.brokers()
    if not brokers or any(
        broker.host not in {"127.0.0.1", "localhost", "::1"}
        or type(broker.port) is not int
        or not 1 <= broker.port <= 65535
        for broker in brokers
    ):
        raise ValueError("Broker metadata advertises a non-loopback endpoint")


def capture_record(reader, topic):
    """Manual assignment, no subscription/group and never a commit."""
    partitions = reader.partitions_for_topic(topic)
    if partitions != {0}:
        raise ValueError("Expected an existing single-partition own topic")
    require_loopback_metadata(reader)
    partition = TopicPartition(topic, 0)
    reader.assign([partition])
    begin = reader.beginning_offsets([partition], timeout_ms=OFFSET_TIMEOUT_MS)[
        partition
    ]
    end = reader.end_offsets([partition], timeout_ms=OFFSET_TIMEOUT_MS)[partition]
    if end - begin != 1:
        raise ValueError(
            f"Expected exactly one input record; offsets are [{begin}, {end})"
        )
    reader.seek(partition, begin)
    deadline = time.monotonic() + 15
    while time.monotonic() < deadline:
        records = [
            record
            for batch in reader.poll(timeout_ms=1000, max_records=1).values()
            for record in batch
        ]
        if not records:
            continue
        if len(records) != 1:
            raise ValueError("Unexpected extra broker record")
        record = records[0]
        if (record.topic, record.partition, record.offset) != (topic, 0, begin):
            raise ValueError(
                "Broker record coordinates differ from the captured window"
            )
        if (
            not isinstance(record.value, bytes)
            or not record.value
            or len(record.value) > 8192
        ):
            raise ValueError("Expected bounded raw CSV bytes")
        if record.key is not None and not isinstance(record.key, bytes):
            raise ValueError("Unexpected broker key type")
        return (
            record.value,
            record.key,
            {
                "topic": topic,
                "partition": 0,
                "offset": begin,
                "begin": begin,
                "end": end,
                "timestamp_ms": record.timestamp,
                "bytes": len(record.value),
                "raw_sha256": hashlib.sha256(record.value).hexdigest(),
                "key_is_null": record.key is None,
                "key_sha256": hashlib.sha256(record.key).hexdigest()
                if record.key is not None
                else None,
                "reader_auto_commit": False,
                "reader_group": None,
            },
        )
    raise RuntimeError("Own broker record not readable within 15 seconds")


def broker_state(observer, record):
    """OffsetFetch and log-end reads only; do not subscribe or join the group."""
    tp = TopicPartition(record["topic"], record["partition"])
    state = {
        "committed": observer.committed(tp, timeout_ms=OFFSET_TIMEOUT_MS),
        "end": observer.end_offsets([tp], timeout_ms=OFFSET_TIMEOUT_MS)[tp],
    }
    require_loopback_metadata(observer)
    return state


def require_ack(state, record):
    if state["end"] != record["end"] or state["committed"] != record["offset"] + 1:
        raise ValueError(
            "Broker ACK/end mismatch; input changed or worker did not commit"
        )


def command(
    worker, manifest, namespace, topic, api, es, index, bootstrap, group, *, record=None
):
    scope_guards(bootstrap, namespace, topic, es)
    api = local_url(api)
    if not re.fullmatch(r"cnc-local-kafka-[a-f0-9]{32}", index) or not re.fullmatch(
        r"cnc-local-worker-[a-f0-9]{32}", group
    ):
        raise ValueError("Fresh own index/group names required")
    args = [
        sys.executable,
        "-m",
        "scripts.run_durable_pipeline",
        "--root",
        str(worker),
        "--manifest",
        str(manifest),
        "--source-namespace",
        namespace,
        "--source-kind",
        "lab_fixture",
        "--legacy-source-kind",
        "cg14-lab-kafka",
        "--scoring-url",
        api + "/predict",
        "--es-url",
        es,
        "--es-index",
        index,
        "--attempts",
        "1",
        "--timeout",
        "10",
    ]
    if record is not None:
        if (
            record["topic"] != topic
            or record["partition"] != 0
            or type(record["offset"]) is not int
            or record["offset"] < 0
        ):
            raise ValueError("Captured replay coordinates invalid")
        return args + [
            "stdin",
            "--topic",
            topic,
            "--partition",
            "0",
            "--offset",
            str(record["offset"]),
        ]
    return args + [
        "kafka",
        "--bootstrap-servers",
        bootstrap,
        "--group-id",
        group,
        "--topic",
        topic,
        "--api-version",
        "3.7",
        "--offset-reset",
        "earliest",
        "--max-records",
        "1",
        "--max-polls",
        "12",
        "--max-poll-interval-ms",
        "120000",
    ]


def execute_kafka(command_line, output, env):
    try:
        result = subprocess.run(
            command_line,
            capture_output=True,
            cwd=ROOT,
            env=env,
            timeout=90,
            check=False,
        )
    except subprocess.TimeoutExpired as error:
        (output / "kafka.stdout").write_bytes(error.stdout or b"")
        (output / "kafka.stderr").write_bytes(error.stderr or b"")
        raise RuntimeError("Kafka worker exceeded 90 seconds; logs retained") from error
    (output / "kafka.stdout").write_bytes(result.stdout)
    (output / "kafka.stderr").write_bytes(result.stderr)
    if result.returncode:
        raise RuntimeError(
            f"Kafka worker exited {result.returncode}; inspect kafka.stderr"
        )
    reports = [json.loads(line) for line in result.stdout.splitlines() if line.strip()]
    if reports != [{"completed": 1, "rejected": 0, "replay": 0}]:
        raise ValueError("Expected exactly one completed real Kafka delivery")
    return reports[0]


def run(output, manifest_path, es_url, bootstrap, namespace, topic):
    es_url = scope_guards(bootstrap, namespace, topic, es_url)
    manifest_path = Path(manifest_path).resolve(strict=True)
    manifest = json.loads(manifest_path.read_bytes())
    source = source_identity()
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=False)
    token = uuid.uuid4().hex
    index, group = "cnc-local-kafka-" + token, "cnc-local-worker-" + token
    worker = output / "worker"
    result = {
        "status": "started",
        "source_identity": source,
        "transport": "real_Kafka_then_staged_stdin_replay",
        "source_ack_verified": False,
        "namespace": namespace,
        "topic": topic,
        "group": group,
        "index": index,
        "bootstrap_servers": bootstrap,
        "es_url": es_url,
        "model_kind": "explicit_local_test_bundle_not_approved_deployment",
        "model_manifest_sha256": hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
        "producer_evidence": "external; Filebeat production is not inferred from the payload alone",
        "not_run": [
            "NiFi",
            "SMB",
            "browser",
            "production_model_acceptance",
            "producer_startup",
        ],
        "doubles": [],
    }
    process = reader = observer = None
    try:
        reader = consumer(bootstrap)
        raw, key_bytes, record = capture_record(reader, topic)
        (output / "input.csv").write_bytes(raw)
        (output / "input.key.bin").write_bytes(key_bytes or b"")
        (output / "broker-record.json").write_text(json.dumps(record, indent=2))
        reader.close(autocommit=False)
        reader = None
        observer = consumer(bootstrap, group)
        before_ack = broker_state(observer, record)
        (output / "broker-before.json").write_text(json.dumps(before_ack, indent=2))
        if before_ack != {"committed": None, "end": record["end"]}:
            raise ValueError("Fresh group required and captured input must not change")
        read = {
            "scope": {
                "source_uri": f"kafka://{namespace}/{topic}",
                "model_artifact_sha256": manifest["files"]["rf.pkl"],
                "policy": manifest["policy"],
                "risk_threshold": manifest["risk_threshold"],
            },
            "archive_root": str(worker / "archive"),
            "elasticsearch": {"url": es_url, "index": index},
        }
        (output / "read.json").write_text(json.dumps(read, indent=2))
        with httpx.Client(timeout=20, trust_env=False) as client:
            prepare_es(client, es_url, index)
            with socket.socket() as listener, (output / "api.log").open("wb") as log:
                listener.bind(("127.0.0.1", 0))
                listener.listen(128)
                api = "http://127.0.0.1:" + str(listener.getsockname()[1])
                result["api_url"] = api
                env = {
                    **os.environ,
                    "MODEL_MANIFEST": str(manifest_path),
                    "SCORING_LEDGER": str(output / "canonical.sqlite3"),
                    "CNC_READ_CONFIG": str(output / "read.json"),
                    "OPENBLAS_NUM_THREADS": "1",
                    "OMP_NUM_THREADS": "1",
                }
                process = subprocess.Popen(
                    [
                        sys.executable,
                        "-m",
                        "uvicorn",
                        "scoring.score_api:app",
                        "--fd",
                        str(listener.fileno()),
                    ],
                    cwd=ROOT,
                    env=env,
                    pass_fds=(listener.fileno(),),
                    stdout=log,
                    stderr=log,
                )
                deadline = time.monotonic() + 30
                while True:
                    if process.poll() is not None:
                        raise RuntimeError("Own API exited; inspect api.log")
                    try:
                        if client.get(api + "/health", timeout=1).status_code == 200:
                            break
                    except httpx.TransportError:
                        pass
                    if time.monotonic() >= deadline:
                        raise RuntimeError("Own API readiness exceeded 30 seconds")
                    time.sleep(0.1)
                base = (
                    worker,
                    manifest_path,
                    namespace,
                    topic,
                    api,
                    es_url,
                    index,
                    bootstrap,
                    group,
                )
                kafka_command = command(*base)
                (output / "kafka-command.json").write_text(
                    json.dumps(kafka_command, indent=2)
                )
                result["kafka_worker"] = execute_kafka(kafka_command, output, env)
                after_ack = broker_state(observer, record)
                (output / "broker-after-kafka.json").write_text(
                    json.dumps(after_ack, indent=2)
                )
                require_ack(after_ack, record)
                result["source_ack_verified"] = True
                delivery = delivery_id(
                    namespace, topic, record["partition"], record["offset"]
                )
                before_raw, before = journal_state(worker, delivery, api + "/predict")
                (output / "initial-journal.json").write_text(
                    json.dumps(before, indent=2)
                )
                (output / "canonical.json").write_bytes(before_raw)
                staged_command = command(*base, record=record)
                (output / "replay-command.json").write_text(
                    json.dumps(staged_command, indent=2)
                )
                result["staged_replay"] = execute_worker(
                    staged_command, raw, output, "replay", env
                )
                after_raw, after = journal_state(worker, delivery, api + "/predict")
                (output / "replay-journal.json").write_text(json.dumps(after, indent=2))
                (output / "canonical-replay.json").write_bytes(after_raw)
                verify_replay(raw, before_raw, before, after_raw, after)
                final_ack = broker_state(observer, record)
                (output / "broker-after-staged.json").write_text(
                    json.dumps(final_ack, indent=2)
                )
                require_ack(final_ack, record)
                key = event_key("prediction", json.loads(after_raw))
                client.post(es_url + "/" + index + "/_refresh").raise_for_status()
                cutoff = datetime.now(UTC).isoformat()
                replies = {
                    "snapshot": client.get(
                        api + "/api/makinak", params={"as_of": cutoff}
                    ),
                    "history": client.get(
                        api + "/api/historikoa/CNC-004", params={"as_of": cutoff}
                    ),
                    "kpis": client.get(api + "/api/kpis", params={"as_of": cutoff}),
                    "es": client.get(es_url + "/" + index + "/_doc/" + key),
                }
                for name, reply in replies.items():
                    (output / (name + ".response")).write_bytes(reply.content)
                    reply.raise_for_status()
                    (output / (name + ".json")).write_text(
                        json.dumps(reply.json(), indent=2)
                    )
                snapshots = replies["snapshot"].json()
                history = replies["history"].json()["metadata"]["events"]
                matching = [row for row in history if row["event_key"] == key]
                if (
                    len(snapshots) != 1
                    or len(matching) != 1
                    or replies["kpis"].json()["gertakariak"] != 1
                ):
                    raise ValueError(
                        "Expected one machine, historical event and exact KPI after replay"
                    )
                result["reconciliation"] = same_event(
                    after_raw,
                    worker / "archive",
                    replies["es"].json(),
                    snapshots[0],
                    matching[0],
                )
                result["status"] = "passed"
    except Exception as error:
        result.update(
            status="failed", error_type=type(error).__name__, error=str(error)
        )
        raise
    finally:
        cleanup_errors = []
        for client in (reader, observer):
            if client is not None:
                try:
                    client.close(autocommit=False)
                except (KafkaError, OSError) as error:
                    cleanup_errors.append(type(error).__name__)
        if process is not None:
            try:
                stop(process)
            except (OSError, subprocess.SubprocessError) as error:
                cleanup_errors.append(type(error).__name__)
        result["api_stopped"] = process is None or process.poll() is not None
        if cleanup_errors:
            result.update(status="failed", cleanup_errors=cleanup_errors)
        (output / "result.json").write_text(json.dumps(result, indent=2))
        if cleanup_errors:
            raise RuntimeError("Own client/process cleanup failed; inspect result.json")
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--es-url", required=True)
    parser.add_argument("--bootstrap-servers", required=True)
    parser.add_argument("--source-namespace", required=True)
    parser.add_argument("--topic", required=True)
    parser.add_argument("--owned-es", action="store_true", required=True)
    parser.add_argument("--owned-broker", action="store_true", required=True)
    args = parser.parse_args()
    print(
        json.dumps(
            run(
                args.output,
                args.manifest,
                args.es_url,
                args.bootstrap_servers,
                args.source_namespace,
                args.topic,
            ),
            indent=2,
        )
    )
