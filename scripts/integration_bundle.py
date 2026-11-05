"""Allowlisted source/evidence ZIP; no model, credential, cache or environment trees."""

import argparse
import hashlib
import json
import subprocess
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TREES = {
    "scripts",
    "scoring",
    "tests",
    "contracts",
    "dashboard_laneki",
    "deploy",
    "elasticsearch",
    "filebeat",
    "kibana",
    "nifi",
    "engine",
    "cnc_guard",
    "nifi-flows",
    "cg14_validation",
    "lan",
}
EXTENSIONS = {
    ".py",
    ".json",
    ".yaml",
    ".yml",
    ".toml",
    ".md",
    ".txt",
    ".css",
    ".schema",
    ".lock",
    ".js",
    ".sh",
    ".webp",
    ".png",
    ".svg",
    ".ndjson",
    ".Dockerfile",
    ".patch",
    ".xml",
    ".csv",
    ".rs",
    ".go",
    ".java",
    ".sum",
    ".mod",
    ".in",
    ".groovy",
    ".cjs",
    ".c",
    ".properties",
    ".cfg",
}
RESULTS = {
    "result.json",
    "fixture.json",
    "canonical.json",
    "es-double.json",
    "get-snapshot.json",
    "get-history.json",
}


def build(output, evidence):
    output, evidence = Path(output), Path(evidence)
    tracked = (
        subprocess.check_output(["git", "ls-files", "-z"], cwd=ROOT)
        .decode()
        .split("\0")
    )
    selected = []
    for name in filter(None, tracked):
        p = Path(name)
        if (
            name
            in {
                "uv.lock",
                ".dockerignore",
                "docker-compose.yml",
                "docker-compose.lan.yml",
                "data/ai4i2020_train.csv",
                "docs/evidence/CG26_REHEARSAL_2026-10-21.json",
                "README.md",
                "vendor/README.md",
                "vendor/kafka-python-provenance.json",
                "vendor/kafka_python-3.0.11+cncguard.2-py3-none-any.whl",
                "pyproject.toml",
                "docs/integration/README.md",
                "docs/integration/LOCAL_HTTP.md",
                "docs/integration/LOCAL_WORKER.md",
                "docs/integration/LOCAL_KAFKA.md",
                "docs/integration/LOCAL_FILEBEAT.md",
                "docs/integration/LOCAL_IMAGE_BUILDS.md",
                "docs/integration/NIFI_CANDIDATE.md",
                "docs/evidence/INTEGRATION_CANDIDATES_20261105.md",
                "docs/evidence/INTEGRATION_CANDIDATES_20261105.json",
                "docs/evidence/CLAUDE_NIFI_GUARDS_HADOOP_FINAL_RECHECK_20261105.md",
                "docs/evidence/CLAUDE_HAZELCAST_WRAPPER_REVIEW_20261105.md",
                "docs/evidence/CLAUDE_PARQUET_WRAPPER_REVIEW_20261105.md",
                "docs/evidence/LOCAL_PIPELINE_BROWSER_20261103.md",
                "docs/evidence/LOCAL_CONTAINERS_20261103.md",
                "docs/evidence/LOCAL_HTTP_20261103.md",
                "docs/integration/issues.json",
                "docs/backend/READ_API.md",
                "dashboard_laneki/INTEGRATION.md",
            }
            or (name.startswith(".github/workflows/") and p.suffix in {".yml", ".yaml"})
            or (
                p.parts[0] in TREES
                and (p.suffix in EXTENSIONS or p.name == "Dockerfile")
                and not any(
                    part.startswith(".")
                    or part in {"models", "__pycache__", "node_modules"}
                    for part in p.parts
                )
            )
        ):
            selected.append((name, ROOT / name))
    selected += [("evidence/" + name, evidence / name) for name in sorted(RESULTS)]
    # Only this runner's pristine archive, never arbitrary operator archive roots.
    for path in (evidence / "pristine-archive").rglob("*"):
        if path.is_file() and (
            path.name == "ledger.sqlite" or path.suffix in {".parquet", ".bin"}
        ):
            selected.append(("evidence/" + str(path.relative_to(evidence)), path))
    hashes = {}
    # Exclusive creation: previous evidence is never replaced.
    with zipfile.ZipFile(output, "x", compression=zipfile.ZIP_DEFLATED) as archive:
        total = 0
        for name, path in selected:
            if path.is_symlink() or not path.is_file():
                raise ValueError("missing or symlink input: " + name)
            total += path.stat().st_size
            if total > 40 * 1024**2:
                raise ValueError("bundle exceeds 40 MiB source budget")
            raw = path.read_bytes()
            hashes[name] = hashlib.sha256(raw).hexdigest()
            archive.writestr(name, raw)
        source = {
            "revision": subprocess.check_output(
                ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
            ).strip(),
            "dirty": bool(
                subprocess.check_output(
                    ["git", "status", "--porcelain"], cwd=ROOT, text=True
                )
            ),
        }
        raw = json.dumps(source, indent=2).encode()
        hashes["BUNDLE_SOURCE.json"] = hashlib.sha256(raw).hexdigest()
        archive.writestr("BUNDLE_SOURCE.json", raw)
        archive.writestr("SHA256.json", json.dumps(hashes, indent=2))
    with zipfile.ZipFile(output) as archive, tempfile.TemporaryDirectory() as temp:
        if archive.testzip() is not None:
            raise ValueError("ZIP CRC failed")
        for name, sha in hashes.items():
            if hashlib.sha256(archive.read(name)).hexdigest() != sha:
                raise ValueError("ZIP hash mismatch")
        sample = "evidence/fixture.json"
        archive.extract(sample, temp)
        if (
            hashlib.sha256((Path(temp) / sample).read_bytes()).hexdigest()
            != hashes[sample]
        ):
            raise ValueError("sample restore mismatch")
    result = {
        "sha256": hashlib.sha256(output.read_bytes()).hexdigest(),
        "files": len(hashes),
        "crc": "passed",
        "all_member_hashes": "passed",
        "sample_restore": "passed",
    }
    output.with_suffix(".sha256.json").write_text(json.dumps(result, indent=2))
    return result


if __name__ == "__main__":
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--output", type=Path, required=True)
    cli.add_argument("--evidence", type=Path, required=True)
    args = cli.parse_args()
    print(json.dumps(build(args.output, args.evidence), indent=2))
