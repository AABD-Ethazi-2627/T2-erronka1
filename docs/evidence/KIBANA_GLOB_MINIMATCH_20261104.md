# Kibana: Glob migration and legacy Minimatch preprocessing bounds

This change repairs dependency code and preserves the remaining scanner findings.
It does not authorize new scanner exceptions or establish full Kibana/ES acceptance.

## Source and image identity

The source snapshot was captured **before** each build, against base commit
`2da877c`, with the candidate edits recorded by individual SHA-256 hashes.
Those source files were checked unchanged after the build. The concise artifact
index is `KIBANA_GLOB_MINIMATCH_20261104.json` next to this document; raw logs and
reports are in `/home/tears/.cache/cnc-kibana-image-20261104/`.

Both builds produced the same Docker image ID and OCI manifest digest:
`sha256:34a89b0e71b3339c51e5144d363a782a4d6b78cf96b712719da429be38fd5ddd`.
The OCI config digest is
`sha256:2a7d671ce3feee69ba28e140be4b5343eef411694f032458b46656cbcb741293`.
The first build executed the final dependency regressions. The second added and
executed the static importer guard, reusing the identical final image layers.
Its only source changes were the audit script and the Dockerfile audit step.
The builder was limited to 768 MiB and one CPU, then stopped.

## Actual vendor import inventory

The pinned Elastic base image, using its own **Node 24.21.0**, was inspected in a
read-only, network-disabled container. The audit read 78,273 JS files, totaling
541,467,035 bytes; there were no symlinks. It records all literal quoted names
`glob`, `rimraf`, `minimatch`, their context and their **CommonJS resolution**.
Computed imports, ESM export-condition resolution and embedded copies are not
established by this static inventory.

The build guard requires these actual literal importer sets before migration:

- Root Glob: Rimraf's CJS and ESM entrypoints, plus
  `piscina/scripts/run-tests.js` (`globSync`).
- Root Rimraf: no external literal importer. Gaxios 7.1.3 declares `^5.0.1`
  but does not import it in the inspected image. This declaration is outside
  the replacement's major; the absence of an import is bounded evidence, not
  a general compatibility guarantee for Gaxios or future computed imports.
- Minimatch 3.x: only `del/node_modules/glob/{common,glob,sync}.js`.

The audit guard fails if these sets, the exact 3.x source hash or the no-symlink
assumption change. It is repeated in the image build rather than relying only
on an upstream lockfile.

## Code changes and regressions

**Glob:** root Rimraf 6.1.4 explicitly supports Glob `^14.0.3`; the replacement
uses Glob **14.0.3**, nested Minimatch **11.0.4** and a separate integrity-pinned
lockfile for the full dependency closure. The old root Glob/Rimraf directories
are removed before copying, so the old nested Minimatch 9 cannot survive.
Glob 14.0.2 is rejected: its minified main still embeds the vulnerable optimizer.

Tests exercise the CJS and ESM **main** entrypoints, the 10,000-pattern bound,
actual filesystem reads after abort (zero new reads), ordinary and synchronous
Rimraf deletion, cancellation, preserved files, `ignore` and the `globSync`
consumer API. Glob 14 includes `.` in a bare `**` result; this changed behavior
is explicit in the control. This is not a promise that all Glob 10 semantics
are unchanged. The retained `del` subtree uses its original Glob 7/Rimraf 3.

