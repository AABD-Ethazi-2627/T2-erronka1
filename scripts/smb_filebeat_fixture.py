"""Prepare offline CG05/CG29 lab inputs and expected keys, without running Filebeat.

python -m scripts.smb_filebeat_fixture --output outputs/smb-filebeat-fixture
The manifest is an oracle for a future Filebeat 9.5.4 run, not a registry emulator.
"""

import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = "docs/requisitos/evidencias/muestras/cnc_batch_20261015_080906_00001.csv"


def expected_records(raw):
    """Reference for message-only fingerprint serialization in Beats v9.5.4."""
    records = []
    offset = 0
    for line in raw.splitlines(keepends=True):
        message = line.removesuffix(b"\n")
        if not message.startswith(b"timestamp,"):
            fingerprint = hashlib.sha256(b"|message|" + message + b"|").hexdigest()
            records.append(
                {"message": message.decode("utf-8"), "key": f"{fingerprint}:{offset}"}
            )
        offset += len(line)
    return records


def prepare(output):
    source = (ROOT / SOURCE).read_bytes()
    lines = source.splitlines(keepends=True)
    # Synthetic boundary fixture. Reuse the frozen emission date, never claim
    # these sentinel sensor values are measurements or AI4I training observations.
    tiny_row = b",".join(lines[1].split(b",")[:3] + [b"1"] * 5 + [b"0"] * 6) + b"\n"
    fixtures = {
        "ten_rows.csv": source,
        "one_row.csv": b"".join(lines[:2]),
        "tiny_synthetic.csv": lines[0] + tiny_row,
        "header_only.csv": lines[0],
        "partial.csv": source[:-1],
        "invalid.csv": b"bad,columns\n1,2\n",
    }
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    manifest = {
        "scope": "offline fixture/oracle only; Filebeat, registry and Kafka unexecuted",
        "filebeat_version": "9.5.4",
        "source": SOURCE,
        "source_sha256": hashlib.sha256(source).hexdigest(),
        "tiny_origin": "synthetic sensor/label sentinels; frozen timestamp and machine",
        "fixtures": {},
    }
    for name, content in fixtures.items():
        (output / name).write_bytes(content)
        valid = name in {"ten_rows.csv", "one_row.csv", "tiny_synthetic.csv"}
        manifest["fixtures"][name] = {
            "bytes": len(content),
            "sha256": hashlib.sha256(content).hexdigest(),
            "capture_accepts": valid,
            "expected_records": expected_records(content) if valid else [],
        }
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    return manifest


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    print(json.dumps(prepare(parser.parse_args().output), indent=2))
