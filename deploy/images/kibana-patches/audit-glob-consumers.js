// Read-only inventory of literal dependency references in the actual vendor tree.
// This is static evidence: computed imports and startup execution need separate checks.
const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');
const { createRequire } = require('node:module');
const assert = require('node:assert/strict');

const root = path.resolve(process.argv[2] || '/usr/share/kibana');
const targets = new Set(['glob', 'rimraf', 'minimatch']);
const report = { root, node: process.version, files: 0, bytes: 0, references: [], symlinks: [], packages: {} };
const hash = file => crypto.createHash('sha256').update(fs.readFileSync(file)).digest('hex');

function scan(file) {
  // Streaming bounds memory even for large generated bundles. The overlap covers
  // these short literal names and their surrounding diagnostic context.
  const fd = fs.openSync(file, 'r');
  const buffer = Buffer.alloc(128 * 1024);
  let tail = '', position = 0, length;
  const seen = new Set();
  try {
    while ((length = fs.readSync(fd, buffer, 0, buffer.length, position))) {
      const text = tail + buffer.toString('utf8', 0, length);
      const base = position - Buffer.byteLength(tail);
      const re = /["'](glob|rimraf|minimatch)(?:\/[^"'\s]{0,160})?["']/g;
      for (const match of text.matchAll(re)) {
        const offset = base + Buffer.byteLength(text.slice(0, match.index));
        if (seen.has(offset)) continue;
        seen.add(offset);
        const specifier = match[0].slice(1, -1);
        let resolved;
        try { resolved = createRequire(file).resolve(specifier); }
        catch (error) { resolved = error.code; }
        report.references.push({
          file: path.relative(root, file), offset, specifier, require_resolution: resolved,
          context: text.slice(Math.max(0, match.index - 90), match.index + match[0].length + 90),
        });
      }
      tail = text.slice(-512);
      position += length;
    }
    report.files++;
    report.bytes += position;
  } finally { fs.closeSync(fd); }
}

function walk(directory) {
  for (const entry of fs.readdirSync(directory, { withFileTypes: true })) {
    const file = path.join(directory, entry.name);
    if (entry.isSymbolicLink()) {
      report.symlinks.push({ file: path.relative(root, file), target: fs.readlinkSync(file) });
    } else if (entry.isDirectory()) walk(file);
    else if (entry.isFile() && /\.(?:cjs|mjs|js)$/.test(file)) scan(file);
    else if (entry.isFile() && entry.name === 'package.json') {
      const metadata = JSON.parse(fs.readFileSync(file, 'utf8'));
      if (targets.has(metadata.name)) report.packages[path.relative(root, file)] = {
        name: metadata.name, version: metadata.version, sha256: hash(file),
      };
    }
  }
}

walk(root);
const mm3 = path.join(root, 'node_modules/del/node_modules/minimatch/minimatch.js');
report.minimatch3_sha256 = hash(mm3);
if (process.argv.includes('--check-legacy-migration')) {
  const imports = report.references.filter(item =>
    /(?:require|import|__require)\s*\(\s*["'](?:glob|rimraf|minimatch)(?:\/[^"']*)?["']/.test(item.context) ||
    /\bfrom\s*["'](?:glob|rimraf|minimatch)(?:\/[^"']*)?["']/.test(item.context));
  const rootGlob = imports.filter(item => item.specifier === 'glob' &&
    item.require_resolution.startsWith(path.join(root, 'node_modules/glob/')));
  assert.deepEqual(rootGlob.map(item => item.file).sort(), [
    'node_modules/piscina/scripts/run-tests.js',
    'node_modules/rimraf/dist/commonjs/index.js',
    'node_modules/rimraf/dist/esm/index.js',
  ]);
  assert.equal(imports.filter(item => item.specifier === 'rimraf' &&
    item.require_resolution.startsWith(path.join(root, 'node_modules/rimraf/'))).length, 0);
  assert.deepEqual(imports.filter(item => item.specifier === 'minimatch' &&
    item.require_resolution === mm3).map(item => item.file).sort(), [
    'node_modules/del/node_modules/glob/common.js',
    'node_modules/del/node_modules/glob/glob.js',
    'node_modules/del/node_modules/glob/sync.js',
  ]);
  assert.equal(report.minimatch3_sha256, '746849f267c4868a53729225bd85c7dccd387712136fb305fcc0a3eadd4a3d9d');
  assert.equal(report.symlinks.length, 0, 'review any symlinked source before using this inventory');
  console.error(JSON.stringify({ checkedLegacyLiteralImports: true, files: report.files, bytes: report.bytes, node: report.node }));
}
console.log(JSON.stringify(report, null, 2));
