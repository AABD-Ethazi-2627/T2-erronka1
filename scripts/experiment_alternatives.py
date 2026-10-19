"""Bounded model/ensemble comparison on original development folds, never old test."""

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
from imblearn.ensemble import BalancedRandomForestClassifier
from sklearn.base import clone
from sklearn.calibration import CalibratedClassifierCV
from sklearn.ensemble import (
    ExtraTreesClassifier,
    GradientBoostingClassifier,
    HistGradientBoostingClassifier,
    IsolationForest,
    RandomForestClassifier,
)
from sklearn.metrics import average_precision_score
from sklearn.model_selection import KFold
from sklearn.neighbors import LocalOutlierFactor
from sklearn.pipeline import Pipeline
from sklearn.svm import SVC
from threadpoolctl import threadpool_limits

from scoring.preparation import SEED, SENSORS, split_development
from scripts.experiment_rf import evaluate, pipeline, threshold


def candidates(quick=False):
    reference = pipeline("rf", True, trees=5 if quick else 120, depth=12)
    models = {"rf_reference": reference}
    if quick:
        return models
    from catboost import CatBoostClassifier

    def with_model(estimator, physical=True):
        model = pipeline("rf", physical)
        model.set_params(model=estimator)
        return model

    models["dummy"] = pipeline("dummy")
    models["logistic_physics"] = pipeline("logistic", True, "balanced")
    models["rf_deep"] = with_model(
        RandomForestClassifier(
            n_estimators=200, min_samples_leaf=1, random_state=SEED, n_jobs=1
        )
    )
    models["rf_calibrated_sigmoid"] = CalibratedClassifierCV(
        clone(reference), method="sigmoid", cv=3, n_jobs=1
    )
    for leaf in [1, 3]:
        models[f"extra_leaf{leaf}"] = with_model(
            ExtraTreesClassifier(
                n_estimators=200, min_samples_leaf=leaf, random_state=SEED, n_jobs=1
            )
        )
    for leaves, weight in [(7, None), (15, None), (15, "balanced"), (31, None)]:
        models[f"hist_leaf{leaves}_{weight}"] = with_model(
            HistGradientBoostingClassifier(
                max_iter=250,
                learning_rate=0.07,
                max_leaf_nodes=leaves,
                l2_regularization=1.0,
                class_weight=weight,
                early_stopping=False,
                random_state=SEED,
            )
        )
    for depth in [2, 3]:
        models[f"gradient_depth{depth}"] = with_model(
            GradientBoostingClassifier(
                n_estimators=200,
                learning_rate=0.05,
                max_depth=depth,
                min_samples_leaf=5,
                random_state=SEED,
            )
        )
    for depth, weight in [(4, None), (6, None), (6, "Balanced")]:
        models[f"cat_depth{depth}_{weight}"] = with_model(
            CatBoostClassifier(
                iterations=400,
                depth=depth,
                learning_rate=0.05,
                l2_leaf_reg=3.0,
                auto_class_weights=weight,
                random_seed=SEED,
                thread_count=1,
                verbose=False,
                allow_writing_files=False,
            )
        )
    for c in [1.0, 10.0]:
        models[f"svm_C{c}"] = with_model(
            SVC(C=c, class_weight="balanced", probability=True, random_state=SEED)
        )
    models["balanced_rf"] = with_model(
        BalancedRandomForestClassifier(
            n_estimators=200,
            max_depth=12,
            min_samples_leaf=2,
            sampling_strategy="all",
            replacement=True,
            bootstrap=False,
            random_state=SEED,
            n_jobs=1,
        )
    )
    return models


def fit_oof(model, train, folds):
    scores = np.full(len(train), np.nan)
    seen = np.zeros(len(train), dtype=int)
    for fit, held in folds:
        if set(fit) & set(held):
            raise ValueError("Overlapping fold")
        fitted = clone(model).fit(train.iloc[fit], train.iloc[fit].machine_failure)
        scores[held] = fitted.predict_proba(train.iloc[held])[:, 1]
        seen[held] += 1
    if not (seen == 1).all() or not np.isfinite(scores).all():
        raise ValueError("Every row must be held out exactly once")
    return scores


def blend(scores, members):
    if not members:
        raise ValueError("Empty ensemble")
    arrays = [np.asarray(scores[name], dtype=float) for name in members]
    if any(a.shape != arrays[0].shape or not np.isfinite(a).all() for a in arrays):
        raise ValueError("Invalid aligned scores")
    return np.mean(arrays, axis=0)


