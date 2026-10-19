"""Export a local draft review calendar from JSON predictions, never send invites."""

import argparse
import csv
import json
from pathlib import Path

from planning.maintenance import build_plan, instant


def export_plan(plan, directory):
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=False)
    (directory / "plan.json").write_text(json.dumps(plan, indent=2) + "\n")
    fields = [
        "task_id",
        "machine_id",
        "priority",
        "status",
        "action",
        "proposed_start",
        "proposed_end",
        "review_due_at",
        "review_deadline_missed",
        "eta_minutes",
    ]
    with (directory / "reviews.csv").open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(plan["tasks"])
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//CNC Guard//Lab draft//EN",
        "CALSCALE:GREGORIAN",
    ]
    for task in plan["tasks"]:
        # UID contains only a deterministic hex identifier; no untrusted ICS text.
        lines.extend(
            [
                "BEGIN:VEVENT",
                f"UID:{task['task_id']}@cnc-guard.lab",
                "DTSTAMP:" + instant(plan["as_of"]).strftime("%Y%m%dT%H%M%SZ"),
                "DTSTART:" + instant(task["proposed_start"]).strftime("%Y%m%dT%H%M%SZ"),
                "DTEND:" + instant(task["proposed_end"]).strftime("%Y%m%dT%H%M%SZ"),
                "SUMMARY:DRAFT - review data and risk",
                "STATUS:TENTATIVE",
                "DESCRIPTION:Human review pending. Not a predicted failure time.",
                "END:VEVENT",
            ]
        )
    lines.append("END:VCALENDAR")
    (directory / "reviews-draft.ics").write_bytes(
        ("\r\n".join(lines) + "\r\n").encode()
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--predictions", type=Path, required=True)
    parser.add_argument("--as-of", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    plan = build_plan(json.loads(args.predictions.read_text()), args.as_of)
    export_plan(plan, args.output)
    print(
        json.dumps(
            {
                "tasks": len(plan["tasks"]),
                "output": str(args.output),
                "missed_deadlines": sum(
                    t["review_deadline_missed"] for t in plan["tasks"]
                ),
            }
        )
    )


if __name__ == "__main__":
    main()
