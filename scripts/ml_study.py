"""Sealed, budgeted #83 study. Commands: smoke, seal, run, worker, summarize."""

import argparse
import hashlib
import importlib.metadata
import json
import os
import platform
import subprocess
import sys
import time
import traceback
import warnings
from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import psutil
from sklearn.metrics import (
    average_precision_score,
    roc_auc_score,
)
from sklearn.model_selection import StratifiedKFold
from threadpoolctl import threadpool_limits

from scoring.preparation import SENSORS, split_development
from scoring.scope import APPROVED_SOURCE_SHA256, INPUT_FEATURES
from scripts.ml_study_models import CORE, StudyCalibrated, StudyModel, catalog

ROOT = Path(__file__).resolve().parents[1]
CODE = [
    "scripts/ml_study.py",
    "scripts/ml_study_models.py",
    "scripts/ml_study_requirements.txt",
    "scoring/preparation.py",
    "scoring/scope.py",
]
GIB = 1024**3


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def canonical(value):
    return hashlib.sha256(
        json.dumps(
            value, sort_keys=True, separators=(",", ":"), allow_nan=False
        ).encode()
    ).hexdigest()


def write_json(path, value):
    # Exclusive creation: an acknowledged result is never silently replaced.
    with Path(path).open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, indent=2, allow_nan=False)
        stream.write("\n")


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def source_train():
    source = ROOT / "data/ai4i2020_train.csv"
    if digest(source) != APPROVED_SOURCE_SHA256:
        raise ValueError("Unapproved training source")
    frame = pd.read_csv(source, float_precision="round_trip")
    if len(frame) != 8000:
        raise ValueError("Unexpected source length")
    # Membership verification is the only use of labels outside train. Neither
    # validation nor excluded-test rows are passed to scoring/evaluation.
    train, validation, excluded = split_development(frame)
    membership = {
        "train": train.index.tolist(),
        "validation": validation.index.tolist(),
        "excluded": excluded.index.tolist(),
    }
    reference = read_json(ROOT / "docs/evidence/CG04_split_membership.json")["active"]
    for name, ref in [
        ("train", "fit"),
        ("validation", "development_validation"),
        ("excluded", "excluded_previously_inspected_test"),
    ]:
        values = membership[name]
        actual = hashlib.sha256(
            json.dumps(values, separators=(",", ":")).encode()
        ).hexdigest()
        if actual != reference[ref]["ordered_index_sha256"]:
            raise ValueError(f"Original membership mismatch: {name}: {actual}")
    signatures = pd.util.hash_pandas_object(frame[INPUT_FEATURES], index=False)
    if signatures.duplicated().any():
        raise ValueError(
            "Duplicate feature signatures: stop; grouped protocol required"
        )
    return train[INPUT_FEATURES + ["machine_failure"]], membership


def folds(frame, seed):
    return [
        {"fit": frame.index[a].tolist(), "held": frame.index[b].tolist()}
        for a, b in StratifiedKFold(3, shuffle=True, random_state=seed).split(
            frame, frame.machine_failure
        )
    ]


def metrics(y, score, cutoff):
    y, score = np.asarray(y, dtype=int), np.asarray(score, dtype=float)
    pred = score >= cutoff
    tp, fn = int(np.sum(pred & (y == 1))), int(np.sum(~pred & (y == 1)))
    fp, tn = int(np.sum(pred & (y == 0))), int(np.sum(~pred & (y == 0)))
    precision, recall = tp / max(tp + fp, 1), tp / max(tp + fn, 1)
    return dict(
        n=len(y),
        positives=int(y.sum()),
        tp=tp,
        fn=fn,
        fp=fp,
        tn=tn,
        recall=recall,
        precision=precision,
        f1=2 * tp / max(2 * tp + fp + fn, 1),
        f2=5 * tp / max(5 * tp + fp + 4 * fn, 1),
        average_precision=float(average_precision_score(y, score)),
        roc_auc=float(roc_auc_score(y, score)),
        cost_per_1000=(100 * fp + 1200 * fn) * 1000 / len(y),
    )


