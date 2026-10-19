"""Select settings on earlier validation; evaluate one choice on later observations."""

from copy import deepcopy
from hashlib import sha256
from pathlib import Path

import numpy as np

from planning.maintenance import instant
from planning.online import OnlineForecaster, digest


def errors(records, sensors, minimum_updates, reference_records=None):
    values = {name: [] for name in sensors}
    for index, record in enumerate(records):
        reference = (
            reference_records[index]["evaluated_forecast"]
            if reference_records is not None
            else None
        )
        forecast = record["evaluated_forecast"]
        if forecast and forecast["updates_at_issue"] >= minimum_updates:
            if reference_records is not None and (
                not reference
                or reference["target_at"] != forecast["target_at"]
                or reference["updates_at_issue"] < minimum_updates
            ):
                continue
            for sensor in sensors:
                actual = forecast["observed"][sensor]
                values[sensor].append(
                    {
                        "at": forecast["target_at"],
                        "candidate": abs(actual - forecast["values"][sensor]),
                        "baseline": abs(
                            actual
                            - (
                                reference["values"][sensor]
                                if reference
                                else forecast["persistence"][sensor]
                            )
                        ),
                        "asset": record.get("asset"),
                    }
                )
    return values


def summarize(values):
    result = {}
    for sensor, items in values.items():
        result[sensor] = {
            "count": len(items),
            "candidate_mae": float(np.mean([p["candidate"] for p in items]))
            if items
            else None,
            "baseline_mae": float(np.mean([p["baseline"] for p in items]))
            if items
            else None,
        }
    return result


