'use strict';
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const Module = require('node:module');
const { pathToFileURL } = require('node:url');
const root = '/usr/share/kibana/node_modules';
const sourceFile = `${root}/del/index.js`;
const old = require(sourceFile);
const patched = process.argv[2];
let candidate;
if (patched) {
  const filename = path.join(patched, 'index.js');
  const m = new Module(filename);
  // Model removal of the legacy nested directory; keep the installed root deps.
  m.filename = filename; m.paths = [root];
  assert.equal(m.require('rimraf/package.json').version, '6.1.4');
  m._compile(fs.readFileSync(filename, 'utf8'), filename);
  candidate = m.exports;
} else {
  candidate = old;
  assert.equal(require(`${root}/del/package.json`).version, '6.1.1+cncguard.1');
  assert(!fs.existsSync(`${root}/del/node_modules`));
  assert.equal(typeof candidate.sync, 'function');
  const copies = [];
  function walk(directory) {
    for (const entry of fs.readdirSync(directory, { withFileTypes: true })) {
      const file = path.join(directory, entry.name);
      assert(!entry.isSymbolicLink(), `unreviewed installed symlink: ${file}`);
      if (entry.isDirectory()) walk(file);
      else if (entry.name === 'package.json') {
        const metadata = JSON.parse(fs.readFileSync(file));
        if (['rimraf', 'glob', 'minimatch'].includes(metadata.name)) {
          copies.push({ file, name: metadata.name, version: metadata.version });
          assert(!(metadata.name === 'rimraf' && metadata.version.startsWith('3.')));
          assert(!(metadata.name === 'glob' && metadata.version.startsWith('7.')));
          assert(!(metadata.name === 'minimatch' && metadata.version.startsWith('3.')));
        }
      }
    }
  }
  walk(root);
  assert.equal(require(`${root}/minimatch/package.json`).version, '10.2.4+cncguard.1');
  assert.equal(require(`${root}/rimraf/package.json`).version, '6.1.4');
  console.error(JSON.stringify({ installedCopies: copies }));
}
const records = [];
let serial = 0;
const fresh = () => fs.mkdtempSync('/tmp/cnc-del-');
function configure(target, operation, code, count) {
  const log = path.join(path.dirname(target), `trace-${++serial}`);
  Object.assign(process.env, { CNC_DEL_TARGET: target, CNC_DEL_OPERATION: operation,
    CNC_DEL_ERRNO: String(os.constants.errno[code] || 0), CNC_DEL_COUNT: String(count),
    CNC_DEL_GENERATION: String(serial), CNC_DEL_LOG: log });
  return () => fs.existsSync(log) ? fs.readFileSync(log, 'utf8').trim().split('\n') : [];
}
function disable() { delete process.env.CNC_DEL_TARGET; }
async function normal(del, label) {
  const cwd = fresh(), outside = fresh();
  fs.mkdirSync(`${cwd}/dir`); fs.writeFileSync(`${cwd}/dir/a`, 'owned');
  fs.writeFileSync(`${cwd}/keep`, 'owned'); fs.writeFileSync(`${outside}/sentinel`, 'owned');
  fs.symlinkSync(outside, `${cwd}/link`);
  const progress = [];
  const dry = await del(['dir', 'link'], { cwd, dryRun: true, concurrency: 1, onProgress: p => progress.push(p) });
  assert.deepEqual(dry.map(f => path.basename(f)), ['dir', 'link']);
  assert(fs.existsSync(`${cwd}/dir/a`));
  assert.equal(progress.length, 2); assert.equal(progress.at(-1).percent, 1);
  assert.deepEqual((await del(['dir', 'link'], { cwd })).map(f => path.basename(f)), ['dir', 'link']);
  assert(fs.existsSync(`${outside}/sentinel`)); assert(fs.existsSync(`${cwd}/keep`));
  assert.deepEqual(await del('absent', { cwd }), []);
  const emptyProgress = [];
  await del('absent', { cwd, onProgress: p => emptyProgress.push(p) });
  assert.deepEqual(emptyProgress, [{ totalCount: 0, deletedCount: 0, percent: 1 }]);
  await assert.rejects(del(`${outside}/sentinel`, { cwd }), /outside/);
  assert.throws(() => del.sync(`${outside}/sentinel`, { cwd }), /outside/);
  assert.equal((await del(`${outside}/sentinel`, { cwd, force: true })).length, 1);
  const previous = process.cwd(); process.chdir(cwd);
  try {
    await assert.rejects(del('.', { cwd }), /current working directory/);
    assert.throws(() => del.sync('.', { cwd }), /current working directory/);
  } finally { process.chdir(previous); }
  fs.writeFileSync(`${cwd}/sync`, 'owned');
  assert.equal(del.sync('sync', { cwd, dryRun: true }).length, 1);
  assert(fs.existsSync(`${cwd}/sync`));
  assert.equal(del.sync('sync', { cwd }).length, 1);
  assert.deepEqual(del.sync('absent', { cwd }), []);
  const failure = new Error('progress callback failure');
  fs.writeFileSync(`${cwd}/callback`, 'owned');
  await assert.rejects(del('callback', { cwd, onProgress() { throw failure; } }), e => e === failure);
  assert(!fs.existsSync(`${cwd}/callback`));
  await assert.rejects(del('absent', { cwd, onProgress() { throw failure; } }), e => e === failure);
  const observed = new Promise(resolve => process.once('unhandledRejection', resolve));
  await del('absent', { cwd, onProgress() { return Promise.reject(failure); } });
  assert.equal(await observed, failure); // Original del does not await callbacks.
  fs.writeFileSync(`${cwd}/sync-progress`, 'owned');
  assert.equal(del.sync('sync-progress', { cwd, onProgress() { throw failure; } }).length, 1);
  fs.writeFileSync(`${cwd}/dry-fault`, 'owned');
  const dryTrace = configure(`${cwd}/dry-fault`, 'unlink', 'ENFILE', -1);
  assert.equal((await del('dry-fault', { cwd, dryRun: true })).length, 1);
  assert.equal(del.sync('dry-fault', { cwd, dryRun: true }).length, 1);
  disable(); assert.equal(dryTrace().length, 0);
  fs.writeFileSync(`${cwd}/race-a`, 'owned'); fs.writeFileSync(`${cwd}/race-b`, 'owned');
  const raced = await del(['race-a', 'race-b'], { cwd, concurrency: 1, onProgress(p) {
    if (p.deletedCount === 1) fs.unlinkSync(`${cwd}/race-a`);
  } });
  assert.equal(raced.length, 2); // ENOENT after enumeration stays tolerated.
  await assert.rejects(del({}, { cwd }), /pattern|Patterns|arguments/i);
  records.push({ label, normal: true });
}
async function syscalls(del, label, sync) {
  for (const operation of ['unlink', 'rmdir']) for (const code of ['EACCES', 'EPERM', 'EBUSY', 'EMFILE', 'ENFILE', 'ENOTEMPTY']) {
    // Old graceful-fs queues descriptor failures for up to 60s: use finite
    // recovery here; its terminal policy is checked at its callback boundary below.
    const counts = label === 'old' && ['EMFILE', 'ENFILE'].includes(code) && !sync ? [2] : [2, -1];
    for (const count of counts) {
      const cwd = fresh(), target = `${cwd}/victim`;
      if (operation === 'rmdir') fs.mkdirSync(target); else fs.writeFileSync(target, 'owned');
      const trace = configure(target, operation, code, count);
      let error;
      try {
        if (sync) del.sync('victim', { cwd }); else await del('victim', { cwd });
      } catch (e) { error = e; }
      disable();
      const attempts = trace();
      assert(attempts.length > 0, `syscall shim was not reached: ${label}/${sync}/${operation}/${code}`);
      if (label === 'new') {
        if (code === 'EACCES') {
          assert.equal(error?.code, code); assert(fs.existsSync(target));
          assert.equal(attempts.length, 1);
        } else if (count === 2) {
          assert(!error, `${code} should recover: ${error}`);
          assert(!fs.existsSync(target));
        } else {
          assert.equal(error?.code, code); assert(fs.existsSync(target));
          const expected = !sync && operation === 'rmdir' && ['EPERM', 'ENOTEMPTY'].includes(code) ? 8 : 4;
          assert.equal(attempts.length, expected);
        }
        assert(attempts.length <= 12, 'retry bound exceeded');
      }
      records.push({ label, sync, operation, code, count, attempts: attempts.length,
        error: error && { code: error.code, syscall: error.syscall }, exists: fs.existsSync(target) });
    }
  }
}
async function oldCallbackTerminals() {
  if (!patched) return;
  // Inject at the exact callback functions del supplies to Rimraf3, bypassing
  // graceful-fs's separately tested native queue. Virtual timers avoid long waits.
  const graceful = require(`${root}/graceful-fs`), realSetTimeout = global.setTimeout;
  const originalUnlink = graceful.unlink;
  const realDate = Date.now;
  try {
    global.setTimeout = (fn, ms, ...args) => setImmediate(fn, ...args);
    for (const code of ['EMFILE', 'ENFILE', 'EACCES', 'EBUSY']) {
      const cwd = fresh(), target = `${cwd}/victim`; fs.writeFileSync(target, 'owned');
      let attempts = 0;
      graceful.unlink = (file, callback) => { attempts++; queueMicrotask(() => callback(Object.assign(new Error('injected'), { code, path: file, syscall: 'unlink' }))); };
      delete require.cache[sourceFile];
      const isolated = require(sourceFile);
      await assert.rejects(isolated('victim', { cwd }), e => e.code === code);
      assert(attempts <= 1001);
      records.push({ label: 'old-callback-boundary', code, attempts, virtualTimers: true });
    }
  } finally { graceful.unlink = originalUnlink; global.setTimeout = realSetTimeout; Date.now = realDate; }
}
async function main() {
  assert.equal(process.version, 'v24.21.0');
  if (patched) await normal(old, 'old');
  await normal(candidate, 'new');
  assert.equal((await import(pathToFileURL(sourceFile))).default.sync instanceof Function, true);
  // The shim is opt-in: final-image normal tests need no compiler/preload.
  if (process.env.LD_PRELOAD) {
    const cwd = fresh(), target = `${cwd}/native`;
    fs.writeFileSync(target, 'owned');
    const trace = configure(target, 'unlink', 'EBUSY', -1);
    let nativeError;
    try { fs.rmSync(target, { recursive: true, force: true, maxRetries: 3, retryDelay: 100 }); }
    catch (error) { nativeError = error; }
    disable();
    assert.equal(trace().length, 4);
    assert.equal(nativeError.code, ''); assert.equal(nativeError.errno, -4094);
    records.push({ label: 'rejected-native-sync-control', code: nativeError.code,
      errno: nativeError.errno, attempts: trace().length });
    if (patched) { await syscalls(old, 'old', false); await syscalls(old, 'old', true); }
    await syscalls(candidate, 'new', false); await syscalls(candidate, 'new', true);
    await oldCallbackTerminals();
  }
  console.log(JSON.stringify({ node: process.version, records }, null, 2));
}
main().catch(error => { disable(); console.error(error); process.exitCode = 1; });
