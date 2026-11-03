"""Own staged-stdin durable worker -> real API/CG15/ES/GET rehearsal.

No broker, source ACK, NiFi scheduling or approved-model acceptance is implied.
"""

import argparse
import csv
import hashlib
import io
import json
import os
import socket
import sqlite3
import subprocess
import sys
import time
import uuid
from datetime import UTC, datetime
from pathlib import Path

import httpx

from scripts.archive_consumer import event_key
from scripts.integration_fixture import source_identity
from scripts.integration_http import prepare_es, stop
from scripts.integration_local import local_url
from scripts.integration_verify import same_event
from scripts.kafka_archive import delivery_id

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests/fixtures/cg14/valid_event.csv"


def fixture_row(timestamp):
    """Retain fixture sensors/labels, explicitly replace time and machine only."""
    stamp = datetime.fromisoformat(timestamp)
    if stamp.tzinfo is None or stamp.utcoffset().total_seconds() != 0:
        raise ValueError("Explicit UTC fixture timestamp required")
    rows = list(csv.reader(io.StringIO(FIXTURE.read_text())))
    if len(rows) != 1 or len(rows[0]) != 14:
        raise ValueError("Expected one 14-field fixture row")
    rows[0][:2] = [timestamp, "CNC-004"]
    output = io.StringIO(newline="")
    csv.writer(output, lineterminator="\n").writerow(rows[0])
    return output.getvalue().encode()


def worker_command(worker, manifest, namespace, topic, api, es, index):
    api, es = local_url(api), local_url(es)
    if not namespace.startswith("local-worker-") or not topic.startswith(
        "cnc-local-raw-"
    ):
        raise ValueError("Own staged namespace/topic required")
    if not index.startswith("cnc-local-worker-"):
        raise ValueError("Own worker index required")
    return [
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
        "stdin",
        "--topic",
        topic,
        "--partition",
        "0",
        "--offset",
        "0",
    ]


def execute_worker(command, raw, output, label, env):
    """Retain subprocess output even if the worker fails or exceeds its budget."""
    try:
        result = subprocess.run(
            command,
            input=raw,
            capture_output=True,
            cwd=ROOT,
            env=env,
            timeout=90,
            check=False,
        )
    except subprocess.TimeoutExpired as error:
        (output / f"{label}.stdout").write_bytes(error.stdout or b"")
        (output / f"{label}.stderr").write_bytes(error.stderr or b"")
        raise RuntimeError(
            "Worker exceeded 90 seconds; inspect retained logs"
        ) from error
    (output / f"{label}.stdout").write_bytes(result.stdout)
    (output / f"{label}.stderr").write_bytes(result.stderr)
    if result.returncode:
        raise RuntimeError(f"Worker exited {result.returncode}; inspect {label}.stderr")
    report = json.loads(result.stdout)
    expected = {
        "transport": "staged-stdin",
        "source_ack": False,
        "completed": int(label == "initial"),
        "replay": int(label == "replay"),
        "rejected": 0,
    }
    if report != expected:
        raise ValueError("Unexpected worker accounting: " + label)
    return report


def journal_state(worker, delivery, scoring_url):
    """Read the closed CLI's journal, including actual request accounting."""
    with sqlite3.connect(
        (worker / "pipeline.sqlite3").as_uri() + "?mode=ro", uri=True
    ) as db:
        rows = db.execute(
            "SELECT id, fingerprint, response, outcome FROM jobs"
        ).fetchall()
        attempts = db.execute(
            "SELECT target, result FROM attempts ORDER BY id"
        ).fetchall()
        objects = db.execute("SELECT path, hash FROM objects ORDER BY path").fetchall()
    if (
        len(rows) != 1
        or rows[0][0] != delivery
        or rows[0][3] != "completed"
        or rows[0][2] is None
    ):
        raise ValueError("Expected exactly one completed canonical worker job")
    for name, expected in objects:
        path = (worker / name).resolve()
        if (
            not path.is_relative_to(worker.resolve())
            or hashlib.sha256(path.read_bytes()).hexdigest() != expected
        ):
            raise ValueError("Worker journal object hash/path mismatch")
    response = bytes(rows[0][2])
    return response, {
        "delivery_id": rows[0][0],
        "raw_sha256": rows[0][1],
        "outcome": rows[0][3],
        "response_sha256": hashlib.sha256(response).hexdigest(),
        "objects": objects,
        "attempts": attempts,
        "scoring_requests": sum(target == scoring_url for target, _ in attempts),
    }


