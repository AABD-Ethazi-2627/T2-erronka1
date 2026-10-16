"""Offline, standard-library-only CG02 inventory. Never reads .env or the network.

python -m scripts.audit_cg02 --write   # regenerate derived inventory
python -m scripts.audit_cg02 --check   # verify bytes and measured results
"""

import argparse
import csv
import hashlib
import io
import json
import math
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

SENSORS = ["air_temp_K", "process_temp_K", "rpm", "torque_Nm", "tool_wear_min"]
SUBTYPES = ["failure_TWF", "failure_HDF", "failure_PWF", "failure_OSF", "failure_RNF"]
LABELS = ["machine_failure"] + SUBTYPES
TRAIN_COLUMNS = ["machine_id", "machine_type"] + SENSORS + LABELS
ROOT = Path(__file__).resolve().parents[1]


def audit_csv(path, kind):
    content = Path(path).read_bytes()
    text = content.decode("utf-8-sig")
    parsed = list(csv.reader(io.StringIO(text, newline="")))
    expected = TRAIN_COLUMNS if kind == "training" else ["timestamp"] + TRAIN_COLUMNS
    if not parsed or parsed[0] != expected:
        raise ValueError(f"Unexpected columns: {Path(path).name}")
    header = parsed[0]
    raw_rows = parsed[1:]
    if not raw_rows:
        raise ValueError(f"Empty dataset: {Path(path).name}")
    rows = [dict(zip(header, row)) for row in raw_rows]
    missing = {c: sum(not row.get(c, "").strip() for row in rows) for c in header}
    numeric = {}
    invalid = {}
    out_of_range = {}
    for c in SENSORS + LABELS:
        values = []
        bad = 0
        outside = 0
        for row in rows:
            value = row.get(c, "").strip()
            if not value:
                continue
            try:
                number = float(value)
                if not math.isfinite(number):
                    raise ValueError("Non-finite number")
            except ValueError:
                bad += 1
                continue
            values.append(number)
            if c in LABELS:
                outside += number not in (0, 1)
            elif c.endswith("_K"):
                outside += number <= 0
            else:
                outside += number < 0
        numeric[c] = {
            "min": min(values) if values else None,
            "max": max(values) if values else None,
        }
        invalid[c] = bad
        out_of_range[c] = outside
    counts = {
        c: dict(sorted(Counter(row.get(c, "") for row in rows).items())) for c in LABELS
    }
    report = {
        "bytes": len(content),
        "sha256": hashlib.sha256(content).hexdigest(),
        "encoding": "utf-8-sig" if content.startswith(b"\xef\xbb\xbf") else "utf-8",
        "delimiter": ",",
        "has_header": True,
        "columns": header,
        "rows": len(rows),
        "malformed_row_widths": sum(len(row) != len(header) for row in raw_rows),
        "missing": missing,
        "invalid_numeric": invalid,
        "invalid_numeric_domain": out_of_range,
        "numeric_ranges": numeric,
        "label_counts": counts,
        "machine_types": dict(
            sorted(Counter(row.get("machine_type", "") for row in rows).items())
        ),
        "machines": len({row.get("machine_id") for row in rows}),
        "duplicate_rows": len(raw_rows) - len({tuple(row) for row in raw_rows}),
        "failure_without_subtype": sum(
            row.get("machine_failure") == "1"
            and all(row.get(c) == "0" for c in SUBTYPES)
            for row in rows
        ),
        "subtype_without_failure": sum(
            row.get("machine_failure") == "0"
            and any(row.get(c) == "1" for c in SUBTYPES)
            for row in rows
        ),
        "time": None,
    }
    if kind == "batch":
        valid = []
        bad = 0
        backward = 0
        previous = {}
        groups = defaultdict(list)
        for row in rows:
            value = row.get("timestamp", "")
            try:
                if not value.endswith("Z"):
                    raise ValueError("Not UTC Z")
                timestamp = datetime.fromisoformat(value)
            except ValueError:
                bad += 1
                continue
            valid.append(timestamp)
            machine = row.get("machine_id", "")
            if machine in previous and timestamp < previous[machine]:
                backward += 1
            previous[machine] = timestamp
            groups[(machine, timestamp)].append(
                tuple(row.get(c) for c in SENSORS + ["machine_type"])
            )
        fmt = lambda t: t.isoformat().replace("+00:00", "Z")
        report["time"] = {
            "min": fmt(min(valid)) if valid else None,
            "max": fmt(max(valid)) if valid else None,
            "invalid_or_non_utc_rows": bad,
            "backward_rows_per_machine_in_file": backward,
            "duplicate_machine_timestamp_rows": sum(
                len(values) - 1 for values in groups.values()
            ),
            "conflicting_machine_timestamp_groups": sum(
                len(set(values)) > 1 for values in groups.values()
            ),
            "failure_timestamps": [
                row.get("timestamp")
                for row in rows
                if row.get("machine_failure") == "1"
            ],
        }
        report["per_machine"] = {}
        for machine in sorted({row.get("machine_id", "") for row in rows}):
            selected = [row for row in rows if row.get("machine_id", "") == machine]
            report["per_machine"][machine] = {
                "rows": len(selected),
                "positive_rows": sum(
                    row.get("machine_failure") == "1" for row in selected
                ),
                "timestamps": sorted({row.get("timestamp", "") for row in selected}),
            }
    if Path(path).read_bytes() != content:
        raise ValueError("Source changed while auditing")
    return report


