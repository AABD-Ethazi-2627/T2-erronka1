"""Offline, causal sensor-learning evaluation from a portable CSV manifest."""

import argparse
import csv
import io
import json
from hashlib import sha256
from pathlib import Path

from planning import adaptive
from planning.adaptive import evaluate_stream, validate_manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--alpha", type=float, default=0.25)
    parser.add_argument("--warmup", type=int, default=2)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError("Output must be a new directory")
    raw, config_raw = args.data.read_bytes(), args.manifest.read_bytes()
    manifest = json.loads(config_raw)
    validate_manifest(manifest)
    reader = csv.DictReader(io.StringIO(raw.decode("utf-8-sig")))
    headers = reader.fieldnames or []
    if len(set(headers)) != len(headers):
        raise ValueError("Duplicate CSV column headers are ambiguous")
    source = list(reader)
    required = [
        *manifest["columns"].values(),
        *(spec["column"] for spec in manifest["sensors"].values()),
    ]
    if not source or any(field not in source[0] for field in required):
        raise ValueError(
            "Dataset lacks mapped asset, observation timestamp, lifecycle or sensors; no dates are invented"
        )
    for row in source:
        for spec in manifest["sensors"].values():
            row[spec["column"]] = float(row[spec["column"]])
    report = evaluate_stream(source, manifest, alpha=args.alpha, warmup=args.warmup)
    report["source_sha256"] = sha256(raw).hexdigest()
    report["manifest_file_sha256"] = sha256(config_raw).hexdigest()
    report["implementation_sha256"] = sha256(
        Path(adaptive.__file__).read_bytes()
    ).hexdigest()
    report["evaluation_scope"] = (
        "Exploratory prequential sensor forecast, not independent maintenance validation"
    )
    args.output.mkdir(parents=True, exist_ok=False)
    (args.output / "report.json").write_text(
        json.dumps(report, indent=2, allow_nan=False) + "\n"
    )
    (args.output / "manifest.json").write_bytes(config_raw)
    print(
        json.dumps(
            {
                "dataset_id": report["dataset_id"],
                "metrics": report["metrics"],
                "promotion_allowed": report["promotion_allowed"],
                "output": str(args.output),
            }
        )
    )


if __name__ == "__main__":
    main()
