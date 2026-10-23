"""Read-only analysis of sealed study evidence; never fits an estimator."""

import argparse
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import brier_score_loss, log_loss, precision_recall_curve

from scripts.ml_study import (
    accounting,
    choose_threshold,
    completed_units,
    digest,
    inner_ranking,
    metrics,
    primary_names,
    read_json,
    verify,
    write_json,
)


def load_rows(records):
    frames = []
    for task, path in records:
        result = read_json(path / "result.json")
        if digest(path / "scores.csv") != result["scores_sha256"]:
            raise ValueError("Score artifact corruption")
        if digest(path / "task.json") != result["task_sha256"]:
            raise ValueError("Task artifact corruption")
        frame = pd.read_csv(path / "scores.csv", float_precision="round_trip")
        if frame.source_row_index.tolist() != task["held"]:
            raise ValueError("Held membership/order mismatch")
        frames.append(frame)
    combined = pd.concat(frames, ignore_index=True)
    if combined.source_row_index.duplicated().any():
        raise ValueError("OOF rows must occur exactly once")
    return combined


def cutoff(name, rows, fp=100, fn=1200):
    return (
        0.5
        if name in {"always0", "always1"}
        else choose_threshold(rows.label, rows.score, fp, fn)
    )


def reliability(rows):
    y, p = rows.label.to_numpy(), rows.score.to_numpy()
    bins = np.minimum((p * 5).astype(int), 4)
    return dict(
        brier=float(brier_score_loss(y, p)),
        log_loss=float(log_loss(y, p, labels=[0, 1])),
        bins=[
            dict(
                lower=k / 5,
                upper=(k + 1) / 5,
                n=int(np.sum(bins == k)),
                positives=int(y[bins == k].sum()),
                mean_score=float(np.mean(p[bins == k])) if np.any(bins == k) else None,
                failure_rate=float(np.mean(y[bins == k]))
                if np.any(bins == k)
                else None,
            )
            for k in range(5)
        ],
    )


def paired_bootstrap(reference, challenger, prediction_column):
    a = reference.set_index("source_row_index").sort_index()
    b = challenger.set_index("source_row_index").sort_index()
    if not a.index.equals(b.index) or not a.label.equals(b.label):
        raise ValueError("Paired bootstrap requires identical rows/labels")
    y = a.label.to_numpy()
    pa = a[prediction_column].to_numpy(dtype=bool)
    pb = b[prediction_column].to_numpy(dtype=bool)
    positives, negatives = np.flatnonzero(y), np.flatnonzero(y == 0)
    rng = np.random.default_rng(42)
    cost_delta, recall_delta = [], []
    for _ in range(2000):
        idx = np.r_[
            rng.choice(positives, len(positives)), rng.choice(negatives, len(negatives))
        ]
        yi, ai, bi = y[idx], pa[idx], pb[idx]
        cost_a = 1200 * np.sum((yi == 1) & ~ai) + 100 * np.sum((yi == 0) & ai)
        cost_b = 1200 * np.sum((yi == 1) & ~bi) + 100 * np.sum((yi == 0) & bi)
        cost_delta.append((cost_b - cost_a) * 1000 / len(idx))
        recall_delta.append(
            float(np.sum(bi & (yi == 1)) - np.sum(ai & (yi == 1))) / len(positives)
        )
    return dict(
        method=(
            "paired stratified bootstrap, 2000 resamples seed42 "
            "of FIXED OOF predictions"
        ),
        conditional_only=True,
        cost_delta_per_1000_95=np.quantile(cost_delta, [0.025, 0.975]).tolist(),
        recall_delta_95=np.quantile(recall_delta, [0.025, 0.975]).tolist(),
    )