def operating_points(y, scores):
    """Lowest false positives at each achievable recall floor, using OOF only."""
    y = np.asarray(y, dtype=bool)
    order = np.argsort(-scores, kind="stable")
    sorted_scores = scores[order]
    ends = np.r_[np.flatnonzero(np.diff(sorted_scores)), len(scores) - 1]
    tp = np.cumsum(y[order])[ends]
    fp = np.cumsum(~y[order])[ends]
    recall = tp / y.sum()
    result = {}
    for floor in [0.76, 0.85, 0.90, 0.95]:
        valid = np.flatnonzero(recall >= floor)
        i = valid[np.argmin(fp[valid])]
        result[str(floor)] = {
            "threshold": float(sorted_scores[ends[i]]),
            "true_positives": int(tp[i]),
            "false_positives": int(fp[i]),
            "recall": float(recall[i]),
        }
    return result


def anomaly_comparison(train, validation, supervised_flags):
    normal = train.loc[train.machine_failure.eq(0)]
    prep = pipeline("rf", True)[:-1]
    models = {
        "isolation": IsolationForest(n_estimators=200, random_state=SEED, n_jobs=1),
        "lof20": LocalOutlierFactor(n_neighbors=20, novelty=True, n_jobs=1),
        "lof50": LocalOutlierFactor(n_neighbors=50, novelty=True, n_jobs=1),
    }
    results = {}
    for name, detector in models.items():
        model = Pipeline([("prep", clone(prep)), ("detector", detector)])
        held_scores = np.full(len(normal), np.nan)
        for fit, held in KFold(4, shuffle=True, random_state=SEED).split(normal):
            fold = clone(model).fit(normal.iloc[fit])
            held_scores[held] = -fold.score_samples(normal.iloc[held])
        cutoff = float(np.quantile(held_scores, 0.99, method="higher"))
        fitted = model.fit(normal)
        score = -fitted.score_samples(validation)
        flags = score >= cutoff
        y = validation.machine_failure.to_numpy(dtype=bool)
        results[name] = {
            "threshold_from_normal_train_oof": cutoff,
            "validation_failure_diagnostic_only": evaluate(y, score, cutoff),
            "new_failures_beyond_selected_supervised": int(
                (flags & ~supervised_flags & y).sum()
            ),
            "new_false_alarms_beyond_selected_supervised": int(
                (flags & ~supervised_flags & ~y).sum()
            ),
            "normal_oof_quantile": 0.99,
        }
    return results


