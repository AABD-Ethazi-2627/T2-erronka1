# Independent del consumer migration

Status: implemented and component-tested; parent acceptance of the retry-policy
differences below, image build, fresh scan and runtime acceptance remain pending.
This change does not install root Minimatch 11 or alter the earlier incompatibility
diagnostic. The current two image findings remain authoritative until a new image
scan establishes the result.

## Actual adaptation and pinned inputs

The local fork is honestly identified as `del 6.1.1+cncguard.1`. Its original
CommonJS callable export, `.sync`, globby discovery, sorting, cwd/force safety
checks, progress callbacks and return arrays remain in the upstream source.
Only the deletion engine changes:

* Async: promisified public `node:fs.rm`, with `recursive:true`, `force:true`,
  `maxRetries:3`, `retryDelay:100`. `force` here tolerates ENOENT; del's separate
  outside-cwd/force checks still execute first.
* Sync: public `rimraf.posixSync` **6.1.4**, with globbing disabled and a small
  explicit retry loop for EBUSY/EMFILE/ENFILE/ENOTEMPTY/EPERM. Three retries wait
  100, 200 and 300 ms using `Atomics.wait`, then rethrow the actual error.

The sync choice avoids a reproduced Node 24.21.0 native `rmSync` behavior:
persistent injected EBUSY produces four unlink attempts but ends with `code:""`,
`errno:-4094`, `syscall:"rm"`. The committed test reproduces that rejected
alternative. The selected public POSIX implementation retains `code:"EBUSY"`
and `syscall:"unlink"` after four attempts; no error relabeling is used.

The supported image platform is Linux/Wolfi. The fork declares the exact Rimraf
6.1.4 dependency and a compatible Node engine, and removes its graceful-fs
dependency. Root Rimraf 6.1.4/Glob 14.0.3 and their nested Minimatch 11.0.4 are
already pinned by `glob-migration/package-lock.json`; that lock and its
`npm ci --ignore-scripts --install-strategy=nested` build step are unchanged.
No new npm installation or lifecycle script was run locally. No root MM10,
security allowlist, scanner or unrelated image patch changes.

