"""Whole-extension preparation must preserve source bytes and fail closed on drift."""
import copy
import hashlib
import importlib
import io
import json
import os
import runpy
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


def freeze_fixture(module, profile, source, monkeypatch):
    rows = module.snapshot(source)
    baseline = {'schema': 1, 'expected_source_image_config_id': module.SOURCE_IMAGE_ID,
                'scope_roots': list(module.SCOPES), 'source_tree': rows,
                'binding': {'method': 'cold-image-export-and-verified-oci',
                            'oci_manifest_digest': 'sha256:' + 'a' * 64,
                            'oci_verification_sha256': 'b' * 64, 'config_id': module.SOURCE_IMAGE_ID},
                'runtime_approved': False}
    (source.parent / 'baseline.json').write_text(json.dumps(baseline))
    profile['source_baseline'] = {'status': 'frozen-independent-cold-capture',
                                  'canonical_sha256': module.canonical_sha256(baseline),
                                  'source_tree_sha256': module.canonical_sha256(rows),
                                  'file': 'baseline.json'}
    monkeypatch.setattr(module, 'PROFILE_SHA256', module.canonical_sha256(profile))


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
    freeze_fixture(module, profile, source, monkeypatch)
    return module, profile, source, tmp_path / 'output'


def prepare(fixture, **kwargs):
    module, profile, source, output = fixture
    return module.prepare(source, output, profile, prepare_only=True,
                          baseline=json.loads((source.parent / 'baseline.json').read_text()), **kwargs)


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


def test_absolute_in_scope_symlink_preserved_without_host_resolution(fixture, monkeypatch):
    module, profile, source, output = fixture
    (source / 'opt/nifi/nifi-current').unlink()
    (source / 'opt/nifi/nifi-current').symlink_to('/opt/nifi/nifi-2.12.0')
    freeze_fixture(module, profile, source, monkeypatch)
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
    with pytest.raises(ValueError, match='manifest closure|baseline'):
        prepare(fixture)
    assert not output.exists()


def test_non_nar_metadata_preserved_for_hardlinks(fixture, monkeypatch):
    module, profile, source, output = fixture
    original = source / 'opt/nifi/nifi-current/lib/bootstrap/keep.jar'
    os.link(original, original.parent / 'keep-link.jar')
    freeze_fixture(module, profile, source, monkeypatch)
    prepare(fixture)
    one = output / 'tree/opt/nifi/nifi-current/lib/bootstrap/keep.jar'
    two = one.parent / 'keep-link.jar'
    assert one.stat().st_ino == two.stat().st_ino


def test_excluded_whole_archive_cannot_survive_through_unknown_name(fixture):
    _, profile, source, output = fixture
    excluded = next(r for r in profile['nars'] if r['id'] == 'nifi-amqp-nar')
    (source / 'opt/nifi/hidden.jar').write_bytes((source / excluded['path']).read_bytes())
    with pytest.raises(ValueError, match='alias|baseline'):
        prepare(fixture)
    assert not output.exists()


@pytest.fixture
def oci(tmp_path, monkeypatch):
    import gzip
    module = importlib.import_module('scripts.nifi_runtime_profile')
    layout = tmp_path / 'oci'
    blobs = layout / 'blobs/sha256'
    blobs.mkdir(parents=True)

    def add(data):
        digest = 'sha256:' + hashlib.sha256(data).hexdigest()
        (blobs / digest.split(':')[1]).write_bytes(data)
        return digest

    decoded = b'synthetic tar stream' * 64
    layer = gzip.compress(decoded)
    diff_id = 'sha256:' + hashlib.sha256(decoded).hexdigest()
    cfg = json.dumps({'os': 'linux', 'architecture': 'amd64',
                      'rootfs': {'type': 'layers', 'diff_ids': [diff_id]}}).encode()
    config = add(cfg)
    layer_digest = add(layer)
    manifest_data = {'schemaVersion': 2, 'mediaType': 'application/vnd.oci.image.manifest.v1+json',
                     'config': {'digest': config, 'size': len(cfg),
                                'mediaType': 'application/vnd.oci.image.config.v1+json'},
                     'layers': [{'digest': layer_digest, 'size': len(layer),
                                 'mediaType': 'application/vnd.oci.image.layer.v1.tar+gzip'}]}
    manifest_bytes = json.dumps(manifest_data).encode()
    manifest = add(manifest_bytes)
    (layout / 'oci-layout').write_text('{"imageLayoutVersion":"1.0.0"}')
    (layout / 'index.json').write_text(json.dumps({'schemaVersion': 2, 'manifests': [
        {'digest': manifest, 'size': len(manifest_bytes), 'mediaType': manifest_data['mediaType'],
         'platform': {'os': 'linux', 'architecture': 'amd64'}}]}))
    monkeypatch.setattr(module, 'SOURCE_IMAGE_ID', config)
    return module, layout, manifest, layer_digest