def run(output):
    if output.exists():
        raise FileExistsError("Preserve experiments; use a fresh output directory")
    source = Path("data/ai4i2020_train.csv")
    previous = json.loads(Path("outputs/cg08/report.json").read_text())
    if hashlib.sha256(source.read_bytes()).hexdigest() != previous["source_sha256"]:
        raise ValueError("Source changed since baseline")
    frame = pd.read_csv(source)
    if frame[SENSORS + ["machine_type"]].duplicated().any():
        raise ValueError("Duplicate signatures require grouped CV")
    train, validation, excluded = split_development(frame)
    for key, data in [
        ("train", train),
        ("validation", validation),
        ("excluded_previously_inspected_test", excluded),
    ]:
        if data.index.tolist() != previous["splits"][key]:
            raise ValueError("Original split changed")
    folds = [
        (train.index.get_indexer(f["fit"]), train.index.get_indexer(f["held"]))
        for f in previous["folds"]
    ]
    if any((a < 0).any() or (b < 0).any() for a, b in folds):
        raise ValueError("Unknown fold indices")
    output.mkdir(parents=True)
    models = candidates()
    oof, reports = {}, {}
    y = train.machine_failure.to_numpy()
    for name, model in models.items():
        start = time.perf_counter()
        oof[name] = fit_oof(model, train, folds)
        cutoff = 0.5 if name == "dummy" else threshold(y, oof[name])
        reports[name] = {
            "kind": "individual",
            "oof": evaluate(y, oof[name], cutoff),
            "cv_seconds": time.perf_counter() - start,
            "operating_points_oof": operating_points(y, oof[name]),
        }
        pd.DataFrame(
            {"source_row_index": train.index, "label": y, "score": oof[name]}
        ).to_csv(output / f"{name}_oof.csv", index=False)
        print(
            name, "AP", round(reports[name]["oof"]["average_precision"], 6), flush=True
        )
    baseline = previous["search"][previous["winner"]]["oof_selection_metrics"][
        "average_precision"
    ]
    if not np.isclose(
        reports["rf_reference"]["oof"]["average_precision"],
        baseline,
        atol=1e-12,
        rtol=0,
    ):
        raise ValueError("Reference RF did not reproduce original AP")
    ranked = sorted(
        models, key=lambda n: reports[n]["oof"]["average_precision"], reverse=True
    )
    challenger = next(n for n in ranked if not n.startswith("rf_"))
    ensembles = {
        "rf_challenger_mean": ["rf_reference", challenger],
        "top3_mean": ranked[:3],
    }
    for name, members in ensembles.items():
        oof[name] = blend(oof, members)
        cutoff = threshold(y, oof[name])
        reports[name] = {
            "kind": "soft_voting",
            "members": members,
            "oof": evaluate(y, oof[name], cutoff),
            "operating_points_oof": operating_points(y, oof[name]),
        }
    winner = max(reports, key=lambda n: reports[n]["oof"]["average_precision"])
    # Frozen selection persisted before any validation prediction.
    (output / "selection.json").write_text(
        json.dumps(
            {"winner": winner, "ranking_oof": ranked, "ensembles": ensembles}, indent=2
        )
        + "\n"
    )
    validation_scores = {}
    for name, model in models.items():
        fitted = clone(model).fit(train, y)
        scores = fitted.predict_proba(validation)[:, 1]
        validation_scores[name] = scores
        reports[name]["validation_at_oof_threshold"] = evaluate(
            validation.machine_failure, scores, reports[name]["oof"]["threshold"]
        )
        reports[name]["parameters"] = {
            k: v
            for k, v in fitted.get_params().items()
            if k.startswith("model__")
            and isinstance(v, (str, int, float, bool, type(None)))
        }
        if name in set(ranked[:3] + ["rf_reference", challenger]):
            path = output / f"{name}.pkl"
            joblib.dump(fitted, path)
            np.testing.assert_array_equal(
                scores, joblib.load(path).predict_proba(validation)[:, 1]
            )
            reports[name]["artifact_sha256"] = hashlib.sha256(
                path.read_bytes()
            ).hexdigest()
            reports[name]["artifact_bytes"] = path.stat().st_size
    for name, members in ensembles.items():
        validation_scores[name] = blend(validation_scores, members)
        reports[name]["validation_at_oof_threshold"] = evaluate(
            validation.machine_failure,
            validation_scores[name],
            reports[name]["oof"]["threshold"],
        )
    pd.DataFrame(
        {
            "source_row_index": validation.index,
            "label": validation.machine_failure,
            **validation_scores,
        }
    ).to_csv(output / "validation.csv", index=False)
    rng = np.random.default_rng(SEED)
    deltas = []
    for _ in range(500):
        indices = rng.integers(0, len(y), len(y))
        deltas.append(
            average_precision_score(y[indices], oof[winner][indices])
            - average_precision_score(y[indices], oof["rf_reference"][indices])
        )
    selected_flags = validation_scores[winner] >= reports[winner]["oof"]["threshold"]
    report = {
        "source_sha256": previous["source_sha256"],
        "seed": SEED,
        "versions": {
            "python": platform.python_version(),
            "sklearn": sklearn.__version__,
            "catboost": __import__("catboost").__version__,
        },
        "split_counts": {
            "train": len(train),
            "validation_reused": len(validation),
            "excluded_old_test": len(excluded),
        },
        "folds": previous["folds"],
        "selection": {
            "winner": winner,
            "metric": "train OOF AP",
            "before_validation": True,
        },
        "candidates": reports,
        "selected_vs_rf_oof_ap_delta_bootstrap_percentiles_descriptive": np.quantile(
            deltas, [0.025, 0.5, 0.975]
        ).tolist(),
        "anomaly_diagnostics": anomaly_comparison(train, validation, selected_flags),
        "limitations": [
            "Reused development validation; no new independent final test.",
            "OOF candidate/member/threshold search is optimistic, not nested CV.",
            "Bootstrap percentiles describe fixed OOF scores, not unbiased algorithm uncertainty.",
            "Small unequal search budgets, single seed/source; no universal best-model claim.",
            "Anomaly diagnostics use failure proxy, not verified anomaly ground truth.",
            "One-hot machine_type for all supervised models, including CatBoost; no native categorical claim.",
            "No API model promotion; no 24h forecast or physical machine history.",
        ],
    }
    (output / "report.json").write_text(
        json.dumps(report, indent=2, allow_nan=False) + "\n"
    )
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("outputs/alternatives-v1"))
    args = parser.parse_args()
    with threadpool_limits(limits=1):
        run(args.output)
