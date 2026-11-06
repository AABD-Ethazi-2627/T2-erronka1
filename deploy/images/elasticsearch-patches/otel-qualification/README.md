# Elasticsearch OTel compatibility preparation

Owned scope is this new directory and `tests/test_es_otel_qualification.py`.
This preparation does not alter the Dockerfile, installed image, defaults,
source manifest, security policy, Maven resolver or serving containers.
`replacement: null` and `runtime_approved: false` are mandatory.

## Current observations

On 2026-11-06, a default-user, read-only listing of
`cg32-23669129-elasticsearch-1` was preceded by inspection confirming image
`sha256:2005cca9747e88288e27d18a2f7352486ab0e2a09acd46ee229e9d2bb889ccb4`
and Compose project `cg32-23669129`. No environment/configuration secrets were read.
The listing and plugin descriptors, rather than the aggregated scan, establish:

| Directory | Loader boundary from actual descriptor | Observed OTel families |
| --- | --- | --- |
| `apm` | Named module `org.elasticsearch.telemetry.apm`; no extended plugins declared | API/context/common 1.67; SDK six and four exporters 1.62; API incubator 1.60.1-alpha; disk-buffering 1.57.0-alpha; instrumentation 2.26.1 and associated alpha packages; semconv 1.40.0; Elastic agent 1.57.1 |
| `repository-gcs` | Non-modular isolated plugin; no extended plugins declared | API/context/common 1.67; Google/OpenCensus consumers; no SDK JAR in direct listing |
| `esql-datasource-gcs` | Non-modular plugin extending `x-pack-esql` and `workload-identity` | API/context/common 1.67; Google/OpenCensus consumers; no SDK JAR in direct listing |

The APM entitlement policy names SDK common/trace/metrics/logs, the OkHttp sender,
OkHttp, Okio, disk-buffering and runtime telemetry. The GCS policies use
`ALL-UNNAMED`. Matching automatic/explicit module names is therefore a
compatibility requirement. No entitlement or module-name rewrite is proposed.
The other two extension realms and server parent remain explicit unqualified
boundaries until their actual installed graph and classes are measured.

The serving ES image has started successfully. APM/exporter functions have not
been exercised by this work. The GCP missing-ConfigUtil failure is **not** an
observed Elasticsearch runtime failure.

Official `v9.5.5` loader source uses `ModuleFinder`, `resolveAndBind`, and one
loader per named plugin layer. Non-modular plugins receive a URL loader with
server and extended-plugin parents. `official-sources.json` pins the sources
inspected; it does not claim equivalence with installed bytecode. The inventory
phase also hashes actual `PluginsLoader.class` and its containing JAR.

## Minimum experiment is still undecided

`reusable-official-pins.json` retains previously fetched official 1.67 bytes as
inputs only. None of the GCP eligibility claims transfers to ES. The first
possible model experiment moves only the **six actually installed old SDK
artifacts** in APM to 1.67. The existing API trio is already 1.67. Exporters,
alpha/incubator packages, instrumentation, agent, OkHttp and all GCS files remain
measured consumers. This six-change experiment is not a selected remediation.

`exporter-pom-observation.json` records newly inspected official Maven metadata
and published digests. Exporter-sender-okhttp 1.67 requests **okhttp-jvm 5.5.0**,
whereas the actual APM listing contains **5.3.2**. Upgrading all exporters by
analogy therefore changes a separate published dependency constraint. This work
has not fetched their JAR bytes, approved an OkHttp upgrade or proved that the
six-change experiment preserves exporter/alpha linkage.

Before any experiment becomes eligible, freeze all exact installed consumer
artifacts and derive its runtime closure with a fresh real Maven 3.9.11 oracle.
Preserve literal POM requirements, vendor direct overrides, exclusions and
mediation decisions separately; do not call incompatible version requests
satisfied merely because a custom subset parser returns a set. Existing Maven
H1/H2 tests for Jackson/RabbitMQ are not an OTel closure proof. Keep the original
family and any nonconforming closure as named controls; no exceptions or fake
versions. Any newly required artifact outside the installed observed families
returns to the coordinator before selection.

## Prepared tools and exact next phase

`ModuleAudit.java` runs against the image's bundled JDK without Elasticsearch,
agent attachment, module initialization, exporters or network. It emits per-JAR
hashes, actual JPMS names/requires/exports/services, manifest identities, physical
class/nested-JAR counts, descriptors, entitlement hashes and extension boundaries.
It preserves realms, rejects duplicate ZIP entries and allows no silent
ModuleFinder name collision in the parser. Nested/shaded agent classes are
inventory only. It never treats an agent nested class as an APM provider.

`run_reserved.py` defaults to a JSON dry-run. Once the coordinator grants this
specific phase, freeze this source and invoke the following **on the VM**:

```sh
python3 -B /opt/cnc-guard/evidence/es-otel-qualification-20261106/source/deploy/images/elasticsearch-patches/otel-qualification/run_reserved.py --execute-reserved --attempt inventory-01
```

It takes the common lock nonblocking exactly once (busy => exit 75, no retries),
requires 6 GiB available RAM and 20 GiB free disk, verifies immutable image ID,
and runs one unique disposable container. Limits are 1 CPU, 512 MiB cgroup RAM
and no extra swap, heap 256 MiB, metaspace 96 MiB, direct memory 32 MiB,
64 PIDs, no cores, network none, readonly image and source, user 1000, no caps,
and a 175-second Java phase timeout. It preserves proof under
`/opt/cnc-guard/evidence/es-otel-qualification-20261106/inventory-01`, verifies
source/image identity again, and removes only its own unique container. It does
not exec into or modify the serving container. Preflight and parse/cleanup have
separate short command deadlines; 175 seconds describes the bounded container
phase, not an unconditional wall-time promise for a hung Docker daemon.

`qualify.py inventory` validates that output; `qualify.py static` is prepared
for a later frozen extracted tree and verified cache, neither produced by the
metadata phase. Its SDK experiment refuses unobserved artifacts. The reused
narrow class-file model in `symbolic.py` selects MR classes for the **actual JDK
feature** from inventory, rather than assuming Java 21. Direct ordinary class,
field and method references and inherited lookup are a partial symbolic model.
Public/internal consumer counts, unresolved references and nonvacuous missing-API
controls stay visible. JVM access/default methods/method-handle invocation,
reflection, resources/services, nested agent archives and extended parent
consumers require independent checks. Zero newly broken modeled references
cannot establish JVM or APM approval.

## Outstanding evidence

1. Execute the metadata phase under a coordinator-granted slot; seal exact paths,
   hashes, graph and real JPMS identities. Preserve original image/source hashes.
2. Stage a private exact extracted tree **on the VM**, including server/extension
   boundaries as needed; do not copy large JARs to the laptop. Run current and
   candidate public/internal linkage, access and mutation controls.
3. Establish each experiment's published/mediated closure using real Maven and
   exact official inputs. Candidate exporters/alpha changes need their own proof.
4. Use installed ES loader implementation and matching parent layers for separate
   current/candidate consumer initialization, SDK configuration, instrumentation,
   exporter-builder/SPI and benign trace/context/metrics/log probes. Do not attach
   the agent or send traffic. Named-module access and entitlement identities must
   match. Plain flat-classpath exercises do not qualify the ES loader.
5. Re-read originals/source/image identities and container ownership, then obtain
   independent review before selection. Image build/scan, functional APM,
   integration/CG32 and human acceptance remain separate future evidence.

Portable verification: `python -B -m unittest discover -s tests -p test_es_otel_qualification.py -v`.
Fixtures test guard behavior only; they are not live inventory or runtime proof.
