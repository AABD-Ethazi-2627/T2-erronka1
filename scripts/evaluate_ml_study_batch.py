"""Evaluate an attached batch with frozen study artifacts; never train or tune."""

import argparse
import csv
import gc
import hashlib
import json
import time
import warnings
import zipfile
from io import BytesIO, StringIO
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from threadpoolctl import threadpool_limits

from scoring.preparation import SENSORS
from scoring.scope import APPROVED_SOURCE_SHA256, INPUT_FEATURES
from scripts.ml_study import ROOT, completed_units, digest, read_json, write_json
from scripts.report_ml_study import verify_evidence

SELF = Path(__file__)


def sanitize(frame):
    """Positive allowlist: targets, IDs and all present/future extras stay out."""
    if not frame.columns.is_unique or not set(INPUT_FEATURES) <= set(frame):
        raise ValueError("Missing or duplicate model input columns")
    result = frame.loc[:, INPUT_FEATURES].copy()
    for column in SENSORS:
        result[column] = pd.to_numeric(result[column], errors="raise").astype(float)
    if not np.isfinite(result[SENSORS].to_numpy()).all():
        raise ValueError("Nonfinite sensors: batch requires explicit repair")
    if not result.machine_type.isin(["H", "M", "L"]).all():
        raise ValueError("Unknown or missing machine_type")
    return result


def read_batch(path):
    frames, inventory = [], []
    with zipfile.ZipFile(path) as archive:
        entries = archive.infolist()
        if (
            not entries
            or len(entries) > 1000
            or sum(i.file_size for i in entries) > 10 * 1024**2
            or len({i.filename for i in entries}) != len(entries)
        ):
            raise ValueError("Unexpected archive size or duplicate members")
        schema = None
        for entry in sorted(entries, key=lambda i: i.filename):
            name = entry.filename
            if (
                not name.endswith(".csv")
                or "/" in name
                or "\\" in name
                or ":" in name
                or name.startswith(".")
                or (entry.external_attr >> 16) & 0o170000 == 0o120000
                or entry.flag_bits & 1
            ):
                raise ValueError("Only flat, unencrypted CSV files are accepted")
            raw = archive.read(entry)  # CRC verified; no filesystem extraction.
            header = next(csv.reader(StringIO(raw.decode("utf-8-sig"))))
            if len(set(header)) != len(header) or (schema and header != schema):
                raise ValueError("Duplicate columns or inconsistent batch schema")
            schema = header
            frame = pd.read_csv(BytesIO(raw), float_precision="round_trip")
            sanitize(frame)
            if (
                "machine_failure" not in frame
                or not frame.machine_failure.isin([0, 1]).all()
            ):
                raise ValueError("Binary machine_failure required for metrics")
            frame["_source_file"] = name
            frame["_file_row"] = np.arange(len(frame))
            frames.append(frame)
            inventory.append(
                {
                    "name": name,
                    "sha256": hashlib.sha256(raw).hexdigest(),
                    "rows": len(frame),
                }
            )
    return pd.concat(frames, ignore_index=True), inventory


def exact_membership(inputs, original, membership):
    """Compare exact canonical values, independent of dtype-sensitive hashes."""
    old = pd.MultiIndex.from_frame(sanitize(original))
    if not old.is_unique:
        raise ValueError("Original feature signatures no longer unique")
    positions = old.get_indexer(pd.MultiIndex.from_frame(inputs))
    cohort = {i: name for name, ids in membership.items() for i in ids}
    return positions, [cohort.get(int(i), "unmatched") for i in positions]


