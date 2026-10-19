"""Package only the four verified synthetic partitions, never models or original AI4I."""

import argparse
import hashlib
import json
import zipfile
from pathlib import Path

NOTICE = (
    "SYNTHETIC SEASONAL SCENARIO ONLY\nAll rows and dates are invented. Separate from original AI4I.\n"
    "Independent seeds share simulator rules, not independent industrial truth.\n"
    "Keep train/validation/evaluation/stress partitions separate. Do not random-split hourly rows.\n"
    "Forecast quality is insufficient for operational maintenance decisions.\n"
    "See docs/evidence/CG11_ESTACIONAL_V2.md and versioned report.\n"
)


def package(root):
    root = Path(root)
    report = json.loads((root / "report.json").read_text())
    names = ["train", "validation", "evaluation", "stress"]
    if set(report["datasets"]) != set(names):
        raise ValueError("Unexpected dataset partitions")
    paths = {f"{name}.parquet": root / f"{name}.parquet" for name in names}
    hashes = {}
    for name in names:
        digest = hashlib.sha256(paths[f"{name}.parquet"].read_bytes()).hexdigest()
        if digest != report["datasets"][name]["sha256"]:
            raise ValueError("Partition differs from generator evidence")
        hashes[f"{name}.parquet"] = digest
    manifest = {
        "source_kind": "synthetic_seasonal_v2",
        "warning": "Entirely invented scenario; not AI4I augmentation or observed industrial data. Not suitable as proof of industrial forecast precision.",
        "scenario": report["scenario"],
        "datasets": report["datasets"],
        "ai4i_source_sha256": report["ai4i_source_sha256"],
        "selection": report["selection"]["selected_by_validation_ap"],
    }
    metadata = {
        "dataset_manifest.json": (json.dumps(manifest, indent=2) + "\n").encode(),
        "DATASET_NOTICE.txt": NOTICE.encode(),
    }
    hashes.update(
        {name: hashlib.sha256(data).hexdigest() for name, data in metadata.items()}
    )
    output = root / "dataset_bundle.zip"
    if output.exists():
        with zipfile.ZipFile(output) as bundle:
            if set(bundle.namelist()) != set(hashes) or bundle.testzip() is not None:
                raise ValueError(
                    "Existing bundle contents differ; preserve and investigate"
                )
            for name, digest in hashes.items():
                if hashlib.sha256(bundle.read(name)).hexdigest() != digest:
                    raise ValueError(
                        "Existing bundle bytes differ; never overwrite evidence"
                    )
        return output
    with zipfile.ZipFile(output, "x", compression=zipfile.ZIP_STORED) as bundle:
        for name, path in paths.items():
            bundle.write(path, name)
        for name, data in metadata.items():
            bundle.writestr(name, data)
    with zipfile.ZipFile(output) as bundle:
        if bundle.testzip() is not None:
            raise ValueError("Bundle integrity check failed")
    return output


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("outputs/seasonal-v2"))
    print(package(parser.parse_args().root))
