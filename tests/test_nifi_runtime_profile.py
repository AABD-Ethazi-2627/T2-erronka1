"""Whole-extension preparation must preserve source bytes and fail closed on drift."""
import copy
import hashlib
import importlib
import io
import json
import os
import stat
import zipfile
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
PROFILE = REPO / 'deploy/images/nifi-patches/cnc-runtime/profile.json'


def archive(row):
    fields = {'Manifest-Version': '1.0', 'Nar-Group': row['group'],
              'Nar-Id': row['id'], 'Nar-Version': row['version']}
    if row['parent']:
        fields.update({'Nar-Dependency-Group': 'org.apache.nifi',
                       'Nar-Dependency-Id': row['parent'],
                       'Nar-Dependency-Version': '2.12.0'})
    data = io.BytesIO()
    with zipfile.ZipFile(data, 'w') as z:
        z.writestr('META-INF/MANIFEST.MF', ''.join(f'{k}: {v}\r\n' for k, v in fields.items()) + '\r\n')
        z.writestr('META-INF/bundled-dependencies/preserve.jar', b'nested original including scanner metadata')
        z.writestr('WEB-INF/classes/Keep.class', b'fixture classes')
    return data.getvalue()


@pytest.fixture
def fixture(tmp_path, monkeypatch):
    module = importlib.import_module('scripts.nifi_runtime_profile')
    profile = json.loads(PROFILE.read_text())
    source = tmp_path / 'source'
    nifi = source / 'opt/nifi'
    (nifi / 'nifi-2.12.0/lib').mkdir(parents=True)
    (nifi / 'nifi-current').symlink_to('nifi-2.12.0')
    for row in profile['nars']:
        data = archive(row)
        row['sha256'] = hashlib.sha256(data).hexdigest()
        (source / row['path']).write_bytes(data)
    config = nifi / 'nifi-2.12.0/conf/nifi.properties'
    config.parent.mkdir()
    config.write_bytes(b'original defaults\n')
    config.chmod(0o640)
    os.utime(config, ns=(1700000000123456789, 1700000000987654321))
    os.setxattr(config, 'user.cnc_test', b'metadata preserved')
    bootstrap = nifi / 'nifi-2.12.0/lib/bootstrap'
    bootstrap.mkdir()
    (bootstrap / 'keep.jar').write_bytes(b'unclassified platform jar')
    (nifi / 'scripts').mkdir()
    entry = nifi / 'scripts/start.sh'
    entry.write_bytes(b'#!/bin/bash\nexec java\n')
    entry.chmod(0o755)
    (source / 'usr/local/bin').mkdir(parents=True)
    (source / 'usr/local/bin/uv').write_bytes(b'uv source bytes')
    (source / 'usr/local/bin/uv').chmod(0o755)
    (source / 'usr/local/bin/uvx').symlink_to('uv')
    monkeypatch.setattr(module, 'PROFILE_SHA256', module.canonical_sha256(profile))
    return module, profile, source, tmp_path / 'output'


def prepare(fixture, **kwargs):
    module, profile, source, output = fixture
    return module.prepare(source, output, profile, prepare_only=True, **kwargs)


def test_preparation_retains_nested_bytes_permissions_links_and_unknown_jars(fixture):
    module, profile, source, output = fixture
    before = module.snapshot(source)
    result = prepare(fixture)
    assert result['runtime_approved'] is False
    assert result['replacement'] is None
    assert result['active_configuration_qualified'] is False
    assert result['retained_nars'] == 103
    assert result['excluded_nars'] == 16
    assert module.snapshot(source) == before
    tree = output / 'tree'
    assert (tree / 'opt/nifi/nifi-current').is_symlink()
    assert os.readlink(tree / 'opt/nifi/nifi-current') == 'nifi-2.12.0'
    for row in profile['nars']:
        dest = tree / row['path']
        if row['action'] == 'retain':
            assert dest.read_bytes() == (source / row['path']).read_bytes()
        else:
            assert not dest.exists()
    config = tree / 'opt/nifi/nifi-current/conf/nifi.properties'
    assert stat.S_IMODE(config.stat().st_mode) == 0o640
    assert config.stat().st_mtime_ns == 1700000000987654321
    assert config.stat().st_uid == os.getuid()
    assert config.stat().st_gid == os.getgid()
    assert os.getxattr(config, 'user.cnc_test') == b'metadata preserved'
    assert (tree / 'opt/nifi/nifi-current/lib/bootstrap/keep.jar').read_bytes() == b'unclassified platform jar'
    assert (tree / 'usr/local/bin/uvx').is_symlink()
    assert json.loads((output / 'preparation.json').read_text())['runtime_approved'] is False


