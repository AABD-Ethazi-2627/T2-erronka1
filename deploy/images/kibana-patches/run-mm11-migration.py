"""Pinned, finite Node24/npm component migration; no image builds or services.

Pass a nonexistent private output directory. Uses only already-owned images.
"""
import base64
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tarfile
import urllib.request
import uuid

BASE = 'sha256:46b0a3adf85186f9153fbd322e55ea8f70bc4039dcd55d58826fc1caa372dee5'
IMAGE = 'sha256:34a89b0e71b3339c51e5144d363a782a4d6b78cf96b712719da429be38fd5ddd'
LOCK = '/home/tears/.cache/cnc-integration-audit-20261103/candidate-heavy.lock'
SCRIPTS = Path(__file__).resolve().parent
NPM = Path('/home/tears/.local/share/mise/installs/node/26.13.0/lib/node_modules/npm')


def sha(data):
    return hashlib.sha256(data).hexdigest()


def main():
    output = Path(sys.argv[1]).resolve()
    output.mkdir(mode=0o700, exist_ok=False)
    sources = list(SCRIPTS.glob('*mm11*')) + list((SCRIPTS / 'minimatch-migration').glob('*.json'))
    sources += [SCRIPTS.parent / 'kibana.Dockerfile', SCRIPTS / 'test-del-migration.cjs',
                SCRIPTS / 'prepare-del-migration.cjs', SCRIPTS / 'del-output-hashes.json',
                SCRIPTS / 'del-base-inventory.json', SCRIPTS / 'del-inventory.cjs', SCRIPTS / 'install-del-migration.cjs']
    sources = [p for p in sources if p.is_file()]
    def snapshot():
        return {str(p.relative_to(SCRIPTS.parent)): sha(p.read_bytes()) for p in sources}
    before = snapshot()
    (output / 'sources-before.json').write_text(json.dumps(before, indent=2) + '\n')
    lock = json.loads((SCRIPTS / 'minimatch-migration/package-lock.json').read_bytes())
    tar_files = {}
    for key, entry in lock['packages'].items():
        if not key:
            continue
        url = entry['resolved']
        assert url.startswith('https://registry.npmjs.org/')
        with urllib.request.urlopen(url, timeout=20) as response:
            data = response.read(8 * 1024**2 + 1)
        assert len(data) <= 8 * 1024**2
        assert entry['integrity'] == 'sha512-' + base64.b64encode(hashlib.sha512(data).digest()).decode()
        (output / url.rsplit('/', 1)[-1]).write_bytes(data)
        with tarfile.open(fileobj=io.BytesIO(data), mode='r:gz') as archive:
            for member in archive:
                if member.isdir():
                    continue
                assert member.isfile() and member.name.startswith('package/')
                relative = member.name.removeprefix('package/')
                assert '..' not in Path(relative).parts and not Path(relative).is_absolute()
                destination = (Path(key).relative_to('node_modules/minimatch') / relative).as_posix()
                tar_files[destination] = sha(archive.extractfile(member).read())
    assert tar_files == json.loads((SCRIPTS / 'mm11-official-files.json').read_bytes())
    for i, (url, expected) in enumerate(json.loads((SCRIPTS / 'mm11-primary-sources.json').read_bytes()).items()):
        data = urllib.request.urlopen(url, timeout=20).read()
        assert sha(data) == expected
        (output / f'primary-source-{i}.md').write_bytes(data)
    assert (NPM / 'bin/npm-cli.js').is_file(), 'existing npm CLI unavailable; no fallback Node allowed'
    (output / 'npm-tool-files.json').write_text(json.dumps({str(p.relative_to(NPM)): sha(p.read_bytes())
        for p in NPM.rglob('*') if p.is_file()}, indent=2) + '\n')
    commands = []
    def container(image, stem, args, npm=False):
        name = 'cnc-mm11-' + uuid.uuid4().hex[:12]
        command = ['flock', '-E', '75', '-w', '30', LOCK, 'docker', 'run', '--name', name,
            '--rm', '--pull', 'never', '--network', 'none', '--read-only', '--cpus', '1',
            '--memory', '384m', '--memory-swap', '384m', '--pids-limit', '64', '--ulimit', 'core=0',
            '--cap-drop', 'ALL', '--security-opt', 'no-new-privileges', '--tmpfs', '/tmp:rw,size=64m',
            '--mount', f'type=bind,src={SCRIPTS},dst=/scripts,readonly',
            '--mount', f'type=bind,src={output},dst=/probe,readonly']
        if npm:
            command += ['--mount', f'type=bind,src={NPM},dst=/npm,readonly',
                '--mount', f'type=bind,src={SCRIPTS / "minimatch-migration"},dst=/lock,readonly']
        command += ['--entrypoint', '/usr/share/kibana/node/default/bin/node', image,
                    '--max-old-space-size=256', *args]
        commands.append(command)
        (output / 'commands.json').write_text(json.dumps(commands, indent=2) + '\n')
        try:
            with (output / f'{stem}.json').open('wb') as stdout, (output / f'{stem}.stderr').open('wb') as stderr:
                result = subprocess.run(command, stdout=stdout, stderr=stderr, timeout=140,
                    env={'PATH': '/usr/bin:/bin', 'HOME': '/home/tears'})
            (output / f'{stem}.exit').write_text(str(result.returncode) + '\n')
            assert result.returncode == 0, (stem, result.returncode, (output / f'{stem}.stderr').read_text())
        finally:
            result = subprocess.run(['docker', 'rm', '-f', name], capture_output=True)
            (output / f'{stem}.cleanup.json').write_text(json.dumps({'returncode': result.returncode,
                'stdout': result.stdout.decode(), 'stderr': result.stderr.decode()}, indent=2) + '\n')

    def decode(directory, entries):
        directory.mkdir(mode=0o700, exist_ok=False)
        for name, data in entries.items():
            assert '..' not in Path(name).parts and not Path(name).is_absolute()
            target = directory / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(base64.b64decode(data))

    container(IMAGE, 'npm-ci', ['/scripts/npm-mm11-closure.cjs'], npm=True)
    closure = json.loads((output / 'npm-ci.json').read_bytes())
    assert {p: sha(base64.b64decode(b)) for p, b in closure['files'].items()} == tar_files
    decode(output / 'official', closure['files'])
    container(BASE, 'prepare', ['/scripts/prepare-mm11-component.cjs'])
    prepared = json.loads((output / 'prepare.json').read_bytes())
    assert prepared['proof']['files'] == json.loads((SCRIPTS / 'mm11-output-files.json').read_bytes())
    decode(output / 'prepared', prepared['files'])
    decode(output / 'del', prepared['del'])
    (output / 'del.modules.yaml').write_bytes(base64.b64decode(prepared['delIndex']))
    (output / 'capture.json').write_text(json.dumps(prepared['capture']))
    container(IMAGE, 'consumers', ['/scripts/test-mm11-migration.cjs'])
    assert before == snapshot(), 'tested sources changed during execution'
    manifest = {str(p.relative_to(output)): sha(p.read_bytes()) for p in output.rglob('*') if p.is_file()}
    (output / 'sha256.json').write_text(json.dumps(manifest, indent=2) + '\n')
    print(json.dumps({'output': str(output), 'officialFiles': len(tar_files),
        'status': 'candidate-semantic-migration-component-tested'}))


if __name__ == '__main__':
    main()
