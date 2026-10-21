"""Sensor subset of CG03 telemetry; envelope validation belongs to CG28."""
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

Positive = Annotated[float, Field(gt=0, allow_inf_nan=False, strict=True)]
NonNegative = Annotated[float, Field(ge=0, allow_inf_nan=False, strict=True)]


class SensorReading(BaseModel):
    """Current-state predictors only; labels and metadata are rejected."""

    model_config = ConfigDict(extra="forbid")
    machine_type: Literal["H", "M", "L"]
    air_temp_K: Positive
    process_temp_K: Positive
    rpm: NonNegative
    torque_Nm: NonNegative
    tool_wear_min: NonNegative
