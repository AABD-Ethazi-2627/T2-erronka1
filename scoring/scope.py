"""Binding scope for the corrected classroom task. No dates/RUL training."""

from hashlib import sha256
from io import BytesIO
from pathlib import Path

import pandas as pd

APPROVED_SOURCE_SHA256 = (
    "1cce2859f4833b63dbf0992868884e5deac6f79e4d74a245abbc484d34e396ce"
)
INPUT_FEATURES = [
    "air_temp_K",
    "process_temp_K",
    "rpm",
    "torque_Nm",
    "tool_wear_min",
    "machine_type",
]
SCOPE = {
    "prediction_scope": "AI4I_CURRENT_STATE_ONLY",
    "temporal_prediction_enabled": False,
    "training_source_sha256": APPROVED_SOURCE_SHA256,
    "input_features": INPUT_FEATURES,
    "score_semantics": "uncalibrated_current_state_score",
}


def load_training_source(path=Path("data/ai4i2020_train.csv")):
    path = Path(path)
    raw = path.read_bytes()
    if sha256(raw).hexdigest() != APPROVED_SOURCE_SHA256:
        raise ValueError("Only the approved reduced AI4I training file is authorized")
    frame = pd.read_csv(BytesIO(raw))
    if len(frame) != 8000 or not set(INPUT_FEATURES + ["machine_failure"]).issubset(
        frame.columns
    ):
        raise ValueError("Unexpected approved training schema")
    return frame


def validate_bundle_scope(manifest):
    if not isinstance(manifest, dict):
        raise TypeError("Model manifest must be an object")
    for key, expected in SCOPE.items():
        if manifest.get(key) != expected or (
            key == "temporal_prediction_enabled" and manifest[key] is not False
        ):
            raise ValueError(f"Model bundle scope mismatch: {key}")
