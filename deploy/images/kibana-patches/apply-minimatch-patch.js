// Backport only the official preprocessing bounds; preserve the 10.x public API.
const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');

const root = path.resolve(process.argv[2] || '/patches/node_modules/minimatch-v10');
const sha = bytes => crypto.createHash('sha256').update(bytes).digest('hex');
const inputs = {
  'dist/commonjs/index.js': '3736296f8c1f937821b202626138bcf36163e2ee172ba6a6943dfcf332f4ed96',
  'dist/esm/index.js': '0784807c19502b32ec76d2a59ccdc20927879b71003f75f3731267feee506252',
};
const metadata = JSON.parse(fs.readFileSync(path.join(root, 'package.json'), 'utf8'));
if (metadata.name !== 'minimatch' || metadata.version !== '10.2.4') {
  throw new Error('expected unmodified minimatch 10.2.4');
}
const replacements = [
  ['firstPhasePreProcess(globParts) {',
    'firstPhasePreProcess(globParts) {\n        const { braceExpandMax = 100000 } = this.options;'],
  ["p2 === '..') {", "p2 === '..' ||\n                        globParts.length >= braceExpandMax) {"],
  ['secondPhasePreProcess(globParts) {',
    'secondPhasePreProcess(globParts) {\n        if (globParts.length > 1000) return globParts;'],
];
const updates = {};
// Validate both formats and every context before writing either format.
for (const [relative, expected] of Object.entries(inputs)) {
  const bytes = fs.readFileSync(path.join(root, relative));
  if (sha(bytes) !== expected) throw new Error(`unexpected source hash: ${relative}`);
  let text = bytes.toString('utf8');
  for (const [before, after] of replacements) {
    if (text.split(before).length !== 2) throw new Error(`ambiguous context: ${relative}: ${before}`);
    text = text.replace(before, after);
  }
  // Generated mappings no longer describe the modified JS. Drop those two maps
  // and their references rather than leaving misleading original source/debug data.
  text = text.replace(/\/\/# sourceMappingURL=index\.js\.map\s*$/, '');
  updates[relative] = text;
}
const outputs = {};
for (const [relative, text] of Object.entries(updates)) {
  const target = path.join(root, relative);
  fs.writeFileSync(target, text);
  fs.rmSync(target + '.map', { force: true });
  outputs[relative] = sha(Buffer.from(text));
}
metadata.version = '10.2.4+cncguard.1';
metadata.cncguardSecurityPatch = {
  advisory: 'GHSA-g3hv-75wg-m249',
  upstreamCommit: '77a0f5c4b80bdc641c3c930a1d9edf5ad2db57f8',
  scope: 'official default 100000 preprocessing cap and phase-2 limit; API unchanged',
  inputs, outputs,
};
fs.writeFileSync(path.join(root, 'package.json'), JSON.stringify(metadata, null, 2) + '\n');
console.log(JSON.stringify(metadata.cncguardSecurityPatch));
