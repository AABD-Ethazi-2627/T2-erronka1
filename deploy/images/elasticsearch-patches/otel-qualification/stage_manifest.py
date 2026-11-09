"""Verify private VM copy output without flattening root/SPI loader boundaries."""

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def digest(path):
    d = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(65536), b""):
            d.update(block)
    return d.hexdigest()


def verify(inventory, copy_text, tree):
    expected_closure = json.loads((HERE / "inventory-result.json").read_text())[
        "required_graph_closure"
    ]
    records = {}
    summary = None
    for line in copy_text.splitlines():
        row = line.split("\t")
        if row[0] == "STATUS":
            if (
                summary is not None
                or len(row) != 6
                or row[1] != "stage-only"
                or row[-2:] != ["replacement=null", "runtime_approved=false"]
            ):
                raise ValueError("stage status malformed")
            summary = (int(row[2]), int(row[3]))
            continue
        if row[0] != "COPY" or len(row) != 4 or summary is not None:
            raise ValueError("unexpected stage row")
        _, name, size, sha = row
        path = Path(name)
        if path.is_absolute() or ".." in path.parts or name in records:
            raise ValueError("unsafe or duplicate copied path")
        if not (
            (path.parts[0] == "lib" and len(path.parts) == 2 and name.endswith(".jar"))
            or (
                path.parts[0] == "modules"
                and path.parts[1] in expected_closure
                and (
                    len(path.parts) == 3
                    or len(path.parts) == 4
                    and path.parts[2] == "spi"
                )
            )
        ):
            raise ValueError("unexpected loader input boundary")
        target = Path(tree) / path
        if (
            any(p.is_symlink() for p in (target, *target.parents))
            or not target.is_file()
        ):
            raise ValueError("missing or linked staged input")
        if target.stat().st_size != int(size) or digest(target) != sha:
            raise ValueError("copied input hash/size drift")
        records[name] = {"sha256": sha, "size": int(size)}
    if (
        summary != (len(records), sum(r["size"] for r in records.values()))
        or not records
    ):
        raise ValueError("incomplete copied manifest")
    realms = {Path(name).parts[1] for name in records if name.startswith("modules/")}
    if realms != set(expected_closure):
        raise ValueError("incomplete copied extension graph")
    for realm, data in inventory["realms"].items():
        expected = {
            f"modules/{realm}/{name}": pin for name, pin in data["jars"].items()
        }
        actual = {
            name
            for name in records
            if name.startswith("modules/" + realm + "/") and name.endswith(".jar")
        }
        if actual != set(expected):
            raise ValueError("selected-realm artifact set drift")
        for name, pin in expected.items():
            if (
                records[name]["sha256"] != pin["sha256"]
                or records[name]["size"] != pin["size"]
            ):
                raise ValueError("selected-realm input identity drift")
        for filename, key in [
            ("plugin-descriptor.properties", "descriptor_sha256"),
            ("entitlement-policy.yaml", "entitlement_sha256"),
        ]:
            if (
                records.get(f"modules/{realm}/{filename}", {}).get("sha256")
                != data[key]
            ):
                raise ValueError("selected-realm policy/descriptor drift")
    loader = inventory["loader"][0]
    if records.get("lib/" + loader[0], {}).get("sha256") != loader[1]:
        raise ValueError("installed loader artifact drift")
    return {
        "status": "staged-inputs-only",
        "replacement": None,
        "runtime_approved": False,
        "files": records,
        "module_closure": expected_closure,
        "boundaries": "boot lib; each root and SPI remain distinct; no namespace flattening",
    }


def main():
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--inventory", type=Path, required=True)
    parser.add_argument("--copy-log", type=Path, required=True)
    parser.add_argument("--tree", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError("refusing to overwrite proof")
    expected = json.loads((HERE / "inventory-result.json").read_text())[
        "metadata_sha256"
    ]["inventory.json"]
    if digest(args.inventory) != expected:
        raise ValueError("measured inventory proof drift")
    report = verify(
        json.loads(args.inventory.read_text()), args.copy_log.read_text(), args.tree
    )
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
