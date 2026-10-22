"""Bounded synthetic queue lab. No network clients or production integrations."""

import argparse
import hashlib
import json
import logging
import math
import os
import platform
import queue
import statistics
import subprocess
import sys
import tempfile
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path

if __package__:
    from scripts.platform_io import peak_rss_kib
else:
    # Preserve the original standalone entry point, including from another cwd.
    from platform_io import peak_rss_kib

LOGGER = logging.getLogger(__name__)


def percentile(values, fraction):
    return (
        sorted(values)[max(0, math.ceil(len(values) * fraction) - 1)]
        if values
        else None
    )


def estimates(
    machines=50,
    hz=1,
    event_bytes=512,
    days=90,
    replicas=1,
    overhead=1.5,
    fn=10,
    fp=20,
    hours=1,
    inspection_eur=50,
    infra_eur=100,
):
    """Decimal bytes; hypothetical counts must refer to one common evaluation period."""
    values = (
        machines,
        hz,
        event_bytes,
        days,
        replicas,
        overhead,
        fn,
        fp,
        hours,
        inspection_eur,
        infra_eur,
    )
    if any(not math.isfinite(v) or v < 0 for v in values):
        raise ValueError("finite nonnegative assumptions required")
    raw = machines * hz * 86400 * days * event_bytes
    return {
        "raw_bytes": raw,
        "provisioned_bytes": raw * (1 + replicas) * overhead,
        "expected_cost_eur": fn * hours * 1200 + fp * inspection_eur + infra_eur,
        "assumptions": dict(
            zip(
                (
                    "machines",
                    "events_per_machine_s",
                    "event_bytes",
                    "days",
                    "replicas",
                    "storage_overhead",
                    "FN",
                    "FP",
                    "downtime_hours_per_FN",
                    "inspection_eur_per_FP",
                    "infra_eur_per_period",
                ),
                values,
            )
        ),
    }


