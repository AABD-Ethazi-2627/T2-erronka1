'use strict';
const fs = require('node:fs');
const path = require('node:path');
const assert = require('node:assert/strict');
const { hash } = require('./del-inventory.cjs');
const expected = require('./del-base-inventory.json').legacy;

function files(root) {
  const result = {};
  function walk(directory) {
    for (const entry of fs.readdirSync(directory, { withFileTypes: true })) {
      const file = path.join(directory, entry.name);
      assert(!entry.isSymbolicLink(), 'no symlinks accepted');
      if (entry.isDirectory()) walk(file);
      else { assert(entry.isFile()); result[path.relative(root, file)] = hash(fs.readFileSync(file)); }
    }
  }
  walk(root); return result;
}
function install(root, prepared) {
  const del = path.join(root, 'node_modules/del');
  assert.deepEqual(files(del), expected, 'legacy closure drift; refusing removal');
  const metadata = JSON.parse(fs.readFileSync(path.join(prepared, 'package.json')));
  const provenance = metadata.cncGuardMigration;
  assert.equal(metadata.version, '6.1.1+cncguard.1');
  assert.equal(metadata.dependencies.rimraf, '6.1.4');
  assert(!metadata.dependencies['graceful-fs']);
  const outputs = require('./del-output-hashes.json');
  assert.deepEqual(files(prepared), outputs.files, 'prepared bytes drift');
  const indexPath = path.join(root, 'node_modules/.modules.yaml');
  assert.equal(hash(fs.readFileSync(indexPath)), provenance.originalIndexSha256);
  const index = fs.readFileSync(prepared + '.modules.yaml');
  assert.equal(hash(index), outputs.modulesIndexSha256);
  assert.equal(hash(index), provenance.patchedIndexSha256);
  // Every input/output guard above precedes the first mutation.
  fs.rmSync(del, { recursive: true });
  fs.cpSync(prepared, del, { recursive: true });
  fs.writeFileSync(indexPath, index);
  assert(!fs.existsSync(path.join(del, 'node_modules')));
  return { removedLegacyFiles: Object.keys(expected).filter(n => n.startsWith('node_modules/')).length,
    installed: files(del), indexSha256: hash(index) };
}
module.exports = { install, files };
if (require.main === module) console.log(JSON.stringify(install(path.resolve(process.argv[2]), path.resolve(process.argv[3]))));