def choose_threshold(y, score, fp_cost=100, fn_cost=1200):
    y, score = np.asarray(y, dtype=int), np.asarray(score, dtype=float)
    if not np.isfinite(score).all() or not y.sum():
        raise ValueError("Finite scores and positive support required")
    order = np.argsort(-score, kind="stable")
    ends = np.r_[np.flatnonzero(np.diff(score[order])), len(score) - 1]
    tp = np.cumsum(y[order])[ends]
    fp = np.cumsum(1 - y[order])[ends]
    fn = y.sum() - tp
    eligible = np.flatnonzero(tp / y.sum() >= 0.76)
    # Cost, fewer FN, then higher threshold. Latency is a model-level tie-break.
    best = min(
        eligible,
        key=lambda k: (
            fp_cost * fp[k] + fn_cost * fn[k],
            fn[k],
            -score[order[ends[k]]],
        ),
    )
    return float(score[order[ends[best]]])


def smoke(output):
    output.mkdir(parents=True, exist_ok=False)
    rng = np.random.default_rng(93)
    n = 180
    frame = pd.DataFrame(rng.normal(size=(n, 5)), columns=SENSORS)
    frame["rpm"] = 1500 + 200 * frame.rpm
    frame["torque_Nm"] = 40 + 10 * frame.torque_Nm
    frame["machine_type"] = np.resize(["L", "M", "H"], n)
    y = np.resize([0, 0, 0, 0, 1], n)
    report = []
    with threadpool_limits(1):
        for spec in catalog():
            start = time.perf_counter()
            try:
                with warnings.catch_warnings(record=True) as caught:
                    warnings.simplefilter("always")
                    model = StudyModel(spec).fit(frame.iloc[:150], y[:150])
                    scores = model.score(frame.iloc[150:])
                if not np.isfinite(scores).all():
                    raise ValueError("Nonfinite synthetic scores")
                path = output / (spec["name"] + ".joblib")
                joblib.dump(model, path)
                np.testing.assert_allclose(
                    scores,
                    joblib.load(path).score(frame.iloc[150:]),
                    rtol=0,
                    atol=1e-12,
                )
                path.unlink()  # Only our own synthetic scratch artifact.
                report.append(
                    dict(
                        name=spec["name"],
                        status="complete",
                        warnings=[str(w.message) for w in caught],
                        wall_seconds=time.perf_counter() - start,
                    )
                )
            except Exception:
                report.append(
                    dict(
                        name=spec["name"],
                        status="error",
                        error=traceback.format_exc(),
                        wall_seconds=time.perf_counter() - start,
                    )
                )
    write_json(output / "smoke.json", report)
    print(json.dumps(report), flush=True)
    if any(r["status"] != "complete" for r in report):
        raise RuntimeError("Synthetic compatibility failed; do not seal yet")


