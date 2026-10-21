"""Offline retention of frozen batches; does not connect to SMB or invent dates."""

import argparse
import hashlib
import json
from pathlib import Path

import duckdb
import pandas as pd

from scripts.audit_cg02 import audit_csv
from scripts.verify_history import verify


def retain(sources, output):
    output = Path(output)
    if (output / "manifest.json").exists():
        if not verify(output):
            raise ValueError(
                "Prior history is inconsistent; preserve evidence, do not rebaseline"
            )
    elif output.exists() and any(output.rglob("*")):
        raise ValueError(
            "Nonempty history without manifest requires explicit reconciliation"
        )
    prepared = {}
    # Validate the complete batch before any write. IDs are file hash + row ordinal,
    # not machine/time, which is demonstrably non-unique in the classroom stream.
    for source in sorted(map(Path, sources)):
        raw = source.read_bytes()
        report = audit_csv(source, "batch")
        if (
            report["malformed_row_widths"]
            or any(report["missing"].values())
            or any(report["invalid_numeric"].values())
            or any(report["invalid_numeric_domain"].values())
            or report["time"]["invalid_or_non_utc_rows"]
        ):
            raise ValueError(f"Invalid batch: {source.name}")
        digest = hashlib.sha256(raw).hexdigest()
        frame = pd.read_csv(source)
        if not frame.machine_type.isin(["H", "M", "L"]).all():
            raise ValueError("Unknown machine type")
        if not frame.machine_id.str.fullmatch(r"CNC-\d{3}").all():
            raise ValueError("Invalid machine id")
        frame["timestamp"] = pd.to_datetime(frame.timestamp, utc=True)
        frame["source_sha256"] = digest
        frame["source_row"] = range(1, len(frame) + 1)
        frame["record_id"] = [f"{digest}:{i}" for i in frame.source_row]
        prepared[digest] = (raw, frame)
    if not prepared:
        raise ValueError("No batches supplied")
    # Refuse mutation of existing immutable Bronze objects.
    for digest, (raw, _) in prepared.items():
        path = output / "bronze" / f"{digest}.csv"
        if path.exists() and path.read_bytes() != raw:
            raise ValueError("Existing Bronze object is corrupt")
    for digest, (raw, frame) in prepared.items():
        bronze = output / "bronze" / f"{digest}.csv"
        bronze.parent.mkdir(parents=True, exist_ok=True)
        if not bronze.exists():
            with bronze.open("xb") as handle:
                handle.write(raw)
        for day, group in frame.groupby(frame.timestamp.dt.strftime("%Y-%m-%d")):
            target = output / "silver" / f"date={day}" / f"{digest}.parquet"
            target.parent.mkdir(parents=True, exist_ok=True)
            if target.exists():
                if not pd.read_parquet(target).equals(group.reset_index(drop=True)):
                    raise ValueError("Existing Silver object differs")
            else:
                group.reset_index(drop=True).to_parquet(target, index=False)
    # Recompute Gold from every retained Silver object, including previous runs.
    with duckdb.connect() as con:
        per_machine = con.execute(
            """SELECT machine_id, count(*) n,
            sum(machine_failure) positives, avg(rpm) mean_rpm
            FROM read_parquet(?) GROUP BY machine_id ORDER BY machine_id""",
            [str(output / "silver/**/*.parquet")],
        ).df()
        totals = con.execute(
            """SELECT count(*), count(DISTINCT record_id)
            FROM read_parquet(?)""",
            [str(output / "silver/**/*.parquet")],
        ).fetchone()
    gold = output / "gold"
    gold.mkdir(exist_ok=True)
    summary = gold / "machine_summary.parquet"
    # A writer upgrade can change Parquet bytes without changing the summary.
    # Preserve the verified artifact and its manifest hash on an identical ingest.
    if not summary.exists() or not pd.read_parquet(summary).equals(per_machine):
        per_machine.to_parquet(summary, index=False)
    files = sorted(
        p for p in output.rglob("*") if p.is_file() and p.suffix in {".csv", ".parquet"}
    )
    manifest = {
        "rows": totals[0],
        "unique_records": totals[1],
        "files": {
            str(p.relative_to(output)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in files
        },
        "meaning": (
            "Simulated batch observations, not physical machine "
            + "history or future labels"
        ),
    }
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    return manifest


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("historical"))
    args = parser.parse_args()
    result = retain(
        Path("docs/requisitos/evidencias/muestras").glob("*.csv"), args.output
    )
    print(json.dumps(result, indent=2))
