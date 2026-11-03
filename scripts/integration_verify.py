"""Fail-closed integration checks; static, image, fixture and browser evidence differ."""

import hashlib
import json
import shutil
import sqlite3
from pathlib import Path

from scripts.archive_consumer import event_key


def check_wiring(graph, read, manifest, services, image):
    expected = {
        "scoring_url": "http://api:8000/predict",
        "es_url": "http://elasticsearch:9200",
        "bootstrap_servers": "kafka:19092",
    }
    for key, value in expected.items():
        if graph.get(key) != value:
            raise ValueError(f"hostname/listener mismatch: {key}")
    if (
        not Path(graph["manifest"]).is_file()
        or json.loads(Path(graph["manifest"]).read_text()) != manifest
    ):
        raise ValueError("manifest missing/mismatch")
    if read["scope"] != {
        "source_uri": f"kafka://{graph['source_namespace']}/{graph['topic']}",
        "model_artifact_sha256": manifest["files"]["rf.pkl"],
        "policy": manifest["policy"],
        "risk_threshold": manifest["risk_threshold"],
    }:
        raise ValueError("scope/manifest mismatch")
    if read["elasticsearch"] != {
        "url": graph["es_url"],
        "index": graph["es_index"] + "-read",
    }:
        raise ValueError("index/alias mismatch")
    if (
        read["archive_root"] != "/archive"
        or f"{graph['root']}/archive:/archive:ro" not in services["api"]["volumes"]
    ):
        raise ValueError("read-only archive mount missing")
    if not services["nifi"].get("volumes"):
        raise ValueError("worker runtime mount missing")
    if not image.get("imports_ok") or image.get("duckdb") != "2.0.0":
        raise ValueError("image dependency mismatch")
    return True


def resources(path):
    mem = dict(
        line.split(":", 1) for line in Path("/proc/meminfo").read_text().splitlines()
    )
    ram = int(mem["MemAvailable"].split()[0]) / 2**20
    disk = shutil.disk_usage(path).free / 2**30
    return {
        "available_ram_gib": ram,
        "available_disk_gib": disk,
        "required_ram_gib": 6,
        "required_disk_gib": 20,
        "real_lab": "blocked_resources" if ram < 6 or disk < 20 else "not_run",
    }


def same_event(raw, archive, es, snapshot, history, ui=None):
    """Require raw evidence at every boundary. UI is optional but never inferred."""
    row = json.loads(raw)
    key = event_key("prediction", row)
    canonical = json.dumps(
        row, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode()
    with sqlite3.connect(
        (Path(archive) / "ledger.sqlite").as_uri() + "?mode=ro", uri=True
    ) as db:
        receipt = db.execute("select hash from events where id=?", (key,)).fetchone()
        if receipt != (hashlib.sha256(canonical).hexdigest(),):
            raise ValueError("CG15 canonical receipt mismatch")
        objects = db.execute("select path,hash from objects").fetchall()
        deliveries = db.execute("select hash,outcome from deliveries").fetchall()
    fingerprint = hashlib.sha256(b"prediction\0" + raw).hexdigest()
    if (fingerprint, "stored") not in deliveries and (
        fingerprint,
        "duplicate",
    ) not in deliveries:
        raise ValueError("accepted delivery missing")
    import pyarrow as pa
    import pyarrow.parquet as pq

    paths = [(p, h) for p, h in objects if p.endswith("/" + key + ".parquet")]
    if len(paths) != 1:
        raise ValueError("Parquet receipt missing")
    p, sha = paths[0]
    target = (Path(archive) / p).resolve()
    if not target.is_relative_to(Path(archive).resolve()):
        raise ValueError("archive path escape")
    data = target.read_bytes()
    if (
        hashlib.sha256(data).hexdigest() != sha
        or json.loads(pq.read_table(pa.BufferReader(data))["payload_json"][0].as_py())
        != row
    ):
        raise ValueError("Parquet mismatch")
    if es.get("_id") != key or es.get("_source") != row:
        raise ValueError("ES canonical mismatch")
    for record in (snapshot, history):
        for field in ("event_id", "model_artifact_sha256", "policy", "source"):
            if record.get(field) != row[field]:
                raise ValueError("GET identity mismatch: " + field)
        if record.get("event_key") != key:
            raise ValueError("GET key mismatch")
        for field, expected in {
            "tenperatura": row["process_temp_K"] - 273.15,
            "rpm": row["rpm"],
            "torque": row["torque_Nm"],
            "higadura": row["tool_wear_min"],
        }.items():
            if record.get(field) != expected:
                raise ValueError("GET sentinel mismatch: " + field)
    if ui is not None and (
        ui.get("event_key") != key
        or ui.get("snapshot") != snapshot
        or not ui.get("artifact_sha256")
    ):
        raise ValueError("UI evidence mismatch")
    return {
        "event_key": key,
        "canonical_sha256": hashlib.sha256(canonical).hexdigest(),
        "ui": "supplied_separate_evidence" if ui else "pending_browser",
        "same_event_storage_get": True,
    }


def check_compose(config, graph, python, checkout):
    """Check resolved Docker Compose output, not just an intended graph."""
    services = config["services"]
    if not {"api", "nifi", "kafka", "elasticsearch", "filebeat", "streamlit"} <= set(
        services
    ):
        raise ValueError("service hostname missing")
    kafka = services["kafka"]["environment"]
    if (
        "PLAINTEXT://kafka:19092" not in kafka["KAFKA_ADVERTISED_LISTENERS"]
        or "PLAINTEXT://:19092" not in kafka["KAFKA_LISTENERS"]
    ):
        raise ValueError("Kafka listener mismatch")
    for service in services.values():
        for port in service.get("ports", []):
            if port.get("host_ip") != "127.0.0.1":
                raise ValueError("non-loopback published port")
    for path in (python, checkout, graph["manifest"], graph["root"]):
        if not Path(path).exists():
            raise ValueError("worker path absent: " + path)
        matches = [
            v
            for v in services["nifi"]["volumes"]
            if v["type"] == "bind"
            and Path(path).is_relative_to(v["target"])
            and v["source"] == v["target"]
        ]
        if not matches:
            raise ValueError("worker path not mounted: " + path)
    for target in ("/archive", graph["root"] + "/archive"):
        if not any(
            v["target"] == target
            and v.get("read_only")
            and v["source"] == graph["root"] + "/archive"
            for v in services["api"]["volumes"]
        ):
            raise ValueError("archive writable or absent")
    if services["nifi"]["environment"].get("NIFI_WEB_HTTPS_PORT") != "8443":
        raise ValueError("NiFi TLS mismatch")
    ui = services["streamlit"]
    if (
        ui.get("build", {}).get("dockerfile") != "dashboard_laneki/Dockerfile"
        or not ui.get("read_only")
        or ui.get("volumes")
        or ui.get("user") != "65532:65532"
    ):
        raise ValueError("UI must use its isolated locked image without host runtimes")
    if (
        services["streamlit"]["environment"].get("LANEKI_API_URL")
        != "http://api:8000/api"
    ):
        raise ValueError("UI API endpoint mismatch")
    return True
