"""Export the exact observed optional-symbol boundary from a verified old proof."""

import argparse
import hashlib
import json
from pathlib import Path

# Immutable successful 8429 source proof, not recomputed from a candidate at run time.
SOURCE_SHA256 = "366fde723fa81aee706f3989b9083d2d74f6fd4c034ce5c74eba9ad608b0b15e"
FIELDS = {
    "old": "unresolved_old",
    "aligned": "unresolved_current_references",
    "aligned-all-family-including-api": "unresolved_including_api_family",
}


def export(source, output):
    raw = Path(source).read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    if digest != SOURCE_SHA256:
        raise ValueError("allowlist source is not the immutable reviewed proof")
    proof = json.loads(raw)
    records = {
        scenario: sorted(
            [
                {
                    "consumer": r["consumer"],
                    "reference": r["reference"],
                    "category": r["category"],
                }
                for r in proof[field]
                if r["category"].startswith("internal-optional-incubator")
            ],
            key=lambda r: (r["consumer"], r["reference"]),
        )
        for scenario, field in FIELDS.items()
    }
    if {k: len(v) for k, v in records.items()} != {
        "old": 67,
        "aligned": 50,
        "aligned-all-family-including-api": 50,
    }:
        raise ValueError("reviewed optional coverage count mismatch")
    result = {
        "schema": 1,
        "replacement": None,
        "runtime_approved": False,
        "source_static_sha256": digest,
        "source_commit": "8429e12",
        "scenario_aliases": {"sdk-new-api-old": "aligned"},
        "records": records,
    }
    with Path(output).open("x") as f:
        f.write(json.dumps(result, indent=2, sort_keys=True) + "\n")
    return result


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--source", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    a = p.parse_args()
    export(a.source, a.output)
