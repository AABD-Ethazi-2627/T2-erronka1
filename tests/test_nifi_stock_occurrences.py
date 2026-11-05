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
    support=source/'failureaccess.jar'
    with zipfile.ZipFile(support,'w') as z:z.writestr('support','synthetic visibility fixture')
    pins.append({'file': 'failureaccess-1.0.3.jar', 'sha256': m.writer.digest(support)})
    rows = m.writer.inventory(source)
    # All loose fixture JARs share the same synthetic visibility directory.
    lock = {'archives': [{'path': r['outer'], 'sha256': r['sha256']} for r in rows]}
    monkeypatch.setattr(m, 'load', lambda p: lock if p.name == 'source-lock.json' else pins)
    return source, component, rows, lock, pins


def invocation(model):
    source, component, rows, _, _ = model
    return m.prepare(source, {'occurrences': rows, 'inventory_sha256': m.writer.inventory_hash(rows)}, component)


def test_missing_dependency(model):
    model[4][-1]['sha256']='0'*64
    with pytest.raises(ValueError, match='failureaccess'):
        invocation(model)


def test_complete_synthetic_mapping_can_reach_all_readiness_guards(model):
    result=invocation(model)
    assert result['counts']=={'guava':1,'lz4':1,'snappy':1}
    assert all(t['status']=='candidate-pending-parent-QA' for t in result['targets'])
    assert next(t for t in result['targets'] if t['family']=='guava')['guava_failureaccess_verified']


def test_source_lock_and_complete_source_guards(model,monkeypatch):
    source,component,rows,lock,_=model
    lock['archives'][0]['sha256']='0'*64
    with pytest.raises(ValueError,match='source lock'):invocation(model)
    lock['archives'][0]['sha256']=rows[0]['sha256']
    monkeypatch.setattr(m.writer,'inventory',lambda *a,**kw:rows)
    actual_files=m.writer.files(source)
    monkeypatch.setattr(m.writer,'files',lambda *a:actual_files[:-1])
    with pytest.raises(ValueError,match='incomplete source inventory'):invocation(model)


def test_hadoop_consumer_keeps_snappy_blocked_without_a_coupled_candidate(model):
    source,component,rows,lock,_=model
    with zipfile.ZipFile(source/'hadoop-common-fixture.jar','w') as z:
        z.writestr('org/apache/hadoop/Compressor.class',b'fixture reference org/xerial/snappy/')
    rows[:]=m.writer.inventory(source)
    lock['archives']=[{'path':r['outer'],'sha256':r['sha256']} for r in rows if not r['members']]
    result=invocation(model)
    snappy=[t for t in result['targets'] if t['family']=='snappy']
    assert snappy and all(t['status']=='blocked-consumer-incompatibility' for t in snappy)


def test_committed_historical_plan_keeps_all_snappy_occurrences_blocked():
    p=json.loads((HERE/'candidate-plan.json').read_text())
    assert p['dry_run'] is True and p['executable'] is False
    assert p['counts']=={'guava':7,'lz4':3,'snappy':9}
    assert all(t['status']=='blocked-consumer-incompatibility' for t in p['targets'] if t['family']=='snappy')


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


@pytest.fixture
def emission(tmp_path):
    import emit_plan
    replacement=tmp_path/'replacement.jar';replacement.write_bytes(b'synthetic replacement')
    target={'family':'lz4','status':'candidate-pending-parent-QA','outer':'fixture.jar','members':[],
            'chain_sha256':['1'*64],'replacement':str(replacement),
            'replacement_sha256':m.writer.digest(replacement),'expected_occurrences':1}
    candidate=tmp_path/'candidate.json'
    candidate.write_text(json.dumps({'targets':[target],'counts':{'lz4':1},'inventory_sha256':'2'*64}))
    review={'candidate_sha256':m.writer.digest(candidate),'families':['lz4'],'decision':'approved',
            'review_reference':'synthetic bounded candidate assembly only; no runtime approval'}
    return emit_plan,candidate,replacement,review


@pytest.mark.parametrize('field,value',[('decision','pending'),('families',['guava']),
    ('review_reference',''),('review_reference',None),('candidate_sha256','0'*64),('extra',True)])
def test_every_review_record_guard_is_required(emission,field,value):
    emit,candidate,_,review=emission
    review[field]=value
    record=candidate.with_name('review.json');record.write_text(json.dumps(review))
    with pytest.raises(ValueError,match='review'):emit.emit(candidate,['lz4'],record)


def test_replacement_integrity_and_occurrence_count_guards(emission):
    emit,candidate,replacement,_=emission
    replacement.write_bytes(b'drifted replacement')
    with pytest.raises(ValueError,match='replacement'):emit.emit(candidate,['lz4'])
    p=json.loads(candidate.read_text());p['counts']['lz4']=2
    candidate.write_text(json.dumps(p))
    with pytest.raises(ValueError,match='incomplete occurrence'):emit.emit(candidate,['lz4'])


def test_snappy_and_hadoop_cannot_be_emitted_independently(emission):
    emit,candidate,_,_=emission
    for families in (['snappy'],['hadoop'],['lz4','snappy']):
        with pytest.raises(ValueError,match='atomic Hadoop/Snappy'):emit.emit(candidate,families)
