"""Write explicit-root Maven experiments; execute real Maven separately.

These POMs preserve vendor OTel direct overrides, including alpha artifacts.
They describe Maven mediation, not Elastic's Gradle JVM-variant selection.
"""

import argparse
import json
import xml.etree.ElementTree as ET
from pathlib import Path

HERE = Path(__file__).resolve().parent
# Measured installed JVM variants. Maven cannot infer Gradle .module selection.
VENDOR_JVM_ROOTS = [
    "org.jetbrains.kotlin:kotlin-stdlib:2.2.21",
    "com.squareup.okhttp3:okhttp-jvm:5.3.2",
    "com.squareup.okio:okio-jvm:3.17.0",
    "com.squareup.wire:wire-runtime-jvm:6.4.0",
]


def pom(roots):
    root = ET.Element("project", xmlns="http://maven.apache.org/POM/4.0.0")
    for key, value in (
        ("modelVersion", "4.0.0"),
        ("groupId", "local.cncguard"),
        ("artifactId", "otel-oracle"),
        ("version", "1"),
    ):
        ET.SubElement(root, key).text = value
    deps = ET.SubElement(root, "dependencies")
    for coordinate in roots:
        group, artifact, version = coordinate.split(":")
        dep = ET.SubElement(deps, "dependency")
        for key, value in (
            ("groupId", group),
            ("artifactId", artifact),
            ("version", version),
        ):
            ET.SubElement(dep, key).text = value
        if artifact == "opentelemetry-disk-buffering":
            exclusions = ET.SubElement(dep, "exclusions")
            exclusion = ET.SubElement(exclusions, "exclusion")
            ET.SubElement(exclusion, "groupId").text = "com.squareup.wire"
            ET.SubElement(exclusion, "artifactId").text = "wire-runtime"
    ET.indent(root)
    return ET.tostring(root, encoding="unicode") + "\n"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    model = json.loads((HERE / "published-roots.json").read_text())
    args.output.mkdir(parents=True, exist_ok=False)
    for variant in ("current", "sdk_six", "aligned"):
        directory = args.output / variant
        directory.mkdir()
        roots = model[("sdk_six" if variant == "aligned" else variant) + "_roots"]
        vendor = VENDOR_JVM_ROOTS
        if variant == "aligned":
            roots = [
                x.rsplit(":", 1)[0] + ":1.67.0"
                if ":opentelemetry-exporter-" in x
                else x.rsplit(":", 1)[0] + ":1.67.0-alpha"
                if ":opentelemetry-api-incubator:" in x
                else x
                for x in roots
            ]
            vendor = [
                x.replace("okhttp-jvm:5.3.2", "okhttp-jvm:5.5.0").replace(
                    "okio-jvm:3.17.0", "okio-jvm:3.18.1"
                )
                for x in vendor
            ]
        (directory / "pom.xml").write_text(pom(roots + vendor), encoding="utf-8")


if __name__ == "__main__":
    main()
