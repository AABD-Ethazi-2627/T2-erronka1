"""Bounded Kafka codec A/B with exact official image consumer and stock bytes.

Never runs NiFi; no shared Maven cache, service or archive changes.
"""
import hashlib
import json
import os
from pathlib import Path
import resource
import shutil
import subprocess
import sys
import tempfile
import zipfile

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import map_candidates as mapping


def run(source, component, output):
    source, component, output = map(Path, (source, component, output))
    output = output.absolute()
    for root in (mapping.ROOT, source.absolute(), component.absolute()):
        if output == root or root in output.parents:
            raise ValueError('proof must use a fresh cache outside source/repository')
    if any(p.is_symlink() for p in (output, *output.parents)):
        raise ValueError('symlink proof path')
    output.mkdir(parents=True, exist_ok=False)
    lock = {r['path']: r['sha256'] for r in mapping.load(HERE / 'source-lock.json')['archives']}
    inputs = {}
    def record(p):
        sha = hashlib.sha256(p.read_bytes()).hexdigest()
        if p.is_relative_to(source) and lock.get(p.relative_to(source).as_posix()) != sha:
            raise ValueError('stock source-lock mismatch')
        inputs[str(p)] = sha
        return p
    for tool in ('java', 'javac'):
        record(Path(shutil.which(tool)).resolve())
    # Verify replacement and control library inputs against reviewed pins.
    pins = {r['file']: r for r in mapping.load(HERE.parent / 'compatible-libraries/pins.json')}
    for family, (old, new, _) in mapping.PAIRS.items():
        for name in (old, new):
            if mapping.writer.digest(component / name) != pins[name]['sha256']:
                raise ValueError('library pin mismatch')
            record(component / name)
    lib = source / 'opt/nifi/nifi-current/lib'
    nar = record(lib / 'nifi-kafka-3-service-nar-2.12.0.nar')
    with zipfile.ZipFile(nar) as z:
        names = [n for n in z.namelist() if n.startswith('META-INF/bundled-dependencies/kafka-clients-') and n.endswith('.jar')]
        if len(names) != 1:
            raise ValueError('ambiguous Kafka consumer')
        consumer = output / Path(names[0]).name
        consumer.write_bytes(z.read(names[0]))
        record(consumer)
    aws = record(lib / 'nifi-aws-nar-2.12.0.nar')
    with zipfile.ZipFile(aws) as z:
        jimfs = output / 'jimfs-1.1.jar'
        jimfs.write_bytes(z.read('META-INF/bundled-dependencies/jimfs-1.1.jar'))
        record(jimfs)
    failureaccess = record(component / 'failureaccess-1.0.3.jar')
    if mapping.writer.digest(failureaccess) != pins[failureaccess.name]['sha256']:
        raise ValueError('failureaccess pin mismatch')
    slf4j = record(lib / 'slf4j-api-2.0.19.jar')
    probe = record(HERE / 'ConsumerProbe.java')
    for name in ('probe_consumers.py', 'map_candidates.py'):
        record(HERE / name)
    env = {k: v for k, v in os.environ.items() if k not in {'CLASSPATH', 'JAVA_TOOL_OPTIONS', '_JAVA_OPTIONS', 'JDK_JAVA_OPTIONS', 'JDK_JAVAC_OPTIONS', 'LD_PRELOAD', 'LD_LIBRARY_PATH'}}
    commands = []
    def limits():
        resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
        resource.setrlimit(resource.RLIMIT_CPU, (25, 25))
        os.sched_setaffinity(0, {min(os.sched_getaffinity(0))})
    def execute(args):
        p = subprocess.run(args, env=env, preexec_fn=limits, timeout=40, capture_output=True, text=True)
        commands.append({'argv': args, 'returncode': p.returncode, 'stdout': p.stdout, 'stderr': p.stderr})
        (output / 'execution.json').write_text(json.dumps({'commands': commands, 'inputs': inputs}, indent=2))
        if p.returncode:
            raise ValueError('probe failure; see execution.json')
    execute(['java', '-Xmx256m', '-XX:MaxMetaspaceSize=96m', '-XX:ActiveProcessorCount=1', '-version'])
    classes = output / 'classes'; classes.mkdir()
    cp = [str(consumer), str(slf4j), str(jimfs), str(failureaccess)]
    oldcp = cp + [str(component / mapping.PAIRS[f][0]) for f in ('guava', 'snappy', 'lz4')]
    execute(['javac', '-J-Xmx256m', '-J-XX:MaxMetaspaceSize=96m', '-d', str(classes), '-cp', os.pathsep.join(oldcp), str(probe)])
    for version in (0, 1):
        native = Path(tempfile.mkdtemp(prefix='native-', dir=output))
        classpath = [str(classes)] + cp + [str(component / mapping.PAIRS[f][version]) for f in ('guava', 'snappy', 'lz4')]
        execute(['java', '-Xmx256m', '-XX:MaxMetaspaceSize=96m', '-XX:ActiveProcessorCount=1', '-Djava.io.tmpdir=' + str(native), '-cp', os.pathsep.join(classpath), 'ConsumerProbe'])
    hadoop_nar = record(lib / 'nifi-iceberg-parquet-writer-nar-2.12.0.nar')
    with zipfile.ZipFile(hadoop_nar) as z:
        hadoop = output / 'hadoop-common-3.5.0.jar'
        hadoop.write_bytes(z.read('META-INF/bundled-dependencies/hadoop-common-3.5.0.jar'))
        record(hadoop)
    hprobe = record(HERE / 'HadoopProbe.java')
    hcp = [str(classes), str(hadoop), str(slf4j)]
    execute(['javac', '-J-Xmx256m', '-J-XX:MaxMetaspaceSize=96m', '-d', str(classes), '-cp', os.pathsep.join(hcp + [str(component / mapping.PAIRS['snappy'][0])]), str(hprobe)])
    for version, label in ((0, 'old'), (1, 'new')):
        native = Path(tempfile.mkdtemp(prefix='hadoop-native-', dir=output))
        execute(['java', '-Xmx256m', '-XX:MaxMetaspaceSize=96m', '-XX:ActiveProcessorCount=1', '-Djava.io.tmpdir=' + str(native), '-cp', os.pathsep.join(hcp + [str(component / mapping.PAIRS['snappy'][version])]), 'HadoopProbe', label])
    for p, sha in inputs.items():
        if mapping.writer.digest(p) != sha:
            raise ValueError('input changed during proof')
    (output / 'summary.json').write_text(json.dumps({'status': 'Kafka-and-Jimfs-normal-roundtrip-only', 'inputs': inputs, 'outputs': {str(p.relative_to(output)): mapping.writer.digest(p) for p in output.rglob('*') if p.is_file()}, 'limits': 'single CPU; heap 256 MiB; metaspace 96 MiB; CPU 25 s; wall 40 s; no core dumps', 'gaps': ['Other actual consumers untested by this probe', 'NiFi classloader and image-native behavior untested']}, indent=2))


if __name__ == '__main__':
    run(*sys.argv[1:])
