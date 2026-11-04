# RabbitMQ transport follow-up — conditional component candidate

The parent independently repeats all seven configurations after the strict
resolver corrections and confirms the copied image AMQP NAR equals this official
reference. See [parent evidence and remaining gates](../../../../docs/evidence/NIFI_OCCURRENCES_REVIEW_FIXES_20261104.md).
The child proof and its source hashes below remain historical, not relabelled.

This supplement resolves the **component-level** Netty dependency/transport blocker
recorded in the original `98eb0dc` evidence. It does not replace the original proof
or edit `candidate-plan.json`. Use the new `rabbit-candidate-plan.json` and reproduce
`verify_rabbit.py` when considering RabbitMQ. No archive is modified, no image is
built/scanned, and no NiFi or broker is started. No exception or gate change is added.

## Concrete findings

- The pinned 5.37.0 POM's complete non-test/non-provided/non-optional transitive
  closure is **13 coordinates**: RabbitMQ, SLF4J 1.7.36 and **11 Netty 4.2.18.Final
  modules**. `rabbit-closure-lock.json` lists every coordinate; `rabbit-pins.json`
  records official Maven URLs and full SHA-256 pins for every JAR, POM, ancestor,
  imported BOM and source artifact used in this supplement. Neither Maven nor
  Maven plugins execute. POM resolution alone is not treated as runtime proof.
- Required Netty modules are buffer, common, resolver, transport,
  transport-native-unix-common, handler, codec, codec-base, codec-compression,
  codec-marshalling and codec-protobuf. The `netty-codec` JAR is a metadata-only
  aggregate: its empty class surface is recorded explicitly. The shared bounded
  comparator now handles this case (`class major = null`); original library
  regressions were rerun after that one-line extension.
- The resolver reads inherited dependency-management **scope and optionality**,
  not just versions. Netty's managed Mockito/Reflections/Gson entries are tests.
  Root `netty-codec` exclusions remove protobuf dependencies along those transitive
  paths; managed optional marshalling and compression/TLS provider dependencies
  are recorded as excluded. Imported Bouncy Castle 1.84 and JUnit 5.14.4 BOM POMs
  and all their ancestors are pinned; they do not imply those optional/test JARs
  are required at runtime. Unsupported dependencies, profiles that add dependencies
  or alter required selectors, unknown inputs, unresolved versions, required
  classifiers, version conflicts and checksum mismatches fail closed. No nearest
  version selection, snapshot/range resolution or repository fallback occurs.
- Official Maven `nifi-amqp-nar:2.12.0` SHA-256 is
  `4d43e10bcd08776abb1990dab8b7563559acfd5b44f10be63dd6366ec2469ca8`.
  Its `amqp-client-5.35.0.jar` hash is exactly the report's input object
  `c23f1dffc08e2c209035f8d22a48edfd83477b629477e9416a5d25e2c116f3f6`.
  Its local dependencies include all **11 Netty 4.2.17.Final modules**, not 4.2.18.
  The bundled processor JAR also matches its separately pinned official artifact.
  This is correspondence for these component bytes; it is **not a comparison to
  the Docker NAR occurrence**, nor proof the whole NAR matches the image.
- The official AMQP NAR names `nifi-standard-services-api-nar:2.12.0` as its parent.
  That pinned parent has no further NAR parent and contains neither Netty nor SLF4J.
  Both NAR inventories, all nested object hashes and native-resource paths are
  recorded in each proof. No service/application-level library removals are proposed.
- `AbstractAMQPProcessor.createConnection` bytecode constructs `ConnectionFactory`,
  configures credentials, message size, virtual host and optional JDK SSLContext,
  disables automatic recovery, and calls the executor or executor/address-array
  `newConnection` overload. It does **not** select Netty or JDK NIO. Source inspection
  of all Java files in the pinned processor source JAR corroborates this. The
  tested overloads match those consumer call shapes; the NiFi processor itself
  was not instantiated or scheduled.
- RabbitMQ's pinned source initializes `netty=false` and lazily constructs its
  Netty configuration. Runtime controls demonstrate that the default transport
  can open a connection, create a channel and publish with **no Netty JARs**.
  Explicitly activating Netty on that same small classpath fails with the expected
  missing `io/netty/...` class. A declared dependency does not establish eager loading.

## Runtime proof

The probes use a fixed-size, ephemeral IPv4-loopback AMQP fixture. It performs
only the scripted Start/Tune/Open handshake, one channel, one small publish and
orderly channel/connection close; this fixture is **not a broker**. An invalid
protocol-version fixture tests rejection through the real client. Every accept,
socket read, handshake, channel RPC and process has a deadline. Received fixture
credentials are neither retained nor logged. All executors/groups/sockets close.

Seven separate Java classpath configurations pass:

1. RabbitMQ **5.35.0**, SLF4J 1.7.36, **no Netty** (old normal-transport control).
2. RabbitMQ **5.37.0**, SLF4J 1.7.36, **no Netty**.
3. RabbitMQ **5.37.0**, NiFi-managed SLF4J **2.0.19**, **no Netty**.
4. RabbitMQ 5.37.0 + complete declared Netty **4.2.18.Final**, SLF4J 1.7.36.
5. RabbitMQ 5.37.0 + all 11 **4.2.17.Final** JARs extracted unchanged from the
   pinned official reference NAR, SLF4J 1.7.36.
