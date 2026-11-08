# AWS Glue Wire 6 migration, source-built consumer

The actual stock NiFi 2.12.0 Wire 5.2 carrier is **nifi-aws-nar**, through
`schema-registry-serde-1.1.24.jar`. Seven external AWS classes reference Wire.
NiFi's separate Protobuf NAR already contains runtime/schema 6.4.7. Do not mix
the old AWS schema/compiler with a new reader or remove AWS to hide the finding.

`prepare.py` takes the exact official AWS Glue v1.1.24 source archive, pinned by
commit and SHA256, and creates a fresh external source tree. It changes one
consumer Java file to the exact bytes published by AWS in 2.0.1: the new
`ProtoFileElement` constructor has an extra empty list argument. The entire
resulting Java file is independently hash-checked. No reader source is forked.
Wire becomes the official coherent 6.4.7 family; Kotlin becomes 2.4.20, matching
the current NiFi shared parent. The consumer's new version is
`1.1.24-cnc-wire6.1`. POM parent references are changed consistently. Every other
source file, including every original upstream test, remains unchanged and is
inventoried. This is a local consumer rebuild, not an upstream 1.1.24 release.

The source correction was required by a real compiler failure, not a hypothetical
ABI concern. Original AWS 1.1.24 source with Wire6 failed at the constructor;
the migrated source completed `mvn verify` on 2026-11-08: **1,445 tests, zero
failures/errors/skips**, zero Checkstyle violations, coverage checks met.
38 Surefire XML reports independently reproduce the total. Source/Javadoc
plugins also executed; their inherited warnings remain in the complete log.
No tests, coverage thresholds or scanner checks were disabled.

## Reproduction

Download the `SOURCE_URL` in `prepare.py` to a new private cache. Its exact
SHA256 must match `SOURCE_SHA256` before extraction. Then run Python3.12:

```text
python deploy/images/nifi-patches/wire6/prepare.py --source-archive /private/aws-original.tar.gz --output /private/new-source
```

The executed Linux builder is the official Maven3.9.11/Temurin17 image pinned to
`maven:3.9.11-eclipse-temurin-17@sha256:e4a7ace3dc0d645ed97f8d9ad0b0d3f0b14fa8d150138f27f116d7105a639b82`.
Use an owned container, one CPU/1.5 GiB, no swap expansion, and
`MAVEN_OPTS=-Xmx512m -XX:ActiveProcessorCount=1 -XX:MaxMetaspaceSize=192m`.
Copy the prepared tree into its private writable filesystem, set cwd to that
tree, and run:

```text
mvn -B -ntp -Dmaven.repo.local=/private/m2 -pl serializer-deserializer -am verify
```

Keep the exit status, complete log, source provenance, Surefire XML, JaCoCo and
Checkstyle reports, resolved Maven repository and generated artifacts. This
build needs network access to official Maven repositories, but no AWS/Kafka
credentials or external service contact. It does not run the separate upstream
`integration-tests` module. Repository-installed dependencies are not reused.

JDK17 is deliberate: the original source's Lombok1.18.26 and JaCoCo0.8.8 are
compatible with that toolchain. The JDK21 Windows attempts failed first on
Lombok and then on Windows protoc command length; their logs are preserved.
Neither failed attempt is counted as qualification.

## Real old/fixed reader controls

`readers.py` checks three original NAR hashes against the existing stock source
lock before extracting the runtime5.2/6.4.7 readers and actual inherited
Kotlin2.4.20/Okio3.18.2 dependencies. It compiles `WireReaderProbe.java`, then
runs both versions in bounded JVMs. Normal scalar input must pass; both
published advisory payloads must produce checked IO rejection on the fixed
stream and byte-array readers. The actual old image must fail at least one
negative control. Each run records input, class, tool, JVM-module and log hashes.

```text
python deploy/images/nifi-patches/wire6/readers.py --libraries /private/stock-lib --java-home /absolute/jdk21 --output /private/new-reader-proof
```

The first run passed all six fixed checks. Original Wire5.2 failed three controls
(including two array-bound exceptions), while valid inputs passed. This is
executed standalone JVM component evidence, not NiFi NAR loader, scheduling,
processor or full-image acceptance. Host JDK21 differs from the stock server's
Java21 patch level; both are identified separately in the closeout evidence.

## Assembly boundary

The rebuilt Serde JAR is **not yet installed into the serving image**. A proper
assembly must upgrade the entire AWS Wire family plus its required actual
closure, not just runtime/schema. Wire6.4.7 declares newer JavaPoet0.12.0,
KotlinPoet2.2.0, SwiftPoet1.6.11, kotlinx-serialization1.10.0 and Kaml0.104.0;
the AWS NAR has older copies. Existing parent Okio3.18.2/Kotlin2.4.20 must be
included in the real NAR loader comparison. The successful isolated Maven
closure cannot silently replace the mediated NiFi closure. Keep all NARs and
all required capabilities; run actual consumer/NiFi controls and both image
scans after assembly. No caller-written approval or relabelling of Wire5.2
can substitute for that evidence. `runtime_approved:false` remains mandatory.

See [closeout record](../../../../docs/evidence/NIFI_CLOSEOUT_20261108.md) for
daemon/image identities, failed attempts, cache locations and current build state.
