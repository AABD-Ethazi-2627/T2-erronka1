"""Reject missing fork identity/findings in the standalone renamed-JAR experiment.

This is not a NiFi classloader inventory or a replacement for the image gate.
"""

import argparse
import hashlib
import json
import zipfile
from pathlib import Path


def verify(directory, report):
    pins = json.loads((Path(__file__).parent / "verification-pins.json").read_text())
    packages = [
        p for target in report.get("Results", []) for p in target.get("Packages", [])
    ]
    findings = [
        v
        for target in report.get("Results", [])
        for v in target.get("Vulnerabilities", [])
    ]
    checked = 0
    for jar in directory.rglob("*.jar"):
        with zipfile.ZipFile(jar) as archive:
            if "com/squareup/wire/ProtoReader.class" not in archive.namelist():
                continue
        digest = hashlib.sha256(jar.read_bytes()).hexdigest()
        if digest != pins["candidate_sha256"] or jar.name != digest + ".jar":
            raise ValueError("Unexpected or unreviewed reader artifact")
        relative = jar.relative_to(directory).as_posix()
        if not any(
            p.get("Name") == "com.squareup.wire:wire-runtime-jvm"
            and p.get("Version") == "5.2.0+cncguard.1"
            and p.get("FilePath") == relative
            for p in packages
        ):
            raise ValueError("Reader artifact missing from scanner package inventory")
        if not any(
            v.get("VulnerabilityID") == "CVE-2026-45799"
            and v.get("PkgName") == "com.squareup.wire:wire-runtime-jvm"
            and v.get("InstalledVersion") == "5.2.0+cncguard.1"
            and v.get("PkgPath") == relative
            for v in findings
        ):
            raise ValueError(
                "Expected Wire finding disappeared; review scanner coverage"
            )
        checked += 1
    if not checked:
        raise ValueError("No reader artifacts checked")
    return {
        "reader_artifacts_checked": checked,
        "finding_visible": True,
        "scope": "standalone experiment only",
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    parser.add_argument("report", type=Path)
    args = parser.parse_args()
    print(
        json.dumps(
            verify(args.directory, json.loads(args.report.read_text())), indent=2
        )
    )
