"""Read an immutable SMB snapshot and score latest per-ID records in the local API."""

import argparse
import csv
import hashlib
import json
from pathlib import Path

import httpx

from planning.maintenance import build_plan, instant
from scripts.plan_maintenance import export_plan


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    latest = {}
    for path in sorted((args.snapshot / "raw").glob("*.csv")):
        with path.open() as handle:
            for index, row in enumerate(csv.DictReader(handle), 1):
                key = (row["timestamp"], path.name, index)
                if (
                    row["machine_id"] not in latest
                    or key > latest[row["machine_id"]][0]
                ):
                    latest[row["machine_id"]] = (key, row)
    if not latest:
        raise ValueError("No snapshot rows")
    predictions = []
    with httpx.Client(base_url="http://127.0.0.1:18001", timeout=10) as client:
        for key, row in sorted(latest.values()):
            payload = {
                "event_id": hashlib.sha256(
                    f"planner-preview:{key}".encode()
                ).hexdigest(),
                "machine_id": row["machine_id"],
                "machine_type": row["machine_type"],
                "timestamp": row["timestamp"],
                "schema_version": "0.1.0",
                "quality_flag": "OK",
                "source": {
                    "kind": "smb_csv",
                    "uri": "smb://192.168.75.150/cnc-stream",
                    "record_ref": f"{key[1]}:data-row-{key[2]}",
                },
            }
            for field in [
                "air_temp_K",
                "process_temp_K",
                "rpm",
                "torque_Nm",
                "tool_wear_min",
            ]:
                payload[field] = float(row[field])
            response = client.post("/predict", json=payload)
            response.raise_for_status()
            result = response.json()
            result["source_kind"] = "smb_csv"
            predictions.append(result)
    as_of = max(instant(p["timestamp"]) for p in predictions)
    plan = build_plan(predictions, as_of)
    plan["selection"] = (
        "Latest timestamp per unverified ID; filename/row "
        + "tie-break. Not a conflict resolution or temporal "
        + "history."
    )
    plan["snapshot"] = str(args.snapshot)
    export_plan(plan, args.output)
    (args.output / "predictions.json").write_text(
        json.dumps(predictions, indent=2) + "\n"
    )
    print(
        json.dumps(
            {
                "scored_ids": len(predictions),
                "tasks": len(plan["tasks"]),
                "as_of": as_of.isoformat(),
                "priorities": {
                    p: sum(t["priority"] == p for t in plan["tasks"])
                    for p in ["P1", "P2", "P3"]
                },
                "missed_deadlines": sum(
                    t["review_deadline_missed"] is True for t in plan["tasks"]
                ),
            }
        )
    )


if __name__ == "__main__":
    main()
