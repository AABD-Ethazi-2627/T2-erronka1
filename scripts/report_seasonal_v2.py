"""Reconcile synthetic forecasts, onsets and learning curves; no industrial claims."""

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd


def event_audit(frame, predictions, cutoff):
    if predictions.duplicated(["machine_id", "timestamp"]).any():
        raise ValueError("Duplicate forecast identity")
    eligible, detected, leads = 0, 0, []
    alerts = predictions.score.ge(cutoff)
    for machine, source in frame.groupby("machine_id"):
        forecasts = predictions.loc[predictions.machine_id.eq(machine)]
        for onset in source.loc[source.simulated_fault_onset.eq(1), "timestamp"]:
            previous = forecasts.loc[
                (forecasts.timestamp >= onset - pd.Timedelta(hours=24))
                & (forecasts.timestamp < onset)
            ]
            if len(previous) != 24:
                continue
            eligible += 1
            alarm = previous.loc[previous.score.ge(cutoff)]
            if not alarm.empty:
                detected += 1
                leads.append((onset - alarm.timestamp.min()).total_seconds() / 3600)
    return {
        "eligible_onsets": eligible,
        "detected_onsets": detected,
        "event_recall": detected / eligible if eligible else None,
        "median_first_alert_lead_hours": float(np.median(leads)) if leads else None,
        "alert_hours": int(alerts.sum()),
        "forecast_hours": len(predictions),
        "alert_hour_fraction": float(alerts.mean()),
        "meaning": "Onsets with full 24h forecast coverage only; overlapping positive hours are not independent failures",
    }


def run(root=Path("outputs/seasonal-v2")):
    source = root / "report.json"
    report = json.loads(source.read_text())
    for name, summary in report["datasets"].items():
        path = root / f"{name}.parquet"
        if hashlib.sha256(path.read_bytes()).hexdigest() != summary["sha256"]:
            raise ValueError("Synthetic data differs from recorded source")
    selected = report["selection"]["selected_by_validation_ap"]
    scores = pd.read_parquet(root / "evaluation_predictions.parquet")
    forecasts = scores[["timestamp", "machine_id", selected]].rename(
        columns={selected: "score"}
    )
    data = pd.read_parquet(root / "evaluation.parquet")
    cutoff = report["results"][selected]["threshold_from_validation_f2"]
    report["code_sha256"] = {
        str(path): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in [
            Path("scripts/seasonal_v2.py"),
            Path("scripts/train_seasonal_v2.py"),
            Path("scoring/preparation.py"),
        ]
    }
    report["event_audit_selected"] = event_audit(data, forecasts, cutoff)
    report["evidence_sha256"] = {
        "full_report": hashlib.sha256(source.read_bytes()).hexdigest(),
        "evaluation_predictions": hashlib.sha256(
            (root / "evaluation_predictions.parquet").read_bytes()
        ).hexdigest(),
        "selection_before_evaluation": hashlib.sha256(
            (root / "selection_before_evaluation.json").read_bytes()
        ).hexdigest(),
    }
    destination = Path("docs/evidence/CG11_seasonal_v2.json")
    destination.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, axes = plt.subplots(1, 3, figsize=(16, 5), layout="constrained")
    for kind, label in [
        ("sensors", "Sensors"),
        ("history", "Sensors + past"),
        ("seasonal", "Sensors + past + calendar"),
    ]:
        rows = [r for r in report["results"].values() if r["kind"] == kind]
        axes[0].plot(
            [r["training_rows"] for r in rows],
            [r["evaluation_synthetic"]["average_precision"] for r in rows],
            marker="o",
            label=label,
        )
    ref = report["references"]["constant_training_prevalence"]["average_precision"]
    axes[0].axhline(
        ref, color="gray", linestyle="--", label="Positive-window prevalence"
    )
    axes[0].set(
        xlabel="Synthetic train rows (correlated hourly readings)",
        ylabel="AP on fixed synthetic 2025",
        title="More rows need not improve every model",
    )
    axes[0].legend(fontsize=8)
    seasons = ["winter", "spring", "summer", "autumn"]
    labels = ["Winter", "Spring", "Summer", "Autumn"]
    grouped = report["results"][selected]["evaluation_synthetic"]["by_season"]
    axes[1].bar(
        labels, [grouped[s]["average_precision"] for s in seasons], color="#426ab2"
    )
    axes[1].scatter(
        labels,
        [grouped[s]["positive_windows"] / grouped[s]["rows"] for s in seasons],
        color="#bd651c",
        label="Positive-window prevalence",
    )
    axes[1].set(ylabel="Average precision", title=f"Selected: {selected}")
    axes[1].legend(fontsize=8)
    monthly = data.groupby(data.timestamp.dt.month).agg(air=("air_temp_K", "mean"))
    axes[2].plot(monthly.index, monthly.air, marker="o", color="#19766a")
    axes[2].set(
        xlabel="Month",
        ylabel="Simulated ambient temperature (K)",
        title="Invented northern indoor seasonal cycle",
        xticks=range(1, 13),
    )
    fig.suptitle(
        "Synthetic scenario only — not observed industrial performance", fontsize=14
    )
    fig.savefig("docs/evidence/CG11_seasonal_v2.png", dpi=140)
    plt.close(fig)
    print("Exported seasonal evidence and onsets audit")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("outputs/seasonal-v2"))
    run(parser.parse_args().root)