def test_oci_config_identity_and_all_layer_hashes_bound_before_build(oci):
    module, layout, manifest, layer = oci
    result = module.verify_oci(layout, manifest)
    assert len(result['layers']) == 1
    assert result['runtime_approved'] is False
    assert result['build_context'] == 'oci-layout://' + str(layout) + '@' + manifest
    (layout / 'blobs/sha256' / layer.split(':')[1]).write_bytes(b'corrupt layer')
    with pytest.raises(ValueError, match='digest drift|size drift'):
        module.verify_oci(layout, manifest)


def test_oci_manifest_digest_cannot_be_relabelled_as_expected_config_id(oci, monkeypatch):
    module, layout, manifest, _ = oci
    monkeypatch.setattr(module, 'SOURCE_IMAGE_ID', 'sha256:' + '0' * 64)
    with pytest.raises(ValueError, match='config ID mismatch'):
        module.verify_oci(layout, manifest)


@pytest.mark.parametrize('mutation', ['script', 'bootstrap', 'uv', 'hidden-code'])
def test_changed_non_nar_source_never_receives_frozen_image_provenance(fixture, mutation):
    _, _, source, output = fixture
    names = {'script': 'opt/nifi/scripts/start.sh',
             'bootstrap': 'opt/nifi/nifi-current/lib/bootstrap/keep.jar',
             'uv': 'usr/local/bin/uv', 'hidden-code': 'opt/nifi/unpacked/excluded.class'}
    path = source / names[mutation]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b'untrusted source content')
    with pytest.raises(ValueError, match='baseline|binding'):
        prepare(fixture)
    assert not output.exists()


def test_scope_inventory_does_not_identify_or_restore_mount_stub_parents(fixture):
    module, _, source, _ = fixture
    before = module.snapshot(source)
    assert not {'opt', 'usr', 'usr/local', 'usr/local/bin'} & set(before)
    os.utime(source / 'usr', ns=(1700000000000000000, 1800000000000000000))
    os.chmod(source / 'usr/local/bin', 0o700)
    assert module.snapshot(source) == before


def test_unmodified_real_profile_pin_and_current_repository_flow_closure():
    module = importlib.import_module('scripts.nifi_runtime_profile')
    profile = module.load(PROFILE)
    module.validate_profile(profile)
    result = module.flow_guard(REPO, profile)
    assert len(result['modern_seeds']) == 11
    assert len(result['closure']) == 13
    assert result['runtime_approved'] is False


def test_new_flow_using_excluded_extension_requires_explicit_scope_review(tmp_path):
    module = importlib.import_module('scripts.nifi_runtime_profile')
    import shutil
    shutil.copytree(REPO / 'nifi-flows', tmp_path / 'nifi-flows')
    (tmp_path / 'deploy/cg14').mkdir(parents=True)
    shutil.copy2(REPO / 'deploy/cg14/restore-inventory.json', tmp_path / 'deploy/cg14/restore-inventory.json')
    (tmp_path / 'nifi-flows/new-cloud.json').write_text(json.dumps({
        'type': 'org.apache.nifi.processors.gcp.PutGCSObject',
        'bundle': {'group': 'org.apache.nifi', 'artifact': 'nifi-gcp-nar', 'version': '2.12.0'}}))
    with pytest.raises(ValueError, match='excluded|flow'):
        module.flow_guard(tmp_path, module.load(PROFILE))


def test_zero_oci_layers_rejected_even_with_honest_config_hash(oci):
    module, layout, _, _ = oci
    config = module.SOURCE_IMAGE_ID
    data = json.dumps({'schemaVersion': 2, 'config': {'digest': config}, 'layers': []}).encode()
    digest = hashlib.sha256(data).hexdigest()
    (layout / 'blobs/sha256' / digest).write_bytes(data)
    with pytest.raises(ValueError):
        module.verify_oci(layout, 'sha256:' + digest)


def test_oci_layout_membership_is_required_not_just_a_blob_directory(oci):
    module, layout, manifest, _ = oci
    (layout / 'index.json').write_text('{"schemaVersion":2,"manifests":[]}')
    with pytest.raises(ValueError):
        module.verify_oci(layout, manifest)


