const fs = require('fs');

const rsaPath = '/usr/share/kibana/node_modules/node-forge/lib/rsa.js';
const packagePath = '/usr/share/kibana/node_modules/node-forge/package.json';
const before = `if(!asn1.validate(obj, digestInfoValidator, capture, errors) ||
            obj.value.length !== 2) {`;
const after = `if(!asn1.validate(obj, digestInfoValidator, capture, errors) ||
            obj.value.length !== 2 ||
            obj.value[0].value.length !==
              (('parameters' in capture) ? 2 : 1)) {`;

const source = fs.readFileSync(rsaPath, 'utf8');
if (source.split(before).length !== 2 || source.includes(after)) {
  throw new Error('unexpected node-forge rsa.js; refusing an ambiguous patch');
}
fs.writeFileSync(rsaPath, source.replace(before, after));

const metadata = JSON.parse(fs.readFileSync(packagePath, 'utf8'));
if (metadata.version !== '1.4.0') {
  throw new Error(`unexpected node-forge version: ${metadata.version}`);
}
metadata.version = '1.4.0+cncguard.1';
fs.writeFileSync(packagePath, `${JSON.stringify(metadata, null, 2)}\n`);

const patched = fs.readFileSync(rsaPath, 'utf8');
if (!patched.includes(after) || patched.includes(before)) {
  throw new Error('node-forge CVE-2026-85393 backport verification failed');
}
