"""Audit whether dated batches support time-to-failure labels; never invent RUL."""

import argparse
import hashlib
import json
import re
from pathlib import Path

import numpy as np
import pandas as pd

from scoring.preparation import SENSORS


def signatures(frame, columns):
    normalized = frame[columns].copy()
    for column in columns:
        if column not in {"machine_id", "machine_type"}:
            normalized[column] = pd.to_numeric(
                normalized[column], errors="raise"
            ).astype("float64")
        else:
            normalized[column] = normalized[column].astype(str)
    return pd.util.hash_pandas_object(normalized, index=False)


def audit(frame, reference=None, verified_identity=False, verified_onsets=False):
    data = frame.copy()
    data["timestamp"] = pd.to_datetime(data.timestamp, utc=True, errors="raise")
    if not data.machine_failure.isin([0, 1]).all() or data.machine_id.isna().any():
        raise ValueError("Binary observed state and machine identity required")
    if not np.isfinite(data[SENSORS].to_numpy(dtype=float)).all():
        raise ValueError("Finite sensors required")
    keys = ["machine_id", "timestamp"]
    state = ["machine_type"] + SENSORS + ["machine_failure"]
    counts = data.groupby(keys).size()
    variations = data.groupby(keys)[state].nunique(dropna=False).max(axis=1)
    conflict = variations[variations.gt(1)].index
    conflict_mask = pd.MultiIndex.from_frame(data[keys]).isin(conflict)
    label_conflicts = data.groupby(keys).machine_failure.nunique().gt(1)
    types = data.groupby("machine_id").machine_type.nunique()
    # No arbitrary ordering within conflicting simultaneous states.
    clean = data.loc[~conflict_mask].drop_duplicates(keys).sort_values(keys)
    gaps = clean.groupby("machine_id").timestamp.diff().dt.total_seconds().dropna()
    batch_times = pd.Series(data.timestamp.unique()).sort_values()
    batch_gaps = batch_times.diff().dt.total_seconds().dropna()
    pair = clean.groupby("machine_id")
    type_changes = (
        clean.machine_type.ne(pair.machine_type.shift())
        & pair.machine_type.shift().notna()
    ).sum()
    wear_delta = pair.tool_wear_min.diff()
    state_delta = pair.machine_failure.diff()
    feature_sig = signatures(data, ["machine_type"] + SENSORS)
    repeated_feature_time = (
        pd.DataFrame({"sig": feature_sig, "time": data.timestamp})
        .groupby("sig")
        .time.nunique()
    )
    next_minutes = []
    censored = 0
    for _, machine in clean.groupby("machine_id"):
        observed = machine.timestamp.astype("int64").to_numpy()
        positives = (
            machine.loc[machine.machine_failure.eq(1), "timestamp"]
            .astype("int64")
            .to_numpy()
        )
        positions = np.searchsorted(positives, observed, side="right")
        valid = positions < len(positives)
        censored += int((~valid).sum())
        next_minutes.extend(
            ((positives[positions[valid]] - observed[valid]) / 60e9).tolist()
        )
    full_state = ["machine_id"] + state + [c for c in data if c.startswith("failure_")]
    ordered_signatures = signatures(data, full_state).to_numpy()
    replay = (
        bool(np.array_equal(ordered_signatures[2000:], ordered_signatures[:-2000]))
        if len(data) > 2000
        else None
    )
    blockers = []
    if len(conflict):
        blockers.append("Conflicting states for same machine and timestamp")
    if types.gt(1).any():
        blockers.append("Machine type changes under same machine_id")
    if not verified_identity:
        blockers.append("No verified physical machine identity")
    if not verified_onsets:
        blockers.append("No verified failure onset and maintenance/cycle log")
    if replay:
        blockers.append("Exactly repeated 2000-row sequence with new timestamps")
    if clean.empty:
        blockers.append("No unambiguous temporal observations")
    result = {
        "rows": len(data),
        "ordered_rows_repeat_every_2000_excluding_timestamp": replay,
        "machines": int(data.machine_id.nunique()),
        "distinct_timestamps": int(data.timestamp.nunique()),
        "start": str(data.timestamp.min()),
        "end": str(data.timestamp.max()),
        "positive_state_rows": int(data.machine_failure.sum()),
        "positive_unique_sensor_type_states": int(
            data.drop_duplicates(["machine_type"] + SENSORS).machine_failure.sum()
        ),
        "duplicate_machine_timestamp_groups": int(counts.gt(1).sum()),
        "conflicting_machine_timestamp_groups": len(conflict),
        "rows_in_conflicting_groups": int(conflict_mask.sum()),
        "conflicting_failure_label_groups": int(label_conflicts.sum()),
        "machines_with_multiple_types": int(types.gt(1).sum()),
        "unambiguous_unique_rows": len(clean),
        "type_changes_in_unambiguous_series": int(type_changes),
        "wear_decreases_between_unambiguous_readings": int(wear_delta.lt(0).sum()),
        "observed_zero_to_one_transitions_not_verified_onsets": int(
            state_delta.eq(1).sum()
        ),
        "sensor_type_signatures": int(feature_sig.nunique()),
        "signatures_repeated_at_multiple_times": int(repeated_feature_time.gt(1).sum()),
        "batch_gap_seconds": {
            "median": float(batch_gaps.median()) if len(batch_gaps) else None
        },
        "per_machine_gap_seconds": {
            "median": float(gaps.median()) if len(gaps) else None,
            "p95": float(gaps.quantile(0.95)) if len(gaps) else None,
            "fraction_over_5minutes": float(gaps.gt(300).mean()) if len(gaps) else None,
        },
        "next_positive_diagnostic": {
            "meaning": (
                "Strictly later observed positive state, NOT failure "
                + "onset or physical remaining lifetime"
            ),
            "unambiguous_rows_with_later_positive": len(next_minutes),
            "censored_rows": censored,
            "median_minutes_to_later_positive": float(np.median(next_minutes))
            if next_minutes
            else None,
        },
        "blockers": blockers,
        "eta_training_ready": not blockers,
        "eta_minutes": None,
        "temporal_criticality": "UNKNOWN",
        "meaning": (
            "This audit estimates feasibility, not a trained ETA "
            + "or validated urgency policy"
        ),
    }
    if reference is not None:
        common = ["machine_type"] + SENSORS
        full = (
            common
            + ["machine_failure"]
            + [c for c in reference if c.startswith("failure_") and c in data]
        )
        for title, columns in [
            ("sensor_type", common),
            ("sensor_type_and_labels", full),
        ]:
            matches = signatures(data, columns).isin(
                set(signatures(reference, columns))
            )
            result[f"exact_ai4i_{title}_match_rows"] = int(matches.sum())
            result[f"exact_ai4i_{title}_match_fraction"] = float(matches.mean())
    return result


