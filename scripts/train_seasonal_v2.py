"Generate and evaluate an invented seasonal forecasting laboratory, never AI4I test."

import argparse
import hashlib
import json
import platform
import time
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import sklearn
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import HistGradientBoostingClassifier, RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.metrics import brier_score_loss
from sklearn.pipeline import Pipeline
from threadpoolctl import threadpool_limits

from scoring.preparation import split_development
from scripts.experiment_rf import evaluate, threshold
from scripts.seasonal_v2 import SCENARIO, generate, predictor_columns


def make_model(kind, iterations=180):
    if kind not in {"sensors", "history", "seasonal", "rf_seasonal"}:
        raise ValueError("Unknown predictor specification")
    columns = predictor_columns(temporal=kind != "sensors", calendar=kind != "history")
    prep = ColumnTransformer(
        [("observed", SimpleImputer(strategy="median"), columns)], remainder="drop"
    )
    estimator = (
        RandomForestClassifier(
            n_estimators=120,
            max_depth=12,
            min_samples_leaf=5,
            n_jobs=1,
            random_state=42,
        )
        if kind == "rf_seasonal"
        else HistGradientBoostingClassifier(
            max_iter=iterations,
            max_leaf_nodes=15,
            min_samples_leaf=50,
            max_bins=128,
            learning_rate=0.06,
            l2_regularization=5,
            early_stopping=False,
            random_state=42,
        )
    )
    return Pipeline([("predictors", prep), ("model", estimator)])


def metrics(frame, scores, cutoff):
    y = frame.failure_next_24h.to_numpy(dtype=int)
    if len(np.unique(y)) != 2:
        raise ValueError("Evaluation requires both classes; expand simulated duration")
    result = evaluate(y, scores, cutoff)
    result["rows"] = len(y)
    result["positive_windows"] = int(y.sum())
    result["brier"] = float(brier_score_loss(y, scores))
    result["by_season"] = {}
    for season in ["winter", "spring", "summer", "autumn"]:
        mask = frame.season.eq(season).to_numpy()
        if not mask.any():
            continue
        if len(np.unique(y[mask])) != 2:
            result["by_season"][season] = {
                "rows": int(mask.sum()),
                "positive_windows": int(y[mask].sum()),
                "metrics_unavailable": "One class only",
            }
            continue
        part = evaluate(y[mask], scores[mask], cutoff)
        part.update(
            rows=int(mask.sum()),
            positive_windows=int(y[mask].sum()),
            brier=float(brier_score_loss(y[mask], scores[mask])),
        )
        result["by_season"][season] = part
    return result


def summarize(frame):
    observed = frame.failure_next_24h.notna()
    return {
        "rows": len(frame),
        "labeled_rows": int(observed.sum()),
        "machines": int(frame.machine_id.nunique()),
        "seed": int(frame.seed.iloc[0]),
        "onsets": int(frame.simulated_fault_onset.sum()),
        "positive_windows": int(frame.failure_next_24h.sum()),
        "censored_rows": int((~observed).sum()),
        "start": str(frame.timestamp.min()),
        "end": str(frame.timestamp.max()),
        "by_season": {
            str(s): {
                "rows": len(g),
                "onsets": int(g.simulated_fault_onset.sum()),
                "positive_windows": int(g.failure_next_24h.sum()),
                "mean_air_K": float(g.air_temp_K.mean()),
            }
            for s, g in frame.groupby("season")
        },
    }


