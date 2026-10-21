"""Validate the six current-state inputs; physics stays in the active pipeline."""

import pandas as pd

from cnc_guard.schemas import SensorReading
from scoring.scope import INPUT_FEATURES

FEATURE_COLUMNS = list(INPUT_FEATURES)
TARGET_COLUMN = "machine_failure"


def prepare_inference_features(data: pd.DataFrame) -> pd.DataFrame:
    """Reject extras rather than silently accepting labels or temporal fields."""
    if data.empty:
        raise ValueError("Se requiere al menos una lectura")
    records = [
        SensorReading.model_validate(row).model_dump()
        for row in data.to_dict(orient="records")
    ]
    return pd.DataFrame(records, columns=FEATURE_COLUMNS, index=data.index)


def prepare_features(data: pd.DataFrame) -> tuple[pd.DataFrame, pd.Series]:
    missing = sorted(set(FEATURE_COLUMNS + [TARGET_COLUMN]) - set(data.columns))
    if missing:
        raise ValueError(f"Faltan columnas necesarias: {missing}")
    X = prepare_inference_features(data[FEATURE_COLUMNS])
    y = data[TARGET_COLUMN].copy()
    if y.isnull().any() or not y.isin([0, 1]).all():
        raise ValueError("El objetivo debe ser binario (0 o 1), sin ausentes")
    return X, y
