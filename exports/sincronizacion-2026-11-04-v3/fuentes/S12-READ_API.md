# Opt-in current-state read API (#106–#108)

The write API, model readiness and response-ledger identity are unchanged.
Enable using `create_app(read_config={"scope": ReadScope(...), "current": reader,
"archive": ArchiveReader(root), "evaluation_config": config})` or set
`CNC_READ_CONFIG` to an operator-owned JSON file:

```json
{
  "scope": {
    "source_uri": "fixture://integration",
    "model_artifact_sha256": "<64 lowercase hex characters>",
    "policy": "f2",
    "risk_threshold": 0.5
  },
  "elasticsearch": {"url": "http://elasticsearch:9200", "index": "explicit-alias"},
  "archive_root": "/archive"
}
```

This is opt-in; no automatic fallback. HTTPX keeps TLS verification enabled.
An injected reader implements `rows(scope, start_datetime, end_datetime)`.
ES uses an independent point-in-time search, exact keyword scope terms, and no
approximate cardinality. Timestamp, machine_id and event_id must be sortable
(existing CG18 mapping). Only the configured source/model/policy match.
An optional `risk_threshold` binds prediction reads and offline evaluation to one
exact decision threshold. The generated integration configuration always pins it
from the manifest. Legacy configurations without it can read predictions, but
model evaluation is unavailable (`read_threshold_not_pinned`). ES filters and
CG15 use the same threshold scope; provenance/cursor scope includes the pin.
ES `date` sorting has millisecond precision, while stored payloads and CG15 retain
microseconds. Events within one ES millisecond tie by event_id, not by submillisecond
time; callers must not assume microsecond ordering from the current-state snapshot.
Failures, invalid persisted predictions, partial ES shards, conflicting duplicate
identities and >50 machines return 503. Empty ES returns an empty list.

## Wire contract

- `GET /api/makinak?as_of=<aware ISO timestamp>` returns a list, ordered by machine
  ID. Latest row per machine: timestamp DESC, event_id ASC, within the previous
  185 days, excluding as_of. Headers `X-CNC-As-Of`, `X-CNC-Lookback-Start` expose
  the snapshot interval without changing the list contract. Pass the same explicit
  as_of to KPI and snapshot to align cutoffs; separate ES PITs are not a cross-request
  transaction, so late ingestion can change their contents. The dashboard fixes
  a shared as_of per refresh (automatic best-effort polling every 5 seconds in API
  mode, with pause control), displays the cutoff and per-observation age, and
  uses a 20-second read timeout (2-second connect timeout). History is requested
  by the relevant view rather than eagerly for every page.
- `GET /api/kpis?as_of=...`: exact deduplicated events in `[as_of-24h,as_of)`,
  latest machine counts, mean process Celsius and denominator. `motak` contains
  H/M/L counts (unknown excluded); `osasuna=null`. Counts refer to inferred alert
  levels, never observed machine failures or proof of physical operation.
- Every projected event preserves event_id/model hash/policy/source, and adds
  `event_key` matching CG15/ES, `risk_threshold`, `decision_rule`, `machine_type`.
  Risk decision and threshold are preserved and checked; alert levels retain the
  stored 0.15/0.70 presentation policy. Temperatures are process/ambient Kelvin
  minus 273.15; torque Nm and wear minutes retain their units. Missing sensors
  remain null. No health, vibration, current, forecast, ETA or RUL is synthesized.
- `GET /api/historikoa/{id}?desde=...&hasta=...&limit=1000&cursor=...`: columns
  in `datuak`; metadata contains full page `events`, total count, page_count,
  source, UTC limits, coverage and latest age. Samples ordered timestamp ASC,
  event_id ASC. Default previous 24h. Bounds are inclusive/exclusive and at most
  185 days. ID follows the existing canonical `CNC-[0-9]{3}` contract (not a
  new machine population restriction). Unknown machine in this scope: 404;
  known machine with no observations in the interval: 200 empty columns.
- Cursor fixes interval, scope, machine, offset and result fingerprint. Clients
  should pass it unmodified and can omit time parameters on subsequent requests.
  Invalid cursor/limits: 422. Changed archive result: 409; restart pagination.
- `GET /api/historikoa/{id}/periodoak?as_of=...`: `astea`, `hilabetea`,
  `sei_hilabete`, each a History container with `next_cursor=null`. All observations
  in the window participate regardless of page size. Seven/thirty days use
  consecutive UTC 24h bins anchored at the window start (at most 7/30); six calendar
  months clamp the day to the target month's last day and use calendar-month bins
  (at most 7). Empty bins are omitted. Metadata identifies `kind=mean`, exact
  aggregation, per-signal n, bucket count and last full event. Missing signals
  average to null, never zero. Bucket labels can precede the clipped six-month
  window; metadata.desde/hasta remain the exact selection bounds.

## Committed archive integrity and capacity

