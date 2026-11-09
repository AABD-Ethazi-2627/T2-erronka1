'use strict';
// Conservative byte inventory: no syntax classifier, extension or UTF-8 gaps.
const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');
const zlib = require('node:zlib');
const { createRequire } = require('node:module');
const hash = b => crypto.createHash('sha256').update(b).digest('hex');

function inventory(root) {
  const tree = crypto.createHash('sha256');
  const report = { files: 0, bytes: 0, treeSha256: '', legacy: {}, references: [], declarations: [], compressed: [] };
  const legacy = 'node_modules/del/';
  function references(relative, text, base = 0, seen = new Set()) {
    const pattern = /['"`](del(?:\/[^'"`\r\n]{0,512})?)['"`]|del[\\/]+node_modules[\\/]/g;
    for (const m of text.matchAll(pattern)) {
      const offset = base + m.index;
      if (seen.has(offset)) continue;
      seen.add(offset);
      report.references.push({ file: relative, offset, specifier: m[1] || m[0],
        context: text.slice(Math.max(0, m.index - 70), m.index + m[0].length + 70) });
    }
  }
  function walk(directory) {
    for (const name of fs.readdirSync(directory).sort()) {
      const file = path.join(directory, name), relative = path.relative(root, file);
      const stat = fs.lstatSync(file);
      if (stat.isSymbolicLink()) throw new Error(`review symlink: ${relative}`);
      if (stat.isDirectory()) { walk(file); continue; }
      if (!stat.isFile()) throw new Error(`review non-file: ${relative}`);
      const h = crypto.createHash('sha256'), fd = fs.openSync(file, 'r');
      const buffer = Buffer.alloc(128 * 1024), seen = new Set();
      let position = 0, length, tail = '';
      try {
        while ((length = fs.readSync(fd, buffer, 0, buffer.length, position))) {
          const chunk = buffer.subarray(0, length);
          h.update(chunk);
          const text = tail + chunk.toString('latin1');
          references(relative, text, position - tail.length, seen);
          tail = text.slice(-2048);
          position += length;
        }
      } finally { fs.closeSync(fd); }
      const sha256 = h.digest('hex');
      tree.update(`${relative}\0${stat.mode & 0o777}\0${position}\0${sha256}\n`);
      if (relative.startsWith(legacy)) report.legacy[relative.slice(legacy.length)] = sha256;
      report.files++; report.bytes += position;
      if (/\.(gz|br)$/.test(name)) {
        const packed = fs.readFileSync(file);
        const text = (name.endsWith('.gz') ? zlib.gunzipSync : zlib.brotliDecompressSync)(packed,
          { maxOutputLength: 32 * 1024 * 1024 }).toString('latin1');
        report.compressed.push({ file: relative, unpackedSha256: hash(text) });
        references(`${relative}:unpacked`, text);
      }
      if (name === 'package.json') {
        const metadata = JSON.parse(fs.readFileSync(file, 'utf8'));
        for (const section of ['dependencies', 'optionalDependencies', 'peerDependencies', 'devDependencies']) {
          for (const [dependency, range] of Object.entries(metadata[section] || {})) {
            if (!['del', 'rimraf', 'glob', 'minimatch', 'brace-expansion'].includes(dependency)) continue;
            let resolution;
            try { resolution = path.relative(root, createRequire(file).resolve(`${dependency}/package.json`)); }
            catch (error) { resolution = error.code; }
            if (dependency === 'del' || resolution.startsWith(`${legacy}node_modules/`)) {
              report.declarations.push({ file: relative, section, dependency, range, resolution });
            }
          }
        }
      }
    }
  }
  walk(root);
  report.treeSha256 = tree.digest('hex');
  report.references.sort((a, b) => a.file.localeCompare(b.file) || a.offset - b.offset);
  return report;
}
function fingerprint(report) {
  const { files, bytes, treeSha256, legacy, declarations } = report;
  return { files, bytes, treeSha256, legacy, declarations,
    referenceCount: report.references.length, compressedCount: report.compressed.length };
}
module.exports = { inventory, fingerprint, hash };
if (require.main === module) console.log(JSON.stringify(inventory(path.resolve(process.argv[2])), null, 2));
