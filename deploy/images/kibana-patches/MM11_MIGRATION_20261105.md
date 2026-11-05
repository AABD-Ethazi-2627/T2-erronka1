# Root Minimatch 11 candidate: official matching semantics

Status: actual dependency/consumer migration implemented and component-tested.
The coordinator explicitly accepted official MM11 semantics for this reversible
candidate, including the reproduced negative-extglob changes and the additional
trailing-slash, final-empty-segment and dotfile differences documented below. This
supersedes the earlier requirement to preserve MM10 matching exactly; it does
not supersede the historical diagnostic or imply image/runtime/human approval.
No scanner policy, exceptions, NiFi, dashboard/model contracts or workflows
are changed. The coordinator separately reconciles source/evidence manifests.

## Official inputs and semantic policy

Root Minimatch is the unmodified official **11.0.4** npm package, with its complete
nested closure: `@isaacs/nonrecursive-glob-match 1.0.3`, `brace-expansion 5.0.12`,
`balanced-match 4.0.4`. `minimatch-migration/package-lock.json` pins every resolved
tarball and SHA-512; transitive overrides pin these exact versions. A real
`npm ci --offline --ignore-scripts --install-strategy=nested` ran with the
immutable image's **Node 24.21.0**, using npm CLI **11.20.0**. The npm CLI's local
source happens to reside under a host Node26 tool directory; that host Node
binary and its npm shell wrapper were never executed. The CLI source/dependency
file hashes are recorded in `npm-tool-files.json`.

All four downloaded official tarballs passed their lock's SHA-512. All **90 npm
installed files** match the tarball bytes and the committed
`mm11-official-files.json`, including actual CommonJS/ESM code, types and maps.
The package version is not relabeled and no MM10 compiler is retained in the
new root package. The existing Glob 14.0.3/Rimraf 6.1.4 lock and nested MM11
closures are unchanged.

Pinned primary sources in `mm11-primary-sources.json`:

