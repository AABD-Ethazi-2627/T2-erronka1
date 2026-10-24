"""Independent CSV arithmetic and hashes for batch evaluation; no inference."""

import argparse
import csv
import math
from collections import Counter
from pathlib import Path

from scripts.audit_ml_study import average_precision
from scripts.ml_study import digest, read_json, write_json


def read_csv(path):
    with path.open(newline="", encoding="utf-8") as stream:
        return list(csv.DictReader(stream))


def scalar_counts(labels, scores, cut, weights):
    cells = Counter({k: 0 for k in ("tp", "fn", "fp", "tn")})
    for y, score, weight in zip(labels, scores, weights, strict=True):
        predicted = score >= cut
        case = "tp" if y and predicted else "fn" if y else "fp" if predicted else "tn"
        cells[case] += weight
    cells["n"] = sum(weights)
    cells["cost_total_eur"] = cells["tp"] * 300 + cells["fn"] * 5000 + cells["fp"] * 200
    return dict(cells)


def audit(output, destination):
    protocol = read_json(output / "protocol.json")
    if (
        digest(output / "protocol.json")
        != read_json(output / "seal.json")["protocol_sha256"]
    ):
        raise ValueError("Invalid batch seal")
    for name, key in [
        ("inputs.csv", "input_sha256"),
        ("targets-and-origin.csv", "targets_sha256"),
    ]:
        if digest(output / name) != protocol[key]:
            raise ValueError("Sealed batch file changed")
    with (output / "inputs.csv").open(newline="") as stream:
        if next(csv.reader(stream)) != protocol["input_columns"]:
            raise ValueError("Inputs contain unexpected columns")
    result = read_json(output / "results/metrics.json")
    unique = read_csv(output / "results/unique-labels.csv")
    origin = read_csv(output / "targets-and-origin.csv")
    group_by_event = {int(r["event_index"]): int(r["group"]) for r in origin}
    multiplicity = Counter(
        int(r["group"]) for r in origin if r["cohort"] == "unmatched"
    )
    y = [int(r["label"]) for r in unique]
    weights = [multiplicity[group_by_event[int(r["event_index"])]] for r in unique]
    if (
        len(y) != result["counts"]["unique"]
        or sum(weights) != result["counts"]["events"]
    ):
        raise ValueError("Unique/event population mismatch")
    records = [("rf_final_5600-fixed-scores.csv", result["fixed"])]
    for kind in ("outer_models", "anomalies"):
        for name, variants in result[kind].items():
            for fold, record in enumerate(variants):
                records.append((f"{name}-outer{fold}-scores.csv", record))
    verified = []
    for file, record in records:
        path = output / "results" / file
        if digest(path) != record["scores_sha256"]:
            raise ValueError("Score bytes changed")
        rows = read_csv(path)
        if [int(r["unique_row"]) for r in rows] != list(range(len(unique))):
            raise ValueError("Score alignment mismatch")
        scores = [float(r["score"]) for r in rows]
        for label, policy in record["policies"].items():
            for cohort, weight in [("unique", [1] * len(y)), ("events", weights)]:
                independent = scalar_counts(y, scores, policy["threshold"], weight)
                if any(independent[k] != policy[cohort][k] for k in independent):
                    raise ValueError(f"Count/cost mismatch {file}/{label}/{cohort}")
        independent_ap = (
            average_precision(
                [
                    {"label": label, "score": score}
                    for label, score in zip(y, scores, strict=True)
                ]
            )
            if any(y)
            else None
        )
        reported_ap = next(iter(record["policies"].values()))["unique"][
            "average_precision"
        ]
        if (independent_ap is None and reported_ap is not None) or (
            independent_ap is not None
            and not math.isclose(independent_ap, reported_ap, abs_tol=1e-12, rel_tol=0)
        ):
            raise ValueError("Independent AP mismatch")
        verified.append(file)
    if len(records) != 151:
        raise ValueError("Incomplete artifact coverage")
    report = {
        "status": "pass",
        "artifacts": len(records),
        "all_policy_confusion_cells_and_four_cell_costs": True,
        "unique_and_event_multiplicities": True,
        "independent_tied_score_average_precision": True,
        "inputs_are_six_column_allowlist": True,
        "verified_scores": verified,
        "metrics_sha256": digest(output / "results/metrics.json"),
    }
    write_json(destination, report)
    print({k: v for k, v in report.items() if k != "verified_scores"})


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--destination", type=Path, required=True)
    args = parser.parse_args()
    audit(args.output, args.destination)
