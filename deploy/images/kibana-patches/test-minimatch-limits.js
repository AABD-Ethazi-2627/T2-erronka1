// Official preprocessing-limit regressions, plus Fleet's required makeRe API.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { pathToFileURL } = require('node:url');
const root = path.resolve(process.argv[2] || '/usr/share/kibana/node_modules/minimatch');

function check(Minimatch) {
  const options = { optimizationLevel: 2 };
  const largePattern = Array(30).fill('**/../a/b').join('/');
  // Small enough to fail safely on the original implementation (256 vs 64).
  const probe = Array(8).fill('**/../a/b').join('/');
  assert.equal(new Minimatch(probe, { ...options, braceExpandMax: 64 }).set.length, 64);
  const below = new Minimatch('**/../a/b/**/../c/d', options);
  assert.equal(below.set.length, 4);
  assert.equal(below.match('../a/b/../c/d'), true);
  assert.equal(below.match('x/a/b/y/c/d'), true);
  assert.equal(new Minimatch('{x,*}/{0..9}', options).set.length, 10);
  const large = new Minimatch('{x,*}/{0..999}', options);
  assert.equal(large.set.length, 2000);
  assert.equal(large.match('x/5'), true);
  assert.equal(large.match('y/999'), true);
  assert.equal(large.match('.y/5'), false);
  // Directly exercise the official default without constructing 100000 regexes.
  const normal = new Minimatch('package-*/manifest.yml');
  const expanded = normal.firstPhasePreProcess([largePattern.split('/')]);
  assert.equal(expanded.length, 100000);
  normal.partsMatch = () => { throw new Error('quadratic comparison must be skipped'); };
  const parts = Array.from({ length: 1001 }, (_, i) => [String(i)]);
  assert.equal(normal.secondPhasePreProcess(parts), parts);
  // Fleet uses this method, removed upstream in Minimatch 11.
  const fleet = new Minimatch('package-*/manifest.yml');
  const regex = fleet.makeRe();
  assert.ok(regex instanceof RegExp);
  assert.equal(regex.test('package-one/manifest.yml'), true);
  assert.equal(regex.test('other/manifest.yml'), false);
}

(async () => {
  const metadata = JSON.parse(fs.readFileSync(path.join(root, 'package.json')));
  assert.equal(metadata.version, process.argv.includes('--unpatched-control') ? '10.2.4' : '10.2.4+cncguard.1');
  for (const mode of ['commonjs', 'esm']) {
    const file = path.join(root, 'dist', mode, 'index.js');
    const module = mode === 'commonjs' ? require(file) : await import(pathToFileURL(file));
    check(module.Minimatch);
    console.log(mode + ': official preprocessing limits and Fleet makeRe controls passed');
  }
})().catch(error => { console.error(error); process.exitCode = 1; });
