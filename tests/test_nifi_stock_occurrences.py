"""Fail-closed occurrence mapping and NAR closure regressions; synthetic only."""
import importlib.util
import json
import sys
import zipfile
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parents[1] / 'deploy/images/nifi-patches/stock-occurrences'
sys.path.insert(0, str(HERE))
spec = importlib.util.spec_from_file_location('stock_mapping', HERE / 'map_candidates.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


def nar(ident, parent=None):
    fields = {'Nar-Group': 'g', 'Nar-Id': ident, 'Nar-Version': '1'}
    if parent:
        fields |= {'Nar-Dependency-Group': 'g', 'Nar-Dependency-Id': parent, 'Nar-Dependency-Version': '1'}
    return {'manifest': fields}


def test_parent_closure():
    assert m.closure('a', {'a': nar('a', 'b'), 'b': nar('b')}) == ['a', 'b']


@pytest.mark.parametrize('nars', [
    {'a': nar('a', 'b')},
    {'a': nar('a', 'b'), 'b': nar('b', 'a')},
    {'a': nar('a', 'b'), 'b': nar('b'), 'duplicate': nar('b')},
    {'a': {'manifest': {'Nar-Dependency-Version': '1'}}},
])
def test_bad_closure(nars):
    with pytest.raises(ValueError):
        m.closure('a', nars)


def test_duplicate_json(tmp_path):
    p = tmp_path / 'data.json'; p.write_text('{"a":1,"a":2}')
    with pytest.raises(ValueError, match='duplicate'):
        m.load(p)


@pytest.fixture
def model(tmp_path, monkeypatch):
    source = tmp_path / 'source'; source.mkdir()
    component = tmp_path / 'component'; component.mkdir()
    pins = []
    for old, new, _prefix in m.PAIRS.values():
        for name in (old, new):
            p = component / name
            with zipfile.ZipFile(p, 'w') as z:
                z.writestr('resource.txt', 'preserved')
                z.writestr('version', name)
            pins.append({'file': name, 'sha256': m.writer.digest(p)})
        (source / old).write_bytes((component / old).read_bytes())
    pins.append({'file': 'failureaccess-1.0.3.jar', 'sha256': '0' * 64})
    rows = m.writer.inventory(source)
    # Fixtures have no Guava NAR visibility; missing failureaccess stays blocked.
    lock = {'archives': [{'path': r['outer'], 'sha256': r['sha256']} for r in rows]}
    monkeypatch.setattr(m, 'load', lambda p: lock if p.name == 'source-lock.json' else pins)
    return source, component, rows, lock, pins


def invocation(model):
    source, component, rows, _, _ = model
    return m.prepare(source, {'occurrences': rows, 'inventory_sha256': m.writer.inventory_hash(rows)}, component)


def test_missing_dependency(model):
    with pytest.raises(ValueError, match='failureaccess'):
        invocation(model)


def test_missing_occurrence(model):
    model[2].pop()
    with pytest.raises(ValueError, match='incomplete'):
        invocation(model)


def test_source_drift(model):
    (model[0] / m.PAIRS['guava'][0]).write_bytes((model[1] / m.PAIRS['guava'][1]).read_bytes())
    with pytest.raises(ValueError, match='drift'):
        invocation(model)


def test_replacement_drift(model):
    (model[1] / m.PAIRS['snappy'][1]).write_bytes(b'drift')
    with pytest.raises(ValueError, match='component hash'):
        invocation(model)


def test_null_inventory(model):
    with pytest.raises((ValueError, TypeError)):
        m.prepare(model[0], {'occurrences': [], 'inventory_sha256': None}, model[1])


def test_blocked_inputs(model, monkeypatch):
    monkeypatch.setattr(m.writer, 'BLOCKED_INPUTS', {model[4][0]['sha256']})
    with pytest.raises(ValueError, match='blocked'):
        invocation(model)


def test_emit_fixture_approval_only(tmp_path):
    import emit_plan
    replacement = tmp_path / 'replacement.jar'; replacement.write_bytes(b'fixture only')
    target = {'family': 'lz4', 'status': 'candidate-pending-parent-QA', 'outer': 'fixture.jar', 'members': [], 'chain_sha256': ['1' * 64], 'replacement': str(replacement), 'replacement_sha256': m.writer.digest(replacement), 'expected_occurrences': 1}
    candidate = tmp_path / 'candidate.json'
    candidate.write_text(json.dumps({'targets': [target], 'counts': {'lz4': 1}, 'inventory_sha256': '2' * 64}))
    assert emit_plan.emit(candidate, ['lz4'])['targets'][0]['status'] == 'candidate-pending-parent-QA'
    approval = tmp_path / 'review.json'
    approval.write_text(json.dumps({'candidate_sha256': m.writer.digest(candidate), 'families': ['lz4'], 'decision': 'approved', 'review_reference': 'synthetic fixture review only'}))
    assert emit_plan.emit(candidate, ['lz4'], approval)['targets'][0]['status'] == 'approved-exact-occurrence'
    candidate.write_text(candidate.read_text() + '\n')
    with pytest.raises(ValueError, match='review'):
        emit_plan.emit(candidate, ['lz4'], approval)
    with pytest.raises(ValueError):
        emit_plan.emit(candidate, ['snappy'])
    target['status'] = 'blocked-consumer-incompatibility'
    candidate.write_text(json.dumps({'targets': [target], 'counts': {'lz4': 1}, 'inventory_sha256': '2' * 64}))
    with pytest.raises(ValueError, match='blocked'):
        emit_plan.emit(candidate, ['lz4'])
