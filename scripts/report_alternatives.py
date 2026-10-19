"""Export traceable compact comparison and charts without fitting/selecting on validation."""

import hashlib
import json
import time
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.metrics import brier_score_loss

from scripts.experiment_rf import evaluate


def cost_cutoff(y, scores, fp_cost, fn_cost):
    y = np.asarray(y, dtype=bool)
    order = np.argsort(-scores, kind="stable")
    ranked = np.asarray(scores)[order]
    ends = np.r_[np.flatnonzero(np.diff(ranked)), len(ranked) - 1]
    tp = np.cumsum(y[order])[ends]
    fp = np.cumsum(~y[order])[ends]
    costs = np.r_[y.sum() * fn_cost, fp * fp_cost + (y.sum() - tp) * fn_cost]
    limits = np.r_[np.nextafter(ranked[0], np.inf), ranked[ends]]
    return float(limits[np.argmin(costs)])


def performance_diagnostic(root, broad):
    from scoring.preparation import split_development

    _, validation, _ = split_development(pd.read_csv("data/ai4i2020_train.csv"))
    members = broad["candidates"]["top3_mean"]["members"]
    names = set(members + ["rf_reference", "gradient_depth3"])
    models = {}
    for name in names:
        path = root / f"{name}.pkl"
        if (
            hashlib.sha256(path.read_bytes()).hexdigest()
            != broad["candidates"][name]["artifact_sha256"]
        ):
            raise ValueError("Own artifact hash changed")
        models[name] = joblib.load(path)
    result = {}
    for name, group in {
        "rf_reference": ["rf_reference"],
        "gradient_depth3": ["gradient_depth3"],
        "top3_mean": members,
    }.items():
        durations = []
        for i in range(31):
            row = validation.iloc[[i]]
            start = time.perf_counter()
            np.mean([models[n].predict_proba(row)[:, 1] for n in group], axis=0)
            if i:
                durations.append((time.perf_counter() - start) * 1000)
        result[name] = {
            "p50_ms": float(np.median(durations)),
            "p95_ms": float(np.quantile(durations, 0.95)),
            "total_artifact_bytes": sum(
                (root / f"{n}.pkl").stat().st_size for n in group
            ),
        }
    return {
        "meaning": "Own verified models, warm sequential single-row in-process; no HTTP or load SLA",
        "repetitions": 30,
        "models": result,
    }


