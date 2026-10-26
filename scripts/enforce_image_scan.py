"""Fail closed on image findings, with two narrowly verified patched cases."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

VERIFIED_FINDINGS = {
    "filebeat": {
        ("GO-2026-5932", "golang.org/x/crypto", "v0.57.0"),
    },
    "kibana": {
        ("CVE-2026-85393", "node-forge", "1.4.0+cncguard.1"),
        ("CVE-2026-19693", "extract-zip", "2.0.1+cncguard.1"),
        ("CVE-2026-56876", "extract-zip", "2.0.1+cncguard.1"),
    },
}


def findings(report: dict) -> set[tuple[str, str, str]]:
    return {
        (
            vulnerability["VulnerabilityID"],
            vulnerability["PkgName"],
            vulnerability["InstalledVersion"],
        )
        for result in report.get("Results", [])
        for vulnerability in result.get("Vulnerabilities") or []
    }


def expected_reference(image: str) -> str | None:
    root = Path(__file__).resolve().parents[1]
    targets = json.loads((root / "deploy/build-targets.json").read_bytes())
    if image in targets:
        return "cnc-guard-audit:" + image
    return json.loads((root / "deploy/images.json").read_bytes()).get(image)


def validate(
    image: str, report: dict, *, expected_artifact: str | None = None
) -> list[str]:
    # An empty/misdirected report is missing coverage, not a clean image scan.
    if not isinstance(report, dict) or (
        report.get("SchemaVersion") != 2
        or report.get("ArtifactType") != "container_image"
        or not report.get("ArtifactName")
    ):
        return ["missing Trivy container image report identity"]
    expected = expected_artifact or expected_reference(image)
    if expected is None or report["ArtifactName"] != expected:
        return ["image report does not identify the expected scan artifact"]
    metadata = report.get("Metadata")
    if (
        not isinstance(metadata, dict)
        or not isinstance(metadata.get("ImageID"), str)
        or not metadata["ImageID"]
    ):
        return ["image report contains no image ID"]
    results = report.get("Results")
    if not isinstance(results, list) or not results:
        return ["image report contains no analyzed targets"]
    for result in results:
        if not isinstance(result, dict) or not all(
            result.get(field) for field in ("Target", "Class", "Type")
        ):
            return ["image report contains an unidentified analysis target"]
        if result["Class"] not in ("os-pkgs", "lang-pkgs"):
            return ["image report contains an unsupported analysis class"]
        packages = result.get("Packages")
        if (
            not isinstance(packages, list)
            or not packages
            or not all(
                isinstance(package, dict) and package.get("Name")
                for package in packages
            )
            or not any(package.get("Version") for package in packages)
        ):
            return ["image report contains an analysis target without package coverage"]
        vulnerabilities = result.get("Vulnerabilities")
        if vulnerabilities is not None and (
            not isinstance(vulnerabilities, list)
            or not all(
                isinstance(item, dict)
                and all(
                    isinstance(item.get(field), str) and item[field]
                    for field in ("VulnerabilityID", "PkgName", "InstalledVersion")
                )
                for item in vulnerabilities
            )
        ):
            return ["image report contains malformed vulnerability records"]
    analyzed = {(result["Class"], result["Type"]) for result in results}
    if image != "uv" and not any(kind == "os-pkgs" for kind, _ in analyzed):
        return ["image report contains no operating system package coverage"]
    required = {"api": ("lang-pkgs", "python-pkg"), "uv": ("lang-pkgs", "rustbinary")}
    if image in required and required[image] not in analyzed:
        return ["image report is missing required runtime package coverage"]
    found = findings(report)
    permitted = VERIFIED_FINDINGS.get(image, set())
    unexpected = found - permitted
    missing = permitted - found
    errors = [f"unexpected vulnerability: {item!r}" for item in sorted(unexpected)]
    if image in VERIFIED_FINDINGS:
        errors.extend(
            f"verified patched finding disappeared; review the exception: {item!r}"
            for item in sorted(missing)
        )
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("image")
    parser.add_argument("report", type=Path)
    args = parser.parse_args()
    errors = validate(args.image, json.loads(args.report.read_text()))
    for error in errors:
        print(error)
    return bool(errors)


if __name__ == "__main__":
    raise SystemExit(main())
