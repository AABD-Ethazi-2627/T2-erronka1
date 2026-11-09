# Hono Node adapter: supported consumer update — 2026-11-04

This follows the [same-line patch set](KIBANA_CI_SAME_LINE_20261104.md). No final
image build/scan or Kibana-wide acceptance is asserted here. Scanner policy,
exceptions and the other remaining major-version dependencies are unchanged.

## Why this particular major is supported

The already selected `@modelcontextprotocol/sdk` **1.32.0** package declares
`@hono/node-server: ^1.19.9 || ^2.0.5`. Its actual CJS and ESM
`server/streamableHttp.js` load `getRequestListener` from that package. Thus
**2.1.3** is inside this consumer's supported range, rather than an arbitrary
replacement of an unsupported API generation.

The upstream adapter has no runtime dependencies and declares peer `hono: ^4`.
The final Dockerfile already installs Hono **4.13.11**. Adapter 2.1.3 requires
Node >=20; the pinned Kibana v9.5.5 source manifest declares Node **24.21.0**.
This is primary source metadata, not a newly executed vendor-binary version check.

The adapter is pinned as a new npm alias with registry SHA-512 integrity. No old
lock entries change. Docker removes the old adapter directory before copying
actual upstream 2.1.3 code, then runs the test below with Kibana's own Node and
actual final module tree. The build's separate transitive adapter installation
is not substituted for that explicitly selected runtime copy.

Primary sources:
- [MCP SDK 1.32.0 metadata](https://registry.npmjs.org/@modelcontextprotocol/sdk/1.32.0)
- [Adapter 2.1.3 metadata](https://registry.npmjs.org/@hono/node-server/2.1.3)
- [Kibana v9.5.5 manifest](https://github.com/elastic/kibana/blob/v9.5.5/package.json)
- [Official adapter fix](https://github.com/honojs/node-server/commit/982179278529d5673812116b042829f27794966f)
- [CVE-2026-118663 advisory](https://github.com/honojs/node-server/security/advisories/GHSA-rmxm-3fg6-px4f)

## Executed compatibility and security regression

The test uses an isolated exact-version npm fixture: adapter 2.1.3, Hono 4.13.11
and MCP SDK 1.32.0. Local Node is 26.13.0. In both **CJS and ESM** it:

- loads `getRequestListener` and handles an actual loopback HTTP health request;
- serves a normal filename containing an encoded space;
- preserves direct and percent-encoded protected-prefix authentication;
- rejects the advisory's malformed encoded-prefix request with 404;
- rejects an encoded parent traversal and never returns the outside-root sentinel;
- creates the real MCP `McpServer` and `StreamableHTTPServerTransport`, connects
  them, and completes an actual JSON-RPC initialize POST via the adapter listener.

The same fixture with adapter **1.19.17** fails the exploit assertion: the protected
static file is returned with HTTP 200 instead of 404. All listeners bind only to
loopback, requests have five-second timeouts, and fixture files/listeners are
cleaned up in `finally`. No real credentials or application data are involved.

Reproduction:

```sh
node deploy/images/kibana-patches/test-hono-node-server.js /absolute/pinned-fixture/node_modules
```

The Dockerfile invokes that script without a fixture argument, selecting
`/usr/share/kibana/node_modules`. This final-image run, the subsequent image scan
and the whole Kibana startup remain CI/integration gates. The fixture does not
prove every vendor importer or prebundled copy is compatible.

Also passed: 15 focused Python tests and 18 subtests, image inventory, JS syntax
and `git diff --check`. Evidence, exact fixtures, npm lock, old/fixed logs and the
read-only research report are under
`/home/tears/.cache/cnc-kibana-major-research-20261104/`.

## Remaining blockers

Glob 10.5.0 and Minimatch 3/9/10 still have the previously reported scanner findings.
No upgrade, backport or exception for them is implemented here. The official Glob
fix is small enough to investigate as an API-preserving backport; Minimatch 9/10
need preprocessing limits, while 3.1.5 lacks those particular preprocessing methods
and has a callable export incompatible with an unadapted 11.x replacement.
Actual nested importer resolution and an independent policy review are needed
before calling any broad-range finding inapplicable. Keep the current PR gated.
