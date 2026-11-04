# Dependency reconciliation, 2026-11-03

Base c34cabe; local implementation only. **Remediation is incomplete.** No push,
PR, deployment, or full lab acceptance. The parent must combine the backend commit
c7adef8 before building its integrated API. No application modules were imported.

## Implemented and verified locally

- Runtime closure includes the existing exact DuckDB 2.0.0, PyArrow 23.0.1 and
  httpx 0.28.1 pins. The scoring image copies `scripts/duckdb_output.py` and all
  scoring modules. Runtime export includes transitive hashes.
- Pydantic 2.14.2 brings pydantic-core 2.50.2; tzdata is 2026.6 in the canonical
  uv lock and serving export. Scientific pins remain unchanged.
- setup-uv action updated to the immutable 10.3.3 commit in five workflows.
  Rust 1.99.1 and Wolfi 88a20e2 image references reconciled across active build
  files/inventory. Upstream uv source still selects its own Rust toolchain.
- HAProxy 3.4 digest reconciled in inventory and LAN image pin only; no service
  wiring changes. Actual image `haproxy -vv` succeeded. Trivy 0.76.1 scanned it,
  and `scripts.enforce_image_scan haproxy` passed with the resulting JSON.
- New `scripts.check_runtime_image IMAGE` runs imports, Parquet/JSON query and
  timestamp conversion in Docker with no network, read-only root, 512 MiB memory
  (including swap limit), one CPU and 64 MiB tmpfs. CI invokes it for the API.
  Probe passes in the Python venv; **the container probe has not yet run**.
- Recovered only `scripts/expose_nested_jars.py` and its tests from the old dirty
  worktree. Added a NiFi audit-only stage and strict nested archive scan gate.
  Runtime classpath and Wire ABI are unchanged; no new vulnerability exceptions.

## Actual upstream failures and disposition of #112–#118

| PR | Disposition |
| --- | --- |
| #112 | HAProxy update absorbed with missing inventory change. Remote LAN failure was an assertion comparing inventory 3.2 against Compose 3.4. Local TLS rotation still failed to start within its 20-second deadline; cleanup then masked that with Docker stop failure. Not TLS-accepted. |
| #113 | setup-uv action update absorbed. |
| #114 | Rust base update absorbed in every shared uv stage, not just scoring. Final build pending. |
| #115 | Wolfi digest update absorbed across inventory/build copies. Final build pending. |
| #116 | Rejected PyArrow 26: downloaded Python 3.11/3.12 CI logs show `ImportError: pyarrow requires NumPy 2.0 or newer, found 1.26.4`. Keep 23.0.1 rather than silently changing the trained-model numerical environment. |
| #117 | Pydantic runtime update superseded by canonical lock + regenerated export, including core. Independent dashboard requirements were not changed here. |
| #118 | tzdata runtime update superseded by canonical lock + regenerated export. Independent dashboard and sealed research exports were not changed here. |

Five PRs changed generated requirements without reconciling the canonical closure;
main itself was not stale. Export now matches **both uv 0.13.6 (CI pin) and local
0.13.7 exactly**, and `uv 0.13.6 lock --check` passes.

#116 Filebeat failed before scanning: `apk upgrade` reported
`ERROR: krb5-conf-1.0-r10: Permission denied`. Do not describe that run as a CVE
scan failure. Its cause still needs reproduction on a runner; no speculative
permission bypass or retry masking has been added.

## Elasticsearch candidate, not verified remediation

Inspected the real pinned base image offline. OpenTelemetry API/context/common
1.62.0 appear in `modules/apm`, `modules/esql-datasource-gcs`, and
`modules/repository-gcs`. Dockerfile now replaces actual JAR bytes in all three
locations with SHA-256-pinned 1.67.0 artifacts from Maven Central, checking the
expected originals exist. SDK/instrumentation remain vendor versions. Requires
final image scan and startup/query compatibility testing before acceptance.

