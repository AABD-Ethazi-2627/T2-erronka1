'use strict';
const fs = require('node:fs');
const path = require('node:path');
const { prepare: prepareDel } = require('./prepare-del-migration.cjs');
const { prepare } = require('./mm11-migration.cjs');
const inputs = require('./mm11-inputs.json');
const root = '/usr/share/kibana';
// The original base tree stays untouched across both preparations.
const delProof = prepareDel(root, '/tmp/del');
const proof = prepare(root, '/probe/official', '/tmp/prepared', '/tmp/del.modules.yaml');
const encode = (base, names) => Object.fromEntries(names.map(name => [name, fs.readFileSync(path.join(base, name), 'base64')]));
const legacy = Object.fromEntries(Object.entries(encode(root + '/node_modules/minimatch', Object.keys(inputs.legacy)))
  .map(([name, base64]) => ['node_modules/minimatch/' + name, { base64 }]));
const bash = Object.fromEntries(Object.entries(encode(root + '/node_modules/just-bash', Object.keys(inputs.justBash)))
  .map(([name, base64]) => ['node_modules/just-bash/' + name, { base64 }]));
console.log(JSON.stringify({ proof, delProof, files: encode('/tmp/prepared', Object.keys(proof.files)),
  del: encode('/tmp/del', ['index.js', 'package.json', 'license']),
  delIndex: fs.readFileSync('/tmp/del.modules.yaml', 'base64'), capture: { legacy, bash } }));
