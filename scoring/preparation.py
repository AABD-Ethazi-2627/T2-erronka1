"""Shared offline sensor features, preserving the original inspected test split."""

import numpy as np
from sklearn.model_selection import train_test_split

SENSORS = ["air_temp_K", "process_temp_K", "rpm", "torque_Nm", "tool_wear_min"]
DERIVED = ["temp_diff", "power_W", "wear_torque"]
SEED = 42


def features(frame):
    result = frame[SENSORS + ["machine_type"]].copy()
    result["temp_diff"] = result.process_temp_K - result.air_temp_K
    result["power_W"] = result.rpm * result.torque_Nm * (2 * np.pi / 60)
    result["wear_torque"] = result.tool_wear_min * result.torque_Nm
    return result


def split_development(frame):
    if frame.machine_failure.isna().any() or set(frame.machine_failure.unique()) != {
        0,
        1,
    }:
        raise ValueError("Target must contain both binary classes")
    if not np.isfinite(frame[SENSORS].to_numpy(dtype=float)).all():
        raise ValueError("Sensors must be finite")
    train, remaining = train_test_split(
        frame, test_size=0.3, random_state=SEED, stratify=frame.machine_failure
    )
    validation, excluded = train_test_split(
        remaining, test_size=0.5, random_state=SEED, stratify=remaining.machine_failure
    )
    # Exact old membership: never reshuffle a previously inspected test into training.
    return train, validation, excluded
