'use strict';
// Diagnostic only: never loaded by the Dockerfile or by Kibana.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const Module = require('node:module');
const { createHash } = require('node:crypto');
const { pathToFileURL } = require('node:url');
const root = '/usr/share/kibana/node_modules';
const sha = s => createHash('sha256').update(s).digest('hex');
const old = require(`${root}/minimatch`);
const next = require('/next');
const options = { noglobstar: true, nonegate: true };

async function main() {
  assert.equal(process.version, 'v24.21.0');
  assert.equal(require(`${root}/minimatch/package.json`).version, '10.2.4+cncguard.1');
  assert.equal(require('/next/package.json').version, '11.0.4');
  const esm = await import(pathToFileURL('/next/dist/esm/index.js'));
  const source = fs.readFileSync(`${root}/@kbn/fleet-plugin/server/services/epm/packages/get.js`, 'utf8');
  assert.equal(sha(source), 'ea4352a9baed2ae7c635cfb11cbcb1e05e2b35e9264f8cae48b4bb749f9271e5');
  const start = source.indexOf('function getInstalledPackageSavedObjectDataStreams(');
  const end = source.indexOf('\nconst getInstallations =', start);
  assert(start > 0 && end > start);
  const body = source.slice(start, end);
  for (const literal of ['const patternRegex =', '}).makeRe();', 'dataStreamName.match(patternRegex)']) {
    assert.equal(body.split(literal).length, 2, literal);
  }
  const adapted = body.replace('const patternRegex =', 'const patternMatcher =')
    .replace('}).makeRe();', '});')
    .replace('dataStreamName.match(patternRegex)', 'patternMatcher.match(dataStreamName)');
  const compile = (code, mm) => vm.runInNewContext(`${code};getInstalledPackageSavedObjectDataStreams`, { _minimatch: mm });
  const original = compile(body, old);
  const migrated = compile(adapted, next);
  const migratedESM = compile(adapted, esm);
  const call = (fn, pattern, name) => JSON.parse(JSON.stringify(fn({ stream: pattern }, 'logs', [{ name }])));
  assert.throws(() => call(compile(body, next), 'logs-*-*', 'logs-a-default'), /makeRe is not a function/);
  const witness = { pattern: 'logs-!(a|b)*-default', name: 'logs-a-default' };
  assert.deepEqual(call(original, witness.pattern, witness.name), []);
  assert.equal(new old.Minimatch(witness.pattern, options).match(witness.name), false);
  for (const fn of [migrated, migratedESM]) {
    assert.deepEqual(call(fn, witness.pattern, witness.name), [{ name: witness.pattern, title: 'stream' }]);
    assert.deepEqual(call(fn, 'logs-*-*', witness.name), [{ name: 'logs-*-*', title: 'stream' }]);
    assert.deepEqual(call(fn, 'logs-z-*', witness.name), []);
    assert.deepEqual(call(fn, witness.pattern, 'logs-foo-default'), call(original, witness.pattern, 'logs-foo-default'));
  }

  // Bounded, seeded contract differential. Count differences, do not hide them.
  let seed = 0x119;
  const random = n => { seed = (Math.imul(seed, 1664525) + 1013904223) >>> 0; return (seed >>> 16) % n; };
  const atoms = ['a', 'b', '*', '?', '[ab]', '[!a]', '@(a|b)', '!(a|b)', '+(a|b)', '*(a|b)', '?(a|b)', '{a,b}', 'foo'];
  const names = ['a', 'b', 'aa', 'ab', 'ba', 'foo', 'foobar', 'foo.bar', 'x'];
  let comparisons = 0, differences = 0;
  const witnesses = [];
  for (let i = 0; i < 2000; i++) {
    const pattern = `logs-${Array.from({ length: 1 + random(4) }, () => atoms[random(atoms.length)]).join('')}-default`;
    for (const middle of names) {
      const name = `logs-${middle}-default`;
      const a = call(original, pattern, name);
      for (const fn of [migrated, migratedESM]) {
        comparisons++;
        if (JSON.stringify(a) !== JSON.stringify(call(fn, pattern, name))) {
          differences++;
          if (witnesses.length < 8) witnesses.push({ pattern, name });
        }
      }
    }
  }
  assert(differences > 0, 'negative compatibility control must discriminate');
  for (const mm of [next, esm]) {
    const bounded = new mm.Minimatch('**/../a/b/'.repeat(8), { optimizationLevel: 2, braceExpandMax: 64 });
    assert(bounded.globParts.length <= 64);
    assert.equal(mm.minimatch('logs-a-default', 'logs-*-*'), true);
    assert.equal(mm.minimatch('metrics-a-default', 'logs-*-*'), false);
  }

  // Real del implementation, adapted in memory only. All deletions stay in fresh /tmp fixtures.
  const delFile = `${root}/del/index.js`;
  const delSource = fs.readFileSync(delFile, 'utf8');
  const modernSource = delSource.replace("const {promisify} = require('util');", '')
    .replace("const rimraf = require('rimraf');", `const rimraf = require('${root}/rimraf');`)
    .replace('const rimrafP = promisify(rimraf);', 'const rimrafP = rimraf.rimraf;')
    .replace(/const rimrafOptions = \{[\s\S]*?\n\};/, 'const rimrafOptions = {glob: false};');
  assert.notEqual(modernSource, delSource);
  const mod = new Module(delFile);
  mod.filename = delFile;
  mod.paths = Module._nodeModulePaths(path.dirname(delFile));
  mod._compile(modernSource, delFile);
  const originalDel = require(delFile), migratedDel = mod.exports;
  const outcomes = [];
  for (const del of [originalDel, migratedDel]) {
    const cwd = fs.mkdtempSync('/tmp/cnc-del-supported-');
    fs.mkdirSync(`${cwd}/dir`);
    fs.writeFileSync(`${cwd}/dir/a.tmp`, 'owned');
    fs.writeFileSync(`${cwd}/keep.txt`, 'owned');
    fs.symlinkSync('/usr/share/kibana', `${cwd}/link`);
    const progress = [];
    const dry = await del(['dir', 'link'], { cwd, dryRun: true, onProgress: p => progress.push(p) });
    assert(fs.existsSync(`${cwd}/dir/a.tmp`));
    assert.equal(dry.length, 2);
    const removed = await del(['dir', 'link'], { cwd });
    assert.equal(removed.length, 2);
    assert(fs.existsSync(`${cwd}/keep.txt`));
    assert(fs.existsSync('/usr/share/kibana/package.json'));
    fs.writeFileSync(`${cwd}/sync.tmp`, 'owned');
    assert.equal(del.sync('*.tmp', { cwd }).length, 1);
    const outside = fs.mkdtempSync('/tmp/cnc-del-outside-');
    fs.writeFileSync(`${outside}/guard.txt`, 'owned');
    await assert.rejects(del(`${outside}/guard.txt`, { cwd }), /outside/);
    assert(fs.existsSync(`${outside}/guard.txt`));
    assert.equal((await del('absent', { cwd })).length, 0);
    outcomes.push({ dry: dry.map(f => path.basename(f)), removed: removed.map(f => path.basename(f)), progress });
  }
  assert.deepEqual(outcomes[0], outcomes[1]);
  const semver = require(`${root}/semver`);
  const declarations = {};
  for (const name of ['del', 'just-bash']) {
    const metadata = require(`${root}/${name}/package.json`);
    declarations[name] = metadata.dependencies;
  }
  assert.equal(semver.satisfies('11.0.4', declarations['just-bash'].minimatch), false);
  assert.equal(semver.satisfies('6.1.4', declarations.del.rimraf), false);

  // Actual installed just-bash CJS consumer, using its virtual filesystem only.
  // Reload the bundle so the second control cannot reuse the old import binding.
  const bashFile = `${root}/just-bash/dist/bundle/index.cjs`;
  const loader = Module._load;
  const bashResults = [];
  for (const mm of [old, next]) {
    let imports = 0;
    delete require.cache[bashFile];
    Module._load = function (id, parent, ...rest) {
      if (id === 'minimatch' && parent?.filename === bashFile) {
        imports++;
        return mm;
      }
      return loader.call(this, id, parent, ...rest);
    };
    try {
      const { Bash } = require(bashFile);
      const bash = new Bash({ files: {
        '/work/logs-a-default': 'virtual', '/work/logs-ab-default': 'virtual',
        '/work/logs-foo-default': 'virtual',
      }, cwd: '/work' });
      const control = await bash.exec("ls 'logs-*-default'");
      assert.equal(control.exitCode, 0);
      assert.equal(control.stdout, 'logs-a-default\nlogs-ab-default\nlogs-foo-default\n');
      const result = await bash.exec("ls 'logs-!(a|b)*-default'");
      assert.equal(result.exitCode, 0);
      assert.equal(result.stderr, '');
      assert.equal(imports, 1);
      bashResults.push({ stdout: result.stdout, imports });
    } finally { Module._load = loader; }
  }
  assert.equal(bashResults[0].stdout, 'logs-foo-default\n');
  assert.equal(bashResults[1].stdout, 'logs-a-default\nlogs-ab-default\nlogs-foo-default\n');
  console.log(JSON.stringify({ status: 'blocked-direct-minimatch-migration', node: process.version,
    fleetSourceSha256: sha(source), fleetFunctionSha256: sha(body), adaptedFunctionSha256: sha(adapted),
    delSourceSha256: sha(delSource), delAdaptedSha256: sha(modernSource),
    witness, comparisons, differences, witnesses, seed: '0x119',
    cjsAndEsm: true, boundedExpansion: true, delFixtureControlsEqual: true,
    justBashCjsSourceSha256: sha(fs.readFileSync(bashFile)), justBashCjsResults: bashResults,
    declarations, limits: ['No Fleet persisted-pattern domain proof', 'No full importer guard or final installed candidate',
      'No graceful-fs failure injection, Windows or EMFILE controls', 'No image build/scan or service acceptance'] }, null, 2));
}
main().catch(error => { console.error(error); process.exitCode = 1; });
