// Optional source-build preparation; NOT proof that vendor bundles were rebuilt.
// Scope deliberately limited to the two reviewed, regression-tested updates.
const fs = require('node:fs');
const path = require('node:path');
const root = process.argv[2];
if (!root) throw new Error('Usage: node prepare-reviewed-source.js PINNED_KIBANA_SOURCE');
const file = path.join(root, 'package.json');
const workspaceFile = path.join(root, 'pnpm-workspace.yaml');
const project = JSON.parse(fs.readFileSync(file));
let workspace = fs.readFileSync(workspaceFile, 'utf8');
if (project.version !== '9.5.5') throw new Error('Expected Kibana 9.5.5');
if (workspace.split('  # END GENERATED OVERRIDES').length !== 2) throw new Error('Missing/ambiguous overrides boundary');
project.resolutions ||= {};
for (const [name, version] of Object.entries({'follow-redirects': '1.16.2', 'node-forge': '1.4.1'})) {
  const pattern = new RegExp(`^  '${name}':.*$`, 'gm');
  const count = [...workspace.matchAll(pattern)].length;
  if (count > 1) throw new Error(`Ambiguous override: ${name}`);
  workspace = count === 1
    ? workspace.replace(pattern, `  '${name}': '${version}'`)
    : workspace.replace('  # END GENERATED OVERRIDES', `  '${name}': '${version}'\n  # END GENERATED OVERRIDES`);
  project.resolutions[name] = version;
  for (const group of ['dependencies', 'devDependencies']) {
    if (project[group]?.[name]) project[group][name] = version;
  }
}
// Validate everything before writing either input. Lock regeneration/build remain required.
fs.writeFileSync(file, JSON.stringify(project, null, 2) + '\n');
fs.writeFileSync(workspaceFile, workspace);