def report(output, destination):
    manifest = verify(output)
    records = completed_units(output)
    coverage = []
    for spec in manifest["catalog"]:
        rows = []
        for path in (output / "units").glob("*/accounting.json"):
            task = read_json(path.parent / "task.json")
            if task["model"] == spec["name"]:
                a = read_json(path)
                rows.append(
                    dict(
                        phase=task["phase"],
                        fold=task["fold"],
                        status=a["status"],
                        unit=path.parent.name,
                    )
                )
        coverage.append(
            dict(
                **spec,
                units=rows,
                screening_complete=sum(
                    r["phase"] == "screening" and r["status"] == "complete"
                    for r in rows
                ),
                inner_complete=sum(
                    r["phase"] == "inner" and r["status"] == "complete" for r in rows
                ),
                outer_complete=sum(
                    r["phase"] == "outer" and r["status"] == "complete" for r in rows
                ),
            )
        )
    analysis = dict(
        manifest_sha256=digest(output / "manifest.json"),
        accounting=accounting(output),
        coverage=coverage,
        screening={},
        models={},
        anomalies={},
        selectors={},
        calibration={},
        pilot={},
        packages=[],
    )
    for spec in manifest["catalog"]:
        name = spec["name"]
        screen = [
            (t, p)
            for t, p in records
            if t["model"] == name and t["phase"] == "screening"
        ]
        if len(screen) == 3 and not spec["anomaly"]:
            rows = load_rows(screen)
            cut = cutoff(name, rows)
            analysis["screening"][name] = dict(
                threshold=cut, exploratory_metrics=metrics(rows.label, rows.score, cut)
            )
        if spec["anomaly"]:
            continue
        outer_records = [
            (t, p) for t, p in records if t["model"] == name and t["phase"] == "outer"
        ]
        if len(outer_records) != 3:
            continue
        outer_frames, fold_results = [], []
        sensitivities = {
            f"fp{fp}_fn{fn}": [] for fp in (25, 100, 300) for fn in (600, 1200, 4800)
        }
        for task, path in sorted(outer_records, key=lambda r: r[0]["fold"]):
            outer = task["fold"]
            inner = load_rows(
                [
                    (t, p)
                    for t, p in records
                    if t["model"] == name
                    and t["phase"] == "inner"
                    and t["fold"][0] == outer
                ]
            )
            rows = load_rows([(task, path)])
            cut = cutoff(name, inner)
            rows["outer"] = outer
            rows["threshold"] = cut
            rows["optimized_prediction"] = rows.score >= cut
            rows["aviso_prediction"] = rows.score >= 0.15
            outer_frames.append(rows)
            result = read_json(path / "result.json")
            fold_results.append(
                dict(
                    outer=outer,
                    threshold=cut,
                    inner_metrics=metrics(inner.label, inner.score, cut),
                    optimized=metrics(rows.label, rows.score, cut),
                    aviso=metrics(rows.label, rows.score, 0.15),
                    critica=metrics(rows.label, rows.score, 0.70),
                    resources=result,
                    accounting=read_json(path / "accounting.json"),
                )
            )
            for fp in (25, 100, 300):
                for fn in (600, 1200, 4800):
                    c = cutoff(name, inner, fp, fn)
                    m = metrics(rows.label, rows.score, c)
                    sensitivities[f"fp{fp}_fn{fn}"].append(
                        dict(
                            outer=outer,
                            threshold=c,
                            fp=m["fp"],
                            fn=m["fn"],
                            cost_euros=fp * m["fp"] + fn * m["fn"],
                        )
                    )
        all_rows = pd.concat(outer_frames, ignore_index=True)
        if len(all_rows) != 5600 or all_rows.source_row_index.duplicated().any():
            raise ValueError("Incomplete outer cohort")
        analysis["models"][name] = dict(
            optimized=metrics(all_rows.label, all_rows.score, all_rows.threshold),
            aviso=metrics(all_rows.label, all_rows.score, 0.15),
            critica=metrics(all_rows.label, all_rows.score, 0.70),
            mean_fold_ap=float(
                np.mean([r["optimized"]["average_precision"] for r in fold_results])
            ),
            folds=fold_results,
            sensitivity=sensitivities,
            reliability=reliability(all_rows),
        )
        analysis["models"][name]["_rows"] = all_rows
    names = primary_names(output, manifest)
    analysis["primary_pool"] = names
    for label, pool in [("core10", manifest["core"]), ("pool40", names)]:
        if label == "pool40" and len(pool) != 40:
            continue
        selected_rows, decisions = [], []
        for outer in range(3):
            ranking = inner_ranking(output, pool, outer)
            chosen = ranking[0]
            rows = analysis["models"][chosen["name"]]["_rows"]
            selected_rows.append(rows.loc[rows.outer == outer].copy())
            decisions.append(
                dict(
                    outer=outer,
                    selected=chosen["name"],
                    inner_threshold=chosen["threshold"],
                    inner_metrics=chosen["metrics"],
                )
            )
        rows = pd.concat(selected_rows, ignore_index=True)
        analysis["selectors"][label] = dict(
            decisions=decisions,
            optimized=metrics(rows.label, rows.score, rows.threshold),
            aviso=metrics(rows.label, rows.score, 0.15),
            critica=metrics(rows.label, rows.score, 0.70),
            meaning=(
                "Evaluates selector procedure, NOT the subsequently "
                "packaged fixed model"
            ),
        )
    # Historical AP+F2 selection rule, reconstructed within each outer-train.
    history_rows, history_decisions = [], []
    for outer in range(3):
        candidates = []
        for name in names:
            inner = load_rows(
                [
                    (t, p)
                    for t, p in records
                    if t["model"] == name
                    and t["phase"] == "inner"
                    and t["fold"][0] == outer
                ]
            )
            p, r, thresholds = precision_recall_curve(inner.label, inner.score)
            f2 = 5 * p[:-1] * r[:-1] / np.maximum(4 * p[:-1] + r[:-1], 1e-15)
            cut = (
                0.5
                if name in {"always0", "always1"}
                else float(thresholds[np.argmax(f2)])
            )
            candidates.append(
                (metrics(inner.label, inner.score, cut)["average_precision"], name, cut)
            )
        _, name, cut = max(candidates, key=lambda r: r[0])
        rows = analysis["models"][name]["_rows"]
        rows = rows.loc[rows.outer == outer].copy()
        rows["threshold"] = cut
        history_rows.append(rows)
        history_decisions.append(dict(outer=outer, name=name, threshold=cut))
    rows = pd.concat(history_rows)
    analysis["selectors"]["historical_ap_f2"] = dict(
        decisions=history_decisions,
        optimized=metrics(rows.label, rows.score, rows.threshold),
    )
    reference = analysis["models"]["rf_reference"]["_rows"]
    for name, result in analysis["models"].items():
        if name != "rf_reference":
            result["bootstrap_A"] = paired_bootstrap(
                reference, result["_rows"], "optimized_prediction"
            )
            result["bootstrap_B"] = paired_bootstrap(
                reference, result["_rows"], "aviso_prediction"
            )
    for spec in manifest["catalog"]:
        if not spec["anomaly"]:
            continue
        name = spec["name"]
        frames, fold_stats = [], []
        for outer in range(3):
            inner_records = [
                (t, p)
                for t, p in records
                if t["model"] == name
                and t["phase"] == "inner"
                and t["fold"][0] == outer
            ]
            outer_records = [
                (t, p)
                for t, p in records
                if t["model"] == name and t["phase"] == "outer" and t["fold"] == outer
            ]
            if len(inner_records) != 3 or len(outer_records) != 1:
                continue
            inner = load_rows(inner_records)
            normal = inner.loc[inner.label == 0]
            cut = float(np.quantile(normal.score, 0.99, method="higher"))
            rows = load_rows(outer_records)
            rows = rows.merge(
                reference[["source_row_index", "aviso_prediction"]],
                on="source_row_index",
                validate="one_to_one",
            )
            rows["flag"] = rows.score >= cut
            frames.append(rows)
            fold_stats.append(
                dict(
                    outer=outer,
                    threshold=cut,
                    normal_inner_rows=len(normal),
                    normal_inner_flags=int(np.sum(normal.score >= cut)),
                )
            )
        if len(frames) == 3:
            rows = pd.concat(frames)
            analysis["anomalies"][name] = dict(
                n=len(rows),
                positive_proxy=int(rows.label.sum()),
                total_flags=int(rows.flag.sum()),
                failure_labels_flagged=int(np.sum(rows.flag & (rows.label == 1))),
                normal_proxy_flags=int(np.sum(rows.flag & (rows.label == 0))),
                rf_fn_recovered=int(
                    np.sum(rows.flag & ~rows.aviso_prediction & (rows.label == 1))
                ),
                false_alarms_added=int(
                    np.sum(rows.flag & ~rows.aviso_prediction & (rows.label == 0))
                ),
                rf_fn_denominator=int(
                    np.sum(~rows.aviso_prediction & (rows.label == 1))
                ),
                rf_normal_no_alert_denominator=int(
                    np.sum(~rows.aviso_prediction & (rows.label == 0))
                ),
                folds=fold_stats,
                meaning=(
                    "Failure-label diagnostic only; no anomaly ground truth; "
                    "never suppress RF"
                ),
            )
    for name in manifest["pilot"]["models"]:
        rows = []
        score_records = {}
        for task, path in records:
            if task["phase"] == "pilot" and task["model"] == name:
                result = read_json(path / "result.json")
                account = read_json(path / "accounting.json")
                scores = load_rows([(task, path)])
                score_records[(task["device"], task["fold"])] = scores
                rows.append(
                    dict(
                        device=task["device"],
                        repeat=task["fold"],
                        resources=result,
                        accounting=account,
                        metrics=metrics(scores.label, scores.score, 0.15),
                    )
                )
        comparisons = []
        for repeat in range(manifest["pilot"]["repeats"]):
            if ("cpu", repeat) in score_records and ("cuda", repeat) in score_records:
                a, b = score_records[("cpu", repeat)], score_records[("cuda", repeat)]
                comparisons.append(
                    dict(
                        repeat=repeat,
                        max_score_difference=float(np.max(np.abs(a.score - b.score))),
                        mean_score_difference=float(np.mean(np.abs(a.score - b.score))),
                        aviso_disagreements=int(
                            np.sum((a.score >= 0.15) != (b.score >= 0.15))
                        ),
                    )
                )
        analysis["pilot"][name] = dict(runs=rows, comparisons=comparisons)
    for outer in range(3):
        variants = []
        for task, path in records:
            if task["phase"] != "calibration_outer" or task["fold"] != outer:
                continue
            name, method = task["model"], task["calibration"]
            inner = load_rows(
                [
                    (t, p)
                    for t, p in records
                    if t["phase"] == "calibration_inner"
                    and t["model"] == name
                    and t["calibration"] == method
                    and t["fold"][0] == outer
                ]
            )
            rows = load_rows([(task, path)])
            cut = cutoff(name, inner)
            variants.append(
                dict(
                    name=name,
                    method=method,
                    threshold=cut,
                    inner=metrics(inner.label, inner.score, cut),
                    outer=metrics(rows.label, rows.score, cut),
                    aviso=metrics(rows.label, rows.score, 0.15),
                    reliability=reliability(rows),
                    support=read_json(path / "result.json"),
                )
            )
        if variants:
            eligible = [r for r in variants if r["inner"]["recall"] >= 0.76]
            chosen = min(
                eligible,
                key=lambda r: (
                    r["inner"]["cost_per_1000"],
                    r["inner"]["fn"],
                    r["name"],
                    r["method"],
                ),
            )
            analysis["calibration"][str(outer)] = dict(
                variants=variants,
                selected=dict(
                    name=chosen["name"],
                    method=chosen["method"],
                    threshold=chosen["threshold"],
                    outer=chosen["outer"],
                ),
            )
    for task, path in records:
        if task["phase"] == "package":
            analysis["packages"].append(
                dict(
                    model=task["model"],
                    threshold=task["threshold"],
                    fit_rows=len(task["fit"]),
                    probe=(
                        "32 TRAINING rows, reload/latency ONLY; "
                        "no generalization metrics"
                    ),
                    resources=read_json(path / "result.json"),
                    unit=path.name,
                )
            )
    analysis["fixed_choice_from_5600_inner"] = inner_ranking(output, names)[0]
    destination.mkdir(parents=True, exist_ok=False)
    for name, result in analysis["models"].items():
        result.pop("_rows").to_csv(destination / (name + "-outer.csv"), index=False)
    write_json(destination / "summary.json", analysis)
    print(str(destination / "summary.json"))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--destination", type=Path, required=True)
    args = parser.parse_args()
    report(args.output, args.destination)
