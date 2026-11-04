# Reproducing the Glob/Minimatch evidence

These drivers were added **after** review of `f80c37f`. They make the checks
repeatable; they are not the missing contemporaneous driver files or scope
attestation for the earlier executions. Original artifacts remain unchanged.
Use fresh output files when repeating scans or probes.

The original and patched package directories used below are:

```text
/home/tears/.cache/cnc-kibana-major-research-20261104/fixture/node_modules/mm10
/home/tears/.cache/cnc-kibana-image-20261104/patch-preparation/node_modules/minimatch-v10
```

They are inputs, not recreated by these commands. The first must contain the
official 10.2.4 package and its dependencies; the second is the pinned npm
installation plus `apply-minimatch-patch.js`. Both must be independently prepared
and verified before using this recipe on a different machine. The drivers use
the host Node; record `node --version`. The review's separate differential used
the image's Node 24.21.0.

## Ordinary-match differential

Save the following as `differential.js` in a fresh evidence directory. Invoke
`node --max-old-space-size=256 differential.js ORIGINAL PATCHED` and retain its
source hash, command, exit status and output. It compares 2,000 patterns at
levels 1 and 2 against 24 paths. This is a seeded corpus, not exhaustive fuzzing.

```javascript
const assert = require('node:assert/strict');
const path = require('node:path');
const original = path.resolve(process.argv[2]);
const patched = path.resolve(process.argv[3]);
assert.equal(require(path.join(original, 'package.json')).version, '10.2.4');
assert.equal(require(path.join(patched, 'package.json')).version, '10.2.4+cncguard.1');
const O = require(original).Minimatch;
const P = require(patched).Minimatch;
let seed = 0xA11CE;
const random = n => { seed = (Math.imul(seed, 1664525) + 1013904223) >>> 0; return seed % n; };
const atoms = ['**', '..', '.', 'a', 'b', '*', '?', 'x*', '{a,b}', '{1..3}', '[ab]'];
const segments = ['a', 'b', 'x', '.h', '..', '1', '2'];
const paths = Array.from({ length: 24 }, () => Array.from({ length: 1 + random(6) }, () => segments[random(segments.length)]).join('/'));
for (let i = 0; i < 2000; i++) {
  const pattern = Array.from({ length: 1 + random(8) }, () => atoms[random(atoms.length)]).join('/');
  for (const optimizationLevel of [1, 2]) {
    const a = new O(pattern, { optimizationLevel });
    const b = new P(pattern, { optimizationLevel });
    assert.deepEqual(b.globParts, a.globParts, pattern);
    for (const file of paths) assert.equal(b.match(file), a.match(file), pattern + ' ' + file);
  }
}
console.log(JSON.stringify({ node: process.version, seed: '0xA11CE', patterns: 2000, levels: [1, 2], paths: 24, comparisons: 96000, differences: 0 }));
```

## Patch guards

Save the following as `guards.py` beside that driver. Invoke
`python guards.py REPOSITORY ORIGINAL PATCHED`. It clones inputs to an owned
temporary directory; the supplied package directories are never modified.

```python
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

repository, original, patched = map(lambda value: Path(value).resolve(), sys.argv[1:])
script = repository / 'deploy/images/kibana-patches/apply-minimatch-patch.js'
files = ['package.json', 'dist/commonjs/index.js', 'dist/esm/index.js']

def hashes(root):
    return {name: hashlib.sha256((root / name).read_bytes()).hexdigest() for name in files}

with tempfile.TemporaryDirectory(prefix='cnc-minimatch-guards-') as temporary:
    root = Path(temporary)
    mutated = root / 'mutated'
    shutil.copytree(original, mutated)
    target = mutated / 'dist/esm/index.js'
    target.write_bytes(target.read_bytes() + b'\n// changed input\n')
    before = hashes(mutated)
    result = subprocess.run(['node', '--max-old-space-size=256', str(script), str(mutated)], capture_output=True, text=True, timeout=10)
    assert result.returncode and 'unexpected source hash: dist/esm/index.js' in result.stderr
    assert hashes(mutated) == before
    repeated = root / 'repeated'
    shutil.copytree(patched, repeated)
    before = hashes(repeated)
    result = subprocess.run(['node', '--max-old-space-size=256', str(script), str(repeated)], capture_output=True, text=True, timeout=10)
    assert result.returncode and 'expected unmodified minimatch 10.2.4' in result.stderr
    assert hashes(repeated) == before
print(json.dumps({'mutated_second_format_rejected_before_writes': True, 'double_application_rejected_without_changes': True}))
```

## Scan invocation and local artifact identity

The parent invocation used Trivy 0.76.1 with these arguments, inside a user
`systemd-run --scope` configured with `MemoryMax=512M` and `CPUQuota=100%`:

```text
trivy image --image-src docker --parallel 1 --scanners vuln --format json
  --list-all-pkgs --skip-db-update --offline-scan
  --output FRESH_OUTPUT.json cnc-guard-local:kibana-glob-candidate
```

This reconstructs the command from the parent invocation. The historical logs
do not retain the command or the live scope properties. A future rerun should
save both, plus the scanner version, DB metadata and inspected Docker image ID.
Do not treat this retrospective note as verification of the old memory limit.
`candidate-scan.log` records only the failed first attempt to reach the user bus;
`candidate-scan-v2.log` belongs to the successful scanner execution.

For this **local** image name, the recorded gate check is the following Python
call. CI uses its own expected artifact name; its CLI identity check is unchanged.

```python
import json
from scripts.enforce_image_scan import validate
with open('/home/tears/.cache/cnc-kibana-image-20261104/candidate-scan.json') as stream:
    report = json.load(stream)
errors = validate('kibana', report, expected_artifact='cnc-guard-local:kibana-glob-candidate')
assert len(errors) == 2 and all('minimatch' in error for error in errors)
print('\n'.join(errors))
```

The local override binds the check to the actual local artifact name. It does
not permit either remaining finding and does not change scanner policy.