def seal(output, smoke_path):
    smoke_report = read_json(smoke_path)
    if len(smoke_report) != 50 or any(r["status"] != "complete" for r in smoke_report):
        raise ValueError("All synthetic adapters must complete before seal")
    train, membership = source_train()
    outer = [dict(**f, inner=folds(train.loc[f["fit"]], 42)) for f in folds(train, 43)]
    manifest = dict(
        schema=1,
        created_at=datetime.now(timezone.utc).isoformat(),
        base_commit=subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
        ).strip(),
        source_sha256=APPROVED_SOURCE_SHA256,
        membership=membership,
        code={p: digest(ROOT / p) for p in CODE},
        environment={
            d.metadata["Name"]: d.version for d in importlib.metadata.distributions()
        },
        python=platform.python_version(),
        platform=platform.platform(),
        smoke_sha256=digest(smoke_path),
        catalog=catalog(),
        core=CORE,
        screening=folds(train, 42),
        outer=outer,
        rule=dict(
            fp_euros=100,
            fn_hours=1,
            euros_per_hour=1200,
            recall_floor=0.76,
            tie_break=["fewer_fn", "lower_inner_latency", "catalog_order"],
        ),
        budgets=dict(
            cpu_hours=dict(screening=3, nested=8, secondary=2, benchmark=1),
            gpu_seconds=7200,
            pilot_seconds=600,
            rss_bytes=2 * GIB,
            host_available_bytes=4 * GIB,
            disk_free_bytes=10 * GIB,
            evidence_bytes=2 * GIB,
            gpu_memory_bytes=4 * GIB,
            gpu_free_bytes=6 * GIB,
            screening_fit_seconds=60,
            nested_fit_seconds=120,
        ),
        primary_backend="cpu",
        reload_atol=1e-12,
        constant_classifier_threshold=0.5,
        pilot=dict(
            models=["cat_d4_False", "xgb_d3_True"],
            devices=["cpu", "cuda"],
            repeats=2,
            fit_rows=outer[0]["inner"][0]["fit"],
            held_rows=outer[0]["inner"][0]["held"],
            use_for_selection=False,
            rule=(
                "Only accelerate a separately documented round if total time "
                "improves >=25%; primary pool remains CPU. CPU/GPU are different "
                "implementations, not score-equivalent."
            ),
        ),
        optional=dict(
            calibration=dict(
                scope="top2 inner-ranked per outer plus RF without duplication",
                methods=["raw75", "sigmoid", "isotonic"],
                fit_fraction=0.75,
                calibration_fraction=0.25,
                seed=43,
                budget_cpu_hours=2,
            ),
            stacking=(
                "not executed in this round: additional nesting outside "
                "initial implementation"
            ),
            abstention="not executed: no preregistered human capacity/decision policy",
        ),
        limitations=[
            "Development data already explored; no independent final test",
            "No validation scoring; excluded test untouched for evaluation",
            "Reading full CSV for integrity and original membership only",
            "Anomaly labels unavailable: failure=0 is normality proxy",
            "No served model or API changes",
        ],
    )
    output.mkdir(parents=True, exist_ok=False)
    write_json(output / "manifest.json", manifest)
    write_json(
        output / "seal.json", dict(manifest_sha256=digest(output / "manifest.json"))
    )
    print(
        json.dumps(
            dict(
                output=str(output),
                manifest_sha256=digest(output / "manifest.json"),
                train_rows=len(train),
                train_positives=int(train.machine_failure.sum()),
            )
        )
    )


def verify(output):
    m = read_json(output / "manifest.json")
    if (
        digest(output / "manifest.json")
        != read_json(output / "seal.json")["manifest_sha256"]
    ):
        raise ValueError("Manifest seal changed")
    for path, sha in m["code"].items():
        if digest(ROOT / path) != sha:
            raise ValueError(f"Sealed code changed: {path}. New protocol/run required")
    actual = {d.metadata["Name"]: d.version for d in importlib.metadata.distributions()}
    if actual != m["environment"] or platform.python_version() != m["python"]:
        raise ValueError("Sealed environment changed")
    return m


