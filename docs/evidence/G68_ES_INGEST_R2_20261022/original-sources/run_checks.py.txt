"""Own gates: exact commands, output and exit codes; no ML invocation."""
import hashlib
import json
import os
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

OUT = Path(__file__).resolve().parent
ROOT = Path('D:/github/_worktrees/t2-es-ingest-20261022')
PY = Path('D:/github/_local/t2-babysit-20261021/es-ingest-20261022/venv/Scripts/python.exe')
assert PY.is_file()
env = os.environ.copy()
for name in ('temp', 'cache/uv', 'cache/ruff', 'tools', 'tools/bin'):
    (OUT / name).mkdir(parents=True, exist_ok=True)
env.update({k: str(OUT / 'temp') for k in ('TMP', 'TEMP', 'TMPDIR')})
env.update(PYTHONDONTWRITEBYTECODE='1', PYTHONPATH='.;tests',
           UV_CACHE_DIR=str(OUT / 'cache/uv'), RUFF_CACHE_DIR=str(OUT / 'cache/ruff'),
           UV_TOOL_DIR='D:/github/_local/t2-babysit-20261021/es-ingest-20261022/tools',
           UV_TOOL_BIN_DIR=str(OUT / 'tools/bin'),
           UV_PROJECT_ENVIRONMENT=str(PY.parent.parent),
           UV_PYTHON_INSTALL_DIR=str(OUT / 'python'))
attempt = OUT / sys.argv[1]
attempt.mkdir(exist_ok=False)
results = []
def run(name, args, timeout=240):
    args = list(map(str, args))
    start = datetime.now(UTC).isoformat()
    executed_hash = hashlib.sha256((ROOT / 'tests/verify_elasticsearch_contract.py').read_bytes()).hexdigest()
    p = subprocess.run(args, cwd=ROOT, env=env, capture_output=True, text=True,
                       encoding='utf-8', errors='replace', timeout=timeout)
    log = attempt / (name + '.log')
    log.write_text(p.stdout + '\nSTDERR:\n' + p.stderr, encoding='utf-8')
    results.append(dict(name=name, command=args, started_at=start, exit_code=p.returncode,
                        log=log.name, sha256=hashlib.sha256(log.read_bytes()).hexdigest(),
                        contract_verifier_sha256_at_start=executed_hash))
    (attempt / 'results.json').write_text(json.dumps(results, indent=2)+'\n', encoding='utf-8')
    print(name, 'exit', p.returncode, flush=True)
    if p.returncode:
        print(p.stdout[-4000:] + p.stderr[-4000:], flush=True)
    return p.returncode

if sys.argv[1] == 'contract-exact-final':
    run('es-contract', [PY, '-B', 'tests/verify_elasticsearch_contract.py', '--work-dir',
                        OUT / 'contract-exact-final-lab', '--output', attempt / 'contract.json',
                        '--docker-via-wsl', 'FedoraLinux-43'])
elif sys.argv[1] == 'setup-and-contract-final':
    run('build-setup', [PY, '-B', OUT / 'build_setup.py'])
    run('documented-setup', [PY, '-B', OUT / 'documented_setup.py'])
    run('es-contract', [PY, '-B', 'tests/verify_elasticsearch_contract.py', '--work-dir',
                        OUT / 'contract-final-lab', '--output', attempt / 'contract.json',
                        '--docker-via-wsl', 'FedoraLinux-43'])
elif sys.argv[1].startswith('live'):
    run('es-contract', [PY, '-B', 'tests/verify_elasticsearch_contract.py', '--work-dir',
                        OUT / (sys.argv[1] + '-contract'), '--output', attempt / 'contract.json',
                        '--docker-via-wsl', 'FedoraLinux-43'])
    run('es-ingest', [PY, '-B', 'tests/verify_es_ingest_pipeline.py', '--work-dir',
                      OUT / (sys.argv[1] + '-ingest'), '--docker-via-wsl', 'FedoraLinux-43'])
else:
    changed = ['scripts/build_es_ingest_pipeline.py', 'tests/test_es_ingest_pipeline.py',
               'tests/verify_es_ingest_pipeline.py', 'tests/verify_elasticsearch_contract.py',
               'tests/verify_durable_pipeline.py']
    run('python', [PY, '--version'])
    run('export', [PY, '-B', '-m', 'scripts.build_es_ingest_pipeline', '--check'])
    run('contracts', [PY, '-B', '-W', 'error::ResourceWarning', '-m', 'unittest', '-v',
        'test_es_ingest_pipeline', 'test_contract_validation',
        'test_elasticsearch_contract.ElasticsearchContractTests.test_entire_prediction_contract_has_explicit_compatible_mappings'])
    run('ruff-version', ['ruff', '--version'])
    run('ruff-check', ['ruff', 'check', '--select', 'E,F,I,PLW1510'] + changed)
    run('ruff-format', ['ruff', 'format', '--check'] + changed)
    run('CG02', [PY, '-B', '-m', 'scripts.audit_cg02', '--check'])
    run('CG25', [PY, '-B', '-m', 'scripts.check_cg25_memory'])
    run('layout', [PY, '-B', 'scripts/check_repository_layout.py'])
    uv = ['uv', 'tool', 'run', '--from', 'uv==0.13.1', 'uv']
    run('uv-version', uv + ['--version'])
    run('lock', uv + ['lock', '--check', '--offline'])
    run('audit', uv + ['audit', '--locked'])
    run('diff', ['git', 'diff', '--check', 'cc36beb49a17949c805f789b5aa3b4b568f5d4c6'])
raise SystemExit(any(r['exit_code'] for r in results))
