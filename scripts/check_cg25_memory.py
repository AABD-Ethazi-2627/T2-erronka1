"""Read-only verification of CG25 documentation; no services or network access."""
import hashlib
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]


def main():
    manifest = json.loads((ROOT / 'docs/memoria/manifest.json').read_text())
    source = json.loads((ROOT / 'docs/rubrica/fuente.json').read_text())
    expected = {f"Zereginak!{d['advanced_cell']}" for d in source['descriptors']}
    memory = (ROOT / 'docs/memoria/README.md').read_text()
    cells = re.findall(r'^\| (Zereginak!G\d+) \|', memory, re.M)
    assert len(cells) == 40 and set(cells) == expected, 'Criterion coverage mismatch'
    for name, digest in manifest['files'].items():
        assert hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == digest, name
    links = 0
    for path in (ROOT / 'docs/memoria').glob('*.md'):
        for target in re.findall(r'\]\(([^)]+)\)', path.read_text()):
            assert '://' not in target, 'CG25 references should remain local'
            assert (path.parent / target).resolve().is_file(), target
            links += 1
    print(f'PASS: {len(cells)} criteria, {links} links, {len(manifest["files"])} hashes')
    print('Human review, CI, integration and technical reruns remain pending.')


if __name__ == '__main__':
    main()