def worker(output, task_path):
    manifest = verify(output)
    task = read_json(task_path)
    spec = next(s for s in manifest["catalog"] if s["name"] == task["model"])
    train, _ = source_train()
    fit, held = train.loc[task["fit"]], train.loc[task["held"]]
    if set(fit.index) & set(held.index) and task["phase"] != "package":
        raise ValueError("Overlapping fit/held")
    unit = task_path.parent
    begin_cpu, begin = time.process_time(), time.perf_counter()
    with warnings.catch_warnings(record=True) as caught, threadpool_limits(1):
        warnings.simplefilter("always")
        model = (
            StudyCalibrated(spec, task["calibration"])
            if "calibration" in task
            else StudyModel(spec, task.get("device", "cpu"))
        )
        # Includes all fit-time preprocessing; no preprocessing can cross a fold.
        a = time.perf_counter()
        model.fit(fit[INPUT_FEATURES], fit.machine_failure.to_numpy())
        fit_seconds = time.perf_counter() - a
        a = time.perf_counter()
        scores = model.score(held[INPUT_FEATURES])
        prediction_seconds = time.perf_counter() - a
        if not np.isfinite(scores).all():
            raise ValueError("Nonfinite predictions")
        if not spec["anomaly"] and (np.min(scores) < 0 or np.max(scores) > 1):
            raise ValueError("Invalid probability scores")
        reload_difference, artifact = None, None
        if task.get("artifact"):
            artifact = unit / "model.joblib"
            joblib.dump(model, artifact)
            reloaded = joblib.load(artifact).score(held[INPUT_FEATURES])
            reload_difference = float(np.max(np.abs(scores - reloaded)))
            np.testing.assert_allclose(
                scores, reloaded, rtol=0, atol=manifest["reload_atol"]
            )
        latency = []
        if task.get("artifact"):
            for _ in range(10):
                model.score(held[INPUT_FEATURES].iloc[:1])
            for _ in range(50):
                a = time.perf_counter()
                model.score(held[INPUT_FEATURES].iloc[:1])
                latency.append(1000 * (time.perf_counter() - a))
    predictions = pd.DataFrame(
        dict(
            source_row_index=held.index,
            label=held.machine_failure.to_numpy(),
            score=scores,
        )
    )
    predictions.to_csv(unit / "scores.csv", index=False)
    write_json(
        unit / "result.json",
        dict(
            status="complete",
            model=task["model"],
            device=task.get("device", "cpu"),
            task_sha256=digest(task_path),
            fit_rows_sha256=canonical(task["fit"]),
            held_rows_sha256=canonical(task["held"]),
            preparation_included_in_fit=True,
            preparation_seconds=model.preparation_seconds_,
            fit_positive_support=getattr(model, "fit_positive_support_", None),
            calibration_positive_support=getattr(
                model, "calibration_positive_support_", None
            ),
            fit_seconds=fit_seconds - model.preparation_seconds_,
            prediction_seconds=prediction_seconds,
            cpu_seconds=time.process_time() - begin_cpu,
            wall_seconds=time.perf_counter() - begin,
            warnings=[
                dict(category=w.category.__name__, message=str(w.message))
                for w in caught
            ],
            scores_sha256=digest(unit / "scores.csv"),
            reload_max_difference=reload_difference,
            model_sha256=digest(artifact) if artifact else None,
            model_bytes=artifact.stat().st_size if artifact else None,
            warm_process_batch1_p50_ms=float(np.median(latency)) if latency else None,
            warm_process_batch1_p95_ms=float(np.quantile(latency, 0.95))
            if latency
            else None,
        ),
    )


def accounting(output):
    result = {
        k: 0.0 for k in ("screening", "nested", "secondary", "benchmark", "gpu_seconds")
    }
    for path in (output / "units").glob("*/accounting.json"):
        row = read_json(path)
        result[row["stage"]] += row["cpu_seconds"]
        result["gpu_seconds"] += row["gpu_seconds"]
    return result


def gpu_state():
    raw = subprocess.check_output(
        [
            "nvidia-smi",
            "--query-gpu=memory.used,memory.free",
            "--format=csv,noheader,nounits",
        ],
        text=True,
        timeout=5,
    )
    used, free = map(int, raw.strip().splitlines()[0].split(","))
    return used * 1024**2, free * 1024**2


