const fs = require('fs');
const path = require('path');
const root = process.argv[2] || path.join(__dirname, 'node_modules/deepmerge-patched');
const metadataPath = path.join(root, 'package.json');
const metadata = JSON.parse(fs.readFileSync(metadataPath, 'utf8'));
if (metadata.version !== '4.3.1') throw new Error('Unexpected deepmerge base version');
for (const name of ['index.js', 'dist/cjs.js', 'dist/umd.js']) {
  const file = path.join(root, name);
  const source = fs.readFileSync(file, 'utf8');
  let count = 0;
  const patched = source.replace(/destination\[key\] = ([^\n]+?);?$/gm, (_, value) => {
    count++;
    return `Object.defineProperty(destination, key, { value: ${value}, enumerable: true, writable: true, configurable: true });`;
  });
  if (count !== 3 || patched.includes('destination[key] =')) throw new Error(`Unexpected deepmerge source: ${name}`);
  fs.writeFileSync(file, patched);
}
// This is a local fork version, not an upstream release or a metadata-only fix.
metadata.version = '4.3.2-cncguard.1';
metadata.cncguardBackport = { baseVersion: '4.3.1', advisory: 'CVE-2026-93753', fix: 'Define own data properties in every mergeObject write; never invoke prototype setters' };
fs.writeFileSync(metadataPath, JSON.stringify(metadata, null, 2) + '\n');
