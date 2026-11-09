"""Fail-closed experiment status and reproducible summary; never runtime approval."""

import argparse
import hashlib
import json
from pathlib import Path

PASSED = "aligned-qualification-phases-passed-not-runtime-approval"
PHASE_STATUS = {
    "oracle": "published-closure-equals-real-Maven",
    "static": "aligned-symbolic-analysis-completed",
    "runtime": "bounded-real-NarClassLoader-aligned-controls-passed",
}
METADATA = (
    "aligned-pins.json",
    "aligned-result.json",
    "narrow-result.json",
    "known-inputs.json",
    "incubator-allowlist.json",
    "loader-inputs.json",
)


def require_preparation(record):
    if (
        not isinstance(record, dict)
        or record.get("runtime_approved") is not False
        or "replacement" not in record
        or record["replacement"] is not None
    ):
        raise ValueError(
            "metadata must retain replacement:null and runtime_approved:false"
        )


def check_metadata(root):
    for name in METADATA:
        require_preparation(read_json(Path(root) / name)[0])


def read_json(path):
    if any(p.is_symlink() for p in (path, *path.parents)) or not path.is_file():
        raise ValueError("missing or linked proof input: " + str(path))
    raw = path.read_bytes()
    return json.loads(raw), hashlib.sha256(raw).hexdigest()


def finish_report(report):
    """Both the process status and the saved outcome must fail on any gap."""
    require_preparation(report)
    commands = report.get("commands", [])
    required = {"portable-guards", *PHASE_STATUS}
    valid = (
        report.get("status") == PASSED
        and len(commands) == len(required)
        and {c.get("phase") for c in commands} == required
        and all(
            type(c.get("returncode")) is int and c["returncode"] == 0 for c in commands
        )
        and report.get("image_identity_unchanged") is True
        and report.get("source_unchanged") is True
        and report.get("remaining_owned_containers") == []
        and not report.get("finalization_errors")
    )
    if not valid:
        report["status"] = "blocked-aligned-qualification"
        report.setdefault(
            "error", "Incomplete phases, integrity verification or cleanup"
        )
    return 0 if valid else 1


def seal_summary(proof, output):
    proof, output = Path(proof), Path(output)
    runner, runner_sha = read_json(proof / "aligned-reserved-result.json")
    if finish_report(runner):
        raise ValueError("cannot seal blocked or incomplete qualification")
    phases, hashes = {}, {"aligned-reserved-result.json": runner_sha}
    prefix = "deploy/images/nifi-patches/otel-qualification/"
    expected_sources = {
        "/tools/" + name.removeprefix(prefix): digest
        for name, digest in runner.get("source_sha256", {}).items()
        if name.startswith(prefix) and "/" not in name.removeprefix(prefix)
    }
    if not expected_sources:
        raise ValueError("source crosshash coverage missing")
    for phase, expected in PHASE_STATUS.items():
        name = phase + "-result.json"
        data, digest = read_json(proof / name)
        require_preparation(data)
        if data.get("phase") != phase or data.get("status") != expected:
            raise ValueError("phase status does not demonstrate completion: " + phase)
        if (
            data.get("sources_before") != expected_sources
            or data.get("sources_after") != expected_sources
        ):
            raise ValueError("phase/runner source crosshash mismatch: " + phase)
        phases[phase] = data
        hashes[name] = digest
    result = {
        "schema": 1,
        "status": PASSED,
        "replacement": None,
        "runtime_approved": False,
        "scope": "sealed phase reports, not full consumer, CVE, image or service acceptance",
        "phase_reports": phases,
        "input_sha256": hashes,
        "consumer_initialization": {
            x["variant"]: {
                "consumer_init_passed": sorted(
                    k
                    for k, v in x["observed_external_consumer_initialization"].items()
                    if v["status"] == "PASS"
                ),
                "consumer_init_failed": {
                    k: v["cause"]
                    for k, v in x["observed_external_consumer_initialization"].items()
                    if v["status"] == "FAIL"
                },
            }
            for x in phases["runtime"].get("outcomes", [])
        },
    }
    with output.open("x") as handle:
        handle.write(json.dumps(result, indent=2, sort_keys=True) + "\n")
    return result


def export_compact_manifest(proof, output):
    """Positive export of exact snapshotted source and recorded raw phase outputs."""
    proof = Path(proof)
    runner, _ = read_json(proof / "aligned-reserved-result.json")
    names = {
        "aligned-reserved-result.json",
        "guards-green.log",
        "summary.json",
        "runner.log",
        "runner.exit",
        "preflight.json",
        "external-consumers-for-probe.json",
        "consumer-origins.json",
        "consumer-origins.tsv",
        "runtime-parents.tsv",
        "aligned-consumers.json",
        "tracestate-encoding-source-diff.patch",
    }
    for phase in PHASE_STATUS:
        names.update({phase + ".stdout", phase + ".stderr", phase + "-result.json"})
        record, _ = read_json(proof / (phase + "-result.json"))
        for command in record.get("commands", []):
            label = command["label"]
            if not label or Path(label).name != label:
                raise ValueError("unsafe output label")
            names.update(
                {label + ".stdout", label + ".stderr", label + ".class-load.log"}
            )
    result = {}
    for name, digest in runner.get("source_sha256", {}).items():
        if Path(name).is_absolute() or ".." in Path(name).parts:
            raise ValueError("unsafe source path")
        file = proof / "source" / name
        raw = file.read_bytes()
        if file.is_symlink() or hashlib.sha256(raw).hexdigest() != digest:
            raise ValueError("export source drift")
        result["source/" + name] = digest
    if not result:
        raise ValueError("empty source export")
    for name in sorted(names):
        file = proof / name
        if file.exists() or file.is_symlink():
            if file.is_symlink() or not file.is_file():
                raise ValueError("linked/non-file export input")
            result[name] = hashlib.sha256(file.read_bytes()).hexdigest()
    with Path(output).open("x") as f:
        f.write(json.dumps(result, indent=2, sort_keys=True) + "\n")
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--proof", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--export-manifest", action="store_true")
    args = parser.parse_args()
    (export_compact_manifest if args.export_manifest else seal_summary)(
        args.proof, args.output
    )


def finish_narrow_report(report, phases):
    require_preparation(report)
    commands = report.get("commands", [])
    completed = {c.get("phase") for c in commands if c.get("returncode") == 0}
    passed = (
        report.get("status")
        in {
            "bounded-component-qualification-phases-passed",
            "bounded-requested-phase-passed",
        }
        and bool(phases)
        and set(phases) <= completed
        and "unit-green" in completed
        and all(
            type(c.get("returncode")) is int and c["returncode"] == 0 for c in commands
        )
        and report.get("image_identity_unchanged") is True
        and report.get("source_unchanged") is True
        and report.get("remaining_owned_containers") == []
    )
    if not passed:
        report["status"] = "qualification-blocked-or-failed"
    return 0 if passed else 1


if __name__ == "__main__":
    main()
