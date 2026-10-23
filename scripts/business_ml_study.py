"""Additional user-supplied business matrix; read saved scores, never fit."""

import argparse
from pathlib import Path

import matplotlib
import numpy as np
import pandas as pd

from scripts.ml_study import (
    choose_threshold,
    completed_units,
    digest,
    metrics,
    read_json,
    write_json,
)
from scripts.report_ml_study import load_rows, verify_evidence

matplotlib.use("Agg")


def economic_metrics(rows, cut, costs):
    result = metrics(rows.label, rows.score, cut)
    total = sum(result[k] * costs[k] for k in ("tp", "fn", "fp", "tn"))
    result["cost_total_eur"] = total
    result["cost_per_1000"] = total * 1000 / len(rows)
    baseline = result["positives"] * costs["fn"]
    result["no_alert_cost_total_eur"] = baseline
    result["hypothetical_saving_vs_no_alert_eur"] = baseline - total
    return result


def economic_cut(rows, name, costs):
    if name in {"always0", "always1"}:
        return 0.5
    # TP cost matters: with fixed positive support TP=P-FN.
    return choose_threshold(
        rows.label,
        rows.score,
        costs["fp"] - costs["tn"],
        costs["fn"] - costs["tp"],
    )


def curve(rows, costs):
    order = np.argsort(-rows.score.to_numpy(), kind="stable")
    y = rows.label.to_numpy()[order]
    score = rows.score.to_numpy()[order]
    ends = np.r_[np.flatnonzero(np.diff(score)), len(score) - 1]
    tp = np.cumsum(y)[ends]
    fp = np.cumsum(1 - y)[ends]
    fn, tn = y.sum() - tp, len(y) - y.sum() - fp
    return pd.DataFrame(
        {
            "threshold": score[ends],
            "tp": tp,
            "fn": fn,
            "fp": fp,
            "tn": tn,
            "recall": tp / y.sum(),
            "cost_per_1000": (
                costs["tp"] * tp
                + costs["fn"] * fn
                + costs["fp"] * fp
                + costs["tn"] * tn
            )
            * 1000
            / len(y),
        }
    )


def analyze(root, config_path, destination):
    manifest = verify_evidence(root)
    config = read_json(config_path)
    costs = config["cost_eur"]
    if config["minimum_inner_recall"] != 0.76:
        raise ValueError("This addendum preserves the original recall constraint")
    destination.mkdir(exist_ok=False)
    records = completed_units(root)
    names = [s["name"] for s in manifest["catalog"] if not s["anomaly"]]
    cache = {}

    def rows_for(name, phase, outer=None, method=None):
        key = name, phase, outer, method
        if key not in cache:
            selected = [
                (t, p)
                for t, p in records
                if t["model"] == name
                and t["phase"] == phase
                and (
                    outer is None
                    or (
                        t["fold"][0] == outer
                        if isinstance(t["fold"], list)
                        else t["fold"] == outer
                    )
                )
                and (method is None or t.get("calibration") == method)
            ]
            expected = 3 if phase in {"inner", "screening", "calibration_inner"} else 1
            if len(selected) != expected:
                raise ValueError(f"Incomplete scores: {key}")
            cache[key] = (load_rows(selected), selected)
        return cache[key]

    def rank(pool, outer=None):
        ranked = []
        for name in pool:
            rows, selected = rows_for(
                name, "screening" if outer is None else "inner", outer
            )
            cut = economic_cut(rows, name, costs)
            m = economic_metrics(rows, cut, costs)
            latency = sum(
                read_json(p / "result.json")["prediction_seconds"] for _, p in selected
            ) / len(rows)
            if m["recall"] >= 0.76:
                ranked.append(
                    {"name": name, "threshold": cut, "metrics": m, "latency": latency}
                )
        return sorted(
            ranked,
            key=lambda r: (
                r["metrics"]["cost_per_1000"],
                r["metrics"]["fn"],
                r["latency"],
                names.index(r["name"]),
            ),
        )

    models, outer_rows = {}, {}
    for name in names:
        pieces, decisions = [], []
        for outer in range(3):
            inner, _ = rows_for(name, "inner", outer)
            cut = economic_cut(inner, name, costs)
            held, _ = rows_for(name, "outer", outer)
            held = held.copy()
            held["threshold"] = cut
            held["outer"] = outer
            pieces.append(held)
            decisions.append(
                {
                    "outer": outer,
                    "threshold": cut,
                    "inner": economic_metrics(inner, cut, costs),
                }
            )
        rows = pd.concat(pieces, ignore_index=True)
        if len(rows) != 5600 or rows.source_row_index.duplicated().any():
            raise ValueError("Outer coverage mismatch")
        rows.to_csv(destination / (name + "-outer.csv"), index=False)
        outer_rows[name] = rows
        models[name] = {
            "A": economic_metrics(rows, rows.threshold, costs),
            "B": economic_metrics(rows, 0.15, costs),
            "C": economic_metrics(rows, 0.70, costs),
            "folds": decisions,
        }
    selectors = {}
    for label, pool in [("core10", manifest["core"]), ("pool40", names)]:
        pieces, decisions = [], []
        for outer in range(3):
            best = rank(pool, outer)[0]
            decisions.append({"outer": outer, **best})
            rows = outer_rows[best["name"]]
            pieces.append(rows.loc[rows.outer == outer])
        rows = pd.concat(pieces, ignore_index=True)
        rows.to_csv(destination / (label + "-outer.csv"), index=False)
        selectors[label] = {
            "decisions": decisions,
            "A": economic_metrics(rows, rows.threshold, costs),
            "B": economic_metrics(rows, 0.15, costs),
        }
    fixed_rank = rank(names)
    # Existing calibration finalists are conditional on the original matrix.
    calibration_rows, calibration_decisions = [], []
    for outer in range(3):
        variants = []
        for task, _ in records:
            if task["phase"] != "calibration_outer" or task["fold"] != outer:
                continue
            name, method = task["model"], task["calibration"]
            inner, selected = rows_for(name, "calibration_inner", outer, method)
            held, _ = rows_for(name, "calibration_outer", outer, method)
            cut = economic_cut(inner, name, costs)
            m = economic_metrics(inner, cut, costs)
            latency = sum(
                read_json(p / "result.json")["prediction_seconds"] for _, p in selected
            ) / len(inner)
            if m["recall"] >= 0.76:
                variants.append(
                    (
                        m["cost_per_1000"],
                        m["fn"],
                        latency,
                        names.index(name),
                        manifest["optional"]["calibration"]["methods"].index(method),
                        name,
                        method,
                        cut,
                        held,
                    )
                )
        best = min(variants, key=lambda r: r[:5])
        rows = best[8].copy()
        rows["threshold"] = best[7]
        calibration_rows.append(rows)
        calibration_decisions.append(
            {"outer": outer, "name": best[5], "method": best[6], "threshold": best[7]}
        )
    calibrated = pd.concat(calibration_rows, ignore_index=True)
    calibrated.to_csv(destination / "restricted-calibration-outer.csv", index=False)
    summary = {
        "config_sha256": digest(config_path),
        "config": config,
        "manifest_sha256": digest(root / "manifest.json"),
        "models": models,
        "selectors": selectors,
        "fixed_specification_ranking": fixed_rank,
        "fixed_specification_refit_performed": False,
        "restricted_calibration": {
            "decisions": calibration_decisions,
            "A": economic_metrics(calibrated, calibrated.threshold, costs),
            "B": economic_metrics(calibrated, 0.15, costs),
        },
        "marginal_recovered_failure_value_eur": costs["fn"] - costs["tp"],
        "marginal_added_false_alarm_cost_eur": costs["fp"] - costs["tn"],
        "extra_fp_per_extra_tp_break_even": (costs["fn"] - costs["tp"])
        / (costs["fp"] - costs["tn"]),
    }
    # Direct scalar arithmetic independent of vectorized threshold selection.
    for name, rows in outer_rows.items():
        for policy, cuts in [
            ("A", rows.threshold),
            ("B", [0.15] * len(rows)),
            ("C", [0.70] * len(rows)),
        ]:
            total = 0
            for y, score, cut in zip(rows.label, rows.score, cuts, strict=True):
                case = (
                    "tp"
                    if y and score >= cut
                    else "fn"
                    if y
                    else ("fp" if score >= cut else "tn")
                )
                total += costs[case]
            if total != models[name][policy]["cost_total_eur"]:
                raise ValueError("Independent four-cell economic arithmetic failed")
    summary["independent_4_cell_arithmetic"] = "pass: 40 models × 3 policies"
    write_json(destination / "business-summary.json", summary)
    plot_curves(root, destination, names, rows_for, costs)
    return summary