def execute(output, manifest, task, stage, timeout):
    key = canonical(task)
    unit = output / "units" / key
    if unit.exists():
        # An interrupted/failed attempt is never replayed automatically.
        if (unit / "accounting.json").exists():
            record = read_json(unit / "accounting.json")
            if record["status"] == "complete":
                result = read_json(unit / "result.json")
                if (
                    digest(unit / "scores.csv") != result["scores_sha256"]
                    or digest(unit / "task.json") != result["task_sha256"]
                ):
                    raise ValueError("Cached evidence corruption")
            return unit, record["status"]
        raise RuntimeError(
            f"Unaccounted interrupted unit: {unit}; inspect before resuming"
        )
    budget = manifest["budgets"]
    used = accounting(output)
    reserve = timeout  # One thread expected, but actual total CPU is monitored.
    if (
        used[stage] + reserve > budget["cpu_hours"][stage] * 3600
        or sum(used[s] for s in budget["cpu_hours"]) + reserve > 14 * 3600
    ):
        return None, "not_executed_budget"
    gpu = task.get("device") == "cuda"
    if gpu and used["gpu_seconds"] + timeout > budget["gpu_seconds"]:
        return None, "not_executed_gpu_budget"
    evidence_bytes = sum(p.stat().st_size for p in output.rglob("*") if p.is_file())
    if evidence_bytes >= budget["evidence_bytes"]:
        return None, "not_executed_evidence_limit"
    if (
        psutil.virtual_memory().available < budget["host_available_bytes"]
        or psutil.disk_usage(output).free < budget["disk_free_bytes"]
    ):
        return None, "not_executed_host_resource"
    unit.mkdir(parents=True, exist_ok=False)
    write_json(unit / "task.json", task)
    env = os.environ.copy()
    env.update(
        {
            k: "1"
            for k in (
                "OMP_NUM_THREADS",
                "OPENBLAS_NUM_THREADS",
                "MKL_NUM_THREADS",
                "NUMEXPR_NUM_THREADS",
                "VECLIB_MAXIMUM_THREADS",
            )
        }
    )
    start = time.perf_counter()
    cpu_peak = rss_peak = 0
    max_threads = 1
    gpu_used_start = gpu_peak = None
    if gpu:
        gpu_used_start, free = gpu_state()
        gpu_peak = gpu_used_start
        if free < budget["gpu_free_bytes"]:
            write_json(
                unit / "accounting.json",
                dict(
                    stage=stage,
                    status="not_executed_vram",
                    cpu_seconds=0,
                    gpu_seconds=0,
                    wall_seconds=0,
                    peak_rss_bytes=0,
                ),
            )
            return unit, "not_executed_vram"
    status = "complete"
    with (
        (unit / "stdout.log").open("x") as stdout,
        (unit / "stderr.log").open("x") as stderr,
    ):
        process = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "scripts.ml_study",
                "worker",
                "--output",
                str(output),
                "--task",
                str(unit / "task.json"),
            ],
            cwd=ROOT,
            env=env,
            stdout=stdout,
            stderr=stderr,
        )
        monitored = psutil.Process(process.pid)
        while process.poll() is None:
            elapsed = time.perf_counter() - start
            try:
                tree = [monitored] + monitored.children(recursive=True)
                rss = sum(p.memory_info().rss for p in tree)
                cpu = sum(p.cpu_times().user + p.cpu_times().system for p in tree)
                max_threads = max(max_threads, sum(p.num_threads() for p in tree))
                cpu_peak, rss_peak = max(cpu_peak, cpu), max(rss_peak, rss)
                reason = None
                if elapsed > timeout:
                    reason = "timeout"
                if (
                    rss > budget["rss_bytes"]
                    or psutil.virtual_memory().available
                    < budget["host_available_bytes"]
                ):
                    reason = "resource_limit_ram"
                if used[stage] + cpu > budget["cpu_hours"][stage] * 3600:
                    reason = "resource_limit_cpu"
                if gpu:
                    gpu_used, free = gpu_state()
                    gpu_peak = max(gpu_peak, gpu_used)
                    if (
                        gpu_used - gpu_used_start > budget["gpu_memory_bytes"]
                        or free < budget["gpu_free_bytes"]
                    ):
                        reason = "resource_limit_vram"
                if reason:
                    status = reason
                    for child in reversed(tree[1:]):
                        child.kill()
                    process.kill()
                    break
            except psutil.NoSuchProcess:
                pass
            time.sleep(0.2)
        code = process.wait()
    elapsed = time.perf_counter() - start
    if code != 0 and status == "complete":
        status = "error"
    if status == "complete":
        cpu_peak = max(cpu_peak, read_json(unit / "result.json")["cpu_seconds"])
    write_json(
        unit / "accounting.json",
        dict(
            stage=stage,
            status=status,
            exit_code=code,
            cpu_seconds=cpu_peak + max_threads * 0.2,
            cpu_sample_seconds=cpu_peak,
            cpu_method=(
                "process-tree CPU samples plus 0.2s per peak thread for unsampled tail"
            ),
            gpu_seconds=elapsed if gpu else 0,
            wall_seconds=elapsed,
            peak_rss_bytes=rss_peak,
            gpu_total_peak_bytes=gpu_peak,
            gpu_baseline_bytes=gpu_used_start,
            gpu_memory_method=(
                "device total sampled; delta may include desktop workloads"
            )
            if gpu
            else None,
        ),
    )
    print(
        f"{stage} {task['model']} {task.get('fold', '')} "
        f"{task.get('device', 'cpu')} {status} {elapsed:.2f}s",
        flush=True,
    )
    return unit, status


