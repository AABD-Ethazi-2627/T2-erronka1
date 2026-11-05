'use strict';
const fs = require('node:fs');
const path = require('node:path');
const assert = require('node:assert/strict');
const { createRequire } = require('node:module');
const { pathToFileURL } = require('node:url');
const { files } = require('./install-del-migration.cjs');
const { hash } = require('./del-inventory.cjs');
const inputs = require('./mm11-inputs.json');
const outputs = require('./mm11-output-files.json');
const root = process.argv[2] || '/usr/share/kibana';
async function main() {
  assert.deepEqual(files(path.join(root, 'node_modules/minimatch')), require('./mm11-official-files.json'));
  for (const [file, sha256] of Object.entries(inputs.consumers)) {
    assert.equal(hash(fs.readFileSync(path.join(root, file))), outputs[file] || sha256);
  }
  for (const file of Object.keys(inputs.packages)) {
    const metadata = JSON.parse(fs.readFileSync(path.join(root, file)));
    assert(metadata.version.endsWith('+cncguard.mm11.3'));
    assert.equal(metadata.dependencies.minimatch, '11.0.4');
    assert.equal(metadata.cncGuardMinimatchMigration.braceExpandMax, 1024);
    assert.equal(metadata.cncGuardMinimatchMigration.cachePolicy, 'uncached-new-Minimatch');
    assert.equal(metadata.dependencies['@cnc-guard/bounded-minimatch'], '1.0.0');
  }
  for (const name of ['index.cjs', 'package.json']) {
    const file = 'node_modules/@cnc-guard/bounded-minimatch/' + name;
    assert.equal(hash(fs.readFileSync(path.join(root, file))), outputs[file], `adapter drift: ${file}`);
  }
  const adapter = createRequire(path.join(root, 'package.json'))('@cnc-guard/bounded-minimatch');
  assert(new adapter.Minimatch('{1..1024}').match('1024'));
  assert.throws(() => adapter.minimatch('1500', '!{1..2000}'), /expansion budget exceeded/);
  const semver = require('/usr/share/kibana/node_modules/semver');
  const copies = [], runtimeDeclarations = [];
  function walk(directory) {
    for (const entry of fs.readdirSync(directory, { withFileTypes: true })) {
      const file = path.join(directory, entry.name);
      assert(!entry.isSymbolicLink(), `unreviewed installed symlink: ${file}`);
      if (entry.isDirectory()) walk(file);
      else if (entry.name === 'package.json') {
        const metadata = JSON.parse(fs.readFileSync(file));
        if (metadata.name === 'minimatch') {
          assert(semver.gte(metadata.version, '11.0.4'), `orphan legacy minimatch: ${file}`);
          copies.push({ file: path.relative(root, file), version: metadata.version });
        }
        for (const section of ['dependencies', 'optionalDependencies', 'peerDependencies']) {
          if (!metadata[section]?.minimatch) continue;
          const req = createRequire(file);
          const resolved = req.resolve('minimatch/package.json');
          const installed = JSON.parse(fs.readFileSync(resolved));
          assert(semver.satisfies(installed.version, metadata[section].minimatch), `${file}: unsupported minimatch range`);
          runtimeDeclarations.push({ file: path.relative(root, file), section, range: metadata[section].minimatch, resolved: path.relative(root, resolved) });
        }
      }
    }
  }
  walk(path.join(root, 'node_modules'));
  const mm = createRequire(path.join(root, 'package.json'))('minimatch');
  const esm = await import(pathToFileURL(path.join(root, 'node_modules/minimatch/dist/esm/index.js')));
  for (const api of [mm, esm]) {
    assert.equal(api.makeRe, undefined); assert.equal(api.Minimatch.prototype.makeRe, undefined);
    assert.equal(api.minimatch('logs-a-default', 'logs-!(a|b)*-default'), true);
    assert.equal(api.minimatch('logs-a-default', 'logs-!(a|ab)-default'), false);
    assert.equal(api.minimatch('café.txt', '*.txt'), true);
    assert(new api.Minimatch('**/../a/b/'.repeat(8), { optimizationLevel: 2, braceExpandMax: 64 }).globParts.length <= 64);
  }
  console.log(JSON.stringify({ rootVersion: '11.0.4', copies, runtimeDeclarations, officialBytes: true }));
}
main().catch(error => { console.error(error); process.exitCode = 1; });
