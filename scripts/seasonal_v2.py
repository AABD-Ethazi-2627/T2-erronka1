"""Invented northern seasonal scenario. Never relabels or appends to AI4I."""

import numpy as np
import pandas as pd

from scoring.preparation import SENSORS

SCENARIO = {
    "version": "synthetic_seasonal_v2",
    "meaning": "Invented northern indoor scenario, not measured industrial dynamics",
    "annual_amplitude_K": 6.0,
    "annual_peak_day": 205,
    "diurnal_amplitude_K": 1.2,
    "weather_ar": 0.96,
    "weather_noise_K": 0.25,
    "baseline_fault_hazard_per_hour": 0.00015,
    "wear_hazard_coefficient": 0.003,
    "heat_hazard_coefficient": 0.0015,
    "cold_start_hazard_coefficient": 0.001,
    "planned_tool_replacement_minutes_range": [240, 320],
    "horizon_hours": 24,
}


def future_labels(onsets, horizon=24):
    onsets = np.asarray(onsets)
    result = np.full(len(onsets), np.nan)
    if len(onsets) > horizon:
        prefix = np.r_[0, np.cumsum(onsets)]
        i = np.arange(len(onsets) - horizon)
        result[i] = (prefix[i + horizon + 1] - prefix[i + 1]) > 0
    return result


def predictor_columns(temporal=True, calendar=True):
    columns = SENSORS + ["temp_diff", "power_W"]
    if temporal:
        columns += [
            "torque_mean_24h",
            "air_mean_24h",
            "temp_diff_mean_24h",
            "wear_mean_24h",
            "torque_mean_168h",
        ]
    if temporal and calendar:
        columns += [
            "year_sin",
            "year_cos",
            "hour_sin",
            "hour_cos",
            "weekday_sin",
            "weekday_cos",
        ]
    return columns


def generate(
    start="2022-01-01",
    days=730,
    machines=8,
    seed=42,
    air_base=300.0,
    torque_base=40.0,
    stress=False,
):
    if days < 1 or machines < 1:
        raise ValueError("Positive duration and machine count required")
    times = pd.date_range(start, periods=days * 24, freq="h", tz="UTC")
    annual = np.cos(
        2 * np.pi * (times.dayofyear.to_numpy() - SCENARIO["annual_peak_day"]) / 365.25
    )
    daily = np.sin(2 * np.pi * (times.hour.to_numpy() - 8) / 24)
    seasons = np.array(
        [
            "winter",
            "winter",
            "spring",
            "spring",
            "spring",
            "summer",
            "summer",
            "summer",
            "autumn",
            "autumn",
            "autumn",
            "winter",
        ]
    )
    parts = []
    for machine in range(machines):
        rng = np.random.default_rng(np.random.SeedSequence([seed, machine]))
        n = len(times)
        weather = np.empty(n)
        innovations = rng.normal(0, SCENARIO["weather_noise_K"], n)
        weather[0] = innovations[0]
        for i in range(1, n):
            weather[i] = SCENARIO["weather_ar"] * weather[i - 1] + innovations[i]
        air = (
            air_base
            + SCENARIO["annual_amplitude_K"] * annual
            + SCENARIO["diurnal_amplitude_K"] * daily
            + weather
            + rng.normal(0, 0.8)
            + (3.0 if stress else 0.0)
        )
        # Invented work schedule and correlated load; not linked to operator identity.
        weekday = times.dayofweek.to_numpy()
        hour = times.hour.to_numpy()
        planned = np.where((weekday < 5) & (hour >= 6) & (hour < 22), 1.1, 0.78)
        load = np.clip(planned + 0.08 * daily + rng.normal(0, 0.08, n), 0.5, 1.4)
        torque_noise = rng.normal(0, 0.7, n)
        rpm_noise = rng.normal(0, 25, n)
        thermal_noise = rng.normal(0, 0.15, n)
        rolls = rng.random(n)
        wear = rng.uniform(0, 180)
        damage = 0.0
        replacement = rng.uniform(*SCENARIO["planned_tool_replacement_minutes_range"])
        sensitivity = rng.uniform(0.8, 1.2)
        rows = np.empty((n, 7))
        for i in range(n):
            if wear >= replacement:
                wear = 0.0
                damage *= 0.25
                replacement = rng.uniform(
                    *SCENARIO["planned_tool_replacement_minutes_range"]
                )
            torque = max(1.0, torque_base * load[i] + 0.018 * wear + torque_noise[i])
            rpm = max(400.0, 1500 / load[i] + rpm_noise[i])
            gap = (
                10.5
                - 0.12 * (air[i] - air_base)
                - 1.2 * (load[i] - 1)
                - 0.8 * damage
                + thermal_noise[i]
                - (1.5 if stress else 0.0)
            )
            process = air[i] + max(3.0, gap)
            hot = max(0.0, air[i] - 303.0) / 4.0
            cold_start = max(0.0, 296.0 - air[i]) / 4.0 * float(6 <= hour[i] <= 8)
            hazard = (
                SCENARIO["baseline_fault_hazard_per_hour"]
                + SCENARIO["wear_hazard_coefficient"] * max(0.0, wear - 150.0) / 100.0
                + SCENARIO["heat_hazard_coefficient"] * hot * max(0.1, 11.0 - gap)
                + SCENARIO["cold_start_hazard_coefficient"] * cold_start
                + 0.0008 * damage
            ) * sensitivity
            fault = int(rolls[i] < min(0.03, hazard))
            rows[i] = [process, rpm, torque, wear, fault, damage, gap]
            wear += 2.5 * load[i]
            damage = 0.99 * damage + 0.004 * max(0.0, load[i] - 0.8) + 0.0008 * hot
            if fault:
                wear = 0.0
                damage *= (
                    0.1  # hypothetical immediate repair, not an observed intervention
                )
                replacement = rng.uniform(
                    *SCENARIO["planned_tool_replacement_minutes_range"]
                )
        frame = pd.DataFrame(
            rows,
            columns=[
                "process_temp_K",
                "rpm",
                "torque_Nm",
                "tool_wear_min",
                "simulated_fault_onset",
                "latent_damage",
                "temp_diff",
            ],
        )
        frame["air_temp_K"] = air
        frame["timestamp"] = times
        frame["machine_id"] = f"SIM-{seed}-{machine:03}"
        frame["power_W"] = frame.rpm * frame.torque_Nm * (2 * np.pi / 60)
        for source, target, window in [
            ("torque_Nm", "torque_mean_24h", 24),
            ("air_temp_K", "air_mean_24h", 24),
            ("temp_diff", "temp_diff_mean_24h", 24),
            ("tool_wear_min", "wear_mean_24h", 24),
            ("torque_Nm", "torque_mean_168h", 168),
        ]:
            frame[target] = frame[source].shift(1).rolling(window, min_periods=1).mean()
        phase = 2 * np.pi * (times.dayofyear.to_numpy() - 1) / 365.25
        for name, angle in [
            ("year", phase),
            ("hour", 2 * np.pi * hour / 24),
            ("weekday", 2 * np.pi * weekday / 7),
        ]:
            frame[name + "_sin"], frame[name + "_cos"] = np.sin(angle), np.cos(angle)
        frame["failure_next_24h"] = future_labels(
            frame.simulated_fault_onset.to_numpy()
        )
        frame["season"] = seasons[times.month.to_numpy() - 1]
        frame["source_kind"] = SCENARIO["version"]
        frame["seed"] = seed
        parts.append(frame)
    return pd.concat(parts, ignore_index=True)
