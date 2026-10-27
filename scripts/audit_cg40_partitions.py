"""Audit published CG40 row identities without loading data, models or pickles."""

import argparse
import hashlib
import json
from pathlib import Path


def identities(values):
    if any(type(value) is not int or not 0 <= value < 8000 for value in values):
        raise ValueError("Invalid source row identity")
    result = set(values)
    if len(result) != len(values):
        raise ValueError("Duplicate source row identity")
    return result


def folds(items, population, label):
    if len(items) != 3:
        raise ValueError(f"{label}: expected three folds")
    observed = set()
    sizes = []
    for item in items:
        fit, held = identities(item["fit"]), identities(item["held"])
        if not fit or not held or fit & held or fit | held != population:
            raise ValueError(f"{label}: overlapping or incomplete partition")
        if observed & held:
            raise ValueError(f"{label}: repeated held identity across folds")
        observed.update(held)
        sizes.append({"fit": len(fit), "held": len(held)})
    if observed != population:
        raise ValueError(f"{label}: held folds do not cover population")
    return sizes


def audit(manifest):
    membership = manifest["membership"]
    groups = {
        name: identities(membership[name])
        for name in ("train", "validation", "excluded")
    }
    if [len(groups[name]) for name in groups] != [5600, 1200, 1200]:
        raise ValueError("Unexpected original split sizes")
    if set.union(*groups.values()) != set(range(8000)):
        raise ValueError("Original split overlap or missing source identities")
    train = groups["train"]
    screening = folds(manifest["screening"], train, "screening")
    outer = folds(manifest["outer"], train, "outer")
    inner = [
        folds(item["inner"], identities(item["fit"]), f"inner {index}")
        for index, item in enumerate(manifest["outer"])
    ]
    return {
        "status": "pass",
        "membership_sizes": {name: len(rows) for name, rows in groups.items()},
        "screening": screening,
        "outer": outer,
        "inner": inner,
        "limits": [
            "Published manifest identities only; not execution or score verification",
            "No dataset, excluded test, model or pickle loaded",
            "No calibration-fit membership or native reload independently verified",
            "SELF_REVIEW / NOT_INDEPENDENT; no human acceptance or promotion",
        ],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("docs/evidence/CG34_20261023"))
    args = parser.parse_args()
    raw = (args.root / "manifest.json").read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    seal = json.loads((args.root / "seal.json").read_text())
    if digest != seal["manifest_sha256"]:
        raise ValueError("Manifest seal mismatch")
    result = audit(json.loads(raw))
    result["manifest_sha256"] = digest
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
