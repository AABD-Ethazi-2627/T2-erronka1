"""Package only artifacts trained locally by this checkout, no downloaded pickle."""

import hashlib
import json
import shutil
from pathlib import Path


def package(output=Path("outputs/api")):
    if output.exists():
        raise FileExistsError("Refuse replacing a model bundle")
    rf = json.loads(Path("outputs/cg08/report.json").read_text())
    anomaly = json.loads(Path("outputs/cg09/report.json").read_text())
    sources = {
        "rf.pkl": Path("outputs/cg08/rf.pkl"),
        "if.pkl": Path("outputs/cg09/if.pkl"),
    }
    expected = {"rf.pkl": rf["model_sha256"], "if.pkl": anomaly["model_sha256"]}
    for name, path in sources.items():
        if hashlib.sha256(path.read_bytes()).hexdigest() != expected[name]:
            raise ValueError("Artifact differs from its training report")
    output.mkdir(parents=True)
    for name, path in sources.items():
        shutil.copyfile(path, output / name)
    manifest = {
        "model_version": "ai4i-development-v3",
        "versions": rf["versions"],
        "files": expected,
        "risk_threshold": rf["validation_tuning_metrics"]["threshold"],
        "anomaly_threshold": anomaly["threshold"],
        "policy": "f2",
        "limitation": "Development classification only; not calibrated industrial or future risk.",
    }
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    return manifest


if __name__ == "__main__":
    package()
