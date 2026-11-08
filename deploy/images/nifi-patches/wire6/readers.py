"""Execute official old/fixed Wire readers from the same pinned NiFi stock image."""
import argparse
import hashlib
import json
import subprocess
import zipfile
from pathlib import Path


def sha(data):
    return hashlib.sha256(data).hexdigest()


def old_control_failed(result):
    valid = all('PASS ' + kind + ' valid-scalar' in result.stdout for kind in ('false', 'true'))
    regression = any('FAIL ' + kind + ' ' + case in result.stdout
                     for kind in ('false', 'true')
                     for case in ('negative-length-skipped-group', 'positive-length-overflow'))
    return result.returncode != 0 and valid and regression


def run(libraries, java_home, output):
    here = Path(__file__).resolve().parent
    lock = json.loads((here.parent / 'stock-occurrences/source-lock.json').read_text())
    pins = {Path(row['path']).name: row['sha256'] for row in lock['archives']}
    output = Path(output)
    if output.exists():
        raise ValueError('reader output must be fresh')
    tools = {name: Path(java_home) / 'bin' / name for name in ('java.exe', 'javac.exe')}
    if not all(p.is_file() for p in tools.values()):
        tools = {name: Path(java_home) / 'bin' / name for name in ('java', 'javac')}
    if not all(p.is_file() for p in tools.values()):
        raise ValueError('JDK java/javac missing')
    selected = {
        'nifi-aws-nar-2.12.0.nar': [('old', 'wire-runtime-jvm-5.2.0.jar')],
        'nifi-protobuf-services-nar-2.12.0.nar': [('fixed', 'wire-runtime-jvm-6.4.7.jar')],
        'nifi-standard-shared-nar-2.12.0.nar': [
            (kind, artifact) for kind in ('old', 'fixed')
            for artifact in ('kotlin-stdlib-2.4.20.jar', 'okio-jvm-3.18.2.jar')],
    }
    for name in selected:
        if sha((Path(libraries) / name).read_bytes()) != pins[name]:
            raise ValueError('stock original NAR fingerprint drift: ' + name)
    output.mkdir(parents=True)
    evidence = {'image': lock['image'], 'input_nars': {}, 'commands': [],
                'probe_sha256': sha((here / 'WireReaderProbe.java').read_bytes()),
                'tool_sha256': {name: sha(path.read_bytes()) for name, path in (
                    list(tools.items()) + [('lib/modules', Path(java_home) / 'lib/modules'),
                                           ('release', Path(java_home) / 'release')])},
                'runtime_approved': False, 'scope': 'standalone real JVM readers; not NiFi classloader or processors'}
    for name, artifacts in selected.items():
        evidence['input_nars'][name] = pins[name]
        with zipfile.ZipFile(Path(libraries) / name) as archive:
            for kind, artifact in artifacts:
                target = output / kind / artifact
                target.parent.mkdir(exist_ok=True)
                target.write_bytes(archive.read('META-INF/bundled-dependencies/' + artifact))
    classes = output / 'classes'
    classes.mkdir()

    def execute(argv, label):
        result = subprocess.run([str(v) for v in argv], capture_output=True, text=True, timeout=40, check=False)
        log = result.stdout + result.stderr
        (output / (label + '.log')).write_text(log)
        evidence['commands'].append({'argv': [str(v) for v in argv], 'exit_code': result.returncode,
                                     'log_sha256': sha(log.encode())})
        return result

    compiled = execute([tools['javac.exe' if 'javac.exe' in tools else 'javac'], '-J-Xmx256m',
                        '-J-XX:ActiveProcessorCount=1', '--release', '17', '-cp', str(output / 'fixed/*'),
                        '-d', classes, here / 'WireReaderProbe.java'], 'compile')
    if compiled.returncode:
        raise ValueError('reader compilation failed; see compile.log')
    separator = ';' if 'java.exe' in tools else ':'
    results = {}
    for kind in ('old', 'fixed'):
        results[kind] = execute([tools['java.exe' if 'java.exe' in tools else 'java'], '-Xmx128m',
                                 '-XX:ActiveProcessorCount=1', '-XX:-CreateCoredumpOnCrash', '-cp',
                                 str(classes) + separator + str(output / kind / '*'), 'WireReaderProbe'], kind)
    evidence['payload_sha256'] = {p.relative_to(output).as_posix(): sha(p.read_bytes())
                                  for p in output.rglob('*') if p.suffix in ('.jar', '.class')}
    evidence['fixed_passed'] = results['fixed'].returncode == 0 and results['fixed'].stdout.count('PASS ') == 6
    evidence['old_control_failed'] = old_control_failed(results['old'])
    (output / 'reader-proof.json').write_text(json.dumps(evidence, indent=2) + '\n')
    if not evidence['fixed_passed'] or not evidence['old_control_failed']:
        raise ValueError('fixed reader or original negative control failed; see proof/logs')
    return evidence


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--libraries', type=Path, required=True)
    parser.add_argument('--java-home', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    proof = run(args.libraries, args.java_home, args.output)
    print(json.dumps({k: proof[k] for k in ('fixed_passed', 'old_control_failed', 'runtime_approved')}))