**Minimatch 10:** the official preprocessing fix
[`77a0f5c`](https://github.com/isaacs/minimatch/commit/77a0f5c4b80bdc641c3c930a1d9edf5ad2db57f8)
is backported to both CJS and ESM. The fork is explicitly identified as
`10.2.4+cncguard.1`, with input/output hashes and upstream commit in its metadata.
Both original source hashes and unique patch contexts are validated before any
write. The two stale JS source maps are removed; the 10.x public API is retained.
The final copy includes Brace Expansion 5 and its own Balanced Match 4 dependency.

Controls cover the official cap of 100,000, an explicit cap of 64, the phase-2
limit, ordinary matches and **Fleet's required `.makeRe()`**, removed in 11.x.
The original 10.2.4 fails the small behavioral probe with 256 patterns instead
of 64; it does not need an unbounded OOM reproduction. A separate seeded corpus
checks 2,000 patterns, levels 1 and 2, and 24 paths: **96,000 match comparisons,
zero differences**. A mutated second-format input is rejected before changing
the first format or metadata; a second patch application is also rejected.

The official cap bounds amplification but still permits expensive pathological
patterns and can change matches at the limit. Neither this backport nor upstream
Glob 14 establishes safety for attacker-controlled `ignore` patterns. No new
product interface exposes those options.

**Minimatch 3:** the installed file's SHA-256 is
`746849f267c4868a53729225bd85c7dccd387712136fb305fcc0a3eadd4a3d9d`.
It lacks the advisory's preprocessing methods and amplification operation.
The actual-image test checks that hash, the callable export, 2,048 seeded
properties and a 30-unit pattern. It instruments the real `del` consumer:
zero Minimatch compilations through async/sync dry-run and deletion, versus
two with the positive Rimraf/Glob control. This establishes only applicability
of this specific advisory to these bytes; it is not a general security claim.
The code and version are unchanged, and no exception is added.

All final dependency regressions run during the image build with its Node.
The Python image-gate/infrastructure suites pass 15 tests and 21 subtests.
Repository layout and image inventory checks pass; no full-suite rerun is claimed.

## New image scan

Trivy **0.76.1** scanned the actual Docker image, with complete package listing,
all severities, one worker, a 512 MiB process limit, and the recorded local DB
(`UpdatedAt=2026-11-04T07:16:25.226375897Z`). The run used `--skip-db-update` and
`--offline-scan`; CI uses its own fresh database and must repeat the result.
The scan's image identity matches Docker inspection.

The corrected gate remains **failed**, with exactly these unexpected findings:

| CVE | Installed instance | State |
| --- | --- | --- |
| CVE-2026-118764 | root Minimatch 10.2.4+cncguard.1 | Official code bounds backported; version finding remains |
| CVE-2026-118764 | del's Minimatch 3.1.5 | Advisory mechanism absent in verified bytes; GHSA range finding remains |

The Glob 10.5.0 and Minimatch 9.0.9 findings are absent. The existing two
`extract-zip` backport findings and their policy are unchanged. No new entry
is added to `VERIFIED_FINDINGS`, and no package metadata is relabeled as a
fixed upstream release.

Trivy warns about 132 skipped records with mismatched PURL namespace. This was
checked against the **current** `/lib/apk/db/installed`: all 68 installed APK
name/version pairs exactly match the 68 scanned OS package records, with no
missing or extra pair. The skipped records' provenance was not independently
traced. The Node target inventories 2,309 packages. These counts do not establish
coverage of unmanifested browser/CLI bundles.

## Bounded bootstrap and remaining gates

The first isolated bootstrap failed on the probe's own
`xpack.security.enabled: false`, which Kibana 9.5.5 rejects. Its log/result are
preserved; this setting is not present in the project's Kibana service. The
trace already showed Fleet resolving the patched root Minimatch. A second
probe removes that setting and retains security defaults, with no network or ES.
It reaches setup of 203 plugins and traces all five root Minimatch importers,
plus the retained `del` chain. It then reports a JavaScript heap exhaustion under
the probe's 512 MiB heap. The 90-second observation limit is reached; cleanup
stops the container (final exit 137), which is removed without cleanup errors.
The recorded cgroup `OOMKilled` flag is false: this is not evidence of a cgroup
OOM kill. Total observation plus inspection/cleanup takes 139.72 seconds.
This is not a ready-service, browser or Elasticsearch integration test, and
does not establish compatibility beyond the observed imports and build controls.
The original pinned base image was then tested with the same network-disabled
configuration, trace and 512 MiB heap/768 MiB container budget (`core=0` added).
It also exhausts the JavaScript heap and exits 134 after 66.73 seconds. Both
containers are removed and no service remains running. This control establishes
that the probe budget cannot boot the original image either; it does not measure
the patch's memory overhead or justify lowering the project's larger budget.

Independent review of the implementation, complete Kibana/ES acceptance,
unmanifested copies, NiFi closure, fresh CI and the required GitHub approval
remain separate gates. The earlier Claude assessment is research of prototypes,
not approval of this patch. A new path/hash-bound exception or an external request
to correct the GHSA requires a separate authorized decision; neither is performed.
The CG32 resource gate, historical evidence and academic/human acceptance are
unchanged.
