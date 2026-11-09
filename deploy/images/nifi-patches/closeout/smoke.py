"""Capture cold API evidence from an owned NiFi container, with daemon identity."""
import argparse
import hashlib
import json
import subprocess
from pathlib import Path

TYPE_KEYS = ('processorTypes', 'controllerServiceTypes', 'reportingTaskTypes',
             'parameterProviderTypes', 'flowRegistryClientTypes')


def flow_contract(captures, flow_root):
    """Compare declared modern flow types/bundles to the actual live registry."""
    available = set()
    for payload in captures.values():
        for key in TYPE_KEYS:
            for row in payload.get(key, []):
                for declaration in [row, *row.get('controllerServiceApis', [])]:
                    bundle = declaration['bundle']
                    available.add((declaration['type'], bundle['group'], bundle['artifact'], bundle['version']))
    required = set()

    def visit(value):
        if isinstance(value, dict):
            bundle = value.get('bundle')
            if isinstance(bundle, dict) and bundle.get('version') == '2.12.0' and 'type' in value:
                required.add((value['type'], bundle['group'], bundle['artifact'], bundle['version']))
            for child in value.values():
                visit(child)
        elif isinstance(value, list):
            for child in value:
                visit(child)

    sources = sorted(Path(flow_root).glob('*.json'))
    if not sources:
        raise ValueError('no declared flow sources')
    for path in sources:
        visit(json.loads(path.read_text(encoding='utf-8')))
    if not required:
        raise ValueError('no modern declared component requirements')
    return {'required': sorted(required), 'missing': sorted(required - available),
            'source_sha256': {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sources},
            'scope': 'live type registration only; no scheduling or persisted-state restoration'}


def run(args, **kwargs):
    return subprocess.run(['docker', *args], check=True, capture_output=True,
                          text=True, timeout=180, **kwargs).stdout


def capture(container, output):
    if not container.startswith('cnc-closeout-nifi-'):
        raise ValueError('only explicitly owned cnc-closeout-nifi containers are permitted')
    output = Path(output)
    if output.exists():
        raise ValueError('output must be a fresh directory')
    before = json.loads(run(['inspect', container]))[0]
    if not before['State']['Running'] or before['HostConfig']['NetworkMode'] != 'none':
        raise ValueError('smoke requires a running network-isolated container')
    daemon = json.loads(run(['info', '--format', '{{json .}}']))
    source = Path(__file__).with_name('api_probe.py').read_bytes()
    evidence = json.loads(run(['exec', '-i', container, 'python3', '-'], input=source.decode()))
    after = json.loads(run(['inspect', container]))[0]
    if before['Id'] != after['Id'] or before['Image'] != after['Image'] or not after['State']['Running']:
        raise ValueError('container identity/state changed during smoke')
    evidence['identity'] = {
        'daemon_id': daemon['ID'], 'daemon_name': daemon['Name'],
        'daemon_memory_bytes': daemon['MemTotal'], 'container_id': before['Id'],
        'image_config_id': before['Image'], 'probe_sha256': hashlib.sha256(source).hexdigest(),
        'memory_limit_bytes': before['HostConfig']['Memory'],
        'nano_cpus': before['HostConfig']['NanoCpus'],
        'network': before['HostConfig']['NetworkMode'],
    }
    if evidence['cold_api_smoke_passed']:
        repository = Path(__file__).resolve().parents[4]
        evidence['declared_flow_contract'] = flow_contract(evidence['captures'], repository / 'nifi-flows')
        evidence['cold_api_smoke_passed'] = not evidence['declared_flow_contract']['missing']
    output.mkdir(parents=True)
    (output / 'cold-api-smoke.json').write_text(json.dumps(evidence, indent=2) + '\n')
    return evidence


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--container', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = capture(args.container, args.output)
    print(json.dumps({'checks': result['checks'], 'identity': result['identity'],
                      'cold_api_smoke_passed': result['cold_api_smoke_passed']}))
    return 0 if result['cold_api_smoke_passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
