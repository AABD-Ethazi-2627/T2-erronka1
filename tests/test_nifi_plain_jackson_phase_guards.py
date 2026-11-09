"""Protect failed experiment evidence before Docker can start, including under -O."""
import subprocess
import sys
from pathlib import Path

import pytest

PHASE = Path(__file__).resolve().parents[1] / 'deploy/images/nifi-patches/plain-jackson-qualification/run_phase.py'


@pytest.mark.parametrize('suffix', ['.json', '.stdout', '.stderr', '-execution.json'])
@pytest.mark.parametrize('optimized', [False, True])
def test_existing_phase_evidence_is_preserved(tmp_path, suffix, optimized):
    existing = tmp_path / ('runtime-existing' + suffix)
    existing.write_bytes(b'previous failed experiment: preserve these bytes')
    command = [sys.executable, *(['-O'] if optimized else []), str(PHASE),
               'runtime-existing', '--proof-root', str(tmp_path)]
    result = subprocess.run(command, capture_output=True, text=True, check=False, timeout=5)
    assert result.returncode != 0
    assert 'phase evidence already exists' in result.stderr
    assert existing.read_bytes() == b'previous failed experiment: preserve these bytes'
    assert set(tmp_path.iterdir()) == {existing}


def test_phase_label_cannot_escape_proof_directory(tmp_path):
    result = subprocess.run([sys.executable, str(PHASE), '../escape', '--proof-root', str(tmp_path)],
                            capture_output=True, text=True, check=False, timeout=5)
    assert result.returncode != 0
    assert 'invalid phase label' in result.stderr
    assert not list(tmp_path.iterdir())
