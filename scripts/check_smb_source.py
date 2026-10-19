"""Read-only SMB listing/sample check using a private .env file.

python -m scripts.check_smb_source
python -m scripts.check_smb_source --download-dir data/stream_samples
Requires the local smbclient command, never mounts or writes to the remote share.
"""

import argparse
import csv
import hashlib
import ipaddress
import json
import os
import re
import shlex
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BATCH = re.compile(r"^\s*(cnc_batch_[0-9]{8}_[0-9]{6}_[0-9]+\.csv)\s+N\s+[0-9]+\s+")


@dataclass(frozen=True)
class SmbConfig:
    host: str
    share: str
    username: str = field(repr=False)
    password: str = field(repr=False)
    timeout: int = 8


def read_config(path):
    path = Path(path)
    if path.stat().st_mode & 0o077:
        raise ValueError("Unsafe env permissions; run chmod 600 on the env file")
    values = {}
    for number, line in enumerate(path.read_text().splitlines(), 1):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        key, separator, value = line.partition("=")
        if not separator or not re.fullmatch(r"[A-Z_][A-Z_0-9]*", key):
            raise ValueError(f"Invalid env entry at line {number}")
        if key in values:
            raise ValueError(f"Duplicate env key at line {number}")
        try:
            tokens = shlex.split(value, comments=True)
        except ValueError:
            raise ValueError(f"Invalid quoted env entry at line {number}") from None
        if len(tokens) > 1:
            raise ValueError(f"Quote env values containing spaces at line {number}")
        values[key] = tokens[0] if tokens else ""
    required = ["SMB_HOST", "SMB_SHARE", "SMB_USERNAME", "SMB_PASSWORD"]
    if not all(values.get(k) for k in required):
        raise ValueError("Required SMB connection fields are missing or empty")
    try:
        host = str(ipaddress.ip_address(values["SMB_HOST"]))
        timeout = int(values.get("SMB_TIMEOUT", "8"))
    except ValueError:
        raise ValueError("Invalid SMB host IP or timeout") from None
    if not 1 <= timeout <= 60:
        raise ValueError("SMB timeout must be between 1 and 60 seconds")
    if not re.fullmatch(r"[A-Za-z0-9_.-]+", values["SMB_SHARE"]):
        raise ValueError("Invalid SMB share name")
    if any(c in values[k] for k in required for c in "\r\n"):
        raise ValueError("SMB connection fields cannot contain line breaks")
    return SmbConfig(
        host,
        values["SMB_SHARE"],
        values["SMB_USERNAME"],
        values["SMB_PASSWORD"],
        timeout,
    )


def list_batch_names(listing):
    return sorted(
        {m.group(1) for line in listing.splitlines() if (m := BATCH.match(line))}
    )


def smb_command(config, command, cwd=None):
    if command != "ls" and not re.fullmatch(
        r"get cnc_batch_[0-9]{8}_[0-9]{6}_[0-9]+\.csv sample\.csv", command
    ):
        raise ValueError("Only read-only ls/get commands are allowed")
    # Credentials never appear in process arguments, output or repository files.
    with tempfile.NamedTemporaryFile(
        mode="w", prefix="cnc-smb-", suffix=".auth"
    ) as auth:
        os.fchmod(auth.fileno(), 0o600)
        auth.write(f"username = {config.username}\npassword = {config.password}\n")
        auth.flush()
        try:
            result = subprocess.run(
                [
                    "smbclient",
                    f"//{config.host}/{config.share}",
                    "-s",
                    "/dev/null",
                    "-A",
                    auth.name,
                    "-t",
                    str(config.timeout),
                    "-c",
                    command,
                ],
                check=False,
                cwd=cwd,
                capture_output=True,
                text=True,
                timeout=config.timeout + 5,
            )
        except subprocess.TimeoutExpired:
            raise RuntimeError(
                "SMB operation timed out; no remote changes attempted"
            ) from None
    statuses = re.findall(r"NT_STATUS_[A-Z0-9_]+", result.stdout + result.stderr)
    if result.returncode or any(s != "NT_STATUS_OK" for s in statuses):
        detail = ", ".join(sorted(set(statuses))) or f"exit {result.returncode}"
        raise RuntimeError(f"SMB operation failed: {detail}; credentials withheld")
    return result.stdout


def inspect_source(config, download_dir=None):
    names = list_batch_names(smb_command(config, "ls"))
    result = {
        "host": config.host,
        "share": config.share,
        "read_only": True,
        "batch_count_at_listing": len(names),
        "samples": [],
    }
    if not names:
        raise RuntimeError(
            "SMB is reachable but no compatible CNC CSV batches were listed"
        )
    if download_dir is None:
        return result
    output = Path(download_dir)
    output.mkdir(parents=True, exist_ok=True)
    # Read only first/latest observed batch; never synchronize/delete the whole share.
    for name in dict.fromkeys([names[0], names[-1]]):
        with tempfile.TemporaryDirectory(prefix="cnc-smb-sample-") as tmp:
            smb_command(config, f"get {name} sample.csv", cwd=tmp)
            content = (Path(tmp) / "sample.csv").read_bytes()
        destination = output / name
        if destination.exists():
            if destination.read_bytes() != content:
                raise ValueError(f"Existing sample differs; refusing overwrite: {name}")
        else:
            with destination.open("xb") as target:
                target.write(content)
        rows = list(csv.DictReader(content.decode("utf-8-sig").splitlines()))
        result["samples"].append(
            {
                "file": str(destination),
                "rows": len(rows),
                "columns": list(rows[0]) if rows else [],
                "sha256": hashlib.sha256(content).hexdigest(),
            }
        )
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", type=Path, default=ROOT / ".env")
    parser.add_argument("--download-dir", type=Path)
    args = parser.parse_args()
    try:
        print(
            json.dumps(
                inspect_source(read_config(args.env_file), args.download_dir), indent=2
            )
        )
    except (OSError, ValueError, RuntimeError) as error:
        # Errors we raise contain no credential values; OS errors only concern paths/executables.
        parser.exit(1, f"{error}\n")
