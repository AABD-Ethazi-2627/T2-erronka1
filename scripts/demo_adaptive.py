"""Deterministic synthetic fixture: not industrial degradation evidence."""

import argparse
import csv
from datetime import UTC, datetime, timedelta
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    with (args.output / "observations.csv").open("w", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["asset_id", "component_cycle", "event_time", "wear_minutes"],
        )
        writer.writeheader()
        for scenario in ["steady", "reversal", "flat"]:
            for minute in range(120):
                value = (
                    10 + 2 * minute
                    if scenario == "steady"
                    else 10 + 2 * minute
                    if scenario == "reversal" and minute < 60
                    else 248 - 2 * minute
                    if scenario == "reversal"
                    else 10
                )
                writer.writerow(
                    {
                        "asset_id": scenario,
                        "component_cycle": "fixture-only",
                        "event_time": (
                            datetime(2026, 1, 1, tzinfo=UTC) + timedelta(minutes=minute)
                        ).isoformat(),
                        "wear_minutes": value,
                    }
                )
    print(args.output / "observations.csv")


if __name__ == "__main__":
    main()
