"""Sensor subset of CG03; the API still validates the complete telemetry envelope.

Adapted from PR43 a0c33600b99c9af9decb90d8129306244d59b35d.
"""

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

Positive = Annotated[float, Field(gt=0, allow_inf_nan=False, strict=True)]
NonNegative = Annotated[float, Field(ge=0, allow_inf_nan=False, strict=True)]


class SensorReading(BaseModel):
    model_config = ConfigDict(extra="forbid")
    machine_type: Literal["H", "M", "L"]
    air_temp_K: Positive
    process_temp_K: Positive
    rpm: NonNegative
    torque_Nm: NonNegative
    tool_wear_min: NonNegative
