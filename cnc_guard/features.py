import pandas as pd

from cnc_guard.data import load_dataset

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

    X = data[FEATURE_COLUMNS].copy()
    y = data[TARGET_COLUMN].copy()

    if X.isnull().any().any() or y.isnull().any():
        raise ValueError("Hay valores ausentes en las variables o el objetivo")

    return X, y


def load_training_data(path: str) -> tuple[pd.DataFrame, pd.Series]:
    """Carga el dataset y devuelve las variables preparadas."""
    return prepare_features(load_dataset(path))
