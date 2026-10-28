"""Local supplementary benchmark. No training, no shared services."""

import hashlib
import json
import os
import resource
import subprocess
import sys
import time
from concurrent import futures
from pathlib import Path

import httpx
import joblib
import pandas as pd

from scripts.cg32_lab import free_port, verify_bundle
from scripts.cg32_load import SENSORS, nominal_rows, percentiles

repo = Path.cwd()
root = Path("/home/admin/labs/cg32-rebuilt-20261028")
manifest = root / "api/manifest.json"
identity = verify_bundle(
    manifest, repo / "docs/evidence/CG32_REBUILT_IDENTITY_20261028.json"
)
output = {
    "identity_kind": identity["identity_kind"],
    "manifest_sha256": identity["sha256"],
    "identity_record_sha256": identity["identity_record_sha256"],
    "scope": "Supplementary same-host candidate benchmark; no graph concurrency change",
    "cold_load": [],
    "in_process": [],
    "http": [],
    "not_applicable": {
        "HTTP_batch32": "API contract accepts one event per request; no batch endpoint",
        "graph_concurrency4": "single offset owner and ledger/ACK guarantees preserved; no additional graph consumer",
    },
}
for _ in range(3):
    start = time.perf_counter()
    code = "import joblib,time,resource,json,sys; from pathlib import Path; p=Path(sys.argv[1]); t=time.perf_counter(); models=[joblib.load(p/n) for n in ('rf.pkl','if.pkl')]; print(json.dumps({'load_ms':(time.perf_counter()-t)*1000,'peak_rss_kib':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss}))"
    result = subprocess.run(
        [sys.executable, "-c", code, str(manifest.parent)],
        check=True,
        text=True,
        capture_output=True,
    )
    output["cold_load"].append(
        {
            **json.loads(result.stdout),
            "process_wall_ms": (time.perf_counter() - start) * 1000,
        }
    )
models = [joblib.load(manifest.parent / n) for n in ("rf.pkl", "if.pkl")]
rows = nominal_rows(repo / "data/ai4i2020_train.csv", 32)
frames = {
    n: pd.DataFrame(
        [
            {
                c: r[c] if c == "machine_type" else float(r[c])
                for c in ["machine_type", *SENSORS]
            }
            for r in rows[:n]
        ]
    )
    for n in (1, 32)
}
for n, frame in frames.items():
    for workers in (1, 4):

        def predict(_, frame=frame):
            start = time.perf_counter()
            models[0].predict_proba(frame)
            models[1].score_samples(frame)
            return (time.perf_counter() - start) * 1000

        for i in range(20):
            predict(i)
        cpu_start = time.process_time()
        start = time.perf_counter()
        with futures.ThreadPoolExecutor(max_workers=workers) as pool:
            values = list(pool.map(predict, range(100)))
        elapsed = time.perf_counter() - start
        output["in_process"].append(
            {
                "batch_size": n,
                "concurrency": workers,
                "warmup_excluded": 20,
                "latency_ms": percentiles(values),
                "rows_per_s": 100 * n / elapsed,
                "driver_cpu_s": time.process_time() - cpu_start,
            }
        )
port = free_port()
ledger = root / "supplement-ledger.sqlite3"
timing = root / "supplement-api-timing.jsonl"
assert not ledger.exists() and not timing.exists()
with (root / "supplement-api.log").open("x") as log:
    start = time.perf_counter()
    env = {**os.environ, "PYTHONPATH": str(repo)}
    process = subprocess.Popen(
        [
            sys.executable,
            str(repo / "deploy/cg32/api_server.py"),
            str(manifest),
            str(ledger),
            str(timing),
            "127.0.0.1",
            str(port),
        ],
        stdout=log,
        stderr=log,
        env=env,
    )
    try:
        with httpx.Client(
            base_url=f"http://127.0.0.1:{port}", trust_env=False, timeout=30
        ) as client:
            deadline = time.monotonic() + 60
            while True:
                if process.poll() is not None:
                    raise RuntimeError("API process exited")
                try:
                    if client.get("/health").status_code == 200:
                        break
                except httpx.TransportError:
                    pass
                if time.monotonic() > deadline:
                    raise TimeoutError("API readiness")
                time.sleep(0.1)
            output["HTTP_cold_start_to_ready_ms"] = (time.perf_counter() - start) * 1000
            template = json.loads(
                (repo / "contracts/examples/valid/telemetry.json").read_text()
            )
            for workers in (1, 4):

                def post(i, workers=workers):
                    payload = {
                        **template,
                        "event_id": hashlib.sha256(
                            f"cg32-supplement-{workers}-{i}".encode()
                        ).hexdigest(),
                    }
                    start = time.perf_counter()
                    response = client.post("/predict", json=payload)
                    elapsed = (time.perf_counter() - start) * 1000
                    assert response.status_code == 200, response.text
                    assert response.json()["event_id"] == payload["event_id"]
                    return elapsed

                for i in range(-20, 0):
                    post(i)
                cpu_start = sum(
                    int(x)
                    for x in Path(f"/proc/{process.pid}/stat")
                    .read_text()
                    .split()[13:15]
                )
                start = time.perf_counter()
                with futures.ThreadPoolExecutor(max_workers=workers) as pool:
                    values = list(pool.map(post, range(100)))
                output["http"].append(
                    {
                        "batch_size": 1,
                        "concurrency": workers,
                        "warmup_excluded": 20,
                        "latency_ms": percentiles(values),
                        "requests_per_s": 100 / (time.perf_counter() - start),
                        "server_cpu_s": (
                            sum(
                                int(x)
                                for x in Path(f"/proc/{process.pid}/stat")
                                .read_text()
                                .split()[13:15]
                            )
                            - cpu_start
                        )
                        / os.sysconf("SC_CLK_TCK"),
                    }
                )
    finally:
        process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()
output["artifact_bytes"] = {
    n: (manifest.parent / n).stat().st_size
    for n in ("manifest.json", "rf.pkl", "if.pkl")
}
output["peak_driver_rss_kib"] = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
(root / "supplement-benchmark.json").write_text(json.dumps(output, indent=2) + "\n")
print("Supplement benchmark completed")
