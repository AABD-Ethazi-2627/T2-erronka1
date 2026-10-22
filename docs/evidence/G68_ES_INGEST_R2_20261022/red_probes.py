"""Independent read-only PR review probes. Only own labelled ES and D: files."""
import asyncio
import copy
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import time
import uuid

OUT = Path(__file__).resolve().parent
ROOT = Path('D:\\github\\_worktrees\\t2-es-ingest-20261022')
os.environ['TMP'] = os.environ['TEMP'] = str(OUT / 'temp')
os.environ['PYTHONDONTWRITEBYTECODE'] = '1'
sys.path[:0] = [str(ROOT), str(ROOT / 'tests')]
from scripts.durable_pipeline import Pipeline, PipelineBlocked, encoded
from scripts.archive_consumer import event_key
from scripts.validate_contracts import validators
import httpx

DOCKER = ['wsl', '-d', 'FedoraLinux-43', '--exec', '/usr/sbin/docker']
IMAGE = 'docker.elastic.co/elasticsearch/elasticsearch:9.5.4'
LABEL = 't2.review=g68-pr74-fix-r2-20261022'
result = {'passed': False, 'operations': [], 'checks': []}
cid = None
def command(args, **kwargs):
    p = subprocess.run(DOCKER + args, capture_output=True, text=True, timeout=35, **kwargs)
    if p.returncode:
        raise RuntimeError({'command': args, 'code': p.returncode, 'stderr': p.stderr})
    return p.stdout.strip()
def request(method, path, body=None, raw=None, expected=None, ctype='application/json'):
    if raw is None:
        raw = '' if body is None else json.dumps(body, ensure_ascii=False)
    response = command(['exec', '-i', cid, 'curl', '-sS', '--max-time', '10', '-X', method, '-H', 'Content-Type: ' + ctype, '--data-binary', '@-', '-w', '\n%{http_code}', 'http://127.0.0.1:9200' + path], input=raw)
    text, code = response.rsplit('\n', 1)
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        data = text
    result['operations'].append({'method': method, 'path': path, 'request': raw, 'status': int(code), 'response': data})
    if expected is not None:
        assert int(code) == expected, (path, code, data)
    return int(code), data
def check(name):
    result['checks'].append(name)
    print('PASS:', name, flush=True)
def put(path, doc, expected=200):
    return request('PUT', path, doc, expected=expected)[1]

def main():
    global cid
    OUT.joinpath('temp').mkdir(exist_ok=True)
    lab = OUT / 'red-lab'
    lab.mkdir(exist_ok=False)
    for name in ('data', 'java-temp', 'logs'):
        (lab / name).mkdir()
    result['containers_before'] = command(['ps', '-aq']).splitlines()
    result['image'] = json.loads(command(['image', 'inspect', IMAGE]))[0]['Id']
    mounts = []
    for name in ('data', 'java-temp', 'logs'):
        src = '/mnt/d/' + (lab / name).as_posix()[3:]
        mounts += ['--mount', f'type=bind,src={src},dst=/usr/share/elasticsearch/{name}']
    cid = command(['run', '-d', '--pull=never', '--name', 'pr74-review-' + uuid.uuid4().hex, '--label', LABEL, '--cap-drop=ALL', '--security-opt=no-new-privileges', '--log-driver=none', '--memory=1280m', '--memory-swap=1280m', '--cpus=2', '--pids-limit=512', '-p', '127.0.0.1::9200', *mounts, '-e', 'ES_LOG_STYLE=file', '-e', 'ES_TMPDIR=/usr/share/elasticsearch/java-temp', '-e', 'discovery.type=single-node', '-e', 'network.host=0.0.0.0', '-e', 'xpack.security.enabled=false', '-e', 'xpack.ml.enabled=false', '-e', 'ingest.geoip.downloader.enabled=false', '-e', 'ES_JAVA_OPTS=-Xms384m -Xmx384m', IMAGE])
    inspected = json.loads(command(['inspect', cid]))[0]
    assert inspected['Config']['Labels']['t2.review'] == LABEL.split('=', 1)[1]
    assert all(m['Type'] == 'bind' and m['Source'].startswith('/mnt/d/') for m in inspected['Mounts'])
    assert inspected['HostConfig']['PortBindings']['9200/tcp'][0]['HostIp'] == '127.0.0.1'
    result['isolation'] = {'id': cid, 'mounts': inspected['Mounts'], 'ports': inspected['NetworkSettings']['Ports'], 'label': LABEL}
    deadline = time.monotonic() + 150
    while True:
        p = subprocess.run(DOCKER + ['exec', cid, 'curl', '-sf', '--max-time', '2', 'http://127.0.0.1:9200'], capture_output=True, text=True, timeout=10)
        if p.returncode == 0:
            assert json.loads(p.stdout)['version']['number'] == '9.5.4'
            break
        assert time.monotonic() < deadline, 'Own ES not ready after 150s'
        time.sleep(1)

    from test_es_ingest_pipeline import synthetic_prediction
    doc = synthetic_prediction()
    validators(ROOT / 'contracts')['prediction'].validate(doc)
    template = json.loads((ROOT / 'elasticsearch/index-template.json').read_text())
    put('/_index_template/cnc-red', template)
    code, body = request('PUT', '/cnc-telemetry-red/_doc/valid', doc)
    assert code == 400 and 'does not exist' in json.dumps(body)
    result['F1'] = {'expected_valid_status': 201, 'actual_status': code, 'regression_red': True}
    put('/_ingest/pipeline/cnc-prediction-v1', json.loads((ROOT / 'elasticsearch/ingest-pipeline.json').read_text()))
    put('/cnc-telemetry-red/_doc/valid?refresh=true', doc, expected=201)
    result['F2'] = []
    for name, value in [('root', {**doc, 'unexpected_contract_field': True}), ('source', {**doc, 'source': {**doc['source'], 'unexpected_contract_field': True}})]:
        error = request('PUT', '/cnc-telemetry-red/_doc/rejected', value, expected=400)[1]
        assert 'CG18 unknown field' in json.dumps(error)
        try:
            assert 'strict_dynamic_mapping_exception' in json.dumps(error)
        except AssertionError:
            result['F2'].append({'case': name, 'old_assertion': 'strict_dynamic_mapping_exception', 'regression_red': True})
        else:
            raise AssertionError('Expected old verifier assertion to fail')
    result['passed'] = True

if __name__ == '__main__':
    try:
        main()
    finally:
        if cid:
            command(['rm', '--force', cid])
        result['containers_after'] = command(['ps', '-aq']).splitlines()
        assert sorted(result['containers_before']) == sorted(result['containers_after'])
        result['container_removed'] = True
        (OUT / 'red-result.json').write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
