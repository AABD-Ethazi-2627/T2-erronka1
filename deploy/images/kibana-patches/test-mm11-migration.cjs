'use strict';
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const { createRequire } = require('node:module');
const { pathToFileURL } = require('node:url');
const VENDOR = '/usr/share/kibana';
const { install, FLEET, FLEET_PACKAGE, BASH_PACKAGE } = require('./mm11-migration.cjs');
const { files } = require('./install-del-migration.cjs');
const { hash } = require('./del-inventory.cjs');
const inputs = require('./mm11-inputs.json');
const acorn = require(VENDOR + '/node_modules/acorn');
const normalize = value => JSON.parse(JSON.stringify(value));
const rows = [];

function extract(source, names, context) {
  const tree = acorn.parse(source, { ecmaVersion: 'latest', sourceType: 'script' });
  const statements = names.map(name => {
    const node = tree.body.find(node => node.type === 'FunctionDeclaration' && node.id.name === name ||
      node.type === 'VariableDeclaration' && node.declarations.some(d => d.id.name === name));
    assert(node, name); return source.slice(node.start, node.end);
  });
  return vm.runInNewContext(statements.join('\n') + `\n;${names.at(-1)}`, context);
}
function fixture(data) {
  const root = fs.mkdtempSync('/tmp/mm11-fixture-');
  const put = (file, bytes) => { fs.mkdirSync(path.dirname(path.join(root, file)), { recursive: true }); fs.writeFileSync(path.join(root, file), bytes); };
  for (const [file, value] of Object.entries(data.legacy)) put(file, Buffer.from(value.base64, 'base64'));
  for (const [file, value] of Object.entries(data.bash)) put(file, Buffer.from(value.base64, 'base64'));
  for (const file of Object.keys(inputs.consumers)) if (!file.startsWith('node_modules/just-bash/')) put(file, fs.readFileSync(path.join(VENDOR, file)));
  for (const file of Object.keys(inputs.packages)) if (file !== BASH_PACKAGE) put(file, fs.readFileSync(path.join(VENDOR, file)));
  put('node_modules/.modules.yaml', fs.readFileSync('/probe/del.modules.yaml'));
  // Non-modified dependencies point to immutable, read-only image packages.
  function links(source, destination) {
    for (const entry of fs.readdirSync(source, { withFileTypes: true })) {
      const target = path.join(destination, entry.name);
      if (!fs.existsSync(target)) fs.symlinkSync(path.join(source, entry.name), target);
      else if (entry.name === '@kbn') links(path.join(source, entry.name), target);
    }
  }
  links(VENDOR + '/node_modules', root + '/node_modules');
  return root;
}
function controls(root, old) {
  const requireFrom = createRequire(root + '/' + FLEET);
  const mm = requireFrom('minimatch');
  const matcher = requireFrom('@cnc-guard/bounded-minimatch');
  const fleet = extract(fs.readFileSync(root + '/' + FLEET, 'utf8'), ['getInstalledPackageSavedObjectDataStreams'], { _minimatch: matcher });
  const original = extract(fs.readFileSync(VENDOR + '/' + FLEET, 'utf8'), ['getInstalledPackageSavedObjectDataStreams'], { _minimatch: old });
  const call = (fn, p, name) => normalize(fn({ stream: p }, 'logs', [{ name }]));
  const yes = [{ name: 'logs-*-default', title: 'stream' }];
  assert.deepEqual(call(fleet, 'logs-*-default', 'logs-a-default'), yes);
  assert.deepEqual(call(fleet, 'logs-z*-default', 'logs-a-default'), []);
  assert.deepEqual(normalize(fleet({ x: 'metrics-a-default' }, 'logs', undefined)), []);
  assert.deepEqual(normalize(fleet({ x: 'logs-a-default' }, undefined, [])), []);
  assert.deepEqual(normalize(fleet({ x: 'logs-a-default' }, undefined, undefined)), [{ name: 'logs-a-default', title: 'x' }]);
  let seed = 0x119;
  const random = n => { seed = (Math.imul(seed, 1664525) + 1013904223) >>> 0; return (seed >>> 16) % n; };
  const atoms = ['a', 'b', '*', '?', '[ab]', '[!a]', '@(a|b)', '!(a|b)', '+(a|b)', '*(a|b)', '?(a|b)', '{a,b}', 'foo'];
  const names = ['a', 'b', 'aa', 'ab', 'ba', 'foo', 'foobar', 'foo.bar', 'x'];
  return { mm, matcher, fleet, original, call, random, atoms, names, rows };
}
async function main() {
  assert.equal(process.version, 'v24.21.0');
  const data = JSON.parse(fs.readFileSync('/probe/capture.json'));
  const prepared = '/probe/prepared';
  const root = fixture(data);
  const rejected = [];
  for (const file of [FLEET, BASH_PACKAGE, 'node_modules/just-bash/dist/bundle/browser.js', 'node_modules/minimatch/dist/commonjs/index.js']) {
    const target = root + '/' + file, original = fs.readFileSync(target);
    const index = hash(fs.readFileSync(root + '/node_modules/.modules.yaml'));
    fs.appendFileSync(target, '\n// drift\n');
    assert.throws(() => install(root, prepared));
    assert.equal(hash(fs.readFileSync(root + '/node_modules/.modules.yaml')), index);
    assert.equal(hash(fs.readFileSync(target)), hash(Buffer.concat([original, Buffer.from('\n// drift\n')])));
    fs.writeFileSync(target, original); rejected.push(file);
  }
  const indexFile = root + '/node_modules/.modules.yaml';
  const originalIndex = fs.readFileSync(indexFile);
  fs.appendFileSync(indexFile, '\n');
  assert.throws(() => install(root, prepared));
  assert.deepEqual(files(root + '/node_modules/minimatch'), inputs.legacy);
  fs.writeFileSync(indexFile, originalIndex); rejected.push('post-del-index-drift');
  const mutant = fs.mkdtempSync('/tmp/mm11-output-drift-');
  fs.cpSync(prepared, mutant, { recursive: true });
  fs.appendFileSync(mutant + '/node_modules/minimatch/dist/esm/index.js', '\n// drift');
  assert.throws(() => install(root, mutant), /prepared migration bytes drifted/);
  assert.deepEqual(files(root + '/node_modules/minimatch'), inputs.legacy);
  assert.equal(hash(fs.readFileSync(indexFile)), hash(originalIndex));
  rejected.push('prepared-ESM-drift');
  const result = install(root, prepared);
  assert.equal(result.removedRootLegacyFiles, 28);
  assert.deepEqual(files(root + '/node_modules/minimatch'), require('./mm11-official-files.json'));
  assert.throws(() => install(root, prepared));
  const old = require(VENDOR + '/node_modules/minimatch');
  const { mm, matcher, fleet, original, call, random, atoms, names } = controls(root, old);
  const cachedFunction = mm.minimatch;
  mm.minimatch = () => { throw new Error('official shared compiled cache must not be called'); };
  try {
    assert(matcher.minimatch('logs-a', 'logs-*'));
    assert(new matcher.Minimatch('logs-*').match('logs-a'));
  } finally { mm.minimatch = cachedFunction; }
  const esm = await import(pathToFileURL(root + '/node_modules/minimatch/dist/esm/index.js'));
  assert.equal(mm.Minimatch.prototype.makeRe, undefined);
  assert.equal(mm.makeRe, undefined);
  let comparisons = 0, differences = 0;
  for (let i = 0; i < 2000; i++) {
    const pattern = `logs-${Array.from({ length: 1 + random(4) }, () => atoms[random(atoms.length)]).join('')}-default`;
    for (const middle of names) {
      const name = `logs-${middle}-default`, previous = call(original, pattern, name);
      for (const api of [mm, esm]) {
        const current = new api.Minimatch(pattern, { noglobstar: true, nonegate: true }).match(name) ? [{ name: pattern, title: 'stream' }] : [];
        assert.deepEqual(current, call(fleet, pattern, name)); comparisons++;
        if (JSON.stringify(previous) !== JSON.stringify(current)) {
          assert(pattern.includes('!('), 'unclassified semantic difference'); differences++;
        }
      }
    }
  }
  assert.equal(comparisons, 36000); assert.equal(differences, 216);
  rows.push({ corpus: 'historical-0x119', comparisons, differences, classification: 'adopted official negative-extglob semantics' });
  let ordinary = 0;
  const ordinaryAtoms = atoms.filter(a => a !== '!(a|b)');
  for (let i = 0; i < 1000; i++) {
    const p = `logs-${Array.from({ length: 1 + random(4) }, () => ordinaryAtoms[random(ordinaryAtoms.length)]).join('')}-default`;
    for (const n of names) { assert.deepEqual(call(fleet, p, `logs-${n}-default`), call(original, p, `logs-${n}-default`)); ordinary++; }
  }
  for (const api of [mm, esm]) {
    for (const [name, pattern, expected, options] of [
      ['café.txt', '*.txt', true], ['é', '[[:alpha:]]', true], ['é', '?', true],
      ['cafe\u0301', 'café', false], ['Σ', 'σ', true, { nocase: true }],
      ['.hidden', '*', false], ['.hidden', '*', true, { dot: true }],
      ['a/b', 'a/*', true], ['a/b/c', 'a/*', false], ['a/b/c', 'a/**', true],
      ['logs-a-default', 'logs-!(a|b)*-default', true],
      ['logs-a-default', 'logs-!(a|ab)-default', false],
    ]) {
      assert.equal(api.minimatch(name, pattern, options), expected);
      if (!pattern.includes('!(')) assert.equal(old.minimatch(name, pattern, options), expected);
    }
    assert(new api.Minimatch('**/../a/b/'.repeat(8), { optimizationLevel: 2, braceExpandMax: 64 }).globParts.length <= 64);
    assert.equal(api.minimatch('a'.repeat(128) + 'b', '*(a|aa)'.repeat(12)), false);
    assert.deepEqual(api.match(['a.js', 'b.txt'], '*.js'), ['a.js']);
    assert.equal(api.filter('*.js')('a.js'), true);
    assert.equal(api.unescape(api.escape('a*b')), 'a*b');
  }
  rows.push({ ordinaryComparisons: ordinary, unicodeAndBounds: true, formats: ['CJS', 'ESM'] });
  const load = (suffix, names, context = {}) => {
    const file = Object.keys(inputs.consumers).find(p => p.includes(suffix)); assert(file);
    return extract(fs.readFileSync(root + '/' + file, 'utf8'), names, { _minimatch: matcher, ...context });
  };
  const task = load('task_claimers/index.js', ['isTaskTypeExcluded']);
  assert.equal(task(['alerting:*'], 'alerting:é'), true); assert.equal(task(['alerting:*'], 'reports:daily'), false);
  const allowed = load('health_diagnostic_receiver', ['isPathAllowed']);
  assert.equal(allowed('/_cluster/health', [{ path: '/_cluster/*' }]), true);
  assert.equal(allowed('/_Cluster/health', [{ path: '/_cluster/*' }]), false);
  assert.equal(allowed('/_security/user', [{ path: '/_cluster/*' }]), false);
  const excludes = load('classify_streams', ['matchesExcludePatterns']);
  assert.equal(excludes('logs-a-default', ['metrics-*']), false);
  assert.equal(excludes('logs-a-default', ['logs-!(a|b)*-default']), true);
  const fields = load('get_field_values_handler', ['KEYWORD_TYPES', 'NUMERIC_TYPES', 'DATE_TYPES', 'BOOLEAN_TYPES', 'TEXT_TYPES', 'getFieldCategory', 'resolveInputToConcreteFields']);
  const types = { 'attributes.é': 'keyword', 'attributes.num': 'long', '.hidden': 'keyword', object: undefined };
  assert.deepEqual(normalize(fields('attributes.*', Object.keys(types), types)), [
    { field: 'attributes.é', fieldType: 'keyword', category: 'keyword' },
    { field: 'attributes.num', fieldType: 'long', category: 'numeric' },
  ]);
  assert.equal(normalize(fields('*', Object.keys(types), types)).some(f => f.field === '.hidden'), true);
  assert.equal(normalize(fields('absent', Object.keys(types), types))[0].error, 'Field "absent" not found');
  rows.push({ realCompiledKbnConsumers: 5, noServicesOrElasticsearch: true });
  // These domains were absent from the original Fleet-only 9,000 corpus.
  assert.deepEqual(call(fleet, 'logs-*', 'logs-a-default/'), [{ name: 'logs-*', title: 'stream' }]);
  assert.deepEqual(call(original, 'logs-*', 'logs-a-default/'), []);
  assert.equal(excludes('.kibana-x', ['?(logs)*']), false);
  assert.equal(old.minimatch('.kibana-x', '?(logs)*'), true);
  assert.equal(allowed('/_cluster/', [{ path: '/_cluster/?(x)' }]), false);
  assert.equal(old.minimatch('/_cluster/', '/_cluster/?(x)', { nocase: false }), true);
  const securityPatterns = ['_transform/*/_stats', '_nodes/stats', '_nodes/*/stats', '_cluster/stats',
    '_ml/anomaly_detectors/_stats', '_ml/anomaly_detectors/*/_stats', '_ml/trained_models/_stats', '_ilm/status', '_watcher/stats'];
  const apiNames = ['_nodes/stats', '_nodes/abc/stats', '_nodes/a/b/stats', '_nodes//stats', '_nodes/./stats', '_nodes/../stats',
    '_nodes/.x/stats', '_nodes/%2e%2e/stats', '_nodes/stats/', '/_nodes/stats', '_cluster/stats', '_cluster/stats/',
    '_transform/x/_stats', '_transform/../_stats', '_transform//_stats', '_ml/anomaly_detectors/_stats',
    '_ml/anomaly_detectors/x/_stats', '_ml/anomaly_detectors/../_stats', '_ml/trained_models/_stats', '_ilm/status',
    '_watcher/stats', '_security/user', '_nodes/../_security/user', '_nodes/../../_security/stats', '_transform/../_security/_stats', '', '/', '*'];
  for (const pattern of securityPatterns) for (const name of apiNames) {
    assert.equal(allowed(name, [{ path: pattern }]), old.minimatch(name, pattern, { nocase: false }));
  }
  rows.push({ securityDefaultPatternComparisons: 252, differences: 0,
    additionalDeclaredSemanticClasses: ['trailing slash in Fleet matcher API', 'positive extglob dotfile', 'empty final path segment'] });

  // Check the options passed by the actual consumers, rather than an option
  // invented by this test. All eight import sites share the same finite budget.
  const checkedMatch = (name, pattern, options) => {
    assert.equal(options?.braceExpandMax, 1024, 'real consumer expansion budget missing');
    return mm.minimatch(name, pattern, options);
  };
  checkedMatch.Minimatch = class extends mm.Minimatch {
    constructor(pattern, options) {
      assert.equal(options?.braceExpandMax, 1024, 'real Fleet expansion budget missing');
      super(pattern, options);
    }
  };
  const boundedContext = { _minimatch: { minimatch: checkedMatch, Minimatch: checkedMatch.Minimatch } };
  const boundedFleet = extract(fs.readFileSync(root + '/' + FLEET, 'utf8'), ['getInstalledPackageSavedObjectDataStreams'], boundedContext);
  call(boundedFleet, 'logs-*', 'logs-a-default');
  load('task_claimers/index.js', ['isTaskTypeExcluded'], boundedContext)(['alerting:*'], 'alerting:x');
  load('health_diagnostic_receiver', ['isPathAllowed'], boundedContext)('/_cluster/health', [{ path: '/_cluster/*' }]);
  load('classify_streams', ['matchesExcludePatterns'], boundedContext)('logs', ['logs*']);
  load('get_field_values_handler', ['KEYWORD_TYPES', 'NUMERIC_TYPES', 'DATE_TYPES', 'BOOLEAN_TYPES', 'TEXT_TYPES', 'getFieldCategory', 'resolveInputToConcreteFields'], boundedContext)('attributes.*', Object.keys(types), types);
  for (const [route, check] of [['excludes', () => excludes('2048', ['{1..99999}'])], ['task', () => task(['{1..99999}'], '2048')],
    ['allowed', () => allowed('2048', [{ path: '{1..99999}' }])], ['fleet', () => call(fleet, 'logs-{1..99999}', 'logs-2048')],
    ['fields', () => fields('{1..99999}/*', ['2048/value'], { '2048/value': 'keyword' })],
    ['negated allowlist', () => allowed('1500', [{ path: '!{1..2000}' }])]]) {
    assert.throws(check, /expansion budget exceeded/, `overflow must reject: ${route}`);
  }
  assert(new matcher.Minimatch('{1..1024}').match('1024'));
  assert.throws(() => new matcher.Minimatch('{1..1025}'), /expansion budget exceeded/);
  // AST-check both actual call sites in every bundle before any retention
  // probe. A missing budget fails without repeatedly allocating large caches.
  for (const suffix of ['browser.js', 'chunks/chunk-R4IFXNY5.js', 'index.cjs']) {
    const file = Object.keys(inputs.consumers).find(p => p.endsWith('just-bash/dist/bundle/' + suffix));
    const tree = acorn.parse(fs.readFileSync(root + '/' + file, 'utf8'), { ecmaVersion: 'latest', sourceType: 'module' });
    const pending = [tree]; let calls = 0, constructors = 0;
    while (pending.length) {
      const node = pending.pop();
      if (node.type === 'CallExpression') {
        const last = node.callee;
        if (last.type === 'MemberExpression' && last.object.name === 'CncPattern' && last.property.name === 'match') calls++;
      }
      if (node.type === 'NewExpression' && (node.callee.name === 'CncBoundedMinimatch' ||
        node.callee.type === 'MemberExpression' && node.callee.object.name === 'Dp' && node.callee.property.name === 'Minimatch')) {
        constructors++;
        const options = node.arguments[1];
        assert.equal(options?.type, 'ObjectExpression', 'actual bundle matcher options missing');
        assert(options.properties.some(p => p.key.name === 'braceExpandMax' && p.value.value === 1024));
      }
      for (const value of Object.values(node)) {
        if (Array.isArray(value)) { for (const child of value) if (child?.type) pending.push(child); }
        else if (value?.type) pending.push(value);
      }
    }
    assert.equal(calls, 2, 'both actual bundle match sites must be bounded');
    assert.equal(constructors, 1, 'compile once per ls pattern, never per filesystem entry');
  }
  assert.equal(typeof global.gc, 'function', 'retention phase requires --expose-gc');
  const heap = () => { global.gc(); return process.memoryUsage().heapUsed; };
  const retainedStart = heap();
  for (let i = 0; i < 12; i++) {
    const start = heap();
    excludes('logs', [`{1..${1000 + i}}`]);
    fields(`{1..${1000 + i}}/*`, ['2048/value'], { '2048/value': 'keyword' });
    await new Promise(setImmediate); // Measure retention beyond the current JS job, not live compiler temporaries.
    assert(heap() - start < 8 * 1024**2, 'unexpected per-pattern retention; stop before additional probes');
  }
  const retainedBytes = heap() - retainedStart;
  assert(retainedBytes < 24 * 1024**2, 'bounded consumer retention exceeded fixture budget');
  const longPattern = (length, end = 1024) => (`{1..${end}}/` + 'a/'.repeat(length)).slice(0, length - 1) + '*';
  const longStart = heap();
  for (let i = 0; i < 3; i++) {
    const before = heap();
    excludes('logs', [longPattern(4095, 1024 - i)]);
    fields(longPattern(1023, 1024 - i), ['2048/value'], { '2048/value': 'keyword' });
    const synchronousDelta = heap() - before;
    await new Promise(setImmediate);
    const retainedDelta = heap() - before;
    rows.push({ longPatternStep: i, synchronousDelta, retainedDelta });
    assert(retainedDelta < 8 * 1024**2, `long-pattern retention exceeded safe stop: ${retainedDelta}`);
  }
  const longRetainedBytes = heap() - longStart;
  assert(longRetainedBytes < 8 * 1024**2, 'long accepted patterns must not persist in shared cache');
  rows.push({ realConsumersBraceExpandMax: 1024, measuredShortPatterns: 24, retainedBytes,
    measuredLongPatterns: 6, longPatternLengths: [1023, 4095], longRetainedBytes,
    retentionBudgetBytes: 24 * 1024**2, overflowRejectedBeforeCompilation: true, sharedCompiledCache: false });

  const variants = [
    ['CJS', require(root + '/node_modules/just-bash/dist/bundle/index.cjs')],
    ['ESM', await import(pathToFileURL(root + '/node_modules/just-bash/dist/bundle/index.js'))],
    ['browser-entry-in-Node', await import(pathToFileURL(root + '/node_modules/just-bash/dist/bundle/browser.js'))],
  ];
  const cases = [
    ['logs-*-default', 'logs-a-default\nlogs-ab-default\nlogs-foo-default\n', 0],
    ['logs-z*-default', '', 2],
    ['logs-@(a|ab)*-default', 'logs-a-default\nlogs-ab-default\n', 0],
    ['logs-+(a|b)*-default', 'logs-a-default\nlogs-ab-default\n', 0],
    ['logs-!(a|b)*-default', 'logs-a-default\nlogs-ab-default\nlogs-foo-default\n', 0],
    ['logs-!(a*|ab*)-default', 'logs-foo-default\n', 0],
    ['café*', 'café.txt\n', 0],
  ];
  // Quoted positive extglobs without a wildcard never reach ls's matcher in
  // the original bundle. Preserve and explicitly test that existing limitation.
  const OldBash = require(VENDOR + '/node_modules/just-bash').Bash;
  const oldBash = new OldBash({ cwd: '/work', files: { '/work/logs-a-default': 'virtual', '/work/logs-ab-default': 'virtual', '/work/logs-foo-default': 'virtual' } });
  assert.equal((await oldBash.exec("ls 'logs-@(a|ab)-default'")).exitCode, 2);
  assert.equal((await oldBash.exec("ls 'logs-!(a|b)*-default'")).stdout, 'logs-foo-default\n');
  for (const [variant, { Bash }] of variants) {
    const bash = new Bash({ cwd: '/work', files: { '/work/logs-a-default': 'virtual', '/work/logs-ab-default': 'virtual', '/work/logs-foo-default': 'virtual', '/work/café.txt': 'virtual' } });
    for (const [pattern, stdout, exitCode] of cases) {
      const result = await bash.exec(`ls '${pattern}'`);
      assert.equal(result.stdout, stdout, variant + ': ' + pattern); assert.equal(result.exitCode, exitCode);
    }
    assert.equal((await bash.exec("ls 'logs-@(a|ab)-default'")).exitCode, 2);
    const boundedBash = new Bash({ cwd: '/budget', files: { '/budget/2048/value': 'owned virtual data' } });
    const before = heap();
    const oversized = await boundedBash.exec("ls '{1..99999}/*'");
    assert.equal(oversized.exitCode, 1); assert.equal(oversized.stdout, '');
    assert(oversized.stderr.includes('expansion budget exceeded'));
    const longBefore = heap();
    const acceptedLong = await boundedBash.exec(`ls '${longPattern(4096)}'`);
    assert.equal(acceptedLong.exitCode, 2);
    await new Promise(setImmediate);
    const longBashRetainedBytes = heap() - longBefore;
    assert(longBashRetainedBytes < 8 * 1024**2, 'actual Bash bundle retained a long compiled pattern');
    assert(heap() - before < 8 * 1024**2, 'actual Bash bundle retained unbounded expansion');
    rows.push({ actualJustBashVariant: variant, cases: cases.length, longPatternLength: 4096, longBashRetainedBytes });
  }
  // Coexistence: the independently accepted del engine bytes/pins stay unchanged.
  fs.unlinkSync(root + '/node_modules/del');
  fs.cpSync('/probe/del', root + '/node_modules/del', { recursive: true });
  assert.deepEqual(files(root + '/node_modules/del'), require('./del-output-hashes.json').files);
  const del = require(root + '/node_modules/del');
  const cwd = fs.mkdtempSync('/tmp/cnc-mm11-del-'); fs.writeFileSync(cwd + '/async', 'owned'); fs.writeFileSync(cwd + '/sync', 'owned');
  assert.equal((await del('async', { cwd, dryRun: true })).length, 1);
  assert.equal((await del('async', { cwd })).length, 1); assert.equal(del.sync('sync', { cwd }).length, 1);
  rows.push({ delCoexistence: true, exactEngineBytesRetained: true });
  const semver = require(VENDOR + '/node_modules/semver');
  for (const file of [FLEET_PACKAGE, BASH_PACKAGE]) {
    const metadata = JSON.parse(fs.readFileSync(root + '/' + file));
    assert.equal(metadata.dependencies.minimatch, '11.0.4');
    assert(semver.satisfies('11.0.4', metadata.dependencies.minimatch));
  }
  console.log(JSON.stringify({ node: process.version, installation: result, rejectedDrift: rejected,
    doubleApplicationRejected: true, rootMinimatch: '11.0.4', rows }, null, 2));
}
main().catch(error => { console.error(error); process.exitCode = 1; });