def verify_replay(raw, before_raw, before, after_raw, after):
    if before_raw != after_raw:
        raise ValueError("Replay changed the canonical worker response")
    for state in (before, after):
        if (
            state["raw_sha256"] != hashlib.sha256(raw).hexdigest()
            or state["scoring_requests"] != 1
        ):
            raise ValueError(
                "Replay must retain raw bytes and reuse one scoring request"
            )
    for key in ("delivery_id", "outcome", "objects", "response_sha256"):
        if before[key] != after[key]:
            raise ValueError("Replay changed worker journal identity: " + key)
    if not any(status == "409" for _, status in after["attempts"]):
        raise ValueError("ES immutable-create replay was not observed")


def run(output, manifest_path, es_url):
    es_url = local_url(es_url)
    manifest_path = Path(manifest_path).resolve(strict=True)
    manifest = json.loads(manifest_path.read_bytes())
    identity = source_identity()
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=False)
    token = uuid.uuid4().hex
    namespace, topic, index = (
        "local-worker-" + token,
        "cnc-local-raw-" + token,
        "cnc-local-worker-" + token,
    )
    worker = output / "worker"
    scope = {
        "source_uri": f"kafka://{namespace}/{topic}",
        "model_artifact_sha256": manifest["files"]["rf.pkl"],
        "policy": manifest["policy"],
        "risk_threshold": manifest["risk_threshold"],
    }
    read = {
        "scope": scope,
        "archive_root": str(worker / "archive"),
        "elasticsearch": {"url": es_url, "index": index},
    }
    (output / "read.json").write_text(json.dumps(read, indent=2))
    result = {
        "status": "started",
        "source_identity": identity,
        "transport": "staged-stdin",
        "source_ack": False,
        "coordinates_origin": "synthetic isolated fixture coordinates, not a broker read",
        "model_kind": "explicit_local_test_bundle_not_approved_deployment",
        "model_manifest_sha256": hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
        "fixture_sha256": hashlib.sha256(FIXTURE.read_bytes()).hexdigest(),
        "fixture_changes": ["current UTC timestamp", "machine_id=CNC-004"],
        "namespace": namespace,
        "topic": topic,
        "index": index,
        "es_url": es_url,
        "not_run": [
            "Kafka",
            "Filebeat",
            "NiFi",
            "SMB",
            "browser",
            "production_model_acceptance",
        ],
        "doubles": [],
    }
    process = None
    try:
        raw = fixture_row(
            datetime.now(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")
        )
        (output / "input.csv").write_bytes(raw)
        result["input_sha256"] = hashlib.sha256(raw).hexdigest()
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
                command = worker_command(
                    worker, manifest_path, namespace, topic, api, es_url, index
                )
                (output / "worker-command.json").write_text(
                    json.dumps(command, indent=2)
                )
                result["initial"] = execute_worker(command, raw, output, "initial", env)
                delivery = delivery_id(namespace, topic, 0, 0)
                before_raw, before = journal_state(worker, delivery, api + "/predict")
                (output / "initial-journal.json").write_text(
                    json.dumps(before, indent=2)
                )
                (output / "canonical.json").write_bytes(before_raw)
                result["replay"] = execute_worker(command, raw, output, "replay", env)
                after_raw, after = journal_state(worker, delivery, api + "/predict")
                (output / "replay-journal.json").write_text(json.dumps(after, indent=2))
                (output / "canonical-replay.json").write_bytes(after_raw)
                verify_replay(raw, before_raw, before, after_raw, after)
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
                result.update(
                    status="passed",
                    worker_replay="same bytes and coordinates; one scoring request; ES create conflict verified",
                )
    except Exception as error:
        result.update(
            status="failed", error_type=type(error).__name__, error=str(error)
        )
        raise
    finally:
        if process is not None:
            stop(process)
        result["api_stopped"] = process is None or process.poll() is not None
        (output / "result.json").write_text(json.dumps(result, indent=2))
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--es-url", required=True)
    parser.add_argument(
        "--owned-es",
        action="store_true",
        required=True,
        help="ES belongs exclusively to this local rehearsal",
    )
    args = parser.parse_args()
    print(json.dumps(run(args.output, args.manifest, args.es_url), indent=2))
