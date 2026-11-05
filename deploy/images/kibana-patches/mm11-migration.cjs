'use strict';
const fs = require('node:fs');
const path = require('node:path');
const assert = require('node:assert/strict');
const { hash, inventory, fingerprint } = require('./del-inventory.cjs');
const { files } = require('./install-del-migration.cjs');
const inputs = require('./mm11-inputs.json');
const FLEET = 'node_modules/@kbn/fleet-plugin/server/services/epm/packages/get.js';
const FLEET_PACKAGE = 'node_modules/@kbn/fleet-plugin/package.json';
const BASH_PACKAGE = 'node_modules/just-bash/package.json';

function checkInputs(root) {
  assert.deepEqual(files(path.join(root, 'node_modules/minimatch')), inputs.legacy, 'legacy root MM bytes drifted');
  assert.deepEqual(files(path.join(root, 'node_modules/just-bash')), inputs.justBash, 'just-bash bytes drifted');
  for (const [file, sha256] of Object.entries({ ...inputs.consumers, ...inputs.packages })) {
    assert.equal(hash(fs.readFileSync(path.join(root, file))), sha256, `consumer drift: ${file}`);
  }
}
function prepare(root, official, output, afterDelIndex) {
  assert.equal(process.version, 'v24.21.0');
  assert.deepEqual(fingerprint(inventory(root)), require('./del-base-inventory.json'), 'whole base tree drifted');
  checkInputs(root);
  assert(!fs.existsSync(output), 'output must be fresh');
  const officialFiles = files(official);
  assert.deepEqual(officialFiles, require('./mm11-official-files.json'), 'npm closure drifted');
  assert.equal(JSON.parse(fs.readFileSync(path.join(official, 'package.json'))).version, '11.0.4');
  const original = fs.readFileSync(path.join(root, FLEET), 'utf8');
  const replacements = [
    ['const patternRegex = new _minimatch.minimatch.Minimatch(stream.name, {', 'const patternMatcher = new _minimatch.minimatch.Minimatch(stream.name, {'],
    ['}).makeRe();', '});'],
    ['dataStreamName.match(patternRegex)', 'patternMatcher.match(dataStreamName)'],
  ];
  let fleet = original;
  for (const [before, after] of replacements) {
    assert.equal(fleet.split(before).length, 2, `unique Fleet patch context: ${before}`);
    fleet = fleet.replace(before, after);
  }
  assert(!fleet.includes('.makeRe('));
  const patch = new Map([[FLEET, Buffer.from(fleet)]]);
  for (const file of [FLEET_PACKAGE, BASH_PACKAGE]) {
    const metadata = JSON.parse(fs.readFileSync(path.join(root, file)));
    const upstreamVersion = metadata.version;
    metadata.version += '+cncguard.mm11.1';
    metadata.dependencies = { ...metadata.dependencies, minimatch: '11.0.4' };
    metadata.cncGuardMinimatchMigration = { upstreamVersion, originalPackageSha256: inputs.packages[file],
      minimatch: '11.0.4', semanticPolicy: 'official MM11 semantics accepted for candidate; not MM10 equivalence',
      sourceChange: file === FLEET_PACKAGE ? 'get.js: boolean Minimatch.match instead of makeRe/String.match' : 'bundle bytes unchanged; local dependency integration of upstream ^10 consumer',
      inputSources: Object.fromEntries(Object.entries(inputs.consumers).filter(([name]) => name.startsWith(path.dirname(file) + '/'))),
    };
    patch.set(file, Buffer.from(JSON.stringify(metadata, null, 2) + '\n'));
  }
  const indexBytes = fs.readFileSync(afterDelIndex);
  assert.equal(hash(indexBytes), require('./del-output-hashes.json').modulesIndexSha256, 'del index must be prepared first');
  const index = JSON.parse(indexBytes);
  // Kibana's packaging index is JSON despite its .yaml suffix. Preserve all
  // unrelated entries; replace only paths for the physically replaced root MM.
  let removed = 0;
  function prune(value) {
    if (value === 'node_modules/minimatch') { removed++; return undefined; }
    if (Array.isArray(value)) return value.map(prune).filter(v => v !== undefined);
    if (value && typeof value === 'object') return Object.fromEntries(Object.entries(value).flatMap(([key, old]) => {
      const next = prune(old);
      return Array.isArray(old) && old.length && Array.isArray(next) && !next.length ? [] : [[key, next]];
    }));
    return value;
  }
  const updated = prune(index);
  assert.equal(removed, 1);
  // Find the existing package-location map, without depending on its outer key.
  let maps = [];
  function find(value) {
    if (!value || typeof value !== 'object') return;
    if (Object.values(value).some(v => Array.isArray(v) && v.includes('node_modules/just-bash'))) maps.push(value);
    for (const item of Object.values(value)) find(item);
  }
  find(updated); assert.equal(maps.length, 1);
  const bashLocator = Object.keys(maps[0]).filter(key => key.startsWith('just-bash@3.0.1') && maps[0][key].includes('node_modules/just-bash'));
  assert.equal(bashLocator.length, 1);
  maps[0][bashLocator[0].replace('just-bash@3.0.1', 'just-bash@3.0.1+cncguard.mm11.1')] = maps[0][bashLocator[0]];
  delete maps[0][bashLocator[0]];
  for (const [name, location] of [
    ['minimatch@11.0.4', 'node_modules/minimatch'],
    ['@isaacs/nonrecursive-glob-match@1.0.3', 'node_modules/minimatch/node_modules/@isaacs/nonrecursive-glob-match'],
    ['brace-expansion@5.0.12', 'node_modules/minimatch/node_modules/brace-expansion'],
    ['balanced-match@4.0.4', 'node_modules/minimatch/node_modules/brace-expansion/node_modules/balanced-match'],
  ]) maps[0][name] = [...(maps[0][name] || []), location];
  patch.set('node_modules/.modules.yaml', Buffer.from(JSON.stringify(updated, null, 2) + '\n'));
  // All preflight checks precede writes; do not overlay old MM AST/maps/files.
  fs.mkdirSync(output);
  fs.mkdirSync(path.join(output, 'node_modules'));
  fs.cpSync(official, path.join(output, 'node_modules/minimatch'), { recursive: true });
  for (const [file, bytes] of patch) {
    fs.mkdirSync(path.dirname(path.join(output, file)), { recursive: true });
    fs.writeFileSync(path.join(output, file), bytes);
  }
  return { files: files(output), adoptedSemantics: 'MM11.0.4', oldImporters: Object.keys(inputs.consumers) };
}
function install(root, prepared) {
  checkInputs(root);
  assert.equal(hash(fs.readFileSync(path.join(root, 'node_modules/.modules.yaml'))), require('./del-output-hashes.json').modulesIndexSha256);
  assert.deepEqual(files(prepared), require('./mm11-output-files.json'), 'prepared migration bytes drifted');
  // Every preimage/output is guarded before the first mutation.
  fs.rmSync(path.join(root, 'node_modules/minimatch'), { recursive: true });
  for (const file of Object.keys(require('./mm11-output-files.json'))) {
    const destination = path.join(root, file);
    fs.mkdirSync(path.dirname(destination), { recursive: true });
    fs.copyFileSync(path.join(prepared, file), destination);
  }
  assert.deepEqual(files(path.join(root, 'node_modules/minimatch')), require('./mm11-official-files.json'));
  return { installedVersion: '11.0.4', installedOfficialFiles: Object.keys(require('./mm11-official-files.json')).length,
    removedRootLegacyFiles: Object.keys(inputs.legacy).length, fleetSourceSha256: hash(fs.readFileSync(path.join(root, FLEET))) };
}
module.exports = { prepare, install, checkInputs, FLEET, FLEET_PACKAGE, BASH_PACKAGE };
if (require.main === module) {
  const [mode, root, ...args] = process.argv.slice(2);
  assert(['prepare', 'install'].includes(mode));
  console.log(JSON.stringify(mode === 'prepare' ? prepare(root, ...args) : install(root, ...args)));
}
