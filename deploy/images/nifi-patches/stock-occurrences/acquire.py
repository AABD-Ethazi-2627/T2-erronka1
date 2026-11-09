"""Copy only public archive files from a never-started pinned stock container.

No pull, build, start, configuration/state/log or volume reads. docker export
omits volume contents. Non-library tar members are skipped, never materialized.
"""
import hashlib
import json
import subprocess
import sys
import tarfile
from pathlib import Path

IMAGE = 'apache/nifi:2.12.0@sha256:6f7f2840dbf178c6dd3fa13435b9b358f3be3c6fb7417de467a35a267f4d28ad'


def acquire(dest):
    dest = Path(dest)
    dest.mkdir(exist_ok=False, parents=True)
    commands = []

    def run(args):
        commands.append(args)
        return subprocess.check_output(args, timeout=60)

    inspect = json.loads(run(['docker', 'image', 'inspect', IMAGE]))
    (dest / 'image.json').write_text(json.dumps(inspect, indent=2))
    cid = run(['docker', 'create', '--network', 'none', '--entrypoint', '/bin/false',
               '--memory', '512m', '--cpus', '1', IMAGE]).decode().strip()
    rows = []
    try:
        state = json.loads(run(['docker', 'inspect', cid]))
        if state[0]['State']['Status'] != 'created':
            raise ValueError('owned acquisition container is not stopped/created')
        (dest / 'container.json').write_text(json.dumps(state, indent=2))
        args = ['docker', 'export', cid]
        commands.append(args)
        proc = subprocess.Popen(args, stdout=subprocess.PIPE)
        try:
            with tarfile.open(fileobj=proc.stdout, mode='r|') as archive:
                for entry in archive:
                    p = Path(entry.name)
                    if not entry.name.startswith('opt/nifi/') or p.suffix.lower() not in {'.jar', '.nar', '.war', '.zip'}:
                        continue
                    if set(p.parts) & {'conf', 'logs', 'state', 'content_repository', 'database_repository', 'flowfile_repository', 'provenance_repository', 'nar_extensions', 'python_extensions'}:
                        continue
                    if not entry.isfile() or '..' in p.parts or p.is_absolute():
                        raise ValueError('nonregular archive: ' + entry.name)
                    out = dest / 'source' / p
                    out.parent.mkdir(parents=True, exist_ok=True)
                    h = hashlib.sha256()
                    with archive.extractfile(entry) as src, out.open('xb') as dst:
                        while chunk := src.read(1024 * 1024):
                            h.update(chunk)
                            dst.write(chunk)
                    rows.append({'path': p.as_posix(), 'sha256': h.hexdigest(), 'size': entry.size})
            if proc.wait(timeout=60):
                raise ValueError('export failed')
        finally:
            if proc.poll() is None:
                proc.kill()
                proc.wait()
        final = json.loads(run(['docker', 'inspect', cid]))
        if final[0]['State']['Status'] != 'created':
            raise ValueError('owned acquisition container changed state')
    finally:
        run(['docker', 'rm', '-v', cid])
        (dest / 'acquisition.json').write_text(json.dumps({'commands': commands, 'image': IMAGE, 'archives': sorted(rows, key=lambda r: r['path']), 'scope': 'public archives only; volume contents excluded; never started'}, indent=2))


if __name__ == '__main__':
    acquire(sys.argv[1])
