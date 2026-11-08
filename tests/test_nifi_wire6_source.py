"""Source migration must preserve tests and reject unpinned or unsafe inputs."""
import hashlib
import importlib.util
import io
import json
import tarfile
from pathlib import Path
from types import SimpleNamespace

import pytest


@pytest.fixture
def migration():
    script = Path(__file__).resolve().parents[1] / 'deploy/images/nifi-patches/wire6/prepare.py'
    spec = importlib.util.spec_from_file_location('wire6_prepare', script)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


def test_wrong_source_is_rejected_before_output(migration, tmp_path):
    archive = tmp_path / 'wrong.tar.gz'
    archive.write_bytes(b'not original source')
    with pytest.raises(ValueError, match='fingerprint'):
        migration.prepare(archive, tmp_path / 'output')
    assert not (tmp_path / 'output').exists()


def test_source_change_preserves_original_test_bytes(migration, tmp_path, monkeypatch):
    java = ('prefix\n' + migration.OLD_CALL + '\nsuffix\n').encode()
    pom = (b'<version>1.1.24</version><square-wireschema.version>5.2.0</square-wireschema.version>'
           b'<kotlin.version>1.9.25</kotlin.version>')
    test = b'original upstream regression test must remain unchanged'
    files = {'pom.xml': pom, migration.JAVA_PATH: java, 'serializer-deserializer/src/test/Keep.java': test}
    archive = tmp_path / 'fixture.tar.gz'
    with tarfile.open(archive, 'w:gz') as target:
        for name, payload in files.items():
            entry = tarfile.TarInfo('aws-glue-schema-registry-' + migration.SOURCE_COMMIT + '/' + name)
            entry.size = len(payload)
            target.addfile(entry, io.BytesIO(payload))
    monkeypatch.setattr(migration, 'SOURCE_SHA256', migration.digest(archive))
    monkeypatch.setattr(migration, 'OLD_JAVA_SHA256', hashlib.sha256(java).hexdigest())
    expected = java.decode().replace(migration.OLD_CALL, migration.NEW_CALL).encode()
    monkeypatch.setattr(migration, 'NEW_JAVA_SHA256', hashlib.sha256(expected).hexdigest())
    output = tmp_path / 'fresh'
    proof = migration.prepare(archive, output)
    assert (output / 'serializer-deserializer/src/test/Keep.java').read_bytes() == test
    assert (output / migration.JAVA_PATH).read_bytes() == expected
    assert set(proof['changed']) == {'pom.xml', migration.JAVA_PATH}
    assert migration.VERSION.encode() in (output / 'pom.xml').read_bytes()
    assert proof['runtime_approved'] is False
    assert json.loads((output / 'cnc-source-provenance.json').read_text()) == proof


@pytest.mark.parametrize('kind', ['symlink', 'traversal'])
def test_unsafe_source_members_are_rejected_before_output(migration, tmp_path, monkeypatch, kind):
    archive = tmp_path / 'unsafe.tar.gz'
    with tarfile.open(archive, 'w:gz') as target:
        prefix = 'aws-glue-schema-registry-' + migration.SOURCE_COMMIT + '/'
        entry = tarfile.TarInfo(prefix + ('link' if kind == 'symlink' else '../../outside'))
        if kind == 'symlink':
            entry.type = tarfile.SYMTYPE
            entry.linkname = '/outside'
        target.addfile(entry)
    monkeypatch.setattr(migration, 'SOURCE_SHA256', migration.digest(archive))
    with pytest.raises(ValueError, match='unsupported'):
        migration.prepare(archive, tmp_path / 'output')
    assert not (tmp_path / 'output').exists()


def test_old_control_requires_working_valid_inputs_not_a_broken_classpath():
    script = Path(__file__).resolve().parents[1] / 'deploy/images/nifi-patches/wire6/readers.py'
    spec = importlib.util.spec_from_file_location('wire6_readers', script)
    readers = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(readers)
    broken = 'FAIL true positive-length-overflow java.lang.NoClassDefFoundError\n'
    assert not readers.old_control_failed(SimpleNamespace(returncode=1, stdout=broken))
    control = ('PASS false valid-scalar\nPASS true valid-scalar\n'
               'FAIL true positive-length-overflow java.lang.ArrayIndexOutOfBoundsException\n')
    assert readers.old_control_failed(SimpleNamespace(returncode=1, stdout=control))
    assert not readers.old_control_failed(SimpleNamespace(returncode=0, stdout=control))