def task_for(spec, fit, held, phase, fold, **kw):
    return dict(model=spec["name"], fit=fit, held=held, phase=phase, fold=fold, **kw)


def completed_units(output):
    records = []
    for path in (output / "units").glob("*/accounting.json"):
        account = read_json(path)
        if account["status"] == "complete":
            records.append((read_json(path.parent / "task.json"), path.parent))
    return records


def primary_names(output, manifest):
    units = completed_units(output)
    complete = []
    for spec in manifest["catalog"]:
        if spec["anomaly"]:
            continue
        records = [t for t, _ in units if t["model"] == spec["name"]]
        if (
            sum(t["phase"] == "inner" for t in records) == 9
            and sum(t["phase"] == "outer" for t in records) == 3
        ):
            complete.append(spec["name"])
    if len(complete) == 40:
        return complete
    if set(manifest["core"]) <= set(complete):
        return manifest["core"]
    raise RuntimeError("Primary core incomplete: secondary selection is blocked")


def inner_ranking(output, names, outer=None):
    ranking = []
    units = completed_units(output)
    for name in names:
        found = [
            (t, p)
            for t, p in units
            if t["model"] == name
            and t["phase"] == ("screening" if outer is None else "inner")
            and (outer is None or t["fold"][0] == outer)
        ]
        if len(found) != 3:
            raise RuntimeError(f"Incomplete inner coverage: {name}")
        scores = pd.concat(
            [
                pd.read_csv(p / "scores.csv", float_precision="round_trip")
                for _, p in found
            ]
        )
        if scores.source_row_index.duplicated().any():
            raise ValueError("Duplicate OOF row")
        cutoff = (
            0.5
            if name in {"always0", "always1"}
            else choose_threshold(scores.label, scores.score)
        )
        m = metrics(scores.label, scores.score, cutoff)
        latency = sum(
            read_json(p / "result.json")["prediction_seconds"] for _, p in found
        ) / len(scores)
        ranking.append(dict(name=name, threshold=cutoff, metrics=m, latency=latency))
    eligible = [r for r in ranking if r["metrics"]["recall"] >= 0.76]
    return sorted(
        eligible,
        key=lambda r: (
            r["metrics"]["cost_per_1000"],
            r["metrics"]["fn"],
            r["latency"],
            names.index(r["name"]),
        ),
    )


