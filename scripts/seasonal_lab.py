"""Explicitly invented seasonal laboratory, separate from AI4I and real evidence.
No model is trained here; future labels characterize only these simulator rules.
"""

import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd


def simulate(days=365, machines=4, seed=42):
    rng = np.random.default_rng(seed)
    times = pd.date_range("2025-01-01", periods=days * 24, freq="h", tz="UTC")
    parts = []
    for machine in range(machines):
        wear = 0.0
        rows = []
        for timestamp in times:
            seasonal = 8 * np.sin(2 * np.pi * (timestamp.dayofyear - 80) / 365.25)
            air = 298 + seasonal + rng.normal(0, 0.5)
            load = rng.uniform(0.7, 1.3)
            torque = 40 * load + wear * 0.03 + rng.normal(0, 1)
            wear += load
            # Invented fault hazard: degradation and heat, not fitted industrial physics.
            fault = int(
                rng.random()
                < (0.0005 + max(0, wear - 160) * 0.00005 + max(0, air - 303) * 0.0002)
            )
            rows.append(
                (
                    timestamp,
                    f"SIM-{machine:03}",
                    air,
                    air + 10 + load,
                    1500 / load,
                    torque,
                    wear,
                    fault,
                )
            )
            if fault:
                wear = 0.0  # hypothetical immediate repair, not a recorded maintenance event
        frame = pd.DataFrame(
            rows,
            columns=[
                "timestamp",
                "machine_id",
                "air_temp_K",
                "process_temp_K",
                "rpm",
                "torque_Nm",
                "tool_wear_min",
                "simulated_fault_onset",
            ],
        )
        frame["past_torque_mean"] = (
            frame.torque_Nm.shift(1).rolling(24, min_periods=1).mean()
        )
        onsets = frame.simulated_fault_onset.to_numpy()
        labels = np.full(len(frame), np.nan)
        for i in range(max(0, len(frame) - 24)):
            labels[i] = int(onsets[i + 1 : i + 25].any())
        frame["failure_next_24h"] = labels
        frame["source_kind"] = "synthetic_seasonal_rules_v1"
        parts.append(frame)
    return pd.concat(parts, ignore_index=True)


def temporal_split(frame):
    times = sorted(frame.timestamp.unique())
    cut1 = times[int(len(times) * 0.6)]
    cut2 = times[int(len(times) * 0.8)]
    horizon = pd.Timedelta(hours=24)
    observed = frame.failure_next_24h.notna()
    train = frame[observed & (frame.timestamp + horizon < cut1)]
    validation = frame[
        observed & (frame.timestamp >= cut1) & (frame.timestamp + horizon < cut2)
    ]
    test = frame[observed & (frame.timestamp >= cut2)]
    return train, validation, test


if __name__ == "__main__":
    output = Path("outputs/seasonal-lab")
    if output.exists():
        raise FileExistsError(
            "Use preserved output or a new version; no silent overwrite"
        )
    frame = simulate()
    output.mkdir(parents=True)
    frame.to_parquet(output / "observations.parquet", index=False)
    splits = temporal_split(frame)
    report = {
        "seed": 42,
        "rows": len(frame),
        "machines": 4,
        "days": 365,
        "censored_last_24h_rows": int(frame.failure_next_24h.isna().sum()),
        "sha256": hashlib.sha256(
            (output / "observations.parquet").read_bytes()
        ).hexdigest(),
        "splits": {
            name: {
                "rows": len(part),
                "start": str(part.timestamp.min()),
                "end": str(part.timestamp.max()),
                "positives": int(part.failure_next_24h.sum()),
            }
            for name, part in zip(["train", "validation", "test"], splits)
        },
        "limitations": [
            "Invented independent simulation, not AI4I timestamps or new industrial truth.",
            "Annual cycle occurs once; held-out calendar periods do not establish generalization across years.",
            "Rolling mean excludes current/future readings; future onset used only as label.",
            "24h purge and end censoring prevent horizon overlap between partitions.",
            "No forecasting model trained or predictive accuracy claimed. AI4I remains exclusive classification training source.",
        ],
    }
    (output / "report.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))
