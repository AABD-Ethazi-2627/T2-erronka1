"""Expose nested NAR/JAR dependencies to image scanners in an audit-only stage.

Output names are content hashes, never archive entry paths. The runtime image
stays unchanged. Missing, malformed or oversized archives abort the audit.
"""

import argparse
import hashlib
import io
import json
import zipfile
from pathlib import Path

MAX_ARCHIVE_BYTES = 256 * 1024 * 1024
MAX_TOTAL_BYTES = 4 * 1024 * 1024 * 1024
MAX_DEPTH = 8


def expose(source: Path, destination: Path):
    destination.mkdir(parents=True, exist_ok=False)
    inventory = []
    seen = set()
    total = 0

    def visit(payload, origin, depth):
        nonlocal total
        if depth > MAX_DEPTH:
            raise ValueError(f"Archive nesting exceeds {MAX_DEPTH}: {origin}")
        digest = hashlib.sha256(payload).hexdigest()
        if digest in seen:
            return
        seen.add(digest)
        total += len(payload)
        if total > MAX_TOTAL_BYTES:
            raise ValueError("Archive audit exceeds total byte budget")
        with zipfile.ZipFile(io.BytesIO(payload)) as archive:
            for entry in archive.infolist():
                if not entry.filename.lower().endswith(
                    (".jar", ".nar", ".war", ".zip")
                ):
                    continue
                if entry.file_size > MAX_ARCHIVE_BYTES:
                    raise ValueError(
                        f"Oversized nested archive: {origin}!{entry.filename}"
                    )
                nested = archive.read(entry)
                nested_digest = hashlib.sha256(nested).hexdigest()
                if entry.filename.lower().endswith(".jar"):
                    path = destination / (nested_digest + ".jar")
                    if not path.exists():
                        path.write_bytes(nested)
                    inventory.append(
                        {
                            "source": origin + "!" + entry.filename,
                            "sha256": nested_digest,
                        }
                    )
                visit(nested, origin + "!" + entry.filename, depth + 1)

    for path in sorted(source.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in {
            ".jar",
            ".nar",
            ".war",
            ".zip",
        }:
            continue
        if path.stat().st_size > MAX_ARCHIVE_BYTES:
            raise ValueError(f"Oversized archive: {path}")
        visit(path.read_bytes(), str(path.relative_to(source)), 0)
    if not inventory:
        raise ValueError("No nested dependencies found; refusing an empty NAR audit")
    (destination / "inventory.json").write_text(json.dumps(inventory, indent=2) + "\n")
    return inventory


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("destination", type=Path)
    args = parser.parse_args()
    inventory = expose(args.source, args.destination)
    print(f"Exposed {len(inventory)} nested dependency occurrences")


if __name__ == "__main__":
    main()