SQLite uses `mode=ro`, a read transaction and busy_timeout=1000ms, never immutable.
It snapshots object hashes, event hashes and accepted receipts, then closes the
connection before hashing/decoding immutable object bytes. A concurrent writer
therefore does not wait for the expensive Parquet validation phase. No directories
or schema are created. A concurrent writer's uncommitted objects are invisible. Only ledger-listed `prediction/date=.../*.parquet` contributes
points. Telemetry-only records do not imply model-scoped observations. Coverage
means observed predictions, not expected physical sampling completeness.

The additive `prediction_read_index` selects committed predictions by source,
model, policy, optional decision threshold, machine and exact UTC microsecond
window **before** opening objects. Each entry links the composite event key and
canonical hash to its Parquet path and one accepted delivery ID. The reader
verifies both the selected Parquet and that delivery's original bronze bytes
against their `objects` hashes, the `events` canonical hash, and the accepted
`deliveries` fingerprint (`prediction` + NUL + original bytes). JSON need not use
canonical whitespace. All indexed metadata must match the verified prediction,
and Parquet must contain that same single prediction. A duplicate retains the
first accepted representative receipt; it never substitutes a rejected delivery.

The reader checks every object it uses, not every retained object. Unrelated
old, other-source, telemetry or rejected objects do not consume the query budget;
their corruption is not detected or certified by this GET. For an empty interval,
one separately bounded, verified latest prediction in the same machine/scope
proves existence (200 empty rather than 404). This witness can be outside the
requested interval; if corrupt, the request fails 503. Unknown machines require
no object reads. Files absent from `objects` (orphans) are never scanned. Paths
must resolve beneath the configured root. DuckDB consumes verified Arrow bytes,
avoiding a second unverified Parquet filesystem read. Reads never repair receipts
or create inference results.

Limits remain 20,000 **selected** objects and 64 MiB verified bytes per request;
each prediction needs two objects, so at most 10,000 predictions can participate.
Exhaustion returns 503, never truncated counts. Pagination does not bypass this
bound: full selected rows are validated before fingerprinting and aggregation.
Six-month periods can still exceed these limits for a dense single-machine scope;
this fix removes dependence on unrelated retention, not the need for a separate
larger-scale aggregation design. ES snapshot/count limits are below.
DuckDB: one in-memory connection per read, one thread, 128 MB internal memory,
no spill directory, external access disabled after connection initialization,
autoinstall/autoload extensions disabled. No JSON/network extension is required.
These bounds do not prove total RSS below 512 MB under concurrent load; container
RSS/concurrency acceptance remains #109/#110. Periods validate the archive once
per request and then filter that snapshot into the three windows.

### Index coverage and legacy migration

New writes commit index entries in the same transaction as object/event/delivery
receipts, before ACK. Small transactional coverage counters track prediction
objects and index entries; missing coverage, version mismatch, missing triggers,
or mutated/deleted index metadata fail closed. Prediction-object deletion or path
mutation marks coverage dirty, so equal counts cannot hide replacement objects.
An older writer appending predictions creates a detectable coverage gap. These
checks assume the existing trusted SQLite ledger boundary; they do not authenticate
an attacker rewriting the ledger and its triggers together.

GET opens only `mode=ro`; it never initializes or repairs an index. A legacy archive
without the index, or mixed legacy/new writes with incomplete coverage, returns
503 while coverage remains incomplete. The recommended way to establish complete
coverage is this explicit offline operation, with **all writers stopped**:

```sh
python -m scripts.archive_read_index /owned/archive --writer-stopped
```

The command requires an existing ledger, takes `BEGIN IMMEDIATE` without waiting
for another writer, verifies accepted original bronze receipts and all resulting
indexed predictions, and commits complete coverage atomically. It uses only ledger
paths, preserves all existing objects and all three original receipt tables, and
is idempotent. A failure rolls back new index changes. Back up the archive first;
the flag confirms an operational prerequisite, it does not stop writer processes.
This is a full offline verification pass and can be expensive for a large archive.
Accepted duplicate predictions with new delivery IDs can also progressively add
missing index entries through the current writer. If those entries cover every
committed prediction and the index is not dirty, reads can become available
without running backfill; each selected entry is still fully verified. GET itself
never performs this reconciliation. Direct SQL access remains a trusted boundary.

The writer's pre-existing **global** committed-object reconciliation remains
unchanged. Its per-write hash scan, deployment resource bounds and sustained-rate
acceptance need separate measurements; this read fix makes no sustained 4 events/s
or unlimited retention claim.

## Elasticsearch snapshot and exact KPI capacity

The production ES reader selects the latest event per machine with a composite
machine aggregation and `top_hits(timestamp DESC, event_id ASC)`. It requests
51 buckets so exceeding the 50-machine scope fails explicitly. It does not
retrieve every document from the 185-day lookback. Missing event/machine identity,
partial shards and timeouts fail closed. All copies of each selected event are
compared as canonical JSON under the same PIT, so replayed copies across indices
are accepted only when identical. An alias is not assumed to guarantee uniqueness.

