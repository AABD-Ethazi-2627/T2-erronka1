"""CG32 bounded load of the integrated graph: fixture, offer, reconcile, summarize.

Pure helpers plus a CLI. Infrastructure (Compose, NiFi, ES) lives in
``scripts/cg32_lab.py``; this module never starts services or loads models.

Measurement points (all on one host clock):
- ``offer``: UTC/monotonic instant after ``os.write`` + ``fsync`` of one CSV line
  into the Filebeat input file (entry of the graph).
- HTTP: server-side span of the real API app, written by ``deploy/cg32/api_server.py``.
- E2E: first ES ``_search`` poll that returns the document (refresh included).
"""

import argparse
import csv
import hashlib
import json
import math
import os
import statistics
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path

HEADER = (
    "timestamp,machine_id,machine_type,air_temp_K,process_temp_K,rpm,torque_Nm,"
    "tool_wear_min,machine_failure,failure_TWF,failure_HDF,failure_PWF,"
    "failure_OSF,failure_RNF"
)
SENSORS = ("air_temp_K", "process_temp_K", "rpm", "torque_Nm", "tool_wear_min")
LABELS = (
    "machine_failure",
    "failure_TWF",
    "failure_HDF",
    "failure_PWF",
    "failure_OSF",
    "failure_RNF",
)
BASE_TIME = datetime(2026, 10, 23, tzinfo=UTC)
MAX_RATE = 50
MAX_DURATION = 60


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def utc(ts):
    return datetime.fromtimestamp(ts, UTC).isoformat().replace("+00:00", "Z")


def nominal_rows(source, count):
    """First ``count`` nominal rows (all labels 0) of the development CSV."""
    rows = []
    with Path(source).open(newline="") as handle:
        for row in csv.DictReader(handle):
            if any(row[label] != "0" for label in LABELS):
                continue
            if row["machine_type"] not in ("H", "M", "L"):
                continue
            rows.append(row)
            if len(rows) == count:
                return rows
    raise ValueError(f"Only {len(rows)} nominal rows available, {count} required")


def fixture_lines(source, count):
    """Deterministic CSV lines: unique per index, identical across repetitions."""
    lines = []
    for index, row in enumerate(nominal_rows(source, count)):
        stamp = (BASE_TIME + timedelta(seconds=index)).strftime("%Y-%m-%dT%H:%M:%SZ")
        values = [stamp, row["machine_id"], row["machine_type"]]
        values += [row[name] for name in SENSORS] + ["0"] * len(LABELS)
        lines.append(",".join(values))
    return lines


def fixture_hash(lines):
    return sha256(("\n".join(lines) + "\n").encode())


def line_key(line):
    """Content identity of one offered row (index is encoded in its timestamp)."""
    return sha256(line.encode())


def validate_plan(rate, duration):
    if type(rate) is not int or not 1 <= rate <= MAX_RATE:
        raise ValueError(f"rate must be an integer in 1..{MAX_RATE}")
    if type(duration) is not int or not 1 <= duration <= MAX_DURATION:
        raise ValueError(f"duration must be an integer in 1..{MAX_DURATION}")
    return rate * duration


def offer(path, lines, rate, *, clock=time.monotonic, wall=time.time, sleep=None):
    """Append ``lines`` at a fixed schedule; never overwrite an existing file.

    The header and first line are written together so Filebeat's 228-byte
    fingerprint window is satisfied before the first scheduled instant.
    Returns one record per line with scheduled/actual instants.
    """
    sleep = sleep or time.sleep
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_APPEND, 0o644)
    records = []
    try:
        start = clock()
        start_wall = wall()
        for index, line in enumerate(lines):
            scheduled = start + index / rate
            delay = scheduled - clock()
            if delay > 0:
                sleep(delay)
            payload = (line + "\n").encode()
            if index == 0:
                payload = (HEADER + "\n").encode() + payload
            os.write(fd, payload)
            os.fsync(fd)
            now = clock()
            records.append(
                {
                    "index": index,
                    "key": line_key(line),
                    "scheduled_offset_s": index / rate,
                    "written_mono": now,
                    "written_utc": utc(start_wall + (now - start)),
                    "producer_lag_ms": (now - scheduled) * 1000,
                }
            )
    finally:
        os.close(fd)
    return records


def nearest_rank(values, pct):
    if not values:
        return None
    ordered = sorted(values)
    return ordered[max(0, math.ceil(pct / 100 * len(ordered)) - 1)]


def percentiles(values):
    return {
        "n": len(values),
        "p50": nearest_rank(values, 50),
        "p95": nearest_rank(values, 95),
        "max": max(values) if values else None,
    }


def dispersion(values):
    values = [v for v in values if v is not None]
    if not values:
        return None
    return {
        "n": len(values),
        "mean": statistics.fmean(values),
        "median": statistics.median(values),
        "min": min(values),
        "max": max(values),
        "stdev": statistics.stdev(values) if len(values) > 1 else None,
    }


