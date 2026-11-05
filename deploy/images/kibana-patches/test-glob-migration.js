// Exercise the package's main entrypoints: 14.0.2's minified main was still unsafe.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const { createRequire } = require('node:module');
const { pathToFileURL } = require('node:url');
const root = path.resolve(process.argv[2] || '/usr/share/kibana/node_modules');
const localRequire = createRequire(path.join(root, 'package.json'));
const fixture = fs.mkdtempSync(path.join(os.tmpdir(), 'cnc-glob-regression-'));
const delay = ms => new Promise(resolve => setTimeout(resolve, ms));

async function check(glob, rimraf) {
  const nested = path.join(fixture, 'a/b');
  fs.mkdirSync(nested, { recursive: true });
  fs.writeFileSync(path.join(nested, 'remove.tmp'), 'owned fixture');
  fs.writeFileSync(path.join(nested, 'keep.txt'), 'owned fixture');
  assert.deepEqual(glob.globSync('**/*.tmp', { cwd: fixture }), ['a/b/remove.tmp']);
  assert.equal(await rimraf.rimraf(path.join(fixture, '**/*.tmp'), { glob: true }), true);
  assert.equal(fs.existsSync(path.join(nested, 'keep.txt')), true);
  assert.equal(fs.existsSync(path.join(nested, 'remove.tmp')), false);
  fs.writeFileSync(path.join(nested, 'remove.tmp'), 'owned fixture');
  assert.equal(rimraf.rimrafSync(path.join(fixture, '**/*.tmp'), { glob: true }), true);
  assert.equal(fs.existsSync(path.join(nested, 'remove.tmp')), false);
  const plain = path.join(fixture, 'plain');
  fs.mkdirSync(plain);
  assert.equal(await rimraf.rimraf(plain), true);
  const aborted = new AbortController();
  const reason = new Error('expected cancellation');
  aborted.abort(reason);
  await assert.rejects(rimraf.rimraf(path.join(fixture, '**'), { glob: true, signal: aborted.signal }), error => error === reason);
  assert.equal(fs.existsSync(path.join(nested, 'keep.txt')), true);
  // Observe actual filesystem reads after abort, rather than only rejection.
  const controller = new AbortController();
  let reads = 0;
  const counted = { ...fs, readdir(...args) {
    if (++reads === 1) controller.abort(reason);
    return fs.readdir(...args);
  } };
  await assert.rejects(glob.glob('**', { cwd: fixture, signal: controller.signal, fs: counted }), error => error === reason);
  const atRejection = reads;
  await delay(120);
  assert.ok(atRejection > 0);
  assert.equal(reads, atRejection);
  // Minified main must include the Minimatch bound, not merely ./raw.
  const amplified = new glob.Glob(Array(30).fill('**/../a/b').join('/'), { cwd: fixture });
  assert.equal(amplified.patterns.length, 10000);
  // Both Glob 10 and 14 include cwd for this pattern; preserve that result shape.
  assert.deepEqual(new Set(glob.globSync('**', { cwd: fixture, ignore: '**/*.txt' })), new Set(['.', 'a', 'a/b']));
}

(async () => {
  try {
    assert.equal(localRequire('glob/package.json').version, '14.0.3');
    assert.equal(localRequire('rimraf/package.json').version, '6.1.4');
    const modes = [
      ['commonjs', localRequire('glob'), localRequire('rimraf')],
      ['esm', await import(pathToFileURL(path.join(root, 'glob/dist/esm/index.min.js'))),
        await import(pathToFileURL(path.join(root, 'rimraf/dist/esm/index.js')))],
    ];
    for (const [mode, glob, rimraf] of modes) {
      await check(glob, rimraf);
      console.log(mode + ': main-entry glob limits, cancellation, rimraf and globSync consumer controls passed');
    }
  } finally { fs.rmSync(fixture, { recursive: true, force: true }); }
})().catch(error => { console.error(error); process.exitCode = 1; });
