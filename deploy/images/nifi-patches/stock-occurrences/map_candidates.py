"""Read-only exact occurrence mapping. Produces unapproved candidates only.

Uses the existing bounded archive inventory, never writes or patches archives.
Consumer references are constant-pool/package linkage candidates, not JVM proof.
"""
import argparse
import hashlib
import io
import json
import sys
import zipfile
from collections import Counter
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / 'scripts'))
import patch_nested_jars as writer

PAIRS = {
 'guava': ('guava-33.7.1-jre.jar', 'guava-33.7.2-jre.jar', b'com/google/common/'),
 'lz4': ('lz4-java-1.11.2.jar', 'lz4-java-1.11.4.jar', b'net/jpountz/'),
 'snappy': ('snappy-java-1.1.10.8.jar', 'snappy-java-1.1.10.9.jar', b'org/xerial/snappy/'),
}
HADOOP_HASH = 'dad07af66b59454e71b046a2fce0c0fddb9c522eadd146075e6add82aad86ce6'
FAMILIES = set(PAIRS) | {'hadoop'}


def load(path):
    def pairs(items):
        d = {}
        for k, v in items:
            if k in d:
                raise ValueError('duplicate JSON key')
            d[k] = v
        return d
    return json.loads(writer.regular(path).read_text(), object_pairs_hook=pairs)


@lru_cache(maxsize=1)
def outer_bytes(path):
    return writer.regular(path).read_bytes()


def payload(source, row):
    data = outer_bytes(source / row['outer'])
    if hashlib.sha256(data).hexdigest() != row['chain_sha256'][0]:
        raise ValueError('outer drift')
    for index, name in enumerate(row['members'], 1):
        writer.canonical(name)
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            data = z.read(name)
        if hashlib.sha256(data).hexdigest() != row['chain_sha256'][index]:
            raise ValueError('member drift')
    if hashlib.sha256(data).hexdigest() != row['sha256']:
        raise ValueError('leaf drift')
    return data


def closure(outer, nars):
    result = []
    while outer:
        if outer in result:
            raise ValueError('NAR parent cycle')
        result.append(outer)
        m = nars[outer]['manifest']
        ident = m.get('Nar-Dependency-Id')
        if not ident:
            if any(k.startswith('Nar-Dependency-') for k in m):
                raise ValueError('partial NAR parent')
            break
        key = (m.get('Nar-Dependency-Group'), ident, m.get('Nar-Dependency-Version'))
        matches = [p for p, r in nars.items() if tuple(r['manifest'].get(k) for k in ('Nar-Group', 'Nar-Id', 'Nar-Version')) == key]
        if len(matches) != 1:
            raise ValueError('missing/ambiguous NAR parent: ' + str(key))
        outer = matches[0]
    return result


