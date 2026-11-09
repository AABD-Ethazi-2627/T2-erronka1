"""Cold API evidence must reject missing capabilities and broken access controls."""
import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1] / 'deploy/images/nifi-patches/closeout'


def module(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / (name + '.py'))
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


@pytest.mark.parametrize('anonymous_status', [200, 401])
def test_api_probe_checks_access_control_and_real_registry_path(monkeypatch, anonymous_status):
    probe = module('api_probe')
    monkeypatch.setenv('SINGLE_USER_CREDENTIALS_USERNAME', 'private-user')
    monkeypatch.setenv('SINGLE_USER_CREDENTIALS_PASSWORD', 'private-password')
    paths = []

    def request(path, *, token=None, data=None):
        paths.append(path)
        if data:
            return (201, 'private-token') if data['username'] == 'private-user' else (400, '')
        if path == '/nifi/':
            return 200, 'html'
        if not token:
            return anonymous_status, '{}'
        assert token == 'private-token'
        return 200, '{}'

    monkeypatch.setattr(probe, 'request', request)
    evidence = probe.probe()
    assert evidence['cold_api_smoke_passed'] == (anonymous_status == 401)
    assert '/nifi-api/controller/registry-types' in paths
    assert '/nifi-api/flow/registry-types' not in paths
    assert 'private-' not in json.dumps(evidence)
    assert evidence['runtime_approved'] is False


def test_flow_contract_rejects_registered_type_in_wrong_bundle(tmp_path):
    smoke = module('smoke')
    row = {'type': 'required.Type', 'bundle': {
        'group': 'org.apache.nifi', 'artifact': 'nifi-required-nar', 'version': '2.12.0'}}
    (tmp_path / 'flow.json').write_text(json.dumps({'nested': [row]}))
    captures = {'processor-types': {'processorTypes': [row]}}
    assert smoke.flow_contract(captures, tmp_path)['missing'] == []
    captures['processor-types']['processorTypes'] = [row | {'bundle': row['bundle'] | {'artifact': 'wrong'}}]
    assert smoke.flow_contract(captures, tmp_path)['missing']


def test_smoke_never_operates_on_unowned_container(tmp_path, monkeypatch):
    smoke = module('smoke')
    monkeypatch.setattr(smoke, 'run', lambda *a, **k: pytest.fail('Docker must not be called'))
    with pytest.raises(ValueError, match='explicitly owned'):
        smoke.capture('existing-user-nifi', tmp_path / 'output')
    assert not (tmp_path / 'output').exists()


def test_flow_contract_accepts_interface_only_when_live_implementation_declares_it(tmp_path):
    smoke = module('smoke')
    interface = {'type': 'api.Type', 'bundle': {
        'group': 'org.apache.nifi', 'artifact': 'nifi-api-nar', 'version': '2.12.0'}}
    (tmp_path / 'flow.json').write_text(json.dumps({'serviceApi': interface}))
    implementation = {'type': 'impl.Type', 'bundle': interface['bundle'] | {'artifact': 'nifi-impl-nar'},
                      'controllerServiceApis': [interface]}
    captures = {'controller-service-types': {'controllerServiceTypes': [implementation]}}
    assert smoke.flow_contract(captures, tmp_path)['missing'] == []
    implementation['controllerServiceApis'] = []
    assert smoke.flow_contract(captures, tmp_path)['missing']
