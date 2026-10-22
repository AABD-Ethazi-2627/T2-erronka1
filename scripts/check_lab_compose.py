#!/usr/bin/env python3
"""Validate historical Compose without a daemon, services or real credentials."""
import json
import os
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
COMPOSE = ROOT / 'docs/templates/infra/docker-compose.yaml'
ENV = {k: v for k, v in os.environ.items() if not k.startswith('CNC_')}
ENV.update(CNC_NIFI_PASSWORD='validation-only-password', CNC_STREAM_DIR='/tmp/cnc-fixture')


def render(overrides=None, missing=None):
    env = ENV | (overrides or {})
    if missing:
        env.pop(missing, None)
    return subprocess.run(
        ['docker', 'compose', '--env-file', '/dev/null', '-f', str(COMPOSE),
         'config', '--format', 'json'], env=env, cwd=ROOT,
        capture_output=True, text=True,
    )


def check(overrides, bind, hosts):
    result = render(overrides)
    assert result.returncode == 0, result.stderr
    services = json.loads(result.stdout)['services']
    assert set(services) == {'kafka', 'filebeat', 'nifi', 'elasticsearch', 'kibana', 'scoring-api'}
    for name, service in services.items():
        for port in service.get('ports', []):
            assert port['host_ip'] == (bind if name == 'nifi' else '127.0.0.1'), (name, port)
    nifi = services['nifi']
    assert nifi['image'] == 'apache/nifi:1.25.0'
    assert nifi['environment']['NIFI_WEB_PROXY_HOST'] == hosts
    assert str(nifi['environment']['NIFI_WEB_HTTPS_PORT']) == '8443'
    assert nifi['environment']['SINGLE_USER_CREDENTIALS_PASSWORD'] == ENV['CNC_NIFI_PASSWORD']
    assert 'NIFI_WEB_HTTP_PORT' not in nifi['environment']
    assert nifi['ports'][0]['target'] == 8443
    assert services['scoring-api']['build']['context'] == str(COMPOSE.parent / 'scoring')
    mounts = services['scoring-api']['volumes']
    assert any(v['source'] == str(ROOT / 'models') and v['read_only'] for v in mounts)
    assert not (ROOT / 'infra').exists(), 'Keep one canonical historical template'


if __name__ == '__main__':
    defaults = 'localhost:8443,127.0.0.1:8443'
    check({}, '127.0.0.1', defaults)
    check({'CNC_LAN_BIND_IP': '', 'CNC_NIFI_PROXY_HOST': ''}, '127.0.0.1', defaults)
    check({'CNC_LAN_BIND_IP': '192.0.2.10', 'CNC_NIFI_PROXY_HOST': '192.0.2.10:8443'},
          '192.0.2.10', '192.0.2.10:8443')
    check({'CNC_LAN_BIND_IP': '192.0.2.10', 'CNC_NIFI_PROXY_HOST': 'cnc-lab.example:8443'},
          '192.0.2.10', 'cnc-lab.example:8443')
    for key in ('CNC_NIFI_PASSWORD', 'CNC_STREAM_DIR'):
        for result in (render(missing=key), render({key: ''})):
            assert result.returncode != 0 and key in result.stderr, key
    print('PASS: defaults, empty defaults, LAN IP/DNS, private ports, auth, paths, required variables')
