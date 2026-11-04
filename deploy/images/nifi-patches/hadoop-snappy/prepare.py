"""Standalone local source correction. No Maven, image, overlay or approval action."""
import argparse
import copy
import hashlib
import io
import json
import os
import re
import resource
import subprocess
import tempfile
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
CLASS = 'org/apache/hadoop/io/compress/snappy/SnappyCompressor.class'
SOURCE = CLASS.removesuffix('.class') + '.java'
PROVENANCE = 'META-INF/cnc-guard/hadoop-snappy-local-patch.json'
HADOOP = 'dad07af66b59454e71b046a2fce0c0fddb9c522eadd146075e6add82aad86ce6'
SNAPPY = '35228628442e4b9797681c7cbd3b26594f6da3379159dbd0cb07094ed3aece0d'


def sha(b):
    return hashlib.sha256(b).hexdigest()


def regular(p):
    p = Path(p).absolute()
    if any(x.is_symlink() for x in (p, *p.parents)) or not p.is_file():
        raise ValueError('regular non-symlink input required')
    return p.read_bytes()


def pinned(p, expected):
    data = regular(p)
    if sha(data) != expected:
        raise ValueError('input hash mismatch: ' + str(p))
    return data


def signed(z):
    for n in z.namelist():
        u = n.upper()
        if u.startswith('META-INF/') and '/' not in u[9:] and (u.endswith(('.SF', '.RSA', '.DSA', '.EC')) or u[9:].startswith('SIG-')):
            return True
        if u == 'META-INF/MANIFEST.MF' and re.search(rb'(?im)^[^\r\n:]*-Digest(?:-[^\r\n:]*)?:', z.read(n)):
            return True
    return False


def checked(z):
    names = z.namelist()
    if len(set(names)) != len(names):
        raise ValueError('duplicate ZIP entry')
    for n in names:
        if n.startswith('/') or '\\' in n or '..' in n.split('/'):
            raise ValueError('unsafe ZIP entry')
    if signed(z):
        raise ValueError('signed archive or ancestor')


def patch_source(text, mode='fixed'):
    a = 'compressedDirectBuf = ByteBuffer.allocateDirect(directBufferSize);\n    compressedDirectBuf.position(directBufferSize);'
    b = 'compressedDirectBuf = ByteBuffer.allocateDirect(\n        Snappy.maxCompressedLength(directBufferSize));\n    compressedDirectBuf.limit(0);'
    c = '      int size = Snappy.compress((ByteBuffer) uncompressedDirectBuf,'
    d = '      compressedDirectBuf.clear(); // full writable worst-case output capacity\n' + c
    if text.count(a) != 1 or text.count(c) != 1:
        raise ValueError('unexpected source preimage')
    if mode in ('fixed', 'capacity-only'):
        text = text.replace(a, b)
    if mode in ('fixed', 'limit-only'):
        text = text.replace(c, d)
    return text


def rebuild(original, replacement, provenance):
    with zipfile.ZipFile(io.BytesIO(original)) as z:
        checked(z)
        if PROVENANCE in z.namelist() or CLASS not in z.namelist():
            raise ValueError('wrong or already patched JAR')
        out = io.BytesIO()
        with zipfile.ZipFile(out, 'w') as w:
            w.comment = z.comment
            infos = z.infolist()
            for index, original_info in enumerate(infos):
                info = copy.copy(original_info)
                if info.filename == CLASS:
                    # Retain the original data-descriptor protocol for changed content.
                    seekable = w._seekable
                    w._seekable = not bool(info.flag_bits & 8)
                    w.writestr(info, replacement)
                    w._seekable = seekable
                else:
                    # Preserve raw local headers, compressed payload and descriptors.
                    # Only the central-directory local-header offset is relocated.
                    end = infos[index + 1].header_offset if index + 1 < len(infos) else z.start_dir
                    raw = original[info.header_offset:end]
                    info.header_offset = w.fp.tell()
                    w.fp.write(raw)
                    w.filelist.append(info)
                    w.NameToInfo[info.filename] = info
                    w.start_dir = w.fp.tell()
                    w._didModify = True
            info = zipfile.ZipInfo(PROVENANCE, (2026, 11, 4, 0, 0, 0))
            info.external_attr = 0o100644 << 16
            w.writestr(info, json.dumps(provenance, sort_keys=True, indent=2).encode())
    return out.getvalue()


