"Validation diagnostics and hypothetical cost sensitivity; never industrial savings."

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.metrics import precision_recall_curve, roc_curve

from scoring.alert_policy import cost
from scripts.experiment_rf import evaluate


def run():
    root = Path("docs/evidence")
    # Preserve equality at a saved threshold (notably source row 7763).
    data = pd.read_csv("outputs/cg08/validation.csv", float_precision="round_trip")
    report = json.loads(Path("outputs/cg08/report.json").read_text())
    y, p = data.label.to_numpy(), data.rf_score.to_numpy()
    tuned = report["validation_tuning_metrics"]["threshold"]
    policies = {str(t): evaluate(y, p, t) for t in [0.15, 0.7, tuned]}
    scenarios = []
    for inspection in [25, 100, 300]:
        for hours in [0.5, 1, 4]:
            for name, m in policies.items():
                _tn, fp = m["confusion_matrix"][0]
                fn, _tp = m["confusion_matrix"][1]
                scenarios.append(
                    {
                        "threshold": name,
                        "inspection_eur": inspection,
                        "downtime_hours": hours,
                        "hypothetical_error_cost_eur": cost(fp, fn, inspection, hours),
                    }
                )
    # Conditional uncertainty: resample fixed predictions, not a substitute for
    # independent data.
    rng = np.random.default_rng(42)
    positive = np.flatnonzero(y == 1)
    recalls = [
        float((p[rng.choice(positive, len(positive), replace=True)] >= tuned).mean())
        for _ in range(2000)
    ]
    result = {
        "policies": policies,
        "recall_conditional_bootstrap_95": np.quantile(
            recalls, [0.025, 0.975]
        ).tolist(),
        "cost_scenarios": scenarios,
        "limitations": [
            "Validation used for tuning: optimistic results.",
            (
                "Bootstrap fixes selected model and threshold; "
                + "excludes selection and domain uncertainty."
            ),
            (
                "1200 EUR/hour is classroom downtime assumption, not "
                + "cost per FN or proven savings."
            ),
            (
                "Inspection costs and downtime durations are "
                + "hypothetical sensitivity inputs."
            ),
            (
                "Planned maintenance can prevent observed failure: "
                + "action changes future labels; requires intervention "
                + "logs."
            ),
        ],
    }
    (root / "CG10_results.json").write_text(json.dumps(result, indent=2) + "\n")
    precision, recall, _ = precision_recall_curve(y, p)
    fpr, tpr, _ = roc_curve(y, p)
    fig, axes = plt.subplots(1, 3, figsize=(14, 4), layout="constrained")
    axes[0].plot(recall, precision)
    axes[0].axhline(y.mean(), color="grey", linestyle="--", label="Prevalence")
    axes[0].set(
        xlabel="Recall",
        ylabel="Precision",
        title="Validation precision–recall",
        xlim=(0, 1),
        ylim=(0, 1),
    )
    axes[0].legend()
    axes[1].plot(fpr, tpr)
    axes[1].plot([0, 1], [0, 1], color="grey", linestyle="--")
    axes[1].set(
        xlabel="False positive rate",
        ylabel="True positive rate",
        title="Validation ROC",
        xlim=(0, 1),
        ylim=(0, 1),
    )
    matrix = policies[str(tuned)]["confusion_matrix"]
    axes[2].imshow(matrix, cmap="Blues")
    for row in range(2):
        for col in range(2):
            axes[2].text(
                col,
                row,
                str(matrix[row][col]),
                ha="center",
                va="center",
                color="white" if matrix[row][col] > 500 else "black",
            )
    axes[2].set(
        xticks=[0, 1],
        yticks=[0, 1],
        xlabel="Predicted class",
        ylabel="Observed class",
        title=f"Validation tuned threshold {tuned:.3f}",
    )
    fig.suptitle("Development diagnostics — no independent final test")
    fig.savefig(root / "CG10_diagnostics.png", dpi=150)
    plt.close(fig)
    return result


if __name__ == "__main__":
    run()
