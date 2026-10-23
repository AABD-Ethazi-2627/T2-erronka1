"Capture active configuration and versions, before stopping own resources."

import hashlib
import json
import platform
from datetime import UTC, datetime
from importlib.metadata import version

import lab

E, ROOT, S, C = lab.E, lab.ROOT, lab.S, lab.C
evidence = json.loads((E / "same-event.json").read_text())
key = hashlib.sha256(evidence["worker_delivery_id"].encode()).hexdigest()
paths = [
    ROOT / "input/normal.csv",
    ROOT / "worker/raw" / f"{key}.bin",
    ROOT / "worker/identity" / f"{key}.json",
]
paths.extend(ROOT / row["path"] for row in evidence["parquet"])
times = {
    str(p.relative_to(ROOT)): datetime.fromtimestamp(p.stat().st_mtime, UTC).isoformat()
    for p in paths
}
capture = {
    "captured_utc": datetime.now(UTC).isoformat(),
    "python": platform.python_version(),
    "libraries": {
        name: version(name)
        for name in ("httpx", "uvicorn", "fastapi", "pyarrow", "kafka-python")
    },
    "es": lab.es("GET", "/").json(),
    "nifi": lab.api("GET", "/flow/about"),
    "source_artifacts_mtime_utc": times,
    "timing_scope": (
        "filesystem mtime observations, not indep"
        "endent per-stage latency instrumentation"
        " or SLA; scored_at is canonical inferenc"
        "e time, timestamp is fixture event time"
    ),
    "api_metrics_after_recovery": lab.client.get(
        "http://127.0.0.1:" + str(S["api_port"]) + "/metrics"
    ).json(),
}
(E / "versions-and-timing.json").write_text(json.dumps(capture, indent=2) + "\n")
for name, path in {
    "es-final-pipeline.json": "/_ingest/pipeline/cnc-prediction-v1",
    "es-final-template.json": "/_index_template/cnc-lab-v1",
    "es-mapping.json": "/" + S["index"] + "/_mapping",
}.items():
    (E / name).write_text(json.dumps(lab.es("GET", path).json(), indent=2) + "\n")
print("Captured versions, active ES settings and artifact times")