The async approach also exists in official del 8.0.1; this is a scoped CJS source
adaptation, **not** a claim to have installed upstream del 8. Its official tarball
was downloaded and its registry SHA-512 verified in the fresh research cache.
Tarball SHA-256: `51d92e89870834273bb7ff7b9274525332ee11dd80e479eebb4ef1432e89575b`.
References: [official del source](https://github.com/sindresorhus/del/blob/main/index.js),
[Node fs API](https://nodejs.org/api/fs.html#fsrmpath-options-callback),
[Rimraf public APIs](https://github.com/isaacs/rimraf#api).

## Guarded closure removal and consumer inventory

`prepare-del-migration.cjs` verifies the **entire pinned incoming Kibana tree**
before preparing output: 95,737 files, 1,405,460,623 physical bytes, zero symlinks,
633 gzip/Brotli assets additionally decompressed and inspected. The canonical
path/mode/size/content fingerprint is
`3dd63ede6574561c715a3627d293406b31b6475dc38c4d13fcfe56c6da277841`.
This includes JS, CJS, ESM, TS, extensionless scripts, bundles, source maps,
metadata and binaries; it has no syntax-based exemption for comments, templates,
bare imports, require.resolve or bundler aliases. Any byte drift fails closed
and requires a new inventory/review. Decompression above 32 MiB fails closed.

The conservative literal inventory contains 802 references, mostly locale/HTML
data, not 802 importers. The actual six CommonJS importers are:

```text
node_modules/@kbn/cli/plugin/install/cleanup.js
node_modules/@kbn/cli/plugin/install/install.js
node_modules/@kbn/cli/plugin/remove/remove.js
node_modules/@kbn/screenshotting-plugin/server/browsers/chromium/driver_factory/index.js
node_modules/@kbn/screenshotting-plugin/server/browsers/download/index.js
node_modules/@kbn/screenshotting-plugin/server/browsers/install.js
```

No additional literal ESM, subpath or bundled package import of del was found;
the just-bash `del/1` strings are jq operator names. The only external deep-path
references to `del/node_modules` are the four packaging-index entries.
Standard Node package resolution scopes the legacy copies to del's subtree.
Every declared dependency resolving to that subtree is recorded in
`del-base-inventory.json`: del→Rimraf3→Glob7→Minimatch3→BraceExpansion1,
plus Glob's dev dependency on Rimraf2. The seven other inbound del declarations
are development-only and already use older ranges in the base; this fork does
not claim to run their development suites or repair those pre-existing ranges.
The six installed runtime importers retain their callable/default and sync API.

This is a pinned-byte/static inventory plus real consumer and resolution tests,
not a mathematical proof about arbitrary computed imports. The full-tree guard
prevents such future code changes from silently passing a narrow regex check.

The base del subtree has 18 files, including 15 files in its four nested
packages. `install-del-migration.cjs` rechecks all 18 hashes immediately before
removal, verifies every prepared output hash and both packaging-index hashes,
then physically replaces the subtree. The four removed path mappings are also
removed from `.modules.yaml`; no unrelated mappings are rewritten semantically.
The original license is retained. The old Brace Expansion copy step is removed
from the Dockerfile so it cannot recreate an orphan nested directory.

The final-image test asserts no nested del directory, walks installed package
metadata to reject Rimraf3/Glob7/Minimatch3 copies, checks root MM10 and Rimraf6,
and exercises normal del controls. **This final-image test is wired but has not
run against a newly built image here.** Embedded unrelated browser/CLI matchers
are not removed or claimed fixed by this migration.

## Controls, intentional differences and limits

The finite Node24 component driver passes **99 records**: old/new normal
contracts, 92 old/new syscall-fault scenarios, four old callback-boundary
terminal controls, and the rejected native-sync control. The syscall shim only
injects errors for one exact fresh `/tmp/cnc-del-*` victim path. It intercepts
unlink/rmdir/remove/unlinkat; no host permissions, descriptor exhaustion or
descriptor limits are changed.

| Contract | Result |
| --- | --- |
| async/sync, sorted arrays, dry-run, empty/absent paths, ENOENT race | Pass |
| outside-cwd denial, force on owned outside fixture, current-cwd denial | Pass |
| symlink deletion with outside sentinel retained | Pass |
| progress throws after deletion, empty progress throws | Same rejection identity |
| rejected progress Promise | Not awaited in either version; observed unhandled rejection unchanged |
| progress supplied to sync | Ignored in both versions |
| transient two-operation failures | New retryable cases recover on attempt 3; EACCES remains terminal |
| persistent EACCES | One attempt; original code/path preserved |
| persistent retryable errors | Sync four attempts, async four attempts; async empty-dir EPERM/ENOTEMPTY has eight underlying rmdir calls |
| drift guards | Six mutations plus double application rejected before source/index writes |
| physical installed fixture | 15 legacy files removed; standard CJS/ESM resolution reaches root Rimraf6 |

**Parent decisions:** async descriptor errors now have a bounded three-retry
policy rather than graceful-fs's potentially 60-second queue. In the old
post-graceful callback boundary, persistent EMFILE causes 1,001 attempts and
ENFILE one; these were tested with virtual timers, not long real waits.
The old native graceful-fs queue was tested with finite transient faults only.
Sync calls now retry retryable errors that the old POSIX synchronous engine
usually returned immediately. Thus retry timing/counts intentionally differ;
this is not a claim of exact behavior under resource exhaustion. The three
retries apply per path/operation, not a global deletion deadline.

No Windows, real descriptor exhaustion, full Kibana startup, browser, ES,
SMB, CG32, human or model acceptance is claimed. Root deletion is never tested.
Rimraf's root-preservation safety remains enabled for sync calls. The Node
container and all deletion fixtures are disposable.

## Reproduction and proof

```sh
python deploy/images/kibana-patches/run-del-migration.py \
  /home/tears/.cache/cnc-del-migration-NEW-RUN
```

The output directory must not exist. The driver uses only these already-owned
immutable images, with `--pull never`:

* Base: `sha256:46b0a3adf85186f9153fbd322e55ea8f70bc4039dcd55d58826fc1caa372dee5`.
* Existing candidate: `sha256:34a89b0e71b3339c51e5144d363a782a4d6b78cf96b712719da429be38fd5ddd`.

Every Node/compile phase acquires the common `candidate-heavy.lock` (30-second
acquisition limit). Containers: exact Node 24.21.0, one CPU, 384 MiB memory plus
swap total cap, 256 MiB heap, core=0, 64 PIDs, no network, read-only root and
fixtures, 64 MiB /tmp. The driver imposes a 140-second wall bound including lock
wait and cleans up only its uniquely named component container. GCC compilation
uses one allowed CPU, 256 MiB address-space cap, core=0 and a 60-second wall bound
including lock wait. No image builds or services are used.
The shim ELF records GCC `(GNU) 16.2.1 20260810` in its `.comment` section;
the extracted toolchain proof is preserved as `compiler-proof.txt` in the
research directory. The compiler is test-only, not a final-image dependency.

Authoritative output directory:
`/home/tears/.cache/cnc-del-migration-20261105-NYRZdO/final-run/`.
`commands.json` records exact invocations; `sources-before.json` records tested
source hashes (asserted unchanged after execution); `sha256.json` covers all
artifacts. Earlier failed experiments remain preserved separately.

| Proof | SHA-256 |
| --- | --- |
| `tests.json` | `960174d48aac566dd710ebc3d8d0dd1832dd9fe2453c460d546244c65b5af669` |
| `guards.json` | `8df814fc20573448686f2b87c0ffa587ac93a8008586bc001f377e3175477905` |
| `sha256.json` | `0e31bdadfd4c9b5bb5ecd971193ec3956e0e33ae141fa4ea1b52b20c668efbf4` |
| Patched del `index.js` | `11c55f488491bc447a8663a76a9d2e61b8871dee31f877419e215f4d65a895bd` |
| Patched del `package.json` | `7acd717a5d8fc928d9caa20fd39eb3b1fbf30e7b6dc08e6c45c367e886243e6e` |

`del-output-hashes.json` also pins the license and updated packaging index.
The raw complete base inventory is preserved as `base-inventory-v2.json` in the
parent research directory, SHA-256
`4fa1c476fa829b957341eb83c8d74700ffa768e1802a71035a36bfba08d0978d`.

The parent must accept the explicit retry-policy changes, apply this local
commit, update its owned source/evidence manifests, obtain QA, then build and
scan the actual image with the normal fresh database and unchanged enforcement
gate. Existing resource gates apply. Only that scan can establish removal of
the 3.1.5 finding; the root 10.x finding is expected to remain. No push, PR,
watch, exception, academic-manifest edit or parent checkout mutation is included.
