const fs = require('fs');

const root = '/patches/node_modules/extract-zip-patched';
const sourcePath = `${root}/index.js`;
const packagePath = `${root}/package.json`;
const before = `    const symlink = (mode & IFMT) === IFLNK
    let isDir = (mode & IFMT) === IFDIR`;
const after = `    const symlink = (mode & IFMT) === IFLNK
    if (symlink) {
      throw new Error(\`Refusing symbolic link archive entry: \${entry.fileName}\`)
    }
    let isDir = (mode & IFMT) === IFDIR`;

const source = fs.readFileSync(sourcePath, 'utf8');
if (source.split(before).length !== 2 || source.includes(after)) {
  throw new Error('unexpected extract-zip index.js; refusing an ambiguous patch');
}
fs.writeFileSync(sourcePath, source.replace(before, after));

const metadata = JSON.parse(fs.readFileSync(packagePath, 'utf8'));
if (metadata.version !== '2.0.1') {
  throw new Error(`unexpected extract-zip version: ${metadata.version}`);
}
metadata.version = '2.0.1+cncguard.1';
fs.writeFileSync(packagePath, `${JSON.stringify(metadata, null, 2)}\n`);