def run(rate, duration, workers, capacity=16, service_ms=10, fail_every=17):
    """One temporary buffered sink; retry IDs survive only in process memory."""
    integers = (rate, workers, capacity, fail_every)
    if (
        any(type(v) is not int for v in integers)
        or not math.isfinite(duration)
        or not math.isfinite(service_ms)
        or not (
            1 <= rate <= 1000
            and 0 < duration <= 5
            and workers in (1, 4)
            and 1 <= capacity <= 64
            and 0 <= service_ms <= 100
            and fail_every >= 0
        )
    ):
        raise ValueError("lab bounds exceeded")
    count = int(rate * duration)
    if count < 1:
        raise ValueError("at least one event required")
    pending = queue.Queue(capacity)
    lock = threading.Lock()
    abort = threading.Event()
    latencies, retry, ids, errors = [], [], set(), []
    highwater = failures = duplicates = 0
    producer_lag_max_ms = 0
    cpu_start = time.process_time()
    start = time.perf_counter()
    with tempfile.TemporaryDirectory(prefix="cg23-") as directory:
        sink_path = Path(directory) / "events.jsonl"
        with sink_path.open("w", encoding="utf-8") as sink:

            def consume():
                nonlocal failures, duplicates
                while True:
                    item = pending.get()
                    try:
                        if item is None:
                            return
                        if abort.is_set():
                            continue
                        ident, scheduled = item
                        time.sleep(service_ms / 1000)
                        with lock:
                            if fail_every and (ident + 1) % fail_every == 0:
                                failures += 1
                                retry.append(ident)
                            else:
                                duplicates += ident in ids
                                ids.add(ident)
                                sink.write(
                                    json.dumps({"id": ident, "payload": "x" * 128})
                                    + "\n"
                                )
                                latencies.append(
                                    (time.perf_counter() - scheduled) * 1000
                                )
                    except Exception as exc:
                        LOGGER.exception(
                            "Local sink worker failed; aborting measurement"
                        )
                        # Keep draining tasks so a failed sink cannot strand join().
                        with lock:
                            errors.append(exc)
                        abort.set()
                    finally:
                        pending.task_done()

            with ThreadPoolExecutor(max_workers=workers) as pool:
                futures = [pool.submit(consume) for _ in range(workers)]
                for ident in range(count):
                    if abort.is_set():
                        break
                    scheduled = start + ident / rate
                    time.sleep(max(0, scheduled - time.perf_counter()))
                    producer_lag_max_ms = max(
                        producer_lag_max_ms, (time.perf_counter() - scheduled) * 1000
                    )
                    try:
                        pending.put_nowait((ident, scheduled))
                        highwater = max(highwater, pending.qsize())
                    except queue.Full:
                        retry.append(ident)
                offer_elapsed = time.perf_counter() - start
                pending.join()
                elapsed = time.perf_counter() - start
                for _ in futures:
                    pending.put(None)
                for future in futures:
                    future.result()
            if errors:
                raise RuntimeError(
                    "local sink worker failed; no capacity result"
                ) from errors[0]
            successful = len(ids)
            replay_start = time.perf_counter()
            # Replay omits synthetic failures, then repeats every retry ID once.
            for ident in retry + retry:
                if ident in ids:
                    duplicates += 1
                    continue
                ids.add(ident)
                sink.write(json.dumps({"id": ident, "payload": "x" * 128}) + "\n")
        replay_elapsed = time.perf_counter() - replay_start
        disk_bytes = sink_path.stat().st_size
        with sink_path.open(encoding="utf-8") as source:
            records = [json.loads(line)["id"] for line in source]
        missing = len(set(range(count)) - set(records))
        unexpected = len(set(records) - set(range(count)))
        duplicate_rows = len(records) - len(set(records))
        if count != successful + failures + len(retry) - failures:
            raise RuntimeError("initial delivery accounting mismatch")
        if missing or unexpected or duplicate_rows:
            raise RuntimeError("local replay did not reconcile exact IDs")
        return {
            "rate_events_s": rate,
            "offered": count,
            "offered_duration_s": duration,
            "scheduled_span_s": (count - 1) / rate,
            "producer_elapsed_s": offer_elapsed,
            "producer_schedule_lag_max_ms": producer_lag_max_ms,
            "workers": workers,
            "queue_capacity": capacity,
            "service_delay_ms": service_ms,
            "injected_failure_every": fail_every,
            "initial_success": successful,
            "initial_failure": failures,
            "rejected": len(retry) - failures,
            "drain_elapsed_s": elapsed,
            "throughput_success_s": successful / elapsed,
            "p50_end_to_end_ms": percentile(latencies, 0.5),
            "p95_end_to_end_ms": percentile(latencies, 0.95),
            "max_queue_events": highwater,
            "replay_candidates": len(retry),
            "duplicate_attempts_blocked": duplicates,
            "final_missing": missing,
            "final_unexpected": unexpected,
            "final_duplicate_rows": duplicate_rows,
            "sink_bytes": disk_bytes,
            "replay_elapsed_s": replay_elapsed,
            "cpu_process_s": time.process_time() - cpu_start,
            "process_peak_rss_KiB": peak_rss_kib(),
            "workload_sha256": hashlib.sha256(
                json.dumps(
                    {
                        "ids": list(range(count)),
                        "payload": "x" * 128,
                        "fail_every": fail_every,
                    },
                    sort_keys=True,
                ).encode()
            ).hexdigest(),
        }


def summaries(runs):
    """Describe run-to-run variation; never pool latency percentiles."""
    result = []
    for rate, workers in sorted({(r["rate_events_s"], r["workers"]) for r in runs}):
        group = [
            r for r in runs if (r["rate_events_s"], r["workers"]) == (rate, workers)
        ]
        metrics = {}
        for key in (
            "throughput_success_s",
            "p95_end_to_end_ms",
            "rejected",
            "initial_failure",
            "cpu_process_s",
            "process_peak_rss_KiB",
        ):
            values = [r[key] for r in group if r[key] is not None]
            metrics[key] = {
                "n": len(values),
                "mean": statistics.mean(values) if values else None,
                "median": statistics.median(values) if values else None,
                "min": min(values) if values else None,
                "max": max(values) if values else None,
                "sample_stdev": statistics.stdev(values) if len(values) > 1 else None,
            }
        result.append(
            {
                "rate_events_s": rate,
                "workers": workers,
                "repetitions": len(group),
                "metrics": metrics,
            }
        )
    return result


