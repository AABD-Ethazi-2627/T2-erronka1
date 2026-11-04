"""Exercise the Filebeat build resource guard without compiling or networking."""

import os
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
STAGE = (ROOT / "deploy/images/filebeat.Dockerfile").read_text()


def run_stage(tmp_path, jobs):
    # Only the source directory is redirected. Shell validation, exports and Go
    # arguments are taken from the Dockerfile, with harmless tar/Go executables.
    script = STAGE.split('RUN case "$GO_BUILD_JOBS"', 1)[1].split("\nFROM ", 1)[0]
    script = 'case "$GO_BUILD_JOBS"' + script.replace("\\\n", "")
    script = script.replace("/src", str(tmp_path / "src"))
    capture = tmp_path / "commands.txt"
    for name, body in {
        "tar": "printf 'tar\\n' >> \"$FILEBEAT_CAPTURE_PATH\"\n",
        "go": (
            "printf '%s|%s|%s\\n' \"$GOMAXPROCS\" "
            '"${CGO_ENABLED-unset}" "$*" >> "$FILEBEAT_CAPTURE_PATH"\n'
        ),
    }.items():
        executable = tmp_path / name
        executable.write_text("#!/bin/sh\n" + body)
        executable.chmod(0o755)
    env = {
        **os.environ,
        "PATH": str(tmp_path) + os.pathsep + os.environ["PATH"],
        "GO_BUILD_JOBS": jobs,
        "FILEBEAT_CAPTURE_PATH": str(capture),
    }
    env.pop("GOMAXPROCS", None)
    env.pop("CGO_ENABLED", None)
    result = subprocess.run(
        ["/bin/sh", "-c", script],
        check=False,
        env=env,
        capture_output=True,
        text=True,
        timeout=5,
    )
    return result, capture.read_text().splitlines() if capture.exists() else []


@pytest.mark.parametrize("jobs", ["1", "2", "16"])
def test_go_commands_receive_matching_limits(tmp_path, jobs):
    result, commands = run_stage(tmp_path, jobs)
    assert result.returncode == 0, result.stderr
    assert commands == [
        "tar",
        f"{jobs}|unset|get github.com/google/cel-go@v0.29.0 golang.org/x/net@v0.62.0",
        f"{jobs}|0|build -p {jobs} -trimpath -o /tmp/filebeat ./filebeat",
    ]
    assert "ARG GO_BUILD_JOBS=2\n" in STAGE


@pytest.mark.parametrize("jobs", ["", "0", "00", "01", "-1", "1.5", " 1", "1 ", "auto"])
def test_invalid_limits_fail_before_source_extraction_or_go(tmp_path, jobs):
    result, commands = run_stage(tmp_path, jobs)
    assert result.returncode == 2
    assert "must be a positive decimal integer" in result.stderr
    assert commands == []
    assert not (tmp_path / "src").exists()