def compare_signatures(training_rows, batch_rows):
    # Contemporaneous sensor/label signatures; IDs and emission dates do not add novelty.
    def signature(row):
        return (row["machine_type"],) + tuple(float(row[c]) for c in SENSORS + LABELS)

    training = {signature(row) for row in training_rows}
    signatures = [signature(row) for row in batch_rows]
    counts = Counter(signatures)
    return {
        "comparison_columns": ["machine_type"] + SENSORS + LABELS,
        "excluded_columns": ["machine_id", "timestamp"],
        "distinct_sensor_label_signatures": len(counts),
        "repeated_rows_beyond_first_signature": sum(
            value - 1 for value in counts.values()
        ),
        "rows_matching_training_signature": sum(
            value in training for value in signatures
        ),
        "interpretation": "Exact signature overlap only; zero overlap does not prove statistical independence.",
    }


def build_inventory(root):
    root = Path(root)
    train_path = root / "data/ai4i2020_train.csv"
    training = {
        "file": str(train_path.relative_to(root)),
        **audit_csv(train_path, "training"),
    }
    samples = sorted((root / "docs/requisitos/evidencias/muestras").glob("*.csv"))
    if not samples:
        raise ValueError("No frozen SMB evidence found")
    batches = [
        {"file": str(path.relative_to(root)), **audit_csv(path, "batch")}
        for path in samples
    ]
    with train_path.open() as handle:
        train_rows = list(csv.DictReader(handle))
    batch_rows = []
    for sample in samples:
        with sample.open() as handle:
            batch_rows.extend(csv.DictReader(handle))
    overlap = compare_signatures(train_rows, batch_rows)
    days = sorted({b["time"]["min"][:10] for b in batches if b["time"]["min"]})
    return {
        "schema_version": "1.0.0",
        "source_catalog_sha256": hashlib.sha256(
            (root / "docs/cg02/sources.json").read_bytes()
        ).hexdigest(),
        "training": training,
        "batches": batches,
        "batch_summary": {
            "files": len(batches),
            "rows": sum(b["rows"] for b in batches),
            "days_observed": days,
            "machine_ids_observed": sorted(
                {m for b in batches for m in b["per_machine"]}
            ),
            "min_timestamp": min(b["time"]["min"] for b in batches if b["time"]["min"]),
            "max_timestamp": max(b["time"]["max"] for b in batches if b["time"]["max"]),
        },
        "signature_overlap": overlap,
        "roles": {
            "training": "Local AI4I train CSV only; timestamps absent.",
            "operational_logs": "Frozen SMB batches; operational machine observations in this simulated lab.",
            "retention": "SMB has no retention guarantee per user; own historical storage is CG06.",
            "maintenance": "No independent maintenance ledger supplied for this audit.",
        },
        "decision": {
            "state_classification": "supported_by_contemporaneous_machine_failure_labels",
            "forecast_24h": "not_validated",
            "reasons": [
                "Training CSV has no timestamps.",
                "Batch time is simulator emission time; no complete per-machine 24h follow-up.",
                "Failure bits are contemporaneous outcomes, not independent dated maintenance/failure onsets.",
                "Stream lineage/overlap with training and stable machine identity over time are not established.",
            ],
        },
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--write", action="store_true")
    group.add_argument("--check", action="store_true")
    args = parser.parse_args()
    inventory = build_inventory(ROOT)
    path = ROOT / "docs/cg02/inventory.json"
    if args.write:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(inventory, indent=2, allow_nan=False) + "\n")
        print("Wrote derived docs/cg02/inventory.json; source files unchanged")
    else:
        if not path.exists() or json.loads(path.read_text()) != inventory:
            raise SystemExit(
                "CG02 inventory differs or is missing; inspect inputs before --write"
            )
        print(
            "CG02 inventory verified offline: source bytes, quality, labels and time coverage match"
        )