def run(output):
    if output.exists():
        raise FileExistsError("Preserve output; use a fresh scenario version")
    source = Path("data/ai4i2020_train.csv")
    training, _, _ = split_development(pd.read_csv(source))
    # Sensor scale only, from original training rows, never from held-out AI4I rows.
    scale_training_rows = len(training)
    scale = {
        "air_base": float(training.air_temp_K.median()),
        "torque_base": float(training.torque_Nm.median()),
    }
    output.mkdir(parents=True)
    sets = {}
    specifications = {
        "train": ("2022-01-01", 730, 8, 42, False),
        "validation": ("2024-01-01", 366, 4, 43, False),
        "evaluation": ("2025-01-01", 365, 4, 44, False),
        "stress": ("2025-01-01", 365, 4, 45, True),
    }
    dataset = {}
    for name, (start, days, machines, seed, stress) in specifications.items():
        data = generate(start, days, machines, seed, stress=stress, **scale)
        path = output / f"{name}.parquet"
        data.to_parquet(path, index=False)
        dataset[name] = summarize(data)
        dataset[name]["sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
        sets[name] = data.loc[data.failure_next_24h.notna()].copy()
        print(
            "generated", name, len(data), "onsets", dataset[name]["onsets"], flush=True
        )
    if (
        sets["train"].timestamp.max() + pd.Timedelta(hours=24)
        >= sets["validation"].timestamp.min()
    ):
        raise ValueError("Training label horizon crosses validation")
    if (
        sets["validation"].timestamp.max() + pd.Timedelta(hours=24)
        >= sets["evaluation"].timestamp.min()
    ):
        raise ValueError("Validation label horizon crosses evaluation")
    names = list(sets)
    for i, name in enumerate(names):
        for other in names[i + 1 :]:
            if set(sets[name].machine_id) & set(sets[other].machine_id):
                raise ValueError(
                    "Machine cohorts overlap across independent simulations"
                )
    training, validation = sets["train"], sets["validation"]
    models = output / "models"
    models.mkdir()
    results = {}
    train_ids = sorted(training.machine_id.unique())
    for machine_count in [1, 2, 4, 8]:
        cohort = training.loc[training.machine_id.isin(train_ids[:machine_count])]
        for kind in ["sensors", "history", "seasonal"]:
            name = f"{kind}_{machine_count}machines"
            start = time.perf_counter()
            model = make_model(kind).fit(cohort, cohort.failure_next_24h)
            scores = model.predict_proba(validation)[:, 1]
            cutoff = threshold(validation.failure_next_24h, scores)
            path = models / f"{name}.pkl"
            joblib.dump(model, path)
            np.testing.assert_array_equal(
                scores, joblib.load(path).predict_proba(validation)[:, 1]
            )
            results[name] = {
                "kind": kind,
                "training_machines": machine_count,
                "training_rows": len(cohort),
                "training_onsets": int(cohort.simulated_fault_onset.sum()),
                "fit_and_validation_seconds": time.perf_counter() - start,
                "validation": metrics(validation, scores, cutoff),
                "threshold_from_validation_f2": cutoff,
                "model_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            }
            print(
                name,
                "validation AP",
                round(results[name]["validation"]["average_precision"], 4),
                flush=True,
            )
    model = make_model("rf_seasonal").fit(training, training.failure_next_24h)
    scores = model.predict_proba(validation)[:, 1]
    cutoff = threshold(validation.failure_next_24h, scores)
    name = "rf_seasonal_8machines"
    path = models / f"{name}.pkl"
    joblib.dump(model, path)
    np.testing.assert_array_equal(
        scores, joblib.load(path).predict_proba(validation)[:, 1]
    )
    results[name] = {
        "kind": "rf_seasonal",
        "training_machines": 8,
        "training_rows": len(training),
        "training_onsets": int(training.simulated_fault_onset.sum()),
        "validation": metrics(validation, scores, cutoff),
        "threshold_from_validation_f2": cutoff,
        "model_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
    }
    eligible = [name for name, r in results.items() if r["training_machines"] == 8]
    selected = max(
        eligible, key=lambda name: results[name]["validation"]["average_precision"]
    )
    frozen = {
        "selected_by_validation_ap": selected,
        "candidates": {
            name: {
                "threshold": r["threshold_from_validation_f2"],
                "model_sha256": r["model_sha256"],
            }
            for name, r in results.items()
        },
    }
    (output / "selection_before_evaluation.json").write_text(
        json.dumps(frozen, indent=2) + "\n"
    )
    evaluation = sets["evaluation"]
    predictions = evaluation[
        ["timestamp", "machine_id", "season", "failure_next_24h"]
    ].copy()
    for name, result in results.items():
        path = models / f"{name}.pkl"
        if hashlib.sha256(path.read_bytes()).hexdigest() != result["model_sha256"]:
            raise ValueError("Own model artifact changed")
        model = joblib.load(path)
        scores = model.predict_proba(evaluation)[:, 1]
        predictions[name] = scores
        result["evaluation_synthetic"] = metrics(
            evaluation, scores, result["threshold_from_validation_f2"]
        )
    predictions.to_parquet(output / "evaluation_predictions.parquet", index=False)
    chosen = joblib.load(models / f"{selected}.pkl")
    stress_scores = chosen.predict_proba(sets["stress"])[:, 1]
    stress = metrics(
        sets["stress"], stress_scores, results[selected]["threshold_from_validation_f2"]
    )
    # Two fixed references; no future labels or evaluation labels used in fit.
    prevalence = float(training.failure_next_24h.mean())
    base = np.full(len(evaluation), prevalence)
    seasonal_prior = training.groupby("season").failure_next_24h.mean()
    prior_scores = evaluation.season.map(seasonal_prior).to_numpy(dtype=float)
    references = {
        "constant_training_prevalence": metrics(evaluation, base, prevalence),
        "season_prior_training_only": metrics(evaluation, prior_scores, prevalence),
    }
    report = {
        "scenario": SCENARIO,
        "scale_from_ai4i_training_only": scale,
        "ai4i_source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
        "ai4i_training_rows_for_sensor_scale": scale_training_rows,
        "versions": {
            "python": platform.python_version(),
            "sklearn": sklearn.__version__,
            "numpy": np.__version__,
            "pandas": pd.__version__,
        },
        "datasets": dataset,
        "results": results,
        "selection": frozen,
        "stress_selected_model_only": stress,
        "references": references,
        "learning_curve_definition": (
            "Nested 1/2/4/8 machine cohorts across identical "
            + "two-year duration, not independent hourly rows"
        ),
        "api_promoted": False,
        "limitations": [
            (
                "Entirely invented simulator; more generated rows do "
                + "not establish better industrial precision."
            ),
            (
                "Air/torque scale from AI4I train only; "
                + "hazard/season/history are assumptions, not fitted "
                + "industrial truth."
            ),
            (
                "No synthetic data appended to original AI4I or used "
                + "to inflate its classification metrics."
            ),
            (
                "Independent seeds/machines and future calendar "
                + "periods, but shared simulator rules are not "
                + "independent real-world evidence."
            ),
            (
                "24h overlapping labels and autocorrelated readings; "
                + "report actual onsets, not independent-row sample "
                + "claims."
            ),
            (
                "Learning curve changes machine diversity as well as "
                + "sample count; not pure sample-size causal experiment."
            ),
            (
                "Thresholds and full-data candidate chosen on "
                + "validation before evaluation; no further tuning from "
                + "evaluation/stress."
            ),
            (
                "All predefined curve points reported on same "
                + "synthetic evaluation; do not repeatedly optimize "
                + "against this set."
            ),
            (
                "Immediate repair and tool replacement policy are "
                + "invented; season risk depends on hypothetical "
                + "operations."
            ),
        ],
    }
    (output / "report.json").write_text(
        json.dumps(report, indent=2, allow_nan=False) + "\n"
    )
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("outputs/seasonal-v2"))
    args = parser.parse_args()
    with threadpool_limits(limits=1):
        run(args.output)
