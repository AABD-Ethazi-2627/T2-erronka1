from pathlib import Path

import pandas as pd

REQUIRED_COLUMNS = [
    "machine_id",
    "machine_type",
    "air_temp_K",
    "process_temp_K",
    "rpm",
    "torque_Nm",
    "tool_wear_min",
    "machine_failure",
    "failure_TWF",
    "failure_HDF",
    "failure_PWF",
    "failure_OSF",
    "failure_RNF",
]


def load_dataset(path: str | Path) -> pd.DataFrame:
    """Carga el CSV y comprueba que contiene las columnas esperadas."""
    csv_path = Path(path)
    if not csv_path.is_file():
        raise FileNotFoundError(f"No se encuentra el dataset: {csv_path}")

    data = pd.read_csv(csv_path)
    missing = sorted(set(REQUIRED_COLUMNS) - set(data.columns))
    if missing:
        raise ValueError(f"Faltan columnas obligatorias: {missing}")
    if data.empty:
        raise ValueError("El dataset está vacío")

    return data
