"""Isolated current-state API rehearsal; no sockets, SMB or shared services."""

import argparse
import asyncio
import hashlib
import json
import platform
import subprocess
import tempfile
from contextlib import AsyncExitStack, asynccontextmanager
from datetime import UTC, datetime
from pathlib import Path

from httpx import ASGITransport, AsyncClient

from scoring.preparation import split_development
from scoring.scope import INPUT_FEATURES, SCOPE, load_training_source
from scoring.score_api import create_app

# First normal/failure examples in the existing seeded FIT partition, not a test.
CASES = {"normal_fit_example": 1386, "failure_fit_example": 679}


def require(condition, message):
    if not condition:
        raise ValueError(message)


@asynccontextmanager
async def _rehearsal_client(app):
    # HTTPX does not run lifespan. Keep shutdown separate from request errors:
    # the application's cleanup after yield must still run on normal closure.
    lifespan = AsyncExitStack()
    try:
        await lifespan.enter_async_context(app.router.lifespan_context(app))
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://testserver"
        ) as client:
            yield client
    finally:
        await lifespan.aclose()


async def _checkout_head():
    return (
        await asyncio.to_thread(
            subprocess.check_output, ["git", "rev-parse", "HEAD"], text=True
        )
    ).strip()


def rehearsal(manifest_path):
    return asyncio.run(_rehearsal(manifest_path))


async def _rehearsal(manifest_path):
    manifest_path = Path(manifest_path)
    manifest = json.loads(manifest_path.read_text())
    train, _, _ = split_development(load_training_source())
    payloads = {}
    for name, index in CASES.items():
        row = train.loc[index]
        payloads[name] = {
            "event_id": hashlib.sha256(f"cg26:fit-row:{index}".encode()).hexdigest(),
            "machine_id": row.machine_id,
            "timestamp": "2026-10-21T00:00:00Z",
            "schema_version": "0.1.0",
            "quality_flag": "OK",
            "source": {
                "kind": "lab_fixture",
                "uri": "data/ai4i2020_train.csv",
                "record_ref": f"zero-based-data-row:{index};fit;demo-only",
            },
            **{
                field: str(row[field]) if field == "machine_type" else float(row[field])
                for field in INPUT_FEATURES
            },
        }

    async with _rehearsal_client(create_app(manifest_path)) as client:
        health = await client.get("/health")
        require(health.status_code == 200, f"Bundle not ready: {health.status_code}")
        require(health.json()["prediction_scope"] == SCOPE["prediction_scope"], "Scope")
        results = {}
        for name, payload in payloads.items():
            response = await client.post("/predict", json=payload)
            require(response.status_code == 200, f"{name}: {response.text}")
            result = response.json()
            require(result["temporal_prediction_enabled"] is False, "Temporal output")
            require(result["score_semantics"] == SCOPE["score_semantics"], "Semantics")
            results[name] = {"http_status": response.status_code, "prediction": result}
        normal = results["normal_fit_example"]["prediction"]
        failure = results["failure_fit_example"]["prediction"]
        require(normal["alert_level"] == "OK" and not normal["risk_alert"], "Normal RF")
        require(failure["risk_alert"], "Failure example did not trigger RF alert")

        payload = payloads["normal_fit_example"]
        rejections = {}
        for field in [
            "machine_failure",
            "failure_TWF",
            "failure_HDF",
            "failure_PWF",
            "failure_OSF",
            "failure_RNF",
            "eta_minutes",
            "rul_minutes",
        ]:
            response = await client.post("/predict", json={**payload, field: 1})
            require(response.status_code == 422, f"Accepted forbidden field {field}")
            rejections[field] = response.status_code
        for name, invalid in {
            "negative_rpm": {**payload, "rpm": -1},
            "raw_record": {
                **payload,
                "source": {**payload["source"], "raw_record": "0,1"},
            },
        }.items():
            response = await client.post("/predict", json=invalid)
            require(response.status_code == 422, f"Accepted invalid case {name}")
            rejections[name] = response.status_code
        response = await client.post(
            "/predict",
            json={
                **payload,
                "machine_id": "CNC-099",
                "timestamp": "2000-01-01T00:00:00Z",
            },
        )
        require(response.status_code == 200, "Trace-only variant rejected")
        for field in [
            "failure_score",
            "anomaly_score",
            "risk_alert",
            "anomaly_alert",
            "alert_level",
        ]:
            require(response.json()[field] == normal[field], f"Trace affects {field}")

    # A missing manifest is exercised in memory too; no existing bundle is modified.
    with tempfile.TemporaryDirectory() as directory:
        async with _rehearsal_client(
            create_app(Path(directory) / "manifest.json")
        ) as client:
            missing_health = (await client.get("/health")).status_code
            missing_predict = (await client.post("/predict", json=payload)).status_code
            require(
                missing_health == missing_predict == 503,
                "Missing bundle did not fail closed",
            )

    return {
        "status": "isolated_rehearsal_passed",
        "executed_at_utc": datetime.now(UTC).isoformat(),
        "checkout_head": await _checkout_head(),
        "python": platform.python_version(),
        "scope": SCOPE,
        "source_rows": 8000,
        "manifest_sha256": hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
        "execution_files_sha256": {
            name: hashlib.sha256(Path(name).read_bytes()).hexdigest()
            for name in ["scripts/rehearse_cg26.py", "scoring/score_api.py", "uv.lock"]
        },
        "model_hashes": manifest["files"],
        "health": {"http_status": health.status_code, "body": health.json()},
        "cases": results,
        "rejected_422": rejections,
        "trace_invariance": True,
        "missing_bundle": {"health": missing_health, "predict": missing_predict},
        "human_review": "pending",
        "limits": [
            "HTTPX ASGI with lifespan; no live HTTP server or streaming E2E.",
            "Two FIT examples for demonstration, not independent evaluation.",
            "Timestamp is fixture metadata, not observed machine history.",
            "No SMB, OT, Docker, Kafka, NiFi, Elasticsearch or Kibana exercised.",
            "No ETA/RUL/forecast24h, calibrated industrial risk or observed savings.",
            "No team defence, reviewer acceptance or delivery evidence established.",
        ],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--manifest", type=Path, default=Path("outputs/api/manifest.json")
    )
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError("Preserve earlier rehearsal; choose a new output file")
    result = rehearsal(args.manifest)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8") as handle:
        json.dump(result, handle, indent=2, allow_nan=False)
        handle.write("\n")
    print(
        f"CG26 isolated rehearsal PASS; evidence: {args.output}; human review pending"
    )


if __name__ == "__main__":
    main()
