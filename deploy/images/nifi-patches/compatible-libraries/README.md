# Compatible-library candidate — component evidence only

Scoped source candidate on parent `f80c37f72e35d2a5568b5a0801e4304a23a1ce41`.
No image/archive was patched. No NiFi/container build, service, scanner exception,
metadata rewriting, root dependency change, push or PR operation is part of this
candidate. Final nested-image scanning and NiFi processor/runtime acceptance are
**pending**, as are original archive occurrence/classloader mapping and integration.
Component success does not establish a green gate or merge readiness.

## Decisions and exact replacement bytes

All bytes come unchanged from official Maven Central at
`https://repo.maven.apache.org/maven2/`. `pins.json` contains full artifact URLs,
coordinates and SHA-256 values for binaries, source JARs, POMs, required Guava
closure, SLF4J, POM ancestors and official fix commits. These are locally measured
SHA-256 pins obtained over HTTPS, not a claim of independent signature validation.
No JAR binaries are committed. Parent must use whole upstream JARs, preserving
native resources, signatures, service descriptors and Maven metadata.

| Candidate | SHA-256 | Current disposition |
| --- | --- | --- |
| Guava 33.7.2-jre | `b530942257fb935f8b2cfaa5f8eb5bd59c555fd8e8d01b8ce98912e077ea606c` | Component-tested for exact upstream 33.7.1-jre input only |
| RabbitMQ 5.37.0 | `b27134820890c5e56ed57d27cc50b70742fa2c31b36a6e9e28e14a43f34ff96f` | Parser tested; dependency closure blocks replacement |
| at.yawk LZ4 1.11.4 | `58c8e0b813960d2a248e050c353baea73139b48a2ffc55382d42c69707e17325` | Component-tested candidate |
| Snappy 1.1.10.9 | `35228628442e4b9797681c7cbd3b26594f6da3379159dbd0cb07094ed3aece0d` | Component-tested candidate |

