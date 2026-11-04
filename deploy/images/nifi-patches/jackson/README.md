# Jackson nested-archive candidates — component preparation only

Child base: `f4e32bf528536c36e5b14efbe702b68383c346aa`; parent incorporation
starts after `6d67bc2`. Later review corrections are documented separately.
No rooted runtime archive is patched. No Dockerfile, runtime manifest, scanner
metadata, security exception or CG32 gate changes; the academic manifest tracks
the candidate source and evidence.
The 59-tuple nested gate and two-finding Kibana gate remain blocking. There is
no NiFi/image/SMB/human acceptance or classloader approval here.

## Candidate decisions

Maven Central publishes old/fixed core and databind binaries, sources and POMs
for **2.21.2 → 2.21.7, 2.22.2 → 2.22.3, 3.1.2 → 3.1.7 and 3.2.2 → 3.2.3**.
`pins.json` identifies actual bytes, including model ancestors/imported BOMs.
`official-advisories.json` records primary FasterXML affected/fixed metadata;
`upstream-pins.json` pins full original advisory responses and three inspected
fix patches kept outside git. The official fixes include
[bounded error tokens](https://github.com/FasterXML/jackson-core/commit/211cf2c5d91abbec38067f37efc1363cd4e88ee3),
[bounded type-ID caching](https://github.com/FasterXML/jackson-databind/commit/2870d1d6dc1b7e1c07ee11dd5b04ab71cddbb577), and
[ignored record names](https://github.com/FasterXML/jackson-databind/commit/baa2cdf5ca2b2717fbb88d91955d69d8651df3e4).
Same-minor candidates avoid a major/minor migration; publication and component
success do not establish suitability for every consumer.

The scan's ten Jackson package/version/object rows refer to six unique objects:

| Object SHA-256 prefix | Actual input | Decision |
| --- | --- | --- |
| `241ec66cea849178` | Hazelcast 5.7.0; Jackson 2.21.2 and 3.1.2 metadata | Wrapper-specific rebuild required; replacement null |
| `1914fed4ed18999c` | Parquet Jackson 1.18.1; Jackson 2.22.2 metadata | Wrapper-specific rebuild required; replacement null |
| `ff167a6317be1589` | Stock Jackson 2 core 2.22.2 | Proposed 2.22.3; ABI/consumer review blocked |
| `d0da14c12b16b5d5` | Stock Jackson 2 databind 2.22.2 | Proposed 2.22.3; consumers unapproved |
| `93d9090b8c505b2f` | Stock Jackson 3 core 3.2.2 | Proposed 3.2.3; consumers unapproved |
| `d27509f990d990fc` | Stock Jackson 3 databind 3.2.2 | Proposed 3.2.3; ABI/consumer review blocked |

Full digests, every occurrence, ancestry hashes and decisions are emitted in
`candidate-plan.json`. Stock LIB includes bootstrap occurrences that the parent
image already replaces; this verifier does not claim they survive in that image.
The wrappers must never be replaced wholesale by a plain Jackson JAR. Their
embedded classes/relocations need wrapper-specific sources, dependencies,
rebuild and consumer tests. Research probes of 2.21/3.1 are not wrapper tests.

This table is the **metadata-scanner universe**, not all Jackson code. Class
packages also identify AWS `third-party-jackson-core-2.54.14.jar` (four copies,
`software/amazon/awssdk/thirdparty/jackson/core`) and Azure `azure-json-1.5.1.jar`
(three copies, `com/azure/json/implementation/jackson/core`) without Jackson Maven
identity. `embedded-jackson-inventory.json` and the plan explicitly retain them
as unassessed blocked carriers. The independent review observed AWS 2.21.4 with
an unbounded DataInput token error; Azure's subset/version remains unclassified.
Neither observation proves NiFi reachability or absence of other renamed copies.

## Verification and scope

`verify.py` checks the exact scan, object grouping and complete public inventory
against `input-lock.json`, checks scan/group equality both ways, and re-reads
every source root and all selected nested chains from the immutable 156-file
source, rejecting symlinks, missing/extra roots and unselected-root drift. The four plain
objects equal their official old Maven JARs. All 156 source hashes are compared
before and after. Inputs, code, generated classes, logs and local JDK binaries,
modules and libjvm are hashed; proof summaries identify actual tested bytes.
The strict existing model/ABI helpers are read-only and hash-pinned in
`support-lock.json`.

The inspected old/fixed databind Maven closures each require core plus
`com.fasterxml.jackson.core:jackson-annotations` 2.21 or 2.22. Jackson 3 shares
these annotations; it does not use an invented tools.jackson annotations JAR.
Core/databind Java namespaces remain separate. No build, plugin or profile is
executed. Unsupported model shapes fail closed; this restricted resolver is
not full Maven mediation. Optional/test/provided dependencies are recorded.
Core/databind are paired atomically per namespace/version/context; a missing
companion or either ABI block keeps the complete pair blocked.

Safe Java probes cover malformed-token bounds, type-ID cache retention and
record ignore/naming behavior with old/fixed controls, plus record/list/tree/
unicode roundtrips. `coverage.json` maps all 19 advisory IDs explicitly: three
have local runtime probes; the other sixteen have primary upstream evidence
only. In the four plain candidates only two advisory IDs/four of seven tuples
have an old/fixed discriminating probe; the record-ignore case is an earlier-fix
positive control there. No claim of redundant-fix coverage is inferred. No OOM, DNS, network
provider, external service or dangerous polymorphic class is exercised.

Actual stock `json-community-utils-1.3.0.jar` (both NAR and UI-WAR occurrence)
passes a map/list/null roundtrip on 3.2.2 and 3.2.3. Actual stock CSV and JSR310
2.22.2 JARs are checked by SHA and tested with 2.22.2 and 2.22.3 core/databind.
These bounded consumer paths do not exercise complete Jolt transformations,
NiFi processors, all Jackson module APIs, or all optional dependency closures.
`consumer-contexts.json` lists siblings per selected archive context;
`extension-inventory.json` retains Jackson datatype/dataformat/module Maven
metadata and hashes from the complete inventory. YAML/Smile/CBOR/Avro, Jakarta
XML binding/schema and other consumers remain untested. Their full dependency
closures, services and inherited NAR/webapp delegation are integration blockers.

Symbolic ABI comparison records every public/protected base-class member
removal/hierarchy change without suppressing internals. Jackson 2 core removes
four version-qualified internal fast-double-parser classes. Jackson 3 databind
removes `StdDateFormat.DATE_FORMAT_RFC1123`, and 3.1 additionally removes
`UnwrappedPropertyHandler._hasUnwrappedAnySetter`. These need consumer reference
and linkage review. The comparison does not establish inherited or package
private linkage, serialization, resource/service or multi-release compatibility.
The four core classes are public; 44 versioned-package entries change overall.
The removed DateFormat field is not an inlineable constant and remains blocked.

Each Java/javac process has one CPU, 256 MiB heap, 96 MiB metaspace, bounded
code/direct caches, 30 CPU seconds, 40 seconds wall time and no core dumps.
The JDK21 toolchain is selected explicitly and checked against `jdk21-pins.json`,
including modules/libjvm/release. Child JVMs receive only PATH/LANG/LC_ALL/TMPDIR.
Java injection environment variables are removed. These are JVM/CPU bounds,
not a kernel RSS reservation. All classes/downloads/logs live outside the repo.

## Reproduction

Use a fresh owned directory outside the repository and source tree, never `.m2`.
The proof directory must not exist; existing proof/cache/originals are preserved.
First run may use `--fetch` to download the pinned official artifacts; omit it
for the fully offline reproduction. Mutable upstream responses that drift from
the captured hashes fail rather than updating pins.

```bash
PYTHONDONTWRITEBYTECODE=1 python -m unittest discover -s tests -p test_nifi_jackson_candidate.py -v

PYTHONDONTWRITEBYTECODE=1 python deploy/images/nifi-patches/jackson/verify.py \
  --cache /absolute/owned/jackson-cache \
  --proof /absolute/owned/new-proof \
  --inputs /home/tears/.cache/cnc-nifi-ci-remediation-20261104 \
  --source /home/tears/.cache/cnc-nifi-ci-remediation-20261104/nested-patcher-occurrences/source \
  --jdk /usr/lib/jvm/java-21-openjdk \
  --fetch
```

## Parent handoff

1. Reproduce against the pinned helper files and input reports; review ABI
   deltas, annotated module requirements and each NAR/WAR inheritance chain.
2. Obtain wrapper-specific fixes/rebuilds for Hazelcast and Parquet; keep them
   blocked until tested. Do not use the research candidates as replacements.
3. Extend real NiFi consumer/linkage coverage for each selected pure occurrence
   and existing modules, then approve occurrence-specific replacements using
   the parent writer with complete source/candidate hashes.
4. Only the parent may integrate Dockerfile/manifest changes, build the image,
   run normal and nested scans, resolve Kibana, pass unchanged CG32 resources,
   exercise NiFi/SMB and obtain human acceptance, fresh CI and protected reviews.

This branch ends at auditable **component-prepared** status. It grants no
permission to merge PR119 or claim any runtime gate green.
