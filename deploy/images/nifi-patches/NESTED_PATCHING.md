# Offline occurrence inventory and exact copy patching

Parent follow-up: the [complete inventory and narrow ZIP metadata
correction](../../../docs/evidence/NIFI_OCCURRENCES_REVIEW_FIXES_20261104.md)
supersede the partial diagnostic below. All 156 copied lib files now traverse
successfully (2,040 occurrences); no archive has been patched.

`scripts/patch_nested_jars.py` uses only the Python standard library. It does not
resolve dependencies, approve candidates, modify the distribution, relabel
versions, strip signatures, build images or contact services. `candidate-plan.json`
is **not** an executable application plan: null original paths remain unmapped.
The parent owns runtime assembly, standalone Jackson, manifests and acceptance.

## Interface and review boundary

```sh
python scripts/patch_nested_jars.py /owned/source > inventory.json
python scripts/patch_nested_jars.py /owned/source --plan mapped.json --output /owned/fresh-output
# Same preflight, then explicit publication:
python scripts/patch_nested_jars.py /owned/source --plan mapped.json --output /owned/fresh-output --apply
```

Only the final command publishes files. Output must not exist (even an empty
directory is refused). Its existing parent must be owned by the caller. Output is
an **overlay of changed outer archives**, retaining their source-relative names;
it is not a distribution or final image. Inventory-only stdout should be captured
to a new evidence file; nonzero exit invalidates that file. No successful partial
inventory is returned. Use private immutable source/replacement/cache trees;
concurrent hostile filesystem mutation is outside this offline tool's threat model.

Every loose or nested `.jar`, `.nar`, `.war` and `.zip` is traversed independently,
including byte-identical archives at different prefixes. The ordered inventory
binds the outer path/hash, exact member list and every archive hash along that
ancestry. Manifest fields include NAR identity/dependency attributes; embedded
Maven properties and class package paths expose observable fat/shaded content.
These are observations, not an exhaustive package detector or compatibility
proof: absent metadata does not establish a standalone library. Arbitrarily named
archive blobs without those extensions are not recursively interpreted.

An executable plan has exactly these keys (values below are schematic):

```json
{
  "schema": 1,
  "inventory_sha256": "SHA256_OF_CANONICAL_COMPLETE_INVENTORY_ROWS",
  "targets": [{
    "outer": "extension.nar",
    "members": ["META-INF/bundled-dependencies/library.jar"],
    "chain_sha256": ["OUTER_PREIMAGE_SHA256", "LEAF_PREIMAGE_SHA256"],
    "replacement": "/owned/official-stock-library.jar",
    "replacement_sha256": "EXACT_REPLACEMENT_SHA256",
    "status": "approved-exact-occurrence",
    "expected_occurrences": 1
  }]
}
```

Generate `inventory_sha256` with the module's `inventory_hash(rows)` (sorted JSON
keys, compact separators, UTF-8), not the pretty-printed CLI document's file hash.
A loose JAR has empty `members` and a one-element hash chain. Repeat a target row
for **every occurrence** of a selected leaf hash; `expected_occurrences` is its
source-wide count, repeated identically in those rows. Paths are case sensitive.
Unknown/missing fields, statuses, duplicate JSON keys, missing/extra occurrences,
duplicate/overlapping selections, drift and count mismatches fail closed.
Blocked identities are checked throughout each selected ancestry and throughout
the replacement inventory. No-op replacements and replacements retaining any
selected old archive hash are refused, including nested copies.
The approval status is an explicit reviewer assertion; the tool never derives it
from package labels, candidate status or successful component probes. Known blocked
Guava 33.4.8/33.6 and RabbitMQ input hashes are additionally refused in code.

The reviewer must inspect every classloader's dependency closure before approving
any conditional Guava 33.7.1, LZ4 or Snappy occurrence. Never approve a whole fat
JAR from a Guava package label. RabbitMQ closure remains separate work. No automatic
mapped-plan generator is provided deliberately.

## Safety and byte guarantees

Preflight snapshots archive inputs and replacement bytes into an owned temporary
tree; validates the complete inventory binding, all ancestry/leaf/replacement
hashes and source-wide counts; rejects signed enclosing archives before rebuilding.
Leaf stock JARs are copied whole, retaining their signatures, native resources,
service files and metadata exactly. Both signature files (`SF/RSA/DSA/EC/SIG-*`)
and manifest digest attributes block changes to an enclosing archive.

