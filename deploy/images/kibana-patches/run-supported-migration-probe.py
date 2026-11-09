"""Read-only component diagnostic. No image build, pull, npm scripts, or services.

Usage: python run-supported-migration-probe.py FRESH_OUTPUT_DIRECTORY
Only the fresh output directory and disposable container /tmp are written.
"""
import base64
import hashlib
import io
import json
from pathlib import Path
import subprocess
import sys
import tarfile
import urllib.request
import uuid

IMAGE = 'sha256:34a89b0e71b3339c51e5144d363a782a4d6b78cf96b712719da429be38fd5ddd'
CACHE = Path('/home/tears/.cache/cnc-kibana-image-20261104/migration-preparation')
PREFIX = 'node_modules/glob/node_modules/minimatch'
LOCK = Path('/home/tears/.cache/cnc-integration-audit-20261103/candidate-heavy.lock')
SCRIPT = Path(__file__).with_name('probe-supported-migration.cjs').resolve()


def sha(data):
    return hashlib.sha256(data).hexdigest()


def main():
    output = Path(sys.argv[1]).resolve()
    output.mkdir(exist_ok=False)
    lock_bytes = (CACHE / 'package-lock.json').read_bytes()
    assert lock_bytes == (SCRIPT.parent / 'glob-migration/package-lock.json').read_bytes()
    lock = json.loads(lock_bytes)
    inventory = {}
    # Compare every byte of each tested official package, not just package.json.
    # Nested node_modules belong to independently verified lock entries.
    for key, entry in lock['packages'].items():
        if key != PREFIX and not key.startswith(PREFIX + '/node_modules/'):
            continue
        url = entry['resolved']
        assert url.startswith('https://registry.npmjs.org/') and url.endswith('.tgz')
        with urllib.request.urlopen(url, timeout=20) as response:
            payload = response.read(8 * 1024 * 1024 + 1)
        assert len(payload) <= 8 * 1024 * 1024
        algorithm, expected = entry['integrity'].split('-', 1)
        assert algorithm == 'sha512'
        assert base64.b64encode(hashlib.sha512(payload).digest()).decode() == expected
        artifact = key.replace('/', '_') + '.tgz'
        (output / artifact).write_bytes(payload)
        files = {}
        with tarfile.open(fileobj=io.BytesIO(payload), mode='r:gz') as archive:
            for member in archive.getmembers():
                if member.isdir():
                    continue
                assert member.isfile() and member.name.startswith('package/')
                relative = member.name.removeprefix('package/')
                assert '..' not in Path(relative).parts and not Path(relative).is_absolute()
                actual = CACHE / key / relative
                assert not actual.is_symlink()
                data = archive.extractfile(member).read()
                assert actual.read_bytes() == data, actual
                files[relative] = sha(data)
        installed = {str(p.relative_to(CACHE / key)) for p in (CACHE / key).rglob('*')
                     if p.is_file() and 'node_modules' not in p.relative_to(CACHE / key).parts}
        assert installed == set(files), (key, installed ^ set(files))
        inventory[key] = dict(version=entry['version'], integrity=entry['integrity'],
                              url=url, tarball_sha256=sha(payload), files=files)
    (output / 'verified-packages.json').write_text(json.dumps(inventory, indent=2) + '\n')
    (output / 'probe.cjs').write_bytes(SCRIPT.read_bytes())
    name = 'cnc-supported-probe-' + uuid.uuid4().hex[:12]
    docker = ['docker', 'run', '--name', name, '--rm', '--pull', 'never', '--network', 'none',
              '--read-only', '--cpus', '1', '--memory', '384m', '--memory-swap', '384m',
              '--pids-limit', '64', '--ulimit', 'core=0', '--cap-drop', 'ALL',
              '--security-opt', 'no-new-privileges', '--tmpfs', '/tmp:rw,size=64m',
              '--mount', f'type=bind,src={output / "probe.cjs"},dst=/probe.cjs,readonly',
              '--mount', f'type=bind,src={CACHE / PREFIX},dst=/next,readonly',
              '--entrypoint', '/usr/share/kibana/node/default/bin/node', IMAGE,
              '--max-old-space-size=256', '/probe.cjs']
    command = ['flock', '-w', '30', str(LOCK), *docker]
    (output / 'command.json').write_text(json.dumps(command, indent=2) + '\n')
    inspect = subprocess.run(['docker', 'image', 'inspect', IMAGE], check=True, capture_output=True)
    (output / 'image-inspect.json').write_bytes(inspect.stdout)
    try:
        with (output / 'result.json').open('wb') as stdout, (output / 'stderr.txt').open('wb') as stderr:
            result = subprocess.run(command, stdout=stdout, stderr=stderr, timeout=80,
                                    env={'PATH': '/usr/bin:/bin', 'HOME': '/home/tears'})
        (output / 'exit-code.txt').write_text(str(result.returncode) + '\n')
        assert result.returncode == 0, (output / 'stderr.txt').read_text()
        report = json.loads((output / 'result.json').read_bytes())
        assert report['status'] == 'blocked-direct-minimatch-migration'
    finally:
        # Our uniquely named disposable component container only; no cache pruning.
        cleanup = subprocess.run(['docker', 'rm', '-f', name], capture_output=True)
        (output / 'cleanup.json').write_text(json.dumps(dict(returncode=cleanup.returncode,
            stdout=cleanup.stdout.decode(), stderr=cleanup.stderr.decode()), indent=2) + '\n')
    manifest = {p.name: sha(p.read_bytes()) for p in output.iterdir() if p.is_file()}
    manifest['input-lock-sha256'] = sha(lock_bytes)
    (output / 'sha256.json').write_text(json.dumps(manifest, indent=2) + '\n')
    print(json.dumps(dict(output=str(output), comparisons=report['comparisons'],
                          differences=report['differences'], status=report['status'])))


if __name__ == '__main__':
    main()
