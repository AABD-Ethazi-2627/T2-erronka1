"""The release checksum must reject corrupt downloads before installing a binary."""

import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_corrupt_release_is_rejected_before_install(tmp_path):
    script = tmp_path / "install_trivy_release.sh"
    shutil.copyfile(ROOT / "scripts/install_trivy_release.sh", script)
    # Fixture replaces transport only; the actual installer's digest check runs.
    (tmp_path / "trivy-download-curl.sh").write_text(
        '#!/bin/sh\nwhile [ "$1" != --output ]; do shift; done\nprintf corrupt > "$2"\n'
    )
    destination = tmp_path / "bin"
    result = subprocess.run(
        ["sh", str(script), str(destination)],
        check=False,
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert result.returncode != 0
    assert not (destination / "trivy").exists()