For KPI counts, a separate composite aggregation within that same PIT traverses
only event_id keys from `[as_of-24h,as_of)`, in pages of 10,000. Counting buckets is
exact; no cardinality approximation, full prediction transfer or 185-day event
cap is used. Duplicate buckets trigger bounded payload reads and conflict checks.
The default budget is 1,000 composite pages per KPI request; exhaustion returns
503, never a partial count. Payload validation for selected/duplicate identities
retains the 100,000-document safety limit. The generic `rows()` adapter also retains
its original cap for injected integrations. These are request capacity guards,
not retention limits. A machine-only GET does not perform the event count.

KPI metadata explicitly uses `coverage_basis=latest_per_machine`: its count and
first/last observations describe the selected machine snapshots, while
`gertakariak` and `event_window` describe the exact 24-hour event population.
This read path validates selected payloads and conflicting replay identities;
it is not an integrity audit of every older, unselected prediction. Each HTTP
request gets one PIT; requests with the same cutoff remain separate transactions.

Local MockTransport regressions exercise 110,000 recent distinct identities with
a simulated 10-million-document corpus and a payload budget of one: the result
remains exact because only keys are counted. They also cover timestamp ties,
identical/conflicting replays, 51-machine rejection, partial search failure,
empty results, cursor progression, page-budget exhaustion and PIT cleanup.
This verifies query/adapter behavior, not ES throughput or real cluster latency.
Live ES latency/concurrency and read-only image acceptance remain integration gates.

## Offline evaluation trust boundary

`GET /api/model-evaluation` returns `available=false` with a reason when absent,
invalid or unverified. It emits no matrix or guessed model identity then.
The existing cg19-offline.json alone is insufficient and is never auto-discovered.
Optional JSON `evaluation` configuration requires:

- `path`, `sha256`: evaluation artifact with overall tn/fp/fn/tp, rows, positives,
  negatives, alerts, threshold, provenance including source_sha256 and partition.
- `model_manifest_path`, `model_manifest_sha256`: independently approved manifest;
  sibling rf.pkl bytes must match the configured scope hash. Model policy and
  risk_threshold must match the selected scope and evaluation threshold.
- `provenance_path`, `provenance_sha256`: independently approved binding JSON with
  evaluation_sha256, scope (same three fields), model_version matching manifest,
  provenance exactly matching the artifact. This pin is an operator trust root:
  do not fabricate a binding from filenames/proximity or generate it from cg19
  just to make the endpoint available. No sealed dataset is loaded.

Available responses have scope=offline_model_evaluation, labels=[0,1], matrix
[[tn,fp],[fn,tp]], denominators, recomputed accuracy/precision/recall/F1 (null for
zero denominators), partition, provenance hashes and decision_rule=`risk_alert@policy`.
This is not evaluation by machine, live quality, or the AVISO/CRITICA confusion
matrix. Reused validation must retain its original partition label.

## Assembly and verification limits

Runtime additions for parent #109: `duckdb==2.0.0`, `pyarrow==23.0.1`,
`httpx==0.28.1`, and copy `scripts/duckdb_output.py` and
`scripts/archive_read_index.py` into the scoring image. The latter's read path has
no Kafka imports; its offline backfill additionally needs `scripts/platform_io.py`.
No dependency manifests, lock, exports, Dockerfile or dashboard changed here.
Local tests use synthetic payloads, actual CG15 SQLite/Parquet and ASGI, with ES
HTTP doubles; they do not establish live ES, SMB or image integration. Fixtures
keep lab_fixture provenance. Run `tests/test_read_api.py`, `test_archive_consumer.py`,
`test_duckdb_output.py`, `test_api.py`, `test_scoring_replay.py`. The two packaged
model tests skip when no approved bundle exists; replay tests use explicit doubles.

Local verification on 2026-11-03: focused read/API/replay/archive/Arrow suite passed
on CPython 3.11 and 3.12 with DuckDB 2.0.0: **60 passed, 2 skipped, 11 subtests**
on each interpreter. Both skips are the existing packaged-model tests without a
bundle. Ruff and git diff --check passed. Live-writer test observes one committed
row during a second pending delivery and two after its commit. This is local
filesystem concurrency evidence, not a read-only Docker mount acceptance test.

Interpreter verification: dedicated `/tmp/cnc-backend-311` uses CPython 3.11.17;
`/tmp/cnc-backend-312` uses 3.12.14. The inherited repository venv turned out to
use 3.12 and was not counted as 3.11 evidence. A subsequent mixed-ledger regression
(telemetry + two prediction policies + rejected delivery) passed independently on
both interpreters: **one additional passed test each**. It verifies only the scoped
prediction contributes a history point and its event_key matches the Parquet name.
