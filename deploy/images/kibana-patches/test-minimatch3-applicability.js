// Bounded proof for this exact installed file and this advisory's mechanism.
// This script does not authorize a scanner exception or claim all patterns safe.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const crypto = require('node:crypto');
const { createRequire } = require('node:module');
const root = path.resolve(process.argv[2] || '/usr/share/kibana/node_modules');
const delRequire = createRequire(path.join(root, 'del/index.js'));
const target = delRequire.resolve('minimatch');
assert.equal(target, path.join(root, 'del/node_modules/minimatch/minimatch.js'));
assert.equal(delRequire('minimatch/package.json').version, '3.1.5');
const bytes = fs.readFileSync(target);
assert.equal(crypto.createHash('sha256').update(bytes).digest('hex'), '746849f267c4868a53729225bd85c7dccd387712136fb305fcc0a3eadd4a3d9d');
const source = bytes.toString('utf8');
for (const symbol of ['firstPhasePreProcess', 'secondPhasePreProcess', 'optimizationLevel', 'globParts.push', 'partsMatch']) {
  assert.equal(source.includes(symbol), false, symbol);
}
const minimatch = delRequire('minimatch');
const { Minimatch } = minimatch;
assert.equal(typeof minimatch, 'function');
assert.equal(new Minimatch(Array(30).fill('**/../a/b').join('/'), { optimizationLevel: 2 }).set.length, 1);
let seed = 0xA11CE;
const random = limit => { seed = (Math.imul(seed, 1664525) + 1013904223) >>> 0; return seed % limit; };
const atoms = ['a', 'b', '**', '..', '.', '*', '?', '[ab]', '{a,b}', '{1..3}'];
for (let i = 0; i < 2048; i++) {
  const pattern = Array.from({ length: 1 + random(6) }, () => atoms[random(atoms.length)]).join('/');
  const mm = new Minimatch(pattern, { optimizationLevel: 2 });
  assert.deepEqual(mm.globParts, mm.globSet.map(part => part.split(/\/+/)));
}

(async () => {
  const fixture = fs.mkdtempSync(path.join(os.tmpdir(), 'cnc-minimatch3-proof-'));
  const originalCwd = process.cwd();
  const originalMake = Minimatch.prototype.make;
  let calls = 0;
  Minimatch.prototype.make = function (...args) { calls++; return originalMake.apply(this, args); };
  try {
    const del = require(path.join(root, 'del'));
    fs.writeFileSync(path.join(fixture, 'one.tmp'), 'owned fixture');
    fs.writeFileSync(path.join(fixture, 'keep.txt'), 'owned fixture');
    assert.equal((await del('*.tmp', { cwd: fixture, dryRun: true })).length, 1);
    assert.equal(del.sync('*.tmp', { cwd: fixture, dryRun: true }).length, 1);
    await del(Array(30).fill('**/../a/b').join('/'), { cwd: fixture, dryRun: true });
    await del('*.tmp', { cwd: fixture });
    assert.equal(fs.existsSync(path.join(fixture, 'one.tmp')), false);
    assert.equal(fs.existsSync(path.join(fixture, 'keep.txt')), true);
    assert.equal(calls, 0);
    fs.writeFileSync(path.join(fixture, 'control.tmp'), 'owned fixture');
    process.chdir(fixture);
    delRequire('rimraf').sync('*.tmp');
    assert.ok(calls > 0, 'positive control must detect active Glob 7 compilation');
    console.log(JSON.stringify({ version: '3.1.5', propertyCases: 2048, delCompilations: 0, positiveControlCompilations: calls, node: process.version }));
  } finally {
    process.chdir(originalCwd);
    Minimatch.prototype.make = originalMake;
    fs.rmSync(fixture, { recursive: true, force: true });
  }
})().catch(error => { console.error(error); process.exitCode = 1; });
