"""Describe fixed RF alerts on reused validation; never tune or score test rows."""

import argparse
import json
from hashlib import sha256
from io import BytesIO
from pathlib import Path

import numpy as np
import pandas as pd

from scoring.preparation import SEED, split_development
from scoring.scope import APPROVED_SOURCE_SHA256, SCOPE, load_training_source


def diagnostic(labels, scores, cutoff):
    """Expose counts and denominators; undefined rates remain null, never zero."""
    positive = np.asarray(labels) == 1
    alert = np.asarray(scores) >= cutoff
    tp = int((positive & alert).sum())
    fn = int((positive & ~alert).sum())
    fp = int((~positive & alert).sum())
    tn = int((~positive & ~alert).sum())

    def ratio(numerator, denominator):
        return numerator / denominator if denominator else None

    return {
        "rows": tp + fn + fp + tn,
        "positives": tp + fn,
        "negatives": tn + fp,
        "alerts": tp + fp,
        "tp": tp,
        "fn": fn,
        "fp": fp,
        "tn": tn,
        "false_negative_rate": ratio(fn, tp + fn),
        "false_positive_rate": ratio(fp, tn + fp),
        "recall": ratio(tp, tp + fn),
        "precision": ratio(tp, tp + fp),
        "alert_rate": ratio(tp + fp, tp + fn + fp + tn),
    }


def build_report(source, validation_raw, report_raw):
    """Reject incompatible evidence before attaching types to prediction rows."""
    frame = load_training_source(Path(source))
    train, validation, excluded = split_development(frame)
    experiment = json.loads(report_raw)
    if (
        experiment.get("source_sha256") != APPROVED_SOURCE_SHA256
        or experiment.get("task") != "contemporaneous_state_classification"
        or experiment.get("seed") != SEED
    ):
        raise ValueError("Experiment source, task or seed does not match active scope")
    expected = {
        "train": train.index.tolist(),
        "validation": validation.index.tolist(),
        "excluded_previously_inspected_test": excluded.index.tolist(),
    }
    if experiment.get("splits") != expected:
        raise ValueError("Experiment partitions do not match the preserved split")
    cutoff = experiment["validation_tuning_metrics"]["threshold"]
    if (
        isinstance(cutoff, bool)
        or not isinstance(cutoff, (int, float))
        or not np.isfinite(cutoff)
        or not 0 <= cutoff <= 1
    ):
        raise ValueError("RF threshold must be finite and within [0, 1]")
    # Preserve equality with the JSON threshold across CSV serialization.
    scores = pd.read_csv(BytesIO(validation_raw), float_precision="round_trip")
    if set(scores.columns) != {"source_row_index", "label", "rf_score"}:
        raise ValueError("Unexpected validation columns")
    indices = scores.source_row_index
    if (
        not pd.api.types.is_integer_dtype(indices)
        or indices.duplicated().any()
        or len(indices) != len(validation)
        or set(indices) != set(validation.index)
    ):
        raise ValueError("Validation indices must cover the preserved validation once")
    if (
        not scores.label.isin([0, 1]).all()
        or not pd.api.types.is_numeric_dtype(scores.rf_score)
        or not np.isfinite(scores.rf_score).all()
        or not scores.rf_score.between(0, 1).all()
    ):
        raise ValueError("Invalid validation labels or RF scores")
    if not np.array_equal(
        scores.label.to_numpy(), frame.loc[indices, "machine_failure"].to_numpy()
    ):
        raise ValueError("Validation labels do not match the approved source rows")
    scores["machine_type"] = frame.loc[indices, "machine_type"].to_numpy()
    return {
        "schema_version": 1,
        "scope": SCOPE,
        "provenance": {
            "source_sha256": APPROVED_SOURCE_SHA256,
            "validation_csv_sha256": sha256(validation_raw).hexdigest(),
            "experiment_report_sha256": sha256(report_raw).hexdigest(),
            "seed": SEED,
            "partition": "reused_validation_for_threshold_tuning",
            "excluded_test_rows": len(excluded),
        },
        "alert_rule": {"score": "rf_score", "operator": ">=", "threshold": cutoff},
        "overall": diagnostic(scores.label, scores.rf_score, cutoff),
        "by_machine_type": {
            kind: diagnostic(group.label, group.rf_score, cutoff)
            for kind in ("H", "L", "M")
            for group in [scores.loc[scores.machine_type == kind]]
        },
        "rate_denominators": {
            "false_negative_rate": "fn / positives",
            "false_positive_rate": "fp / negatives",
            "recall": "tp / positives",
            "precision": "tp / alerts",
            "alert_rate": "alerts / rows",
            "undefined": "null when denominator is zero",
        },
        "limitations": [
            "Validation was already observed and used to tune this fixed threshold; "
            "not an independent final test.",
            "No threshold or model is selected by this report; scores are "
            "uncalibrated current-state scores.",
            "H/L/M are synthetic machine categories, not people or verified "
            "physical machine regimes.",
            "Small positive counts make subgroup rates unstable; "
            "no causal or fairness conclusion.",
            "Counts describe RF tuned alerts, not classroom severity bands "
            "or Isolation Forest alerts.",
            "Hashes identify inputs; they do not authenticate an experiment "
            "or prove score generation.",
            "No ETA, RUL, 24h forecast, industrial validation "
            "or automated machine control.",
        ],
    }


def run(source, experiment_dir, output):
    output = Path(output)
    if output.exists():
        raise FileExistsError("Use a new output file; preserve previous evidence")
    experiment_dir = Path(experiment_dir)
    result = build_report(
        source,
        (experiment_dir / "validation.csv").read_bytes(),
        (experiment_dir / "report.json").read_bytes(),
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("x", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(result, indent=2, allow_nan=False) + "\n")
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=Path("data/ai4i2020_train.csv"))
    parser.add_argument("--experiment-dir", type=Path, default=Path("outputs/cg08"))
    parser.add_argument(
        "--output", type=Path, default=Path("outputs/cg24-type-diagnostics.json")
    )
    args = parser.parse_args()
    run(args.source, args.experiment_dir, args.output)
