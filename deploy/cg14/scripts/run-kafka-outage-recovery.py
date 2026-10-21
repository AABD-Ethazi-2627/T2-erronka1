#!/usr/bin/env python3
"""Controlled Kafka outage/recovery test for the isolated CG14 lab only.

Each repetition uses a fresh retained topic and group. Within a repetition the
same ConsumeKafka processor and group stay active across baseline, outage, and
recovery. No existing topic, group, volume, or offset is reset or deleted.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import re
import subprocess
import sys
import time
import uuid
from datetime import UTC, datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
BASE = HERE / "run-kafka-lab-e2e.py"
spec = importlib.util.spec_from_file_location("cg14_lab_e2e", BASE)
if spec is None or spec.loader is None:
    raise RuntimeError("cannot load CG14 lab API helpers")
e2e = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = e2e
spec.loader.exec_module(e2e)

BROKER = e2e.BROKER
BOOTSTRAP = e2e.BOOTSTRAP
CONSUMER = "ConsumeKafka — CG14 synthetic E2E"
SOURCE_META = "CG14 lab — Kafka source metadata"
ORDER = [
    "DLQ — durable local file sink",
    "DLQ — add failure reason to filename",
    "Local rejection audit sink — attributes only",
    "Local engine-error sink — attributes only",
    "Local accepted fixture sink — attributes only",
    "Local HTTP original sink — attributes only",
    "RouteOnAttribute — max two retries",
    "UpdateAttribute — count mock retries",
    "InvokeHTTP — local CG14 mock only",
    "RouteOnAttribute — accepted or rejected",
    "ExecuteGroovyScript — CG14 contract validator",
    SOURCE_META,
    CONSUMER,
]


def run_docker(*args: str, input_bytes: bytes | None = None) -> str:
    result = subprocess.run(
        ["docker", *args], input=input_bytes, capture_output=True, check=True
    )
    return result.stdout.decode("utf-8", errors="replace")


def broker_ready(api: e2e.NifiApi) -> dict:
    health = run_docker(
        "inspect", "--format", "{{.State.Health.Status}}", BROKER
    ).strip()
    api_versions = run_docker(
        "exec",
        BROKER,
        "/opt/kafka/bin/kafka-broker-api-versions.sh",
        "--bootstrap-server",
        BOOTSTRAP,
    )
    if not api_versions.startswith("cg14-kafka-test:9092"):
        raise RuntimeError(
            "broker metadata did not advertise the expected lab DNS endpoint"
        )
    tcp = run_docker(
        "exec",
        "cnc-cg14-nifi",
        "bash",
        "-lc",
        "</dev/tcp/cg14-kafka-test/9092 && printf TCP_OK",
    ).strip()
    if health != "healthy" or tcp != "TCP_OK":
        raise RuntimeError("broker health or NiFi-to-broker TCP readiness check failed")
    return {
        "health": health,
        "advertised_endpoint": "cg14-kafka-test:9092",
        "nifi_tcp": tcp,
    }


def offset_row(topic: str, group: str) -> dict | None:
    try:
        output = run_docker(
            "exec",
            BROKER,
            "/opt/kafka/bin/kafka-consumer-groups.sh",
            "--bootstrap-server",
            BOOTSTRAP,
            "--describe",
            "--group",
            group,
        )
    except subprocess.CalledProcessError:
        # A new group may not be visible/committed yet; let the bounded phase
        # wait continue instead of converting eventual consistency into failure.
        return None
    return e2e.parse_group_offset(output, topic)


def phase_complete(expected: int, row: dict | None, queued: int) -> bool:
    """Require expected committed offsets and a drained queue.

    NiFi processor counters can reset across component scheduling changes, so
    they are diagnostic only; final RECEIVE provenance verifies emitted events.
    """
    return bool(
        row is not None
        and row.get("current_offset") == row.get("log_end_offset")
        and row.get("current_offset") == expected
        and row.get("lag") == 0
        and queued == 0
    )


def produce(topic: str, rows: list[str], phase: str) -> None:
    wire = "".join(f"{phase}-{i}|{row}\n" for i, row in enumerate(rows)).encode()
    run_docker(
        "exec",
        "-i",
        BROKER,
        "/opt/kafka/bin/kafka-console-producer.sh",
        "--bootstrap-server",
        BOOTSTRAP,
        "--topic",
        topic,
        "--property",
        "parse.key=true",
        "--property",
        "key.separator=|",
        input_bytes=wire,
    )


def wait_for(
    api: e2e.NifiApi,
    topic: str,
    group: str,
    expected_out: int,
    base_out: int,
    timeout: int,
) -> tuple[dict, dict | None, int]:
    consumer_id = api.components()[CONSUMER]["id"]
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        _, queued = api.metrics()
        status = api.call(f"/flow/processors/{consumer_id}/status")["processorStatus"][
            "aggregateSnapshot"
        ]
        row = offset_row(topic, group)
        if phase_complete(expected_out, row, queued):
            return status, row, queued
        time.sleep(1)
    _metrics, queued = api.metrics()
    status = api.call(f"/flow/processors/{consumer_id}/status")["processorStatus"][
        "aggregateSnapshot"
    ]
    return status, offset_row(topic, group), queued


def make_rows(count: int, start: int) -> list[str]:
    fixture = ROOT / "tests/fixtures/cg14/valid_event.csv"
    template = fixture.read_text(encoding="utf-8").splitlines()[0].split(",")
    rows = []
    for i in range(count):
        serial = start + i
        values = list(template)
        values[0] = f"2026-10-20T12:{serial // 60:02d}:{serial % 60:02d}Z"
        values[1] = f"CNC-{(100 + serial) % 1000:03d}"
        rows.append(",".join(values))
    return rows


def safe_log_excerpt(container: str, since_seconds: int = 60) -> list[str]:
    try:
        raw = run_docker("logs", "--since", f"{since_seconds}s", container)
    except subprocess.CalledProcessError as exc:
        raw = (exc.stderr or b"").decode("utf-8", errors="replace")
    result = []
    for line in raw.splitlines():
        if re.search(
            r"kafka|broker|disconnect|timeout|exception|error", line, re.IGNORECASE
        ):
            line = re.sub(
                r"(?i)(password|token|secret)(\s*[=:]\s*)\S+", r"\1\2[REDACTED]", line
            )
            result.append(line[:500])
    return result[-30:]


def bulletin_summary(api: e2e.NifiApi, consumer_id: str) -> list[dict]:
    try:
        data = api.call("/flow/bulletin-board?limit=100")
    except (
        OSError,
        ValueError,
        KeyError,
        TypeError,
        RuntimeError,
        subprocess.SubprocessError,
    ):
        return []
    bulletins = data.get("bulletinBoard", {}).get("bulletins", [])
    rows = []
    for entity in bulletins:
        b = entity.get("bulletin", entity)
        if b.get("sourceId") != consumer_id:
            continue
        message = re.sub(
            r"(?i)(password|token|secret)(\s*[=:]\s*)\S+",
            r"\1\2[REDACTED]",
            b.get("message", ""),
        )
        rows.append(
            {
                "category": b.get("category"),
                "level": b.get("level"),
                "message": message[:500],
            }
        )
    return rows


def run_one(
    api: e2e.NifiApi, run_number: int, timeout: int, outage_seconds: int
) -> dict:
    run_id = (
        datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
        + f"-{run_number}-"
        + uuid.uuid4().hex[:6]
    )
    run_key = run_id.lower().replace("-", "").replace("t", "")
    topic, group = f"cg14-outage-{run_key}", f"cg14-outage-group-{run_key}"
    evidence_dir = (
        HERE.parent
        / "data/evidence"
        / datetime.now(UTC).strftime("%Y-%m-%d")
        / f"outage-{run_id}"
    )
    evidence_dir.mkdir(parents=True, exist_ok=False)
    components = api.components()
    consumer_id = components[CONSUMER]["id"]
    running = [x["name"] for x in components.values() if x["state"] == "RUNNING"]
    if running:
        raise RuntimeError(
            "CG14 Process Group has running processors; refusing to interfere"
        )
    if (
        run_docker(
            "inspect", "--format", "{{.State.Health.Status}}", "cnc-cg14-nifi"
        ).strip()
        != "healthy"
    ):
        raise RuntimeError("NiFi is not healthy")
    _ready_before = broker_ready(api)
    run_docker(
        "exec",
        BROKER,
        "/opt/kafka/bin/kafka-topics.sh",
        "--bootstrap-server",
        BOOTSTRAP,
        "--create",
        "--topic",
        topic,
        "--partitions",
        "1",
        "--replication-factor",
        "1",
        "--config",
        "retention.ms=86400000",
    )

    entity = api.call(f"/processors/{consumer_id}")
    component = entity["component"]
    component["config"]["properties"].update(
        {
            "Topics": topic,
            "Group ID": group,
            "Topic Format": "names",
            "auto.offset.reset": "earliest",
            "Processing Strategy": "FLOW_FILE",
            "Message Demarcator": None,
            "Commit Offsets": "true",
        }
    )
    api.call(
        f"/processors/{consumer_id}",
        "PUT",
        {"revision": entity["revision"], "component": component},
    )
    meta_id = components[SOURCE_META]["id"]
    meta = api.call(f"/processors/{meta_id}")
    meta_component = meta["component"]
    meta_component["config"]["properties"]["cg14.source.uri"] = (
        f"kafka://cg14-kafka-test/{topic}"
    )
    api.call(
        f"/processors/{meta_id}",
        "PUT",
        {"revision": meta["revision"], "component": meta_component},
    )

    before_metrics, _ = api.metrics()
    base_out = before_metrics.get(consumer_id, {}).get("flowFilesOut", 0)
    dlq_dir = HERE.parent / "data/dlq"
    dlq_before = {p.name for p in dlq_dir.iterdir() if p.is_file()}
    start_ids = []
    baseline_rows, recovery_rows = (
        make_rows(3, run_number * 20),
        make_rows(3, run_number * 20 + 10),
    )
    evidence = {
        "run_id": run_id,
        "topic": topic,
        "consumer_group": group,
        "bootstrap_server": BOOTSTRAP,
        "phases": {},
        "result": "PARTIAL",
        "limitations": [
            "Isolated synthetic lab only; not the real CG13 broker or topic.",
            (
                "Kafka commits offsets after ConsumeKafka output; this is "
                "at-least-once behavior, not exactly-once."
            ),
        ],
    }
    broker_stopped = False
    try:
        for name in ORDER[:-1]:
            api.set_state(components[name]["id"], "RUNNING")
            start_ids.append(components[name]["id"])
        api.set_state(consumer_id, "RUNNING")
        start_ids.append(consumer_id)
        active_deadline = time.monotonic() + 30
        while time.monotonic() < active_deadline:
            status = api.call(f"/flow/processors/{consumer_id}/status")[
                "processorStatus"
            ]["aggregateSnapshot"]
            if (
                status.get("runStatus", "").lower() == "running"
                and status.get("activeThreadCount", 0) > 0
            ):
                break
            time.sleep(1)
        else:
            raise TimeoutError(
                "ConsumeKafka did not obtain an active execution thread before baseline"
            )

        produce(topic, baseline_rows, "baseline")
        status, baseline_offset, queue = wait_for(
            api, topic, group, 3, base_out, timeout
        )
        baseline_seen = (
            api.metrics()[0].get(consumer_id, {}).get("flowFilesOut", 0) - base_out
        )
        evidence["phases"]["baseline"] = {
            "produced": 3,
            "consumed_flowfiles": baseline_seen,
            "offset": baseline_offset,
            "queue_flowfiles": queue,
            "active_thread_count": status.get("activeThreadCount"),
            "processor_flowfiles_out_delta_observed": baseline_seen,
            "passed": phase_complete(3, baseline_offset, queue),
        }
        if not evidence["phases"]["baseline"]["passed"]:
            raise TimeoutError(
                "baseline messages did not commit before outage injection"
            )

        outage_started = time.monotonic()
        run_docker("stop", "--time", "5", BROKER)
        broker_stopped = True
        time.sleep(outage_seconds)
        outage_logs = safe_log_excerpt("cnc-cg14-nifi", outage_seconds + 10)
        bullets = bulletin_summary(api, consumer_id)
        same_processor_state = api.components()[CONSUMER]["state"] == "RUNNING"
        evidence["phases"]["outage"] = {
            "duration_seconds": round(time.monotonic() - outage_started, 2),
            "nifi_remained_healthy": run_docker(
                "inspect", "--format", "{{.State.Health.Status}}", "cnc-cg14-nifi"
            ).strip()
            == "healthy",
            "consumer_desired_state": "RUNNING"
            if same_processor_state
            else "NOT_RUNNING",
            "redacted_kafka_log_excerpt": outage_logs,
            "consumer_bulletins": bullets,
            "broker_readiness_after_restore": None,
        }
        run_docker("start", BROKER)
        ready = None
        recovery_deadline = time.monotonic() + 120
        while time.monotonic() < recovery_deadline:
            try:
                ready = broker_ready(api)
                break
            except (
                OSError,
                ValueError,
                KeyError,
                TypeError,
                RuntimeError,
                subprocess.SubprocessError,
            ):
                time.sleep(2)
        if ready is None:
            raise TimeoutError(
                "lab broker did not pass broker API, advertised endpoint, DNS/"
                "TCP readiness"
            )
        broker_stopped = False
        evidence["phases"]["outage"]["broker_readiness_after_restore"] = ready
        outage_status_before = api.call(f"/flow/processors/{consumer_id}/status")[
            "processorStatus"
        ]["aggregateSnapshot"]
        produce(topic, recovery_rows, "recovery")
        status, final_offset, queue = wait_for(api, topic, group, 6, base_out, timeout)
        final_seen = (
            api.metrics()[0].get(consumer_id, {}).get("flowFilesOut", 0) - base_out
        )
        evidence["phases"]["recovery"] = {
            "produced_new": 3,
            "processor_flowfiles_out_delta_observed": final_seen,
            "offset": final_offset,
            "queue_flowfiles": queue,
            "broker_readiness": ready,
            "consumer_active_threads": status.get("activeThreadCount"),
            "consumer_active_threads_before_recovery_publish": outage_status_before.get(
                "activeThreadCount"
            ),
            "passed": phase_complete(6, final_offset, queue),
        }
        if not evidence["phases"]["recovery"]["passed"]:
            raise TimeoutError(
                "recovery records did not drain with expected committed offsets"
            )
        time.sleep(2)
        topic_events = e2e.provenance_query(api, topic)
        receive_events = [
            x
            for x in topic_events
            if x.get("eventType") == "RECEIVE" and x.get("componentName") == CONSUMER
        ]
        identities = {
            (
                x.get("attributes", {}).get("kafka.partition"),
                x.get("attributes", {}).get("kafka.offset"),
            )
            for x in receive_events
        }
        event_attrs: dict[str, dict] = {}
        for event in topic_events:
            fid = event.get("flowFileUuid")
            if not fid:
                continue
            attrs = event.get("attributes") or {}
            event_attrs.setdefault(fid, {}).update(attrs)
        receive_ids = [
            event_attrs.get(x.get("flowFileUuid", ""), {}).get("cg14.event.id")
            for x in receive_events
        ]
        valid_ids = [event_id for event_id in receive_ids if event_id]
        dlq_after = {p.name for p in dlq_dir.iterdir() if p.is_file()} - dlq_before
        evidence["provenance"] = {
            "receive_events": len(receive_events),
            "distinct_partition_offsets": len(identities),
            "event_ids_present": len(valid_ids),
            "distinct_event_ids": len(set(valid_ids)),
            "event_types": {
                kind: sum(x.get("eventType") == kind for x in topic_events)
                for kind in sorted({x.get("eventType") for x in topic_events})
            },
        }
        evidence["dlq"] = {
            "new_files": sorted(dlq_after),
            "new_file_count": len(dlq_after),
            "expected_new_files": 0,
            "passed": len(dlq_after) == 0,
        }
        evidence["phases"]["provenance"] = {
            "passed": len(receive_events) == 6
            and len(identities) == 6
            and len(valid_ids) == 6
            and len(set(valid_ids)) == 6,
        }
        evidence["phases"]["dlq"] = {"passed": evidence["dlq"]["passed"]}
        passed = (
            evidence["phases"]["provenance"]["passed"]
            and evidence["phases"]["dlq"]["passed"]
        )
        evidence["result"] = "VERIFIED" if passed else "PARTIAL"
    except (
        OSError,
        ValueError,
        KeyError,
        TypeError,
        RuntimeError,
        subprocess.SubprocessError,
    ) as exc:
        evidence["error_type"] = type(exc).__name__
        evidence["error"] = str(exc)[:500]
    finally:
        if broker_stopped:
            try:
                run_docker("start", BROKER)
            except (
                OSError,
                ValueError,
                KeyError,
                TypeError,
                RuntimeError,
                subprocess.SubprocessError,
            ):
                print(
                    "Cleanup incomplete; inspect owned resources before retrying.",
                    file=sys.stderr,
                )
        for component_id in reversed(start_ids):
            try:
                api.set_state(component_id, "STOPPED")
            except (
                OSError,
                ValueError,
                KeyError,
                TypeError,
                RuntimeError,
                subprocess.SubprocessError,
            ):
                print(
                    "Cleanup incomplete; inspect owned resources before retrying.",
                    file=sys.stderr,
                )
    evidence["processor_states_after"] = {
        name: c["state"] for name, c in api.components().items()
    }
    evidence["created_at"] = datetime.now(UTC).isoformat()
    evidence["evidence_file"] = str(evidence_dir / "outage-recovery.json")
    (evidence_dir / "outage-recovery.json").write_text(
        json.dumps(evidence, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    return evidence


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runs", type=int, default=3, choices=(1, 2, 3))
    parser.add_argument("--timeout-seconds", type=int, default=120)
    parser.add_argument("--outage-seconds", type=int, default=12)
    args = parser.parse_args()
    if args.timeout_seconds < 30 or args.outage_seconds < 5:
        parser.error("timeouts must be >=30 seconds and outage >=5 seconds")
    api = e2e.NifiApi(e2e.read_env())
    results = []
    for i in range(1, args.runs + 1):
        result = run_one(api, i, args.timeout_seconds, args.outage_seconds)
        results.append(result)
        print(
            json.dumps(
                {
                    "run_id": result["run_id"],
                    "topic": result["topic"],
                    "consumer_group": result["consumer_group"],
                    "result": result["result"],
                    "error": result.get("error"),
                    "evidence": result["evidence_file"],
                },
                ensure_ascii=False,
            )
        )
        if result["result"] != "VERIFIED":
            return 1
    print(
        json.dumps(
            {
                "outage_recovery_runs": len(results),
                "verified": sum(x["result"] == "VERIFIED" for x in results),
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
