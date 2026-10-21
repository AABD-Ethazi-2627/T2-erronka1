"""Resumable causal sensor forecasting; fixed horizons and lab crossing scenarios."""

import json
from copy import deepcopy
from datetime import timedelta
from hashlib import sha256
from math import isfinite
from pathlib import Path

import numpy as np

from planning.adaptive import validate_manifest
from planning.maintenance import instant


def digest(value):
    return sha256(
        json.dumps(value, sort_keys=True, allow_nan=False).encode()
    ).hexdigest()


class OnlineForecaster:
    def __init__(self, manifest, *, alpha=0.25, horizon_minutes=5):
        validate_manifest(manifest)
        if (
            isinstance(alpha, bool)
            or not isinstance(alpha, (float, int))
            or not 0 < alpha <= 1
        ):
            raise ValueError("Invalid alpha")
        if (
            isinstance(horizon_minutes, bool)
            or not isinstance(horizon_minutes, (float, int))
            or not isfinite(horizon_minutes)
            or horizon_minutes <= 0
        ):
            raise ValueError("Invalid fixed horizon")
        self.manifest = deepcopy(manifest)
        self.alpha, self.horizon = alpha, horizon_minutes
        self.states, self.latest = {}, {}

    def snapshot(self):
        payload = {
            "version": 1,
            "implementation_sha256": sha256(Path(__file__).read_bytes()).hexdigest(),
            "manifest_sha256": digest(self.manifest),
            "alpha": self.alpha,
            "horizon_minutes": self.horizon,
            "states": deepcopy(self.states),
            "latest": deepcopy(self.latest),
        }
        return {**payload, "checksum": digest(payload)}

    @classmethod
    def restore(cls, snapshot, manifest):
        payload = {k: v for k, v in snapshot.items() if k != "checksum"}
        if (
            snapshot.get("version") != 1
            or digest(payload) != snapshot.get("checksum")
            or payload.get("manifest_sha256") != digest(manifest)
            or payload.get("implementation_sha256")
            != sha256(Path(__file__).read_bytes()).hexdigest()
        ):
            raise ValueError("Incompatible or corrupt state")
        engine = cls(
            manifest, alpha=payload["alpha"], horizon_minutes=payload["horizon_minutes"]
        )
        engine.states, engine.latest = (
            deepcopy(payload["states"]),
            deepcopy(payload["latest"]),
        )
        return engine

    def observe(self, row):
        columns, sensors = self.manifest["columns"], self.manifest["sensors"]
        try:
            asset, cycle = row[columns["asset"]], row[columns["lifecycle"]]
            at = instant(row[columns["timestamp"]])
            values = {name: row[spec["column"]] for name, spec in sensors.items()}
        except (KeyError, TypeError) as exc:
            raise ValueError("Missing observation fields") from exc
        if any(not isinstance(v, str) or not v.strip() for v in (asset, cycle)) or any(
            isinstance(v, bool) or not isinstance(v, (float, int)) or not isfinite(v)
            for v in values.values()
        ):
            raise ValueError("Invalid identity or sensor values")
        key = json.dumps([asset, cycle])
        if asset in self.latest:
            latest = self.latest[asset]
            if at < instant(latest["at"]):
                raise ValueError("Out-of-order observation")
            if at == instant(latest["at"]):
                if latest["cycle"] == cycle and latest["values"] == values:
                    return {
                        "duplicate": True,
                        "evaluated_forecast": None,
                        "forecast": None,
                    }
                raise ValueError("Conflicting observation")
            if latest["cycle"] != cycle and key in self.states:
                raise ValueError("Reused closed lifecycle identifier")
        old = deepcopy(self.states.get(key))
        if (
            old
            and (at - instant(old["at"])).total_seconds() / 60
            > self.manifest["max_gap_minutes"]
        ):
            old = None
        state = old or {
            "rates": {},
            "rate_errors": {name: [] for name in sensors},
            "updates": 0,
            "pending": [],
        }
        matched = next(
            (p for p in state["pending"] if instant(p["target_at"]) == at), None
        )
        # Score a stored forecast before using today's values to update any state.
        scored = None
        if matched:
            scored = {
                **deepcopy(matched),
                "observed": deepcopy(values),
                "asset": asset,
                "lifecycle": cycle,
            }
        diagnostics = {}
        if old:
            dt = (at - instant(old["at"])).total_seconds() / 60
            for name, value in values.items():
                rate = (value - old["values"][name]) / dt
                if not isfinite(rate):
                    raise ValueError("Nonfinite observation rate")
                if name in state["rates"]:
                    prior_errors = state["rate_errors"][name]
                    prior_p95 = (
                        float(np.quantile(np.abs(prior_errors), 0.95))
                        if len(prior_errors) >= 20
                        else None
                    )
                    innovation = rate - state["rates"][name]
                    diagnostics[name] = {
                        "prior_absolute_error_p95": prior_p95,
                        "innovation_rate": innovation,
                        "rate_shift_flag": prior_p95 is not None
                        and abs(innovation) > max(prior_p95, 1e-12),
                        "notice": "Diagnostic only; no calibrated drift probability",
                    }
                    state["rate_errors"][name] = (
                        state["rate_errors"][name] + [rate - state["rates"][name]]
                    )[-64:]
                    state["rates"][name] = (1 - self.alpha) * state["rates"][
                        name
                    ] + self.alpha * rate
                else:
                    state["rates"][name] = rate
            state["updates"] += 1
        forecast_values = {
            name: value + state["rates"].get(name, 0.0) * self.horizon
            for name, value in values.items()
        }
        if any(not isfinite(v) for v in forecast_values.values()):
            raise ValueError("Nonfinite forecast")
        forecast = {
            "asset": asset,
            "lifecycle": cycle,
            "issued_at": at.isoformat(),
            "target_at": (at + timedelta(minutes=self.horizon)).isoformat(),
            "horizon_minutes": self.horizon,
            "values": forecast_values,
            "persistence": deepcopy(values),
            "updates_at_issue": state["updates"],
        }
        state["pending"] = [p for p in state["pending"] if instant(p["target_at"]) > at]
        if len(state["pending"]) >= 4096:
            raise ValueError(
                "Too many pending forecasts; choose an appropriate cadence/horizon"
            )
        state["pending"].append(forecast)
        state.update(at=at.isoformat(), values=deepcopy(values))
        self.states[key] = state
        self.latest[asset] = {
            "at": at.isoformat(),
            "cycle": cycle,
            "values": deepcopy(values),
        }
        return {
            "duplicate": False,
            "evaluated_forecast": scored,
            "forecast": deepcopy(forecast),
            "diagnostics": diagnostics,
        }


