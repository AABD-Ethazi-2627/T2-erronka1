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


def validate(image: str, report: dict) -> list[str]:
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
