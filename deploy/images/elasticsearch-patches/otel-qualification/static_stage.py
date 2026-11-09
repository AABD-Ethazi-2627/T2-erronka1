"""Bounded symbolic model on frozen VM tree; actual loader/entitlements separate."""

import argparse
import importlib.util
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("_es_stage_q", HERE / "qualify.py")
q = importlib.util.module_from_spec(spec)
spec.loader.exec_module(q)


def visible_paths(realm, graph, files):
    """Server first, then extension parents' SPI/root URLs, then this realm root.

    Duplicate OTel provider classes are rejected during modeling rather than
    claiming this approximation proves exact branch-specific loader behavior.
    """
    result = [p for p in sorted(files) if p.startswith("lib/") and p.endswith(".jar")]
    active = set()

    def visit(name, exported):
        if name in active or name not in graph:
            raise ValueError("missing/cyclic loader graph")
        active.add(name)
        for parent in graph[name]["extended_plugins"]:
            visit(parent, True)
        prefix = (
            "modules/" + name + ("/spi/" if exported and graph[name]["spi"] else "/")
        )
        for path in sorted(files):
            if (
                path.startswith(prefix)
                and "/" not in path[len(prefix) :]
                and path.endswith(".jar")
                and path not in result
            ):
                result.append(path)
        active.remove(name)

    visit(realm, False)
    return result


def collect(realm, inventory, staged, tree, cache, replacements):
    models, refs, consumers, origins = {}, {}, [], {}
    pins = {
        p["file"]: p
        for p in json.loads((HERE / "reusable-official-pins.json").read_text())["files"]
    }
    for relative in visible_paths(realm, inventory["graph"], staged["files"]):
        file = q.safe_file(tree / relative)
        if q.sha(file) != staged["files"][relative]["sha256"]:
            raise ValueError("staged artifact drift")
        candidate_name = (
            replacements.get(file.name) if relative.startswith("modules/apm/") else None
        )
        if candidate_name:
            file = q.safe_file(cache / candidate_name)
            if q.sha(file) != pins[candidate_name]["sha256"]:
                raise ValueError("official SDK artifact drift")
        for entry, model in q.s.classes(file, inventory["java_feature"]):
            label = relative + "!" + entry
            if model["name"].startswith("io/opentelemetry/"):
                if model["name"] in models:
                    raise ValueError(
                        "shadowed OTel provider needs exact branch-sensitive loader proof"
                    )
                models[model["name"]] = model
                origins[model["name"]] = relative
            if model["references"]:
                refs[label] = [tuple(r) for r in model["references"]]
                consumers.append(
                    {
                        "entry": label,
                        "public": bool(model["flags"] & 1),
                        "internal": "/internal/" in model["name"],
                    }
                )
    references = [(label, ref) for label, values in refs.items() for ref in values]
    if not models or not consumers or not references:
        raise ValueError("vacuous realm/parent consumers")
    return models, references, consumers, origins


def compare(realm, inventory, staged, tree, cache):
    original, _, _, _ = collect(realm, inventory, staged, tree, cache, {})
    experiment = q.sdk_experiment(inventory) if realm == "apm" else {}
    candidate, refs, consumers, origins = collect(
        realm, inventory, staged, tree, cache, experiment
    )
    mutant = dict(candidate)
    mutant.pop("io/opentelemetry/api/OpenTelemetry", None)
    negatives = q.s.newly_broken(candidate, mutant, refs)
    if not negatives:
        raise ValueError("vacuous missing-API negative control")
    broken = q.s.newly_broken(original, candidate, refs)
    unresolved = [
        {"consumer": label, "reference": list(ref)}
        for label, ref in refs
        if not q.s.resolve(candidate, ref[0], (ref[3], ref[1], ref[2]))
    ]
    return {
        "realm": realm,
        "status": "symbolic-only-not-eligibility",
        "replacement": None,
        "runtime_approved": False,
        "experiment_only": experiment,
        "visible_jars": visible_paths(realm, inventory["graph"], staged["files"]),
        "OTel_provider_origins": origins,
        "consumer_entries": len(consumers),
        "references": len(refs),
        "public_consumer_entries": sum(c["public"] for c in consumers),
        "internal_consumer_entries": sum(c["internal"] for c in consumers),
        "newly_broken_modeled_references": broken,
        "candidate_unresolved": unresolved,
        "missing_API_negative_control_failures": len(negatives),
        "limits": q.LIMITS,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--inventory", type=Path, required=True)
    parser.add_argument("--staged-manifest", type=Path, required=True)
    parser.add_argument("--tree", type=Path, required=True)
    parser.add_argument("--cache", type=Path, required=True)
    parser.add_argument("--realm", choices=q.REALMS, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    # The model is portable; bounded execution requires POSIX resource limits.
    import resource

    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    resource.setrlimit(resource.RLIMIT_AS, (400 * 1024**2,) * 2)
    resource.setrlimit(resource.RLIMIT_CPU, (165, 165))
    if args.output.exists():
        raise ValueError("refusing to overwrite proof")
    expected = json.loads((HERE / "inventory-result.json").read_text())
    if (
        q.sha(q.safe_file(args.inventory))
        != expected["metadata_sha256"]["inventory.json"]
    ):
        raise ValueError("inventory proof drift")
    inventory = json.loads(args.inventory.read_text())
    staged = json.loads(args.staged_manifest.read_text())
    if (
        staged["status"] != "staged-inputs-only"
        or staged["replacement"] is not None
        or staged["runtime_approved"]
    ):
        raise ValueError("unverified staged input manifest")
    source = {p.name: q.sha(p) for p in HERE.iterdir() if p.is_file()}
    result = compare(args.realm, inventory, staged, args.tree, args.cache)
    if source != {p.name: q.sha(p) for p in HERE.iterdir() if p.is_file()}:
        raise ValueError("qualification source drift")
    result["source_sha256"] = source
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