@pytest.mark.parametrize('mutation', ['drift', 'missing', 'extra', 'library-symlink'])
def test_source_nar_inventory_drift_rejected_before_output(fixture, mutation):
    _, profile, source, output = fixture
    row = profile['nars'][0]
    path = source / row['path']
    if mutation == 'drift':
        path.write_bytes(path.read_bytes() + b'changed')
    elif mutation == 'missing':
        path.unlink()
    elif mutation == 'extra':
        (path.parent / 'unknown.nar').write_bytes(b'unknown')
    else:
        path.unlink()
        path.symlink_to('nifi-standard-nar-2.12.0.nar')
    with pytest.raises(ValueError):
        prepare(fixture)
    assert not output.exists()


@pytest.mark.parametrize('mutation', ['retain-excluded', 'exclude-required', 'hash-rebind', 'traversal', 'absolute'])
def test_untrusted_profile_rebinding_cannot_authorize_a_different_classifier(fixture, mutation):
    _, profile, _, output = fixture
    if mutation == 'retain-excluded':
        next(r for r in profile['nars'] if r['action'] == 'exclude')['action'] = 'retain'
    elif mutation == 'exclude-required':
        next(r for r in profile['nars'] if r['id'] == 'nifi-standard-nar')['action'] = 'exclude'
    elif mutation == 'hash-rebind':
        profile['nars'][0]['sha256'] = '0' * 64
    else:
        profile['nars'][0]['path'] = '../escape.nar' if mutation == 'traversal' else '/tmp/escape.nar'
    with pytest.raises(ValueError):
        prepare(fixture)
    assert not output.exists()


def test_rebound_profile_cannot_hide_parent_or_implicit_jetty_gap(fixture, monkeypatch):
    module, profile, _, output = fixture
    # Even a newly trusted fixture profile must satisfy the semantic closure.
    next(r for r in profile['nars'] if r['id'] == 'nifi-jetty-nar')['action'] = 'exclude'
    monkeypatch.setattr(module, 'PROFILE_SHA256', module.canonical_sha256(profile))
    with pytest.raises(ValueError, match='closure|classification'):
        prepare(fixture)
    assert not output.exists()


@pytest.mark.parametrize('target', ['/etc/passwd', '../../../../outside', 'loop'])
def test_escaped_or_cyclic_symlink_fails_before_copy(fixture, target):
    _, _, source, output = fixture
    (source / 'opt/nifi/loop').symlink_to(target)
    with pytest.raises(ValueError, match='link|escape|scope'):
        prepare(fixture)
    assert not output.exists()


def test_absolute_in_scope_symlink_preserved_without_host_resolution(fixture):
    _, _, source, output = fixture
    (source / 'opt/nifi/nifi-current').unlink()
    (source / 'opt/nifi/nifi-current').symlink_to('/opt/nifi/nifi-2.12.0')
    prepare(fixture)
    assert os.readlink(output / 'tree/opt/nifi/nifi-current') == '/opt/nifi/nifi-2.12.0'


def test_existing_output_and_overlapping_paths_are_never_reused(fixture):
    module, profile, source, output = fixture
    output.mkdir()
    sentinel = output / 'keep'
    sentinel.write_bytes(b'user work')
    with pytest.raises(ValueError):
        prepare(fixture)
    assert sentinel.read_bytes() == b'user work'
    with pytest.raises(ValueError):
        module.prepare(source, source / 'nested', profile, prepare_only=True)
    assert not (source / 'nested').exists()


@pytest.mark.parametrize('context', [
    {'status': 'qualified', 'components': [], 'providers': [], 'external_classpaths': []},
    {'status': 'not-captured', 'components': [{'artifact': 'nifi-amqp-nar'}], 'providers': [], 'external_classpaths': []},
    {'status': 'not-captured', 'components': [], 'providers': ['unknown.provider.Class'], 'external_classpaths': []},
    {'status': 'not-captured', 'components': [], 'providers': [], 'external_classpaths': ['/injected.jar']},
])
def test_unqualified_or_unknown_active_context_cannot_be_reported_as_accepted(fixture, context):
    _, _, _, output = fixture
    with pytest.raises(ValueError, match='context|configuration'):
        prepare(fixture, active_context=context)
    assert not output.exists()


