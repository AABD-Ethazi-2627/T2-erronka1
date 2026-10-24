"Read-only Docker identity/config/state inventory and preservation comparison."

import json
import subprocess
import sys
from pathlib import Path

E = Path(__file__).resolve().parent
phase = sys.argv[1]


def cmd(*args):
    p = subprocess.run(["docker", *args], check=False, capture_output=True, text=True)
    with (E / "inventory-commands.jsonl").open("a") as f:
        f.write(
            json.dumps(
                {
                    "argv": ["docker", *args],
                    "exit": p.returncode,
                    "stdout": p.stdout,
                    "stderr": p.stderr,
                }
            )
            + "\n"
        )
    p.check_returncode()
    return p.stdout


def inspect(kind, ids):
    return [json.loads(cmd(*(kind + ["inspect", i])))[0] for i in ids]


ids = cmd("ps", "-aq", "--no-trunc").split()
containers = inspect([], ids)
data = {
    "containers": {
        c["Id"]: {
            k: c[k]
            for k in ("Id", "Name", "Image", "Config", "HostConfig", "Mounts", "State")
        }
        for c in containers
    },
    "volumes": {
        v["Name"]: v for v in inspect(["volume"], cmd("volume", "ls", "-q").split())
    },
    "networks": {
        n["Id"]: {
            k: n[k]
            for k in (
                "Id",
                "Name",
                "Labels",
                "IPAM",
                "Options",
                "Internal",
                "Driver",
                "Containers",
            )
        }
        for n in inspect(["network"], cmd("network", "ls", "-q", "--no-trunc").split())
    },
    "images": sorted(set(cmd("image", "ls", "-q", "--no-trunc").split())),
    "old_kafka_layer": cmd(
        "diff", ("28d70b96fca30458914c3f8cb26fe7bcc388778bcb78f7b5cb35d38a5463b464")
    ),
}
path = E / (phase + "-inventory.json")
assert not path.exists()
path.write_text(json.dumps(data, indent=2) + "\n")
if phase == "after":
    before = json.loads((E / "before-inventory.json").read_text())
    comparison = {}
    for kind in ("containers", "volumes", "networks"):
        mismatches = []
        for key, value in before[kind].items():
            current = data[kind].get(key)
            if kind == "containers" and current:
                # Health log timestamps change naturally on running foreign services.
                value = json.loads(json.dumps(value))
                current = json.loads(json.dumps(current))
                value["State"].pop("Health", None)
                current["State"].pop("Health", None)
            if current != value:
                mismatches.append(key)
        comparison[kind] = {
            "before": len(before[kind]),
            "preserved": len(before[kind]) - len(mismatches),
            "mismatches": mismatches,
        }
    comparison["images_unchanged"] = data["images"] == before["images"]
    comparison["old_kafka_layer_unchanged"] = sorted(
        data["old_kafka_layer"].splitlines()
    ) == sorted(before["old_kafka_layer"].splitlines())
    (E / "preservation.json").write_text(json.dumps(comparison, indent=2) + "\n")
    assert all(
        not comparison[k]["mismatches"] for k in ("containers", "volumes", "networks")
    ), comparison
    assert comparison["images_unchanged"] and comparison["old_kafka_layer_unchanged"]
print(phase, {k: len(data[k]) for k in ("containers", "volumes", "networks", "images")})
