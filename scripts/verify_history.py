"""Verify a local retained history against its manifest, without repairing it."""

import hashlib
import json
from pathlib import Path

import duckdb


def verify(root):
    root = Path(root).resolve()
    try:
        manifest = json.loads((root / "manifest.json").read_text())
        for name, digest in manifest["files"].items():
            path = (root / name).resolve()
            if (
                not path.is_relative_to(root)
                or hashlib.sha256(path.read_bytes()).hexdigest() != digest
            ):
                return False
        with duckdb.connect() as con:
            count, unique = con.execute(
                "SELECT count(*), count(DISTINCT record_id) FROM read_parquet(?)",
                [str(root / "silver/**/*.parquet")],
            ).fetchone()
        return count == manifest["rows"] == unique == manifest["unique_records"]
    except (OSError, ValueError, KeyError, duckdb.Error):
        return False


if __name__ == "__main__":
    ok = verify(Path("historical"))
    print(
        "Retained history verified"
        if ok
        else "Retained history differs: preserve evidence and investigate"
    )
    raise SystemExit(0 if ok else 1)
