"""Causal next-observation forecasting sandbox; never promotes a runtime model."""

import json
from collections import defaultdict
from hashlib import sha256
from math import isfinite

from planning.maintenance import instant


def validate_manifest(manifest):
    if (
        not isinstance(manifest.get("dataset_id"), str)
        or not manifest["dataset_id"].strip()
    ):
        raise ValueError("dataset_id required")
    if manifest.get("provenance") not in ("physical", "synthetic", "replay", "unknown"):
        raise ValueError("Explicit provenance required")
    if type(manifest.get("physical_identity_verified")) is not bool:
        raise ValueError("Explicit identity verification declaration required")
    if manifest.get("timestamp_role") != "observation":
        raise ValueError(
            "Observation timestamp required; ingestion time is insufficient"
        )
    columns = manifest.get("columns", {})
    if any(
        not isinstance(columns.get(k), str) or not columns[k].strip()
        for k in ("asset", "timestamp", "lifecycle")
    ):
        raise ValueError("Asset, observation timestamp and lifecycle mappings required")
    sensors = manifest.get("sensors", {})
    if not sensors or not isinstance(sensors, dict):
        raise ValueError("Sensor mapping required")
    mapped = list(columns.values())
    for name, spec in sensors.items():
        if not isinstance(name, str) or not isinstance(spec, dict):
            raise TypeError("Invalid sensor mapping")
        if any(
            not isinstance(spec.get(k), str) or not spec[k].strip()
            for k in ("column", "unit")
        ):
            raise ValueError(
                "Explicit sensor columns and units required; no implicit conversions"
            )
        mapped.append(spec["column"])
    if len(set(mapped)) != len(mapped):
        raise ValueError("Mapped columns must be distinct")
    gap = manifest.get("max_gap_minutes")
    if (
        isinstance(gap, bool)
        or not isinstance(gap, (int, float))
        or not isfinite(gap)
        or gap <= 0
    ):
        raise ValueError("Positive finite max_gap_minutes required")


def evaluate_stream(rows, manifest, *, alpha=0.25, warmup=2):
    """Forecast the next observed value with its elapsed-time horizon.

    The target's timestamp is used as an explicit requested forecast horizon, not
    its values. At runtime the caller must request that horizon before observing
    the value. This is not a fixed-horizon industrial acceptance evaluation.
    """
    validate_manifest(manifest)
    if (
        isinstance(alpha, bool)
        or not isinstance(alpha, (int, float))
        or not 0 < alpha <= 1
    ):
        raise ValueError("alpha must be in (0,1]")
    if type(warmup) is not int or warmup < 0:
        raise ValueError("warmup must be a nonnegative integer")
    columns, sensors = manifest["columns"], manifest["sensors"]
    groups, unique, signatures = defaultdict(list), {}, set()
    duplicate_rows = repeated_states = 0
    for row in rows:
        try:
            asset, lifecycle = row[columns["asset"]], row[columns["lifecycle"]]
            at = instant(row[columns["timestamp"]])
            values = {name: row[spec["column"]] for name, spec in sensors.items()}
        except (KeyError, TypeError) as exc:
            raise ValueError("Missing or invalid canonical observation fields") from exc
        if any(not isinstance(v, str) or not v.strip() for v in (asset, lifecycle)):
            raise ValueError("Nonempty asset and lifecycle IDs required")
        if any(
            isinstance(v, bool) or not isinstance(v, (int, float)) or not isfinite(v)
            for v in values.values()
        ):
            raise ValueError("Sensors must be finite numbers")
        key = (asset, lifecycle, at)
        if key in unique:
            if values != unique[key]:
                raise ValueError(
                    "Conflicting observations at same asset/lifecycle/time"
                )
            duplicate_rows += 1
            continue
        unique[key] = values
        signature = (asset, lifecycle, tuple(sorted(values.items())))
        repeated_states += signature in signatures
        signatures.add(signature)
        groups[(asset, lifecycle)].append((at, values))
    predictions, diagnostics = [], []
    totals = {
        name: {
            "count": 0,
            "persistence_absolute_error": 0.0,
            "online_drift_absolute_error": 0.0,
        }
        for name in sensors
    }
    for (asset, lifecycle), observations in sorted(groups.items()):
        observations.sort(key=lambda x: x[0])
        previous, rates, updates, gaps = None, {}, 0, 0
        for at, values in observations:
            if previous is None:
                previous = (at, values)
                continue
            previous_at, previous_values = previous
            dt = (at - previous_at).total_seconds() / 60
            if dt > manifest["max_gap_minutes"]:
                rates, updates = {}, 0
                gaps += 1
                previous = (at, values)
                continue
            for name, value in values.items():
                persistence = previous_values[name]
                forecast = persistence + rates.get(name, 0.0) * dt
                if not isfinite(forecast):
                    raise ValueError("Nonfinite forecast; check units/scales")
                evaluated = updates >= warmup
                predictions.append(
                    {
                        "asset": asset,
                        "lifecycle": lifecycle,
                        "sensor": name,
                        "issued_at": previous_at.isoformat(),
                        "target_at": at.isoformat(),
                        "horizon_minutes": dt,
                        "persistence": persistence,
                        "online_drift": forecast,
                        "observed": value,
                        "evaluated": evaluated,
                    }
                )
                if evaluated:
                    totals[name]["count"] += 1
                    totals[name]["persistence_absolute_error"] += abs(
                        value - persistence
                    )
                    totals[name]["online_drift_absolute_error"] += abs(value - forecast)
                # Only AFTER predicting and scoring may the new observation update state.
                observed_rate = (value - persistence) / dt
                if not isfinite(observed_rate):
                    raise ValueError("Nonfinite observed rate")
                rates[name] = (
                    (1 - alpha) * rates[name] + alpha * observed_rate
                    if name in rates
                    else observed_rate
                )
            updates += 1
            previous = (at, values)
        diagnostics.append(
            {
                "asset": asset,
                "lifecycle": lifecycle,
                "observations": len(observations),
                "gap_resets": gaps,
            }
        )
    metrics = {}
    for name, total in totals.items():
        count = total["count"]
        metrics[name] = {
            "count": count,
            "unit": sensors[name]["unit"],
            "persistence_mae": total["persistence_absolute_error"] / count
            if count
            else None,
            "online_drift_mae": total["online_drift_absolute_error"] / count
            if count
            else None,
        }
    canonical = json.dumps(manifest, sort_keys=True, allow_nan=False).encode()
    return {
        "schema_version": 1,
        "dataset_id": manifest["dataset_id"],
        "manifest_sha256": sha256(canonical).hexdigest(),
        "settings": {"alpha": alpha, "warmup_pairs_per_segment": warmup},
        "metrics": metrics,
        "predictions": predictions,
        "segments": diagnostics,
        "duplicate_rows_removed": duplicate_rows,
        "repeated_sensor_states": repeated_states,
        "provenance": manifest["provenance"],
        "promotion_allowed": False,
        "promotion_blockers": [
            "EXPLORATORY_NEXT_OBSERVATION_EVALUATION",
            "NO_UNTOUCHED_TEMPORAL_ACCEPTANCE",
            "NO_VERIFIED_MAINTENANCE_OUTCOMES",
        ],
        "failure_eta_minutes": None,
        "notice": "Online sensor drift experiment. No maintenance timing model or runtime promotion.",
    }