All sibling targets in an ancestor are rewritten together once. Unrelated entries
retain uncompressed bytes, order, timestamp, comments, extras, compression method,
external/internal attributes and archive comment through copied `ZipInfo` records.
ZIP writer bookkeeping (CRC, compressed sizes, offsets and flags) is regenerated;
compressed containers are **not byte-identical**. No extraction uses member paths.
Zero external attributes are explicitly restored after Python's writer sets its
default. Before publication, the bounded output inventory and every rewritten
ancestor are checked against the source: sibling names/order/content, comments
and preserved metadata must match, with only selected leaves replaced.
Duplicate/ambiguous names, absolute/traversal/backslash/drive paths, ZIP symlinks or
special files, source/replacement symlinks, encrypted or unsupported compression,
CRC/truncation failures and malformed archives are refused. Only STORED and
DEFLATED compression are supported. Unknown external file types are refused,
except the exact legacy Unix `0xffff0010` representation of an empty STORED
directory with a trailing slash, zero sizes and CRC. It is preserved as metadata;
paths are never extracted. Four negative variants remain rejected.
Normal empty deflated directories are allowed only when their bounded compressed
stream decodes to empty. Any directory payload, ZIP preamble, non-ASCII name
without UTF-8 flag, local/central header mismatch or invalid descriptor boundary
is refused. ZIP64 sentinel sizes and bounded data descriptors are validated.

After staged output validation and leaf hash verification, Linux `renameat2` with
`RENAME_NOREPLACE` atomically publishes the entire tree. A concurrent existing
output wins; no output is overwritten. Failures clean owned temporary artifacts,
including injected write failure; no partial success tree is published. Process
termination can leave an unpublished temporary tree for owner inspection. This is
atomic publication, not a power-loss durability guarantee.

CLI processes use one allowed CPU, 512 MiB virtual address space and disabled core
dumps. Archive payloads stream/spool on disk, never accumulate an archive tree in
RAM. Defaults: depth 8, 256 MiB per archive/entry, 1,000,000 cumulative entries,
32 GiB cumulative expanded bytes (each repeated occurrence counts). Numeric CLI
budget options can tighten these offline limits. Snapshot compressed input bytes
are bounded too. Set `TMPDIR` to a private owned disk directory. Disk exhaustion
fails without publication. Central-directory and inventory metadata consume RAM;
the address-space cap fails closed rather than promising every valid large tree
will fit. Imported API callers must impose their own process limits. These offline
budgets do not change the CG32 6 GiB RAM / 20 GiB disk gate.

## Pinned source evidence, 2026-11-04

Cache: `/home/tears/.cache/cnc-nifi-ci-remediation-20261104/nested-patcher-occurrences`.
Parent baseline: `ea9e84f566685daeb50be896eae4c3e0a6439fac`.

51 GiB free preceded the authorized pull of
`apache/nifi:2.12.0@sha256:6f7f2840dbf178c6dd3fa13435b9b358f3be3c6fb7417de467a35a267f4d28ad`.
`image-inspect.json` records local image identity. `acquisition.json` records exact
Docker argv and cleanup. A uniquely named container was created with overridden
`/bin/false` entrypoint, network none, one CPU and 512 MiB memory; it was **never
started**. Only `/opt/nifi/nifi-current/lib/.` was copied (783 MiB). No conf, logs,
state or user mounts were copied. `stopped-inspect.json` records its stopped state;
`docker rm -v` removed only that owned container and its anonymous volumes.

`source-hashes.json` binds copied public input files before inventory probes:
`51f3cc3973b67027dd747baa9246134684a0497335e15efaebaf9118c04199ba`.
`inventory-command.json` binds the initial script/source hashes and argv. The first
measurement wrapper failed because `/usr/bin/time` is absent (`inventory.log`).
The Python retry (`inventory-retry.log`) failed closed at an unsupported ZIP mode:
`nifi-aws-nar-2.12.0.nar!META-INF/bundled-dependencies/commons-digester-2.1.jar`
contains `META-INF/maven/` with `external_attr=0xffff0010`, creator system 3.
No validation exception was added for this source. The failed full inventory is
**not complete evidence and cannot authorize any executable mapped plan**.

