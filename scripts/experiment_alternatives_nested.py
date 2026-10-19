"""Nested audit of the declared model pool, using original training rows only."""

import argparse
import json
from pathlib import Path

import pandas as pd
from sklearn.base import clone
from sklearn.metrics import average_precision_score, roc_auc_score
from sklearn.model_selection import StratifiedKFold
from threadpoolctl import threadpool_limits

from scoring.preparation import SEED, split_development
from scripts.experiment_alternatives import blend, candidates, fit_oof
from scripts.experiment_rf import evaluate, threshold


def nested_compare(train, pool, outer_splits=3, inner_splits=3):
    rows, records = [], []
    for outer, (fit, held) in enumerate(
        StratifiedKFold(outer_splits, shuffle=True, random_state=SEED + 1).split(
            train, train.machine_failure
        )
    ):
        development = train.iloc[fit]
        evaluation = train.iloc[held]
        inner = list(
            StratifiedKFold(inner_splits, shuffle=True, random_state=SEED).split(
                development, development.machine_failure
            )
        )
        scores = {
            name: fit_oof(model, development, inner) for name, model in pool.items()
        }
        aps = {
            name: float(average_precision_score(development.machine_failure, p))
            for name, p in scores.items()
        }
        ensemble = None
        non_rf = [n for n in pool if not n.startswith("rf_")]
        if non_rf and "rf_reference" in pool:
            challenger = max(non_rf, key=lambda n: aps[n])
            ensemble = ["rf_reference", challenger]
            scores["rf_challenger_mean"] = blend(scores, ensemble)
            aps["rf_challenger_mean"] = float(
                average_precision_score(
                    development.machine_failure, scores["rf_challenger_mean"]
                )
            )
        top3 = None
        if len(pool) >= 3:
            top3 = sorted(pool, key=lambda n: aps[n], reverse=True)[:3]
            scores["top3_mean"] = blend(scores, top3)
            aps["top3_mean"] = float(
                average_precision_score(
                    development.machine_failure, scores["top3_mean"]
                )
            )
        selected = max(aps, key=aps.get)
        cutoffs = {
            name: threshold(development.machine_failure, score)
            for name, score in scores.items()
        }
        held_scores = {
            name: clone(model)
            .fit(development, development.machine_failure)
            .predict_proba(evaluation)[:, 1]
            for name, model in pool.items()
        }
        if ensemble:
            held_scores["rf_challenger_mean"] = blend(held_scores, ensemble)
        if top3:
            held_scores["top3_mean"] = blend(held_scores, top3)
        for name, p in held_scores.items():
            rows.extend(
                {
                    "source_row_index": int(index),
                    "outer_fold": outer,
                    "model": name,
                    "label": int(label),
                    "score": float(score),
                    "threshold": cutoffs[name],
                    "prediction": bool(score >= cutoffs[name]),
                }
                for index, label, score in zip(
                    evaluation.index, evaluation.machine_failure, p, strict=True
                )
            )
        p = held_scores[selected]
        rows.extend(
            {
                "source_row_index": int(index),
                "outer_fold": outer,
                "model": "nested_selected_strategy",
                "label": int(label),
                "score": float(score),
                "threshold": cutoffs[selected],
                "prediction": bool(score >= cutoffs[selected]),
            }
            for index, label, score in zip(
                evaluation.index, evaluation.machine_failure, p, strict=True
            )
        )
        records.append(
            {
                "outer": outer,
                "fit": development.index.tolist(),
                "held": evaluation.index.tolist(),
                "selected": selected,
                "inner_ap": aps,
                "inner_thresholds": cutoffs,
                "ensemble_members": {"rf_challenger_mean": ensemble, "top3_mean": top3},
                "inner_folds": [
                    {
                        "fit": development.index[a].tolist(),
                        "held": development.index[b].tolist(),
                    }
                    for a, b in inner
                ],
            }
        )
        print(
            "outer",
            outer,
            "selected",
            selected,
            "inner AP",
            round(aps[selected], 6),
            flush=True,
        )
    predictions = pd.DataFrame(rows)
    results = {}
    for name, data in predictions.groupby("model"):
        if data.source_row_index.duplicated().any() or len(data) != len(train):
            raise ValueError("Outer evaluation must cover each training row once")
        metrics = evaluate(data.label, data.prediction.to_numpy(dtype=float), 0.5)
        metrics["threshold"] = (
            "F2 cutoff selected separately in each outer-training inner CV"
        )
        metrics["average_precision"] = float(
            average_precision_score(data.label, data.score)
        )
        metrics["roc_auc"] = float(roc_auc_score(data.label, data.score))
        results[name] = metrics
    return {
        "shortlist": list(pool),
        "seed_outer": SEED + 1,
        "seed_inner": SEED,
        "outer_folds": records,
        "outer_metrics": results,
        "limitations": [
            "Audit of declared candidate pool and selection strategy; no further tuning on outer-held rows.",
            "No validation or excluded-test rows used; source remains synthetic development data.",
            "Pooled AP mixes outer-fitted scores; calibration varies across folds/models.",
            "No independent final evaluation or industrial/temporal prediction guarantee.",
        ],
    }, predictions


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output", type=Path, default=Path("outputs/alternatives-nested-v2")
    )
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError("Use a fresh output directory")
    train, _, _ = split_development(pd.read_csv("data/ai4i2020_train.csv"))
    all_models = candidates()
    with threadpool_limits(limits=1):
        report, scores = nested_compare(train, all_models)
    args.output.mkdir(parents=True)
    (args.output / "report.json").write_text(
        json.dumps(report, indent=2, allow_nan=False) + "\n"
    )
    scores.to_csv(args.output / "outer_predictions.csv", index=False)
