"""Bounded read-only SMB capture. --watch is foreground, not a persistent schedule."""

import argparse
import hashlib
import json
import os
import tempfile
import time
from pathlib import Path

from scripts.audit_cg02 import audit_csv
from scripts.check_smb_source import list_batch_sizes, read_config, smb_command


def publish_snapshot(raw, target):
    target = Path(target)
    if target.exists():
        if target.read_bytes() != raw:
            raise ValueError(
                "Previously captured filename changed; preserve and investigate"
            )
        return False
    try:
        # Filebeat filters a plain header and emits one physical line per record.
        # Require the producer's LF-delimited, unquoted UTF-8 envelope unchanged.
        if (
            not raw.endswith(b"\n")
            or raw.startswith(b"\xef\xbb\xbf")
            or b'"' in raw
            or b"\r" in raw
        ):
            raise ValueError("Invalid SMB batch framing")
        with tempfile.NamedTemporaryFile() as check:
            check.write(raw)
            check.flush()
            report = audit_csv(check.name, "batch")
        if (
            report["malformed_row_widths"]
            or any(report["missing"].values())
            or any(report["invalid_numeric"].values())
            or any(report["invalid_numeric_domain"].values())
            or report["time"]["invalid_or_non_utc_rows"]
        ):
            raise ValueError("Invalid SMB batch")
    except (ValueError, UnicodeError):
        rejected = target.parent / "quarantine"
        rejected.mkdir(parents=True, exist_ok=True)
        path = rejected / (hashlib.sha256(raw).hexdigest() + ".bin")
        if not path.exists():
            with path.open("xb") as handle:
                handle.write(raw)
        raise ValueError("Invalid SMB batch preserved outside inference") from None
    target.parent.mkdir(parents=True, exist_ok=True)
    # Link complete flushed bytes into the watched glob atomically and exclusively.
    with tempfile.NamedTemporaryFile(dir=target.parent, prefix=".capture-") as stage:
        stage.write(raw)
        stage.flush()
        os.fsync(stage.fileno())
        os.link(stage.name, target)
    return True


def capture_once(config, output, max_files=2):
    if max_files < 1 or max_files > 20:
        raise ValueError("max_files must be between1 and20")
    output = Path(output)
    sizes = list_batch_sizes(smb_command(config, "ls"))
    names = list(sizes)
    pending = [n for n in names if not (output / n).exists()][:max_files]
    reports = []
    for name in pending:
        with tempfile.TemporaryDirectory() as tmp:
            smb_command(config, f"get {name} sample.csv", cwd=tmp)
            raw = (Path(tmp) / "sample.csv").read_bytes()
        after = list_batch_sizes(smb_command(config, "ls"))
        if sizes[name] != len(raw) or after.get(name) != sizes[name]:
            raise ValueError("SMB batch changed or incomplete; retry after publication")
        publish_snapshot(raw, output / name)
        reports.append(
            {
                "filename": name,
                "bytes": len(raw),
                "sha256": hashlib.sha256(raw).hexdigest(),
            }
        )
    return {
        "read_only": True,
        "available_at_listing": len(names),
        "captured": reports,
        "remaining_at_listing": len([n for n in names if not (output / n).exists()]),
        "limitation": (
            "Immutable generated filenames assumed; recheck or "
            + "reconcile before trusting producer changes. No remote "
            + "retention guarantee."
        ),
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=Path("outputs/smb-stream"))
    parser.add_argument("--max-files", type=int, default=2)
    parser.add_argument("--watch", action="store_true")
    parser.add_argument("--interval", type=int, default=30)
    args = parser.parse_args()
    if args.interval < 5:
        parser.error("interval must be at least5 seconds")
    try:
        config = read_config(args.env_file)
        while True:
            print(
                json.dumps(capture_once(config, args.output, args.max_files)),
                flush=True,
            )
            if not args.watch:
                break
            time.sleep(args.interval)
    except (OSError, ValueError, RuntimeError) as error:
        parser.exit(1, f"{error}\n")
