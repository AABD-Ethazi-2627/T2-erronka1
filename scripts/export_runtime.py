"""Export the serving closure from uv.lock, or check it without changing files."""

import argparse
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HEADER = (
    "# Generated from uv.lock: python -m scripts.export_runtime\n"
    "# Runtime only; all transitive versions and artifact hashes are locked.\n"
)


def render(root: Path) -> str:
    result = subprocess.run(
        [
            "uv",
            "export",
            "--frozen",
            "--only-group",
            "runtime",
            "--no-emit-project",
            "--no-header",
            "--no-annotate",
        ],
        cwd=root,
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode:
        raise RuntimeError("Runtime export failed: " + result.stderr.strip())
    if not result.stdout.strip():
        raise RuntimeError("Runtime export is empty")
    return HEADER + result.stdout


def check(root: Path, target: Path) -> bool:
    expected = render(root).encode("utf-8")
    return target.is_file() and target.read_bytes() == expected


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    target = ROOT / "scoring/requirements.txt"
    if args.check:
        if not check(ROOT, target):
            parser.exit(
                1, "Runtime export is stale; run python -m scripts.export_runtime\n"
            )
        print("Runtime export matches uv.lock")
    else:
        target.write_bytes(render(ROOT).encode("utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
