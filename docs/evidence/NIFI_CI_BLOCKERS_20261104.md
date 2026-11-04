# NiFi nested-image CI audit — 2026-11-04

Scope: PR119, current local code `6a11161fd1d6834167e741aea25ba595a0c0e01d`.
This audit downloaded retained CI reports and three official Maven artifacts,
inspected bytecode with `javap`, and ran focused Python tests. No image was built,
no service started, and no runtime dependency, scan gate or exception was changed.
The old dirty infrastructure worktree was inspected read-only and preserved.

## Confirmed failure, not a transient build problem

The preceding dependency run is
[41606399087](https://github.com/AABD-Ethazi-2627/T2-erronka1/actions/runs/41606399087),
at source `6c5a056267dffec1a66b11c89d30a772c5dc1b19`; its NiFi job is
[125817188003](https://github.com/AABD-Ethazi-2627/T2-erronka1/actions/runs/41606399087/job/125817188003).
Downloaded artifact: `image-nifi`.

| Report | Actual image ID | Findings |
| --- | --- | --- |
| `image-scan.json` | `sha256:428b94c92438c67b923f6896809eb63dfdbdee081497c9c4db0e56ed7da728a5` | No reported vulnerabilities |
| `nested-archive-scan.json` | `sha256:8161ccd8a8ebc1f5adb8c2befb26789384555db374ffa1c1b6fbc033b22d37f7` | 59 distinct vulnerability/package/version tuples, 17 package/version groups, 15 distinct vulnerable objects |

Report SHA-256 values, respectively:
`36614f142a545702a82e4790c1667f709920b5e0373ce50ab2fe19747cf7e1dc`
and `b67ceb35370bc70d551f14b36ed08db6bdb25f6ec998010021e6747eb51ede30`.
The nested report was created at `2026-11-03T09:35:51.171238111Z`.
These are historical, immutable evidence; the new CI run must be checked separately.

The current NiFi dependency-copy instructions match that run. The subsequent
Dockerfile change bounds the shared uv compilation jobs; it does not replace the
vulnerable nested Java dependencies. Therefore a green normal scan alone cannot
establish closure. The nested gate must remain blocking.

## Affected families and reported repair branches

These candidate versions come from the retained scan, not a compatibility result:

| Family | Installed versions | Candidate branch to verify |
| --- | --- | --- |
| Jackson 2 core/databind | 2.21.2, 2.22.2 | Aligned 2.21.7 or 2.22.3 family, including shaded consumers |
| Jackson 3 core/databind | 3.1.2, 3.2.2 | Aligned 3.1.7+ or 3.2.3+ family, including shaded consumers |
| Guava | 33.4.8-jre, 33.6.0-jre, 33.7.1-jre | 33.7.2-jre |
| RabbitMQ AMQP client | 5.35.0 | 5.36.1 or later compatible release |
| LZ4 | 1.11.2 | 1.11.4 |
| Snappy | 1.1.10.8 | 1.1.10.9 |
| OpenTelemetry API | 1.62.0 | 1.67.0, with related API/context/common compatibility checked |
| Wire runtime/runtime-jvm | 5.2.0 | Published fixes start at 6.3.0, requiring an ABI decision |

The active Dockerfile only replaces the standalone bootstrap and toolkit Jackson
2.22.2 JARs with 2.22.3. That does not replace dependencies inside NARs or relocated
Jackson code in other bundles. The old worktree contains unpromoted nested ZIP,
shading and Wire reader candidates. Importing them without compilation, API
comparison, parser regressions and final nested-image scanning would not provide
the missing proof.

## Concrete Wire ABI blocker

The [maintainer advisory](https://github.com/square/wire/security/advisories/GHSA-7xpr-hc2w-34m9)
identifies a negative-length skipped-group decoding flaw and lists Wire 6.3.0 as
fixed. The later [reader-boundary advisory](https://github.com/square/wire/security/advisories/GHSA-9rm7-3qhh-h2mc)
describes additional related bounds checks. A backport needs both its exact scope
and malformed-input regressions, rather than a version label alone.

Official Maven Central JARs were downloaded and hashed:

| Artifact | SHA-256 |
| --- | --- |
| `wire-runtime-jvm-5.2.0.jar` | `c247dbd0dc4f42546090cf203a928400bab5c561746b3ffa2fd3270502d7c5f1` |
| `wire-runtime-jvm-6.3.0.jar` | `015fe322956d43efeed350ece606e3c2eb6f7448e1b982eca64dcc4ff9b4a5d0` |
| `wire-schema-jvm-5.2.0.jar` | `dade32aba414c7695c90022f028705c67f65b88d26ab04f0168334838142b86e` |

`javap -p` confirms a binary-incompatible constructor change in
`com.squareup.wire.internal.RuntimeMessageAdapter`:

```text
5.2.0: RuntimeMessageAdapter(MessageBinding)
6.3.0: RuntimeMessageAdapter(MessageBinding, boolean)
       RuntimeMessageAdapter(MessageBinding, boolean, int, DefaultConstructorMarker)
```

`javap -p -c` on Wire schema 5.2.0 proves that
`SchemaProtoAdapterFactory` calls the removed one-argument constructor:

```text
376: invokespecial ... RuntimeMessageAdapter."<init>":(Lcom/squareup/wire/internal/MessageBinding;)V
```

Consequently, a runtime-only replacement with 6.3.0 is not a binary-compatible
repair for this consumer; executing that path would fail linkage. This audit did
not execute the path or establish NiFi reachability. Upgrading the whole related
Wire dependency set and its consumers, or compiling and validating an ABI-preserving
Wire 5 backport, requires additional work. A backport preserving the 5.2.0 package
identity would also remain reported by the current version-based scan; it cannot
be declared green by rewriting its metadata or suppressing the nested gate.

## Verification and remaining acceptance

`OPENBLAS_NUM_THREADS=1 .venv/bin/python -m pytest -q
tests/test_nested_jar_audit.py tests/test_image_scan_gate.py` passed:
**12 tests and 20 subtests**, in 0.22 seconds. These verify archive exposure and
gate behavior, not patched NiFi runtime compatibility.

Evidence root: `/home/tears/.cache/cnc-nifi-ci-remediation-20261104/`.
It retains the original reports, `scan-findings-summary.json`,
`vulnerable-objects.json`, focused-test log, official artifact provenance and
complete `javap` outputs under `wire-abi/`.

No production-code patch is promoted by this audit. A correct remaining sequence
is: select compatible versions per classloader; produce hash-pinned replacement
and relocated bytes; compile/compare the Wire consumer ABI; exercise valid and
malformed decoding and relevant NiFi processors; build both final and archive-audit
images; then rerun both strict gates. The latest PR head must pass those checks
and its required GitHub review before merge.
