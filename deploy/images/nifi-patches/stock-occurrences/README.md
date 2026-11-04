# Stock Guava / LZ4 / Snappy occurrence candidate

Preparation only, based on parent `f4e32bf528536c36e5b14efbe702b68383c346aa`.
No rooted archive is patched. No real occurrence has approval status.

**Snappy is blocked by a reproduced consumer incompatibility.** With the official
Hadoop 3.5.0 consumer from the image's `nifi-iceberg-parquet-writer-nar`, a normal
4096-byte run of `A` compresses and roundtrips on Snappy 1.1.10.8. On 1.1.10.9 it
throws `IllegalArgumentException: not enough space for output: need 4,810 bytes,
but only 0 remaining`. Hadoop allocates equally sized direct buffers and sets
the compressed buffer limit to zero before `Snappy.compress`. The new Snappy
precondition checks remaining output space. This is normal consumer input, not
an old-native malformed-input probe. `HadoopProbe.java` reproduces it without
starting Hadoop or NiFi. A compatible consumer correction needs separate work
and review; do not omit this occurrence to force an executable Snappy plan.

## Coverage and identities

Owned cache: `/home/tears/.cache/cnc-stock-occurrences-20261104-e3888d81`.
Public stock image: `apache/nifi:2.12.0@sha256:6f7f2840dbf178c6dd3fa13435b9b358f3be3c6fb7417de467a35a267f4d28ad`.
`acquire.py` creates a network-disabled `/bin/false` container, never starts it,
streams the public filesystem export, saves only regular library archives under
`opt/nifi`, skips configuration/state/log/repository/extension volume paths,
and removes only that stopped container and its own anonymous volumes. It does
not pull images. All other exported tar payloads are discarded, never saved.
Image metadata, exact commands, stopped state and public archive hashes are in
`acquisition.json`, `image.json`, `container.json` in the cache.

215 public archives: 156 under `nifi-current/lib`, 59 under toolkit/lib.
The complete supported archive inventory has 2099 occurrences and identity
`5ef465917d5de6c50794c674f3866f22c8b604e4b7a9f7b5b8822ce773980e32`.
No selected family occurs in toolkit; counts remain Guava 7, LZ4 3, Snappy 9.
All 156 original lib preimages match the preserved earlier source snapshot.
`source-lock.json` binds all 215 roots. Other embedded non-archive blobs,
mounted extensions and future image/package changes are outside this coverage.

The runtime Dockerfile copies all `/opt/nifi` and changes only the four
bootstrap/toolkit Jackson core/databind JARs in this Java tree. Those replacements
do not alter the selected three families. The inventory is deliberately the
stock preimage: the parent must inventory and scan the assembled runtime again.
No final image identity or acceptance is inferred from this acquisition.

`candidate-plan.json` maps every selected leaf hash to outer path, member path,
complete hash chain, NAR identity/parent manifests, bundled dependency Maven
metadata and source hashes, plus referring class names and hashes. It retains
replacement identity even for the technically incompatible *stock* Snappy pair;
its blocked status is mandatory. It contains no shaded/repacked candidate inputs.
Resources include all non-class entries, native binaries, service descriptors,
properties and manifest bytes for both exact libraries. No resource paths were
removed. Changed content hashes remain visible, rather than being called equal.
Guava's pinned failureaccess 1.0.3 is visible in every Guava NAR closure. Other
annotation/empty-listenablefuture dependencies retain their visible metadata.

## Consumer evidence and limits

`probe_consumers.py` runs an isolated classpath using actual image Kafka 4.3.1,
Jimfs 1.1 and Hadoop 3.5.0 JARs, with exact source-lock and library-pin checks.
It records source, JAR, executable and resulting class/log hashes. Kafka's normal
Snappy and LZ4 roundtrips and Jimfs's Guava-backed filesystem operations pass
on both old/new pairs. Normal array/direct Snappy roundtrips using
`maxCompressedLength` pass on both. Hadoop's regression is independently
reproduced on both. Java 21 results are in `java21-probes`; earlier Java 27
explorations are retained separately and are not image evidence. Every Java
child has one CPU, 256 MiB heap, 96 MiB metaspace, 25 s CPU/40 s wall limits and
no core dumps; native extraction and compiled classes use fresh owned cache.

The official-source review records URLs/hashes and source lines for Avro,
Kafka, NiFi compression/record processors, ZooKeeper, Parquet and Hadoop.
NiFi processors use Snappy streams; Avro and Parquet explicitly size compression
buffers with `maxCompressedLength`. Hadoop violates the new precondition.
These source observations do not execute those NiFi processors or establish
source-to-bytecode build equivalence. `source-review.json` records the snapshots.

Package references are byte searches in class constant data, not a complete JVM
linker. They can include shaded/self references and dead paths and miss reflection.
Manifest parent closure and descendant consumers are recorded, but framework
loader visibility, child-first precedence, instance cloning, resource dispatch,
all other consumers, service loading and final-image native extraction remain
unverified. No synthetic whole-image classpath is used as compatibility proof.
Guava and LZ4 are technically eligible exact-byte candidates with **partial**
consumer coverage, pending parent QA; Snappy's complete hash group is blocked.

## Reproduce and hand off

Run from the repository root, with Java 21 selected. Every output below is a
new external cache path; preserve earlier proof directories.

```bash
P=deploy/images/nifi-patches/stock-occurrences
S=/home/tears/.cache/cnc-stock-occurrences-20261104-e3888d81/source
C=/home/tears/.cache/cnc-nifi-ci-remediation-20261104/parent-verified-1793795867722215369/component
# Optional fresh acquisition; requires the pinned image already present:
python "$P/acquire.py" /home/tears/.cache/cnc-stock-new-acquisition
python "$P/map_candidates.py" "$S" "$C" > /home/tears/.cache/cnc-stock-new-candidate.json
PATH=/usr/lib/jvm/java-21-openjdk/bin:$PATH JAVA_HOME=/usr/lib/jvm/java-21-openjdk \
 python "$P/probe_consumers.py" "$S" "$C" /home/tears/.cache/cnc-stock-new-proof
python "$P/emit_plan.py" "$P/candidate-plan.json" --families guava lz4 \
 > /home/tears/.cache/cnc-stock-unapproved-plan.json
python -m pytest -q tests/test_nifi_stock_occurrences.py tests/test_patch_nested_jars.py
```

The emitter defaults to unapproved writer-shaped plans. It refuses blocked,
missing, null and drifted inputs. The real prepared plan remains unapproved.
Only **after independent parent QA/review** may the parent provide a JSON review
record with exactly `candidate_sha256`, `families`, `decision: "approved"`, and a
nonempty `review_reference`. The hash must identify the candidate bytes being
reviewed and the families must equal the requested complete subset. This is an
explicit caller attestation, not automated proof that review occurred.

Then emit with `--review-record /external/review.json` and use the existing
writer's default dry-run against `$S` and a fresh external output directory.
The writer rechecks the entire inventory, every occurrence and replacement hash.
Only after that dry-run and further parent authorization should the parent use
`--apply` on a fresh copy overlay. All such promotion/application is **unexecuted**
here. Snappy cannot be emitted while blocked. Fixture tests exercise approved
status only on synthetic data.

Remaining parent gates: independent QA of these scripts and consumer findings;
all missing consumer/runtime proofs; compatible Hadoop correction before any
Snappy promotion; final image build and both scans; NiFi/classloader, native,
SMB and human acceptance; protected CI/reviews. CG32 remains unchanged. This
component work grants no exception, gate waiver, PR, push, merge or deployment.
