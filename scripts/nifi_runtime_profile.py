"""Materialize a frozen whole-NAR capability profile; never authorize runtime.

Only copies fresh preparation outputs. No Docker, service, network, archive edits,
active configuration qualification, security exceptions or installation path.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import re
import stat
import zipfile
from pathlib import Path, PurePosixPath

PROFILE_PATH = Path(__file__).resolve().parents[1] / 'deploy/images/nifi-patches/cnc-runtime/profile.json'
PROFILE_SHA256 = 'b1c5414e562737063e62460aad469581e7191bc6fcd0a8070fc43a36408fee81'
SOURCE_IMAGE_ID = 'sha256:03f3e9a19dbce166304ec63a685c44f2da07239e5659d843c798c7f32f7012d5'
SCOPES = ('opt/nifi', 'usr/local/bin/uv', 'usr/local/bin/uvx')
EXCLUDED = frozenset({
    'nifi-amqp-nar', 'nifi-aws-kinesis-nar', 'nifi-aws-nar',
    'nifi-aws-service-api-nar', 'nifi-gcp-nar', 'nifi-gcp-services-api-nar',
    'nifi-iceberg-aws-nar', 'nifi-iceberg-azure-nar', 'nifi-iceberg-gcs-nar',
    'nifi-iceberg-parquet-writer-nar', 'nifi-iceberg-processors-nar',
    'nifi-iceberg-rest-catalog-nar', 'nifi-iceberg-service-api-nar',
    'nifi-iceberg-shared-nar', 'nifi-kafka-service-aws-nar',
    'nifi-kafka-to-s3-nar',
})
FLOW_CLOSURE = frozenset({
    'nifi-elasticsearch-client-service-api-nar',
    'nifi-elasticsearch-client-service-nar', 'nifi-elasticsearch-restapi-nar',
    'nifi-groovyx-nar', 'nifi-jetty-nar', 'nifi-kafka-3-service-nar',
    'nifi-kafka-nar', 'nifi-kafka-service-api-nar',
    'nifi-record-serialization-services-nar', 'nifi-standard-nar',
    'nifi-standard-services-api-nar', 'nifi-standard-shared-nar',
    'nifi-update-attribute-nar',
})


def require(condition, message):
    if not condition:
        raise ValueError(message)


def canonical_sha256(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def load(path):
    def pairs(items):
        result = {}
        for key, value in items:
            require(key not in result, 'duplicate JSON key')
            result[key] = value
        return result
    path = Path(path)
    require(path.is_file() and not path.is_symlink(), 'metadata must be a regular file')
    return json.loads(path.read_text(), object_pairs_hook=pairs)


def relative(name):
    require(isinstance(name, str) and bool(name) and '\\' not in name and '\x00' not in name,
            'invalid path')
    path = PurePosixPath(name)
    require(not path.is_absolute() and all(p not in ('', '.', '..') for p in name.split('/')),
            'path escape or noncanonical path')
    return path


def in_scope(name):
    return any(name == scope or name.startswith(scope + '/') for scope in SCOPES)


def virtual(source, name):
    """Resolve image-absolute symlinks inside a virtual root, never host /opt."""
    pending = list(relative(name).parts)
    resolved = []
    links = 0
    while pending:
        part = pending.pop(0)
        if part in ('', '.'):
            continue
        if part == '..':
            require(bool(resolved), 'symlink escape')
            resolved.pop()
            continue
        candidate = source.joinpath(*resolved, part)
        if candidate.is_symlink():
            links += 1
            require(links <= 40, 'cyclic symlink')
            target = os.readlink(candidate)
            require('\\' not in target and '\x00' not in target, 'invalid symlink')
            if target.startswith('/'):
                resolved = []
            pending = target.split('/') + pending
        else:
            resolved.append(part)
    result = '/'.join(resolved)
    require(in_scope(result), 'symlink outside approved scope')
    path = source / result
    require(path.exists() and not path.is_symlink(), 'broken symlink target')
    return result


def file_digest(path):
    # Preparation runs as owner/root; fail rather than changing source access time.
    flags = os.O_RDONLY | os.O_NOFOLLOW | os.O_NOATIME
    with os.fdopen(os.open(path, flags), 'rb') as handle:
        digest = hashlib.file_digest(handle, 'sha256').hexdigest()
    return digest


def attributes(path):
    return {key: base64.b64encode(os.getxattr(path, key, follow_symlinks=False)).decode()
            for key in sorted(os.listxattr(path, follow_symlinks=False))}


def snapshot(source):
    """Inventory all preserved paths without following tree symlinks."""
    source = Path(source)
    result = {}
    inodes = {}

    def entry(name, descend=True):
        path = source / name
        info = path.lstat()
        kind = stat.S_IFMT(info.st_mode)
        require(kind in (stat.S_IFDIR, stat.S_IFREG, stat.S_IFLNK), 'unsupported special file type')
        row = {'kind': {stat.S_IFDIR: 'directory', stat.S_IFREG: 'file', stat.S_IFLNK: 'symlink'}[kind],
               'mode': stat.S_IMODE(info.st_mode), 'uid': info.st_uid, 'gid': info.st_gid,
               'mtime_ns': info.st_mtime_ns, 'xattrs': attributes(path)}
        if kind == stat.S_IFREG:
            row.update(size=info.st_size, sha256=file_digest(path))
            key = (info.st_dev, info.st_ino)
            if key in inodes:
                row['hardlink_to'] = inodes[key]
            else:
                inodes[key] = name
        elif kind == stat.S_IFLNK:
            row['target'] = os.readlink(path)
            virtual(source, name)
        result[name] = row
        if kind == stat.S_IFDIR and descend:
            fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_NOATIME)
            try:
                names = sorted(os.listdir(fd))
            finally:
                os.close(fd)
            for child in names:
                entry(name + '/' + child)

    for scope in SCOPES:
        parts = PurePosixPath(scope).parts
        for i in range(1, len(parts)):
            parent = '/'.join(parts[:i])
            if parent not in result:
                entry(parent, descend=False)
        require(os.path.lexists(source / scope), 'missing preserved scope: ' + scope)
        entry(scope)
    return result


def validate_profile(profile):
    require(canonical_sha256(profile) == PROFILE_SHA256, 'profile fingerprint drift')
    require(profile['schema'] == 1 and profile['source_image_config_id'] == SOURCE_IMAGE_ID,
            'source image profile drift')
    require(profile['runtime_approved'] is False and profile['replacement'] is None
            and profile['active_configuration_qualified'] is False, 'profile cannot authorize runtime')
    require(tuple(profile['preserve_scopes']) == SCOPES, 'preservation scope drift')
    rows = profile['nars']
    require(len(rows) == 119 and len({r['id'] for r in rows}) == 119
            and len({r['path'] for r in rows}) == 119, 'source whole-NAR inventory drift')
    by_id = {r['id']: r for r in rows}
    kept = {r['id'] for r in rows if r['action'] == 'retain'}
    excluded = {r['id'] for r in rows if r['action'] == 'exclude'}
    require(excluded == EXCLUDED and len(kept) == 103 and kept | excluded == set(by_id),
            'whole-NAR classification drift')
    require(FLOW_CLOSURE == set(profile['required_flow_bundle_ids']) and FLOW_CLOSURE <= kept,
            'positive flow closure incomplete')
    require(profile['implicit_jetty_root'] == 'nifi-jetty-nar' and 'nifi-jetty-nar' in kept,
            'implicit Jetty closure incomplete')
    for row in rows:
        relative(row['path'])
        require(row['path'] == 'opt/nifi/nifi-current/lib/' + row['id'] + '-2.12.0.nar',
                'whole-NAR path drift')
        require(row['group'] == 'org.apache.nifi' and row['version'] == '2.12.0'
                and re.fullmatch('[0-9a-f]{64}', row['sha256']) and row['reason'], 'invalid NAR identity')
        parent = row['parent']
        require(parent is None or parent in by_id, 'unknown declared NAR parent')
        if row['id'] in kept:
            require(parent is None or parent in kept, 'retained NAR parent closure gap')
        seen = set()
        current = row['id']
        while current:
            require(current not in seen, 'cyclic NAR parent closure')
            seen.add(current)
            current = by_id[current]['parent']
    return by_id


def manifest(path):
    with zipfile.ZipFile(path) as archive:
        entries = [x for x in archive.infolist() if x.filename == 'META-INF/MANIFEST.MF']
        require(len(entries) == 1 and entries[0].file_size <= 1024 * 1024, 'invalid NAR manifest')
        text = archive.read(entries[0]).decode('utf-8').replace('\r\n', '\n')
    lines = []
    for line in text.splitlines():
        if line.startswith(' '):
            require(bool(lines), 'invalid manifest continuation')
            lines[-1] += line[1:]
        else:
            lines.append(line)
    fields = {}
    for line in lines:
        if not line:
            break  # Only the main manifest section defines NAR coordinates.
        require(': ' in line, 'invalid manifest field')
        key, value = line.split(': ', 1)
        require(key not in fields, 'duplicate manifest field')
        fields[key] = value
    return fields


def active_guard(context, observed_config, profile):
    if context is not None:
        require(context == {'status': 'not-captured', 'components': [], 'providers': [],
                            'external_classpaths': []},
                'active context/configuration is not qualified; unknown inputs rejected')
    result = {'status': 'not-captured', 'qualified': False}
    if observed_config is not None:
        observed_config = Path(observed_config)
        require(file_digest(observed_config) == profile['observed_configuration_sha256'],
                'observed configuration fingerprint drift')
        observed = load(observed_config)
        require(observed['image_id'] == SOURCE_IMAGE_ID and observed['runtime_approved'] is False
                and observed['promotion_eligible'] is False, 'observed configuration identity drift')
        supported = {'org.apache.nifi.processors.standard.' + kind for kind in
                     ('GenerateFlowFile', 'ExecuteStreamCommand', 'AttributesToJSON', 'PutFile')}
        require({v['type'] for v in observed['component_types']} == supported,
                'unknown or missing observed component context')
        require(all(v['bundle'] == {'group': 'org.apache.nifi', 'artifact': 'nifi-standard-nar',
                                   'version': '2.12.0'} for v in observed['component_types']),
                'unknown observed active bundle')
        result = {'status': 'own-lab-captured-unqualified', 'qualified': False,
                  'sha256': profile['observed_configuration_sha256'],
                  'provider_selection_and_spi_qualified': False}
    return result


def _copy_metadata(path, row):
    os.chown(path, row['uid'], row['gid'], follow_symlinks=False)
    if row['kind'] != 'symlink':
        os.chmod(path, row['mode'], follow_symlinks=False)
    for name in os.listxattr(path, follow_symlinks=False):
        if name not in row['xattrs']:
            os.removexattr(path, name, follow_symlinks=False)
    for name, value in row['xattrs'].items():
        os.setxattr(path, name, base64.b64decode(value), follow_symlinks=False)
    os.utime(path, ns=(row['mtime_ns'], row['mtime_ns']), follow_symlinks=False)


def prepare(source, output, profile, *, prepare_only, active_context=None, observed_config=None):
    require(prepare_only is True, 'only explicit prepare-only mode is available')
    validate_profile(profile)
    context = active_guard(active_context, observed_config, profile)
    source, output = Path(source).absolute(), Path(output).absolute()
    require(source.resolve(strict=True) == source and source.is_dir(), 'linked source root')
    require(output.parent.resolve(strict=True) == output.parent, 'linked output parent')
    require(not os.path.lexists(output), 'fresh output required')
    require(not output.is_relative_to(source) and not source.is_relative_to(output),
            'overlapping source and output')
    before = snapshot(source)
    physical = {}
    for row in profile['nars']:
        name = virtual(source, row['path'])
        require(name not in physical, 'aliased NAR inventory path')
        physical[name] = row
        require(before[name]['kind'] == 'file' and before[name]['sha256'] == row['sha256'],
                'source whole-NAR hash/type drift')
        fields = manifest(source / name)
        expected = {'Nar-Group': row['group'], 'Nar-Id': row['id'], 'Nar-Version': row['version']}
        if row['parent']:
            expected.update({'Nar-Dependency-Group': 'org.apache.nifi',
                             'Nar-Dependency-Id': row['parent'], 'Nar-Dependency-Version': '2.12.0'})
        else:
            require(not any(k.startswith('Nar-Dependency-') for k in fields), 'unexpected NAR parent')
        require(all(fields.get(k) == v for k, v in expected.items()), 'source manifest closure drift')
    actual = {name for name in before if name.lower().endswith('.nar')}
    require(actual == set(physical), 'additional or missing source NAR inventory')
    removed = {name for name, row in physical.items() if row['action'] == 'exclude'}
    excluded_hashes = {physical[name]['sha256'] for name in removed}
    for name, row in before.items():
        if row['kind'] == 'symlink':
            require(virtual(source, name) not in removed, 'symlink aliases excluded archive')
        elif row['kind'] == 'file' and name not in removed:
            require(row['sha256'] not in excluded_hashes, 'excluded archive survives through alias')
            require(row.get('hardlink_to') not in removed, 'hardlink aliases excluded archive')
    expected_tree = {name: row for name, row in before.items() if name not in removed}
    require(snapshot(source) == before, 'source changed during validation')
    output.mkdir(mode=0o700)
    tree = output / 'tree'
    tree.mkdir(mode=0o755)
    for name, row in expected_tree.items():
        dest = tree / name
        if row['kind'] == 'directory':
            dest.mkdir(mode=0o700)
        elif row['kind'] == 'symlink':
            dest.symlink_to(row['target'])
        elif 'hardlink_to' in row:
            os.link(tree / row['hardlink_to'], dest)
        else:
            with (
                os.fdopen(os.open(source / name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NOATIME), 'rb') as src,
                dest.open('xb') as dst,
            ):
                while chunk := src.read(1024 * 1024):
                    dst.write(chunk)
    for name in sorted(expected_tree, key=lambda x: (len(PurePosixPath(x).parts), x), reverse=True):
        _copy_metadata(tree / name, expected_tree[name])
    require(snapshot(tree) == expected_tree, 'prepared tree metadata or bytes differ')
    require(snapshot(source) == before, 'source changed during copy')
    result = {'schema': 1, 'mode': 'prepared-whole-extension-tree-only',
              'source_image_config_id': SOURCE_IMAGE_ID, 'profile_sha256': canonical_sha256(profile),
              'source_tree_sha256': canonical_sha256(before), 'prepared_tree_sha256': canonical_sha256(expected_tree),
              'retained_nars': 103, 'excluded_nars': 16, 'removed_paths': sorted(removed),
              'runtime_approved': False, 'promotion_eligible': False, 'replacement': None,
              'active_configuration_qualified': False, 'observed_configuration': context,
              'source_image_provenance': 'requires separately verified immutable OCI context',
              'normal_scan': 'not-run', 'nested_scan': 'not-run', 'runtime_tests': 'not-run'}
    for name, value in [('source-tree.json', before), ('prepared-tree.json', expected_tree),
                        ('preparation.json', result)]:
        (output / name).write_text(json.dumps(value, sort_keys=True, indent=2) + '\n')
    return result


def verify_oci(layout, manifest_digest):
    """Bind a local immutable OCI layout to config ID 03f; validate every blob."""
    layout = Path(layout).absolute()
    require(layout.resolve(strict=True) == layout, 'linked OCI layout')
    require(re.fullmatch('sha256:[0-9a-f]{64}', manifest_digest), 'invalid OCI manifest digest')

    def blob(digest):
        require(re.fullmatch('sha256:[0-9a-f]{64}', digest), 'unsupported OCI blob digest')
        path = layout / 'blobs/sha256' / digest.split(':')[1]
        require(path.resolve(strict=True) == path and path.is_file(), 'linked OCI blob')
        require(file_digest(path) == digest.split(':')[1], 'OCI blob digest drift')
        return path

    manifest_data = load(blob(manifest_digest))
    require(manifest_data.get('schemaVersion') == 2 and 'layers' in manifest_data,
            'select a platform image manifest, not an OCI index')
    config = manifest_data['config']['digest']
    require(config == SOURCE_IMAGE_ID, 'OCI source image config ID mismatch')
    config_data = load(blob(config))
    require(config_data.get('os') == 'linux' and config_data.get('architecture') == 'amd64',
            'unexpected source image platform')
    for layer in manifest_data['layers']:
        path = blob(layer['digest'])
        require(path.stat().st_size == layer['size'], 'OCI layer size drift')
    return {'source_image_config_id': config, 'manifest_digest': manifest_digest,
            'build_context': 'oci-layout://' + str(layout) + '@' + manifest_digest,
            'runtime_approved': False, 'layers': len(manifest_data['layers'])}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    prep = sub.add_parser('prepare')
    prep.add_argument('--source', type=Path, required=True)
    prep.add_argument('--output', type=Path, required=True)
    prep.add_argument('--profile', type=Path, default=PROFILE_PATH)
    prep.add_argument('--prepare-only', action='store_true')
    prep.add_argument('--active-context', type=Path)
    prep.add_argument('--observed-config', type=Path)
    oci = sub.add_parser('verify-oci')
    oci.add_argument('--layout', type=Path, required=True)
    oci.add_argument('--manifest-digest', required=True)
    args = parser.parse_args(argv)
    if args.command == 'prepare':
        result = prepare(args.source, args.output, load(args.profile), prepare_only=args.prepare_only,
                         active_context=load(args.active_context) if args.active_context else None,
                         observed_config=args.observed_config)
    else:
        result = verify_oci(args.layout, args.manifest_digest)
    print(json.dumps(result, sort_keys=True))


if __name__ == '__main__':
    main()
