// GHSA-mrwp-f3q8-3g9p: actual redirect, not a source-string assertion.
const assert = require('node:assert/strict');
const http = require('node:http');
const vm = require('node:vm');
const redirects = require(process.argv[2] || '/usr/share/kibana/node_modules/follow-redirects');
const listen = server => new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
(async () => {
  const target = http.createServer((req, res) => res.end(JSON.stringify(req.headers)));
  const source = http.createServer((req, res) => {
    res.writeHead(302, {location: `http://localhost:${target.address().port}/`});
    res.end();
  });
  try {
    await listen(target);
    await listen(source);
    for (const sensitiveHeaders of [['X-API-Key'], vm.runInNewContext("['X-API-Key']")]) {
      const headers = await new Promise((resolve, reject) => {
        redirects.http.get(`http://127.0.0.1:${source.address().port}/`, {
          sensitiveHeaders, headers: {'X-API-Key': 'test-secret', 'X-Public': 'keep'},
          lookup: (_host, opts, cb) => opts.all ? cb(null, [{address: '127.0.0.1', family: 4}]) : cb(null, '127.0.0.1', 4),
        }, res => {
          let body = '';
          res.on('data', data => body += data);
          res.on('end', () => resolve(JSON.parse(body)));
        }).on('error', reject).setTimeout(5000, function () { this.destroy(new Error('timeout')); });
      });
      assert.equal(headers['x-api-key'], undefined);
      assert.equal(headers['x-public'], 'keep');
    }
    console.log('follow-redirects: same/cross-realm credentials stripped; public header retained');
  } finally {
    source.close(); target.close();
  }
})().catch(error => { console.error(error); process.exitCode = 1; });