def test_preparation_never_silently_becomes_installation(fixture):
    module, profile, source, output = fixture
    with pytest.raises(ValueError, match='prepare'):
        module.prepare(source, output, profile, prepare_only=False)
    assert not output.exists()


def test_special_files_cannot_enter_serving_tree(fixture):
    _, _, source, output = fixture
    os.mkfifo(source / 'opt/nifi/special')
    with pytest.raises(ValueError, match='special|type'):
        prepare(fixture)
    assert not output.exists()


def test_same_bytes_with_wrong_manifest_coordinates_rejected_even_after_hash_repin(fixture, monkeypatch):
    module, profile, source, output = fixture
    row = next(r for r in profile['nars'] if r['id'] == 'nifi-standard-nar')
    wrong = copy.deepcopy(row)
    wrong['parent'] = 'nifi-amqp-nar'
    data = archive(wrong)
    (source / row['path']).write_bytes(data)
    row['sha256'] = hashlib.sha256(data).hexdigest()
    monkeypatch.setattr(module, 'PROFILE_SHA256', module.canonical_sha256(profile))
    with pytest.raises(ValueError, match='manifest closure'):
        prepare(fixture)
    assert not output.exists()


def test_non_nar_metadata_preserved_for_hardlinks(fixture):
    _, _, source, output = fixture
    original = source / 'opt/nifi/nifi-current/lib/bootstrap/keep.jar'
    os.link(original, original.parent / 'keep-link.jar')
    prepare(fixture)
    one = output / 'tree/opt/nifi/nifi-current/lib/bootstrap/keep.jar'
    two = one.parent / 'keep-link.jar'
    assert one.stat().st_ino == two.stat().st_ino


def test_excluded_whole_archive_cannot_survive_through_unknown_name(fixture):
    _, profile, source, output = fixture
    excluded = next(r for r in profile['nars'] if r['id'] == 'nifi-amqp-nar')
    (source / 'opt/nifi/hidden.jar').write_bytes((source / excluded['path']).read_bytes())
    with pytest.raises(ValueError, match='alias'):
        prepare(fixture)
    assert not output.exists()


@pytest.fixture
def oci(tmp_path, monkeypatch):
    module = importlib.import_module('scripts.nifi_runtime_profile')
    layout = tmp_path / 'oci'
    blobs = layout / 'blobs/sha256'
    blobs.mkdir(parents=True)

    def add(data):
        digest = 'sha256:' + hashlib.sha256(data).hexdigest()
        (blobs / digest.split(':')[1]).write_bytes(data)
        return digest

    config = add(b'{"os":"linux","architecture":"amd64"}')
    layer = b'synthetic compressed layer bytes'
    layer_digest = add(layer)
    manifest = add(json.dumps({'schemaVersion': 2, 'config': {'digest': config},
                              'layers': [{'digest': layer_digest, 'size': len(layer)}]}).encode())
    monkeypatch.setattr(module, 'SOURCE_IMAGE_ID', config)
    return module, layout, manifest, layer_digest


def test_oci_config_identity_and_all_layer_hashes_bound_before_build(oci):
    module, layout, manifest, layer = oci
    result = module.verify_oci(layout, manifest)
    assert result['layers'] == 1
    assert result['runtime_approved'] is False
    assert result['build_context'] == 'oci-layout://' + str(layout) + '@' + manifest
    (layout / 'blobs/sha256' / layer.split(':')[1]).write_bytes(b'corrupt layer')
    with pytest.raises(ValueError, match='digest drift'):
        module.verify_oci(layout, manifest)


def test_oci_manifest_digest_cannot_be_relabelled_as_expected_config_id(oci, monkeypatch):
    module, layout, manifest, _ = oci
    monkeypatch.setattr(module, 'SOURCE_IMAGE_ID', 'sha256:' + '0' * 64)
    with pytest.raises(ValueError, match='config ID mismatch'):
        module.verify_oci(layout, manifest)
