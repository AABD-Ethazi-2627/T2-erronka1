"""Reproduce the local Kafka wheel from the hash-pinned official wheel, offline."""

import argparse
import base64
import csv
import hashlib
import io
import zipfile
from pathlib import Path

UPSTREAM_SHA256 = "9d10cab4e11e02545d82c7e5af5702da5aa46dd4eccd11ad92a50bf6dbbecd14"
VERSION = "3.0.11+cncguard.2"
WHEEL_NAME = f"kafka_python-{VERSION}-py3-none-any.whl"
OLD_INFO = "kafka_python-3.0.11.dist-info/"
NEW_INFO = f"kafka_python-{VERSION}.dist-info/"
LOADER = "kafka/protocol/schemas/load_json.py"
OLD_CALL = b"importlib.resources.read_text(package, msg_type + '.json')"
NEW_CALL = (
    b"importlib.resources.files(package).joinpath(msg_type + '.json')"
    b".read_text(encoding='utf-8')"
)


def replace_once(content, old, new):
    if content.count(old) != 1:
        raise ValueError(f"Expected exactly one occurrence of {old!r}")
    return content.replace(old, new, 1)


def repack(upstream, output):
    raw = upstream.read_bytes()
    if hashlib.sha256(raw).hexdigest() != UPSTREAM_SHA256:
        raise ValueError("Official wheel SHA256 mismatch; refusing to patch")
    with zipfile.ZipFile(io.BytesIO(raw)) as wheel:
        members = {name: wheel.read(name) for name in wheel.namelist()}
    members[LOADER] = replace_once(members[LOADER], OLD_CALL, NEW_CALL)
    # Apache-2.0 section 4(b): mark the modified source file.
    members[LOADER] = (
        b"# Modified by CNC Guard: migrate resource reads to the Python files() API.\n"
        + members[LOADER]
    )
    members["kafka/version.py"] = replace_once(
        members["kafka/version.py"], b"'3.0.11'", f"'{VERSION}'".encode()
    )
    # KIP-511 software versions allow letters, digits, dots and hyphens, not
    # PEP 440's local-version '+'. Preserve distribution identity in metadata
    # while sending a broker-valid version for every client, including Admin.
    for connection in ("kafka/net/connection.py", "kafka/net/manager.py"):
        members[connection] = replace_once(
            members[connection],
            b"'client_software_version': __version__,",
            b"'client_software_version': __version__.replace('+', '-'),",
        )
        members[connection] = (
            b"# Modified by CNC Guard: encode PEP 440 local versions for KIP-511.\n"
            + members[connection]
        )
    members[OLD_INFO + "METADATA"] = replace_once(
        members[OLD_INFO + "METADATA"],
        b"Version: 3.0.11\n",
        f"Version: {VERSION}\n".encode(),
    )
    # files() was introduced in Python 3.9. Keep wheel metadata honest even
    # outside this project's narrower, unchanged Python 3.11/3.12 constraint.
    members[OLD_INFO + "METADATA"] = replace_once(
        members[OLD_INFO + "METADATA"],
        b"Requires-Python: >=3.8\n",
        b"Requires-Python: >=3.9\n",
    )
    members[OLD_INFO + "METADATA"] = replace_once(
        members[OLD_INFO + "METADATA"],
        b"Classifier: Programming Language :: Python :: 3.8\n",
        b"",
    )
    members.pop(OLD_INFO + "RECORD")
    members = {name.replace(OLD_INFO, NEW_INFO): data for name, data in members.items()}
    record = io.StringIO(newline="")
    writer = csv.writer(record, lineterminator="\n")
    for name, data in sorted(members.items()):
        digest = base64.urlsafe_b64encode(hashlib.sha256(data).digest()).rstrip(b"=")
        writer.writerow((name, "sha256=" + digest.decode(), len(data)))
    writer.writerow((NEW_INFO + "RECORD", "", ""))
    members[NEW_INFO + "RECORD"] = record.getvalue().encode()
    # Stored ZIP entries avoid cross-zlib differences. Fixed metadata makes the
    # same wheel byte-reproducible across supported Python versions and hosts.
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_STORED) as wheel:
        for name, data in sorted(members.items()):
            info = zipfile.ZipInfo(name, date_time=(2026, 1, 1, 0, 0, 0))
            info.create_system = 3
            info.external_attr = 0o100644 << 16
            wheel.writestr(info, data)
    print(f"{hashlib.sha256(output.read_bytes()).hexdigest()}  {output.name}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "upstream", type=Path, help="Official 3.0.11 wheel (see vendor/README.md)"
    )
    parser.add_argument("--output", type=Path, default=Path("vendor") / WHEEL_NAME)
    args = parser.parse_args()
    repack(args.upstream, args.output)


if __name__ == "__main__":
    main()