def plot_curves(root, destination, names, rows_for, costs):
    import matplotlib.pyplot as plt

    fig, axes = plt.subplots(1, 2, figsize=(12, 4.8), layout="constrained")
    for name, label in [
        ("rf_reference", "RF"),
        ("gb_depth3", "GB depth3"),
        ("cart_depth5", "CART depth5"),
    ]:
        if name not in names:
            raise ValueError("Expected reference not found")
        rows, _ = rows_for(name, "screening")
        points = curve(rows, costs)
        points.to_csv(destination / (name + "-development-curve.csv"), index=False)
        cut = economic_cut(rows, name, costs)
        m = economic_metrics(rows, cut, costs)
        shown = points.loc[points.recall >= 0.70]
        axes[0].plot(shown.threshold, shown.cost_per_1000, label=label)
        axes[1].plot(shown.recall, shown.cost_per_1000, label=label)
        axes[0].scatter([cut], [m["cost_per_1000"]], s=28)
        axes[1].scatter([m["recall"]], [m["cost_per_1000"]], s=28)
    axes[0].set(xlabel="Umbral", ylabel="Coste docente (€ / 1.000 eventos)")
    axes[1].set(xlabel="Recall", ylabel="Coste docente (€ / 1.000 eventos)")
    for ax in axes:
        ax.grid(alpha=0.25)
        ax.legend()
    axes[1].axvline(0.76, color="gray", linestyle="--", linewidth=1)
    fig.suptitle(
        "Curvas de ajuste OOF train (no evaluación final): FN 5.000 / FP 200 / TP 300 €"
    )
    fig.savefig(destination / "business-cost-curves.png", dpi=160)
    fig.savefig(destination / "business-cost-curves.svg")
    plt.close(fig)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--destination", type=Path, required=True)
    args = parser.parse_args()
    summary = analyze(args.root, args.config, args.destination)
    print(
        {
            "selected": [
                r["name"] for r in summary["selectors"]["pool40"]["decisions"]
            ],
            "fixed_specification": summary["fixed_specification_ranking"][0]["name"],
        }
    )


if __name__ == "__main__":
    main()
