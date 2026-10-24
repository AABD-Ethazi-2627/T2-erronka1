"""Local shadow workflow. No API deployment, timers, invites or physical actions."""

import argparse
import csv
import io
import json
from hashlib import sha256
from pathlib import Path

from planning.adaptive import validate_manifest
from planning.cycle import update_batch
from planning.online import OnlineForecaster, crossing_proposal, digest
from planning.registry import ShadowRegistry
from planning.selection import compare_candidates


def read_data(path, manifest):
    validate_manifest(manifest)
    raw = Path(path).read_bytes()
    reader = csv.DictReader(io.StringIO(raw.decode("utf-8-sig")))
    fields = reader.fieldnames or []
    required = [
        *manifest["columns"].values(),
        *(v["column"] for v in manifest["sensors"].values()),
    ]
    if len(set(fields)) != len(fields) or any(k not in fields for k in required):
        raise ValueError("Missing or ambiguous mapped CSV columns")
    rows = list(reader)
    if not rows:
        raise ValueError("Empty observation dataset")
    for row in rows:
        if None in row or any(row[k] is None for k in required):
            raise ValueError("Malformed CSV row")
        for spec in manifest["sensors"].values():
            row[spec["column"]] = float(row[spec["column"]])
    return rows, sha256(raw).hexdigest()


def write_output(path, value):
    encoded = json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n"
    path = Path(path)
    path.mkdir(parents=True, exist_ok=False)
    (path / "result.json").write_text(encoded)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("train", "update", "propose"):
        sub = commands.add_parser(name)
        sub.add_argument("--manifest", type=Path, required=True)
        sub.add_argument("--output", type=Path, required=True)
        if name in ("train", "update"):
            sub.add_argument("--data", type=Path, required=True)
        if name in ("update", "propose"):
            sub.add_argument("--checkpoint", type=Path)
        if name == "train":
            sub.add_argument("--registry", type=Path)
            sub.add_argument("--horizon-minutes", type=float, default=5)
            sub.add_argument("--champion-alpha", type=float)
        if name == "update":
            sub.add_argument("--batch-id", required=True)
        if name == "propose":
            sub.add_argument("--limits", type=Path, required=True)
            sub.add_argument("--asset", required=True)
            sub.add_argument("--lifecycle", required=True)
    for name in ("status", "activate", "rollback"):
        sub = commands.add_parser(name)
        sub.add_argument("--registry", type=Path, required=True)
        if name != "status":
            sub.add_argument(
                "--expected-active", required=True, help="64-char ID or none"
            )
            sub.add_argument("--actor", required=True)
            sub.add_argument("--reason", required=True)
        if name == "activate":
            sub.add_argument("--version", required=True)
    args = parser.parse_args()
    if args.command in ("status", "activate", "rollback"):
        registry = ShadowRegistry(args.registry)
        if args.command == "activate":
            registry.activate(
                args.version,
                expected_active=None
                if args.expected_active == "none"
                else args.expected_active,
                actor=args.actor,
                reason=args.reason,
            )
        elif args.command == "rollback":
            registry.rollback(
                expected_active=None
                if args.expected_active == "none"
                else args.expected_active,
                actor=args.actor,
                reason=args.reason,
            )
        print(json.dumps(registry.status()))
        return
    if args.output.exists():
        raise FileExistsError("Output directory already exists")
    manifest = json.loads(args.manifest.read_text())
    if args.command == "train":
        rows, source_hash = read_data(args.data, manifest)
        active = None
        champion_alpha = args.champion_alpha
        champion_snapshot = None
        if args.registry:
            registry = ShadowRegistry(args.registry)
            active = registry.status()["active"]
            if active:
                current = registry._load(active)
                if (
                    current["state"]["manifest_sha256"] != digest(manifest)
                    or current["state"]["horizon_minutes"] != args.horizon_minutes
                ):
                    raise ValueError(
                        "Dataset/schema/horizon changed; use a separate shadow registry"
                    )
                if (
                    champion_alpha is not None
                    and champion_alpha != current["state"]["alpha"]
                ):
                    raise ValueError(
                        "Explicit champion settings do not match active version"
                    )
                champion_alpha = current["state"]["alpha"]
                champion_snapshot = current["state"]
        result = compare_candidates(
            rows,
            manifest,
            horizon_minutes=args.horizon_minutes,
            champion_alpha=champion_alpha,
            champion_snapshot=champion_snapshot,
        )
        result["compared_shadow_version"] = active
        result["source_sha256"] = source_hash
        if args.registry:
            result["staged_version"] = ShadowRegistry(args.registry).stage(
                result, result["state_after_acceptance"]
            )
    else:
        checkpoint = (
            json.loads(args.checkpoint.read_text()) if args.checkpoint else None
        )
        if args.command == "update":
            rows, source_hash = read_data(args.data, manifest)
            result = update_batch(
                rows,
                manifest,
                batch_id=args.batch_id,
                source_hash=source_hash,
                checkpoint=checkpoint,
            )
        else:
            if checkpoint is None:
                raise ValueError("Checkpoint required for proposal")
            snapshot = checkpoint.get(
                "state", checkpoint.get("state_after_acceptance", checkpoint)
            )
            model = OnlineForecaster.restore(snapshot, manifest)
            result = crossing_proposal(
                model, args.asset, args.lifecycle, json.loads(args.limits.read_text())
            )
    write_output(args.output, result)
    print(
        json.dumps(
            {
                "command": args.command,
                "output": str(args.output),
                "scope": "LAB_SHADOW_ONLY",
            }
        )
    )


if __name__ == "__main__":
    main()