def publish(path, data):
    # Exclusive creation: failed/repeated publication never overwrites an artifact.
    with Path(path).open('xb') as f:
        f.write(data)


def external_fresh(output, forbidden):
    output = Path(output).absolute()
    if any(x.is_symlink() for x in (output, *output.parents)):
        raise ValueError('symlink output')
    for root in forbidden:
        root = Path(root).resolve()
        if output == root or root in output.parents:
            raise ValueError('output must be outside repository/input/.m2')
    output.mkdir(parents=True, exist_ok=False)
    return output


def limits():
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    resource.setrlimit(resource.RLIMIT_CPU, (25, 25))
    os.sched_setaffinity(0, {min(os.sched_getaffinity(0))})


def run(source, component, acquired, output):
    source, component, acquired = (Path(p).resolve() for p in (source, component, acquired))
    output = external_fresh(output, (ROOT, source, component, acquired, Path.home() / '.m2'))
    inputs = {}
    def record(p, expected=None):
        b = pinned(p, expected) if expected else regular(p)
        inputs[str(p)] = sha(b)
        return b
    pins = json.loads(regular(HERE / 'pins.json'))
    for p in HERE.iterdir():
        if p.is_file():
            record(p)
    for row in pins:
        record(acquired / row['file'], row['sha256'])
    lock_path = HERE.parent / 'stock-occurrences/source-lock.json'
    lock = json.loads(record(lock_path))['archives']
    if len(lock) != 215:
        raise ValueError('wrong acquisition scope')
    actual = {p.relative_to(source).as_posix() for p in source.rglob('*') if p.is_file()}
    if actual != {r['path'] for r in lock}:
        raise ValueError('incomplete stock source set')
    occurrences = []
    def walk(data, chain, hashes, ancestors_signed=False, depth=0):
        if depth > 8:
            raise ValueError('archive depth')
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            if len(set(z.namelist())) != len(z.namelist()):
                raise ValueError('duplicate archive entries')
            is_signed = ancestors_signed or signed(z)
            for info in z.infolist():
                n = info.filename
                if n.endswith('/SnappyCompressor.class') or n == 'SnappyCompressor.class':
                    occurrences.append({'chain': chain, 'chain_sha256': hashes, 'class': n, 'class_sha256': sha(z.read(n)), 'signed_ancestor': is_signed})
                if n.lower().endswith(('.jar', '.nar', '.zip')) and not info.is_dir():
                    if info.file_size > 256 * 1024 * 1024:
                        raise ValueError('archive size')
                    b = z.read(info)
                    walk(b, chain + [n], hashes + [sha(b)], is_signed, depth + 1)
    for row in lock:
        b = record(source / row['path'], row['sha256'])
        walk(b, [row['path']], [sha(b)])
    (output / 'occurrences.json').write_text(json.dumps(occurrences, indent=2))
    if not occurrences or any(r['signed_ancestor'] for r in occurrences):
        raise ValueError('signed consumer ancestor')
    # Other actual consumer variants remain mapped and explicitly unpatched.
    if not any(r['class'] == CLASS and r['chain_sha256'][-1] == HADOOP for r in occurrences):
        raise ValueError('missing exact target consumer')
    # Exact pinned original NAR extraction; downloaded JAR is only an equality control.
    nar = source / 'opt/nifi/nifi-current/lib/nifi-iceberg-parquet-writer-nar-2.12.0.nar'
    with zipfile.ZipFile(nar) as z:
        checked(z)
        original = z.read('META-INF/bundled-dependencies/hadoop-common-3.5.0.jar')
    if sha(original) != HADOOP:
        raise ValueError('wrong Hadoop preimage')
    publish(output / 'original.jar', original)
    snappy = component / 'snappy-java-1.1.10.9.jar'
    record(snappy, SNAPPY)
    record(HERE.parent / 'stock-occurrences/HadoopProbe.java')
    library_pins = json.loads(record(HERE.parent / 'compatible-libraries/pins.json'))
    old = component / 'snappy-java-1.1.10.8.jar'
    record(old, next(x['sha256'] for x in library_pins if x['file'] == old.name))
    slf = source / 'opt/nifi/nifi-current/lib/slf4j-api-2.0.19.jar'
    java_home = Path('/usr/lib/jvm/java-21-openjdk')
    for n in ('bin/java', 'bin/javac', 'bin/javap', 'release', 'lib/modules', 'lib/server/libjvm.so'):
        record(java_home / n)
    env = {'PATH':str(java_home / 'bin') + ':/usr/bin:/bin', 'HOME':str(output), 'LANG':'C.UTF-8', 'LC_ALL':'C.UTF-8', 'TMPDIR':str(output)}
    commands = []
    def execute(tool, args):
        tmp = tempfile.mkdtemp(prefix='tool-tmp-', dir=output)
        args = [('-D' if tool == 'java' else '-J-D') + 'java.io.tmpdir=' + tmp] + args
        if tool == 'java' and '-Xmx256m' not in args:
            args = ['-Xmx256m', '-XX:MaxMetaspaceSize=96m', '-XX:ActiveProcessorCount=1'] + args
        if tool == 'javap':
            args = ['-J-Xmx256m', '-J-XX:MaxMetaspaceSize=96m', '-J-XX:ActiveProcessorCount=1'] + args
        p = subprocess.run([str(java_home / 'bin' / tool)] + args, env=env, preexec_fn=limits, timeout=40, capture_output=True, text=True, check=False)
        commands.append({'argv':p.args,'rc':p.returncode,'stdout':p.stdout,'stderr':p.stderr})
        (output / 'execution.json').write_text(json.dumps(commands, indent=2))
        if p.returncode:
            raise ValueError('command failed; see execution.json')
        return p.stdout
    execute('java', ['-version'])
    common = ['-Xmx256m','-XX:MaxMetaspaceSize=96m','-XX:ActiveProcessorCount=1']
    cp = os.pathsep.join(map(str, (output / 'original.jar', snappy, slf)))
    with zipfile.ZipFile(acquired / 'hadoop-common-3.5.0-sources.jar') as z:
        text = z.read(SOURCE).decode()
    (output / 'source-before.java').write_text(text)
    abi = execute('javap', ['-p','-s','-classpath',str(output / 'original.jar'),CLASS[:-6].replace('/','.')])
    bytecode = execute('javap', ['-c','-p','-verbose','-classpath',str(output / 'original.jar'),CLASS[:-6].replace('/','.')])
    (output / 'original-bytecode.txt').write_text(bytecode)
    original_class = zipfile.ZipFile(io.BytesIO(original)).read(CLASS)
    for mode in ('unmodified','fixed','capacity-only','limit-only'):
        folder = output / mode; folder.mkdir()
        src = folder / 'SnappyCompressor.java'; src.write_text(text if mode == 'unmodified' else patch_source(text, mode))
        execute('javac', ['-J' + x for x in common] + ['--release','17','-g','-proc:none','-implicit:none','-d',str(folder),'-cp',cp,str(src)])
        cls = regular(folder / CLASS)
        if cls[6:8] != original_class[6:8] or cls[6:8] != b'\x00=':
            raise ValueError('class major mismatch')
        if execute('javap', ['-p','-s','-classpath',str(folder),CLASS[:-6].replace('/','.')]) != abi:
            raise ValueError('symbolic ABI drift')
    disassembly = execute('javap', ['-c','-p','-classpath',str(output / 'original.jar'),CLASS[:-6].replace('/','.')])
    rebuilt_disassembly = execute('javap', ['-c','-p','-classpath',str(output / 'unmodified'),CLASS[:-6].replace('/','.')])
    if disassembly != rebuilt_disassembly:
        raise ValueError('official source does not reproduce exact symbolic instruction disassembly')
    prov = {'kind':'CNC Guard local source correction, NOT an upstream release','upstream_version':'3.5.0','input_sha256':HADOOP,'source_jar_sha256':next(x['sha256'] for x in pins if x['file'].endswith('-sources.jar')),'patched_source_sha256':sha(regular(output / 'fixed/SnappyCompressor.java')),'changed_entry':CLASS,'original_class_sha256':sha(original_class),'replacement_class_sha256':sha(regular(output / 'fixed' / CLASS)),'snappy_unchanged_sha256':SNAPPY,'approval':False}
    candidate = rebuild(original, regular(output / 'fixed' / CLASS), prov)
    publish(output / 'hadoop-common-3.5.0-cnc-snappy-buffer-v1.jar', candidate)
    # Recheck every content and preserved ZipInfo attribute (CRC/size/offset are derived).
    attrs = ('date_time','compress_type','comment','extra','create_system','create_version','extract_version','flag_bits','volume','internal_attr','external_attr')
    with zipfile.ZipFile(io.BytesIO(original)) as a, zipfile.ZipFile(io.BytesIO(candidate)) as b:
        if b.namelist() != a.namelist() + [PROVENANCE] or a.comment != b.comment:
            raise ValueError('JAR structure drift')
        for n in a.namelist():
            if n != CLASS and a.read(n) != b.read(n):
                raise ValueError('unrelated entry content drift')
            if any(getattr(a.getinfo(n), k) != getattr(b.getinfo(n), k) for k in attrs):
                raise ValueError('entry attribute drift')
    probes = output / 'probes'; probes.mkdir()
    execute('javac', ['-J' + x for x in common] + ['--release','17','-proc:none','-d',str(probes),'-cp',cp,str(HERE / 'CompatibilityProbe.java'),str(HERE.parent / 'stock-occurrences/HadoopProbe.java')])
    def java(classpath, main, *args):
        native = Path(tempfile.mkdtemp(prefix='native-',dir=output))
        return execute('java', common + ['-Djava.io.tmpdir='+str(native),'-Dorg.xerial.snappy.tempdir='+str(native),'-cp',os.pathsep.join(map(str,[probes]+classpath)),main,*args])
    for lib,label in ((old,'old'),(snappy,'new')):
        java([output/'original.jar',lib,slf], 'HadoopProbe',label)
    for mode in ('capacity-only','limit-only'):
        java([output/mode,output/'original.jar',snappy,slf], 'CompatibilityProbe','reject')
    for lib in (snappy,old):
        java([output/'hadoop-common-3.5.0-cnc-snappy-buffer-v1.jar',lib,slf], 'CompatibilityProbe','pass', 'guard' if lib == snappy else 'control')
    for p,digest in inputs.items():
        if sha(regular(p)) != digest:
            raise ValueError('input drift during proof')
    summary = {'status':'standalone-candidate-only; all nine Snappy occurrences remain blocked','candidate_sha256':sha(candidate),'provenance':prov,'occurrences':occurrences,'inputs_before_after':inputs,'abi':'javap -p -s identical; class major 61; release 17 compiled on pinned Java 21','changed_entries':{CLASS:{'before':sha(original_class),'after':sha(regular(output / 'fixed' / CLASS))},PROVENANCE:{'before':None,'after':sha(zipfile.ZipFile(io.BytesIO(candidate)).read(PROVENANCE))}},'source_equivalence':'unmodified official source javap -c -p exactly matches original instructions/constant references','preserved':'all unrelated entry contents and listed ZipInfo attributes; original Maven/manifest/native/service bytes','limits':'one CPU; heap 256m; metaspace 96m; CPU 25s; wall 40s; no cores','gaps':['independent QA','source-bound overlay mapping','NiFi classloader and native runtime','full dependency closure and pooled SnappyCodec configuration','image builds/scans','SMB/CG32/human acceptance']}
    summary['outputs'] = {p.relative_to(output).as_posix():sha(regular(p)) for p in output.rglob('*') if p.is_file()}
    (output / 'summary.json').write_text(json.dumps(summary, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('source','component','acquired','output'):
        parser.add_argument(name)
    run(**vars(parser.parse_args()))