def compare_candidates(
    rows,
    manifest,
    *,
    alphas=(0.1, 0.25, 0.5),
    horizon_minutes=1,
    minimum_pairs=20,
    minimum_updates=2,
    blocks=4,
    champion_alpha=None,
    champion_snapshot=None,
):
    if (
        type(minimum_pairs) is not int
        or minimum_pairs < 1
        or type(minimum_updates) is not int
        or minimum_updates < 0
        or type(blocks) is not int
        or blocks < 2
    ):
        raise ValueError("Invalid acceptance settings")
    if not alphas or len(set(alphas)) != len(alphas):
        raise ValueError("Distinct candidate alphas required")
    champion = None
    if champion_snapshot is not None:
        champion = OnlineForecaster.restore(champion_snapshot, manifest)
        if champion.horizon != horizon_minutes or (
            champion_alpha is not None and champion.alpha != champion_alpha
        ):
            raise ValueError("Champion configuration mismatch")
        champion_alpha = champion.alpha
    if champion is None and champion_alpha is not None:
        champion = OnlineForecaster(
            manifest, alpha=champion_alpha, horizon_minutes=horizon_minutes
        )
    timestamp = manifest["columns"]["timestamp"]
    source = sorted(
        deepcopy(rows),
        key=lambda r: (
            instant(r[timestamp]),
            r[manifest["columns"]["asset"]],
            r[manifest["columns"]["lifecycle"]],
        ),
    )
    times = sorted({instant(r[timestamp]) for r in source})
    if len(times) < 10:
        raise ValueError("Insufficient distinct observation timestamps")
    val_start, acceptance_start = (
        times[int(len(times) * 0.6)],
        times[int(len(times) * 0.8)],
    )
    history = [r for r in source if instant(r[timestamp]) < val_start]
    validation = [
        r for r in source if val_start <= instant(r[timestamp]) < acceptance_start
    ]
    acceptance = [r for r in source if instant(r[timestamp]) >= acceptance_start]
    candidates = []
    for alpha in alphas:
        model = OnlineForecaster(manifest, alpha=alpha, horizon_minutes=horizon_minutes)
        for row in history:
            model.observe(row)
        records = [model.observe(row) for row in validation]
        per_sensor = summarize(errors(records, manifest["sensors"], minimum_updates))
        if any(m["count"] < minimum_pairs for m in per_sensor.values()):
            score = float("inf")
        else:
            score = float(
                np.mean(
                    [
                        m["candidate_mae"] / max(m["baseline_mae"], 1e-12)
                        for m in per_sensor.values()
                    ]
                )
            )
        candidates.append((score, alpha, model, per_sensor))
    score, alpha, chosen, _validation_metrics = min(
        candidates, key=lambda c: (c[0], c[1])
    )
    if champion:
        for row in history + validation:
            champion.observe(row)
    # No unselected challenger sees the acceptance segment. Settings are now frozen;
    # measured observations may still update the selected online model causally.
    before = chosen.snapshot()
    records = [chosen.observe(row) for row in acceptance]
    for record, row in zip(records, acceptance, strict=True):
        record["asset"] = row[manifest["columns"]["asset"]]
    reference_records = (
        [champion.observe(row) for row in acceptance] if champion else None
    )
    paired = errors(records, manifest["sensors"], minimum_updates, reference_records)
    metrics = summarize(paired)
    reasons = []
    if not np.isfinite(score):
        reasons.append("INSUFFICIENT_VALIDATION_PAIRS")
    block_advantages, block_intervals = {}, {}
    for sensor, items in paired.items():
        if len(items) < max(minimum_pairs, blocks):
            reasons.append(f"INSUFFICIENT_ACCEPTANCE_PAIRS:{sensor}")
            block_advantages[sensor] = []
            continue
        target_times = sorted({p["at"] for p in items})
        if len(target_times) < blocks:
            reasons.append(f"INSUFFICIENT_DISTINCT_TIMES:{sensor}")
            block_advantages[sensor] = []
            continue
        grouped_times = np.array_split(np.arange(len(target_times)), blocks)
        means = []
        for indices in grouped_times:
            selected_times = {target_times[int(i)] for i in indices}
            means.append(
                float(
                    np.mean(
                        [
                            p["baseline"] - p["candidate"]
                            for p in items
                            if p["at"] in selected_times
                        ]
                    )
                )
            )
        block_advantages[sensor] = means
        rng = np.random.default_rng(42)
        sampled = rng.choice(means, size=(2000, len(means)), replace=True).mean(axis=1)
        block_intervals[sensor] = np.quantile(sampled, [0.025, 0.975]).tolist()
        for asset in sorted({r[manifest["columns"]["asset"]] for r in acceptance}):
            subset = [p for p in items if p["asset"] == asset]
            if len(subset) < minimum_pairs:
                reasons.append(f"INSUFFICIENT_ASSET_PAIRS:{sensor}:{asset}")
            elif np.mean([p["baseline"] - p["candidate"] for p in subset]) < 0:
                reasons.append(f"ASSET_REGRESSION:{sensor}:{asset}")
        if min(means) <= 0:
            reasons.append(f"NOT_BETTER_IN_EVERY_TEMPORAL_BLOCK:{sensor}")
    return {
        "schema_version": 1,
        "implementation_sha256": digest(
            {
                name: sha256(Path(__file__).with_name(name).read_bytes()).hexdigest()
                for name in ("online.py", "selection.py")
            }
        ),
        "manifest_sha256": digest(manifest),
        "compared_shadow_version": None,
        "selection_basis": "VALIDATION_ONLY",
        "baseline_kind": "CURRENT_CHAMPION" if champion else "PERSISTENCE",
        "champion_alpha": champion_alpha,
        "selected_alpha": alpha,
        "horizon_minutes": horizon_minutes,
        "settings": {
            "minimum_pairs": minimum_pairs,
            "minimum_updates": minimum_updates,
            "blocks": blocks,
        },
        "chronology": {
            "train_end": max(instant(r[timestamp]) for r in history).isoformat(),
            "validation_start": val_start.isoformat(),
            "acceptance_start": acceptance_start.isoformat(),
        },
        "validation_candidates": [
            {"alpha": a, "metrics": m} for _, a, _, m in candidates
        ],
        "acceptance": {
            "count": min(m["count"] for m in metrics.values()),
            "metrics": metrics,
            "paired_block_advantage": block_advantages,
            "empirical_block_bootstrap_interval": block_intervals,
            "interval_caveat": "Not a calibrated confidence guarantee; temporal dependence may persist",
            "scope": "FROZEN_SETTINGS_PREQUENTIAL_OBSERVATION_EVALUATION",
        },
        "lab_decision": "REJECTED" if reasons else "ACCEPTED_SHADOW_ONLY",
        "rejection_reasons": reasons,
        "runtime_promotion_allowed": False,
        "failure_eta_minutes": None,
        "state_before_acceptance": before,
        "state_after_acceptance": chosen.snapshot(),
        "notice": "Temporal block checks are experimental gates, not confidence guarantees or maintenance outcome validation.",
    }
