"""Independent anomaly channel: not a failure probability."""

import hashlib
import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest
from sklearn.pipeline import Pipeline

from scoring.preparation import SEED, split_development
from scripts.experiment_rf import evaluate, pipeline


def fit_normal(train, trees=200):
    normal = train.loc[train.machine_failure.eq(0)]
    if normal.empty:
        raise ValueError("No normal training rows")
    prep = pipeline("rf", True)[:-1]
    model = Pipeline(
        [
            ("preprocess", prep),
            (
                "anomaly",
                IsolationForest(
                    n_estimators=trees,
                    random_state=SEED,
                    contamination="auto",
                    n_jobs=1,
                ),
            ),
        ]
    )
    model.fit(normal)
    return model, len(normal)


def signals(risk, anomaly, anomaly_threshold, risk_threshold=0.15):
    return {
        "risk": bool(risk >= risk_threshold),
        "anomaly": bool(anomaly >= anomaly_threshold),
        "any_alert": bool(risk >= risk_threshold or anomaly >= anomaly_threshold),
    }


def run(output=Path("outputs/cg09")):
    if output.exists():
        raise FileExistsError("Use a fresh output directory")
    train, validation, _ = split_development(pd.read_csv("data/ai4i2020_train.csv"))
    model, count = fit_normal(train)
    scores = -model.score_samples(validation)
    normal = validation.machine_failure.eq(0).to_numpy()
    cutoff = float(np.quantile(scores[normal], 0.99, method="higher"))
    flags = scores >= cutoff
    report = {
        "normal_fit_rows": count,
        "normal_validation_rows": int(normal.sum()),
        "seed": SEED,
        "n_estimators": 200,
        "contamination": "auto",
        "score": "negative score_samples; larger = stranger",
        "threshold": cutoff,
        "normal_quantile": 0.99,
        "observed_normal_alert_fraction": float(flags[normal].mean()),
        "failure_label_diagnostic_not_anomaly_ground_truth": evaluate(
            validation.machine_failure, scores, cutoff
        ),
        "limitations": [
            "Normal failure label is a proxy, not verified anomaly-free truth.",
            "Quantile is selected on validation; no independent anomaly labels or final test.",
            "Anomaly score is not a calibrated failure probability; cannot suppress RF alarms.",
        ],
    }
    output.mkdir(parents=True)
    joblib.dump(model, output / "if.pkl")
    np.testing.assert_array_equal(
        scores, -joblib.load(output / "if.pkl").score_samples(validation)
    )
    report["model_sha256"] = hashlib.sha256(
        (output / "if.pkl").read_bytes()
    ).hexdigest()
    pd.DataFrame(
        {"source_row_index": validation.index, "anomaly_score": scores}
    ).to_csv(output / "validation.csv", index=False)
    (output / "report.json").write_text(json.dumps(report, indent=2) + "\n")
    return report


if __name__ == "__main__":
    print(json.dumps(run(), indent=2))
