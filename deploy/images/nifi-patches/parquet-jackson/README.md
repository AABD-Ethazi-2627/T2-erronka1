# Parquet Jackson 1.18.1 — local wrapper candidate, runtime blocked

Scope: only this directory and `tests/test_nifi_parquet_jackson.py`. Hazelcast,
common helpers, Dockerfiles, scanner/gate/exception configuration, academic
manifest and the parent's concurrent Maven/Hadoop/atomic-plan work are untouched.

## Official inputs and actual code

Stock wrapper SHA-256:
`1914fed4ed18999ce98ad844aa5d0b09f31027be329ffd82d861d6f7c6f097c7`.
It is byte-identical to the official
[parquet-jackson 1.18.1 artifact](https://repo.maven.apache.org/maven2/org/apache/parquet/parquet-jackson/1.18.1/parquet-jackson-1.18.1.jar).
The sole selected occurrence is
`opt/nifi/nifi-current/lib/nifi-iceberg-parquet-writer-nar-2.12.0.nar` →
`META-INF/bundled-dependencies/parquet-jackson-1.18.1.jar`, outer SHA-256
`d8c2a22419cf91e483d2fa46cf242aaed5571d8af6f4afb0fa75626bd59ef82e`.
`candidate-plan.json` retains the original occurrence/chain and four scan tuples.
The current CI6d scan is pinned separately from any candidate result.

The captured official Maven version catalog ends at 1.18.1: no newer published
same-line wrapper from that catalog is available to test. The module/root
POMs and Apache parent 39 are pinned, together with official source archives.
The [official module source POM](https://raw.githubusercontent.com/apache/parquet-java/apache-parquet-1.18.1/parquet-jackson/pom.xml)
overwrites the root's minimization setting with `minimizeJar=false`, includes
Jackson core/annotations/databind, relocates `com.fasterxml.jackson` to
`shaded.parquet.com.fasterxml.jackson`, adds MR paths for 9/11/17/19/21/22,
and applies the services transformer. Apache parent 39 supplies Shade 3.6.2.
There are 1,110 actual classes in the wrapper, all Jackson, including relocated
annotations and core/databind PackageVersion classes. Actual old/fixed wrapper
probes report databind 2.22.2/2.22.3 and prove changed parser/cache behavior.
This is neither a metadata-only finding nor a plain-JAR replacement.

## Rebuild and preservation

`Shade.java` invokes only the pinned Apache Shade API, offline, with the exact
seven-JAR API classpath listed in `prepare.py`. No upstream Maven lifecycle,
plugin discovery, profile, install, arbitrary script or shared `.m2` executes.
The API driver follows the module's artifact order: core, annotations, databind.
No manually renamed classfiles or namespace migrations are used.

The old shaded payload's **1,121 entries** must equal the official wrapper.
The comparison excludes only aggregate manifest/LICENSE/NOTICE/DEPENDENCIES;
it rejects missing/different entries and extra Jackson classes/metadata.
The new payload uses coordinated official core/databind **2.22.3**, with the
same relocated annotations 2.22. Only 68 original entries differ; 68 replacement
entries carry changed code and its corresponding Maven/MR metadata. Every
identical entry stays in its original raw ZIP record. New/old component notices
are handled explicitly in local fork provenance; original wrapper aggregate
licenses, manifest and unrelated metadata remain intact.

Publication checks content, entry sets, raw local headers/compressed bytes/data
descriptors and central attributes (including UTF-8 flags on ASCII names and
zero external attributes), plus archive comment. The target must be unsigned,
unambiguous, unpatched and non-no-op. The local fork has explicit
`runtime_approved:false` provenance and is not an Apache release. The plan's
`replacement` remains null until independent QA.

All **215 stock roots** are compared to the hash-pinned acquisition lock before
and after. Cache inputs, executable sources, support locks and pinned JDK21
java/javac/modules/libjvm are also checked before/after. Publication occurs only
after those checks. Existing caches, originals, failed attempts and artifacts
are preserved. Large binaries/classes/logs are outside Git.

Every Java command takes one `flock --no-fork --timeout 10` on the shared
`candidate-heavy.lock`, with one CPU, 256 MiB heap, 96 MiB metaspace, 32 MiB
direct memory, 30 CPU/40 wall seconds, no cores and an allowlisted environment
with private HOME/user.home/tmp. Do not recursively wrap the Python preparation
or probes in the same lock. Static analysis takes its own single bounded lock.

## Actual verification and limits

The four tuples are mapped separately, including old/new affected-class hashes:

- CVE-2026-89425: discriminating actual-wrapper old/fixed DataInput token-error
  control, 4,295 → 457 characters; InputStream control stays 468.
- CVE-2026-91776: discriminating 1,500 benign distinct fallback type IDs → 500
  retained entries; repeated-ID control stays 1.
- CVE-2026-89407: pinned primary upstream evidence plus removal of the actual
  NumberInput regex field. This is a static fix marker, not timing/DoS proof.
- CVE-2026-91777: pinned primary upstream evidence and a normal 128-forward-
  reference identity check on both wrappers; no quadratic-cost reproduction.

Record/list/tree/Unicode JSON and ignored-record behavior are normal component
controls, not Parquet acceptance. Separate **real Parquet 1.18.1 consumers** run
`ParquetMetadata.toJSON/toPrettyJSON` through the relocated mapper and use
`ExampleParquetWriter`/`ParquetFileReader` to write/read a three-row UNCOMPRESSED
file, checking IDs, Unicode and an absent optional field. Both wrappers produce
identical 519-byte files. There is no Hadoop service or cluster; PlainParquet-
Configuration avoids default Hadoop configuration discovery. Class-loading logs
confirm the mapper's actual JAR and no Hadoop NativeCodeLoader path. No native
codec, hostile input, malicious polymorphic class, OOM or image build runs.

`consumer-pins.json` fixes the exact exercised classpath: six stock-equal Parquet
JARs, stock-equal SLF4J/Hadoop common, stock-equal JTS core and official Hadoop MapReduce core
(MapReduce is absent from the 215 acquired roots; it closes a symbol requirement
for this isolated harness, which also fails without it against the stock wrapper).
These libraries and POMs are read as data, never built. Early omitted-dependency
controls are retained in `consumer-explore*`: default reader needs Hadoop
Configuration; explicit Plain configuration additionally needs MapReduce's
FileInputFormat, and row writing needs JTS ParseException. Closing these
requirements lets the real path pass without substitutes. This is a pinned
classpath for the exercised APIs, not a full Maven mediation result or proof of
all optional dependencies in the NiFi NAR. AVRO, encryption, compression codecs,
large row groups, evolution and NAR delegation remain untested.

Static analysis checks 4,524 base classes in the candidate and six real Parquet
consumer JARs, recording 37 removed classes and six removed declared members.
It finds no direct references to removed symbols and no class-header/member-
access flag changes. It covers class/member/descriptor constant-pool references,
including changed wrapper code; it does **not** resolve inherited/interface
members, reflection, MR dispatch, resources, custom classloaders or complete
NiFi runtime closure. The version-qualified fast-double-parser removals remain
explicit in `linkage.json`. No CVE or runtime closure is inferred from the absence
of direct references or from updated version labels.

## Reproduction

Commands below were run against the pinned cache. Use fresh output names for a
repeat: exclusive publication refuses existing paths. Missing inputs may be
fetched only from their exact official pin URL into an owned cache, with SHA-256
verification before execution. Execution itself is offline.

```bash
ruff check deploy/images/nifi-patches/parquet-jackson tests/test_nifi_parquet_jackson.py
PYTHONDONTWRITEBYTECODE=1 python -m unittest discover -s tests -p test_nifi_parquet_jackson.py -v

PYTHONDONTWRITEBYTECODE=1 python deploy/images/nifi-patches/parquet-jackson/prepare.py \
  --cache /home/tears/.cache/cnc-parquet-jackson-20261105T080058Z \
  --output /home/tears/.cache/cnc-parquet-jackson-20261105T080058Z-final2 \
  --source /home/tears/.cache/cnc-stock-occurrences-20261104-e3888d81/source

PYTHONDONTWRITEBYTECODE=1 python deploy/images/nifi-patches/parquet-jackson/probes.py \
  --cache /home/tears/.cache/cnc-parquet-jackson-20261105T080058Z \
  --proof /home/tears/.cache/cnc-parquet-jackson-20261105T080058Z-final2 \
  --output /home/tears/.cache/cnc-parquet-jackson-20261105T080058Z-final2-probes

bash -c 'ulimit -c 0; ulimit -t 30; exec timeout -k 2s 40s \
  flock --no-fork --timeout 10 /home/tears/.cache/cnc-integration-audit-20261103/candidate-heavy.lock \
  taskset -c "$(awk "/Cpus_allowed_list/{split(\$2,a,\"[-,]\");print a[1]}" /proc/self/status)" \
  env -i PATH=/usr/bin LANG=C.UTF-8 LC_ALL=C.UTF-8 PYTHONDONTWRITEBYTECODE=1 \
  python deploy/images/nifi-patches/parquet-jackson/linkage.py \
  --cache /home/tears/.cache/cnc-parquet-jackson-20261105T080058Z \
  --proof /home/tears/.cache/cnc-parquet-jackson-20261105T080058Z-final2 \
  --output /home/tears/.cache/cnc-parquet-jackson-20261105T080058Z-final2/linkage.json'
```

`verification-summary.json` binds final code, candidate, logs, class fingerprints,
stock preservation, probes and focused tests. Earlier `explore*` objects are
historical and not final artifacts. No full suite or independent review is
claimed here. Parent QA, occurrence/atomic approval, complete symbolic and
classloader closure, NiFi/image scans, unchanged CG32 resources, real SMB and
human acceptance remain pending. Other wrappers, unmanifested AWS/Azure Jackson,
Kibana and root integration work remain separate.

## Independent review and parent regression supplement

The independent review of `0dafc5d` reproduced `bad77fac…` and found no defect
in its bytes, nor Critical/High finding. It permits continued bounded private
assembly only. Its report is `docs/evidence/CLAUDE_PARQUET_WRAPPER_REVIEW_20261105.md`.
The frozen preparation sources and JAR are unchanged. These additions live
outside the candidate provenance and do not reattribute the original 19 tests.

The parent now runs 27 portable tests. Added cases exercise external member and
descriptor references, header/member access changes, CLI failure on a real
consumer reference, the actual orchestration with data-only Shade/Java stubs,
stock/source/baseline rejection before publication, obsolete-class removal,
version metadata replacement, faulty-writer entry/content/raw/central changes,
CPU/core/affinity limits and the NativeCodeLoader rejection path. All 21 hand-
chosen mutations in the review now fail those tests. This is a bounded mutation
set, not exhaustive proof. The CLI's explicit six-consumer minimum remains a
future grouped reconstruction change; the current immutable consumer-pins and
the independent review both record the six actual consumer JARs.

`tests/fixtures/ParquetJacksonReferenceProbe.java` adds a separate benign
128-reference reverse-order counter, interleaved list and map identity/order
checks, and exact ObjectMapper origin checks. The parent compiles/runs it with
both unchanged wrappers in four bounded JDK21 commands: **8384 stock versus 128
candidate Key.equals calls**. No timing, hostile input, native codecs or NiFi
services are involved. This supplements CVE-2026-91777; the historical candidate
plan and its two-discriminant count remain historical. CVE-2026-89407 still has
static/upstream evidence rather than a local complexity discriminant.

The actual parent logs and source/JDK/artifact hashes are at
`/home/tears/.cache/cnc-parquet-reference-parent-20261105-03/`. Two preceding
attempts failed to obtain a successful compile (empty logs, flock return 1);
they are retained and are not counted as passes. Commands in each `.log.json`
record the finite lock wait, CPU/core/heap and environment bounds.

The review also records legacy DEPENDENCIES text, missing separate databind
NOTICE, empty versioned directories and uncompressed delta entries. These are
not represented as repaired or legally approved. Path canonicalization,
additional consumer controls and those metadata changes must be grouped with
any future source/JAR reconstruction, not silently applied to this frozen SHA.
The automated 519-byte equality/origin assertions in the older probes remain
a follow-up; equality was independently measured, not inferred as CVE closure.

**Scan accounting:** removing this wrapper alone cannot reduce the distinct
CI tuples: the same four Jackson 2.22.2 CVEs remain in simple carriers in five
NARs outside the current assembly. At most four of 63 raw records would be
removed; only a fresh actual scan can establish that effect. The authoritative
gate remains 59 distinct tuples. AWS/Azure carriers, classloaders, images,
CG32, SMB and human acceptance are still pending.
