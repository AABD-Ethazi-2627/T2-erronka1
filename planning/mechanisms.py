"""Explicit AI4I-generator margins, not portable industrial failure thresholds."""

from math import isfinite, pi

from planning.maintenance import instant


def ai4i_margins(row):
    required = ("air_temp_K", "process_temp_K", "rpm", "torque_Nm", "tool_wear_min")
    if any(
        k not in row
        or isinstance(row[k], bool)
        or not isinstance(row[k], (float, int))
        or not isfinite(row[k])
        for k in required
    ):
        raise ValueError("AI4I sensors with documented units required")
    if row.get("machine_type") not in ("L", "M", "H") or any(
        not isinstance(row.get(k), str) or not row[k].strip()
        for k in ("asset_id", "component_cycle", "event_time")
    ):
        raise ValueError(
            "Type, asset, lifecycle and observed time required; never inferred"
        )
    instant(row["event_time"])
    if row["rpm"] < 0 or row["torque_Nm"] < 0 or row["tool_wear_min"] < 0:
        raise ValueError("Invalid physical sensor domain")
    return {
        "asset_id": row["asset_id"],
        "component_cycle": row["component_cycle"],
        "event_time": row["event_time"],
        "power_W": row["rpm"] * row["torque_Nm"] * 2 * pi / 60,
        "thermal_margin": max(
            ((row["process_temp_K"] - row["air_temp_K"]) - 8.6) / 8.6,
            (row["rpm"] - 1380) / 1380,
        ),
        "overstrain_margin": {"L": 11000, "M": 12000, "H": 13000}[row["machine_type"]]
        - row["tool_wear_min"] * row["torque_Nm"],
    }
