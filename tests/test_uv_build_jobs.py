"""Exercise the actual uv-stage shell guard without compiling or using a network."""

import os
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
STAGE = (ROOT / "deploy/images/uv-stage.Dockerfile").read_text()


def run_stage(tmp_path, jobs):
    # Execute the Dockerfile RUN with harmless executables. Only the patch input
    # path changes; validation, exports, command order and arguments stay intact.
    script = STAGE.split('RUN case "$UV_BUILD_JOBS"', 1)[1].split(
        "\nFROM scratch AS uv", 1
    )[0]
    script = 'case "$UV_BUILD_JOBS"' + script.replace("\\\n", "")
    patch_file = tmp_path / "uv.patch"
    patch_file.write_text("")
    script = script.replace("/tmp/uv-rustls.patch", str(patch_file))
    capture = tmp_path / "commands.txt"
    for name, body in {
        "patch": "printf 'patch\\n' >> \"$CARGO_CAPTURE_PATH\"\n",
        "cargo": (
            "printf '%s|%s|%s|%s\\n' \"$CARGO_BUILD_JOBS\" "
            '"${CARGO_PROFILE_RELEASE_LTO-unset}" '
            '"${CARGO_PROFILE_RELEASE_CODEGEN_UNITS-unset}" "$*" '
            '>> "$CARGO_CAPTURE_PATH"\n'
        ),
    }.items():
        executable = tmp_path / name
        executable.write_text("#!/bin/sh\n" + body)
        executable.chmod(0o755)
    env = {
        **os.environ,
        "PATH": str(tmp_path) + os.pathsep + os.environ["PATH"],
        "UV_BUILD_JOBS": jobs,
        "CARGO_CAPTURE_PATH": str(capture),
    }
    for name in (
        "CARGO_BUILD_JOBS",
        "CARGO_PROFILE_RELEASE_LTO",
        "CARGO_PROFILE_RELEASE_CODEGEN_UNITS",
    ):
        env.pop(name, None)
    result = subprocess.run(
        ["/bin/sh", "-c", script],
        check=False,
        env=env,
        capture_output=True,
        text=True,
        timeout=5,
    )
    return result, capture.read_text().splitlines() if capture.exists() else []


@pytest.mark.parametrize("jobs", ["1", "4", "16"])
def test_both_cargo_invocations_receive_the_requested_limit(tmp_path, jobs):
    result, commands = run_stage(tmp_path, jobs)
    assert result.returncode == 0, result.stderr
    assert commands == [
        "patch",
        f"{jobs}|unset|unset|install --locked --version 0.7.7 cargo-auditable",
        f"{jobs}|false|16|auditable build --locked --release --package uv --bin uv --bin uvx",
    ]
    assert "ARG UV_BUILD_JOBS=4\n" in STAGE


@pytest.mark.parametrize("jobs", ["", "0", "00", "01", "-1", "1.5", " 1", "1 ", "auto"])
def test_invalid_limits_fail_before_any_build_command(tmp_path, jobs):
    result, commands = run_stage(tmp_path, jobs)
    assert result.returncode == 2
    assert "must be a positive decimal integer" in result.stderr
    assert commands == []
