"""Bounded RF search and independent Isolation Forest integration.

python -m scripts.refine_model --output models/offline-ai4i-v2
Previously inspected test rows are deliberately excluded from refinement/evaluation.
"""

import argparse
import hashlib
import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import IsolationForest, RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.metrics import (
    average_precision_score,
    confusion_matrix,
    fbeta_score,
    precision_recall_curve,
    precision_score,
    recall_score,
)
from sklearn.model_selection import ParameterSampler, StratifiedKFold, cross_val_predict
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import FunctionTransformer, OneHotEncoder

from scoring.model_features import DERIVED, SENSORS, engineer_features
from scripts.train_model import ROOT, SEED, make_models, split_data


def best_threshold(y, scores, beta=1):
    precision, recall, thresholds = precision_recall_curve(y, scores)
    b2 = beta**2
    values = (
        (1 + b2)
        * precision[:-1]
        * recall[:-1]
        / np.maximum(b2 * precision[:-1] + recall[:-1], 1e-15)
    )
    return float(thresholds[int(np.argmax(values))])


def metrics(y, scores, threshold):
    pred = np.asarray(scores) >= threshold
    tn, fp, fn, tp = confusion_matrix(y, pred, labels=[0, 1]).ravel()
    return {
        "threshold": float(threshold),
        "precision": float(precision_score(y, pred, zero_division=0)),
        "recall": float(recall_score(y, pred, zero_division=0)),
        "f1": float(fbeta_score(y, pred, beta=1, zero_division=0)),
        "f2": float(fbeta_score(y, pred, beta=2, zero_division=0)),
        "average_precision": float(average_precision_score(y, scores)),
        "tn": int(tn),
        "fp": int(fp),
        "fn": int(fn),
        "tp": int(tp),
    }


def preprocessing(engineered):
    numeric = SENSORS + DERIVED if engineered else SENSORS
    columns = ColumnTransformer(
        [
            ("numeric", SimpleImputer(strategy="median"), numeric),
            ("type", OneHotEncoder(handle_unknown="ignore"), ["machine_type"]),
        ],
        remainder="drop",
    )
    steps = []
    if engineered:
        steps.append(
            ("engineering", FunctionTransformer(engineer_features, validate=False))
        )
    steps.append(("columns", columns))
    return Pipeline(steps)


def rf_pipeline(parameters, engineered):
    return Pipeline(
        [
            ("preprocess", preprocessing(engineered)),
            (
                "model",
                RandomForestClassifier(
                    n_estimators=200, random_state=SEED, n_jobs=1, **parameters
                ),
            ),
        ]
    )


def anomaly_scores(model, frame):
    """Higher means more anomalous (opposite of sklearn score_samples)."""
    return -model.score_samples(frame)


def fit_anomaly(train):
    # AI4I contemporaneous y=0 is only a proxy for normal operation, not verified history.
    normal = train.loc[train.machine_failure.eq(0)]
    model = Pipeline(
        [
            ("preprocess", preprocessing(False)),
            (
                "model",
                IsolationForest(
                    n_estimators=200,
                    max_samples=256,
                    contamination="auto",
                    random_state=SEED,
                    n_jobs=1,
                ),
            ),
        ]
    )
    model.fit(normal)
    return model, {
        "fit_row_indices": normal.index.tolist(),
        "normal_proxy": "training machine_failure == 0",
        "parameters": model.named_steps["model"].get_params(),
    }


