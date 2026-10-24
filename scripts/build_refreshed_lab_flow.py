"""Retarget the preserved 2.0 laboratory export for a disabled NiFi 2.12 import."""

import argparse
import copy
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "nifi-flows/cnc_lab_completed_nifi_2.12.0.json"


def build():
    flow = copy.deepcopy(
        json.loads((ROOT / "nifi-flows/cnc_lab_completed.json").read_text())
    )
    components = json.loads(
        (ROOT / "tests/fixtures/nifi-2.12-lab-components.json").read_text()
    )["components"]

    def retarget(value):
        if isinstance(value, dict):
            bundle = value.get("bundle")
            if bundle and bundle.get("group") == "org.apache.nifi":
                if bundle["version"] != "2.0.0":
                    raise ValueError(
                        "Review the changed source bundle before retargeting"
                    )
                bundle["version"] = "2.12.0"
                if "properties" in value:
                    # NiFi 2.12 uses canonical display names for many properties.
                    # A bundle-only rewrite silently loses scripts, schemas and
                    # service references. Names come from real 2.12 descriptors.
                    renames = components[value["type"]]["property_renames"]
                    properties, descriptors = {}, {}
                    for old, setting in value["properties"].items():
                        descriptor = value.get("propertyDescriptors", {}).get(old, {})
                        name = renames.get(old)
                        if name is None and descriptor.get("dynamic"):
                            name = old
                        if name is None:
                            if setting is not None:
                                raise ValueError(f"Unmapped NiFi property: {old}")
                            continue
                        properties[name] = setting
                        descriptors[name] = {
                            **descriptor,
                            "name": name,
                            "displayName": name,
                        }
                    if (
                        value["type"]
                        == "org.apache.nifi.elasticsearch.ElasticSearchClientServiceImpl"
                    ):
                        # Match the explicitly anonymous, private lab ES service;
                        # the old BASIC-with-empty-credentials import is invalid.
                        properties["Authorization Scheme"] = "NONE"
                    value["properties"] = properties
                    value["propertyDescriptors"] = descriptors
            if "scheduledState" in value:
                value["scheduledState"] = "DISABLED"
            for child in value.values():
                retarget(child)
        elif isinstance(value, list):
            for child in value:
                retarget(child)

    retarget(flow)
    flow["flowContents"]["name"] = "CNC lab — NiFi 2.12 (disabled review import)"
    return flow


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    content = json.dumps(build(), ensure_ascii=False, indent=2) + "\n"
    if args.check:
        if not OUTPUT.is_file() or OUTPUT.read_bytes() != content.encode():
            parser.exit(
                1,
                "Refreshed flow is stale; run python -m scripts.build_refreshed_lab_flow\n",
            )
    else:
        OUTPUT.write_bytes(content.encode())


if __name__ == "__main__":
    main()
