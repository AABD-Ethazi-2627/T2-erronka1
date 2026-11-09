# ES inventory sealed; next stage prepared

2026-11-08 local closeout supersedes the pending execution described below:
[ES_CLOSEOUT_20261108.md](../../../../docs/evidence/ES_CLOSEOUT_20261108.md).
The historical inventory and 89f58fc source remain unchanged. The new run proves
actual Maven mediation, JDK27 compilation, loader/components, and enabled
metrics/traces export with entitlements. Six SDKs alone failed runtime; the new
candidate also aligns exporters/incubator and their published JVM dependencies.

`inventory-result.json` was regenerated from the downloaded **executed 89f58fc**
source and metadata. `seal_inventory.py` checks every frozen metadata digest,
source-before hashes, image/source preservation, exit codes and exact generator
output. The earlier `preparation-01` source archive remains historical and was
not used to relabel execution.

Verified compact text archive, source and test (14 files, no JAR/model/secrets):
`/home/tears/.cache/cnc-benten-vm-20261105/es-otel-qualification-20261106/inventory-01-verified/`.
Archive SHA256: `9187e9927179c9c5ec7c5e8530a7f0c1bf3b086aad6e087f460c39fdef6320f1`.

The 2.465-second metadata phase exited 0; parser exited 0. It measured JDK **27**,
APM 27 JARs/23,292,347 bytes, ESQL GCS 31/13,922,264 and repository GCS
35/15,263,160: 93 direct JARs/52,477,771 bytes. All three API trios match existing
official 1.67 SHA256 pins. The actual loader class hash is
`e5dc023a6a83979e2fd4a2332fa973413ae02639e53a3fa42e556a36104a1e2b`.
The measured extension closure contains **11** realms, retained explicitly in
`inventory-result.json`, including `workload-identity`'s separate SPI directory.

## Next finite coordinator slot: input stage only

`python -B .../next_phase.py` prints the exact prepared container command. Its
source path is deliberately **next-source**, keeping the executed 89f58fc tree
unchanged. The coordinator must freeze current owned files there, create a fresh
writable `stage-01` directory, use a unique container name, and run the emitted
stage command once under the common nonblocking lock with 175-second container
wall timeout and the normal 6 GiB/20 GiB gate. No automatic lock retries.

The command uses the exact ES image, 1 CPU, 512 MiB RAM and no extra swap, heap
256 MiB, metaspace 96 MiB, direct memory 32 MiB, no cores/network/caps, user 1000,
readonly source image and tool snapshot. Its sole writable bind is the fresh
private proof directory. `StageInputs.java` copies only boot `lib/*.jar` and
measured realm root/SPI JARs/descriptors/policies into `/proof/input`, hashes each
original before/after copying and enforces 3,000 files/2 GiB total/512 MiB per
file. It does not copy config, logs, data, JDK or native module distributions.
It invokes no loader, service, plugin, exporter or external endpoint.

Capture stdout as `copy.tsv`. Under the same reserved resource controls, call
`stage_manifest.verify(inventory, copy_text, tree)` and seal its JSON result.
It rehashes copied bytes, requires every selected 93 JAR/hash/size to equal the
measured inventory, checks policies/descriptors, requires all 11 realms, and
checks the actual installed ES loader JAR. On any mismatch retain the attempt
and stop. Recheck image/source identity, remove only the owned unique container,
and preserve command/exit/time evidence. No prepared input copy is runtime approval.

## Later phases prepared; separate evidence still required

1. `static_stage.py` scans one realm per finite VM phase, with 400 MiB Python
   address-space/165 CPU-second bounds plus the caller's 512 MiB cgroup and
   175-second wall bound. It keeps server-parent priority and SPI/root extension
   boundaries, selects MR classes for actual JDK27, and rejects ambiguous OTel
   provider shadowing instead of flattening it. SDK six is the only APM
   experiment; the unchanged exporters/alpha/instrumentation and visible parent
   consumers remain in the scan. The two GCS realms keep their own providers.
   It reports public/internal consumer counts, unresolved and newly broken
   modeled references, origins, and a nonvacuous missing-API mutation. The narrow
   symbolic model still cannot prove full JVM ABI/access or reflection behavior.
2. `published-roots.json` plus 27 exact official raw POMs cover all 21 installed
   OTel-family APM root artifacts and exactly six SDK alternatives. Structured
   exclusions and raw bytes are retained. `published_metadata.py` verifies those
   declarations; it does **not** perform mediation. Old exporters request 1.62
   SDK, API-incubator requests API1.60.1, and disk-buffering requests SDK1.62.
   These constraints must be preserved in a fresh real-Maven oracle with exact
   installed vendor direct overrides and any Gradle JVM-variant decisions
   recorded explicitly. New transitive inputs must be pinned, compared with
   installed variants and justified before selection. SDK-only eligibility is
   undecided. The 1.67 sender/OkHttp5.5 expansion remains unselected.
3. `EsLoaderProbe.java` and emitted `loader-current`/`loader-sdk-six` commands
   prepare actual installed `PluginsLoader` use, normal ES jar-hell checks,
   server exports, measured extension/SPI boundaries and named APM module layer.
   Source compiles against the installed ES boot module path. The candidate
   command overrides **only APM** with a private six-SDK tree. It verifies nine
   core JAR origins/hashes and loads actual plugin/exporter classes without
   initialization; its benign actual SDK configuration call records a precise
   ConfigUtil failure only if observed in the current control. A passing current
   control is also preserved. It does not invoke plugin constructors, start ES,
   attach the agent or transmit exporter data. Compilation/boot-layer failures
   remain harness evidence and must be fixed without broadening module exports.

Actual consumer initialization, SDK trace/context/metrics/log behavior, exporter
builder/SPI traversal, agent nested/shaded consumer behavior, live entitlement
operation and APM functionality remain **pending**. The loader source does not
enable entitlement instrumentation and cannot qualify it. Existing named-module
identities and entitlement policy hashes must stay unchanged in the private
candidate; matching names alone does not establish operation. No build/scan,
CG32 or human acceptance is implied. `replacement:null` and
`runtime_approved:false` remain enforced throughout.