def reconcile(offered, kafka_records, jobs, es_docs, committed=None):
    """Per-occurrence accounting and ID-set checks.

    offered: [{key}] rows written by the driver.
    kafka_records: [{offset, key}] raw topic content (line hash per offset).
    jobs: {record_ref: outcome or None} from the worker journal.
    es_docs: {record_ref: event_id} documents found in the run index.
    committed: group offset at the end. Unobserved records at or after it are
    retained backlog (still replayable), not loss; before it they are lost.
    """
    offered_keys = [r["key"] for r in offered]
    by_key = {}
    for record in kafka_records:
        by_key.setdefault(record["key"], []).append(record["offset"])
    unexpected = sorted(set(by_key) - set(offered_keys))
    missing_in_kafka = sorted(set(offered_keys) - set(by_key))
    repeated_in_kafka = {k: v for k, v in by_key.items() if len(v) > 1}
    outcome = {"saved": 0, "rejected": 0, "pending": 0}
    for value in jobs.values():
        outcome[
            {"completed": "saved", "rejected": "rejected", None: "pending"}[value]
        ] += 1
    observed = len(jobs)
    refs = {f"{r['topic']}/{r['partition']}/{r['offset']}" for r in kafka_records}
    saved_refs = {ref for ref, value in jobs.items() if value == "completed"}
    event_ids = list(es_docs.values())
    unobserved = [
        r["offset"]
        for r in kafka_records
        if f"{r['topic']}/{r['partition']}/{r['offset']}" not in jobs
    ]
    # Unknown committed offset: conservatively count every unobserved as lost.
    backlog = 0 if committed is None else sum(1 for o in unobserved if o >= committed)
    return {
        "offered": len(offered_keys),
        "offered_unique": len(set(offered_keys)),
        "kafka_records": len(kafka_records),
        "kafka_missing_offered": len(missing_in_kafka),
        "kafka_unexpected": len(unexpected),
        "kafka_repeated_lines": sum(len(v) - 1 for v in repeated_in_kafka.values()),
        "observed": observed,
        **outcome,
        "balance_ok": observed
        == outcome["saved"] + outcome["rejected"] + outcome["pending"],
        "jobs_not_in_kafka": len(set(jobs) - refs),
        "kafka_not_observed": len(refs - set(jobs)),
        "backlog_uncommitted": backlog,
        "es_docs": len(es_docs),
        "es_duplicate_event_ids": len(event_ids) - len(set(event_ids)),
        "saved_missing_in_es": len(saved_refs - set(es_docs)),
        "es_without_saved_job": len(set(es_docs) - saved_refs),
        "valid_lost": len(missing_in_kafka)
        + (len(unobserved) - backlog)
        + len(saved_refs - set(es_docs)),
    }


def e2e_latencies(offered, kafka_records, first_seen):
    """written -> first ES poll with the doc, per offered row (ms)."""
    written = {r["key"]: r["written_mono"] for r in offered}
    values = []
    for record in kafka_records:
        ref = f"{record['topic']}/{record['partition']}/{record['offset']}"
        if ref in first_seen and record["key"] in written:
            values.append((first_seen[ref] - written[record["key"]]) * 1000)
    return values


def summarize(runs):
    """Group runs by rate; percentiles stay per run, dispersion across runs."""
    grouped = {}
    for run in runs:
        grouped.setdefault(run["rate"], []).append(run)
    summary = {}
    for rate, items in sorted(grouped.items()):
        summary[str(rate)] = {
            "runs": len(items),
            "fixture_hashes": sorted({i["fixture_sha256"] for i in items}),
            **{
                metric: dispersion([i["metrics"].get(metric) for i in items])
                for metric in (
                    "throughput_eps",
                    "http_p50_ms",
                    "http_p95_ms",
                    "e2e_p50_ms",
                    "e2e_p95_ms",
                    "lag_max",
                    "drain_s",
                )
            },
        }
    return summary


def write_new(path, data):
    """Exclusive create: never overwrite evidence."""
    with Path(path).open("x") as handle:
        json.dump(data, handle, indent=2, sort_keys=True)
        handle.write("\n")


def main(argv=None):
    cli = argparse.ArgumentParser(description=__doc__)
    sub = cli.add_subparsers(dest="command", required=True)
    fx = sub.add_parser("fixture", help="write the deterministic fixture")
    fx.add_argument("--source", type=Path, default=Path("data/ai4i2020_train.csv"))
    fx.add_argument("--count", type=int, required=True)
    fx.add_argument("--output", type=Path, required=True)
    sm = sub.add_parser("summarize", help="dispersion across run JSON files")
    sm.add_argument("runs", nargs="+", type=Path)
    sm.add_argument("--output", type=Path, required=True)
    args = cli.parse_args(argv)
    if args.command == "fixture":
        lines = fixture_lines(args.source, args.count)
        with args.output.open("x") as handle:
            handle.write("\n".join(lines) + "\n")
        print(json.dumps({"rows": len(lines), "sha256": fixture_hash(lines)}))
    else:
        runs = [json.loads(p.read_text()) for p in args.runs]
        write_new(args.output, summarize(runs))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
