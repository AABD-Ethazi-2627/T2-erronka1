# Supported Minimatch migration: reproduced compatibility blocker

Status: **diagnostic delivered; no dependency migration installed**. This is a
tested blocker for direct replacement, not a proof that every possible adapter
is impossible. No new security exception, version relabel, image layer change,
push, service startup or acceptance claim is made.

## Exact consumer result

The installed `just-bash` 3.0.1 CJS bundle imports root Minimatch. Running the
actual bundle's `Bash.exec()` against its virtual filesystem, with cwd `/work`
and files `logs-a-default`, `logs-ab-default`, `logs-foo-default`:

```text
ls 'logs-!(a|b)*-default'

root 10.2.4+cncguard.1: logs-foo-default
official 11.0.4:       logs-a-default
                      logs-ab-default
                      logs-foo-default
```

Both executions return exit 0 with empty stderr. A positive control,
`ls 'logs-*-default'`, lists all three files in both. The probe reloads the real
bundle for each case and asserts exactly one intercepted Minimatch import;
only that dependency binding changes. This is an actual consumer invocation,
not an invented RegExp wrapper. No host filesystem is exposed to this Bash
instance. Bundle SHA-256:
`574c456bab8a1f20dbb18c334ca49825df2d242f35c347a8f92d19c040617a08`.

Fleet's real compiled `getInstalledPackageSavedObjectDataStreams` was extracted
with an exact full-file SHA guard, then executed in isolation. Blind replacement
throws `makeRe is not a function`. The proposed boolean `.match()` adaptation
also changes the result for pattern `logs-!(a|b)*-default` and name
`logs-a-default`: old rejects, new accepts. The old `.match()` agrees with the
old RegExp for this witness, so replacing only the call method cannot solve it.
Fleet saved-object pattern-domain reachability is **not established**; the
independent just-bash reproduction does not depend on that assumption.

A deterministic corpus (seed `0x119`, 2,000 patterns, nine names, CJS and ESM
11.0.4) performs **36,000 comparisons, 216 differences**. Comparisons count
each format separately. This is bounded compatibility evidence, not exhaustive
fuzzing. Negative cases, positive cases and a small optimization-level-2 cap
control (`braceExpandMax:64`, eight repeated segments) all discriminate.

`just-bash` declares `minimatch:^10.1.1`; 11.0.4 is outside it. Simply editing
that range would neither restore behavior nor constitute a supported migration.
No legacy matcher is copied under a new upstream version.

## Independent del experiment

The actual installed `del/index.js` was compiled in memory after replacing its
promisified Rimraf 3 import with Rimraf 6.1.4's `rimraf` promise function and
using `{glob:false}` instead of obsolete injected graceful-fs callbacks. Both
async and sync still return del's sorted path arrays; Rimraf's boolean return
is internal. Tests compare the original and adapted del for async dry-run,
progress callbacks, directory deletion, symlink deletion without following the
target, sync deletion, absent paths, retained files and outside-cwd rejection.
All physical deletion fixtures are newly created inside disposable `/tmp`.

Those controls pass. This is **not a shippable del patch**: del declares
`rimraf:^3.0.2`, and dropping its injected graceful-fs operations still needs
EMFILE/error/retry testing. No Windows claim is made. Its nested
Rimraf 3/Glob 7/Minimatch 3 closure remains installed and must not be removed
merely because these normal controls pass.

## Reproduction and provenance

From this checkout, choose a previously nonexistent directory outside the repo:

```sh
python deploy/images/kibana-patches/run-supported-migration-probe.py \
  /home/tears/.cache/cnc-kibana-supported-NEW-RUN
```

The driver requires the preserved migration-preparation cache. It asserts that
its lock equals the repository's pinned `glob-migration/package-lock.json`,
downloads the four exact official npm tarballs, verifies each lock's SHA-512,
and compares all **90 package files** byte-for-byte to the tested closure with
no extra files. Packages: Minimatch 11.0.4, nonrecursive-glob-match 1.0.3,
brace-expansion 5.0.12, balanced-match 4.0.4. Tarballs are stored only in fresh
output. No npm install, lifecycle scripts or new installed candidate are used.
This verifies the tested Minimatch closure, not Kibana's entire installed tree.

