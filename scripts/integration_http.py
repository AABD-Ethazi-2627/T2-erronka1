"""Owned loopback HTTP rehearsal with real model, canonical ledger, CG15 and ES.

No Kafka/NiFi/SMB traversal or approved-model/industrial acceptance is implied.
"""

import argparse
import hashlib
import json
import os
import socket
import subprocess
import sys
import time
import uuid
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlsplit

import httpx

from scripts.archive_consumer import consume, event_key
from scripts.integration_fixture import source_identity
from scripts.integration_verify import same_event
from scripts.run_automatic_graph import check_es

ROOT = Path(__file__).resolve().parents[1]


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


def prepare_es(client, url, index):
    """Install the pinned guard only if absent; never replace an existing guard."""
    if not index.startswith("cnc-local-"):
        raise ValueError("Expected fresh local rehearsal namespace")
    pipeline = json.loads((ROOT / "elasticsearch/ingest-pipeline.json").read_text())
    endpoint = url + "/_ingest/pipeline/cnc-prediction-v1"
    response = client.get(endpoint)
    if response.status_code == 404:
        client.put(endpoint, json=pipeline).raise_for_status()
    else:
        response.raise_for_status()
        installed = response.json()["cnc-prediction-v1"]
        for key in ("created_date_millis", "modified_date_millis"):
            installed.pop(key, None)
        if installed != pipeline:
            raise ValueError("Existing ES guard differs; refusing to overwrite")
    # Direct index creation uses the exact checked-in template body without
    # changing a shared index template or relying on its pattern matching.
    template = json.loads((ROOT / "elasticsearch/index-template.json").read_text())
    client.put(url + "/" + index, json=template["template"]).raise_for_status()
    check_es({"es_url": url, "es_index": index, "timeout": 15})


def stop(process):
    if process.poll() is None:
        process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)


def run(output, manifest_path, es_url):
    es_url = local_url(es_url)
    manifest_path = Path(manifest_path).resolve(strict=True)
    manifest = json.loads(manifest_path.read_text())
    identity = source_identity()
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=False)
    token = uuid.uuid4().hex
    index = "cnc-local-" + token
    source_uri = "fixture://local-http/" + token
    scope = {
        "source_uri": source_uri,
        "model_artifact_sha256": manifest["files"]["rf.pkl"],
        "policy": manifest["policy"],
        "risk_threshold": manifest["risk_threshold"],
    }
    config = {
        "scope": scope,
        "archive_root": str(output / "archive"),
        "elasticsearch": {"url": es_url, "index": index},
    }
    (output / "read.json").write_text(json.dumps(config, indent=2))
    result = {
        "status": "started",
        "source_identity": identity,
        "es_url": es_url,
        "index": index,
        "model_manifest_sha256": hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
        "model_kind": "explicit_local_test_bundle_not_approved_deployment",
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
        with httpx.Client(timeout=20, trust_env=False) as client:
            prepare_es(client, es_url, index)
            with socket.socket() as listener, (output / "api.log").open("wb") as log:
                listener.bind(("127.0.0.1", 0))
                listener.listen(128)
                api = "http://127.0.0.1:" + str(listener.getsockname()[1])
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
                        raise RuntimeError("Own API exited; inspect retained api.log")
                    try:
                        ready = client.get(api + "/health", timeout=1)
                        if ready.status_code == 200:
                            break
                    except httpx.TransportError:
                        pass
                    if time.monotonic() >= deadline:
                        raise RuntimeError("Own API not ready within 30 seconds")
                    time.sleep(0.1)
                samples = []
                for number, rpm in enumerate((1801, 1902)):
                    event = json.loads(
                        (ROOT / "contracts/examples/valid/telemetry.json").read_text()
                    )
                    event.update(
                        machine_id="CNC-004",
                        timestamp=datetime.now(UTC)
                        .isoformat(timespec="milliseconds")
                        .replace("+00:00", "Z"),
                        event_id=hashlib.sha256(
                            f"{token}:{number}".encode()
                        ).hexdigest(),
                        rpm=rpm,
                        process_temp_K=294.15,
                        torque_Nm=5.0,
                        tool_wear_min=7,
                        source={
                            "kind": "lab_fixture",
                            "uri": source_uri,
                            "record_ref": str(number),
                        },
                    )
                    started = time.monotonic()
                    response = client.post(api + "/predict", json=event)
                    response.raise_for_status()
                    raw, prediction = response.content, response.json()
                    replay = client.post(api + "/predict", json=event)
                    replay.raise_for_status()
                    if replay.content != raw:
                        raise ValueError("Canonical HTTP replay differs")
                    key = event_key("prediction", prediction)
                    consume(
                        output / "archive",
                        [(str(number), "prediction", raw)],
                        lambda: None,
                    )
                    indexed = client.put(
                        es_url + "/" + index + "/_create/" + key,
                        content=raw,
                        headers={"Content-Type": "application/json"},
                    )
                    indexed.raise_for_status()
                    consume(
                        output / "archive",
                        [(str(number), "prediction", raw)],
                        lambda: None,
                    )
                    duplicate = client.put(
                        es_url + "/" + index + "/_create/" + key,
                        content=raw,
                        headers={"Content-Type": "application/json"},
                    )
                    if duplicate.status_code != 409:
                        raise ValueError(
                            "Expected ES create conflict for immutable replay"
                        )
                    client.post(es_url + "/" + index + "/_refresh").raise_for_status()
                    cutoff = datetime.now(UTC).isoformat()
                    snap = client.get(api + "/api/makinak", params={"as_of": cutoff})
                    history = client.get(
                        api + "/api/historikoa/CNC-004", params={"as_of": cutoff}
                    )
                    kpis = client.get(api + "/api/kpis", params={"as_of": cutoff})
                    for reply in (snap, history, kpis):
                        reply.raise_for_status()
                    hit = client.get(es_url + "/" + index + "/_doc/" + key)
                    hit.raise_for_status()
                    selected = snap.json()[0]
                    matched = next(
                        row
                        for row in history.json()["metadata"]["events"]
                        if row["event_key"] == key
                    )
                    reconciliation = same_event(
                        raw, output / "archive", hit.json(), selected, matched
                    )
                    if (
                        selected["rpm"] != rpm
                        or kpis.json()["gertakariak"] != number + 1
                    ):
                        raise ValueError("Updated snapshot/KPI not visible")
                    for name, data in (
                        ("telemetry", event),
                        ("canonical", prediction),
                        ("es", hit.json()),
                        ("snapshot", snap.json()),
                        ("history", history.json()),
                        ("kpis", kpis.json()),
                    ):
                        target = output / f"{number}-{name}.json"
                        if name == "canonical":
                            target.write_bytes(raw)
                        else:
                            target.write_text(json.dumps(data, indent=2))
                    reconciliation["post_to_verified_reads_ms"] = (
                        time.monotonic() - started
                    ) * 1000
                    samples.append(reconciliation)
                    time.sleep(0.01)
                result.update(
                    status="passed",
                    samples=samples,
                    api_url=api,
                    scenarios=[
                        "real_HTTP_model_inference",
                        "byte_identical_replay",
                        "CG15_ES_GET_reconciliation",
                        "updated_snapshot",
                        "exact_KPI",
                    ],
                )
    except Exception as error:
        result.update(status="failed", error_type=type(error).__name__)
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
        help="Confirm this is a disposable ES instance owned by this rehearsal",
    )
    args = parser.parse_args()
    print(json.dumps(run(args.output, args.manifest, args.es_url), indent=2))