def rewrite_oci_manifest(layout, manifest, change):
    blobs = layout / 'blobs/sha256'
    data = json.loads((blobs / manifest.split(':')[1]).read_text())
    change(data)
    encoded = json.dumps(data).encode()
    new = 'sha256:' + hashlib.sha256(encoded).hexdigest()
    (blobs / new.split(':')[1]).write_bytes(encoded)
    index = json.loads((layout / 'index.json').read_text())
    index['manifests'][0]['digest'] = new
    index['manifests'][0]['size'] = len(encoded)
    (layout / 'index.json').write_text(json.dumps(index))
    return new


@pytest.mark.parametrize('mutation', ['wrong-rootfs', 'crc', 'truncated', 'unknown-compression',
                                     'foreign', 'foreign-url', 'zero-layers', 'count-mismatch'])
def test_oci_checks_decoded_stream_crc_compression_and_exact_layer_sequence(oci, mutation):
    import gzip
    module, layout, manifest, _ = oci
    blobs = layout / 'blobs/sha256'

    def change(data):
        layer = data['layers'][0]
        if mutation == 'unknown-compression':
            layer['mediaType'] = 'application/vnd.oci.image.layer.v1.tar+zstd'
        elif mutation == 'foreign':
            layer['mediaType'] = 'application/vnd.docker.image.rootfs.foreign.diff.tar.gzip'
        elif mutation == 'foreign-url':
            layer['urls'] = ['https://invalid.example/layer']
        elif mutation == 'zero-layers':
            data['layers'] = []
        elif mutation == 'count-mismatch':
            data['layers'].append(copy.deepcopy(layer))
        else:
            original = (blobs / layer['digest'].split(':')[1]).read_bytes()
            if mutation == 'wrong-rootfs':
                payload = gzip.compress(b'alien filesystem stream')
            elif mutation == 'truncated':
                payload = original[:-5]
            else:
                payload = original[:-8] + bytes([original[-8] ^ 1]) + original[-7:]
            layer['digest'] = 'sha256:' + hashlib.sha256(payload).hexdigest()
            layer['size'] = len(payload)
            (blobs / layer['digest'].split(':')[1]).write_bytes(payload)

    selected = rewrite_oci_manifest(layout, manifest, change)
    with pytest.raises(ValueError):
        module.verify_oci(layout, selected)


def test_uncompressed_tar_media_hashes_the_same_decoded_rootfs_stream(oci):
    import gzip
    module, layout, manifest, _ = oci
    blobs = layout / 'blobs/sha256'

    def change(data):
        layer = data['layers'][0]
        payload = gzip.decompress((blobs / layer['digest'].split(':')[1]).read_bytes())
        layer['digest'] = 'sha256:' + hashlib.sha256(payload).hexdigest()
        layer['size'] = len(payload)
        layer['mediaType'] = 'application/vnd.oci.image.layer.v1.tar'
        (blobs / layer['digest'].split(':')[1]).write_bytes(payload)

    selected = rewrite_oci_manifest(layout, manifest, change)
    result = module.verify_oci(layout, selected)
    assert result['source_binding'] == 'verified-oci-index-config-ordered-layer-diff-ids'
    assert result['layers'][0]['decoded_bytes'] == 1280


def test_decompression_is_bounded_even_when_compressed_digest_is_honest(oci, monkeypatch):
    module, layout, manifest, _ = oci
    monkeypatch.setattr(module, 'MAX_DECODED_BYTES', 100)
    with pytest.raises(ValueError, match='budget'):
        module.verify_oci(layout, manifest)


@pytest.mark.parametrize('mutation', ['wrong-platform', 'missing-index', 'missing-layout', 'not-member'])
def test_oci_selected_manifest_must_belong_to_valid_platform_layout(oci, mutation):
    module, layout, manifest, _ = oci
    if mutation == 'missing-index':
        (layout / 'index.json').unlink()
    elif mutation == 'missing-layout':
        (layout / 'oci-layout').unlink()
    else:
        data = json.loads((layout / 'index.json').read_text())
        if mutation == 'wrong-platform':
            data['manifests'][0]['platform']['architecture'] = 'arm64'
        else:
            data['manifests'][0]['digest'] = 'sha256:' + '0' * 64
        (layout / 'index.json').write_text(json.dumps(data))
    with pytest.raises(ValueError):
        module.verify_oci(layout, manifest)


def test_real_profile_cannot_materialize_before_independent_cold_baseline(tmp_path):
    module = importlib.import_module('scripts.nifi_runtime_profile')
    profile = module.load(PROFILE)
    module.validate_profile(profile)
    source = tmp_path / 'source'
    source.mkdir()
    with pytest.raises(ValueError, match='baseline pending'):
        module.prepare(source, tmp_path / 'new', profile, prepare_only=True)
    assert not (tmp_path / 'new').exists()


