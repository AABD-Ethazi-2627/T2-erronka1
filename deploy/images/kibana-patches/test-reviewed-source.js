const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const assert = require('node:assert/strict');
const {spawnSync} = require('node:child_process');
const root = fs.mkdtempSync(path.join(os.tmpdir(), 'cnc-source-fixture-'));
try {
  const file = path.join(root, 'package.json');
  const workspace = path.join(root, 'pnpm-workspace.yaml');
  const original = JSON.stringify({version: '9.5.5', resolutions: {'follow-redirects': '1.16.1', 'node-forge': '1.4.0'}});
  fs.writeFileSync(file, original);
  fs.writeFileSync(workspace, "overrides:\n  'follow-redirects': '1.16.1'\n");
  const run = () => spawnSync(process.execPath, [path.join(__dirname, 'prepare-reviewed-source.js'), root]);
  assert.notEqual(run().status, 0);
  assert.equal(fs.readFileSync(file, 'utf8'), original, 'failure must not partially edit source');
  fs.appendFileSync(workspace, "  # END GENERATED OVERRIDES\n");
  assert.equal(run().status, 0);
  assert.equal(JSON.parse(fs.readFileSync(file)).resolutions['node-forge'], '1.4.1');
  assert.match(fs.readFileSync(workspace, 'utf8'), /'follow-redirects': '1.16.2'/);
  assert.equal(run().status, 0, 'preparation is idempotent');
} finally { fs.rmSync(root, {recursive: true}); }
console.log('source preparation: ambiguity fails before writes; pins and idempotence pass');
