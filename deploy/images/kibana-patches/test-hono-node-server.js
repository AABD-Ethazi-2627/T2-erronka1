// Actual MCP 1.32 consumer and Hono static-path security checks over loopback.
// Run with the final image Node against its real node_modules, or a pinned fixture.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const http = require('node:http');
const os = require('node:os');
const path = require('node:path');
const { createRequire } = require('node:module');
const { pathToFileURL } = require('node:url');
const root = path.resolve(process.argv[2] || '/usr/share/kibana/node_modules');
const localRequire = createRequire(path.join(root, 'package.json'));
const load = async (name, esm, mode) => mode === 'cjs' ? localRequire(name) : import(pathToFileURL(path.join(root, esm)));

function request(server, method, target, body) {
  return new Promise((resolve, reject) => {
    const raw = body === undefined ? undefined : JSON.stringify(body);
    const req = http.request({
      host: '127.0.0.1', port: server.address().port, path: target, method,
      headers: { connection: 'close', accept: 'application/json, text/event-stream',
        ...(raw ? { 'content-type': 'application/json', 'content-length': Buffer.byteLength(raw) } : {}) },
    }, res => {
      let text = '';
      res.setEncoding('utf8');
      res.on('data', chunk => { text += chunk; });
      res.on('end', () => resolve({ status: res.statusCode, text }));
      res.on('error', reject);
    });
    req.setTimeout(5000, () => req.destroy(new Error('loopback request timeout')));
    req.on('error', reject);
    req.end(raw);
  });
}

(async () => {
  const originalCwd = process.cwd();
  const fixture = fs.mkdtempSync(path.join(os.tmpdir(), 'cnc-hono-regression-'));
  try {
    fs.mkdirSync(path.join(fixture, 'static/admin'), { recursive: true });
    fs.writeFileSync(path.join(fixture, 'static/admin/secret.txt'), 'private-sentinel');
    fs.writeFileSync(path.join(fixture, 'static/hello world.txt'), 'public-control');
    fs.writeFileSync(path.join(fixture, 'outside.txt'), 'outside-root-sentinel');
    process.chdir(fixture);
    for (const mode of ['cjs', 'esm']) {
      const { Hono } = await load('hono', 'hono/dist/index.js', mode);
      const { getRequestListener } = await load('@hono/node-server', '@hono/node-server/dist/index.mjs', mode);
      const { serveStatic } = await load('@hono/node-server/serve-static', '@hono/node-server/dist/serve-static.mjs', mode);
      const { McpServer } = await load('@modelcontextprotocol/sdk/server/mcp.js', '@modelcontextprotocol/sdk/dist/esm/server/mcp.js', mode);
      const { StreamableHTTPServerTransport } = await load('@modelcontextprotocol/sdk/server/streamableHttp.js', '@modelcontextprotocol/sdk/dist/esm/server/streamableHttp.js', mode);
      const mcp = new McpServer({ name: 'local-compatibility-test', version: '1.0.0' });
      const transport = new StreamableHTTPServerTransport({ sessionIdGenerator: undefined, enableJsonResponse: true });
      await mcp.connect(transport);
      const app = new Hono();
      app.get('/health', c => c.text('listener-control'));
      app.use('/static/admin/*', c => c.text('Unauthorized', 401));
      app.use('/static/*', serveStatic({ root: '.' }));
      const listener = getRequestListener(app.fetch, { overrideGlobalObjects: false });
      const server = http.createServer((req, res) => {
        if (req.url === '/mcp') transport.handleRequest(req, res).catch(error => { res.statusCode = 500; res.end(String(error)); });
        else listener(req, res);
      });
      try {
        await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
        assert.deepEqual(await request(server, 'GET', '/health'), { status: 200, text: 'listener-control' });
        assert.deepEqual(await request(server, 'GET', '/static/hello%20world.txt'), { status: 200, text: 'public-control' });
        for (const target of ['/static/admin/secret.txt', '/static/%61dmin/secret.txt']) {
          assert.equal((await request(server, 'GET', target)).status, 401);
        }
        // GHSA-rmxm-3fg6-px4f: the routing and static-file resolver must agree.
        const bypass = await request(server, 'GET', '/static/%%36%31dmin/secret.txt');
        assert.equal(bypass.status, 404);
        assert.notEqual(bypass.text, 'private-sentinel');
        const traversal = await request(server, 'GET', '/static/%2e%2e/outside.txt');
        assert.notEqual(traversal.status, 200);
        assert.notEqual(traversal.text, 'outside-root-sentinel');
        const initialized = await request(server, 'POST', '/mcp', {
          jsonrpc: '2.0', id: 1, method: 'initialize', params: {
            protocolVersion: '2025-06-18', capabilities: {}, clientInfo: { name: 'local-probe', version: '1.0.0' },
          },
        });
        assert.equal(initialized.status, 200, initialized.text);
        const reply = JSON.parse(initialized.text);
        assert.equal(reply.id, 1);
        assert.equal(reply.result.serverInfo.name, 'local-compatibility-test');
        console.log(mode + ': listener HTTP, MCP initialize, encoded-file controls and static security checks passed');
      } finally {
        await mcp.close();
        server.closeAllConnections();
        await new Promise(resolve => server.close(resolve));
      }
    }
  } finally {
    process.chdir(originalCwd);
    fs.rmSync(fixture, { recursive: true, force: true });
  }
})().catch(error => { console.error(error); process.exitCode = 1; });
