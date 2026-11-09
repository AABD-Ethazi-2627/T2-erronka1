"""Finite, serialized Node24 component tests. Pass a nonexistent output directory."""
import hashlib
import json
import os
from pathlib import Path
import resource
import subprocess
import sys
import uuid

BASE = 'sha256:46b0a3adf85186f9153fbd322e55ea8f70bc4039dcd55d58826fc1caa372dee5'
IMAGE = 'sha256:34a89b0e71b3339c51e5144d363a782a4d6b78cf96b712719da429be38fd5ddd'
LOCK = '/home/tears/.cache/cnc-integration-audit-20261103/candidate-heavy.lock'
SCRIPTS = Path(__file__).resolve().parent


def main():
    output = Path(sys.argv[1]).resolve()
    output.mkdir(exist_ok=False)
    commands = []
    inputs = [p for p in SCRIPTS.glob('*del*') if p.is_file()] + [SCRIPTS.parent / 'kibana.Dockerfile',
        SCRIPTS / 'glob-migration/package-lock.json', SCRIPTS / 'glob-migration/package.json']
    def source_hashes():
        return {str(p.relative_to(SCRIPTS.parent)): hashlib.sha256(p.read_bytes()).hexdigest() for p in inputs}
    before = source_hashes()
    (output / 'sources-before.json').write_text(json.dumps(before, indent=2) + '\n')

    def run(command, stem, timeout=140, limits=None):
        command = ['flock', '-E', '75', '-w', '30', LOCK, *command]
        commands.append(command)
        (output / 'commands.json').write_text(json.dumps(commands, indent=2) + '\n')
        with (output / f'{stem}.json').open('wb') as stdout, (output / f'{stem}.stderr').open('wb') as stderr:
            completed = subprocess.run(command, stdout=stdout, stderr=stderr, timeout=timeout,
                env={'PATH': '/usr/bin:/bin', 'HOME': '/home/tears'}, preexec_fn=limits)
        (output / f'{stem}.exit').write_text(str(completed.returncode) + '\n')
        assert completed.returncode == 0, (stem, completed.returncode, (output / f'{stem}.stderr').read_text())

    def container(image, stem, args, preload=False):
        name = 'cnc-del-' + uuid.uuid4().hex[:12]
        command = ['docker', 'run', '--name', name, '--rm', '--pull', 'never', '--network', 'none',
            '--read-only', '--cpus', '1', '--memory', '384m', '--memory-swap', '384m',
            '--pids-limit', '64', '--ulimit', 'core=0', '--cap-drop', 'ALL',
            '--security-opt', 'no-new-privileges', '--tmpfs', '/tmp:rw,size=64m',
            '--mount', f'type=bind,src={SCRIPTS},dst=/scripts,readonly',
            '--mount', f'type=bind,src={output},dst=/probe,readonly']
        if preload:
            command += ['--env', 'LD_PRELOAD=/probe/del-faults.so']
        command += ['--entrypoint', '/usr/share/kibana/node/default/bin/node', image,
                    '--max-old-space-size=256', *args]
        try:
            run(command, stem)
        finally:
            result = subprocess.run(['docker', 'rm', '-f', name], capture_output=True)
            (output / f'{stem}.cleanup.json').write_text(json.dumps({'returncode': result.returncode,
                'stdout': result.stdout.decode(), 'stderr': result.stderr.decode()}, indent=2) + '\n')

    def compiler_limits():
        resource.setrlimit(resource.RLIMIT_AS, (256 * 1024**2, 256 * 1024**2))
        resource.setrlimit(resource.RLIMIT_CORE, (0, 0))

    run(['taskset', '-c', str(min(os.sched_getaffinity(0))), 'gcc', '-shared', '-fPIC', '-O0',
         '-Wall', '-Wextra', '-Werror', str(SCRIPTS / 'del-fault-injection.c'), '-ldl', '-pthread',
         '-o', str(output / 'del-faults.so')], 'compile', timeout=60, limits=compiler_limits)
    container(BASE, 'prepare', ['-e', "const fs=require('fs');const r=require('/scripts/prepare-del-migration.cjs').prepare('/usr/share/kibana','/tmp/del-patched');const files=Object.fromEntries(fs.readdirSync('/tmp/del-patched').map(n=>[n,fs.readFileSync('/tmp/del-patched/'+n,'base64')]));const legacy=Object.fromEntries(Object.keys(require('/scripts/del-base-inventory.json').legacy).map(n=>[n,fs.readFileSync('/usr/share/kibana/node_modules/del/'+n,'base64')]));console.log(JSON.stringify({result:r,files,legacy,index:fs.readFileSync('/tmp/del-patched.modules.yaml','base64')}));"])
    import base64
    prepared = json.loads((output / 'prepare.json').read_bytes())
    (output / 'del').mkdir()
    for name, data in prepared['files'].items():
        assert '/' not in name
        (output / 'del' / name).write_bytes(base64.b64decode(data))
    (output / 'del.modules.yaml').write_bytes(base64.b64decode(prepared['index']))
    (output / 'legacy').mkdir()
    for name, data in prepared['legacy'].items():
        assert '..' not in Path(name).parts and not Path(name).is_absolute()
        file = output / 'legacy' / name
        file.parent.mkdir(exist_ok=True, parents=True)
        file.write_bytes(base64.b64decode(data))
    container(IMAGE, 'tests', ['/scripts/test-del-migration.cjs', '/probe/del'], preload=True)
    container(IMAGE, 'guards', ['/scripts/test-del-guards.cjs', '/probe/del', '/probe/legacy'])
    assert before == source_hashes(), 'source changed while testing'
    manifest = {str(p.relative_to(output)): hashlib.sha256(p.read_bytes()).hexdigest()
                for p in output.rglob('*') if p.is_file()}
    manifest['sources'] = {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                           for p in SCRIPTS.glob('*del*') if p.is_file()}
    (output / 'sha256.json').write_text(json.dumps(manifest, indent=2) + '\n')
    report = json.loads((output / 'tests.json').read_bytes())
    print(json.dumps({'output': str(output), 'node': report['node'], 'records': len(report['records'])}))


if __name__ == '__main__':
    main()