* [MM11.0.4 changelog](https://github.com/isaacs/minimatch/blob/v11.0.4/changelog.md):
  path-part Matcher objects replace RegExp; makeRe/regexp/AST and several old
  internal methods are removed. It also documents empty-path, globstar/partial,
  normalization and optimization-bound changes.
* [MM11.0.4 API](https://github.com/isaacs/minimatch/blob/v11.0.4/README.md):
  boolean `Minimatch.match` and named CJS/ESM exports are the supported interfaces.
* [Matcher 1.0.3 semantics](https://github.com/isaacs/nonrecursive-glob-match/blob/v1.0.3/README.md):
  negative extglobs reject the alternatives for the substring they consume;
  Bash 5 is the reference, with documented dotfile/case-folding differences.
  Unicode normalization is opt-in, not silently enabled by this patch.

The historical `logs-!(a|b)*-default` witness now intentionally matches
`logs-a-default`, `logs-ab-default` and `logs-foo-default`. A negative extglob can
consume an empty substring which is neither `a` nor `b`; the following star
consumes the remaining characters. No fake RegExp object or old compiler is
used to reproduce the former greedy behavior. Complete negation without that
following star still excludes the alternatives, as the controls verify.

## Inventory and actual consumer changes

The exact full incoming base tree is pinned by the unchanged del inventory:
95,737 files, 1,405,460,623 physical bytes, 633 decoded gzip/Brotli assets,
no symlinks, canonical tree hash
`3dd63ede6574561c715a3627d293406b31b6475dc38c4d13fcfe56c6da277841`.
Both del and MM11 preparation run before any mutation of that tree. All bytes,
extensions, templates, comments, alias forms and compressed assets are pinned;
there is no syntax classifier that can exempt drift. This remains bounded
static/byte evidence, not a proof about arbitrary computed imports.

`mm11-inputs.json` pins all eight literal root-MM consumers, all six owning
package metadata files, all 257 just-bash files and all 28 original root-MM
files. The five `@kbn` consumers are:

| Consumer | Actual use / candidate control |
| --- | --- |
| Fleet `services/epm/packages/get.js` | Real compiled filtering function; `patternMatcher.match(dataStreamName)` replaces `.makeRe()` plus `String.match` |
| Task Manager `task_claimers/index.js` | Real task exclusion function; ordinary and Unicode task names |
| Security Solution `health_diagnostic_receiver.js` | Real `isPathAllowed`; positive, case-sensitive and denied API-path controls |
| Significant Events `classify_streams.js` | Real exclusion function, including adopted negative-extglob result |
| Observability Agent Builder `get_field_values_handler.js` | Real concrete-field resolver, dot fields, Unicode names, type/category/error results |

The three remaining references are just-bash's CJS bundle, its ESM
`chunk-R4IFXNY5.js`, and `browser.js`. All call the supported boolean
`minimatch` API. In the revised candidate, both actual matching call sites in
each bundle explicitly pass `braceExpandMax: 1024`; no old compiler is retained. Their actual public `Bash` APIs were executed on virtual filesystems
through CJS, the ESM entrypoint/chunk and the browser entrypoint **in Node**.
This is not browser/UI acceptance.

Fleet is an honest local fork `9.5.5+cncguard.mm11.2`, with the compiled source
adaptation, exact `minimatch:11.0.4` dependency and hash-bound provenance.
just-bash is an honest local dependency-integration fork
`3.0.1+cncguard.mm11.2`, with exact `minimatch:11.0.4`, original bundle hashes, the bounded source edits
and an explicit note that upstream declared `^10.1.1`. This is not a claim of
upstream support for an out-of-range dependency. Root MM security remediation
comes from installing real official MM11 code, not from these fork labels.

Full inbound dependency declaration census (including dev/optional/peer):

| Original declaration | Disposition |
| --- | --- |
| just-bash runtime `^10.1.1` → root MM10 | Replaced by the tested local exact 11.0.4 integration |
| chroma-js dev `^3.0.4` → root MM10 | Already unsatisfied before this migration; no development-suite support claimed |
| jsdom dev `^5.1.0` → root MM10 | Same pre-existing dev-only mismatch |
| micromatch dev `^5.0.1` → root MM10 | Same pre-existing dev-only mismatch |
| Glob10 runtime `^9.0.4` → nested MM9 | Already replaced by the retained Glob14 migration/own MM11 closure |
| del/Glob7 runtime `^3.1.1` → nested MM3 | Removed by the independently accepted del candidate |

The four other `@kbn` matching functions originally had no declared MM range
in their packaged workspace metadata. All five now carry an honest local fork
version, exact runtime declaration and the same explicit expansion budget in
their actual matcher options. Fleet also adapts the removed API. No existing dependency
range is silently rewritten as if upstream itself supported MM11.

## Physical installation and regressions

`mm11-migration.cjs` checks original package/consumer bytes, the post-del index
hash and **all prepared output hashes before the first mutation**. It removes
the entire old 28-file root MM directory, then copies the 90-file official
closure, all eight bounded consumer sources and six honest local package
metadata files (105 output files including the packaging index).
It updates only relevant packaging-index paths/just-bash locator. There is no
overlay that could preserve old AST code or stale old maps.

Dockerfile wiring installs del first, then MM11, before other existing package
copy steps. The original del base-preparation guard remains unchanged and runs
against the original base. The old MM10 fork and brace closure copy steps and
old-format final-image MM10 tests are replaced by MM11 physical/version/API
checks. Historical MM10 scripts, diagnostic, source/scan caches and the unused
historical build-stage npm alias are retained; they are not copied to runtime.
Build-stage original base dependencies are not final-image remediation claims.

The finite component run passes:

* Historical corpus: **36,000 comparisons, exactly 216 differences**, all
  classified as adopted negative-extglob semantics. Any other difference in
  that corpus fails. The original diagnostic is unchanged, not hidden.
* An additional **9,000 Fleet-domain comparisons, zero differences**, plus
  explicit wildcard, dot, Unicode, decomposition, case-folding and path controls.
* CJS/ESM public API controls with an explicit test-only expansion cap 64;
  that historical option did not bound real consumers. The revised candidate
  applies 1024 at every real call site, as described below. A small modern-only
  repeated-extglob negative control, without old-native hostile/OOM probes.
* Five actual compiled `@kbn` matching functions in isolation. No ES, saved-object
  server or whole-plugin lifecycle is simulated as live integration.
* **21 public Bash cases** across the three real bundle variants, plus explicit
  old/new existing-limitation controls and the retained old witness.
* Six drift mutations and double application rejected before input deletion.
* Physical fixture resolution, official byte equality, and async/sync/dry-run
  del coexistence with its exact accepted engine/package hashes.

One exploratory assertion expected quoted `ls 'logs-@(a|ab)-default'` to expand.
The actual old bundle also returns exit 2: its ls fallback does not call the
matcher for that quoted pattern without `*`. The test now preserves that
existing limitation in both versions and separately exercises working positive
extglob patterns containing a star. No library compatibility assertion was
weakened to conceal a new regression. Failed exploratory outputs remain saved.

The accepted del engine and guards/pins are untouched. Only its **final-image**
root-MM version assertion changes from MM10 to 11.0.4. The historical 99-record
hash belongs to the earlier test source and independent parent run; it is not
attributed to this edited source. Current coexistence tests are narrower and
separately recorded. Del source SHA remains
`11c55f488491bc447a8663a76a9d2e61b8871dee31f877419e215f4d65a895bd`.
The historical del test source SHA is
`ef5b585e71d5ee967c38d7b7678239f26f7cc3ece4c4db8a0c0220d9332ef68b`;
the edited final-image assertion source SHA is
`1745e89f9e1b7279e95f9af7a5015be2e1ad0f5209171ea3311caf74d57ee85e`.

The final-image guard additionally inventories installed MM manifests, rejects
every MM version below 11.0.4, checks all runtime MM dependency ranges, all eight
consumer source hashes and all official root bytes. It is wired, **not executed
against a newly built image here**. Embedded unrelated maps/CLI matchers remain
outside this root-package migration; no general claim about them is made.

## Historical initial reproduction and proof (before retention correction)

```sh
python deploy/images/kibana-patches/run-mm11-migration.py \
  /home/tears/.cache/cnc-mm11-migration-NEW-RUN
```

The path must not exist; it is created private (0700). The driver downloads only
pinned public tarballs/primary notes. All npm/Node phases run on already-owned
immutable images with `--pull never`: base
`sha256:46b0a3adf85186f9153fbd322e55ea8f70bc4039dcd55d58826fc1caa372dee5`
and prior candidate
`sha256:34a89b0e71b3339c51e5144d363a782a4d6b78cf96b712719da429be38fd5ddd`.
The old image/root sources stay read-only. Only freshly owned fixture/cache
files are written; no actual filesystem-root deletion is tested.

Each heavy phase uses the common `candidate-heavy.lock` once, 30-second finite
lock wait, 140-second wall bound including that wait, one CPU, container
384 MiB memory/swap total, heap 256 MiB, core=0, 64 PIDs, 64 MiB tmpfs,
network none, read-only root/fixtures and dropped capabilities. npm subprocesses
also use Node24/256 MiB heap and ignore lifecycle scripts. Only uniquely named
component containers are cleaned up. No image build, pull, service, push, watch,
exception, subagent or parent checkout mutation occurs.

Authoritative output:
`/home/tears/.cache/cnc-mm11-migration-20261105-Y57uFf/final-run/`.
`commands.json` records exact commands, `sources-before.json` pins all tested
sources (checked unchanged afterward), and `sha256.json` indexes every artifact.

| Output | SHA-256 |
| --- | --- |
| `consumers.json` | `0574e955a59c8495050ba604d9d5d69368d964ece58179dcdf8d3c9aa3884b96` |
| `npm-ci.json` | `7806eefad335e2aa4560a0c420d18cedefb95134a8c59677b5f0e1625dd39ae2` |
| `prepare.json` | `8e3eab7f08b203e6b691c49cc6b9509a70ac45078c429cf605324820b3abacd4` |
| `sha256.json` | `1e93918db62be63afc8bbae750b9d3f17bd0c3e8c60cb3c653d2b1f1c7e628ba` |
| Patched Fleet JS | `ab604889063402cdcc2147ffb00aaba60d3cbf6253743499097ed9bc3a28da1d` |
| Local just-bash package JSON | `dc98bd9354bc57b58e590ce3a45788a292e28fb6cd2e70a65c0f0db0461cfa52` |

`mm11-output-files.json` pins every installed candidate file; the npm lock pins
source tarballs, and `mm11-primary-sources.json` pins the official API/release
notes. This is not bit-for-bit MM10 compatibility or a broad security guarantee
for arbitrary hostile pattern inputs.

The records above describe the initial source, not the retention correction.
Parent gates remain new QA of revised sources, owned evidence integration, resource-gated
actual image build and fresh normal scan, then Kibana/ES/browser acceptance.
No human, SMB, CG32, model or deployment approval is inferred. Existing two
Kibana findings remain authoritative until that actual scan proves their removal.

## Revised retention budget and semantic scope

The independent review of `0dafc5d` reproduced the migration but found that
MM11's 256-entry compiled-pattern cache retained approximately 35–40 MiB per
short range pattern with the default 100,000-expansion limit. The old explicit
test cap 64 was not a consumer control. No image/runtime impact or OOM was
claimed; no license-based risk exception is accepted.

The coordinator instead fixes **1024 expansions per matcher** in the actual
options of all five compiled Kibana matching functions and both matching sites
in each of the three just-bash bundles. Official MM11 and its 90 official files
remain unchanged. The five Kibana packages and just-bash are explicit local
`+cncguard.mm11.2` source/dependency integration forks. All outputs are pinned
before installation and the image guard verifies their hashes/metadata.

This budget is an intentional supported-input limit: alternatives after 1024
may not match. It can therefore exclude an otherwise valid match, or stop an
exclusion from matching. It is not full equivalence for arbitrary huge patterns
or a general upper bound on all application memory. No old compiler or silent
license dependency is used to preserve the unbounded behavior.

The regression first fails on the old physical fixture because the actual
Fleet options omit the budget. The revised tests inspect real consumer options,
AST-check both matcher calls in every bundle before allocation, and test
above-budget results in the installed matching functions. Retention probes use
24 distinct bounded patterns, explicit GC, a 24 MiB aggregate fixture limit and
an 8 MiB per-step stop. Actual Bash APIs additionally exercise the revised
physical bundles with an above-budget pattern and the same finite stop. No OOM
or root deletion is attempted. Actual measured values belong to the parent
proof recorded in `docs/evidence/INTEGRATION_CANDIDATES_20261105.json`.

The 9000-comparison corpus is only the Fleet name domain; it does not establish
all-consumer equivalence. The independent broader 1234-case corpus found 19
differences: 15 Fleet trailing-slash cases, three empty final path segments and
one positive-extglob dotfile case. The revised regression fixes representative
results for these classes. The 252 default security-pattern comparisons remain
equal; this does not approve arbitrary configured allowlists. MM11 can also
throw `TypeError: pattern is too long` after expanding/merging very large inputs,
where MM10 returned a boolean. The budget reduces expansion, but this remains
a documented failure behavior rather than a total-function guarantee.

The original local component images disappeared during the correction. The
coordinator restores the exact public base digest and builds only a disposable
component fixture with the 451 Glob/Rimraf closure files independently matched
to official SHA-512-pinned tarballs. This is not the full patched serving image.
The fixture keeps original MM10.2.4 as the old comparison (the former fixture
used its backport, inert in modes 0/1), runs as the base UID1000, and has a
recorded immutable image ID. `run-mm11-migration.py OUTPUT IMAGE_ID` validates
that exact local ID, never pulls/builds, and supplies `--expose-gc` only for the
component retention test. All phases retain the CPU, memory, network and finite
lock bounds. Failed fixture identity/UID attempts remain historical failures.

The historical source, package-output hashes and proof table above are not
retagged as this new revision. Fresh parent source/artifact hashes, revised QA,
full serving-image build/scan, Kibana/ES/browser, CG32 and human acceptance are
still separate gates.
