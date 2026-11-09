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
established by this static inventory. The classifier also misses several literal
forms (side-effect imports, templates, interleaved comments, aliases, subpaths)
and scripts outside its JS extensions. The independent final-image scan found
no actual bypass of those forms in the inspected files; its one 9.1 MiB
TypeScript bundle exceeded that scan's per-file limit. This does not establish
future coverage if the pinned base changes.

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
on an upstream lockfile. The separate container inventory used Node 24.21.0;
the build-stage guard used Node 26.13.0 installed with npm. The guard does not
assert the starting package versions; those and its UTF-8 boundary handling
remain improvements for the next rebuild.

## Code changes and regressions

**Glob:** root Rimraf 6.1.4 explicitly supports Glob `^14.0.3`; the replacement
uses Glob **14.0.3**, nested Minimatch **11.0.4** and a separate integrity-pinned
lockfile for the full dependency closure. The old root Glob/Rimraf directories
are removed before copying, so the old nested Minimatch 9 cannot survive.
Glob 14.0.2 is rejected: its minified main still embeds the vulnerable optimizer.
Glob's `main` executes its embedded Minimatch, not the separately inventoried
11.0.4 copy. The override pins the external dependency used by `glob/raw`.
The main-entry behavior tests establish that the embedded preprocessing bound
is present; its precise embedded Minimatch version was not measured.

Tests exercise the CJS and ESM **main** entrypoints, the 10,000-pattern bound,
actual filesystem reads after abort (zero new reads), ordinary and synchronous
Rimraf deletion, cancellation, preserved files, `ignore` and the `globSync`
consumer API. The `.` result for bare `**` is **the same in Glob 10.5.0 and
14.0.3**; it is an expected-result control, not evidence of a changed behavior.
The contrary comment in `test-glob-migration.js` is incorrect and is retained
until the next rebuild because that file is part of the scanned image layers.
This is not a promise that all Glob 10 semantics are unchanged: changes to
`walk()`, `Pattern` methods, `debug` and rooted ignores were not exercised.
The retained `del` subtree uses its original Glob 7/Rimraf 3.

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
all severities and the recorded local DB
(`UpdatedAt=2026-11-04T07:16:25.226375897Z`). The parent invocation configured
one worker, `MemoryMax=512M`, `--skip-db-update` and `--offline-scan`. The saved
scanner log does not attest the transient scope configuration or record the
command, so the memory limit is not independently verifiable from that log.
The [reproduction notes](KIBANA_GLOB_REPRODUCE_20261104.md) give the command and
repeatable probes, added after the review rather than presented as contemporaneous
records. CI uses its own fresh database and must repeat the result. The scan's
image identity matches Docker inspection.

Calling `validate("kibana", report,
expected_artifact="cnc-guard-local:kibana-glob-candidate")` remains **failed**,
with exactly these unexpected findings. The override identifies the local image;
the ordinary CLI correctly rejects this report's non-CI artifact name instead.

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
It **initiates** setup of 203 plugins and exhausts the heap during that phase;
neither completion of setup nor `start` is observed. It traces the five `@kbn`
importers of root Minimatch and the retained `del` chain. The static inventory
has eight root Minimatch import references: three `just-bash` bundles were not
loaded by this bootstrap. Root Glob and root Rimraf were not loaded either;
their compatibility evidence comes from isolated build controls. It reports
a JavaScript heap exhaustion under
the probe's 512 MiB heap. The 90-second observation limit is reached; cleanup
stops the container (final exit 137), which is removed without cleanup errors.
The recorded cgroup `OOMKilled` flag is false: this is not evidence of a cgroup
OOM kill. Total observation plus inspection/cleanup takes 139.72 seconds.
This is not a ready-service, browser or Elasticsearch integration test, and
does not establish compatibility beyond the observed imports and build controls.
The original pinned base image was then tested with the same network-disabled
configuration, trace and 512 MiB heap/768 MiB container budget (`core=0` added).
It also exhausts the JavaScript heap and exits 134 after 66.73 seconds, after
tracing only three of the five `@kbn` importers. It does not reach the same
point as the candidate, so this comparison establishes no later-phase behavior. Both
containers are removed and no service remains running. This control establishes
that the probe budget cannot boot the original image either; it does not measure
the patch's memory overhead or justify lowering the project's larger budget.

The [independent review of `f80c37f`](CLAUDE_KIBANA_GLOB_PATCH_RECHECK_20261104.md)
found no high-severity finding or established runtime breakage. It identified
two documentary findings corrected here and seven low-severity findings.
It independently compared 2,816,000 matches with zero differences and verified
528 copied files against the pinned dependency closure. Those results are the
reviewer's bounded probes, not a full-suite or service acceptance result.
The build guard, unused alias and test-comment improvements remain deferred
to the next image rebuild. The earlier prototype report incorrectly attributed
an embedded optimizer to `just-bash`; that file is absent from this image.
The review instead locates an unbounded browser optimizer in `maps.chunk.957.js`,
with default level 1. Its reachability with higher options is not established.

Complete Kibana/ES acceptance, unmanifested copies, NiFi closure, fresh CI and
the required GitHub approval remain separate gates. A new path/hash-bound exception or an external request
to correct the GHSA requires a separate authorized decision; neither is performed.
The CG32 resource gate, historical evidence and academic/human acceptance are
unchanged.
