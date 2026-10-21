"""Package only artifacts trained locally by this checkout, no downloaded pickle."""

import argparse
import hashlib
import json
import shutil
from pathlib import Path

from scoring.scope import APPROVED_SOURCE_SHA256, SCOPE, load_training_source


def package(
    output=Path("outputs/api"),
    rf_dir=Path("outputs/cg08"),
    anomaly_dir=Path("outputs/cg09"),
):
    if output.exists():
        raise FileExistsError("Refuse replacing a model bundle")
    load_training_source()
    rf = json.loads((rf_dir / "report.json").read_text())
    anomaly = json.loads((anomaly_dir / "report.json").read_text())
    if any(
        report.get("source_sha256") != APPROVED_SOURCE_SHA256
        for report in (rf, anomaly)
    ):
        raise ValueError(
            "Both reports must attest the approved reduced training source"
        )
    sources = {
        "rf.pkl": rf_dir / "rf.pkl",
        "if.pkl": anomaly_dir / "if.pkl",
    }
    expected = {"rf.pkl": rf["model_sha256"], "if.pkl": anomaly["model_sha256"]}
    for name, path in sources.items():
        if hashlib.sha256(path.read_bytes()).hexdigest() != expected[name]:
            raise ValueError("Artifact differs from its training report")
    output.mkdir(parents=True)
    for name, path in sources.items():
        shutil.copyfile(path, output / name)
    manifest = {
        **SCOPE,
        "model_version": "ai4i-current-state-v4",
        "versions": rf["versions"],
        "files": expected,
        "risk_threshold": rf["validation_tuning_metrics"]["threshold"],
        "anomaly_threshold": anomaly["threshold"],
        "policy": "f2",
        "limitation": (
            "Development classification only; not calibrated "
            + "industrial or future risk."
        ),
    }
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    return manifest


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("outputs/api"))
    parser.add_argument("--rf-dir", type=Path, default=Path("outputs/cg08"))
    parser.add_argument("--anomaly-dir", type=Path, default=Path("outputs/cg09"))
    args = parser.parse_args()
    package(args.output, args.rf_dir, args.anomaly_dir)
