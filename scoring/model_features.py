"""Sensor-only feature engineering shared by training and inference."""

import numpy as np

SENSORS = ["air_temp_K", "process_temp_K", "rpm", "torque_Nm", "tool_wear_min"]
DERIVED = ["temp_diff", "power_W", "wear_torque"]


def engineer_features(frame):
    """No labels, IDs or failure subtypes enter this transformation."""
    result = frame[SENSORS + ["machine_type"]].copy()
    result["temp_diff"] = result.process_temp_K - result.air_temp_K
    result["power_W"] = result.rpm * result.torque_Nm * (2 * np.pi / 60)
    result["wear_torque"] = result.tool_wear_min * result.torque_Nm
    return result