def crossing_proposal(
    engine, asset, cycle, limits, *, max_minutes=60, minimum_updates=20
):
    if (
        type(minimum_updates) is not int
        or minimum_updates < 1
        or not isinstance(max_minutes, (float, int))
        or isinstance(max_minutes, bool)
        or not isfinite(max_minutes)
        or max_minutes <= 0
    ):
        raise ValueError("Invalid crossing settings")
    state = engine.states.get(json.dumps([asset, cycle]))
    if not state or engine.latest.get(asset, {}).get("cycle") != cycle:
        raise ValueError("Unknown or closed lifecycle")
    result = {
        "asset": asset,
        "lifecycle": cycle,
        "issued_at": state["at"],
        "status": "INSUFFICIENT_HISTORY",
        "crossings": {},
        "failure_eta_minutes": None,
        "operationally_validated": False,
        "forecast_horizon_minutes": engine.horizon,
        "projection_caveat": (
            "Crossings beyond the measured forecast horizon are "
            + "additional unvalidated extrapolation"
        ),
        "uncertainty_kind": "EMPIRICAL_RATE_SCENARIOS_NOT_CALIBRATED_CONFIDENCE",
        "action": "REVIEW_PROJECTED_LIMITS",
        "requires_human_review": True,
        "requires_current_data_verification": True,
        "model_review_window": None,
    }
    if not limits:
        raise ValueError("Explicit documented limits required")
    for sensor, spec in limits.items():
        if (
            sensor not in engine.manifest["sensors"]
            or spec.get("unit") != engine.manifest["sensors"][sensor]["unit"]
            or not isinstance(spec.get("source"), str)
            or not spec["source"].strip()
        ):
            raise ValueError("Limit needs matching sensor/unit and source")
        boundaries = [
            (direction, spec[direction])
            for direction in ("upper", "lower")
            if direction in spec
        ]
        if not boundaries or any(
            isinstance(v, bool) or not isinstance(v, (float, int)) or not isfinite(v)
            for _, v in boundaries
        ):
            raise ValueError("Finite upper/lower limits required")
        if "lower" in spec and "upper" in spec and spec["lower"] >= spec["upper"]:
            raise ValueError("Inverted limits")
        if state["updates"] < minimum_updates:
            continue
        rate = state["rates"].get(sensor, 0.0)
        errors = state["rate_errors"][sensor]
        spread = np.quantile(errors, [0.1, 0.9]).tolist() if errors else [0.0, 0.0]
        slopes = [rate + spread[0], rate, rate + spread[1]]

        def crossing(slope, boundaries=boundaries, sensor=sensor):
            times = []
            for direction, bound in boundaries:
                value = state["values"][sensor]
                if (direction == "upper" and value >= bound) or (
                    direction == "lower" and value <= bound
                ):
                    times.append(0.0)
                elif (direction == "upper" and slope > 0) or (
                    direction == "lower" and slope < 0
                ):
                    t = (bound - value) / slope
                    if 0 <= t <= max_minutes:
                        times.append(t)
            return min(times) if times else None

        times = [crossing(slope) for slope in slopes]
        result["crossings"][sensor] = {
            "central_minutes": times[1],
            "beyond_forecast_horizon": times[1] is not None
            and times[1] > engine.horizon,
            "scenario_minutes": times,
            "censored_scenarios": sum(t is None for t in times),
            "limit": deepcopy(spec),
            "max_projection_minutes": max_minutes,
        }
    if result["crossings"]:
        result["status"] = (
            "PROJECTED_LIMIT_CROSSING"
            if any(
                v["central_minutes"] is not None for v in result["crossings"].values()
            )
            else "NO_CROSSING_WITHIN_PROJECTION"
        )
    scenario_times = [
        t
        for value in result["crossings"].values()
        for t in value["scenario_minutes"]
        if t is not None
    ]
    if scenario_times:
        earliest = min(scenario_times)
        result["model_review_window"] = {
            "from": state["at"],
            "before": (instant(state["at"]) + timedelta(minutes=earliest)).isoformat(),
            "basis": "EARLIEST_PROJECTED_SCENARIO_CROSSING",
            "notice": (
                "Model-derived review proposal, not an optimized "
                + "maintenance time or validated failure deadline"
            ),
        }
        if earliest == 0:
            result["action"] = "REVIEW_OBSERVED_LIMIT_BREACH"
    return result
