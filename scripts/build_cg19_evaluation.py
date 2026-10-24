"""Describe saved reused-validation scores for CG19; never fit or predict."""

import argparse
import json
from hashlib import sha256
from io import BytesIO
from pathlib import Path

import numpy as np
import pandas as pd

from scoring.preparation import split_development
from scoring.scope import load_training_source

REFERENCE_COMMIT = "a4da1d5474d72e72047c0f334aadedde09114553"
# Pin the independently corrected PR49 report, not its historical predecessor.
REFERENCE_SHA256 = "deb550b826ecdebde2628e7624dbb28ff44b5c17eec2769baecd552f8f5e62dd"


def summarize(frame, threshold):
    positive = frame.label == 1
    alert = frame.rf_score >= threshold
    return {
        "rows": len(frame),
        "positives": int(positive.sum()),
        "negatives": int((~positive).sum()),
        "alerts": int(alert.sum()),
        "tp": int((positive & alert).sum()),
        "fn": int((positive & ~alert).sum()),
        "fp": int((~positive & alert).sum()),
        "tn": int((~positive & ~alert).sum()),
    }


def describe(scores, source, threshold):
    scores = scores.copy()
    for column in ["machine_type", "tool_wear_min"]:
        scores[column] = source.loc[scores.source_row_index, column].to_numpy()
    bins = []
    for kind in ["H", "L", "M"]:
        for lower, name in [
            (0, "0–49"),
            (50, "50–99"),
            (100, "100–149"),
            (150, "150–199"),
            (200, "200–249"),
            (250, "250+"),
        ]:
            group = scores.loc[
                (scores.machine_type == kind)
                & (scores.tool_wear_min >= lower)
                & (scores.tool_wear_min < (lower + 50 if lower < 250 else float("inf")))
            ]
            if len(group):
                bins.append(
                    {
                        "machine_type": kind,
                        "wear_bin": name,
                        "rows": len(group),
                        "positives": int(group.label.sum()),
                        "failure_rate": float(group.label.mean()),
                    }
                )
    cases = {}
    for kind, mask in {
        "FP": (scores.label == 0) & (scores.rf_score >= threshold),
        "FN": (scores.label == 1) & (scores.rf_score < threshold),
    }.items():
        candidates = scores.loc[mask].sort_values("source_row_index")
        if len(candidates):
            cases[kind] = candidates.iloc[0].to_dict()
    return {
        "threshold": threshold,
        "overall": summarize(scores, threshold),
        "wear_bins": bins,
        "cases": cases,
    }


def build(source_path, validation_raw, reference_raw):
    if sha256(reference_raw).hexdigest() != REFERENCE_SHA256:
        raise ValueError("Expected exact corrected PR49 diagnostic report")
    reference = json.loads(reference_raw)
    source = load_training_source(source_path)
    if (
        sha256(validation_raw).hexdigest()
        != reference["provenance"]["validation_csv_sha256"]
    ):
        raise ValueError("Validation CSV differs from corrected reference")
    if reference["provenance"]["partition"] != "reused_validation_for_threshold_tuning":
        raise ValueError("Only reused validation is authorized")
    _, validation, _ = split_development(source)
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
        raise ValueError("Validation must cover the preserved split exactly once")
    if (
        not scores.label.isin([0, 1]).all()
        or not np.isfinite(scores.rf_score).all()
        or not scores.rf_score.between(0, 1).all()
        or not np.array_equal(scores.label, source.loc[indices, "machine_failure"])
    ):
        raise ValueError("Invalid validation scores or source labels")
    result = describe(scores, source, reference["alert_rule"]["threshold"])
    if any(
        result["overall"][key] != reference["overall"][key] for key in result["overall"]
    ):
        raise ValueError("Counts disagree with corrected reference")
    result["provenance"] = {
        **reference["provenance"],
        "reference_commit": REFERENCE_COMMIT,
        "reference_sha256": REFERENCE_SHA256,
    }
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=Path("data/ai4i2020_train.csv"))
    parser.add_argument("--validation-csv", type=Path, required=True)
    parser.add_argument("--reference-json", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = build(
        args.source, args.validation_csv.read_bytes(), args.reference_json.read_bytes()
    )
    with args.output.open("x", encoding="utf-8", newline="\n") as handle:
        handle.write(
            json.dumps(result, indent=2, ensure_ascii=False, allow_nan=False) + "\n"
        )
