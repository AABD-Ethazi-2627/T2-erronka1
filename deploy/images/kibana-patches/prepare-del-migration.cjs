'use strict';
const fs = require('node:fs');
const path = require('node:path');
const assert = require('node:assert/strict');
const { inventory, fingerprint, hash } = require('./del-inventory.cjs');
const expected = require('./del-base-inventory.json');

function prepare(root, output) {
  const report = inventory(root);
  // Pin the entire incoming executable tree, including non-JS, bundles, maps,
  // templates, metadata and compressed copies. No classifier can waive drift.
  assert.deepEqual(fingerprint(report), expected, 'base bytes/importers/declarations drifted; review before deletion');
  const source = path.join(root, 'node_modules/del');
  assert(!fs.existsSync(output), 'output must be fresh');
  const original = fs.readFileSync(path.join(source, 'index.js'), 'utf8');
  let code = original.replace("const gracefulFs = require('graceful-fs');\n", '')
    .replace("const rimraf = require('rimraf');", "const fs = require('node:fs');\nconst {posixSync} = require('rimraf');")
    .replace('const rimrafP = promisify(rimraf);', 'const remove = promisify(fs.rm);')
    .replace(/const rimrafOptions = \{[\s\S]*?\n\};/, [
      '// Local CNC Guard migration: Node maintained recursive removal, no globbing.',
      '// force here only tolerates ENOENT; del safeCheck and its force option stay intact.',
      'const removeOptions = {recursive: true, force: true, maxRetries: 3, retryDelay: 100};',
      '// Avoid Node 24.21 rmSync losing EBUSY error codes after native retries.',
      'function removeSync(file) {',
      "\tconst retryable = new Set(['EBUSY', 'EMFILE', 'ENFILE', 'ENOTEMPTY', 'EPERM']);",
      '\tfor (let attempt = 0; ; attempt++) {',
      '\t\ttry { return posixSync(file, {glob: false}); } catch (error) {',
      '\t\t\tif (!retryable.has(error.code) || attempt >= 3) throw error;',
      '\t\t\tAtomics.wait(new Int32Array(new SharedArrayBuffer(4)), 0, 0, 100 * (attempt + 1));',
      '\t\t}',
      '\t}',
      '}',
    ].join('\n'))
    .replace('await rimrafP(file, rimrafOptions);', 'await remove(file, removeOptions);')
    .replace('rimraf.sync(file, rimrafOptions);', 'removeSync(file);');
  assert(!/rimrafP|rimrafOptions|gracefulFs/.test(code));
  assert.equal(hash(original), '04e820c86f88eb014531345ab22c2ba215c5431342b99409e4b4611d53dfd48a');
  const metadata = JSON.parse(fs.readFileSync(path.join(source, 'package.json')));
  assert.equal(metadata.version, '6.1.1');
  assert.equal(metadata.dependencies.rimraf, '^3.0.2');
  metadata.version = '6.1.1+cncguard.1';
  metadata.dependencies.rimraf = '6.1.4';
  delete metadata.dependencies['graceful-fs'];
  metadata.engines.node = '20 || >=22';
  const indexFile = path.join(root, 'node_modules/.modules.yaml');
  const indexSource = fs.readFileSync(indexFile);
  let removedPaths = 0;
  function prune(value) {
    if (typeof value === 'string' && value.startsWith('node_modules/del/node_modules/')) {
      removedPaths++; return undefined;
    }
    if (Array.isArray(value)) return value.map(prune).filter(v => v !== undefined);
    if (value && typeof value === 'object') return Object.fromEntries(Object.entries(value).flatMap(([key, item]) => {
      const cleaned = prune(item);
      return Array.isArray(cleaned) && cleaned.length === 0 && Array.isArray(item) && item.length > 0 ? [] : [[key, cleaned]];
    }));
    return value;
  }
  const updatedIndex = JSON.stringify(prune(JSON.parse(indexSource)), null, 2) + '\n';
  assert.equal(removedPaths, 4);
  metadata.cncGuardMigration = {
    upstreamVersion: '6.1.1', originalSourceSha256: hash(original),
    implementation: 'async node:fs rm; sync rimraf 6.1.4 posixSync; 3 retries at 100/200/300ms',
    supportedPlatform: 'linux (pinned Wolfi Kibana image)',
    patchedSourceSha256: hash(code),
    originalIndexSha256: hash(indexSource), patchedIndexSha256: hash(updatedIndex),
    upstreamReference: 'https://registry.npmjs.org/del/-/del-8.0.1.tgz',
    note: 'Local CJS consumer adaptation, not upstream del 8; async EMFILE/ENFILE retry policy changes.',
  };
  // All checks precede the first write. Never copy the nested legacy closure.
  fs.mkdirSync(output);
  fs.copyFileSync(path.join(source, 'license'), path.join(output, 'license'));
  fs.writeFileSync(path.join(output, 'index.js'), code);
  fs.writeFileSync(path.join(output, 'package.json'), JSON.stringify(metadata, null, 2) + '\n');
  fs.writeFileSync(output + '.modules.yaml', updatedIndex);
  return { originalTreeSha256: report.treeSha256, sourceSha256: hash(code), packageSha256: hash(fs.readFileSync(path.join(output, 'package.json'))) };
}
module.exports = { prepare };
if (require.main === module) console.log(JSON.stringify(prepare(path.resolve(process.argv[2]), path.resolve(process.argv[3]))));
