# Bounded Kibana CI remediation — 2026-11-04

Based on the failed PR119 image scan at `6c5a056`. No image build, final scan,
Kibana startup, browser test, push or merge was performed in this follow-up.
The scanner gate and its exceptions remain unchanged. This is partial remediation.

## Same-line upstream replacements

| Package | Old → new | Findings addressed by the upstream release |
| --- | --- | --- |
| systeminformation | 5.33.8 → 5.33.16 | CVE-2026-116576, CVE-2026-116673, CVE-2026-116674 |
| re2js (root copy) | 2.8.5 → 2.8.7 | CVE-2026-116795 |
| decode-uri-component | 0.5.0 → 0.5.1 | CVE-2026-118664 |
| joi | 18.2.9 → 18.3.1 | CVE-2026-118772 |
| @hapi/content | 6.0.2 → 6.0.3 | CVE-2026-119202 |

The npm aliases are exact and the lock contains registry SHA-512 integrity.
Existing lock entries retain their versions except decode-uri-component. The
Dockerfile removes each old package directory before copying actual upstream
package bytes, preventing removed files from surviving a directory COPY.
It runs the regression script with Kibana's bundled Node against the final paths.

The retained scan's nested `just-bash/node_modules/re2js` is **1.4.0**, outside the
advisory's affected range starting at 2.2.0. It is left unchanged; replacing it with
2.x would be an unnecessary major upgrade. This corrects the earlier bounded
report's statement that both copies needed the same fix.

Primary references:
[systeminformation advisory](https://github.com/sebhildebrandt/systeminformation/security/advisories/GHSA-3f7j-7jwc-fxfj),
[re2js advisory](https://github.com/le0pard/re2js/security/advisories/GHSA-gg6h-894w-4m9c),
[decode-uri-component advisory](https://github.com/SamVerschueren/decode-uri-component/security/advisories/GHSA-qr28-fpjm-wq7f),
[Joi advisory](https://github.com/hapijs/joi/security/advisories/GHSA-4528-x5fx-h6hg),
[content advisory](https://github.com/hapijs/content/security/advisories/GHSA-8494-f6mr-cjpv).

## Dependency closure

Old and new dependency declarations are identical for each of the five packages.
Systeminformation, re2js and decode-uri-component have no runtime dependencies.
For Joi and content the retained vendor scan contains compatible root dependencies:

| Installed vendor dependency | Version |
| --- | --- |
| @hapi/address | 5.1.1 |
| @hapi/boom | 10.0.1 |
| @hapi/formula | 3.0.2 |
| @hapi/hoek | 11.0.7 |
| @hapi/pinpoint | 2.0.1 |
| @hapi/tlds | 1.1.7 |
| @hapi/topo | 6.0.2 |
| @standard-schema/spec | 1.1.0 |

No dependency COPY is therefore required for these updates. The regressions were
also run in a separate npm fixture using exactly these dependency versions and
only the five replacement package directories. This checks version compatibility;
it is not a byte comparison or execution of the vendor image's own dependencies.
The Dockerfile tests are still required to verify the actual final image closure.

## Verification performed

Local Node 26.13.0 / npm 11.20.0:

- Locked npm install passed with lifecycle scripts disabled.
- Five real-package regressions and ordinary-input controls pass, both against the
  alias tree and the fixture with the vendor dependency versions above.
- The Windows services test executes the real systeminformation Windows branch in
  a VM with PowerShell intercepted. Unicode-quote inputs stay inside the permitted
  service-name filter. No PowerShell command or real Windows runtime was used.
- Re2js repeated lookbehind matching, malformed URI decoding, multiple-email
  validation and Content-Disposition parsing run in child processes with a five
  second bound. The large inputs complete under that bound on patched packages.
- A/B checks against the exact vulnerable versions: systeminformation fails the
  filter assertion; the other four exceed the five-second bound. Their processes
  are terminated, rather than leaving an unbounded reproduction running.
- 15 focused Python tests and 18 subtests pass (`test_dependency_infra` and
  `test_image_scan_gate`). Image inventory, JS syntax and `git diff --check` pass.

These tests do not independently reproduce every systeminformation advisory and
do not establish Kibana-wide compatibility or removal of inlined browser copies.
The optional source-preparation helper still covers its earlier two reviewed
updates; it is not a complete source-build pipeline for this larger patch set.

Raw logs, both npm fixtures, upstream fix metadata and the vendor version inventory:
`/home/tears/.cache/cnc-kibana-ci-20261104/`.

## Remaining CI blockers

The old scan requires these further major-version fixes:

- @hono/node-server 1.19.17 → 2.1.3 (CVE-2026-118663).
- glob 10.5.0 → 14.0.2 (CVE-2026-118773).
- minimatch 3.1.5, 9.0.9 and 10.2.4 → 11.0.1 (CVE-2026-118764).

These five package findings are not closed here. Existing consumers include
different CommonJS/ESM export shapes and API generations; silently substituting
the newest major into each directory is not a compatible fix. Source backports
or an upstream/source-build dependency reconciliation need their own consumer
tests. Prebundled assets and final image scan/startup remain additional gates.
Keep the PR blocked until its actual current-head checks and required review pass.