def test_observed_configuration_branch_retains_unqualified_status_and_rejects_drift(tmp_path):
    module = importlib.import_module('scripts.nifi_runtime_profile')
    kinds = ['PutFile', 'ExecuteStreamCommand', 'AttributesToJSON', 'GenerateFlowFile']
    observed = {'image_id': module.SOURCE_IMAGE_ID, 'runtime_approved': False,
                'promotion_eligible': False, 'component_types': [
                    {'type': 'org.apache.nifi.processors.standard.' + kind,
                     'bundle': {'artifact': 'nifi-standard-nar', 'group': 'org.apache.nifi', 'version': '2.12.0'}}
                    for kind in kinds]}
    path = tmp_path / 'synthetic-observed.json'
    path.write_text(json.dumps(observed))
    # This unit fixture is not the real evidence pin and cannot pass validate_profile.
    profile = {'observed_configuration_sha256': hashlib.sha256(path.read_bytes()).hexdigest()}
    result = module.active_guard(None, path, profile)
    assert result['status'] == 'own-lab-captured-unqualified'
    assert result['qualified'] is False
    observed['component_types'][0]['bundle']['artifact'] = 'nifi-gcp-nar'
    path.write_text(json.dumps(observed))
    with pytest.raises(ValueError, match='fingerprint drift'):
        module.active_guard(None, path, profile)


@pytest.mark.parametrize('tamper', [False, True])
def test_actual_serving_heredoc_materializes_scopes_without_restoring_os_parents(fixture, tmp_path, tamper):
    _, _, _, output = fixture
    prepare(fixture)
    fake_root = tmp_path / 'fresh-os'
    (fake_root / 'usr/local/bin').mkdir(parents=True)
    (fake_root / 'usr/local/bin').chmod(0o731)
    (fake_root / 'usr/local/bin/os-tool').write_bytes(b'fresh OS unchanged')
    if tamper:
        (output / 'tree/usr/local/bin/uv').write_bytes(b'drift')
    docker = (REPO / 'deploy/images/nifi-cnc.Dockerfile').read_text()
    body = docker.split("python3 - <<'PY'\n", 1)[1].split('\nPY\n', 1)[0]
    body = body.replace("'/tools/nifi_runtime_profile.py'", repr(str(REPO / 'scripts/nifi_runtime_profile.py')))
    for name in ['prepared-tree.json', 'preparation.json', 'tree']:
        body = body.replace(repr('/proof/' + name), repr(str(output / name)))
    body = body.replace("Path('/')", 'Path(' + repr(str(fake_root)) + ')')
    assert "'/proof/" not in body and "Path('/')" not in body
    guard = tmp_path / 'actual_serving_guard.py'
    guard.write_text(body)
    if tamper:
        with pytest.raises(ValueError, match='prepared bytes or metadata changed'):
            runpy.run_path(str(guard))
        assert not (fake_root / 'usr/local/bin/uv').exists()
    else:
        runpy.run_path(str(guard))
        assert (fake_root / 'usr/local/bin/uv').read_bytes() == b'uv source bytes'
        assert stat.S_IMODE((fake_root / 'usr/local/bin').stat().st_mode) == 0o731
    assert (fake_root / 'usr/local/bin/os-tool').read_bytes() == b'fresh OS unchanged'


def test_rootfs_diff_ids_are_checked_in_order_not_as_an_unordered_set(oci, monkeypatch):
    import gzip
    module, layout, manifest, _ = oci
    blobs = layout / 'blobs/sha256'
    originals = [b'first decoded layer', b'second decoded layer']
    cfg = json.dumps({'os': 'linux', 'architecture': 'amd64',
                      'rootfs': {'type': 'layers', 'diff_ids': [
                          'sha256:' + hashlib.sha256(v).hexdigest() for v in originals]}}).encode()
    config = 'sha256:' + hashlib.sha256(cfg).hexdigest()
    (blobs / config.split(':')[1]).write_bytes(cfg)
    monkeypatch.setattr(module, 'SOURCE_IMAGE_ID', config)

    def change(data):
        data['config']['digest'] = config
        data['config']['size'] = len(cfg)
        data['layers'] = []
        for stream in reversed(originals):
            encoded = gzip.compress(stream)
            digest = 'sha256:' + hashlib.sha256(encoded).hexdigest()
            (blobs / digest.split(':')[1]).write_bytes(encoded)
            data['layers'].append({'digest': digest, 'size': len(encoded),
                                   'mediaType': 'application/vnd.oci.image.layer.v1.tar+gzip'})

    selected = rewrite_oci_manifest(layout, manifest, change)
    with pytest.raises(ValueError, match='diff_ids mismatch or order'):
        module.verify_oci(layout, selected)
