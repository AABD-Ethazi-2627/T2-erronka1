"""Reproduce the full workflow on explicitly synthetic data; no runtime deployment."""

import argparse
import csv
import json
import subprocess
import sys
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    root = args.output
    root.mkdir(parents=True, exist_ok=False)
    manifest = json.loads(Path("contracts/examples/adaptive/manifest.json").read_text())
    manifest["dataset_id"] = "synthetic-adaptive-cycle-v1"
    config = root / "manifest.json"
    config.write_text(json.dumps(manifest, indent=2))
    fields = ["asset_id", "event_time", "component_cycle", "wear_minutes"]

    def write_csv(path, observations):
        with path.open("w", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fields)
            writer.writeheader()
            writer.writerows(observations)

    series = []
    for day in (1, 2):
        observations = [
            {
                "asset_id": "SIM-001",
                "component_cycle": "fixture-only",
                "event_time": (
                    datetime(2026, 1, day, tzinfo=UTC) + timedelta(minutes=i)
                ).isoformat(),
                "wear_minutes": 10.0 + (2 * i if day == 1 else 0.02 * i * i),
            }
            for i in range(400)
        ]
        source = root / f"phase{day}.csv"
        write_csv(source, observations)
        series.append(observations)

    def call(*arguments):
        subprocess.run(
            [sys.executable, "-m", "scripts.adaptive_cycle", *map(str, arguments)],
            check=True,
            capture_output=True,
            text=True,
        )

    registry = root / "registry"
    call(
        "train",
        "--data",
        root / "phase1.csv",
        "--manifest",
        config,
        "--registry",
        registry,
        "--output",
        root / "training1",
    )
    first = json.loads((root / "training1/result.json").read_text())
    call(
        "activate",
        "--registry",
        registry,
        "--version",
        first["staged_version"],
        "--expected-active",
        "none",
        "--actor",
        "synthetic-lab-agent",
        "--reason",
        "Synthetic integration fixture only",
    )
    call(
        "train",
        "--data",
        root / "phase2.csv",
        "--manifest",
        config,
        "--registry",
        registry,
        "--output",
        root / "training2",
    )
    second = json.loads((root / "training2/result.json").read_text())
    call(
        "activate",
        "--registry",
        registry,
        "--version",
        second["staged_version"],
        "--expected-active",
        first["staged_version"],
        "--actor",
        "synthetic-lab-agent",
        "--reason",
        "Second synthetic fixture beats shadow champion",
    )
    call(
        "rollback",
        "--registry",
        registry,
        "--expected-active",
        second["staged_version"],
        "--actor",
        "synthetic-lab-agent",
        "--reason",
        "Explicit synthetic rollback test",
    )
    next_row = dict(
        series[1][-1], event_time="2026-01-02T06:40:00Z", wear_minutes=3210.0
    )
    write_csv(root / "next.csv", [next_row])
    call(
        "update",
        "--data",
        root / "next.csv",
        "--manifest",
        config,
        "--checkpoint",
        root / "training2/result.json",
        "--batch-id",
        "next",
        "--output",
        root / "continued",
    )
    limits = {
        "wear": {
            "upper": 3500,
            "unit": "min",
            "source": (
                "Synthetic integration fixture threshold; not a "
                + "physical specification"
            ),
        }
    }
    (root / "limits.json").write_text(json.dumps(limits))
    call(
        "propose",
        "--manifest",
        config,
        "--checkpoint",
        root / "continued/result.json",
        "--limits",
        root / "limits.json",
        "--asset",
        "SIM-001",
        "--lifecycle",
        "fixture-only",
        "--output",
        root / "proposal",
    )
    inbox = root / "inbox"
    inbox.mkdir()
    for number, observations in enumerate((series[0][:200], series[0][200:])):
        batch = inbox / f"batch{number}.csv"
        write_csv(batch, observations)
        (inbox / f"batch{number}.ready").write_text(
            json.dumps(
                {"csv": batch.name, "sha256": sha256(batch.read_bytes()).hexdigest()}
            )
        )
    subprocess.run(
        [
            sys.executable,
            "-m",
            "scripts.watch_adaptive",
            "--inbox",
            str(inbox),
            "--manifest",
            str(config),
            "--work",
            str(root / "worker"),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    proposal = json.loads((root / "proposal/result.json").read_text())
    summary = {
        "scope": "SYNTHETIC_INTEGRATION_ONLY",
        "first_alpha": first["selected_alpha"],
        "first_decision": first["lab_decision"],
        "second_alpha": second["selected_alpha"],
        "second_decision": second["lab_decision"],
        "second_baseline": second["baseline_kind"],
        "second_acceptance": second["acceptance"],
        "review_window": proposal["model_review_window"],
        "failure_eta_minutes": None,
        "rollback_tested": True,
        "active_version": json.loads((registry / "pointer.json").read_text())["active"],
        "original_version": first["staged_version"],
        "runtime_promotion_allowed": False,
    }
    (root / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary))


if __name__ == "__main__":
    main()
