'use strict';
const assert = require('node:assert/strict');
const fs = require('node:fs');
const { createHash } = require('node:crypto');
const file = '/usr/share/kibana/package.json';
const bytes = fs.readFileSync(file);
assert.equal(createHash('sha256').update(bytes).digest('hex'),
  'eeca8e3e6a95bc5314a6673da89dc6c56e0da2d52e81255aa3673b1f106e9a6a',
  'original application runtime contract drifted');
const pkg = JSON.parse(bytes);
assert.equal(pkg.version, '9.5.5');
assert.equal(pkg.engines.node, '24.21.0');
assert.equal(process.version, 'v24.22.1');
// Keep the real upstream validator's exact equality check; declare the actual
// locally integrated runtime instead of bypassing that check with UNSAFE_*.
pkg.engines.node = '24.22.1';
pkg.cncGuardNodeRuntime = {
  upstreamApplication: '9.5.5', upstreamNode: '24.21.0', node: '24.22.1',
  donor: 'docker.elastic.co/kibana/kibana-wolfi:9.5.6@sha256:fcc4fd28898aec394dc45c568ba811e34c132f5a0ebadfa8f8d1d412f55e00c3',
  advisory: 'https://discuss.elastic.co/t/kibana-8-19-24-9-4-9-9-5-6-security-update-esa-2026-232/391369',
  scope: 'local Node security integration; not upstream Kibana 9.5.6',
};
fs.writeFileSync(file, JSON.stringify(pkg, null, 2) + '\n');
