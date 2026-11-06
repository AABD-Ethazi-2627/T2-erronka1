"""Fail-closed experiment status and reproducible summary; never runtime approval."""
import argparse
import hashlib
import json
from pathlib import Path

PASSED = 'aligned-qualification-phases-passed-not-runtime-approval'
PHASE_STATUS = {
    'oracle': 'published-closure-equals-real-Maven',
    'static': 'aligned-symbolic-analysis-completed',
    'runtime': 'bounded-real-NarClassLoader-aligned-controls-passed',
}
METADATA = ('aligned-pins.json', 'aligned-result.json', 'narrow-result.json')


def require_preparation(record):
    if not isinstance(record, dict) or record.get('runtime_approved') is not False or 'replacement' not in record or record['replacement'] is not None:
        raise ValueError('metadata must retain replacement:null and runtime_approved:false')


def check_metadata(root):
    for name in METADATA:
        require_preparation(read_json(Path(root) / name)[0])


def read_json(path):
    if path.is_symlink() or not path.is_file():
        raise ValueError('missing or linked proof input: ' + str(path))
    raw = path.read_bytes()
    return json.loads(raw), hashlib.sha256(raw).hexdigest()


def finish_report(report):
    """Both the process status and the saved outcome must fail on any gap."""
    require_preparation(report)
    commands = report.get('commands', [])
    required = {'portable-guards', *PHASE_STATUS}
    valid = (report.get('status') == PASSED
             and len(commands) == len(required)
             and {c.get('phase') for c in commands} == required
             and all(type(c.get('returncode')) is int and c['returncode'] == 0 for c in commands)
             and report.get('image_identity_unchanged') is True
             and report.get('source_unchanged') is True
             and report.get('remaining_owned_containers') == []
             and not report.get('finalization_errors'))
    if not valid:
        report['status'] = 'blocked-aligned-qualification'
        report.setdefault('error', 'Incomplete phases, integrity verification or cleanup')
    return 0 if valid else 1


def seal_summary(proof, output):
    proof, output = Path(proof), Path(output)
    runner, runner_sha = read_json(proof / 'aligned-reserved-result.json')
    if finish_report(runner):
        raise ValueError('cannot seal blocked or incomplete qualification')
    phases, hashes = {}, {'aligned-reserved-result.json': runner_sha}
    for phase, expected in PHASE_STATUS.items():
        name = phase + '-result.json'
        data, digest = read_json(proof / name)
        require_preparation(data)
        if data.get('phase') != phase or data.get('status') != expected:
            raise ValueError('phase status does not demonstrate completion: ' + phase)
        phases[phase] = data
        hashes[name] = digest
    result = {'schema': 1, 'status': PASSED, 'replacement': None, 'runtime_approved': False,
              'scope': 'sealed phase reports, not full consumer, CVE, image or service acceptance',
              'phase_reports': phases, 'input_sha256': hashes}
    with output.open('x') as handle:
        handle.write(json.dumps(result, indent=2, sort_keys=True) + '\n')
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--proof', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    seal_summary(args.proof, args.output)


def finish_narrow_report(report, phases):
    require_preparation(report)
    commands = report.get('commands', [])
    completed = {c.get('phase') for c in commands if c.get('returncode') == 0}
    passed = (report.get('status') in {'bounded-component-qualification-phases-passed', 'bounded-requested-phase-passed'}
              and bool(phases) and set(phases) <= completed and 'unit-green' in completed
              and all(type(c.get('returncode')) is int and c['returncode'] == 0 for c in commands)
              and report.get('image_identity_unchanged') is True
              and report.get('source_unchanged') is True
              and report.get('remaining_owned_containers') == [])
    if not passed:
        report['status'] = 'qualification-blocked-or-failed'
    return 0 if passed else 1


if __name__ == "__main__":
    main()
