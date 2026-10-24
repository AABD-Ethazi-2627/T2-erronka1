"""Independent stdlib audit of sealed bytes, row boundaries and error counts."""

import argparse
import csv
import hashlib
import json
import math
from pathlib import Path


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def counts(rows, threshold):
    tp = fp = fn = tn = 0
    for row in rows:
        y, score = int(row["label"]), float(row["score"])
        cut = float(row["threshold"]) if threshold is None else threshold
        if score >= cut:
            tp += y
            fp += 1 - y
        else:
            fn += y
            tn += 1 - y
    return {
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "tn": tn,
        "cost_per_1000": (fp * 100 + fn * 1200) * 1000 / len(rows),
    }


def average_precision(rows):
    ordered = sorted(rows, key=lambda r: float(r["score"]), reverse=True)
    total_positives = sum(int(r["label"]) for r in ordered)
    positives = previous_positives = 0
    ap = 0.0
    for i, row in enumerate(ordered):
        positives += int(row["label"])
        if i + 1 == len(ordered) or float(row["score"]) != float(
            ordered[i + 1]["score"]
        ):
            ap += (
                (positives - previous_positives) / total_positives * positives / (i + 1)
            )
            previous_positives = positives
    return ap


def audit(root, summary_path, destination):
    manifest = read(root / "manifest.json")
    if sha(root / "manifest.json") != read(root / "seal.json")["manifest_sha256"]:
        raise ValueError("Invalid manifest seal")
    for path, expected in manifest["code"].items():
        if sha(root / "sealed-code" / path) != expected:
            raise ValueError("Executed source code hash mismatch")
    train = set(manifest["membership"]["train"])
    forbidden = set(manifest["membership"]["validation"]) | set(
        manifest["membership"]["excluded"]
    )
    if train & forbidden or len(train) != 5600:
        raise ValueError("Invalid original partition")
    cpu = {k: 0.0 for k in manifest["budgets"]["cpu_hours"]}
    gpu = pilot_wall = max_rss = 0.0
    index, states, warnings = {}, {}, []
    self_accounting_pending = []
    for directory in sorted((root / "units").iterdir()):
        if not directory.is_dir():
            continue
        if not (directory / "accounting.json").exists():
            task = read(directory / "task.json")
            if (
                task.get("phase") == "analysis"
                and task.get("module") == "scripts.audit_ml_study"
            ):
                self_accounting_pending.append(directory.name)
                continue
            raise ValueError("Unaccounted interrupted unit requires inspection")
        account = read(directory / "accounting.json")
        task = read(directory / "task.json")
        cpu[account["stage"]] += account["cpu_seconds"]
        gpu += account["gpu_seconds"]
        max_rss = max(max_rss, account.get("peak_rss_bytes") or 0)
        states[account["status"]] = states.get(account["status"], 0) + 1
        if task["phase"] == "pilot":
            pilot_wall += account["wall_seconds"]
        if task["phase"] == "preflight":
            continue
        if not set(task["fit"]) <= train or not set(task["held"]) <= train:
            raise ValueError("Validation/test rows consumed")
        if set(task["fit"]) & set(task["held"]) and task["phase"] != "package":
            raise ValueError("Fit/held overlap")
        if task["phase"] in {"inner", "calibration_inner"}:
            outer = task["fold"][0]
            if not set(task["fit"] + task["held"]) <= set(
                manifest["outer"][outer]["fit"]
            ):
                raise ValueError("Outer-held leakage into inner")
        if account["status"] != "complete":
            continue
        result = read(directory / "result.json")
        if result["task_sha256"] != sha(directory / "task.json"):
            raise ValueError("Task corruption")
        if result["scores_sha256"] != sha(directory / "scores.csv"):
            raise ValueError("Scores corruption")
        with (directory / "scores.csv").open(newline="") as stream:
            rows = list(csv.DictReader(stream))
        if [int(r["source_row_index"]) for r in rows] != task["held"]:
            raise ValueError("Held score alignment changed")
        if any(not math.isfinite(float(r["score"])) for r in rows):
            raise ValueError("Nonfinite score")
        if result["model_sha256"]:
            if sha(directory / "model.joblib") != result["model_sha256"]:
                raise ValueError("Model corruption")
            if result["reload_max_difference"] > manifest["reload_atol"]:
                raise ValueError("Reload tolerance exceeded")
        warnings.extend(dict(unit=directory.name, **w) for w in result["warnings"])
        for path in directory.iterdir():
            if path.is_file():
                index[str(path.relative_to(root)).replace("\\", "/")] = sha(path)
    if any(cpu[k] > h * 3600 for k, h in manifest["budgets"]["cpu_hours"].items()):
        raise ValueError("Stage CPU budget exceeded")
    if sum(cpu.values()) > 14 * 3600 or gpu > 7200 or pilot_wall > 600:
        raise ValueError("Study time budget exceeded")
    if max_rss > manifest["budgets"]["rss_bytes"]:
        raise ValueError("Observed RSS exceeded limit")
    summary = read(summary_path)
    verified = {}
    for name, model in summary["models"].items():
        with (summary_path.parent / (name + "-outer.csv")).open(newline="") as stream:
            rows = list(csv.DictReader(stream))
        if {int(r["source_row_index"]) for r in rows} != train or len(rows) != 5600:
            raise ValueError("Incomplete outer population")
        for label, cut in [("optimized", None), ("aviso", 0.15), ("critica", 0.70)]:
            independent = counts(rows, cut)
            for key, value in independent.items():
                if not math.isclose(value, model[label][key], rel_tol=0, abs_tol=1e-10):
                    raise ValueError(f"Count/cost mismatch: {name}/{label}/{key}")
        ap = average_precision(rows)
        if not math.isclose(
            ap, model["optimized"]["average_precision"], rel_tol=0, abs_tol=1e-12
        ):
            raise ValueError("Independent AP mismatch")
        verified[name] = {"n": 5600, "independent_ap": ap, "counts_and_costs": True}
    evidence_size = sum(p.stat().st_size for p in root.rglob("*") if p.is_file())
    if evidence_size > manifest["budgets"]["evidence_bytes"]:
        raise ValueError("Evidence disk budget exceeded")
    result = {
        "status": "pass",
        "method": "stdlib csv/float and independent tied-score AP",
        "manifest_sha256": sha(root / "manifest.json"),
        "summary_sha256": sha(summary_path),
        "cpu_seconds": cpu,
        "gpu_seconds": gpu,
        "pilot_sum_process_wall_seconds": pilot_wall,
        "observed_peak_rss_bytes": max_rss,
        "evidence_bytes": evidence_size,
        "states": states,
        "audit_self_accounting_finalized_after_this_output": self_accounting_pending,
        "verified_models": verified,
        "warnings": warnings,
        "hashes": index,
        "limits": [
            "Self-run technical audit; no independent human review",
            "RSS sampled; not a hardware memory peak guarantee",
            "No final test, industrial acceptance or deployment",
        ],
    }
    with destination.open("x", encoding="utf-8") as stream:
        json.dump(result, stream, indent=2, allow_nan=False)
        stream.write("\n")
    print(
        json.dumps(
            {
                k: v
                for k, v in result.items()
                if k not in {"hashes", "warnings", "verified_models"}
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--summary", type=Path, required=True)
    parser.add_argument("--destination", type=Path, required=True)
    args = parser.parse_args()
    audit(args.root, args.summary, args.destination)
