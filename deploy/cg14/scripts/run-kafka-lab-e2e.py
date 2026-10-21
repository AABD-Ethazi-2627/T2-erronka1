#!/usr/bin/env python3
"""Run one bounded, synthetic Kafka -> NiFi CG14 lab integration test.

The script reads deploy/cg14/.env locally, creates a fresh 24-hour topic only
on cnc-cg14-kafka-test, and records redacted evidence under data/evidence/.
It never starts/stops unrelated containers or reads/writes real CG13 topics.
"""

from __future__ import annotations

import argparse
import json
import ssl
import subprocess
import sys
import time
import urllib.parse
import urllib.request
import uuid
from datetime import datetime
from pathlib import Path

DEPLOY = Path(__file__).resolve().parents[1]
REPO = DEPLOY.parents[1]
GROUP_ID = "583bcfb5-01a1-1000-de1a-41cdf8ea78fe"
BROKER = "cnc-cg14-kafka-test"
BOOTSTRAP = "cg14-kafka-test:9092"
ALLOWED_ATTRIBUTES = {
    "cg14.event.id",
    "cg14.valid",
    "cg14.code",
    "cg14.source.kind",
    "cg14.source.uri",
    "cg14.record.ref",
    "kafka.topic",
    "kafka.partition",
    "kafka.offset",
    "kafka.key",
    "record.count",
    "invokehttp.status.code",
}


def read_env() -> dict[str, str]:
    result = {}
    for line in (DEPLOY / ".env").read_text(encoding="utf-8").splitlines():
        if "=" in line and not line.lstrip().startswith("#"):
            key, value = line.split("=", 1)
            result[key] = value
    return result


def docker(*args: str, input_bytes: bytes | None = None) -> str:
    result = subprocess.run(
        ["docker", *args], input=input_bytes, capture_output=True, check=True
    )
    return result.stdout.decode("utf-8", errors="replace")