def run(root):
    manifest_path = root / "capture_manifest.json"
    manifest = json.loads(manifest_path.read_text())
    parts = []
    if manifest["listing_count"] != len(manifest["files"]):
        raise ValueError("Frozen listing count differs from manifest")
    for filename in sorted(manifest["files"]):
        info = manifest["files"][filename]
        if not re.fullmatch(r"cnc_batch_[0-9]{8}_[0-9]{6}_[0-9]+\.csv", filename):
            raise ValueError("Unexpected snapshot filename")
        path = root / "raw" / filename
        if hashlib.sha256(path.read_bytes()).hexdigest() != info["sha256"]:
            raise ValueError("Source snapshot changed")
        frame = pd.read_csv(path)
        frame["source_file"] = filename
        parts.append(frame)
    report = audit(
        pd.concat(parts, ignore_index=True), pd.read_csv("data/ai4i2020_train.csv")
    )
    report["source"] = {
        "host": manifest["host"],
        "share": manifest["share"],
        "read_only": True,
        "frozen_listing_count": manifest["listing_count"],
        "capture_started_at": manifest["started_at"],
        "capture_completed_at": manifest["completed_at"],
        "capture_manifest_sha256": hashlib.sha256(
            manifest_path.read_bytes()
        ).hexdigest(),
    }
    official_path = root / "reference/ai4i2020_uci.csv"
    if official_path.exists():
        official = pd.read_csv(official_path).rename(
            columns={
                "Type": "machine_type",
                "Air temperature [K]": "air_temp_K",
                "Process temperature [K]": "process_temp_K",
                "Rotational speed [rpm]": "rpm",
                "Torque [Nm]": "torque_Nm",
                "Tool wear [min]": "tool_wear_min",
                "Machine failure": "machine_failure",
                "TWF": "failure_TWF",
                "HDF": "failure_HDF",
                "PWF": "failure_PWF",
                "OSF": "failure_OSF",
                "RNF": "failure_RNF",
            }
        )
        data = pd.concat(parts, ignore_index=True)
        training = pd.read_csv("data/ai4i2020_train.csv")
        features = ["machine_type"] + SENSORS
        full = (
            features
            + ["machine_failure"]
            + [c for c in data if c.startswith("failure_")]
        )
        stream_sig = signatures(data, features)
        official_sig = signatures(official, features)
        train_sig = signatures(training, features)
        complement = set(official_sig) - set(train_sig)
        report["official_uci_reference"] = {
            "url": (
                "https://archive.ics.uci.edu/dataset/601/ai4i+2020+pred"
                + "ictive+maintenance+dataset"
            ),
            "sha256": hashlib.sha256(official_path.read_bytes()).hexdigest(),
            "rows": len(official),
            "static_reference_complement_signatures": len(complement),
            "stream_sensor_type_match_rows": int(
                stream_sig.isin(set(official_sig)).sum()
            ),
            "stream_sensor_type_and_labels_match_rows": int(
                signatures(data, full).isin(set(signatures(official, full))).sum()
            ),
            "stream_unique_states_equal_complement_of_8000_training_rows": set(
                stream_sig
            )
            == complement,
            "meaning": (
                "Fingerprint provenance only, not temporal labels or "
                + "model performance evaluation"
            ),
        }
    report["limitations"] = [
        (
            "SMB availability and batch timestamps do not prove "
            + "physical origin or chronological failure onset."
        ),
        (
            "AI4I matching is forensic data provenance, not "
            + "evaluation of the old test or model training."
        ),
        (
            "Simultaneous conflicting states prevent valid "
            + "longitudinal labels; no type changes were observed in "
            + "this snapshot."
        ),
        "A later positive label under a reused ID is not time-to-failure ground truth.",
        (
            "Wear decreases may be maintenance or unrelated "
            + "sample; no repair/cycle log provided."
        ),
        (
            "ETA remains unavailable; current-state severity and "
            + "API response latency are different quantities."
        ),
    ]
    (root / "audit.json").write_text(
        json.dumps(report, indent=2, allow_nan=False) + "\n"
    )
    Path("docs/evidence/CG02_temporal_feasibility.json").write_text(
        json.dumps(report, indent=2, allow_nan=False) + "\n"
    )
    print(json.dumps(report, indent=2))
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("outputs/smb-eta-2026-10-19"))
    run(parser.parse_args().root)