The component container runs the immutable already-owned image ID
`sha256:34a89b0e71b3339c51e5144d363a782a4d6b78cf96b712719da429be38fd5ddd`
with Node **24.21.0**. It uses `--pull never`, no network, read-only root and
fixtures, one CPU, 384 MiB container RAM/swap cap, **256 MiB heap**, core=0,
64 MiB tmpfs and 64 PIDs. The driver serializes through
`candidate-heavy.lock`, waits at most 30 seconds for it and imposes an 80-second
wall limit including that wait; its finally block removes only its own uniquely
named disposable container. `command.json` records the exact invocation.

Delivery output:
`/home/tears/.cache/cnc-kibana-supported-20261105-xoRv2Z/delivery-run/`.
Exit code **0** means the diagnostic assertions passed, including reproduction
of incompatible behavior; it does **not** mean compatibility passed.

| Artifact/source | SHA-256 |
| --- | --- |
| `result.json` | `6801dcd6d778a6a403ee5f46aefea2606d57cfa43341371aa0ea2c10477d4670` |
| `verified-packages.json` | `1959072eeb4d3c9aeeeb15b45280ebe399f141689bd2621aef1d58d20f512f62` |
| `sha256.json` | `340dc9e01e25b7ca71f205b3c7ca3283210924199924a1c8c8d49b99e0d7479f` |
| `probe-supported-migration.cjs` | `7b3bdd1f51e4a6f53ad1680bc41b14fb9c4b8ece03de47090d22348bcef58ce1` |
| `run-supported-migration-probe.py` | `0a5e8bc000e2481e4b2c500c21894e072a0aec1bee0b9b25ac35e4675e1e6827` |

Exploratory runs, including a failed probe caused by using the callback symlink
API, remain preserved in the parent cache directory. `delivery-run` contains
the corrected exact final scripts and authoritative result. `sha256.json`
indexes every output file plus the input lock hash; `image-inspect.json` saves
image identity and `cleanup.json` saves cleanup output.

## Remaining work and parent gates

The narrow supported-API replacement fails the required behavior-preservation
control. Remaining options are a consumer update explicitly accepting and testing
the changed negative-extglob behavior, or a separately proven non-RegExp
compatibility implementation preserving the required language with bounded
work. This report does not authorize a behavior change or select a workaround.
Blind major replacement, restoring the old vulnerable compiler, or changing
scanner policy are not solutions delivered here.

Before any dependency removal, the next implementation must finish all CJS/ESM/
browser consumers, declared dependencies, full installed-copy inventory,
hash-guarded consumer patches, fail-closed importer coverage (including the
previously deferred syntax forms), complete pinned npm-ci closure and error
controls for del. The existing importer guard and embedded maps browser copy
are not changed or newly validated by this diagnostic. No orphan-copy removal
is claimed.

The 22 historical pinned source inputs still match their evidence hashes. The
parent checkout remains clean at `b5f158c9f4f00cc529bddf233e3a461e60356d69`.
Recovery artifact hashes were rechecked. Running the unchanged `validate` on
CI 41833235278's Kibana report still returns exactly the two unexpected
CVE-2026-118764 findings (10.2.4+cncguard.1 and 3.1.5).

Only after a real migration is prepared, on an adequately resourced authorized
parent runner, capture source hashes and build/scan fresh outputs:

```sh
docker build --pull=false --progress=plain -f deploy/images/kibana.Dockerfile \
  -t cnc-guard-audit:kibana .
trivy image --image-src docker --parallel 1 --scanners vuln --format json \
  --list-all-pkgs --output FRESH_IMAGE_SCAN.json cnc-guard-audit:kibana
python scripts/enforce_image_scan.py kibana FRESH_IMAGE_SCAN.json
```

Use the normal fresh DB and unchanged policy. Run the focused image regressions,
reconcile final package bytes and inventory, then complete Kibana+ES/browser and
CI acceptance with the existing CG32 resource gate. These commands are future
parent steps, **not executed here**; rebuilding this diagnostic-only commit
does not remove either finding. No human, SMB, CG32 or model acceptance is inferred.
