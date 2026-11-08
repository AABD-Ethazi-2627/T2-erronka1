"""Verify downloaded compact text proof against frozen 89f58fc inventory hashes."""

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
EXPECTED = {
    "run-result.json": "e810eb67e38aac1b7ab86dfe328e7a10504bfc8f4c3aa2ab491dda9442477324",
    "inventory.json": "24cbefa96985750a721ac8ef16d85efd93d42adedf02b98ea837b9b91ac79b5b",
    "audit.tsv": "32d39b5dedd486afa9458f701dea470e6648758acc832597b707a4e821db7686",
    "audit.stderr": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
    "parse.stderr": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
}


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def closure(graph, roots):
    found, active = set(), set()

    def visit(realm):
        if realm in active:
            raise ValueError("extension graph cycle")
        if realm not in graph:
            raise ValueError("missing extension realm")
        if realm in found:
            return
        active.add(realm)
        for extension in graph[realm]["extended_plugins"]:
            visit(extension)
        active.remove(realm)
        found.add(realm)

    for root in roots:
        visit(root)
    return sorted(found)


def seal(base):
    base = Path(base)
    for filename, expected in EXPECTED.items():
        if digest(base / "inventory-01" / filename) != expected:
            raise ValueError("frozen metadata integrity: " + filename)
    report = json.loads((base / "inventory-01/run-result.json").read_text())
    if (
        report["returncode"]
        or report["parse_returncode"]
        or not report["image_unchanged"]
        or not report["source_unchanged"]
        or report["remaining_owned_containers"]
        or report["replacement"] is not None
        or report["runtime_approved"]
    ):
        raise ValueError("inventory preservation/result gate")
    source = base / "source/deploy/images/elasticsearch-patches/otel-qualification"
    for name, expected in report["source_before"].items():
        if digest(source / name) != expected:
            raise ValueError("executed source integrity: " + name)
    test_sha = "af8275efb451b762724a263e29efd033f8197323d4773e329b773951ac4f7037"
    if digest(base / "source/tests/test_es_otel_qualification.py") != test_sha:
        raise ValueError("executed test integrity")
    # Reproduce inventory with precisely the earlier parser that ran on the VM.
    spec = importlib.util.spec_from_file_location(
        "_es_inventory89", source / "qualify.py"
    )
    q = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(q)
    inventory = q.audit_rows((base / "inventory-01/audit.tsv").read_text())
    if inventory != json.loads((base / "inventory-01/inventory.json").read_text()):
        raise ValueError("inventory generator mismatch")
    realms = inventory["realms"]
    return {
        "status": "measured-inventory-only",
        "replacement": None,
        "runtime_approved": False,
        "executed_source_commit": "89f58fc",
        "executed_test_sha256": test_sha,
        "executed_source_sha256": report["source_before"],
        "executed_source_archive_sha256": "96d9a61b9fec92ba65f110eda7b0764486fc8f4c29f2a3874ccef09fc4461b22",
        "phase_elapsed_seconds": report["elapsed_seconds"],
        "java_feature": inventory["java_feature"],
        "metadata_sha256": EXPECTED,
        "realms": {
            name: {
                "direct_jars": len(row["jars"]),
                "bytes": sum(j["size"] for j in row["jars"].values()),
                "module": row["module"],
                "extended_plugins": row["extended_plugins"],
            }
            for name, row in realms.items()
        },
        "required_graph_closure": closure(inventory["graph"], realms),
        "loader": inventory["loader"],
        "image_id": report["image_before"]["Id"],
        "missing_evidence": [
            "published mediated closure",
            "complete JVM ABI/access",
            "actual ES loader consumer initialization",
            "entitlement operation",
            "APM functional behavior",
        ],
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--compact", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError("refusing to overwrite evidence")
    args.output.write_text(
        json.dumps(seal(args.compact), indent=2, sort_keys=True) + "\n"
    )


if __name__ == "__main__":
    main()
