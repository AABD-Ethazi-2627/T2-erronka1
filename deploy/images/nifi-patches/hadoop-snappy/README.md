# Hadoop 3.5.0 / fixed Snappy buffer candidate

Preparation only. The historical v1 proof below is based on parent `8becc805`.
The v2 correction additionally restores unreadable output after any compression
exception. `candidate-pin.json` binds its source, class and complete artifact;
`jdk21-pins.json` must match all tools/VM inputs before execution.
The default mapping still blocks all nine Snappy occurrences. An explicit v2
candidate enables only a hash-bound atomic Hadoop-plus-nine-Snappy assembly
plan with a separate review record. This is not runtime or human approval and
does not modify stock archives, images, services or scanner policy.

## Source decision and exact change

On 2026-11-04 the [Apache release list](https://hadoop.apache.org/releases.html)
and [Central metadata](https://repo.maven.apache.org/maven2/org/apache/hadoop/hadoop-common/maven-metadata.xml)
list 3.5.0 as the only published 3.5 release. Their exact snapshots, the official
source JAR, POM and binary JAR are pinned by full SHA-256 in `pins.json`.
No published compatible same-line fix was identified. This is an explicit local
source correction, **not an upstream backport claim or Apache release**.

`buffer-protocol.patch` documents the three changes made by `prepare.py`:

- Allocate `Snappy.maxCompressedLength(directBufferSize)` output bytes. For a
  4096-byte block this is `32 + 4096 + floor(4096/6) = 4810` bytes.
- Constructor/reset/no-input state exposes zero readable output. Before each
  actual compression, clear the exhausted output to position 0 / limit capacity.
  Snappy leaves output position 0 and sets limit to actual compressed length.
  Partial caller reads drain that limit before any new compression. Clearing
  for writing happens inside `compressDirectBuf`, after saved input is loaded;
  the empty-input path therefore never exposes uninitialized output bytes.
- If compression throws `IOException`, `RuntimeException` or `Error`, restore
  output limit zero before propagating it. Retries cannot drain stale output.
  `FaultProbe` tests these failures with a pure Java stub, including partial
  output writes; no native library is loaded by the fault tests.

Input position/limit handling, finish, reset, saved-input handling and counters
otherwise retain the exact original source. No Snappy source or byte changes.
Fixed Snappy remains the complete official 1.1.10.9 JAR, SHA-256
`35228628442e4b9797681c7cbd3b26594f6da3379159dbd0cb07094ed3aece0d`.

## Historical v1 proof and current v2 pin

Current artifact name: `hadoop-common-3.5.0-cnc-snappy-buffer-v2.jar`.
Expected SHA-256: `e2ff7c642f17743f0816a941d93714a0ae413203112e6a7d2e5f5bcf876329d2`.
The v2 source/bootstrap compilation is separate from the historical v1 proof.
Do not attribute the v1 test execution below to v2; the parent must repeat the
bounded runner before selecting the new group.

Final proof cache: `/home/tears/.cache/cnc-hadoop-snappy-proof-20261104-sol-7`.
Candidate: `hadoop-common-3.5.0-cnc-snappy-buffer-v1.jar` in that cache.
Expected SHA-256: `599a61b22f6cde7c12dce8a1240217d2285f57e619c1ebc051e0a3414aa52fdb`.
`execution.json` records exact bounded commands and stdout/stderr; `summary.json`
records input/tool/source-before-after and output hashes, changed entry hashes,
ABI, limits and gaps. Prior attempts remain in sibling `sol-1` through `sol-6`
proof directories, including the rejected variant assumption and ZIP attribute
check; they are not the final execution.

Exact original Hadoop JAR is extracted read-only from the pinned original NAR:
`nifi-iceberg-parquet-writer-nar-2.12.0.nar`, member
`META-INF/bundled-dependencies/hadoop-common-3.5.0.jar`, SHA-256
`dad07af66b59454e71b046a2fce0c0fddb9c522eadd146075e6add82aad86ce6`.
The downloaded official binary must have that same hash. The original source
recompiled with Java 21 `--release 17 -g -proc:none -implicit:none` must exactly
reproduce `javap -c -p` instructions/constant references. Original and corrected
`javap -p -s` must match, including private/package symbols; class major is 61.
Java 21 executables, modules, libjvm and release file are hash-pinned and checked. This is symbolic
ABI and instruction evidence, not an upstream reproducible-build attestation.

All unrelated JAR entry contents, resources, Maven metadata, manifest, services,
natives and ZIP entry attributes remain unchanged. The packager copies unrelated
raw local records (compressed bytes and descriptors), relocating only central
header offsets. It uses Python ZipFile internals for this narrowly verified copy;
portable fixture tests and the full candidate comparison guard that dependency.
It retains the changed class's data-descriptor flag. It adds
`META-INF/cnc-guard/hadoop-snappy-local-patch.json` with explicit local provenance,
original/replacement class hashes, source identity and `approval: false`.
The original version remains scanner-visible 3.5.0; nothing is relabeled as fixed
upstream, and no scanner finding is retired. Signed targets/ancestors fail closed;
signatures and digest resources are never removed.

Complete recursive traversal of all 215 hash-locked stock archives maps five
`SnappyCompressor.class` names in `occurrences.json`: **one exact Hadoop class**,
two Airlift classes, one Parquet class and one MongoDB class. No relocated Hadoop
`SnappyCompressor` name was found. Other names are recorded, unmodified, and are
not Hadoop compatibility claims. Traversal covers archive class entries, including
relocated package prefixes, not renamed/obfuscated classes, opaque non-archive
blobs, future extensions or runtime dispatch. All 215 original hashes must match
before and after the proof. Traversal includes `.jar`, `.nar`, `.war` and `.zip`.

The original 4096-byte A probe succeeds with old Snappy and fails with fixed
Snappy with exactly the intended output-space guard. Capacity-only fails with
zero remaining; limit-only fails with 4096 remaining versus 4810 needed. These
negative controls use only compressible A with the fixed guard. The corrected
candidate runs 70 cases on **each** old and fixed Snappy: empty/small/boundary,
deterministic incompressible, output offsets, zero and partial output reads,
chunked input, saved multiblock input, reset/reuse/reinit, counters and actual
Hadoop BlockCompressorStream/BlockDecompressorStream framing. Two fixed-library
normal-input controls independently verify insufficient-capacity/zero-limit
security rejection. No hostile old-native input is used.

The tested closure is only the exact Hadoop JAR, official Snappy JAR, stock SLF4J
API and pinned JDK. New code calls the existing Snappy API and adds no dependency.
Full Hadoop/NiFi dependency resolution, configured/pooled `SnappyCodec` factories,
other consumers, classloaders, native extraction in the final image and SMB remain
unverified. SLF4J's absent-provider warning is expected in the isolated test.
The later `6d67bc2` CI closes the historical ea9 disk-export failure. Its nested
scan has 63 vulnerability records and 59 distinct blocking tuples; Kibana has
two blocking tuples. CG32/SMB, protected checks/review and human acceptance remain
parent gates. The independent v1 review also exercises uniform-size pooled
`SnappyCodec` on a flat NAR-library classpath; it does not prove real NAR dispatch.
Mixed-size CodecPool configurations have pre-existing incompatibilities and are
not supported by this candidate's evidence.

## Reproduction

Use a fresh cache outside the repo, stock source, acquired inputs and `.m2`.
Fetch only each literal HTTPS URL in `pins.json`, store its named file under a
fresh acquired cache, and verify its SHA-256 before use. No remote script or Maven
plugin is executed. Existing acquired cache:
`/home/tears/.cache/cnc-hadoop-snappy-20261104-sol`.

```bash
PYTHONDONTWRITEBYTECODE=1 python -m unittest discover -s tests -p test_nifi_hadoop_snappy.py
ruff check --select F,E9 deploy/images/nifi-patches/hadoop-snappy/prepare.py tests/test_nifi_hadoop_snappy.py
python -B deploy/images/nifi-patches/hadoop-snappy/prepare.py \
 /home/tears/.cache/cnc-stock-occurrences-20261104-e3888d81/source \
 /home/tears/.cache/cnc-nifi-ci-remediation-20261104/parent-stock-1793798208840664428/component \
 /home/tears/.cache/cnc-hadoop-snappy-20261104-sol \
 /home/tears/.cache/cnc-hadoop-snappy-proof-FRESH-V2-DIRECTORY
```

Java children use an explicit minimal environment, one CPU, 256m heap, 96m
metaspace, 25s CPU/40s wall, no cores, fresh class/native/tool temporary directories.
Each child takes the common candidate lock with a 30-second maximum wait; the
40-second execution deadline is separate. Do not add an outer lock around the runner.
The Python traversal is serial, depth-limited to 8 and embedded archive size to
256 MiB; this is not a whole-process memory reservation. No OOM probe, network
consumer, broker, NiFi, Docker, image build or runtime service is run.
