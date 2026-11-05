'use strict';
const fs = require('node:fs');
const path = require('node:path');
const assert = require('node:assert/strict');
const { createRequire } = require('node:module');
const { pathToFileURL } = require('node:url');
const { inventory, hash } = require('./del-inventory.cjs');
const { install, files } = require('./install-del-migration.cjs');
const { prepare } = require('./prepare-del-migration.cjs');
const prepared = process.argv[2], original = process.argv[3];
const fresh = () => fs.mkdtempSync('/tmp/cnc-del-');

async function main() {
  // Every source form is pinned as bytes; there is no syntax-based exemption.
  const probe = fresh();
  const forms = ["import 'del';", "require.resolve('del');", "require(/*x*/'del');",
    'import(`del`);', "__require$42('del');", "import type X from 'del/subpath';",
    '#!/usr/bin/env node\nrequire("del");', "require('del' + suffix);", '// require("del")'];
  forms.forEach((code, i) => fs.writeFileSync(path.join(probe, `fixture${i}.ts`), code));
  fs.writeFileSync(path.join(probe, 'boundary'), 'é'.repeat(65530) + 'require("del");');
  const scanned = inventory(probe);
  assert.equal(scanned.references.length, 10);
  const before = scanned.treeSha256;
  fs.appendFileSync(path.join(probe, 'fixture0.ts'), '// even a comment drifts');
  assert.notEqual(inventory(probe).treeSha256, before);
  const neverCreated = path.join(fresh(), 'out');
  assert.throws(() => prepare(probe, neverCreated), /drifted/);
  assert(!fs.existsSync(neverCreated));
  function fixture() {
    const root = fresh(); fs.mkdirSync(`${root}/node_modules`);
    fs.cpSync(original, `${root}/node_modules/del`, { recursive: true });
    fs.copyFileSync('/usr/share/kibana/node_modules/.modules.yaml', `${root}/node_modules/.modules.yaml`);
    return root;
  }
  const rejected = [];
  for (const kind of ['legacy-source', 'legacy-extra', 'legacy-symlink', 'metadata-index', 'patch-source', 'patch-index']) {
    const root = fixture(), patch = `${fresh()}/patched`;
    fs.cpSync(prepared, patch, { recursive: true });
    fs.copyFileSync(prepared + '.modules.yaml', patch + '.modules.yaml');
    if (kind === 'legacy-source') fs.appendFileSync(`${root}/node_modules/del/index.js`, '// drift');
    if (kind === 'legacy-extra') fs.writeFileSync(`${root}/node_modules/del/new.ts`, "import 'glob';");
    if (kind === 'legacy-symlink') fs.symlinkSync('index.js', `${root}/node_modules/del/alias`);
    if (kind === 'metadata-index') fs.appendFileSync(`${root}/node_modules/.modules.yaml`, '\n');
    if (kind === 'patch-source') fs.appendFileSync(patch + '/index.js', '// drift');
    if (kind === 'patch-index') fs.appendFileSync(patch + '.modules.yaml', '\n');
    const sourceBefore = hash(fs.readFileSync(`${root}/node_modules/del/index.js`));
    const indexBefore = hash(fs.readFileSync(`${root}/node_modules/.modules.yaml`));
    assert.throws(() => install(root, patch));
    assert.equal(hash(fs.readFileSync(`${root}/node_modules/del/index.js`)), sourceBefore);
    assert.equal(hash(fs.readFileSync(`${root}/node_modules/.modules.yaml`)), indexBefore);
    rejected.push(kind);
  }
  const root = fixture();
  const result = install(root, prepared);
  assert.equal(result.removedLegacyFiles, 15);
  assert(!fs.existsSync(`${root}/node_modules/del/node_modules`));
  const installed = files(`${root}/node_modules/del`);
  assert.throws(() => install(root, prepared), /drift/);
  assert.deepEqual(files(`${root}/node_modules/del`), installed);
  // Test standard physical CJS/ESM resolution after actual fixture removal.
  const metadata = require(`${root}/node_modules/del/package.json`);
  for (const dependency of Object.keys(metadata.dependencies)) {
    fs.symlinkSync(`/usr/share/kibana/node_modules/${dependency}`, `${root}/node_modules/${dependency}`);
  }
  const req = createRequire(`${root}/node_modules/del/index.js`);
  assert.equal(req('rimraf/package.json').version, '6.1.4');
  assert(req.resolve('rimraf').startsWith('/usr/share/kibana/node_modules/rimraf/'));
  const del = require(`${root}/node_modules/del`);
  const esm = await import(pathToFileURL(`${root}/node_modules/del/index.js`));
  assert.equal(esm.default, del); assert.equal(esm.default.sync, del.sync);
  const cwd = fresh(); fs.writeFileSync(cwd + '/async', 'owned'); fs.writeFileSync(cwd + '/sync', 'owned');
  assert.equal((await del('async', { cwd })).length, 1);
  assert.equal(esm.default.sync('sync', { cwd }).length, 1);
  console.log(JSON.stringify({ rejected, doubleApplicationRejected: true, forms: forms.length + 1,
    physicalFixture: result, standardCjsAndEsmResolution: true }, null, 2));
}
main().catch(error => { console.error(error); process.exitCode = 1; });
