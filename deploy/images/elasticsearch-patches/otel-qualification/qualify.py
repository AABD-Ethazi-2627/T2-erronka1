"""ES preparation/model checks only; never selects or writes a runtime overlay."""

import argparse
import hashlib
import importlib.util
import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location("_es_otel_symbolic", HERE / "symbolic.py")
s = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(s)
IMAGE = "sha256:2005cca9747e88288e27d18a2f7352486ab0e2a09acd46ee229e9d2bb889ccb4"
REALMS = ("apm", "repository-gcs", "esql-datasource-gcs")
SDK = (
    "sdk",
    "sdk-common",
    "sdk-trace",
    "sdk-metrics",
    "sdk-logs",
    "sdk-extension-autoconfigure-spi",
)
TRIO = ("api", "context", "common")
LIMITS = [
    "symbolic model is not complete JVM verification",
    "JVM access, default-method selection and method-handle invocation are not fully modeled",
    "reflection, exporter behavior, resource-provider and service initialization need independent probes",
    "extended-plugin and server classes are outside the selected-realm symbolic model",
    "agent nested archives and shaded copies are inventory only and not linked into the APM module model",
    "module descriptor identity does not prove entitlement permissions or runtime behavior",
]


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as source:
        for block in iter(lambda: source.read(65536), b""):
            digest.update(block)
    return digest.hexdigest()


def safe_file(path):
    path = Path(path).absolute()
    if any(p.is_symlink() for p in (path, *path.parents)) or not path.is_file():
        raise ValueError("missing or linked input")
    return path


def audit_rows(text):
    """Parse Java metadata; never flatten independent ES module/classloader realms."""
    records = [line.split("\t") for line in text.splitlines()]
    result = {
        "image_id": IMAGE,
        "replacement": None,
        "runtime_approved": False,
        "java_feature": None,
        "realms": {},
        "graph": {},
        "loader": [],
        "status": "metadata-inventory-only-not-linkage-approval",
    }
    jar_keys = set()
    module_keys = set()
    policies = set()
    for row in records:
        if not row:
            continue
        kind, *values = row
        if kind == "JAVA":
            if result["java_feature"] is not None or len(values) != 2:
                raise ValueError("duplicate or invalid runtime")
            result["java_feature"] = int(values[1])
        elif kind == "REALM":
            realm, classname, module, extended, digest = values
            if realm not in REALMS or realm in result["realms"]:
                raise ValueError("duplicate or unknown realm")
            result["realms"][realm] = {
                "classname": classname,
                "module": module or None,
                "extended_plugins": extended.split(",") if extended else [],
                "descriptor_sha256": digest,
                "jars": {},
                "metadata": [],
            }
        elif kind == "JAR":
            realm, filename, size, digest = values
            if realm not in result["realms"] or (realm, filename) in jar_keys:
                raise ValueError("duplicate or orphan jar")
            if (
                Path(filename).name != filename
                or not filename.endswith(".jar")
                or not re.fullmatch("[0-9a-f]{64}", digest)
            ):
                raise ValueError("invalid jar metadata")
            jar_keys.add((realm, filename))
            result["realms"][realm]["jars"][filename] = {
                "sha256": digest,
                "size": int(size),
            }
        elif kind == "MODULE":
            realm, filename, module, automatic, version = values
            if (realm, filename) not in jar_keys or (realm, filename) in module_keys:
                raise ValueError("orphan or duplicate module identity")
            module_keys.add((realm, filename))
            result["realms"][realm]["jars"][filename].update(
                module=module, automatic=automatic == "true", version=version
            )
        elif kind == "POLICY":
            realm, digest = values
            if realm not in result["realms"] or realm in policies:
                raise ValueError("orphan or duplicate policy")
            policies.add(realm)
            result["realms"][realm]["entitlement_sha256"] = digest
        elif kind == "GRAPH":
            realm, module, extended, spi, digest = values
            if realm in result["graph"]:
                raise ValueError("duplicate graph entry")
            result["graph"][realm] = {
                "module": module or None,
                "extended_plugins": extended.split(",") if extended else [],
                "spi": spi == "true",
                "descriptor_sha256": digest,
            }
        elif kind == "LOADER":
            result["loader"].append(values)
        elif kind in (
            "MANIFEST",
            "ENTRIES",
            "SERVICE",
            "REQUIRES",
            "EXPORTS",
            "USES",
            "PROVIDES",
        ):
            if (
                values[0] not in result["realms"]
                or (values[0], values[1]) not in jar_keys
            ):
                raise ValueError("orphan metadata")
            result["realms"][values[0]]["metadata"].append(row)
        elif kind == "STATUS":
            if values != [
                "inventory-only",
                "replacement=null",
                "runtime_approved=false",
            ]:
                raise ValueError("unexpected audit status")
        else:
            raise ValueError("unknown metadata row")
    if (
        set(result["realms"]) != set(REALMS)
        or not jar_keys
        or module_keys != jar_keys
        or policies != set(REALMS)
        or not result["java_feature"]
        or not result["loader"]
        or records[-1]
        != ["STATUS", "inventory-only", "replacement=null", "runtime_approved=false"]
    ):
        raise ValueError("incomplete actual inventory")
    for realm, data in result["realms"].items():
        if (
            realm not in result["graph"]
            or result["graph"][realm]["descriptor_sha256"] != data["descriptor_sha256"]
        ):
            raise ValueError("module graph descriptor mismatch")
        for extension in data["extended_plugins"]:
            if extension not in result["graph"]:
                raise ValueError("unresolved extension boundary")
        # ModuleFinder silently masks duplicate names: reject them within each actual realm.
        modules = [jar["module"] for jar in data["jars"].values()]
        if len(set(modules)) != len(modules):
            raise ValueError("duplicate JPMS identity in realm")
        for artifact in TRIO:
            name = f"opentelemetry-{artifact}-1.67.0.jar"
            pin = next(
                p
                for p in json.loads((HERE / "reusable-official-pins.json").read_text())[
                    "files"
                ]
                if p["file"] == name
            )
            if data["jars"].get(name, {}).get("sha256") != pin["sha256"]:
                raise ValueError("current API trio input mismatch")
    result["limits"] = LIMITS
    return result