Official advisory: https://github.com/open-telemetry/opentelemetry-java/security/advisories/GHSA-ccrj-gw8r-854m
identifies API <=1.66.0 as affected and 1.67.0 as fixed. Downloaded artifact hashes
are embedded in the Dockerfile. This is not a metadata-only version rewrite.

## Unresolved Kibana and old Wire patches

Downloaded the actual #118 `image-kibana` scan artifact. Findings include
systeminformation 5.33.8, follow-redirects 1.16.1, re2js 2.8.5, @hono/node-server
1.19.17, decode-uri-component 0.5.0, minimatch 3/9/10, joi 18.2.9, glob 10.5.0,
node-forge 1.4.0+cncguard.1 and @hapi/content 6.0.2. Several fixed versions require
major changes (glob 14, minimatch 11, node-server 2), so blanket file replacement
would not establish compatibility or repair prebundled browser assets.

Official forge advisory confirms 1.4.1 fixes the deprecated-OID bypass:
https://github.com/digitalbazaar/forge/security/advisories/GHSA-5x38-2vff-x55p
but this alone does not prove closure of all findings or replacement of bundled
copies. Kibana code/pins were left unchanged and its scan remains blocking.

The old worktree's NiFi readers, nested patcher and Kibana source/backport changes
were inspected read-only, not promoted. Wire 5.2 `RuntimeMessageAdapter` ABI must
be preserved; replacing it with Wire 6 is not an accepted fix. Compilation,
binary API comparison, malformed-input parser regressions and actual NAR scanning
are required before promoting those candidates. The recovered audit tool exposes
those bytes without pretending they are fixed.

## Evidence and resource boundary

Logs/artifacts: `/home/tears/.cache/cnc-dependency-remediation-20261103/`.

- `full-tests.log`: 734 passed, 4 skipped, 374 subtests on Python 3.11, with a
  freshly generated own bundle. This ran before adding the final nested-gate test.
- `focused-final.log`: 33 passed, 35 subtests after that addition.
- `dependency-audit.json`: passed; all lock entries, separate research pins and uv
  checked against the configured package advisory source. Not an image scan.
- `runtime-uv0136.txt`, `uv0136.log`: pinned exporter verification.
- `haproxy-scan.json`, `haproxy-runtime.log`: actual image results described above.
- `lan-rotation.log`: preserved local failed rotation attempt.
- `pr112-lan.log`, `pr116-tests.log`, `pr116-images.log`, `ci-kibana/image-scan.json`:
  downloaded real CI evidence. Existing audit archive retains #118 failed logs.
- `es-otel-files.log`: actual base-image file inventory.
- `api-build.log`, `api-build-final.log`, `es-build.log`: incomplete builds.

Builds were explicitly canceled after shared-host resource steering. At stop:
about 1.9 GiB available RAM, 9.8 GiB disk free, 5.6 GiB swap used. No cache/volume
prune, source branch mutation, or running-service changes. Docker had no active
containers afterward. API/ES final images do not exist; no clean scan is claimed.
The full lab's 6 GiB RAM / 20 GiB disk preflight is not met.

## Next gates on a sufficiently provisioned runner

After parent combines backend/runtime changes:

```sh
docker build -f scoring/Dockerfile -t cnc-guard-audit:api .
python -m scripts.check_runtime_image cnc-guard-audit:api
docker build -f deploy/images/elasticsearch.Dockerfile -t cnc-guard-audit:elasticsearch .
trivy image --scanners vuln --list-all-pkgs --format json --output es-scan.json cnc-guard-audit:elasticsearch
python -m scripts.enforce_image_scan elasticsearch es-scan.json
CNC_RUN_LAN_TLS_TESTS=1 uv run --frozen python -m pytest tests/test_lan_ca_rotation.py -q
```

Run Dependency audit's full matrix (including API scan and nested NiFi stage),
ES startup/ingest/query smoke, and address Kibana/Filebeat separately. The new
nested NiFi gate may reveal previously unscanned vulnerabilities; keep it blocking.
Parent-owned lab E2E and live SMB acceptance remain separate gates.
