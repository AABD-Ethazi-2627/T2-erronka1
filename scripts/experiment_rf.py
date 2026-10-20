"""Controlled development experiment. Never evaluates the previously inspected test."""

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
    fbeta_score,
    precision_recall_curve,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.model_selection import StratifiedKFold, cross_val_predict
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import FunctionTransformer, OneHotEncoder, StandardScaler

from scoring.preparation import DERIVED, SEED, SENSORS, features, split_development
from scoring.scope import INPUT_FEATURES, load_training_source


def pipeline(kind, physical=False, weight=None, trees=120, depth=12):
    numeric = SENSORS + (DERIVED if physical else [])
    prep = ColumnTransformer(
        [
            (
                "numeric",
                Pipeline(
                    [
                        ("impute", SimpleImputer(strategy="median")),
                        ("scale", StandardScaler()),
                    ]
                ),
                numeric,
            ),
            ("type", OneHotEncoder(handle_unknown="ignore"), ["machine_type"]),
        ],
        remainder="drop",
    )
    if kind == "dummy":
        estimator = DummyClassifier(strategy="constant", constant=0)
    elif kind == "logistic":
        estimator = LogisticRegression(
            class_weight=weight, max_iter=3000, random_state=SEED
        )
    else:
        estimator = RandomForestClassifier(
            n_estimators=trees,
            max_depth=depth,
            min_samples_leaf=2,
            class_weight=weight,
            random_state=SEED,
            n_jobs=1,
        )
    return Pipeline(
        [
            ("physics", FunctionTransformer(features, validate=False)),
            ("preprocess", prep),
            ("model", estimator),
        ]
    )


def threshold(y, scores, beta=2):
    precision, recall, limits = precision_recall_curve(y, scores)
    b = beta**2
    quality = (
        (1 + b)
        * precision[:-1]
        * recall[:-1]
        / np.maximum(b * precision[:-1] + recall[:-1], 1e-15)
    )
    return float(limits[np.argmax(quality)])


def evaluate(y, scores, cutoff):
    prediction = np.asarray(scores) >= cutoff
    return {
        "threshold": float(cutoff),
        "precision": float(precision_score(y, prediction, zero_division=0)),
        "recall": float(recall_score(y, prediction, zero_division=0)),
        "f1": float(fbeta_score(y, prediction, beta=1, zero_division=0)),
        "f2": float(fbeta_score(y, prediction, beta=2, zero_division=0)),
        "roc_auc": float(roc_auc_score(y, scores)),
        "average_precision": float(average_precision_score(y, scores)),
        "confusion_matrix": confusion_matrix(y, prediction, labels=[0, 1]).tolist(),
    }


def run(output):
    if output.exists():
        raise FileExistsError(
            "Use a new output directory; do not overwrite experiment evidence"
        )
    source = Path("data/ai4i2020_train.csv")
    frame = load_training_source(source)
    train, validation, excluded = split_development(frame)
    # Guard exact feature duplicates across partitions/folds, irrespective of labels/IDs.
    columns = SENSORS + ["machine_type"]
    signature = pd.util.hash_pandas_object(frame[columns], index=False)
    if signature.duplicated().any():
        raise ValueError(
            "Repeated feature signatures: require grouped split/CV before evaluation"
        )
    cv = list(
        StratifiedKFold(n_splits=4, shuffle=True, random_state=SEED).split(
            train, train.machine_failure
        )
    )
    specifications = [("dummy", False, None, 12), ("logistic", False, "balanced", 12)]
    specifications += [
        ("rf", p, w, d)
        for p in [False, True]
        for w in [None, "balanced"]
        for d in [8, 12]
    ]
    results = []
    candidates = []
    for kind, physical, weight, depth in specifications:
        model = pipeline(kind, physical, weight, depth=depth)
        scores = cross_val_predict(
            model,
            train[INPUT_FEATURES],
            train.machine_failure,
            cv=cv,
            method="predict_proba",
            n_jobs=2,
        )[:, 1]
        cutoff = 0.5 if kind == "dummy" else threshold(train.machine_failure, scores)
        result = {
            "kind": kind,
            "physical": physical,
            "class_weight": weight,
            "max_depth": depth,
            "oof_selection_metrics": evaluate(train.machine_failure, scores, cutoff),
        }
        results.append(result)
        candidates.append(model)
        print(json.dumps(result), flush=True)
    # Pick on train OOF AP, not validation; threshold alone tuned on validation.
    eligible = [i for i, r in enumerate(results) if r["kind"] == "rf"]
    winner = max(
        eligible, key=lambda i: results[i]["oof_selection_metrics"]["average_precision"]
    )
    model = candidates[winner].fit(train[INPUT_FEATURES], train.machine_failure)
    scores = model.predict_proba(validation[INPUT_FEATURES])[:, 1]
    cutoff = threshold(validation.machine_failure, scores)
    output.mkdir(parents=True)
    path = output / "rf.pkl"
    joblib.dump(model, path)
    np.testing.assert_array_equal(
        scores, joblib.load(path).predict_proba(validation[INPUT_FEATURES])[:, 1]
    )
    pd.DataFrame(
        {
            "source_row_index": validation.index,
            "label": validation.machine_failure.to_numpy(),
            "rf_score": scores,
        }
    ).to_csv(output / "validation.csv", index=False)
    report = {
        "task": "contemporaneous_state_classification",
        "seed": SEED,
        "source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
        "versions": {
            "python": platform.python_version(),
            "sklearn": sklearn.__version__,
            "numpy": np.__version__,
            "pandas": pd.__version__,
            "joblib": joblib.__version__,
        },
        "splits": {
            "train": train.index.tolist(),
            "validation": validation.index.tolist(),
            "excluded_previously_inspected_test": excluded.index.tolist(),
        },
        "folds": [
            {"fit": train.index[a].tolist(), "held": train.index[b].tolist()}
            for a, b in cv
        ],
        "search": results,
        "winner": winner,
        "validation_tuning_metrics": evaluate(
            validation.machine_failure, scores, cutoff
        ),
        "model_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "reload_max_probability_difference": 0.0,
        "limitations": [
            "OOF model selection and threshold tuning are optimistic; not nested CV.",
            "Validation and excluded test were previously inspected in PR29; no new independent final test.",
            "No timestamps or verified physical identity; no 24h or seasonal forecast claims.",
            "Class weighting changes probability calibration; score is not validated industrial risk.",
        ],
    }
    (output / "report.json").write_text(
        json.dumps(report, indent=2, allow_nan=False) + "\n"
    )
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("outputs/cg08"))
    args = parser.parse_args()
    run(args.output)
