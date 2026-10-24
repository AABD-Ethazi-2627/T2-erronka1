"""Check tracked artifacts and root Compose paths without starting services."""

import json
import os
import shlex
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def run(*args):
    return subprocess.check_output(args, cwd=ROOT, text=True, stderr=subprocess.PIPE)


def check():
    errors = []
    tracked = run("git", "ls-files", "-z").split("\0")
    for name in tracked:
        if any(
            part in {".ipynb_checkpoints", "__pycache__", ".venv", "venv"}
            for part in Path(name).parts
        ):
            errors.append(f"Generated artifact tracked: {name}")
        if Path(name).name.startswith(".env") and not name.endswith(".example"):
            errors.append(f"Private environment tracked: {name}")
    probes = {
        ".venv/bin/python": True,
        "notebooks/.ipynb_checkpoints/probe.ipynb": True,
        "scoring/__pycache__/probe.pyc": True,
        ".env.local": True,
        "outputs/api/rf.pkl": True,
        "historical/bronze/probe.csv": True,
        "models/probe.pkl": True,
        ".env.example": False,
        ".env.smb.example": False,
        "data/probe.csv": False,
        "docs/evidence/probe.json": False,
        "docs/evidence/probe.png": False,
        "contracts/examples/probe.json": False,
        "tests/fixtures/probe.csv": False,
        "uv.lock": False,
        "models/.gitkeep": False,
    }
    for name, expected in probes.items():
        result = subprocess.run(
            [
                "git",
                "-c",
                "core.excludesFile=" + os.devnull,
                "check-ignore",
                "--no-index",
                "-q",
                "--",
                name,
            ],
            cwd=ROOT,
            check=False,
        )
        if result.returncode not in (0, 1) or (result.returncode == 0) != expected:
            errors.append(
                f"Unexpected ignore rule: {name} (expected ignored={expected})"
            )
    compose = ROOT / "docker-compose.yml"
    if compose.exists():
        # Use the template defaults, independent of private caller overrides.
        env = {
            k: v
            for k, v in os.environ.items()
            if not k.startswith(("COMPOSE_", "CNC_", "NIFI_IMAGE"))
        }
        config = json.loads(
            subprocess.check_output(
                [
                    "docker",
                    "compose",
                    "--env-file",
                    os.devnull,
                    "-f",
                    str(compose),
                    "config",
                    "--format",
                    "json",
                ],
                cwd=ROOT,
                text=True,
                env=env,
                stderr=subprocess.PIPE,
            )
        )
        for service, spec in config["services"].items():
            build = spec.get("build")
            if build:
                context = Path(build["context"])
                dockerfile = context / build.get("dockerfile", "Dockerfile")
                if not context.is_dir() or not dockerfile.is_file():
                    errors.append(f"{service}: missing build context or Dockerfile")
                else:
                    # Docker joins backslash-continued instructions before
                    # parsing; shlex cannot parse a dangling escape per line.
                    for line in dockerfile.read_text().replace("\\\n", "").splitlines():
                        parts = shlex.split(line, comments=True)
                        if not parts or parts[0].upper() not in {"COPY", "ADD"}:
                            continue
                        if any(p.startswith("--from=") for p in parts):
                            continue
                        for name in parts[1:-1]:
                            if name.startswith("--") or "://" in name:
                                continue
                            if not list(context.glob(name)):
                                errors.append(f"{service}: missing build source {name}")
            for volume in spec.get("volumes", []):
                if volume["type"] != "bind":
                    continue
                source = Path(volume["source"])
                try:
                    relative = source.relative_to(ROOT)
                except ValueError:
                    errors.append(f"{service}: default mount outside checkout")
                    continue
                if not source.exists() and relative.parts[0] not in {
                    "outputs",
                    "models",
                }:
                    errors.append(f"{service}: missing bind source {relative}")
    return errors


if __name__ == "__main__":
    try:
        failures = check()
    except (OSError, subprocess.CalledProcessError, ValueError) as exc:
        print(f"Layout check could not complete: {exc}", file=sys.stderr)
        sys.exit(2)
    for failure in failures:
        print(failure, file=sys.stderr)
    if failures:
        sys.exit(1)
    print("Repository layout OK: tracked files, ignore rules and Compose paths")