def seal(archive_path, study, output):
    manifest = verify_evidence(study)
    source = ROOT / "data/ai4i2020_train.csv"
    if digest(source) != APPROVED_SOURCE_SHA256:
        raise ValueError("Original source changed")
    frame, inventory = read_batch(archive_path)
    inputs = sanitize(frame)
    original = pd.read_csv(source, float_precision="round_trip")
    matched, cohorts = exact_membership(inputs, original, manifest["membership"])
    # Exclude every prior-development match, including the forbidden old test.
    eligible = np.asarray(cohorts) == "unmatched"
    keys = pd.MultiIndex.from_frame(inputs)
    groups, _ = pd.factorize(keys, sort=False)
    targets = pd.DataFrame(
        {
            "event_index": np.arange(len(frame)),
            "label": frame.machine_failure.astype(int),
            "group": groups,
            "cohort": cohorts,
            "original_row_index": matched,
            "source_file": frame._source_file,
            "file_row": frame._file_row,
        }
    )
    if targets.groupby("group").label.nunique().max() > 1:
        raise ValueError("Identical features carry conflicting labels; stop")
    if not eligible.any():
        raise ValueError("No previously unseen rows; no independent batch scoring")
    output.mkdir(exist_ok=False)
    inputs.to_csv(output / "inputs.csv", index=False)
    targets.to_csv(output / "targets-and-origin.csv", index=False)
    write_json(output / "files.json", inventory)
    package_info = read_json(study / "analysis-v2/packages/packages.json")
    package = package_info["packages"][0]
    package_path = study / "analysis-v2/packages" / package["file"]
    if digest(package_path) != package["artifact_sha256"]:
        raise ValueError("Fixed research package hash mismatch")
    outer = []
    for task, path in completed_units(study):
        if task["phase"] == "outer":
            result = read_json(path / "result.json")
            outer.append(
                {
                    "model": task["model"],
                    "outer": task["fold"],
                    "path": str((path / "model.joblib").resolve()),
                    "sha256": result["model_sha256"],
                    "fit_n": len(task["fit"]),
                }
            )
    if len(outer) != 150:
        raise ValueError("Expected all 50 × 3 saved outer artifacts")
    old_summary = study / "analysis-v2/summary.json"
    business = ROOT / "docs/evidence/CG34_20261023/business-summary.json"
    ranges = {}
    for column in SENSORS:
        lower, upper = original.loc[manifest["membership"]["train"], column].agg(
            ["min", "max"]
        )
        ranges[column] = {
            "train_min": float(lower),
            "train_max": float(upper),
            "batch_outside_train_range": int(
                ((inputs[column] < lower) | (inputs[column] > upper)).sum()
            ),
        }
    protocol = {
        "archive_sha256": digest(archive_path),
        "study_manifest_sha256": digest(study / "manifest.json"),
        "code_sha256": digest(SELF),
        "adapter_sha256": digest(ROOT / "scripts/ml_study_models.py"),
        "input_sha256": digest(output / "inputs.csv"),
        "targets_sha256": digest(output / "targets-and-origin.csv"),
        "source_sha256": digest(source),
        "old_summary_sha256": digest(old_summary),
        "business_summary_sha256": digest(business),
        "files": len(inventory),
        "events": len(frame),
        "unique_vectors": int(keys.nunique()),
        "cohorts": pd.Series(cohorts).value_counts().to_dict(),
        "eligible_events": int(eligible.sum()),
        "eligible_unique_vectors": int(targets.loc[eligible, "group"].nunique()),
        "input_columns": INPUT_FEATURES,
        "excluded_columns": [c for c in frame if c not in INPUT_FEATURES],
        "sensor_ranges": ranges,
        "fixed_model": {
            "name": "rf_final_5600",
            "path": str(package_path.resolve()),
            "sha256": package["artifact_sha256"],
            "fit_n": 5600,
        },
        "outer_artifacts": sorted(outer, key=lambda r: (r["model"], r["outer"])),
        "policies": {
            "fixed": [0.15, 0.70],
            "research_initial": 0.1599255350951087,
            "research_business": 0.11899870801033592,
            "outer_A": "existing inner-learned business threshold per artifact",
            "anomaly": "existing normal inner quantile 0.99 per artifact",
        },
        "cost_eur": {"tp": 300, "fn": 5000, "fp": 200, "tn": 0},
        "reporting": "event-weighted and one occurrence per unique six-input vector",
        "model_comparison": (
            "Each of 3 saved outer models is evaluated separately; report range/mean. "
            "Not a new ensemble; RF trained on 5600 is reported separately."
        ),
        "selection": "No fits, calibration, threshold tuning or model selection",
        "limits": {"timeout_seconds": 300, "rss_bytes": 2 * 1024**3},
    }
    write_json(output / "protocol.json", protocol)
    write_json(
        output / "seal.json", {"protocol_sha256": digest(output / "protocol.json")}
    )
    print(
        json.dumps(
            {
                k: protocol[k]
                for k in (
                    "files",
                    "events",
                    "unique_vectors",
                    "cohorts",
                    "eligible_events",
                )
            }
        )
    )


