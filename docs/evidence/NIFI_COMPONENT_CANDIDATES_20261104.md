# NiFi compatible-library candidates: independent parent verification

This records the original `107edda` execution. The [review corrections and
complete inventory](NIFI_OCCURRENCES_REVIEW_FIXES_20261104.md) supersede its
pending-inventory status and verifier output. Historical commands reproduce the
old result only with the historical source; current source adds stricter guards.

The parent integrated child commit `98eb0dc4593c12e7c9837804f78efb4da6c1d967`
as `107edda`, preserving the eight candidate files byte for byte. The child's
[README](../../deploy/images/nifi-patches/compatible-libraries/README.md) describes
its preparation scope; the parent verification below is a separate execution.

No runtime archive, Dockerfile or scanner policy is changed by this candidate.
All original NAR occurrence paths remain unmapped, and no NiFi processor or
final patched image has been tested. The source files prepare verified upstream
bytes and component probes; they do not establish a green NiFi gate.

## Current CI failure

The parent downloaded the artifacts from run **41810126327**, NiFi job
**126507014432**, source `2da877c`. Its image build, Trivy installation and normal
scan succeeded; the nested audit failed. The nested tuple set is exactly equal
to the previous 59-tuple audit: no added or removed vulnerability/package/version
tuple. This remains relevant at `f80c37f`, whose changes only affected Kibana.

| Artifact | SHA-256 | Findings |
| --- | --- | --- |
| image-scan.json | `602ee0ca740c3cd2ca3a9ad2f8b06c74145edd944edafa01f3502eb36d427137` | 0 reported |
| nested-archive-scan.json | `d06b864d28cd7c3c027bd66098934b3a65ffd482cf346ac235b952e54bfd7c18` | 59 distinct tuples |

The nested audit must remain blocking. The absence of normal-image findings
does not establish coverage of dependencies hidden inside NARs.

## Parent reproduction

Only the inputs listed in `pins.json` were copied to a fresh directory:
`/home/tears/.cache/cnc-nifi-ci-remediation-20261104/parent-compatible-libraries/`.
The original child proof and inputs are preserved. With the integrated source:

```bash
.venv/bin/python deploy/images/nifi-patches/compatible-libraries/verify.py \
  --cache /home/tears/.cache/cnc-nifi-ci-remediation-20261104/parent-compatible-libraries \
  --reports /home/tears/.cache/cnc-nifi-ci-remediation-20261104/artifact-2da877c \
  --objects /home/tears/.cache/cnc-nifi-ci-remediation-20261104/vulnerable-objects.json \
  --offline
```

Result: **component probes pass**, with `patched=false`. The resulting plan
equals the child's six-object conditional plan. Four negative integrity tests
also pass, including execution with Python optimization enabled. The parent
measures maximum child RSS **105,856 KiB** and verifier RSS **37,952 KiB**;
this is an observed and checked peak, not a kernel memory reservation.
The proof directory is
`parent-compatible-libraries/proof-1793791569206013412/` under the cache root.
The adjacent JSON binds the source and artifacts by hash.

## Disposition

| Instance | Result | Remaining condition |
| --- | --- | --- |
| Guava 33.7.1 → 33.7.2-jre | Normal/malformed serialization and bounded API comparison pass | Map every exact occurrence and verify its NiFi dependency/classloader closure |
| LZ4 1.11.2 → 1.11.4 | Java/JNI and selected malformed-input controls pass | Occurrence mapping and NiFi runtime/image tests |
| Snappy 1.1.10.8 → 1.1.10.9 | JNI/stream and selected bounds controls pass | Occurrence mapping and NiFi runtime/image tests |
| Guava 33.4.8 and 33.6 | **Blocked** | Scan object bytes differ from official JARs; inspect repacking/shading and actual consumers |
| RabbitMQ 5.35 → 5.37.0 | Parsers pass; **replacement blocked** | Pin, inspect and test Netty 4.2.18.Final closure and NiFi consumers |

RabbitMQ 5.36.1, suggested in the scanner repair boundary, was not a published
Maven artifact at the checked URL. The official advisories require the published
5.37.0 to cover both tested fixes. This is why the tested candidate differs from
the earlier scan-derived proposal; neither 5.36.0 nor an absent 5.36.1 is promoted.

Whole upstream JARs retain Maven metadata, services, signatures and native
resources. A matching package label inside a different fat/shaded object is
insufficient to authorize whole-object replacement. The component comparator
does not prove inherited-member resolution, reflection, all platforms, full
dependency linkage or NiFi processor compatibility.

The existing exposure helper deduplicates archive traversal by hash. Its scan
inventory is useful for finding detection, but cannot by itself prove **every
original occurrence** when equal enclosing archives recur in different paths.
The application plan needs a complete occurrence map, explicit preimage hashes
and a separately tested archive writer before any runtime wiring.

Wire, Jackson and OpenTelemetry are outside this candidate. Independent code
review, complete occurrence/classloader validation, actual nested-image scans,
NiFi acceptance, fresh CI and GitHub approval remain pending. No new exception,
metadata relabeling or security-gate change is authorized or performed.