def sdk_experiment(inventory):
    """Select exactly observed SDK six; exporters/alpha/agent stay measured consumers."""
    found = inventory["realms"]["apm"]["jars"]
    selection = {}
    for artifact in SDK:
        old = f"opentelemetry-{artifact}-1.62.0.jar"
        if old not in found:
            raise ValueError("unobserved SDK module")
        selection[old] = f"opentelemetry-{artifact}-1.67.0.jar"
    return selection


def collect(realm, inventory, tree, cache=None, replacements=None):
    data = inventory["realms"][realm]
    models, refs, consumers, unresolved_duplicates = {}, [], [], []
    for name, record in sorted(data["jars"].items()):
        original = safe_file(Path(tree) / realm / name)
        if sha(original) != record["sha256"]:
            raise ValueError("actual extracted artifact drift")
        path = original
        if replacements and name in replacements:
            path = safe_file(Path(cache) / replacements[name])
            pins = {
                p["file"]: p
                for p in json.loads((HERE / "reusable-official-pins.json").read_text())[
                    "files"
                ]
            }
            if sha(path) != pins[path.name]["sha256"]:
                raise ValueError("official replacement drift")
        # Top-level only. Nested agent archives are not implicitly merged into this loader.
        for entry, model in s.classes(path, inventory["java_feature"]):
            if model["name"].startswith("io/opentelemetry/"):
                if model["name"] in models:
                    unresolved_duplicates.append(model["name"])
                else:
                    models[model["name"]] = model
            if model["references"]:
                label = realm + "!" + path.name + "!" + entry
                refs.extend((label, tuple(ref)) for ref in model["references"])
                consumers.append(
                    {
                        "entry": label,
                        "references": len(model["references"]),
                        "public": bool(model["flags"] & 1),
                        "internal": "/internal/" in model["name"],
                    }
                )
    if not models or not refs or not consumers:
        raise ValueError("vacuous actual consumer scan")
    if unresolved_duplicates:
        raise ValueError("shadowed OTel provider identity; loader semantics required")
    return models, refs, consumers


def compare_realm(realm, inventory, tree, cache):
    replacement = sdk_experiment(inventory) if realm == "apm" else {}
    current, refs, _consumers = collect(realm, inventory, tree)
    candidate, fixed_refs, fixed_consumers = collect(
        realm, inventory, tree, cache, replacement
    )
    broken = s.newly_broken(current, candidate, fixed_refs)
    current_unresolved = [
        {"consumer": c, "reference": list(ref)}
        for c, ref in refs
        if not s.resolve(current, ref[0], (ref[3], ref[1], ref[2]))
    ]
    unresolved = [
        {"consumer": c, "reference": list(ref)}
        for c, ref in fixed_refs
        if not s.resolve(candidate, ref[0], (ref[3], ref[1], ref[2]))
    ]
    mutant = dict(candidate)
    mutant.pop("io/opentelemetry/api/OpenTelemetry", None)
    negatives = s.newly_broken(candidate, mutant, fixed_refs)
    if not negatives:
        raise ValueError("missing API negative control is vacuous")
    return {
        "realm": realm,
        "replacement": None,
        "runtime_approved": False,
        "experiment_only": replacement,
        "provider_classes": len(candidate),
        "consumer_entries": len(fixed_consumers),
        "reference_records": len(fixed_refs),
        "newly_broken_modeled_references": broken,
        "unresolved_current_model": current_unresolved,
        "unresolved_candidate_model": unresolved,
        "public_consumer_entries": sum(c["public"] for c in fixed_consumers),
        "internal_consumer_entries": sum(c["internal"] for c in fixed_consumers),
        "current_reference_records": len(refs),
        "negative_control_failures": len(negatives),
        "limits": LIMITS,
        "status": "model-only-not-eligibility",
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=["inventory", "static"])
    parser.add_argument("--audit", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--tree", type=Path)
    parser.add_argument("--cache", type=Path)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError("refusing to overwrite evidence")
    inventory = audit_rows(safe_file(args.audit).read_text())
    if args.phase == "inventory":
        report = inventory
    else:
        if args.tree is None or args.cache is None:
            raise ValueError("explicit extracted tree and official cache required")
        report = {
            "replacement": None,
            "runtime_approved": False,
            "realms": [
                compare_realm(r, inventory, args.tree, args.cache) for r in REALMS
            ],
        }
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
