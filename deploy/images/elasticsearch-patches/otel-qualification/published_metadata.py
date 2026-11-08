"""Integrity/declaration inspection for official root POMs; no Maven resolution."""

import hashlib
import json
import xml.etree.ElementTree as ET
from pathlib import Path

HERE = Path(__file__).resolve().parent
NS = {"m": "http://maven.apache.org/POM/4.0.0"}


def dependencies(data):
    root = ET.fromstring(data)
    result = []
    for dep in root.findall("m:dependencies/m:dependency", NS):
        row = {}
        for child in dep:
            key = child.tag.rsplit("}", 1)[-1]
            if key == "exclusions":
                row[key] = [
                    {c.tag.rsplit("}", 1)[-1]: c.text for c in exclusion}
                    for exclusion in child.findall("m:exclusion", NS)
                ]
            else:
                if len(child):
                    raise ValueError("unsupported nested dependency metadata")
                row[key] = child.text
        result.append(row)
    return result


def verify():
    model = json.loads((HERE / "published-roots.json").read_text())
    if model["replacement"] is not None or model["runtime_approved"]:
        raise ValueError("root metadata cannot approve replacements")
    changes = [
        (a, b)
        for a, b in zip(model["current_roots"], model["sdk_six_roots"], strict=True)
        if a != b
    ]
    expected = {
        "opentelemetry-" + a
        for a in (
            "sdk",
            "sdk-common",
            "sdk-trace",
            "sdk-metrics",
            "sdk-logs",
            "sdk-extension-autoconfigure-spi",
        )
    }
    if (
        len(changes) != 6
        or {a.split(":")[1] for a, b in changes} != expected
        or any(
            a.rsplit(":", 1)[1] != "1.62.0" or b.rsplit(":", 1)[1] != "1.67.0"
            for a, b in changes
        )
    ):
        raise ValueError("six observed SDK root experiment drift")
    seen = set()
    for pin in model["files"]:
        if pin["coordinate"] in seen:
            raise ValueError("duplicate POM coordinate")
        seen.add(pin["coordinate"])
        path = HERE / pin["file"]
        if not path.is_relative_to(HERE / "published-poms") or path.is_symlink():
            raise ValueError("unsafe POM input")
        data = path.read_bytes()
        if (
            hashlib.sha256(data).hexdigest() != pin["sha256"]
            or dependencies(data) != pin["dependencies"]
        ):
            raise ValueError("official POM input/declaration drift")
    if seen != set(model["current_roots"] + model["sdk_six_roots"]):
        raise ValueError("root POM inventory incomplete")
    return {
        "status": "official-declarations-only-not-mediated-closure",
        "root_poms": len(seen),
        "changed_roots": changes,
        "replacement": None,
        "runtime_approved": False,
        "real_maven_oracle_executed": False,
    }


if __name__ == "__main__":
    print(json.dumps(verify(), indent=2))
