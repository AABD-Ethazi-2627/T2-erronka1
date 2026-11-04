// Upstream advisory regressions against real package code. Each potentially slow
// input runs in its own bounded process, so a vulnerable version cannot hang CI.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const { createRequire } = require('node:module');
const { spawnSync } = require('node:child_process');
const { pathToFileURL } = require('node:url');

const root = process.argv[2] || '/usr/share/kibana/node_modules';
const aliases = process.argv.includes('--aliases');
const packages = {
  systeminformation: aliases ? 'systeminformation-patched' : 'systeminformation',
  re2js: aliases ? 're2js-patched' : 're2js',
  decode: aliases ? 'decode-uri-component-patched' : 'decode-uri-component',
  joi: aliases ? 'joi-patched' : 'joi',
  content: aliases ? 'hapi-content-patched' : '@hapi/content',
};

async function check(name) {
  const directory = path.resolve(root, packages[name]);
  if (name === 'decode') {
    const decode = (await import(pathToFileURL(path.join(directory, 'index.js')))).default;
    assert.equal(decode('hello%20world'), 'hello world');
    assert.equal(decode('%25%41%zz'), '%A%zz');
    let input = '';
    for (let i = 0; i < 32000; i++) {
      input += '%' + (i >> 8).toString(16).padStart(2, '0') + '%' + (i & 255).toString(16).padStart(2, '0') + 'x';
    }
    assert.ok(decode(input + '%zz').endsWith('%zz'));
  } else if (name === 're2js') {
    const { RE2JS } = require(path.join(directory, 'build/index.cjs'));
    const expression = RE2JS.compile('(?<=a)b', RE2JS.LOOKBEHINDS);
    const matcher = expression.matcher('ab'.repeat(16000));
    let matches = 0;
    while (matcher.find()) matches++;
    assert.equal(matches, 16000);
    assert.equal(RE2JS.compile('ab').matches('ab'), true);
  } else if (name === 'joi') {
    const joi = require(directory);
    const schema = joi.string().email({ multiple: true, tlds: false });
    assert.equal(schema.validate('a@example.com, b@example.com').error, undefined);
    assert.ok(schema.validate('a' + ' '.repeat(256000) + 'b@example.com').error);
  } else if (name === 'content') {
    const content = require(directory);
    assert.deepEqual(content.disposition('form-data; name="field"; filename="file.csv"'), { name: 'field', filename: 'file.csv' });
    assert.deepEqual(content.disposition('form-data; ' + 'a'.repeat(256000) + '; name="field"'), { name: 'field' });
  } else if (name === 'systeminformation') {
    // Exercise the actual Windows services branch while intercepting PowerShell;
    // this test never invokes a shell or claims a real Windows runtime check.
    const file = path.join(directory, 'lib/processes.js');
    const localRequire = createRequire(file);
    const util = localRequire('./util');
    const commands = [];
    util.powerShell = async command => { commands.push(command); return ''; };
    const module = { exports: {} };
    const fakeProcess = new Proxy(process, {
      get: (target, key) => key === 'platform' ? 'win32' : Reflect.get(target, key),
    });
    vm.runInNewContext(fs.readFileSync(file, 'utf8'), {
      module, exports: module.exports, require: localRequire, process: fakeProcess,
      console, Buffer, setTimeout, clearTimeout,
    }, { filename: file });
    for (const input of ['Spooler', 'svc\u2019; Write-Output marker; #', 'svc\u201d; Write-Output marker; #']) {
      await module.exports.services(input);
    }
    assert.equal(commands.length, 3);
    assert.ok(commands[0].includes("Name='spooler'"));
    for (const command of commands) {
      assert.match(command, /^Get-CimInstance Win32_Service -Filter "Name='[a-z0-9 _.@-]*'" \| select Name,Caption,Started,StartMode,ProcessId \| fl$/);
    }
  } else {
    throw new Error('Unknown regression: ' + name);
  }
  console.log(name + ': real package controls and advisory regression passed');
}

if (process.argv[3] === '--case') {
  check(process.argv[4]).catch(error => { console.error(error); process.exitCode = 1; });
} else {
  for (const name of Object.keys(packages)) {
    const args = [__filename, root, '--case', name];
    if (aliases) args.push('--aliases');
    const result = spawnSync(process.execPath, args, { encoding: 'utf8', timeout: 5000 });
    assert.equal(result.error, undefined, name + ': bounded regression failed: ' + result.error);
    assert.equal(result.status, 0, name + ': ' + result.stderr);
    process.stdout.write(result.stdout);
  }
}
