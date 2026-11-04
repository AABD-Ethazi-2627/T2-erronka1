# Stock-library mapping: independent parent verification

Child `7becad6` is incorporated locally as `c176080`. The parent repeats the
mapping and Java consumer probes separately. No archive, runtime image,
Dockerfile, scanner metadata or gate is modified or accepted by this work.

The acquisition covers **215 public library archives** under `/opt/nifi` from
the pinned, never-started stock image: the earlier 156 current/lib files plus
59 toolkit/lib files. Complete supported traversal yields **2,099 occurrences**,
inventory identity `5ef465917d5de6c50794c674f3866f22c8b604e4b7a9f7b5b8822ce773980e32`.
There are no additional selected-family copies in toolkit: **7 Guava, 3 LZ4 and
9 Snappy**. The mapping equals the child's output after substituting the owned
replacement-cache paths. Mounted extensions, non-archive blobs and the final
runtime are outside this stock-preimage coverage.

The parent runs mapping with one CPU, no core dumps and **512 MiB virtual address
space**. It completes in **94.34 s**, maximum child RSS **148,776 KiB**. The seven
Java/javac commands complete in **10.05 s**, maximum child RSS **162,816 KiB**.
Java processes have the declared heap/CPU/wall bounds; RSS is measured rather
than kernel-reserved. The parent also records the actual JDK modules, libjvm and
release, source lock, library pins and writer code, then checks unchanged hashes.

**28 tests and 14 subtests pass** on Python 3.11.17, including writer rejection
cases. The sole warning is an intentional duplicate ZIP fixture. Ruff passes.
Parent code changes only tighten acquisition-state checks, require the intended
Snappy exception message, improve provenance and address lint. No Docker
acquisition was repeated and no local image or cache cleanup was performed.

## Confirmed Hadoop incompatibility

Exact image `hadoop-common-3.5.0.jar`, SHA-256
`dad07af66b59454e71b046a2fce0c0fddb9c522eadd146075e6add82aad86ce6`,
roundtrips a normal 4,096-byte run of `A` with Snappy 1.1.10.8. With 1.1.10.9:

```text
IllegalArgumentException: not enough space for output: need 4,810 bytes, but only 0 remaining
```

The probe now accepts only that output-space precondition failure as the expected
negative result. This is normal input, not malicious native fuzzing. Hadoop's
buffer protocol requires a compatible correction; the new Snappy guard must
remain enabled. **All nine occurrences remain blocked**, including those whose
other normal consumers pass. No occurrence may be omitted to force promotion.

Actual Kafka Snappy/LZ4, Jimfs Guava and correctly sized array/direct Snappy
roundtrips pass on both library versions. These remain partial consumer checks,
not execution of NiFi processors, framework classloader dispatch or image-native
behavior. Guava and LZ4 await independent QA and further integration checks.

The committed candidate and child handoff/probe JSON retain their original child
attribution. [Separate parent proof, source changes and command hashes](NIFI_STOCK_PARENT_20261104.json)
identify this execution. The emitter remains unapproved by default; technical
review records cannot be interpreted as human academic or GitHub approval.
Final image scans, protected CI/review, Kibana, CG32 resources, NiFi/SMB and human
acceptance remain separate gates. No new scanner exception is applied.