A separate diagnostic inventories outer archives independently, discarding each
failed outer's results. `partial-diagnostic.json` explicitly records `complete=false`
and `executable_plan=false`: 919 validated occurrences, 29 rejected outer archives,
35,240 KiB peak RSS. Its file SHA-256 is
`aa59a15fc8679f6e532e38e8ecff5b58f53c7084ce9dc2599585c950d986bc45`.
Counts below are **partial observed lower bounds**, never complete mappings:

| Input family | Observed exact-hash copies | Outer NAR names (all version 2.12.0) |
| --- | ---: | --- |
| Guava 33.4.8, blocked | 0 | Unknown in rejected outer archives |
| Guava 33.6, blocked | 1 | nifi-iceberg-shared (`iceberg-bundled-guava-1.11.0.jar`) |
| Guava 33.7.1, conditional | 3 | nifi-evtx, nifi-opentelemetry, nifi-protobuf-services |
| RabbitMQ, blocked | 1 | nifi-amqp |
| LZ4, conditional | 2 | nifi-kafka-3-service, nifi-kafka-service-aws |
| Snappy, conditional | 5 | nifi-avro, nifi-framework-zookeeper, nifi-kafka-3-service, nifi-kafka-service-aws, nifi-record-serialization-services |

Full observed member paths, outer/leaf hashes, ancestry and NAR dependency fields
are in the diagnostic, grouped against all six candidate input hashes. The shaded
Iceberg occurrence confirms why a whole-JAR replacement from labels is unsafe.
**Zero executable mapped occurrences, zero source archives patched.** A complete
strict source inventory and separate dependency/classloader review remain blockers.
All nested families stay unchanged. Base-source inventory is not final-image
acceptance; normal CI 0 / nested 59 tuples at source `2da877c`, run 41810126327,
job 126507014432 remain the parent's existing evidence, not a new scan here.

## Verification

Run `python -m unittest discover -s tests -p test_patch_nested_jars.py` under
`taskset -c <allowed-cpu> prlimit --as=536870912 --core=0 --`.
Fixtures cover repeated equal enclosing archives, sibling/nested replacements,
whole signed stock leaves, byte/metadata preservation, dry-run CLI, JSON ambiguity,
wrong hashes/counts, missing/duplicate/blocked/unknown rows, signed ancestors,
symlinks, traversal/absolute/duplicate paths, encryption, CRC corruption, malformed
archives, budgets, existing/overlapping output, source/replacement drift and rollback.

The full `python -m pytest -q` was attempted under the same cap; it ended with
collection `MemoryError` / pytest INTERNALERROR (exit 3, one error), before running
the suite. See `full-pytest.log`; this is **not a passing repository suite**. The
available interpreter is Python 3.14, outside this project's declared 3.11–3.12
range; no dependency/global installation was performed. Focused standard-library
verification is reported separately. No image build, NiFi runtime/processor flow,
final scan, SMB/broker/ES contact, push, PR, merge or green integration claim.

Final focused verification: **14 tests passed** under the stated CPU/address-space
limits. The duplicate-name fixture intentionally triggers a `zipfile` warning.
`diagnose.py` and `diagnostic-command-final.json` preserve the reproducible final
read-only diagnostic and hashes before execution. `partial-diagnostic-v2.json`
SHA-256: `26f59a2b3b5a57825a6adc85a31543a5850bd73766e3ed8f5c008b3d08f0db69`.
It again records 919 occurrences / 29 rejected outers. `/proc/self/status` records
VmPeak 47,356 KiB, VmHWM 35,388 KiB and CPU affinity 0. Its `getrusage.ru_maxrss`
field unexpectedly reports 578,620 KiB, inconsistent with that process's kernel
VmHWM; this discrepancy is preserved rather than treated as measured compliance.
The CLI and final diagnostic have a hard 512 MiB address-space cap. Docker daemon
pull/extraction resource consumption was not constrained by the CLI cap; no NiFi
process was started. A final `docker ps -a` name-filter query confirmed the owned
source container is absent.
