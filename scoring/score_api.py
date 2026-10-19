"""Local advisory scoring API. Never controls equipment or trains online."""

import hashlib
import json
import logging
import math
import os
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

import joblib
import pandas as pd
import sklearn
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, field_validator

from scoring.alert_policy import alert_level
from scripts.validate_contracts import validators

log = logging.getLogger(__name__)


class Source(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    kind: Literal["smb_csv", "lab_fixture", "statement_example"]
    uri: str = Field(min_length=1, max_length=1024)
    record_ref: str = Field(min_length=1, max_length=1024)
    raw_record: str | None = Field(default=None, max_length=8192)


class Telemetry(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    event_id: str = Field(pattern=r"^[0-9a-f]{64}$")
    machine_id: str = Field(pattern=r"^CNC-[0-9]{3}$")
    timestamp: str = Field(
        pattern=r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?Z$"
    )
    schema_version: Literal["0.1.0"]
    quality_flag: Literal["OK"]
    source: Source
    machine_type: Literal["H", "M", "L"]
    air_temp_K: float = Field(gt=0, allow_inf_nan=False)
    process_temp_K: float = Field(gt=0, allow_inf_nan=False)
    rpm: float = Field(ge=0, allow_inf_nan=False)
    torque_Nm: float = Field(ge=0, allow_inf_nan=False)
    tool_wear_min: float = Field(ge=0, allow_inf_nan=False)

    @field_validator("timestamp")
    @classmethod
    def real_utc_date(cls, value):
        datetime.fromisoformat(value)
        return value


def create_app(manifest_path=None):
    path = Path(
        manifest_path or os.getenv("MODEL_MANIFEST", "outputs/api/manifest.json")
    )

    @asynccontextmanager
    async def lifespan(application):
        application.state.models = None
        application.state.manifest = None
        try:
            manifest = json.loads(path.read_text())
            if manifest["versions"]["sklearn"] != sklearn.__version__:
                raise ValueError("Model/runtime sklearn mismatch")
            models = {}
            # Validate every artifact before deserializing any; directory must be trusted.
            for filename in ["rf.pkl", "if.pkl"]:
                artifact = path.parent / filename
                if (
                    hashlib.sha256(artifact.read_bytes()).hexdigest()
                    != manifest["files"][filename]
                ):
                    raise ValueError("Artifact hash mismatch")
            for key in ["risk_threshold", "anomaly_threshold"]:
                if not math.isfinite(manifest[key]):
                    raise ValueError("Invalid threshold")
            if not 0 <= manifest["risk_threshold"] <= 1:
                raise ValueError("Invalid risk threshold")
            for filename in ["rf.pkl", "if.pkl"]:
                models[filename] = joblib.load(path.parent / filename)
            probe = pd.DataFrame(
                [
                    {
                        "machine_type": "M",
                        "air_temp_K": 300.0,
                        "process_temp_K": 310.0,
                        "rpm": 1500.0,
                        "torque_Nm": 40.0,
                        "tool_wear_min": 100.0,
                    }
                ]
            )
            risk = float(models["rf.pkl"].predict_proba(probe)[0, 1])
            anomaly = float(models["if.pkl"].score_samples(probe)[0])
            alert_level(risk)
            if not math.isfinite(anomaly):
                raise ValueError("Invalid model probe")
            application.state.models = models
            application.state.manifest = manifest
        except Exception:  # noqa: BLE001 -- fail closed for any model loading/probe error
            log.error("Model bundle unavailable or invalid; scoring remains unready")
        yield
        application.state.models = None

    app = FastAPI(
        title="CNC Guard advisory scoring", version="0.1.0", lifespan=lifespan
    )
    app.state.models = None
    schemas = validators(Path(__file__).resolve().parents[1] / "contracts")

    @app.middleware("http")
    async def bounded_body(request: Request, call_next):
        total = 0
        chunks = []
        async for chunk in request.stream():
            total += len(chunk)
            if total > 32768:
                return JSONResponse(
                    status_code=413, content={"detail": "Request too large"}
                )
            chunks.append(chunk)
        request._body = b"".join(chunks)
        return await call_next(request)

    @app.get("/health")
    def health():
        if app.state.models is None:
            raise HTTPException(503, "Model not ready")
        return {"status": "ready", "model_version": app.state.manifest["model_version"]}

    @app.post("/predict")
    def predict(payload: Telemetry):
        if app.state.models is None:
            raise HTTPException(503, "Model not ready")
        event = payload.model_dump(exclude_none=True)
        try:
            schemas["telemetry"].validate(event)
            frame = pd.DataFrame([event])
            risk = float(app.state.models["rf.pkl"].predict_proba(frame)[0, 1])
            anomaly = float(-app.state.models["if.pkl"].score_samples(frame)[0])
            if not math.isfinite(anomaly):
                raise ValueError("Invalid anomaly output")
            manifest = app.state.manifest
            result = {
                **event,
                "failure_score": risk,
                "risk_alert": risk >= manifest["risk_threshold"],
                "alert_level": alert_level(risk),
                "anomaly_score": anomaly,
                "anomaly_alert": anomaly >= manifest["anomaly_threshold"],
                "policy": manifest["policy"],
                "model_version": manifest["model_version"],
                "scored_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
                "model_artifact_sha256": manifest["files"]["rf.pkl"],
                "risk_threshold": manifest["risk_threshold"],
                "anomaly_threshold": manifest["anomaly_threshold"],
            }
            schemas["prediction"].validate(result)
            return result
        except Exception:
            log.exception("Scoring failed; no fallback probability emitted")
            raise HTTPException(500, "Scoring failed") from None

    return app


app = create_app()