def run():
    root = Path("outputs/alternatives-v1")
    broad_path = root / "report.json"
    nested_path = Path("outputs/alternatives-nested-v2/report.json")
    broad = json.loads(broad_path.read_text())
    nested = json.loads(nested_path.read_text())
    scores = pd.read_csv(root / "validation.csv", float_precision="round_trip")
    original = json.loads(Path("outputs/cg08/report.json").read_text())
    expected_train = set(original["splits"]["train"])
    held = []
    for fold in nested["outer_folds"]:
        if (
            set(fold["fit"]) & set(fold["held"])
            or set(fold["fit"]) | set(fold["held"]) != expected_train
        ):
            raise ValueError("Nested split differs from original training membership")
        held.extend(fold["held"])
    if len(held) != len(set(held)) or set(held) != expected_train:
        raise ValueError("Nested held rows are not an exact partition")
    diagnostics = {}
    for name in [
        "rf_reference",
        "gradient_depth3",
        "top3_mean",
        "rf_challenger_mean",
        "cat_depth4_None",
    ]:
        candidate = broad["candidates"][name]
        if (
            evaluate(scores.label, scores[name], candidate["oof"]["threshold"])
            != candidate["validation_at_oof_threshold"]
        ):
            raise ValueError(
                "Validation CSV does not reproduce recorded metrics exactly"
            )
        oof = (
            pd.read_csv(root / f"{name}_oof.csv", float_precision="round_trip")
            if candidate["kind"] == "individual"
            else None
        )
        if oof is None:
            members = candidate["members"]
            tables = [
                pd.read_csv(root / f"{n}_oof.csv", float_precision="round_trip")
                for n in members
            ]
            if any(
                not t.source_row_index.equals(tables[0].source_row_index)
                for t in tables
            ):
                raise ValueError("OOF members are not aligned")
            oof = tables[0].copy()
            oof["score"] = np.mean([t.score for t in tables], axis=0)
        cost_scenarios = []
        for fp_eur in [25, 100, 300]:
            for fn_eur in [600, 1200, 4800]:
                cutoff = cost_cutoff(oof.label, oof.score.to_numpy(), fp_eur, fn_eur)
                metrics = evaluate(scores.label, scores[name], cutoff)
                cost_scenarios.append(
                    {
                        "fp_eur": fp_eur,
                        "fn_eur": fn_eur,
                        "threshold_selected_on_train_oof": cutoff,
                        "validation": metrics,
                        "hypothetical_validation_cost_eur": fp_eur
                        * metrics["confusion_matrix"][0][1]
                        + fn_eur * metrics["confusion_matrix"][1][0],
                    }
                )
        diagnostic = {
            "cost_scenarios_oof_tuning_not_nested": cost_scenarios,
            "validation_at_oof_threshold": candidate["validation_at_oof_threshold"],
            "validation_brier_diagnostic": float(
                brier_score_loss(scores.label, scores[name])
            ),
            "validation_at_recall_floor_thresholds_chosen_in_oof": {
                floor: evaluate(scores.label, scores[name], point["threshold"])
                for floor, point in candidate["operating_points_oof"].items()
            },
        }
        _tn, fp = candidate["validation_at_oof_threshold"]["confusion_matrix"][0]
        fn, _tp = candidate["validation_at_oof_threshold"]["confusion_matrix"][1]
        diagnostic["hypothetical_cost_at_100_eur_fp_1200_eur_fn"] = 100 * fp + 1200 * fn
        diagnostics[name] = diagnostic
    historical = evaluate(
        scores.label,
        scores.rf_reference,
        original["validation_tuning_metrics"]["threshold"],
    )
    compact = {
        "source_sha256": broad["source_sha256"],
        "versions": broad["versions"],
        "seed": broad["seed"],
        "split_counts": broad["split_counts"],
        "selection": broad["selection"],
        "candidate_count": len(broad["candidates"]),
        "candidates": broad["candidates"],
        "anomaly_diagnostics": broad["anomaly_diagnostics"],
        "ap_delta_bootstrap_descriptive": broad[
            "selected_vs_rf_oof_ap_delta_bootstrap_percentiles_descriptive"
        ],
        "nested": {
            "candidate_pool": nested["shortlist"],
            "outer_metrics": nested["outer_metrics"],
            "fold_selections": [
                {key: fold[key] for key in ["outer", "selected", "ensemble_members"]}
                for fold in nested["outer_folds"]
            ],
            "limitations": nested["limitations"],
        },
        "validation_diagnostics": diagnostics,
        "historical_rf_validation_tuned_threshold_not_fair_new_selection": historical,
        "evidence_sha256": {
            str(path): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in [
                broad_path,
                nested_path,
                root / "validation.csv",
                Path("outputs/alternatives-nested-v2/outer_predictions.csv"),
            ]
        },
        "limitations": broad["limitations"],
        "performance_diagnostic": performance_diagnostic(root, broad),
        "api_promoted": False,
    }
    destination = Path("docs/evidence/CG08_alternatives.json")
    destination.write_text(json.dumps(compact, indent=2, allow_nan=False) + "\n")
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    ordered = sorted(
        broad["candidates"],
        key=lambda n: broad["candidates"][n]["oof"]["average_precision"],
    )
    fig, axes = plt.subplots(1, 2, figsize=(15, 8), layout="constrained")
    values = [broad["candidates"][n]["oof"]["average_precision"] for n in ordered]
    axes[0].barh(
        ordered,
        values,
        color=["#19766a" if n == "rf_reference" else "#426ab2" for n in ordered],
    )
    axes[0].set(
        xlim=(0, 1),
        xlabel="Average precision — original train OOF (selection biased)",
        title="Broad comparison, identical folds",
    )
    nested_names = [
        "rf_reference",
        "gradient_depth3",
        "nested_selected_strategy",
    ]
    for index, name in enumerate(nested_names):
        m = nested["outer_metrics"][name]
        axes[1].barh(
            index,
            m["average_precision"],
            color="#19766a" if name == "rf_reference" else "#426ab2",
        )
        axes[1].text(
            0.02,
            index,
            f"AP {m['average_precision']:.3f}; FN {m['confusion_matrix'][1][0]}, FP {m['confusion_matrix'][0][1]}",
            va="center",
            fontsize=9,
            color="white",
        )
    axes[1].set(
        yticks=np.arange(len(nested_names)),
        yticklabels=nested_names,
        xlim=(0, 1),
        xlabel="AP on outer-held rows; thresholds chosen inside inner CV",
        title="Nested CV audit on 5,600 original training rows",
    )
    fig.suptitle(
        "AI4I development evidence — no new independent final test", fontsize=15
    )
    fig.savefig("docs/evidence/CG08_alternatives.png", dpi=140)
    plt.close(fig)
    print("Exported alternatives metrics and actual-results chart")


if __name__ == "__main__":
    run()
