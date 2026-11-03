"""UI read contracts; deliberately outside the worker schema fingerprint."""
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field


class ReadScope(BaseModel):
    model_config = ConfigDict(frozen=True, extra='forbid')
    source_uri: str = Field(min_length=1)
    model_artifact_sha256: str = Field(pattern=r'^[0-9a-f]{64}$')
    policy: str = Field(min_length=1)


class Machine(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False)
    id: str = Field(pattern=r'^CNC-[0-9]{3}$')
    zenbakia: str
    tenperatura: float | None
    giro_tenperatura: float | None
    rpm: float | None
    torque: float | None
    higadura: float | None
    egoera: Literal['Normala', 'Berrikusteko', 'Akatsa']
    event_id: str = Field(pattern=r'^[0-9a-f]{64}$')
    timestamp: str
    scored_at: str
    model_version: str
    model_artifact_sha256: str
    policy: str
    quality_flag: str
    source: dict
    prediction_scope: Literal['AI4I_CURRENT_STATE_ONLY']
    score_semantics: Literal['uncalibrated_current_state_score']
    temporal_prediction_enabled: Literal[False]
    failure_score: float = Field(ge=0, le=1)
    risk_alert: bool
    alert_level: Literal['OK', 'AVISO', 'CRITICA']


class History(BaseModel):
    datuak: dict[str, list]
    metadata: dict
    next_cursor: str | None = None


class Periods(BaseModel):
    astea: History
    hilabetea: History
    sei_hilabete: History


class KPIs(BaseModel):
    guztira: int
    operatiboak: int
    akatsak: int
    motak: dict[str, int]
    tenperatura: float | None
    gertakariak: int
    osasuna: None = None
    metadata: dict


class Evaluation(BaseModel):
    available: bool
    reason: str | None = None
    scope: Literal['offline_model_evaluation'] = 'offline_model_evaluation'
    model_version: str | None = None
    model_artifact_sha256: str | None = None
    partition: str | None = None
    threshold: float | None = Field(default=None, ge=0, le=1, allow_inf_nan=False)
    labels: list[int] | None = None
    confusion_matrix: list[list[int]] | None = None
    denominators: dict | None = None
    metrics: dict[str, float | None] | None = None
    provenance: dict | None = None
