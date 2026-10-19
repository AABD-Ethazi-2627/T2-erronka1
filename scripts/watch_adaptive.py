"""Consume explicitly ready local lab batches; continuous polling is opt-in."""

import argparse
import fcntl
import json
import os
import tempfile
import time
from hashlib import sha256
from pathlib import Path

from planning.cycle import update_batch
from planning.online import OnlineForecaster, digest
from scripts.adaptive_cycle import read_data


def atomic_json(path, value):
    encoded = json.dumps(value, sort_keys=True, allow_nan=False) + "\n"
    with tempfile.NamedTemporaryFile(mode="w", dir=path.parent, delete=False) as handle:
        handle.write(encoded)
        handle.flush()
        os.fsync(handle.fileno())
        temporary = handle.name
    os.replace(temporary, path)


def run_once(inbox, manifest_path, work, *, seed=None):
    inbox, work = Path(inbox).resolve(), Path(work).resolve()
    if inbox == work or inbox in work.parents or work in inbox.parents:
        raise ValueError("Keep inbox and checkpoint directories separate")
    work.mkdir(parents=True, exist_ok=True)
    manifest = json.loads(Path(manifest_path).read_text())
    processed = 0
    with (work / "worker.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        checkpoint_path = work / "checkpoint.json"
        checkpoint = (
            json.loads(checkpoint_path.read_text())
            if checkpoint_path.exists()
            else None
        )
        if checkpoint is None and seed is not None:
            initial = json.loads(Path(seed).read_text())
            snapshot = initial.get(
                "state", initial.get("state_after_acceptance", initial)
            )
            OnlineForecaster.restore(snapshot, manifest)
            checkpoint = {
                "schema_version": 1,
                "state": snapshot,
                "processed_batches": {},
                "last_batch_evaluation": [],
                "scope": "LAB_SHADOW_ONLY",
                "runtime_promotion_allowed": False,
            }
        if checkpoint:
            OnlineForecaster.restore(checkpoint["state"], manifest)
        for ready in sorted(inbox.glob("*.ready")):
            descriptor = json.loads(ready.read_text())
            name = descriptor.get("csv")
            expected = descriptor.get("sha256")
            if (
                not isinstance(name, str)
                or Path(name).name != name
                or not name.endswith(".csv")
            ):
                raise ValueError("Ready descriptor must name a local CSV basename")
            source = inbox / name
            if source.is_symlink() or source.stat().st_size > 32 * 1024 * 1024:
                raise ValueError("Symlinks and batches over32MiB are not supported")
            if sha256(source.read_bytes()).hexdigest() != expected:
                raise ValueError("Batch does not match producer ready hash")
            if checkpoint and ready.name in checkpoint["processed_batches"]:
                if checkpoint["processed_batches"][ready.name] != expected:
                    raise ValueError("Previously processed batch descriptor changed")
                continue
            rows, actual = read_data(source, manifest)
            if actual != expected:
                raise ValueError("Batch changed while reading")
            updated = update_batch(
                rows,
                manifest,
                batch_id=ready.name,
                source_hash=actual,
                checkpoint=checkpoint,
            )
            result = {
                "prior_checkpoint_sha256": digest(checkpoint),
                "checkpoint": updated,
                "source_sha256": actual,
                "batch_id": ready.name,
            }
            results = work / "results"
            results.mkdir(exist_ok=True)
            destination = results / (digest([ready.name, actual]) + ".json")
            if destination.exists():
                if digest(json.loads(destination.read_text())) != digest(result):
                    raise ValueError(
                        "Recovery output conflicts with current checkpoint"
                    )
            else:
                atomic_json(destination, result)
            atomic_json(checkpoint_path, updated)
            checkpoint = updated
            processed += 1
    return {
        "processed": processed,
        "scope": "LAB_SHADOW_ONLY",
        "runtime_promotion_allowed": False,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inbox", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--work", type=Path, required=True)
    parser.add_argument(
        "--seed",
        type=Path,
        help="Selected model state used only when no checkpoint exists",
    )
    parser.add_argument(
        "--watch",
        action="store_true",
        help="Explicitly keep polling; no auto-install of a timer",
    )
    parser.add_argument("--poll-seconds", type=int, default=30)
    args = parser.parse_args()
    if not 1 <= args.poll_seconds <= 60:
        parser.error("poll-seconds must be1..60")
    while True:
        print(
            json.dumps(run_once(args.inbox, args.manifest, args.work, seed=args.seed)),
            flush=True,
        )
        if not args.watch:
            break
        time.sleep(args.poll_seconds)


if __name__ == "__main__":
    main()