def metric_set(labels, scores, cut):
    from sklearn.metrics import average_precision_score, roc_auc_score

    y, p = np.asarray(labels, dtype=int), np.asarray(scores) >= cut
    tp, fn = int(np.sum((y == 1) & p)), int(np.sum((y == 1) & ~p))
    fp, tn = int(np.sum((y == 0) & p)), int(np.sum((y == 0) & ~p))
    total = 300 * tp + 5000 * fn + 200 * fp
    return {
        "n": len(y),
        "tp": tp,
        "fn": fn,
        "fp": fp,
        "tn": tn,
        "recall": tp / (tp + fn) if tp + fn else None,
        "precision": tp / (tp + fp) if tp + fp else None,
        "f1": 2 * tp / (2 * tp + fp + fn) if 2 * tp + fp + fn else None,
        "f2": 5 * tp / (5 * tp + fp + 4 * fn) if 5 * tp + fp + 4 * fn else None,
        "average_precision": float(average_precision_score(y, scores))
        if y.sum()
        else None,
        "roc_auc": float(roc_auc_score(y, scores)) if len(set(y)) == 2 else None,
        "cost_total_eur": total,
        "cost_per_1000": total * 1000 / len(y),
    }


def score_frame(model, inputs, fixed=False):
    # Assert the boundary immediately before every inference call.
    if list(inputs.columns) != INPUT_FEATURES:
        raise ValueError("Unexpected estimator input columns")
    return np.asarray(
        model.predict_proba(inputs)[:, 1] if fixed else model.score(inputs),
        dtype=np.float64,
    )


