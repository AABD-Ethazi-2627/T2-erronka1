'use strict';
// Real binaries, shared libraries and Brotli API, including launcher's fallback.
const assert = require('node:assert/strict');
const { execFileSync } = require('node:child_process');
const { brotliCompressSync, brotliDecompressSync } = require('node:zlib');
const fs = require('node:fs');
const vm = require('node:vm');
const root = '/usr/share/kibana';
assert.equal(process.version, 'v24.22.1');
assert.deepEqual(fs.readdirSync(`${root}/node`).sort(), ['default', 'glibc-217']);
for (const variant of ['default', 'glibc-217']) {
  assert.equal(execFileSync(`${root}/node/${variant}/bin/node`, ['--version'], {
    encoding: 'utf8', timeout: 10000,
  }).trim(), 'v24.22.1');
}
const plain = Buffer.from('CNC Guard: café / Brotli integrity');
assert.deepEqual(brotliDecompressSync(brotliCompressSync(plain)), plain);
assert.throws(() => brotliDecompressSync(Buffer.from([0xff, 0xff, 0xff])));
// This is the retained application, not a claim to have upgraded it to 9.5.6.
assert.equal(require(`${root}/package.json`).version, '9.5.5');
const pkg = require(`${root}/package.json`);
assert.equal(pkg.engines.node, '24.22.1');
assert.equal(pkg.cncGuardNodeRuntime.upstreamNode, '24.21.0');
assert.equal(process.env.UNSAFE_DISABLE_NODE_VERSION_VALIDATION, undefined);
const validator = `${root}/node_modules/@kbn/setup-node-env/node_version_validator.js`;
execFileSync(process.execPath, [validator], { timeout: 10000 });
// Run the unchanged real validator on both invalid sibling runtime identities.
for (const version of ['v24.21.0', 'v24.22.2']) {
  let rejected = false;
  vm.runInNewContext(fs.readFileSync(validator, 'utf8'), {
    __filename: validator, require: () => pkg, console: { error() {} },
    process: { version, env: {}, exit(code) { assert.equal(code, 1); rejected = true; } },
  });
  assert(rejected, `validator accepted unsupported runtime ${version}`);
}
console.log(JSON.stringify({ application: '9.5.5', node: process.version,
  variants: ['default', 'glibc-217'], brotliControls: true,
  scope: 'runtime identity and API controls; not a memory-corruption exploit test' }));
