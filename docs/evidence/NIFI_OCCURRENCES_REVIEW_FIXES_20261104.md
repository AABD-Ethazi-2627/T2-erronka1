# NiFi complete archive inventory and review corrections

This is preparation for PR #119, not patched-image or NiFi acceptance.
The parent incorporates the occurrence writer (`19b4b1d`, locally `1a1af46`)
and RabbitMQ transport supplement (`322ac9b`, locally `9634705`), then corrects
the independent component-review findings. Exact tested source bytes, commands,
proof paths and hashes are in the adjacent
[machine-readable evidence](NIFI_OCCURRENCES_REVIEW_FIXES_20261104.json).
The source was dirty during testing; hashes were captured **before** execution
and checked afterward. A commit label alone does not identify the tested bytes.

## Corrected guards

- The original parser verifier always leaves RabbitMQ blocked. Adding Netty JAR
  pins cannot grant transport readiness. The separate transport verifier must
  execute its seven real Java classpath configurations.
- POM resolution shares the strict transport resolver. Namespace-free, foreign
  and namespace-reset models fail; parents/BOMs and their ancestors require
  exact coordinates and content hashes. Unsupported inherited profiles,
  classifiers and artifact types fail. Additional official POM pins close the
  inspected model tree. Missing runtime artifacts remain blockers.
- The object grouping has an exact hash and must match scan locations in both
  directions. Empty grouping fails. Blocked shaded Guava entries now have
  **null replacement fields**, rather than suggesting a plain Guava JAR.
- Compilation and native extraction use fresh proof-local directories. Java
  injection environment variables are removed, truncated class files fail,
  source-local caches fail before creating output, and EOF timeout controls
  must print their parser-entry marker first.

Old proofs remain in git/history and cache. `candidate-plan.json` and
`verification-summary.json` describe the corrected parent reproduction. The
RabbitMQ child summaries retain their attribution; this evidence records a
separate parent execution. ABI checks do not prove inherited linkage,
package-private compatibility, serialization, native behavior, services or
multi-release dispatch. Snappy's stricter output-buffer precondition needs
consumer coverage. Malformed-native-input A/B tests were not run.

## Complete inventory

The writer initially rejected real legacy ZIP directory metadata: Unix host,
external attributes `0xffff0010`, trailing slash, STORED method, zero sizes
and CRC. The correction accepts only that inert empty-directory representation.
It does not extract paths or admit unknown regular-file modes, symlinks,
compressed/nonempty directories or other attributes. The new regression fails
against the original writer and passes now, with four negative variants.

All **156 public lib archive files** copied from the pinned NiFi image yield
**2,040 archive occurrences**, with inventory identity
`ce7f5a830051ff4c8da5672573e7005d58e739860e2be86c889cca6285445970`.
Every one of the scan's **17 object groups** has an exact-hash occurrence.
This covers the copied archive tree and supported archive extensions, not
arbitrary embedded blobs or the entire image filesystem.

| Candidate input | Occurrences |
| --- | ---: |
| Guava 33.7.1 | 7 |
| LZ4 1.11.2 | 3 |
| Snappy 1.1.10.8 | 9 |
| RabbitMQ 5.35.0 | 1 |
| Hadoop-shaded Guava / Iceberg-bundled Guava | 1 each |

All 156 source files remain byte-identical. No archive has been patched.
Stock byte equality does not establish consumer/classloader compatibility.
Shaded wrappers cannot be replaced by plain Guava.

## Independent verification

- **46 tests and 18 subtests pass**: writer/model guards, 13 transport
  model/integrity tests and six original-verifier negatives. The warning is a
  deliberately duplicated ZIP name in a rejection fixture.
- Original library probes pass offline with **90 pinned inputs**; maximum child
  RSS **109,392 KiB**. Guava 33.7.1, LZ4 and Snappy remain component candidates;
  RabbitMQ and the shaded wrappers stay blocked in that original plan.
- All **seven RabbitMQ transport configurations pass**, including no-Netty,
  Netty 4.2.17/4.2.18 and both SLF4J APIs; maximum child RSS **110,048 KiB**.
  These use loopback protocol fixtures, not a broker or NiFi execution.
- The image's AMQP NAR equals the official reference, SHA-256
  `4d43e10bcd08776abb1990dab8b7563559acfd5b44f10be63dd6366ec2469ca8`.
  NiFi's logging provider and classloader remain untested.
- Inventory completes in **47.44 s**, maximum child RSS **56,140 KiB**.
  Its CLI uses one CPU, 512 MiB virtual address space and no core dumps.
  Java-probe RSS is measured, not a kernel RSS reservation.

The full working-tree suite also passes: **935 tests, 395 subtests, four skipped**
in 73.92 seconds. This is a local result, not CI or an immutable-head claim;
the JSON records the source-timing limit. Final component/transport probes were
repeated afterward with their exact final source hashes.

## Remaining gates

Real `f80c37f` job **126529543749**, run **41816822549**, passes build and normal
scan, then fails the nested gate with the same **59 distinct tuples**. This
preparation changes no runtime archive or scanner policy. Each selected
occurrence still needs classloader/consumer review, then final image building,
both scans and NiFi acceptance. The two-finding Kibana gate, fresh CI, required
GitHub approval, CG32 resources, SMB and human academic acceptance remain open.
No new exception is authorized or applied.
