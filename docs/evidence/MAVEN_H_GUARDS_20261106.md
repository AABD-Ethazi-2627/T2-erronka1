# Maven inheritance and plain-JAR selector guards, 2026-11-06

Status: focused tool correction, tested against a real offline Maven 3.9.11
consumer oracle. No dependency version, candidate overlay, serving image,
security exception or runtime approval changes.

The fixed parser rejects child interpolation that changes an inherited
dependency's group/artifact key. It also rejects uncertain plain-JAR management
keys before discarding a dependency as test/provided. Classified native test-only
artifacts retain their separate key and remain excluded from the runtime closure.
The Jackson support lock changes together with the parser.

| Valid fixture | Baseline Python versus real Maven | Fixed parser |
| --- | --- | --- |
| H1: child changes inherited dependency property | Omits `x:other:1` | Explicit rejection |
| H1b: reverse property change | Adds `x:leaf:1` | Explicit rejection |
| H1c: child changes `${project.artifactId}` | Omits `x:root-api:1` | Explicit rejection |
| H2: interpolated type followed by literal test management | Omits `x:leaf:1` | Explicit rejection |
| H2b: reverse management order | Equal (control) | Conservative explicit rejection |

The first three fixtures explicitly declare the parent as `packaging=pom`.
The original review omitted that declaration; those exact initial runs are
preserved separately and are not the authoritative Maven comparison. The review
had inferred Maven's result. The valid-parent experiment confirms the divergences
above rather than claiming a broader model of Maven semantics.

The initial correction rejected RabbitMQ's classified native test dependency
`software.amazon.cryptools:AmazonCorrettoCryptoProvider` in Netty management.
That failed attempt is retained. The final guard distinguishes its nonempty
classifier from the plain-JAR ambiguity; a portable regression protects it.

Final parser SHA-256:
`fbeaeb8564c8da3587eab82ab95f80fbb8d8ef0703a3ae86f22e4d29267f9dc9`.
The real oracle matches all eight frozen Jackson closures and all 13 RabbitMQ
5.37.0 runtime coordinates before and after the correction. Python 3.11.17 and
3.12.14 each pass 36 guard tests and 27 subtests. The final paired phase completes
in 9.187 seconds with the common VM lock, one CPU, offline namespace and bounded
Java heap. This is focused verification; the full-suite result still belongs to
`12ca2fa`, before this correction.

Evidence: `/opt/cnc-guard/evidence/maven-H-final-20261106/verified-report.json`
on the Benten guest; the compact export and its hashes are retained under
`/home/tears/.cache/cnc-benten-vm-20261105/maven-H-final-20261106/`.
The source clone at `12ca2fa` is unchanged; the fixed parser was tested from an
explicit hash-bound scratch copy. This remains a bounded resolver, with no
claim that every unsupported Maven model is detected. New pins/families still
need their own closure and consumer evidence.
