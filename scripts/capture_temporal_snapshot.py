"""Bounded read-only forensic snapshot, outside Filebeat inputs; no watch/scheduler."""

import argparse
import hashlib
import json
import tempfile
from datetime import UTC, datetime
from pathlib import Path

from scripts.capture_smb import publish_snapshot
from scripts.check_smb_source import list_batch_names, read_config, smb_command


def snapshot(env_file, output, limit=1000):
    if not 1 <= limit <= 1000:
        raise ValueError("Snapshot limit must be between 1 and 1000")
    output = Path(output)
    if output.exists():
        raise FileExistsError(
            "Preserve existing snapshots; choose a new output directory"
        )
    config = read_config(env_file)
    names = list_batch_names(smb_command(config, "ls"))
    if not names or len(names) > limit:
        raise ValueError(
            "Frozen listing empty or exceeds requested limit; no download performed"
        )
    rawdir = output / "raw"
    rawdir.mkdir(parents=True)
    manifest = {
        "host": config.host,
        "share": config.share,
        "read_only": True,
        "listing_count": len(names),
        "started_at": datetime.now(UTC).isoformat(),
        "files": {},
    }
    (output / "frozen_listing.json").write_text(json.dumps(names, indent=2) + "\n")
    for i, name in enumerate(names):
        with tempfile.TemporaryDirectory() as tmp:
            smb_command(config, f"get {name} sample.csv", cwd=tmp)
            raw = (Path(tmp) / "sample.csv").read_bytes()
        publish_snapshot(raw, rawdir / name)
        manifest["files"][name] = {
            "sha256": hashlib.sha256(raw).hexdigest(),
            "bytes": len(raw),
        }
        if (i + 1) % 50 == 0:
            print(f"Captured {i + 1}/{len(names)}", flush=True)
    manifest["completed_at"] = datetime.now(UTC).isoformat()
    (output / "capture_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    return manifest


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--limit", type=int, default=1000)
    args = parser.parse_args()
    result = snapshot(args.env_file, args.output, args.limit)
    print("Read-only snapshot complete:", len(result["files"]), "files")