def protocol(repetitions=3, rates=(25, 100, 250), duration=1):
    if (
        type(repetitions) is not int
        or not 3 <= repetitions <= 5
        or not rates
        or len(rates) > 3
        or len(set(rates)) != len(rates)
        or any(type(rate) is not int or not 1 <= rate <= 1000 for rate in rates)
        or not math.isfinite(duration)
        or not 0 < duration <= 5
    ):
        raise ValueError("protocol bounds exceeded")
    started = datetime.now(UTC).isoformat()
    script = Path(__file__).resolve()
    script_hash = hashlib.sha256(script.read_bytes()).hexdigest()
    runs = []
    for repetition in range(1, repetitions + 1):
        # Alternate pair order to expose some order effects without random inputs.
        order = (1, 4) if repetition % 2 else (4, 1)
        for rate in rates:
            for workers in order:
                child = subprocess.run(
                    [
                        sys.executable,
                        "-B",
                        "-m",
                        "scripts.cg23_capacity",
                        "--worker",
                        str(rate),
                        str(duration),
                        str(workers),
                    ],
                    check=True,
                    capture_output=True,
                    text=True,
                    timeout=30,
                    cwd=Path(__file__).resolve().parents[1],
                )
                measured = json.loads(child.stdout)
                if (
                    measured["workload_sha256"]
                    != hashlib.sha256(
                        json.dumps(
                            {
                                "ids": list(range(int(rate * duration))),
                                "payload": "x" * 128,
                                "fail_every": 17,
                            },
                            sort_keys=True,
                        ).encode()
                    ).hexdigest()
                ):
                    raise RuntimeError("worker workload identity mismatch")
                runs.append(
                    {"repetition": repetition, "sequence": len(runs) + 1, **measured}
                )
    if hashlib.sha256(script.read_bytes()).hexdigest() != script_hash:
        raise RuntimeError("script changed during measurements")
    return {
        "scope": (
            "synthetic in-process queue and buffered JSONL; "
            "not distributed pipeline capacity"
        ),
        "base_commit": "f446ddaac911431b598e0ecfa961c3caff4164f2",
        "script_sha256": script_hash,
        "started_at_utc": started,
        "finished_at_utc": datetime.now(UTC).isoformat(),
        "environment": {
            "platform": platform.platform(),
            "python": platform.python_version(),
            "logical_cpus": os.cpu_count(),
            "rss_scope": (
                "fresh child interpreter per run; lifetime peak in KiB; "
                "Windows PeakWorkingSetSize or POSIX ru_maxrss"
            ),
            "temporary_filesystem": tempfile.gettempdir(),
        },
        "protocol": {
            "repetitions": repetitions,
            "rates_events_s": list(rates),
            "workers": [1, 4],
            "duration_s": duration,
            "order": "rate ascending as supplied; worker pairs 1,4 / 4,1 / 1,4",
            "worker_timeout_s": 30,
            "queue_capacity": 16,
            "service_delay_ms": 10,
            "failure_every": 17,
        },
        "runs": runs,
        "summaries": summaries(runs),
        "estimates": [
            estimates(hours=h, days=d) for h in (0.5, 1, 2) for d in (7, 30, 90)
        ],
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--repetitions", type=int, choices=range(3, 6), default=3)
    parser.add_argument(
        "--worker",
        nargs=3,
        metavar=("RATE", "SECONDS", "WORKERS"),
        help=argparse.SUPPRESS,
    )
    args = parser.parse_args(argv)
    if args.worker:
        if args.output:
            parser.error("worker cannot publish output")
        rate, duration, workers = args.worker
        print(json.dumps(run(int(rate), float(duration), int(workers))))
    else:
        if args.output is None:
            parser.error("--output is required")
        # Reserve first: a repeat invocation cannot perform work or overwrite evidence.
        # A failed run leaves its reserved file; keep it and choose a fresh path.
        with args.output.open("x", encoding="utf-8") as target:
            result = protocol(args.repetitions)
            json.dump(result, target, indent=2, allow_nan=False)
            target.write("\n")


if __name__ == "__main__":
    main()
