"""Reproducible AI4I state classification; no forecasting claims.

Run from the repository root: python -m scripts.train_model
"""

import argparse
import hashlib
import json
import platform
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import sklearn
from sklearn.compose import ColumnTransformer
from sklearn.dummy import DummyClassifier
from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    average_precision_score,
    confusion_matrix,
    f1_score,
    precision_recall_curve,
    precision_score,
    recall_score,
)
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

FEATURES = ["air_temp_K", "process_temp_K", "rpm", "torque_Nm", "tool_wear_min"]
TARGET = "machine_failure"
SEED = 42
ROOT = Path(__file__).resolve().parents[1]


def split_data(df):
    train, remaining = train_test_split(
        df, test_size=0.3, random_state=SEED, stratify=df[TARGET]
    )
    validation, test = train_test_split(
        remaining, test_size=0.5, random_state=SEED, stratify=remaining[TARGET]
    )
    return train, validation, test


def make_models():
    estimators = {
        "always_zero": DummyClassifier(strategy="constant", constant=0),
        "logistic_regression": LogisticRegression(
            class_weight="balanced", random_state=SEED, max_iter=2000
        ),
        "random_forest": RandomForestClassifier(
            n_estimators=200,
            max_depth=12,
            min_samples_leaf=5,
            class_weight="balanced",
            random_state=SEED,
            n_jobs=1,
        ),
    }
    return {
        name: Pipeline(
            [
                (
                    "features",
                    ColumnTransformer(
                        [
                            (
                                "sensors",
                                Pipeline(
                                    [
                                        ("imputer", SimpleImputer(strategy="median")),
                                        ("scale", StandardScaler()),
                                    ]
                                ),
                                FEATURES,
                            )
                        ],
                        remainder="drop",
                    ),
                ),
                ("classifier", estimator),
            ]
        )
        for name, estimator in estimators.items()
    }


def select_threshold(y, scores):
    precision, recall, thresholds = precision_recall_curve(y, scores)
    f1 = (
        2
        * precision[:-1]
        * recall[:-1]
        / np.maximum(precision[:-1] + recall[:-1], 1e-15)
    )
    # Ascending thresholds: ties favor lower threshold (higher recall).
    return float(thresholds[int(np.argmax(f1))])


def evaluate(y, scores, threshold):
    predicted = np.asarray(scores) >= threshold
    return {
        "threshold": threshold,
        "precision": float(precision_score(y, predicted, zero_division=0)),
        "recall": float(recall_score(y, predicted, zero_division=0)),
        "f1": float(f1_score(y, predicted, zero_division=0)),
        "average_precision": float(average_precision_score(y, scores)),
        "confusion_matrix_tn_fp_fn_tp": confusion_matrix(
            y, predicted, labels=[0, 1]
        ).tolist(),
    }


def run(csv_path, output):
    df = pd.read_csv(csv_path)
    if not set(FEATURES + [TARGET]).issubset(df.columns):
        raise ValueError("Required sensor/target columns missing")
    if df[TARGET].isna().any() or set(df[TARGET].unique()) != {0, 1}:
        raise ValueError(
            "Target must contain both binary classes without missing values"
        )
    if not np.isfinite(df[FEATURES].dropna().to_numpy(dtype=float)).all():
        raise ValueError("Non-finite sensor values")
    output = Path(output)
    if output.exists():
        raise FileExistsError(f"Refusing to overwrite an existing run: {output}")
    train, validation, test = split_data(df)
    report = {
        "task": "contemporaneous_state_classification",
        "seed": SEED,
        "source_sha256": hashlib.sha256(Path(csv_path).read_bytes()).hexdigest(),
        "features": FEATURES,
        "target": TARGET,
        "split_method": "random_stratified_70_15_15_not_chronological",
        "versions": {
            "python": platform.python_version(),
            "scikit-learn": sklearn.__version__,
            "pandas": pd.__version__,
            "numpy": np.__version__,
            "joblib": joblib.__version__,
        },
        "split": {
            name: {
                "rows": len(part),
                "positives": int(part[TARGET].sum()),
                "source_row_indices": part.index.tolist(),
            }
            for name, part in zip(
                ["train", "validation", "test"], [train, validation, test]
            )
        },
        "eda": {
            "rows": len(df),
            "missing": df.isna().sum().to_dict(),
            "duplicates": int(df.duplicated().sum()),
            "sensor_summary": df[FEATURES].describe().to_dict(),
        },
        "models": {},
        "limitations": [
            "No timestamps or maintenance history; no validated 24-hour horizon.",
            "Random splits do not establish transfer to unseen machines or future operation.",
            "Scores are not calibrated probabilities; no operational cost or alarms/day estimate.",
            "AI4I labels and failure subtypes are excluded from model inputs.",
        ],
    }
    models = make_models()
    for name, model in models.items():
        model.fit(train, train[TARGET])
        val_scores = model.predict_proba(validation)[:, 1]
        # Baselines retain their default threshold; RF threshold is selected only on validation.
        threshold = (
            select_threshold(validation[TARGET], val_scores)
            if name == "random_forest"
            else 0.5
        )
        report["models"][name] = {
            "parameters": model.named_steps["classifier"].get_params(),
            "validation": evaluate(validation[TARGET], val_scores, threshold),
            "test": evaluate(test[TARGET], model.predict_proba(test)[:, 1], threshold),
        }
    # No refit after evaluation: persisted model is exactly the evaluated RF pipeline.
    output.mkdir(parents=True)
    model_path = output / "cnc_failure_model.pkl"
    joblib.dump(models["random_forest"], model_path)
    report["model_sha256"] = hashlib.sha256(model_path.read_bytes()).hexdigest()
    report["saved_model"] = "random_forest"
    (output / "report.json").write_text(
        json.dumps(report, indent=2, allow_nan=False) + "\n"
    )
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--csv", type=Path, default=ROOT / "data/ai4i2020_train.csv")
    parser.add_argument("--output", type=Path, default=ROOT / "models/offline-ai4i-v1")
    args = parser.parse_args()
    result = run(args.csv, args.output)
    print(
        json.dumps(
            {name: values["test"] for name, values in result["models"].items()},
            indent=2,
        )
    )