def run(output, phase):
    manifest = verify(output)
    (output / "units").mkdir(exist_ok=True)
    # OS-owned nonblocking lock prevents concurrent drivers or stale PID guesses.
    from scripts.platform_io import exclusive_lock

    with exclusive_lock(output / "study.lock", blocking=False):
        if phase == "pilot":
            start = time.perf_counter()
            p = manifest["pilot"]
            for name in p["models"]:
                spec = next(s for s in manifest["catalog"] if s["name"] == name)
                for repeat in range(p["repeats"]):
                    for device in p["devices"]:
                        remaining = manifest["budgets"]["pilot_seconds"] - (
                            time.perf_counter() - start
                        )

                        if remaining <= 5:
                            return
                        execute(
                            output,
                            manifest,
                            task_for(
                                spec,
                                p["fit_rows"],
                                p["held_rows"],
                                "pilot",
                                repeat,
                                device=device,
                                artifact=True,
                            ),
                            "benchmark",
                            min(75, remaining),
                        )
        elif phase == "screening":
            for spec in manifest["catalog"]:
                for fold, f in enumerate(manifest["screening"]):
                    execute(
                        output,
                        manifest,
                        task_for(spec, f["fit"], f["held"], phase, fold),
                        "screening",
                        60,
                    )
        elif phase == "nested":
            names = manifest["core"] + [
                s["name"]
                for s in manifest["catalog"]
                if s["name"] not in manifest["core"]
            ]
            # Whole core first. Each subsequent candidate completes every outer.
            for name in names:
                spec = next(s for s in manifest["catalog"] if s["name"] == name)
                for outer, f in enumerate(manifest["outer"]):
                    for inner, g in enumerate(f["inner"]):
                        execute(
                            output,
                            manifest,
                            task_for(
                                spec, g["fit"], g["held"], "inner", [outer, inner]
                            ),
                            "nested",
                            120,
                        )
                    execute(
                        output,
                        manifest,
                        task_for(
                            spec, f["fit"], f["held"], "outer", outer, artifact=True
                        ),
                        "nested",
                        120,
                    )
        elif phase == "calibration":
            names = primary_names(output, manifest)
            for outer, f in enumerate(manifest["outer"]):
                ranking = inner_ranking(output, names, outer)
                finalists = list(
                    dict.fromkeys([r["name"] for r in ranking[:2]] + ["rf_reference"])
                )
                for name in finalists:
                    spec = next(s for s in manifest["catalog"] if s["name"] == name)
                    for method in manifest["optional"]["calibration"]["methods"]:
                        for inner, g in enumerate(f["inner"]):
                            execute(
                                output,
                                manifest,
                                task_for(
                                    spec,
                                    g["fit"],
                                    g["held"],
                                    "calibration_inner",
                                    [outer, inner],
                                    calibration=method,
                                ),
                                "secondary",
                                120,
                            )
                        execute(
                            output,
                            manifest,
                            task_for(
                                spec,
                                f["fit"],
                                f["held"],
                                "calibration_outer",
                                outer,
                                calibration=method,
                                artifact=True,
                            ),
                            "secondary",
                            120,
                        )
        elif phase == "package":
            names = primary_names(output, manifest)
            selected = inner_ranking(output, names)[0]
            for name in dict.fromkeys(["rf_reference", selected["name"]]):
                spec = next(s for s in manifest["catalog"] if s["name"] == name)
                execute(
                    output,
                    manifest,
                    task_for(
                        spec,
                        manifest["membership"]["train"],
                        manifest["membership"]["train"][:32],
                        "package",
                        0,
                        artifact=True,
                        threshold=next(
                            r["threshold"] for r in inner_ranking(output, [name])
                        ),
                    ),
                    "benchmark",
                    120,
                )
        else:
            raise ValueError(phase)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["smoke", "seal", "run", "worker"])
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--smoke", type=Path)
    parser.add_argument(
        "--phase", choices=["pilot", "screening", "nested", "calibration", "package"]
    )
    parser.add_argument("--task", type=Path)
    args = parser.parse_args()
    if args.command == "smoke":
        smoke(args.output)
    elif args.command == "seal":
        seal(args.output, args.smoke)
    elif args.command == "worker":
        worker(args.output, args.task)
    else:
        run(args.output, args.phase)


if __name__ == "__main__":
    main()