def prepare(source, inv, component, hadoop_candidate=None):
    source, component = Path(source), Path(component)
    outer_bytes.cache_clear()
    rows = writer.inventory(source)
    if inv is not None and (rows != inv['occurrences'] or writer.inventory_hash(rows) != inv['inventory_sha256']):
        raise ValueError('incomplete or drifted occurrence inventory')
    inv = {'occurrences': rows, 'inventory_sha256': writer.inventory_hash(rows)}
    if not rows or writer.inventory_hash(rows) != inv['inventory_sha256']:
        raise ValueError('invalid inventory identity')
    lock = load(Path(__file__).parent / 'source-lock.json')
    locked = {r['path']: r['sha256'] for r in lock['archives']}
    actual = {r['outer']: r['sha256'] for r in rows if not r['members']}
    if actual != locked:
        raise ValueError('source lock mismatch or incomplete acquisition')
    # Verify complete source set and root bytes even when supplied inventory is cached.
    roots = {r['outer']: r for r in rows if not r['members']}
    if {p.relative_to(source).as_posix() for p in writer.files(source)} != set(roots):
        raise ValueError('incomplete source inventory')
    for outer, r in roots.items():
        if writer.digest(source / outer) != r['sha256']:
            raise ValueError('source hash drift')
    pins = {r['file']: r for r in load(Path(__file__).parent.parent / 'compatible-libraries/pins.json')}
    selected = {}
    resources = {}
    replacement_paths = {}
    replacement_hashes = {}
    for family, (old, new, prefix) in PAIRS.items():
        for name in (old, new):
            if writer.digest(component / name) != pins[name]['sha256']:
                raise ValueError('component hash drift')
        selected[pins[old]['sha256']] = (family, new)
        replacement_paths[family] = str((component/new).absolute())
        replacement_hashes[family] = pins[new]['sha256']
        with zipfile.ZipFile(component / old) as a, zipfile.ZipFile(component / new) as b:
            aa = {n: hashlib.sha256(a.read(n)).hexdigest() for n in a.namelist() if not n.endswith('/') and not n.endswith('.class')}
            bb = {n: hashlib.sha256(b.read(n)).hexdigest() for n in b.namelist() if not n.endswith('/') and not n.endswith('.class')}
            removed = sorted(set(aa) - set(bb))
            if removed:
                raise ValueError('resource removed: ' + str(removed))
            resources[family] = {'old': aa, 'new': bb, 'removed': removed, 'changed': sorted(n for n in aa if aa[n] != bb[n])}
    library_hashes = set(selected)
    if hadoop_candidate is not None:
        replacement = writer.regular(hadoop_candidate)
        expected = writer.ATOMIC_HADOOP_SNAPPY[HADOOP_HASH]['replacement_sha256']
        if writer.digest(replacement) != expected:
            raise ValueError('unreviewed Hadoop candidate hash')
        original = [r for r in rows if r['sha256'] == HADOOP_HASH]
        if len(original) != writer.ATOMIC_HADOOP_SNAPPY[HADOOP_HASH]['count']:
            raise ValueError('missing/ambiguous exact Hadoop consumer')
        selected[HADOOP_HASH] = ('hadoop',str(replacement))
        replacement_paths['hadoop'] = str(replacement)
        replacement_hashes['hadoop'] = expected
    if set(selected) & writer.BLOCKED_INPUTS:
        raise ValueError('blocked library')
    nars = {p: r for p, r in roots.items() if r['manifest'].get('Nar-Id')}
    closures = {p: closure(p, nars) for p in nars}
    relevant = [r for r in rows if r['sha256'] in selected]
    if {r['sha256'] for r in relevant} != set(selected):
        raise ValueError('missing selected library')
    # Scan every archive with direct classes. No image-wide synthetic Java classpath.
    references = []
    for r in rows:
        if not r['class_packages'] or r['sha256'] in library_hashes:
            continue
        data = payload(source, r)
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            found = {}
            for name in z.namelist():
                if not name.endswith('.class'):
                    continue
                data = z.read(name)
                hits = [f for f, (_, _, prefix) in PAIRS.items() if prefix in data]
                for f in hits:
                    found.setdefault(f, []).append({'class': name, 'sha256': hashlib.sha256(data).hexdigest()})
            if found:
                references.append({k: r[k] for k in ('outer', 'members', 'chain_sha256', 'sha256')} | {'references': found})
    hadoop_consumers = [x for x in references if 'snappy' in x['references']
                        and any('hadoop-common-' in n for n in [x['outer'],*x['members']])]
    snappy_hadoop = bool(hadoop_consumers)
    if hadoop_candidate is not None and any(x['sha256'] != HADOOP_HASH for x in hadoop_consumers):
        raise ValueError('unknown Hadoop/Snappy consumer requires separate review')
    result = []
    for r in relevant:
        if r['signed'] or r['sha256'] in writer.BLOCKED_INPUTS:
            raise ValueError('signed/blocked selected occurrence')
        family, new = selected[r['sha256']]
        scope = closures.get(r['outer'], [])
        # Shared NAR consumers can be in descendants, not only sibling JARs.
        consumers = [x for x in references if family in x['references'] and (
            (scope and r['outer'] in closures.get(x['outer'], [])) or
            (not scope and Path(x['outer']).parent == Path(r['outer']).parent))]
        visible = [x for x in rows if (x['outer'] in scope and x['members']) or
                   (not scope and not x['members'] and Path(x['outer']).parent == Path(r['outer']).parent)]
        guava_support = [x for x in visible if x['sha256'] == pins['failureaccess-1.0.3.jar']['sha256']]
        if family == 'guava' and not guava_support:
            raise ValueError('missing visible pinned failureaccess')
        result.append({k: r[k] for k in ('outer', 'members', 'chain_sha256', 'sha256')} | {
            'family': family, 'status': 'blocked-consumer-incompatibility' if family == 'snappy' and snappy_hadoop and hadoop_candidate is None else 'candidate-pending-parent-QA',
            'replacement': replacement_paths[family], 'replacement_sha256': replacement_hashes[family],
            'expected_occurrences': sum(x['sha256'] == r['sha256'] for x in rows),
            'nar_closure': [{'outer': p, 'sha256': nars[p]['sha256'], 'manifest': nars[p]['manifest']} for p in scope],
            'guava_failureaccess_verified': bool(guava_support) if family == 'guava' else None,
            'visible_dependencies': [{k: x[k] for k in ('outer', 'members', 'sha256', 'maven')} for x in visible],
            'consumers': consumers,
            'eligibility': 'exact-stock-bytes-only; consumer/runtime review pending',
            'blockers': (['Hadoop SnappyCompressor rejects normal input on 1.1.10.9; complete-hash replacement cannot omit this occurrence'] if family == 'snappy' and snappy_hadoop and hadoop_candidate is None else []) + ['NiFi classloader dispatch and full consumer behavior unverified', 'parent QA/review approval absent'],
        })
    if hadoop_candidate is not None:
        writer.validate_atomic_targets(rows,result)
    return {'schema': 1, 'inventory_sha256': inv['inventory_sha256'], 'dry_run': True,
            'executable': False, 'targets': result, 'resources': resources,
            'limitations': ['Manifest closure is not classloader execution', 'Constant-pool package references include unused paths and omit reflection', 'Global framework visibility and native extraction require runtime acceptance'],
            'counts': dict(Counter(r['family'] for r in result))}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('source', type=Path)
    p.add_argument('component', type=Path)
    p.add_argument('--hadoop-candidate', type=Path,
                   help='exact pinned consumer; enables only the complete atomic Hadoop/Snappy candidate group')
    # Recompute the full bounded inventory. No caller-provided completeness claim.
    a = p.parse_args()
    print(json.dumps(prepare(a.source, None, a.component, a.hadoop_candidate), indent=2, sort_keys=True))


if __name__ == '__main__':
    main()
