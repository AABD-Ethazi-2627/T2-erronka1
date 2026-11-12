"""Lond Local Lanekik lokalki trebatutako eredua eta sarrera esplizitua irakurtzen ditu."""

import argparse
import json
from pathlib import Path


def configure(source, manifest, output):
    model = json.loads(Path(manifest).read_text(encoding="utf-8"))
    topic, index = {
        "smb": ("cnc-sensors-smb-v1", "cnc-telemetry-smb-v1"),
        "lab": ("cnc-sensors-lab-v2", "cnc-telemetry-lab-v2"),
    }[source]
    config = {
        "scope": {
            "source_uri": "kafka://kafka:9092/" + topic,
            "model_artifact_sha256": model["files"]["rf.pkl"],
            "policy": model["policy"],
            "risk_threshold": model["risk_threshold"],
        },
        "elasticsearch": {"url": "http://elasticsearch:9200", "index": index},
        "history_backend": "elasticsearch",
    }
    if Path(output).exists():
        previous = json.loads(Path(output).read_text(encoding="utf-8"))
        if previous.get("scope") == config["scope"] and previous.get("evaluation"):
            config["evaluation"] = previous["evaluation"]
    Path(output).write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
    print("Configured canonical reads:", source, index)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", choices=("smb", "lab"), required=True)
    parser.add_argument("--manifest", type=Path, default=Path("outputs/api/manifest.json"))
    parser.add_argument("--output", type=Path, default=Path("outputs/read-config.json"))
    args = parser.parse_args()
    configure(args.source, args.manifest, args.output)