class NifiApi:
    def __init__(self, env: dict[str, str]) -> None:
        self.base = "https://localhost:18443/nifi-api"
        self.ctx = ssl.create_default_context(
            cafile=str(DEPLOY / "secrets/nifi-local.crt")
        )
        request = urllib.request.Request(
            self.base + "/access/token",
            data=urllib.parse.urlencode(
                {
                    "username": env["SINGLE_USER_CREDENTIALS_USERNAME"],
                    "password": env["SINGLE_USER_CREDENTIALS_PASSWORD"],
                }
            ).encode(),
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        with urllib.request.urlopen(request, context=self.ctx, timeout=15) as response:
            self.token = response.read().decode()

    def call(self, path: str, method: str = "GET", payload: dict | None = None) -> dict:
        headers = {"Authorization": "Bearer " + self.token}
        data = None
        if payload is not None:
            headers["Content-Type"] = "application/json"
            data = json.dumps(payload).encode()
        request = urllib.request.Request(
            self.base + path, data=data, headers=headers, method=method
        )
        with urllib.request.urlopen(request, context=self.ctx, timeout=30) as response:
            raw = response.read()
            return json.loads(raw) if raw else {}

    def group_flow(self) -> dict:
        return self.call(f"/flow/process-groups/{GROUP_ID}")["processGroupFlow"]["flow"]

    def components(self) -> dict[str, dict]:
        return {
            p["component"]["name"]: p["component"]
            for p in self.group_flow()["processors"]
        }

    def set_state(self, component_id: str, state: str) -> None:
        entity = self.call(f"/processors/{component_id}")
        self.call(
            f"/processors/{component_id}/run-status",
            "PUT",
            {"revision": entity["revision"], "state": state},
        )

    def metrics(self) -> tuple[dict[str, dict[str, int]], int]:
        data = self.call(f"/flow/process-groups/{GROUP_ID}/status?recursive=true")
        aggregate = data["processGroupStatus"]["aggregateSnapshot"]
        components = {}
        for item in aggregate["processorStatusSnapshots"]:
            snap = item["processorStatusSnapshot"]
            components[snap["id"]] = {
                k: int(snap.get(k, 0) or 0)
                for k in (
                    "flowFilesIn",
                    "flowFilesOut",
                    "taskCount",
                    "bytesIn",
                    "bytesOut",
                )
            }
        return components, int(aggregate.get("flowFilesQueued", 0) or 0)


def provenance_query(api: NifiApi, topic: str) -> list[dict]:
    # The NiFi 2.12 REST DTO rejects object-shaped searchTerms. Query the
    # bounded recent index, then scope locally to this run's unique topic.
    entity = api.call(
        "/provenance",
        "POST",
        {
            "provenance": {
                "request": {
                    "maxResults": 1000,
                    "summarize": False,
                    "incrementalResults": True,
                }
            }
        },
    )
    query_id = entity["provenance"]["id"]
    deadline = time.time() + 45
    while time.time() < deadline:
        entity = api.call(f"/provenance/{query_id}")
        provenance = entity.get("provenance", {})
        if provenance.get("finished"):
            events = provenance.get("results", {}).get("provenanceEvents", [])
            safe = []
            for event in events:
                raw_attrs = event.get("attributes") or []
                if isinstance(raw_attrs, dict):
                    raw_attrs = [{"name": k, "value": v} for k, v in raw_attrs.items()]
                if not any(
                    attr.get("name") == "kafka.topic" and attr.get("value") == topic
                    for attr in raw_attrs
                ):
                    continue
                row = {
                    key: event.get(key)
                    for key in (
                        "eventId",
                        "eventType",
                        "eventTime",
                        "flowFileUuid",
                        "componentId",
                        "componentName",
                        "relationship",
                        "transitUri",
                    )
                    if event.get(key) is not None
                }
                attrs = {}
                for key in ("attributes", "updatedAttributes", "previousAttributes"):
                    values = event.get(key) or []
                    if isinstance(values, dict):
                        values = [{"name": k, "value": v} for k, v in values.items()]
                    for attr in values:
                        name = attr.get("name")
                        if name in ALLOWED_ATTRIBUTES:
                            attrs[name] = attr.get("value")
                if attrs:
                    row["attributes"] = attrs
                safe.append(row)
            api.call(f"/provenance/{query_id}", "DELETE")
            return safe
        time.sleep(1)
    raise TimeoutError("provenance query did not finish")


def parse_group_offset(output: str, topic: str) -> dict | None:
    for line in output.splitlines():
        parts = line.split()
        if len(parts) >= 6 and parts[1] == topic and parts[2].isdigit():
            return {
                "topic": parts[1],
                "partition": int(parts[2]),
                "current_offset": int(parts[3]) if parts[3].isdigit() else None,
                "log_end_offset": int(parts[4]) if parts[4].isdigit() else None,
                "lag": int(parts[5]) if parts[5].isdigit() else None,
            }
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--inject-kafka-outage",
        action="store_true",
        help="run the phase-controlled outage/recovery regression (three isolated repetitions)",
    )
    args = parser.parse_args()
    if args.inject_kafka_outage:
        return subprocess.run(
            [
                sys.executable,
                str(DEPLOY / "scripts/run-kafka-outage-recovery.py"),
                "--runs",
                "3",
            ],
            check=False,
        ).returncode
    env = read_env()
    api = NifiApi(env)
    run_id = datetime.now().strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex[:6]
    topic = "cg14-e2e-" + run_id.lower().replace("-", "")
    group = "cg14-nifi-e2e-" + run_id.lower().replace("-", "")
    evidence_dir = DEPLOY / "data" / "evidence" / "2026-10-20" / ("kafka-e2e-" + run_id)
    evidence_dir.mkdir(parents=True, exist_ok=False)

    # Validate the exact owned services and stop state before creating resources.
    if (
        docker(
            "inspect", "--format", "{{.State.Health.Status}}", "cnc-cg14-kafka-test"
        ).strip()
        != "healthy"
    ):
        raise RuntimeError("CG14 lab Kafka broker is not healthy")
    if (
        docker(
            "inspect", "--format", "{{.State.Health.Status}}", "cnc-cg14-mock-predict"
        ).strip()
        != "healthy"
    ):
        raise RuntimeError(
            "CG14 HTTP mock is not healthy; start the integration-mocks profile first"
        )
    components = api.components()
    expected = {
        "ConsumeKafka — CG14 synthetic E2E",
        "CG14 lab — Kafka source metadata",
        "ExecuteGroovyScript — CG14 contract validator",
        "RouteOnAttribute — accepted or rejected",
        "InvokeHTTP — local CG14 mock only",
        "Local accepted fixture sink — attributes only",
        "Local rejection audit sink — attributes only",
        "DLQ — add failure reason to filename",
        "DLQ — durable local file sink",
        "Local engine-error sink — attributes only",
        "UpdateAttribute — count mock retries",
        "RouteOnAttribute — max two retries",
        "Local HTTP original sink — attributes only",
    }
    missing = expected - components.keys()
    if missing:
        raise RuntimeError("required CG14 lab processors missing")
    running = [p["name"] for p in components.values() if p["state"] == "RUNNING"]
    if running:
        raise RuntimeError(
            "group already has running processors; refusing to interfere"
        )
    consumer = components["ConsumeKafka — CG14 synthetic E2E"]
    if consumer.get("validationErrors", []):
        raise RuntimeError("ConsumeKafka is invalid; refusing to start")

    # Create a unique, isolated topic; never reuse or reset a consumer group.
    docker(
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
    consumer_entity = api.call(f"/processors/{consumer['id']}")
    consumer_component = consumer_entity["component"]
    consumer_component["config"]["properties"].update(
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
        f"/processors/{consumer['id']}",
        "PUT",
        {"revision": consumer_entity["revision"], "component": consumer_component},
    )
    metadata = components["CG14 lab — Kafka source metadata"]
    metadata_entity = api.call(f"/processors/{metadata['id']}")
    metadata_component = metadata_entity["component"]
    metadata_component["config"]["properties"]["cg14.source.uri"] = (
        f"kafka://cg14-kafka-test/{topic}"
    )
    api.call(
        f"/processors/{metadata['id']}",
        "PUT",
        {"revision": metadata_entity["revision"], "component": metadata_component},
    )

    group_info_before = docker(
        "exec",
        BROKER,
        "/opt/kafka/bin/kafka-consumer-groups.sh",
        "--bootstrap-server",
        BOOTSTRAP,
        "--list",
    ).splitlines()
    if group in group_info_before:
        raise RuntimeError("fresh consumer group unexpectedly exists")

    before_metrics, _ = api.metrics()
    dlq_dir = DEPLOY / "data" / "dlq"
    before_dlq = {p.name for p in dlq_dir.iterdir() if p.is_file()}
    started: list[str] = []
    broker_stopped = False
    broker_recovered: bool | None = False if args.inject_kafka_outage else None
    consumer_ran_during_outage = False
    outage_seconds = 0.0
    run_error: str | None = None
    _start_time = datetime.now().astimezone()
    fixture_dir = REPO / "tests" / "fixtures" / "cg14"
    valid = (
        (fixture_dir / "valid_event.csv").read_text(encoding="utf-8").splitlines()[0]
    )
    missing_fields = (
        (fixture_dir / "missing_fields.csv").read_text(encoding="utf-8").splitlines()[0]
    )
    wrong_types = (
        (fixture_dir / "wrong_types.csv").read_text(encoding="utf-8").splitlines()[0]
    )
    header = (fixture_dir / "header.csv").read_text(encoding="utf-8").splitlines()[0]
    records = [
        ("semantic-duplicate", valid),
        ("semantic-duplicate", valid),
        ("missing-fields", missing_fields),
        ("wrong-types", wrong_types),
        ("header", header),
    ]
    wire_data = "".join(f"{key}|{value}\n" for key, value in records).encode()

    # Downstream first; source last. Finally always stop only processors started here.
    order = [
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
        "CG14 lab — Kafka source metadata",
        "ConsumeKafka — CG14 synthetic E2E",
    ]
    try:
        for name in order[:-1]:
            api.set_state(components[name]["id"], "RUNNING")
            started.append(components[name]["id"])
        if args.inject_kafka_outage:
            docker("stop", BROKER)
            broker_stopped = True
            outage_started = time.monotonic()
            consumer = components["ConsumeKafka — CG14 synthetic E2E"]
            api.set_state(consumer["id"], "RUNNING")
            started.append(consumer["id"])
            time.sleep(5)
            consumer_ran_during_outage = (
                api.components()[consumer["name"]]["state"] == "RUNNING"
            )
            docker("start", BROKER)
            recovery_deadline = time.time() + 90
            while time.time() < recovery_deadline:
                if (
                    docker(
                        "inspect", "--format", "{{.State.Health.Status}}", BROKER
                    ).strip()
                    == "healthy"
                ):
                    broker_stopped = False
                    broker_recovered = True
                    break
                time.sleep(1)
            outage_seconds = round(time.monotonic() - outage_started, 2)
            if not broker_recovered:
                raise TimeoutError(
                    "CG14 lab Kafka did not return healthy after restart"
                )
        else:
            consumer = components["ConsumeKafka — CG14 synthetic E2E"]
            api.set_state(consumer["id"], "RUNNING")
            started.append(consumer["id"])
        time.sleep(1)
        _producer = docker(
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
            input_bytes=wire_data,
        )
        deadline = time.time() + 75
        final_metrics: dict[str, dict[str, int]] = {}
        queued = -1
        while time.time() < deadline:
            final_metrics, queued = api.metrics()
            offsets = docker(
                "exec",
                BROKER,
                "/opt/kafka/bin/kafka-consumer-groups.sh",
                "--bootstrap-server",
                BOOTSTRAP,
                "--describe",
                "--group",
                group,
            )
            offset_row = parse_group_offset(offsets, topic)
            consumed = final_metrics[
                components["ConsumeKafka — CG14 synthetic E2E"]["id"]
            ]["flowFilesOut"] - before_metrics.get(
                components["ConsumeKafka — CG14 synthetic E2E"]["id"], {}
            ).get("flowFilesOut", 0)
            if (
                consumed >= len(records)
                and queued == 0
                and offset_row
                and offset_row["lag"] == 0
            ):
                break
            time.sleep(1)
        else:
            run_error = "expected Kafka records did not drain through the CG14 group before timeout"

        # Keep the integration flow running long enough for provenance commits, then stop.
        time.sleep(2)
    finally:
        for component_id in reversed(started):
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
        if broker_stopped:
            try:
                docker("start", BROKER)
                recovery_deadline = time.time() + 90
                while time.time() < recovery_deadline:
                    if (
                        docker(
                            "inspect", "--format", "{{.State.Health.Status}}", BROKER
                        ).strip()
                        == "healthy"
                    ):
                        broker_stopped = False
                        broker_recovered = True
                        break
                    time.sleep(1)
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
        stop_deadline = time.time() + 30
        while time.time() < stop_deadline:
            still_running = [
                p["id"] for p in api.components().values() if p["state"] == "RUNNING"
            ]
            if not still_running:
                break
            time.sleep(1)

    _end_time = datetime.now().astimezone()
    time.sleep(1)
    final_metrics, queued = api.metrics()
    final_flow = api.group_flow()
    current_components = {
        p["component"]["name"]: p["component"] for p in final_flow["processors"]
    }
    after_dlq = {p.name for p in dlq_dir.iterdir() if p.is_file()} - before_dlq
    dlq_rows = []
    for name in sorted(after_dlq):
        path = dlq_dir / name
        try:
            body = json.loads(path.read_text(encoding="utf-8"))
            dlq_rows.append(
                {
                    "name": name,
                    "mode": oct(path.stat().st_mode & 0o777),
                    "code": body.get("code"),
                    "valid": body.get("valid"),
                    "event_id_present": bool(body.get("event_id")),
                }
            )
        except (OSError, json.JSONDecodeError):
            dlq_rows.append(
                {
                    "name": name,
                    "mode": oct(path.stat().st_mode & 0o777),
                    "parseable": False,
                }
            )

    # Provenance is filtered to the source and validator processors, then reduced to safe attributes.
    provenance = {}
    errors = {}
    provenance_names = (
        "ConsumeKafka — CG14 synthetic E2E",
        "ExecuteGroovyScript — CG14 contract validator",
        "RouteOnAttribute — accepted or rejected",
        "InvokeHTTP — local CG14 mock only",
        "DLQ — durable local file sink",
    )
    try:
        topic_events = provenance_query(api, topic)
        for name in provenance_names:
            provenance[name] = [
                event for event in topic_events if event.get("componentName") == name
            ]
    except (
        OSError,
        ValueError,
        KeyError,
        TypeError,
        RuntimeError,
        subprocess.SubprocessError,
    ) as exc:
        errors["topic-scoped-query"] = type(exc).__name__
    all_events = [event for values in provenance.values() for event in values]
    by_uuid: dict[str, dict] = {}
    by_type: dict[str, int] = {}
    for event in all_events:
        by_type[event.get("eventType", "UNKNOWN")] = (
            by_type.get(event.get("eventType", "UNKNOWN"), 0) + 1
        )
        fid = event.get("flowFileUuid")
        if fid:
            row = by_uuid.setdefault(fid, {"flowfile_uuid": fid, "attributes": {}})
            row["attributes"].update(event.get("attributes", {}))
            row.setdefault("events", []).append(
                {
                    k: event.get(k)
                    for k in ("eventType", "eventTime", "componentName", "relationship")
                }
            )
    consumer_name = "ConsumeKafka — CG14 synthetic E2E"
    input_records: dict[str, dict] = {}
    for row in by_uuid.values():
        if not any(
            event.get("componentName") == consumer_name
            and event.get("eventType") == "RECEIVE"
            for event in row["events"]
        ):
            continue
        attrs = row["attributes"]
        record_key = "/".join(
            str(attrs.get(key, ""))
            for key in ("kafka.topic", "kafka.partition", "kafka.offset")
        )
        input_records[record_key] = {
            "flowfile_uuid": row["flowfile_uuid"],
            "topic": attrs.get("kafka.topic"),
            "partition": attrs.get("kafka.partition"),
            "offset": attrs.get("kafka.offset"),
            "record_ref": attrs.get("cg14.record.ref"),
            "event_id": attrs.get("cg14.event.id"),
            "valid": attrs.get("cg14.valid"),
            "code": attrs.get("cg14.code"),
        }
    valid_event_ids = [
        row["event_id"]
        for row in input_records.values()
        if row["valid"] == "true" and row["event_id"]
    ]
    id_counts: dict[str, int] = {}
    for event_id in valid_event_ids:
        id_counts[event_id] = id_counts.get(event_id, 0) + 1
    validation_outcomes: dict[str, int] = {}
    http_status_counts: dict[str, int] = {}
    for row in input_records.values():
        valid = row["valid"]
        code = row["code"] or ("VALID" if valid == "true" else "UNKNOWN")
        validation_outcomes[code] = validation_outcomes.get(code, 0) + 1
        status = next(
            (
                candidate["attributes"].get("invokehttp.status.code")
                for candidate in by_uuid.values()
                if candidate["attributes"].get("kafka.offset") == row["offset"]
                and candidate["attributes"].get("invokehttp.status.code")
            ),
            None,
        )
        if status:
            http_status_counts[status] = http_status_counts.get(status, 0) + 1
    route_outcomes: dict[str, int] = {}
    for event in all_events:
        if (
            event.get("componentName") == "RouteOnAttribute — accepted or rejected"
            and event.get("eventType") == "ROUTE"
        ):
            relationship = event.get("relationship") or "UNKNOWN"
            route_outcomes[relationship] = route_outcomes.get(relationship, 0) + 1

    def delta(component_name: str, field: str) -> int:
        cid = current_components[component_name]["id"]
        return final_metrics.get(cid, {}).get(field, 0) - before_metrics.get(
            cid, {}
        ).get(field, 0)

    output = {
        "run_id": run_id,
        "topic": topic,
        "consumer_group": group,
        "bootstrap_server": BOOTSTRAP,
        "topic_config": {
            "partitions": 1,
            "replication_factor": 1,
            "retention_ms": 86400000,
        },
        "processing_strategy": "FLOW_FILE; each Kafka message is expected to become its own FlowFile",
        "commit_offsets": True,
        "broker_outage_test": {
            "injected": args.inject_kafka_outage,
            "consumer_running_during_outage": consumer_ran_during_outage,
            "recovered_healthy": broker_recovered,
            "outage_seconds": outage_seconds if args.inject_kafka_outage else None,
        },
        "run_status": "VERIFIED" if run_error is None else "PARTIAL",
        "run_error": run_error,
        "produced_messages": len(records),
        "message_classes": {
            "valid": 2,
            "missing_fields": 1,
            "wrong_types": 1,
            "header": 1,
        },
        "offsets_after": offset_row,
        "deltas": {
            name: {
                "flowFilesIn": delta(name, "flowFilesIn"),
                "flowFilesOut": delta(name, "flowFilesOut"),
            }
            for name in (
                "ConsumeKafka — CG14 synthetic E2E",
                "CG14 lab — Kafka source metadata",
                "ExecuteGroovyScript — CG14 contract validator",
                "RouteOnAttribute — accepted or rejected",
                "InvokeHTTP — local CG14 mock only",
                "Local accepted fixture sink — attributes only",
                "DLQ — durable local file sink",
            )
        },
        "dlq_files_created": dlq_rows,
        "queue_flowfiles_after": queued,
        "processor_states_after": {
            name: c["state"] for name, c in current_components.items()
        },
        "provenance_events_by_type": by_type,
        "provenance_flowfiles": list(by_uuid.values()),
        "provenance_input_records": list(input_records.values()),
        "route_relationship_counts_by_record": route_outcomes,
        "validation_outcomes_by_record": validation_outcomes,
        "mock_http_status_flowfiles": http_status_counts,
        "valid_event_id_multiplicity": sorted(id_counts.values()),
        "provenance_query_errors": errors,
        "limitations": [
            "This is an isolated synthetic broker, not the team CG13 broker or topic.",
            "Kafka offsets are committed after consumption; this does not prove exactly-once processing.",
            "The current flow has no persistent idempotent accepted sink; duplicate semantic events are not suppressed.",
            "The HTTP endpoint is a local mock and no production predictor or alert destination was exercised.",
        ],
    }
    (evidence_dir / "e2e-summary.json").write_text(
        json.dumps(output, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "evidence": str(evidence_dir / "e2e-summary.json"),
                "run_status": output["run_status"],
                "run_error": run_error,
                "topic": topic,
                "consumer_group": group,
                "produced": len(records),
                "consumed_flowfiles": output["deltas"][
                    "ConsumeKafka — CG14 synthetic E2E"
                ]["flowFilesOut"],
                "validator_flowfiles": output["deltas"][
                    "ExecuteGroovyScript — CG14 contract validator"
                ]["flowFilesIn"],
                "accepted_sink_flowfiles": output["deltas"][
                    "Local accepted fixture sink — attributes only"
                ]["flowFilesIn"],
                "dlq_created": len(dlq_rows),
                "queued_after": queued,
                "provenance_event_types": by_type,
                "provenance_input_records": len(input_records),
                "route_relationship_counts": route_outcomes,
                "validation_outcomes": validation_outcomes,
                "mock_http_status_flowfiles": http_status_counts,
                "broker_outage_test": output["broker_outage_test"],
                "duplicate_event_id_multiplicities": output[
                    "valid_event_id_multiplicity"
                ],
                "provenance_query_errors": errors,
            },
            ensure_ascii=False,
        )
    )
    return 0 if run_error is None else 1


if __name__ == "__main__":
    raise SystemExit(main())