RabbitMQ 5.36.1's exact Maven POM URL returned HTTP 404 during preparation:
`https://repo.maven.apache.org/maven2/com/rabbitmq/amqp-client/5.36.1/amqp-client-5.36.1.pom`.
The actual report and [upstream JSON advisory](https://github.com/rabbitmq/rabbitmq-java-client/security/advisories/GHSA-cqgh-8p3p-mx4m)
identify **5.37.0** as fixed. The [shortstr advisory](https://github.com/rabbitmq/rabbitmq-java-client/security/advisories/GHSA-7822-rcf6-97fx)
identifies 5.36.0. Thus 5.37.0 is the first published release covering both official
fix boundaries on the same 5.x branch; no major upgrade is proposed. The 5.36.0
intermediate control verifies corrected shortstr handling and the still-hanging
EOF comment parser. Do not promote 5.36.0/5.36.1 as covering both fixes.

Guava 33.4.8-jre and 33.6.0-jre scan-object hashes differ from upstream Maven JARs.
Their package version labels alone cannot authorize whole-object replacement;
they may be repacked or embedded in another bundle. Both are explicitly blocked.
The bounded API comparison also flags many declared-surface differences against
those upstream versions (including inheritance moves). These flags are conservative
review requirements, not proof every flagged member would fail JVM resolution.
33.7.1-jre -> 33.7.2-jre has no flagged differences. Guava candidate POM closure is
pinned, including failureaccess 1.0.3, listenablefuture's empty conflict-avoidance
JAR, jspecify 1.0.1, error_prone_annotations 2.50.0 and j2objc-annotations 3.1.
That proves the test classpath; NiFi's existing per-classloader closure must still
be inspected before changing or adding any dependency.

RabbitMQ 5.37.0 declares Netty transport/codec/handler **4.2.18.Final** (5.35.0
used 4.2.17.Final). These Netty artifacts/closure were not approved as replacements,
pinned or tested here. The plan therefore blocks RabbitMQ despite clean bounded
API results and passing parser tests with pinned SLF4J 1.7.36. Optional metrics,
Micrometer, OpenTelemetry and Jackson integrations and Netty transport are untested.
Do not interpret the parser's small test classpath as a complete RabbitMQ runtime.
LZ4 and Snappy have no required external runtime POM dependencies (test/provided
entries are excluded); their published JNI resources remain intact: 9 and 26 paths,
respectively, with no native resource paths removed relative to the old JARs.

## Evidence binding and parent handoff

`verify.py` requires the actual run **41810126327**, job **126507014432** reports:

- `image-scan.json`: `602ee0ca740c3cd2ca3a9ad2f8b06c74145edd944edafa01f3502eb36d427137`
- `nested-archive-scan.json`: `d06b864d28cd7c3c027bd66098934b3a65ffd482cf346ac235b952e54bfd7c18`

It checks zero standard findings and 59 distinct nested vulnerability/package/version
tuples, cross-checks all six focused object identities against cached
`vulnerable-objects.json`, and compares original object hashes to downloaded
upstream controls. `candidate-plan.json` records **all six** exact input hashes,
scan object locations, replacement hashes/URLs and blocker statuses. These are
scan exposure paths under `usr/share/cnc-guard/nested-jars/`, not original NAR
locations. The reports/cache supplied here do not establish original occurrences;
`original_nar_paths` is deliberately null and `patched` is false for every entry.

The parent must obtain the final image's exposure inventory, map each exact hash
to **every** original NAR/JAR occurrence and classloader, inspect shaded/repacked
objects, confirm required closure, and only then apply its separately reviewed
hash-guarded patcher. Reject blocked statuses. Even `component-tested-candidate`
is conditional on this inventory and runtime validation. Unknown bytes must fail
closed. Do not replace an entire fat JAR merely because its scan package name
matches Guava. No untested occurrence is claimed patched by this candidate.

## Reproduce

Use a new, owned cache directory outside the repository, or the prepared cache:
`/home/tears/.cache/cnc-nifi-ci-remediation-20261104/compatible-libraries-3e7e9435`.
No Maven execution or global install is needed: the harness uses the installed
JDK's `javac` directly, avoiding unpinned Maven plugins/shared `.m2` changes.
`toolchain-pins.json` validates the installed JDK executable/compiler, release,
modules and core JVM libraries before testing. Another JDK deliberately fails
until its suitability and pins receive separate review; pins are never auto-refreshed.

```bash
candidate=deploy/images/nifi-patches/compatible-libraries
cache=/home/tears/.cache/cnc-nifi-ci-remediation-20261104/compatible-libraries-3e7e9435
evidence=/home/tears/.cache/cnc-nifi-ci-remediation-20261104
python "$candidate/verify.py" --cache "$cache" \
  --reports "$evidence/artifact-2da877c" \
  --objects "$evidence/vulnerable-objects.json" --offline
LIBRARY_CACHE="$cache" LIBRARY_REPORTS="$evidence/artifact-2da877c" \
  LIBRARY_OBJECTS="$evidence/vulnerable-objects.json" \
  python "$candidate/test_verifier.py"
```

For fresh downloads omit `--offline`; only pinned official inputs are fetched,
and wrong/missing bytes, symlinks, changed reports, unreviewed inherited/profile
dependencies, compiler errors or probe failures abort verification. Each run
creates its own `proof-<timestamp>/` containing logs and, only after probes pass,
results and a conditional plan; failed runs have no new success plan. Four
negative tests exercise missing input, modified bytes under Python `-O`, symlink
input and report drift. Exit zero means component probes passed; consult plan
statuses for unresolved blockers. The POM closure checker is deliberately narrow,
not a general Maven resolver; it handles the inspected pinned POM shapes only.

Child processes run sequentially, pinned to one allowed CPU, core dumps disabled,
with 60 CPU seconds and wall deadlines. Java/javac use `-Xmx256m`,
`-XX:ActiveProcessorCount=1`, 96 MiB metaspace, 48 MiB code cache, 32 MiB direct
memory and 512 KiB stacks. RSS is recorded and checked against 512 MiB after the
probes; the offline verification measured 106,172 KiB maximum child RSS and
39,708 KiB verifier RSS. This is a measured check, not a kernel RSS reservation limit. No native
malicious fuzzing, OOM control or external service is used. EOF comment controls
are separate Java processes killed after two seconds; they spin without allocation.

## Regression coverage and limits

`LibraryProbe.java` exercises actual library code against pinned old/fixed JARs:

- **Guava:** normal serialization plus forged collection-size deserialization in
  CompactHashMap, CompactHashSet and MapMakerInternalMap. It follows the
  [official fix](https://github.com/google/guava/commit/b931fe9d6d5cf00bc55714ad3308d086f71850fe)
  using a bounded 100,000 size instead of Integer.MAX_VALUE and measures thread
  allocations; all three old versions allocate >200 kB per probe, while the fixed
  version stays below 200 kB (approximately 9–12 kB). No OOM is induced.
- **RabbitMQ:** valid JSON/UTF-8, 255 invalid continuation bytes echoed through
  ValueReader/ValueWriter, truncated strings on fixed code, EOF comments on
  old/intermediate/fixed code. The fix truncates replacement-character UTF-8 to
  <=255 bytes; it does not reject all invalid UTF-8. Old shortstr fails re-encoding;
  5.36.0 and 5.37.0 can re-encode. 5.35.0/5.36.0 comment controls time out;
  5.37.0 terminates. RPC broker acknowledgement/requeue behavior is untested.
- **LZ4:** block roundtrip, 10,000 bounded empty Java blocks (old recursive stack
  failure vs fixed EOF), eight empty 4 MiB-header frames (old ~67 MB allocations
  vs fixed ~39 kB), malformed header rejection, normal JNI compression and loading
  in a private tmpdir. The fixed extracted library has no `.lck` companion, matching
  [the extraction fix](https://github.com/yawkat/lz4-java/commit/7a48b7f6b8099b9dab6541e4ac2ee0979dc55aa3).
  [Buffer reuse](https://github.com/yawkat/lz4-java/commit/2acc0ec1ead226145c62a817c18c8ed49233a283)
  and [iterative blocks](https://github.com/yawkat/lz4-java/commit/c8ebf97d504fb34434fda46fc761e8202570e0d8)
  are tested directly. No adversarial filesystem race is performed.
- **Snappy:** normal JNI byte/int/stream roundtrips on old and fixed code; fixed
  typed-array misalignment rejection, negative/oversized array-copy ranges,
  disproportionate declared length (bounded 100,000), and stream typed-array range
  rejection, tied to [bounds/length fix](https://github.com/xerial/snappy-java/commit/943c6043a292568575e8347af4507d015e802c75)
  and [array/stream fix](https://github.com/xerial/snappy-java/commit/2d7ca71c087a98f1219fb2d51909f3891c3ce77b).
  Malformed JNI controls on 1.1.10.8 are deliberately not executed. This is
  selected regression coverage, not complete reproduction of all native exploits.

The classfile comparator checks every base public/protected class's declared
member descriptors/selected access flags and hierarchy, and native resource paths.
It excludes multi-release variants and does not prove reflection, serialization,
behavior, package-private consumers, inherited member resolution or complete JVM
linkage. Against exact controls it flags no changes for Guava 33.7.1, RabbitMQ,
LZ4 or Snappy. Base bytecode maxima are Guava Java 9, RabbitMQ Java 8, LZ4 Java 7,
Snappy Java 8. Actual execution was only OpenJDK **21.0.13+9 on Linux x86_64**;
other OS/architecture/libc/JDK combinations and all NiFi processors remain untested.

`verification-summary.json` is a compact local result; full logs and detailed
surface differences remain in the cache proof directory named there. Final
image scan, all occurrence replacement, dependency/classloader acceptance and
normal NiFi flow execution are still parent gates. This work adds no exceptions.