6. The complete 4.2.18 configuration with SLF4J **2.0.19**.
7. The reference 4.2.17 configuration with SLF4J **2.0.19**.

The no-Netty groups exercise default blocking and JDK NIO connections, both NiFi
executor overload shapes, channel/publish/close, malformed-peer rejection, JDK TLS
factory initialization and the absent-Netty activation control. Netty groups
exercise the real `NettyFrameHandlerFactory` and `NioSocketChannel` over loopback,
valid connection/channel/publish/close and malformed-peer rejection. They also
exercise real Netty `EmbeddedChannel` with fragmented and over-limit input and
initialize a JDK-backed Netty TLS engine. The embedded decoder control alone is
not claimed to reproduce RabbitMQ's private pipeline; the loopback tests cover
that real pipeline separately. A one-thread event loop is explicitly supplied.

SLF4J 2.0.19 is declared by the pinned NiFi root POM, not inferred from a machine
installation. These tests use API-only SLF4J with its documented no-provider/NOP
fallback. They do **not** validate NiFi's real logging provider, bridge ordering or
parent-loader resolution. Metrics, tracing, automatic recovery, authentication
variants, TLS certificate handshakes and broker redelivery semantics remain untested.
The original parser/CVE probes continue to be separate evidence.

The bounded public/protected declared surface comparison flags **zero changes**
for RabbitMQ 5.35 -> 5.37 and for every Netty 4.2.17 -> 4.2.18 module. It is not a
full JVM/consumer linkage proof; reflection, inherited resolution, package-private
uses and multi-release dispatch remain outside that comparator. Detailed output
and consumer bytecode are saved, not replaced with a version-label assertion.

## Platform and resource constraints

Execution uses the unchanged pinned OpenJDK **21.0.13+9**, Linux **x86_64**.
All child processes use the original 256 MiB heap/one-CPU/metaspace/direct-memory
bounds, core dumps disabled and bounded wall/CPU deadlines. Netty arena counts
are limited to one. RSS is measured against the same 512 MiB limit. No native
malicious input or intentional OOM probe executes.

The 13 required JARs contain no packaged native shared libraries. The Unix-common
module provides Java APIs; it is not an epoll/kqueue/io_uring native implementation.
These tests select Netty's JDK NIO transport and JDK TLS, without tcnative/OpenSSL,
Conscrypt, Bouncy Castle providers or native compression engines. Optional backends
need their own compatible closure and tests if a consumer enables them.

RabbitMQ base bytecode is Java 8. Netty base bytecode is predominantly Java 8;
`netty-common` also includes Java 11 JCTools VarHandle classes. Its pinned
`PlatformDependent.hasJctoolsVarHandle()` source gates that path on Java >=11.
Multi-release module descriptors are enumerated in `platform-constraints.json`.
Do not infer an all-JDK compatibility guarantee from a maximum class-major number:
only the pinned JDK 21/platform was executed. NiFi's reference NAR declares Java 21.

## Reproduce and inspect

```bash
candidate=deploy/images/nifi-patches/compatible-libraries
cache=/home/tears/.cache/cnc-nifi-ci-remediation-20261104/rabbit-transport-3e7e9435
PYTHONDONTWRITEBYTECODE=1 python "$candidate/verify_rabbit.py" \
  --cache "$cache" --offline
RABBIT_CACHE="$cache" PYTHONDONTWRITEBYTECODE=1 \
  python "$candidate/test_rabbit.py"
```

Omit `--offline` with a **new owned cache** to fetch all pinned official inputs.
A fresh full-download run and a separate offline run passed. Existing JDK pins
are never refreshed. `rabbit-tool-pins.json` adds the `javap` executable pin.
`rabbit-transport-summary.json` records proof paths, test states and source hashes.
Each run creates a separate proof directory and rejects source changes during
verification; original proofs remain unchanged. Thirteen focused model/integrity
regressions pass, as do the original four negative checks and original library
component suite. No JAR binaries or extracted NAR objects are committed.

The successful proof contains `effective-required-closure.json` (all graph edges,
exclusions, inherited scopes and inspected profiles), `official-nar-inventory.json`,
`nifi-consumer-bytecode.log`, seven transport logs, `bounded-abi.json`,
`platform-constraints.json`, `resource-usage.json` and `rabbit-transport-result.json`.
An unsuccessful run does not produce a new successful result or candidate plan.

## What the parent can conditionally integrate

RabbitMQ replacement remains the unchanged upstream **5.37.0** JAR at
`https://repo.maven.apache.org/maven2/com/rabbitmq/amqp-client/5.37.0/amqp-client-5.37.0.jar`,
SHA-256 `b27134820890c5e56ed57d27cc50b70742fa2c31b36a6e9e28e14a43f34ff96f`.
The tests support compatibility both with its declared Netty patch branch and
with the reference NAR's existing Netty patch branch for the exercised paths.
They do **not** mandate replacing Netty merely to satisfy a POM version label.
Any actual Netty change would require its own final-image scan and consumer scope.

Still irreducible here: mapping and hashing **every actual image NAR/JAR
occurrence**, actual classloader visibility/shadowing (including parent logging
provider), all enabled optional paths, real NiFi processor scheduling/flows,
broker behavior and final strict image/nested scans. The separate engine mapping
must compare actual objects before the parent applies its hash-guarded patcher.
The new status is `transport-component-tested-nar-mapping-pending`, never
"patched", "gate green" or "NiFi accepted". Blocked Guava objects are untouched.
