# Hazelcast 5.7.0 Jackson reconstruction — experimental local candidate

This owns only this directory and `tests/test_nifi_hazelcast_jackson.py`.
It grants no runtime, scanner, NiFi, SMB, model, CG32, human or merge approval.
No Dockerfile, parent checkout, academic manifest, scanner rule or exception changes.

The child handoff below describes `f5fadedd` and its original artifact. Its plan
and verification summary are retained as historical evidence. The parent later
removed unused Python imports/an assignment and repeated construction/probes;
only the embedded preparation-source provenance changed in the resulting JAR.
[Current parent evidence](../../../../docs/evidence/HAZELCAST_PARENT_20261105.md)
identifies that artifact separately. Neither candidate is runtime approved.

## Provenance and reconstruction

The stock wrapper SHA-256 is
`241ec66cea8491787f68c3336f069ac463877af50bdb7676cd9d538f1940dc33`.
It equals the official [Hazelcast 5.7.0 Maven artifact](https://repo.maven.apache.org/maven2/com/hazelcast/hazelcast/5.7.0/hazelcast-5.7.0.jar).
Its one stock occurrence is
`opt/nifi/nifi-current/lib/nifi-hazelcast-services-nar-2.12.0.nar` →
`META-INF/bundled-dependencies/hazelcast-5.7.0.jar`, outer hash
`b734da18bdcc393e410f4a8e018b9a966e4c73cc35e4e584410d6883f6f35e08`.
The captured official Maven version catalog ends at 5.7.0. It provides no newer
published same-line wrapper to test; this is a local fork, not a Hazelcast release.
`pins.json` fixes the catalog, official binary/source/POMs and every tool input.

[Hazelcast's parent POM](https://repo.maven.apache.org/maven2/com/hazelcast/hazelcast-parent/5.7.0/hazelcast-parent-5.7.0.pom)
defines Shade 3.6.2, the two Jackson namespaces, annotation exclusion and
multi-release relocations. The source module POM defines the Hikari relocation
and services/NOTICE transformers. There is no minimization setting on this path.
The actual wrapper has both Jackson families under `com.hazelcast.shaded`,
including 2.21.2 and 3.1.2 PackageVersion classes; runtime controls confirm them.

The audited `Shade.java` invokes Apache Shade's API directly, offline, with an
explicit seven-JAR tool classpath. It runs no upstream Maven lifecycle, build
extension, plugin discovery, install or arbitrary script. The POMs and source
archive of Shade 3.6.2 are pinned for audit. Only the API path exercised here is
claimed; this is not a complete Maven plugin execution environment. Private
HOME/user.home/tmp, allowlisted environment, one CPU, 256 MiB heap, 96 MiB
metaspace, 30 CPU/40 wall seconds and no cores apply to every Java command.
Each command takes the shared `candidate-heavy.lock` once; do not wrap the
whole Python script in the same lock. No shared `.m2` is read or written.

Every old shaded component entry must equal the official wrapper, excluding
only the aggregate NOTICE. This checks real code, not metadata. An initial
Jackson-only relocation exposed two SubTypeValidator differences: the official
Hazelcast source relocates Hikari names in its rejection list. Including that
module rule reproduces both classes exactly. Do not remove this rule.

The candidate replaces complete core/databind pairs 2.21.2 → 2.21.7 and
3.1.2 → 3.1.7 using official pinned libraries and the verified transformations.
Both namespaces and unrelocated user annotations remain distinct. Jackson jr
3.1.2, unrelated Hazelcast classes/resources/services/native files, wrapper
manifest, aggregate original NOTICE and existing unrelated Maven metadata
remain unchanged. Shared component license entries are coalesced only when
identical. Updated component POM/properties accompany changed actual code;
no metadata is removed or relabelled to hide a finding. New component notices
and explicit local fork provenance are embedded separately. `entry-delta.json`
lists every selected/replacement/preserved entry and its content hash.

Unrelated local ZIP records are copied raw. Central-directory attributes,
comments, timestamps, flags, ordering and archive comment are checked separately;
only central offsets change. The UTF-8-on-ASCII regression matters here because
Python's default ZIP writer otherwise changes the acquired flags. All 215
stock roots are hash-checked against the acquisition lock before and after.
Pinned inputs, executable preparation sources and JDK21 binaries/modules/libjvm
are also checked before/after. Output publication is exclusive into a fresh
external directory. Failed and exploratory proofs are preserved in cache.

## Bounded verification and limits

`probes.py` compiles a frozen copy of the parent's bounded Jackson controls
against each actual wrapper, then runs old/fixed controls for malformed DataInput
token errors, type-ID cache retention and record ignored-name handling. It also
checks normal Unicode/list/record/tree JSON, Hazelcast `JsonUtil` through its
retained Jackson jr consumer, and standalone HazelcastJsonValue serialization.
Stock Jackson jr omits null map values on serialization; the consumer control
asserts this same behavior on old and fixed wrappers, plus null parsing.
It starts no Hazelcast instance, cluster, broker or service. There are no hostile
native/OOM probes or dangerous polymorphic classes. Classloader code sources
and library versions are logged; the actual wrapper files are hash-bound.

`linkage.py` compares base classes and all declared members, including private
members. It checks every unchanged wrapper class (including Hazelcast, retained
Jackson jr and other shaded libraries) for constant-pool class, descriptor and
member references to removed symbols. It records removals instead of hiding
internal changes. It does not resolve inherited/default/interface members,
reflection, serialization compatibility, MR dispatch, NiFi NAR inheritance or
resource/service loading. These remain explicit integration blockers even if
no direct reference is found. Neither local probes nor package versions prove
closure of all 37 CVE tuples. `candidate-plan.json` maps each tuple separately;
three advisory IDs have local bounded probes and the remainder have only the
parent's pinned primary upstream evidence.

Parquet's four tuples and the remaining plain Jackson objects are separate.
The four AWS and three Azure unmanifested Jackson carriers remain unassessed.
Kibana still has two findings. No final image scan or full suite is run here.

## Exact reproduction

Cache used: `/home/tears/.cache/cnc-hazelcast-recovery-20261105T072902Z`.
Fetch any missing `pins.json` input from its exact official URL into a fresh
owned cache, using exclusive creation, and require its SHA-256 before use.
Execution is entirely offline. Do not reuse an existing output directory.

```bash
PYTHONDONTWRITEBYTECODE=1 python -m unittest discover -s tests -p test_nifi_hazelcast_jackson.py -v

PYTHONDONTWRITEBYTECODE=1 python deploy/images/nifi-patches/hazelcast-jackson/prepare.py \
  --cache /home/tears/.cache/cnc-hazelcast-recovery-20261105T072902Z \
  --output /home/tears/.cache/cnc-hazelcast-recovery-20261105T072902Z-final2 \
  --source /home/tears/.cache/cnc-stock-occurrences-20261104-e3888d81/source

PYTHONDONTWRITEBYTECODE=1 python deploy/images/nifi-patches/hazelcast-jackson/probes.py \
  --cache /home/tears/.cache/cnc-hazelcast-recovery-20261105T072902Z \
  --candidate /home/tears/.cache/cnc-hazelcast-recovery-20261105T072902Z-final2/hazelcast-5.7.0-cnc-jackson.jar \
  --output /home/tears/.cache/cnc-hazelcast-recovery-20261105T072902Z-final2-probes

# Static Python analysis only; no nested JVM lock.
flock -w 5 /home/tears/.cache/cnc-integration-audit-20261103/candidate-heavy.lock \
  timeout -k 2s 40s env PYTHONDONTWRITEBYTECODE=1 python \
  deploy/images/nifi-patches/hazelcast-jackson/linkage.py \
  --original /home/tears/.cache/cnc-hazelcast-recovery-20261105T072902Z/hazelcast-5.7.0.jar \
  --candidate /home/tears/.cache/cnc-hazelcast-recovery-20261105T072902Z-final2/hazelcast-5.7.0-cnc-jackson.jar \
  --output /home/tears/.cache/cnc-hazelcast-recovery-20261105T072902Z-final2/linkage.json
```

`verification-summary.json` identifies the final artifact/proof, logs and
source hashes. Earlier `proof*`, `final`, `probes*` directories are historical
and must not be substituted for the final artifact. Parent independent QA,
consumer closure/classloaders, NiFi/final-image scans, unchanged CG32 resource
gate, real SMB and protected/human acceptance remain pending.
