"""Blocked qualification must fail both process status and sealed evidence."""
import copy
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parents[1] / 'deploy/images/nifi-patches/otel-qualification'
SPEC = importlib.util.spec_from_file_location('otel_proof_guard', HERE / 'qualification_proof.py')
p = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(p)


def successful():
    return {'status': p.PASSED, 'replacement': None, 'runtime_approved': False,
            'commands': [{'phase': n, 'returncode': 0} for n in ['portable-guards', 'oracle', 'static', 'runtime']],
            'image_identity_unchanged': True, 'source_unchanged': True,
            'remaining_owned_containers': [], 'finalization_errors': []}


@pytest.mark.parametrize('name', p.METADATA)
@pytest.mark.parametrize('mutation', ['approved', 'replacement', 'missing'])
def test_actual_versioned_metadata_cannot_gain_approval(tmp_path, name, mutation):
    for filename in p.METADATA:
        (tmp_path / filename).write_bytes((HERE / filename).read_bytes())
    data = json.loads((tmp_path / name).read_text())
    if mutation == 'approved':
        data['runtime_approved'] = True
    elif mutation == 'replacement':
        data['replacement'] = 'applied'
    else:
        data.pop('replacement')
    (tmp_path / name).write_text(json.dumps(data))
    with pytest.raises(ValueError, match='metadata must retain'):
        p.check_metadata(tmp_path)


@pytest.mark.parametrize('field,value', [('status', 'blocked-aligned-qualification'),
    ('image_identity_unchanged', False), ('source_unchanged', False),
    ('remaining_owned_containers', ['own-container']), ('finalization_errors', ['inspection failed'])])
def test_integrity_or_cleanup_failure_cannot_exit_green(field, value):
    report = successful()
    report[field] = value
    assert p.finish_report(report) == 1
    assert report['status'] == 'blocked-aligned-qualification'


@pytest.mark.parametrize('phase', ['portable-guards', 'oracle', 'static', 'runtime'])
def test_nonzero_phase_cannot_be_hidden(phase):
    report = successful()
    next(c for c in report['commands'] if c['phase'] == phase)['returncode'] = 1
    assert p.finish_report(report) == 1


def test_missing_phase_is_not_completed():
    report = successful()
    report['commands'].pop()
    assert p.finish_report(report) == 1


def test_sealer_preserves_exact_input_hashes_and_refuses_overwrite(tmp_path):
    runner = successful()
    (tmp_path / 'aligned-reserved-result.json').write_text(json.dumps(runner))
    for phase, status in p.PHASE_STATUS.items():
        (tmp_path / (phase + '-result.json')).write_text(json.dumps(
            {'phase': phase, 'status': status, 'replacement': None, 'runtime_approved': False}))
    out = tmp_path / 'summary.json'
    result = p.seal_summary(tmp_path, out)
    assert result['runtime_approved'] is False and result['replacement'] is None
    assert len(result['input_sha256']) == 4
    assert json.loads(out.read_text()) == result
    with pytest.raises(FileExistsError):
        p.seal_summary(tmp_path, out)
    failed = copy.deepcopy(runner)
    failed['commands'][0]['returncode'] = 1
    (tmp_path / 'aligned-reserved-result.json').write_text(json.dumps(failed))
    with pytest.raises(ValueError, match='blocked or incomplete'):
        p.seal_summary(tmp_path, tmp_path / 'forbidden-summary.json')
    assert not (tmp_path / 'forbidden-summary.json').exists()


def test_real_runner_error_path_returns_nonzero_and_saves_blocked(tmp_path, monkeypatch):
    monkeypatch.setitem(sys.modules, 'qualification_proof', p)
    spec = importlib.util.spec_from_file_location('otel_runner_under_test', HERE / 'run_aligned_reserved.py')
    runner = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(runner)
    tools = tmp_path / 'source/deploy/images/nifi-patches/otel-qualification'
    tools.mkdir(parents=True)
    for name in p.METADATA:
        (tools / name).write_bytes((HERE / name).read_bytes())
    config = tmp_path / 'config/security'
    config.mkdir(parents=True)
    (config / 'java.security').write_text('fixture')
    monkeypatch.setattr(runner, 'CONFIG', config.parent)
    image = {'Id': runner.IMAGE, 'RootFS': {'Layers': ['unchanged']}}
    def output(args, **kwargs):
        return json.dumps([image]).encode() if args[1:3] == ['image', 'inspect'] else ''
    monkeypatch.setattr(runner.subprocess, 'check_output', output)
    monkeypatch.setattr(runner.subprocess, 'run', lambda args, **kwargs: subprocess.CompletedProcess(args, 1))
    assert runner.run_qualification(tmp_path) == 1
    saved = json.loads((tmp_path / 'aligned-reserved-result.json').read_text())
    assert saved['status'] == 'blocked-aligned-qualification'
    assert saved['commands'][0]['returncode'] == 1


def test_narrow_runner_checks_requested_phase_integrity_and_previous_failures():
    report = successful()
    report['status'] = 'bounded-requested-phase-passed'
    report['commands'] = [{'phase': 'unit-green', 'returncode': 0}, {'phase': 'static', 'returncode': 0}]
    assert p.finish_narrow_report(report, ['static']) == 0
    assert p.finish_narrow_report(copy.deepcopy(report), ['runtime']) == 1
    for field, value in [('image_identity_unchanged', False), ('source_unchanged', False),
                         ('remaining_owned_containers', ['leftover'])]:
        bad = copy.deepcopy(report)
        bad[field] = value
        assert p.finish_narrow_report(bad, ['static']) == 1
    report['commands'].append({'phase': 'static', 'returncode': 1})
    assert p.finish_narrow_report(report, ['static']) == 1


def test_runner_refuses_failed_phase_logs_before_any_docker_call(tmp_path, monkeypatch):
    monkeypatch.setitem(sys.modules, 'qualification_proof', p)
    spec = importlib.util.spec_from_file_location('otel_existing_guard', HERE / 'run_aligned_reserved.py')
    runner = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(runner)
    failure = tmp_path / 'static.stderr'
    failure.write_text('previous failure must survive')
    def forbidden(*args, **kwargs):
        raise AssertionError('Docker must not run')
    monkeypatch.setattr(runner.subprocess, 'check_output', forbidden)
    with pytest.raises(ValueError, match='fresh proof root'):
        runner.run_qualification(tmp_path)
    assert failure.read_text() == 'previous failure must survive'