def run(study, output):
    manifest = verify_evidence(study)
    protocol = read_json(output / "protocol.json")
    if (
        digest(output / "protocol.json")
        != read_json(output / "seal.json")["protocol_sha256"]
    ):
        raise ValueError("Batch protocol changed")
    paths = {
        "code_sha256": SELF,
        "adapter_sha256": ROOT / "scripts/ml_study_models.py",
        "input_sha256": output / "inputs.csv",
        "targets_sha256": output / "targets-and-origin.csv",
        "old_summary_sha256": study / "analysis-v2/summary.json",
        "business_summary_sha256": ROOT
        / "docs/evidence/CG34_20261023/business-summary.json",
    }
    for key, path in paths.items():
        if digest(path) != protocol[key]:
            raise ValueError("Sealed batch bytes changed: " + key)
    destination = output / "results"
    destination.mkdir(exist_ok=False)
    X = sanitize(pd.read_csv(output / "inputs.csv", float_precision="round_trip"))
    targets = pd.read_csv(output / "targets-and-origin.csv")
    eligible = targets.loc[targets.cohort == "unmatched"].copy()
    unique = eligible.drop_duplicates("group")
    unique_X = X.loc[unique.index, INPUT_FEATURES]
    unique_y = unique.label.to_numpy()
    expansion = pd.Index(unique.group).get_indexer(eligible.group)
    old = read_json(study / "analysis-v2/summary.json")
    business = read_json(paths["business_summary_sha256"])
    result = {
        "protocol_sha256": digest(output / "protocol.json"),
        "fixed": {},
        "outer_models": {},
        "anomalies": {},
        "counts": {
            "events": len(eligible),
            "unique": len(unique),
            "positive_events": int(eligible.label.sum()),
            "positive_unique": int(unique.label.sum()),
        },
    }
    label_artifact = pd.DataFrame(
        {
            "unique_row": np.arange(len(unique)),
            "event_index": unique.event_index,
            "label": unique_y,
        }
    )
    label_artifact.to_csv(destination / "unique-labels.csv", index=False)
    start_wall, start_cpu = time.perf_counter(), time.process_time()
    specs = {s["name"]: s for s in manifest["catalog"]}
    artifacts = [protocol["fixed_model"]] + protocol["outer_artifacts"]
    for item in artifacts:
        fixed = "name" in item
        name = item["name"] if fixed else item["model"]
        artifact = Path(item["path"])
        if digest(artifact) != item["sha256"]:
            raise ValueError("Artifact hash mismatch: " + name)
        with warnings.catch_warnings(record=True) as caught, threadpool_limits(1):
            warnings.simplefilter("always")
            model = joblib.load(artifact)  # Own sealed artifacts only.
            begin = time.perf_counter()
            scores = score_frame(model, unique_X, fixed)
            prediction_seconds = time.perf_counter() - begin
            if len(scores) != len(unique) or not np.isfinite(scores).all():
                raise ValueError("Invalid prediction array")
        anomaly = not fixed and specs[name]["anomaly"]
        if not anomaly and ((scores < 0) | (scores > 1)).any():
            raise ValueError("Classification score outside [0,1]")
        if fixed:
            cuts = {
                "aviso": 0.15,
                "critica": 0.70,
                "research_initial": protocol["policies"]["research_initial"],
                "research_business": protocol["policies"]["research_business"],
            }
        elif anomaly:
            cuts = {
                "rarity": old["anomalies"][name]["folds"][item["outer"]]["threshold"]
            }
        else:
            cuts = {
                "aviso": 0.15,
                "critica": 0.70,
                "business_A": business["models"][name]["folds"][item["outer"]][
                    "threshold"
                ],
            }
        record = {
            "artifact_sha256": item["sha256"],
            "fit_n": item["fit_n"],
            "prediction_seconds_unique_batch": prediction_seconds,
            "warnings": [str(w.message) for w in caught],
            "policies": {},
        }
        for label, cut in cuts.items():
            record["policies"][label] = {
                "threshold": cut,
                "unique": metric_set(unique_y, scores, cut),
                "events": metric_set(eligible.label, scores[expansion], cut),
            }
        suffix = "fixed" if fixed else "outer" + str(item["outer"])
        score_path = destination / f"{name}-{suffix}-scores.csv"
        pd.DataFrame({"unique_row": np.arange(len(unique)), "score": scores}).to_csv(
            score_path, index=False
        )
        record["scores_sha256"] = digest(score_path)
        if fixed:
            result["fixed"] = record
            pd.DataFrame(
                {
                    "event_index": eligible.event_index,
                    "label": eligible.label,
                    "score": scores[expansion],
                    "aviso": scores[expansion] >= 0.15,
                    "critica": scores[expansion] >= 0.70,
                }
            ).to_csv(destination / "rf-event-predictions.csv", index=False)
        else:
            result["anomalies" if anomaly else "outer_models"].setdefault(
                name, []
            ).append(record)
        del model
        gc.collect()
    result["elapsed_seconds"] = time.perf_counter() - start_wall
    result["cpu_seconds_own_process"] = time.process_time() - start_cpu
    result["scope"] = protocol["model_comparison"]
    write_json(destination / "metrics.json", result)
    print(
        json.dumps(
            {
                "counts": result["counts"],
                "rf_aviso": result["fixed"]["policies"]["aviso"],
                "artifacts_scored": len(artifacts),
            }
        ),
        flush=True,
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["seal", "run"])
    parser.add_argument("--archive", type=Path)
    parser.add_argument("--study", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "seal":
        seal(args.archive, args.study, args.output)
    else:
        run(args.study, args.output)


if __name__ == "__main__":
    main()