def run(csv_path, output, jobs=2):
    output = Path(output)
    if output.exists():
        raise FileExistsError(f"Refusing to overwrite {output}")
    df = pd.read_csv(csv_path)
    required = SENSORS + ["machine_type", "machine_failure"]
    if not set(required).issubset(df):
        raise ValueError("Required columns missing")
    if df.machine_failure.isna().any() or set(df.machine_failure.unique()) != {0, 1}:
        raise ValueError("Target must contain both binary classes")
    if np.isinf(df[SENSORS].to_numpy(dtype=float)).any():
        raise ValueError("Infinite sensors")
    # Preserve original membership. Never use old test for search, thresholding or new metrics.
    train, validation, old_test = split_data(df)
    y = train.machine_failure
    cv = StratifiedKFold(n_splits=4, shuffle=True, random_state=SEED)
    fold_manifest = [
        {"fit": train.index[fit].tolist(), "held_out": train.index[held].tolist()}
        for fit, held in cv.split(train, y)
    ]
    space = {
        "max_depth": [8, 12, None],
        "min_samples_leaf": [1, 2, 5],
        "max_features": ["sqrt", 1.0],
        "class_weight": [None, "balanced", "balanced_subsample"],
    }
    sampled = list(ParameterSampler(space, n_iter=12, random_state=SEED))
    baseline = {
        "max_depth": 12,
        "min_samples_leaf": 5,
        "max_features": "sqrt",
        "class_weight": "balanced",
    }
    candidates = [(baseline, False)] + [(p, e) for e in [False, True] for p in sampled]
    search = []
    for i, (params, engineered) in enumerate(candidates):
        model = rf_pipeline(params, engineered)
        oof = cross_val_predict(
            model, train, y, cv=cv, method="predict_proba", n_jobs=jobs
        )[:, 1]
        policies = {
            p: metrics(y, oof, best_threshold(y, oof, beta=b))
            for p, b in [("f1", 1), ("f2", 2)]
        }
        search.append(
            {"id": i, "parameters": params, "engineered": engineered, "oof": policies}
        )
        print(
            f"Candidate {i + 1}/{len(candidates)}: F1={policies['f1']['f1']:.4f} F2={policies['f2']['f2']:.4f}",
            flush=True,
        )
    winners = {}
    for policy in ["f1", "f2"]:
        winners[policy] = max(
            search,
            key=lambda c: (
                c["oof"][policy][policy],
                c["oof"][policy]["average_precision"],
            ),
        )
    models = {}
    results = {}
    thresholds = {}
    validation_scores = {}
    for policy, beta in [("f1", 1), ("f2", 2)]:
        candidate = winners[policy]
        model = rf_pipeline(candidate["parameters"], candidate["engineered"]).fit(
            train, y
        )
        scores = model.predict_proba(validation)[:, 1]
        threshold = best_threshold(validation.machine_failure, scores, beta)
        models[policy] = model
        thresholds[policy] = threshold
        validation_scores[policy] = scores
        results[policy] = {
            "candidate_id": candidate["id"],
            "validation_threshold_tuning": metrics(
                validation.machine_failure, scores, threshold
            ),
        }
    baselines = {}
    for name, model in make_models().items():
        model.fit(train, y)
        scores = model.predict_proba(validation)[:, 1]
        baselines[name] = {
            policy: metrics(
                validation.machine_failure,
                scores,
                best_threshold(validation.machine_failure, scores, beta)
                if name != "always_zero"
                else 0.5,
            )
            for policy, beta in [("f1", 1), ("f2", 2)]
        }
    anomaly, provenance = fit_anomaly(train)
    normal_validation = validation.loc[validation.machine_failure.eq(0)]
    # Predeclared normal-row alarm budget: 1%; no failure labels used to optimize detection.
    anomaly_threshold = float(
        np.quantile(anomaly_scores(anomaly, normal_validation), 0.99, method="higher")
    )
    a_scores = anomaly_scores(anomaly, validation)
    anomaly_result = {
        "threshold": anomaly_threshold,
        "normal_validation_quantile": 0.99,
        "normal_validation_rows": len(normal_validation),
        "validation_diagnostic_against_failure_not_anomaly_truth": metrics(
            validation.machine_failure, a_scores, anomaly_threshold
        ),
        **provenance,
    }
    normal_flags = anomaly_scores(anomaly, normal_validation) >= anomaly_threshold
    anomaly_result["observed_normal_validation_alert_fraction"] = float(
        normal_flags.mean()
    )
    bundle = {
        "model_version": "offline-ai4i-v2",
        "rf_models": models,
        "risk_thresholds": thresholds,
        "isolation_forest": anomaly,
        "anomaly_threshold": anomaly_threshold,
        "features": required[:-1],
        "default_policy": "f1",
    }
    import platform

    import sklearn

    report = {
        "source_sha256": hashlib.sha256(Path(csv_path).read_bytes()).hexdigest(),
        "versions": {
            "python": platform.python_version(),
            "sklearn": sklearn.__version__,
            "pandas": pd.__version__,
            "numpy": np.__version__,
            "joblib": joblib.__version__,
        },
        "search": search,
        "selected": results,
        "baselines_same_validation": baselines,
        "isolation_forest": anomaly_result,
        "cv_folds": fold_manifest,
        "train_rows": train.index.tolist(),
        "validation_rows": validation.index.tolist(),
        "excluded_previously_inspected_test_rows": old_test.index.tolist(),
        "limitations": [
            "Validation scores are threshold-tuning results, not an independent final test.",
            "OOF maxima include hyperparameter/threshold selection optimism; not nested CV.",
            "Previously inspected test excluded; new independent data required.",
            "Normal AI4I labels are a proxy, anomalies are not failure truth.",
            "No timestamps; no forecasting or industrial efficacy claims.",
            "F2 weights recall more; no accepted operational FP/FN costs.",
        ],
        "artifacts": {},
    }
    output.mkdir(parents=True)
    for filename, obj in [
        ("bundle.pkl", bundle),
        ("isolation_forest.pkl", anomaly),
        ("rf_f1.pkl", models["f1"]),
        ("rf_f2.pkl", models["f2"]),
    ]:
        joblib.dump(obj, output / filename)
        report["artifacts"][filename] = hashlib.sha256(
            (output / filename).read_bytes()
        ).hexdigest()
    pd.DataFrame(
        {
            "source_row_index": validation.index,
            "machine_failure": validation.machine_failure.to_numpy(),
            "rf_f1_score": validation_scores["f1"],
            "rf_f2_score": validation_scores["f2"],
            "anomaly_score": a_scores,
        }
    ).to_csv(output / "validation_scores.csv", index=False)
    report["artifacts"]["validation_scores.csv"] = hashlib.sha256(
        (output / "validation_scores.csv").read_bytes()
    ).hexdigest()
    (output / "report.json").write_text(
        json.dumps(report, indent=2, allow_nan=False) + "\n"
    )
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--csv", type=Path, default=ROOT / "data/ai4i2020_train.csv")
    parser.add_argument("--output", type=Path, default=ROOT / "models/offline-ai4i-v2")
    parser.add_argument("--jobs", type=int, default=2)
    args = parser.parse_args()
    result = run(args.csv, args.output, args.jobs)
    print(json.dumps(result["selected"], indent=2))
