# Bounded image follow-up (2026-11-03)

Local candidate only, based on 83c9496. No image builds, lab, push, scanner
exceptions, gate changes or permissions bypass. Final image/scan/startup pending.

## Implemented Kibana candidates

- follow-redirects 1.16.1 -> 1.16.2, exact npm alias + SHA-512 lock integrity.
  CVE-2026-116689 / [upstream advisory](https://github.com/follow-redirects/follow-redirects/security/advisories/GHSA-mrwp-f3q8-3g9p).
  Axios 1.20.0 declares ^1.16.0, so this satisfies the actual consumer's range.
  The scanner identifies node_modules/follow-redirects/package.json.
- node-forge 1.4.0+cncguard.1 -> upstream 1.4.1, exact npm alias + SHA-512.
  Replace the whole old package directory, including its shipped dist files;
  retire execution of the old backport but retain its RSA regression.
  Kibana v9.5.5 package.json directly requires node-forge 1.4.0.
  Scanner identifies node_modules/node-forge/package.json.
  [Upstream deprecated-OID advisory](https://github.com/digitalbazaar/forge/security/advisories/GHSA-5x38-2vff-x55p).
  Scan-listed 1.4.1 fixes: CVE-2026-118775, 118777, 118778, 118779,
  118780, 118781, 118782, 119186, 119187, 119188, 119190.
  This is a candidate for that set, not individual exploit coverage for all eleven.

Local Node 26.13.0 tests: same/cross-realm redirect strips custom credentials while
retaining ordinary headers; fails on 1.16.1 with actual leaked test header.
Forge valid chain and SHA256 signature succeed; both deprecated OIDs fail;
1.4.0 fails this regression by accepting the invalid chain. Existing RSA
CVE-2026-85393 vector passes with 1.4.1. Dockerfile runs these tests again with
Kibana's own Node during CI. Tests accept an explicit package path for A/B runs.

These replacements do NOT rebuild Kibana's existing webpack/compressed assets.
No closure claim for inlined copies. The old dirty worktree's source-preparation
and recursive backport scripts were read only; not promoted wholesale.
`prepare-reviewed-source.js SOURCE` prepares only these two reviewed pins in
Kibana 9.5.5 root package and pnpm overrides before a future source build. Tested
on downloaded v9.5.5 manifests and fixtures (missing boundary fails before writes,
repeat application succeeds). It does not regenerate a lock or build assets.
A complete immutable source-build path remains unresolved: parent must pin the
source archive, Node/pnpm toolchains and regenerated lock, then build on a
provisioned runner and compare runtime/browser behavior. Do not replace the final
image with an unverified source build or treat preparation as a completed build.

Remaining scan blockers: systeminformation 5.33.8 (116576/116674/116673),
re2js 2.8.5 (116795; BOTH root and just-bash/node_modules copies),
decode-uri-component 0.5.0 (118664), @hapi/content 6.0.2 (119202),
joi 18.2.9 (118772), @hono/node-server 1.19.17 (118663),
minimatch 3/9/10 (118764), glob 10.5.0 (118773). Numbers here use CVE-2026- prefix.
No major-version replacement was attempted. Existing extract-zip findings and
accepted gate policy are unchanged. Browser bundle closure remains open.

## Filebeat: diagnosis isolated, not repaired

Read full #116 image log. apk updates eleven packages, then reports
`krb5-conf-1.0-r10: Permission denied`; continues other packages and exits 1.
The same log shows ES/Kibana successfully updating the same package. This does
not establish a filesystem mode problem or a signature problem.

Official sources inspected:
- https://github.com/elastic/beats/blob/v9.5.5/dev-tools/packaging/templates/docker/Dockerfile.tmpl
- https://github.com/wolfi-dev/os/blob/main/krb5-conf.yaml

Wolfi recipe installs static /etc/krb5.conf. Current package URL responds HTTP 200;
its decoded tar contains root-owned etc (0755), etc/krb5.conf (0644), and SBOM,
with no install script. This is source/package evidence, NOT actual Filebeat base
filesystem evidence. No local Filebeat/Kibana image is present; downloading/building
large images was excluded. Actual base permissions and original runner response
remain unknown. Do not infer chmod or disable signature verification from EACCES.

Added `filebeat-base` and `filebeat-os` targets so CI can inspect base permissions,
package ownership and verbose apk failure independently of Go compilation.
`filebeat-runtime` inherits the same vendor base and updated OS; final USER 1000,
entrypoint and binary replacement remain intact. Diagnostics preserve failure;
no ignored apk errors, retry masking, chmod, or trust-policy edits.

## Parent CI commands (not executed locally)

```sh
docker build --progress=plain --target filebeat-os -f deploy/images/filebeat.Dockerfile -t cnc-guard-audit:filebeat-os .
docker build --progress=plain -f deploy/images/filebeat.Dockerfile -t cnc-guard-audit:filebeat .
docker build --progress=plain -f deploy/images/kibana.Dockerfile -t cnc-guard-audit:kibana .
trivy image --scanners vuln --list-all-pkgs --format json --output kibana-scan.json cnc-guard-audit:kibana
python -m scripts.enforce_image_scan kibana kibana-scan.json
trivy image --scanners vuln --list-all-pkgs --format json --output filebeat-scan.json cnc-guard-audit:filebeat
python -m scripts.enforce_image_scan filebeat filebeat-scan.json
```

Keep PR119's full checks blocking. Then run Kibana startup against ES, dashboard
rendering and relevant HTTP/TLS consumers; Filebeat config/startup and Kafka
publishing belong to integration acceptance, not these package tests.
