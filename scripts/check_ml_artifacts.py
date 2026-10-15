"""CI smoke check for trusted, repository-owned ML artifacts; never retrains.

Run: python -m scripts.check_ml_artifacts
"""

import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

from scoring.inference import load_bundle, predict_signals
from scripts.refine_model import metrics


def require(condition, message):
    if not condition:
        raise ValueError(message)


def check(root):
    root = Path(root)
    source = root / "data/ai4i2020_train.csv"
    df = pd.read_csv(source)
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    v1 = root / "models/offline-ai4i-v1"
    first = json.loads((v1 / "report.json").read_text())
    require(first["source_sha256"] == digest, "v1 source hash mismatch")
    require(
        hashlib.sha256((v1 / "cnc_failure_model.pkl").read_bytes()).hexdigest()
        == first["model_sha256"],
        "v1 model hash mismatch",
    )
    directory = root / "models/offline-ai4i-v2"
    report = json.loads((directory / "report.json").read_text())
    require(report["source_sha256"] == digest, "v2 source hash mismatch")
    for filename, expected in report["artifacts"].items():
        require(
            hashlib.sha256((directory / filename).read_bytes()).hexdigest() == expected,
            f"Artifact hash mismatch: {filename}",
        )
    groups = [
        report["train_rows"],
        report["validation_rows"],
        report["excluded_previously_inspected_test_rows"],
    ]
    flat = [index for group in groups for index in group]
    require(
        len(flat) == len(set(flat)) == len(df) and set(flat) == set(df.index),
        "Split membership missing or overlapping",
    )
    train = set(groups[0])
    held_out = []
    for fold in report["cv_folds"]:
        fit, held = set(fold["fit"]), set(fold["held_out"])
        require(not fit & held and fit | held == train, "CV leakage or missing rows")
        held_out.extend(fold["held_out"])
    require(
        len(held_out) == len(set(held_out)) == len(train) and set(held_out) == train,
        "CV held-out membership invalid",
    )
    normal = report["isolation_forest"]["fit_row_indices"]
    require(
        set(normal)
        == set(df.loc[df.index.isin(train) & df.machine_failure.eq(0)].index),
        "Isolation Forest must fit exactly the normal training rows",
    )
    bundle = load_bundle(directory)
    validation = df.iloc[groups[1]]
    saved = pd.read_csv(directory / "validation_scores.csv")
    require(
        saved.source_row_index.tolist() == groups[1], "Saved score membership mismatch"
    )
    require(
        saved.machine_failure.tolist() == validation.machine_failure.tolist(),
        "Saved target labels mismatch",
    )
    sensors = validation[bundle["features"]]
    for policy in ["f1", "f2"]:
        results = predict_signals(bundle, sensors, policy)
        scores = [row["failure_score"] for row in results]
        np.testing.assert_allclose(
            scores, saved[f"rf_{policy}_score"], rtol=0, atol=1e-14
        )
        np.testing.assert_allclose(
            [row["anomaly_score"] for row in results],
            saved.anomaly_score,
            rtol=0,
            atol=1e-14,
        )
        actual = metrics(
            validation.machine_failure, scores, bundle["risk_thresholds"][policy]
        )
        expected = report["selected"][policy]["validation_threshold_tuning"]
        for key, value in expected.items():
            require(
                np.isclose(actual[key], value, rtol=0, atol=1e-12),
                f"{policy} {key} metric mismatch",
            )
        require(
            all(
                row["risk_alert"]
                == (row["failure_score"] >= bundle["risk_thresholds"][policy])
                and row["anomaly_alert"]
                == (row["anomaly_score"] >= bundle["anomaly_threshold"])
                for row in results
            ),
            "Signals are not independent threshold decisions",
        )
    print(
        "ML artifacts verified: hashes, partitions, normal-only IF, scores and F1/F2 metrics"
    )


if __name__ == "__main__":
    check(Path(__file__).resolve().parents[1])
