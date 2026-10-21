import pandas as pd

from cnc_guard.data import load_dataset
from cnc_guard.schemas import SensorReading

FEATURE_COLUMNS = [
    "machine_type",
    "air_temp_K",
    "process_temp_K",
    "rpm",
    "torque_Nm",
    "tool_wear_min",
]

TARGET_COLUMN = "machine_failure"


def prepare_features(
    data: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.Series]:
    """Separa las variables predictoras del objetivo de fallo."""
    required = FEATURE_COLUMNS + [TARGET_COLUMN]
    missing = sorted(set(required) - set(data.columns))
    if missing:
        raise ValueError(f"Faltan columnas necesarias: {missing}")

    X = prepare_inference_features(data[FEATURE_COLUMNS])
    y = data[TARGET_COLUMN].copy()
    if y.isnull().any() or not y.isin([0, 1]).all():
        raise ValueError("El objetivo debe ser binario (0 o 1), sin ausentes")

    return X, y


def load_training_data(path: str) -> tuple[pd.DataFrame, pd.Series]:
    """Carga el dataset y devuelve las variables preparadas."""
    return prepare_features(load_dataset(path))


def prepare_inference_features(data: pd.DataFrame) -> pd.DataFrame:
    """Validate sensor-only rows; Pydantic ValidationError is a ValueError.

    Training explicitly selects predictors first. Inference rejects any extra
    fields, including targets, raw records, identities and temporal fields.
    """
    if data.empty:
        raise ValueError("Se requiere al menos una lectura")
    records = [SensorReading.model_validate(row).model_dump()
               for row in data.to_dict(orient="records")]
    return pd.DataFrame(records, columns=FEATURE_COLUMNS, index=data.index)
