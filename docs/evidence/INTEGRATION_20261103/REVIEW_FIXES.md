# Assembled review corrections, 2026-11-03

Claude reviewed immutable c34cabe..c7adef8, independently reproducing the API/UI
number mismatch, SQLite writer lock, history latency and HTTP 500 responses for invalid dates/cursors.
The full local review is retained at
`/home/tears/.cache/cnc-integration-audit-20261103/CLAUDE_API_DASHBOARD_REVIEW.md`.

Corrections and concrete regression evidence:

- API machine number is an integer; the real ASGI response now passes the actual
  dashboard domain validator and numeric gallery formatting. The canonical
  CNC-000 identifier is accepted consistently by the dashboard.
- CG15 copies committed metadata under SQLite `mode=ro`, then releases the read
  transaction before hashing and parsing immutable objects. A writer invoked
  during the first object validation commits successfully; the current read sees
  its original snapshot and the next read sees the newly committed event.
- Periods validate the archive once for three windows. Pages only request history
  when they display it. Dashboard HTTP timeout is 2 s connect/20 s read.
- ES latest-per-machine aggregation avoids downloading 185 days. Exact 24 h event
  identity buckets replace whole-corpus KPI downloads; no approximate cardinality.
  Synthetic MockTransport tests exercise 110000 recent identities and 10 million older
  documents, scope, timestamp tie ordering, conflicting replays and incomplete
  searches. These are request/response contract tests, not ES latency benchmarks.
- All UI reads share a UTC cutoff until explicit refresh. The UI displays cutoff,
  observation timestamp and age, and states that separate ES requests are not one
  transaction. Refresh invalidates pagination. Null process temperature is explicit.
- Extreme UTC dates and malformed cursor bounds return 422. Evaluation also requires
  the selected prediction's exact risk threshold; incompatible matrices stay hidden.

Verification before final independent recheck: focused backend 51 tests, dashboard
26 unittest/AppTest cases with warnings treated as errors, and wiring 9 tests pass.
Changed Python files pass Ruff lint/format and git diff checks. A repository-wide
Ruff sweep additionally found existing issues in historical scripts/notebooks and
unrelated tests; these were not silently reported as clean or rewritten.

The bounded fixture reconciles canonical response, CG15 receipt/Parquet and GET;
model, ES and ASGI doubles are explicitly recorded. The loopback browser attempt
produced successful HTTP snapshot/KPI/history calls, but preview snapshots timed
out twice and the alternate browser was unavailable. Four-page visual acceptance
remains pending. See the repeatable commands in docs/integration/README.md.

Remaining acceptance: actual final image scans/imports, ES query latency, total
RSS/concurrency/read-only mount under 512 MB, actual full component traversal and
outages, Kibana candidate activation/browser, SMB and human academic gates.
Archive limits remain 20000 objects/events/receipts and 64 MiB per request with strict
all-committed-object integrity verification. Long campaigns require a measured
partitioned/compacted archive design; these bounds do not establish 185 day capacity.

Assembled full suite: **795 passed, 4 skipped, 374 subtests passed** (47.47s).

Portable assembled artifact at code `c7d627c84933323d894a6ab6911c74ff094be751`:
`integration-portable.zip`, 360 members, SHA-256
`4a3ac8aae651de92c4b9f821655ba209193991fa091545b27fc24a096ea4e7eb`.
CRC/all member hashes/sample restore passed. A fresh full extraction (no `.git`)
then executed the integration fixture successfully with the existing locked Python
environment, reproducing all six scenarios and retaining source revision metadata.
This is not an offline dependency installation. The initial extraction exposed a
Git-only runner assumption; the correction embeds hashed `BUNDLE_SOURCE.json`.
Dashboard image assets and image-patch source are included in the revised allowlist.

## Final-review follow-up

Claude rechecked `62a6e10`: seven earlier findings were verified closed or improved,
including a writer commit during 6000-event archive validation and single-pass
periods. Its new findings were corrected as follows:

- Dedicated dashboard image: pinned Wolfi base, Python 3.12, existing hashed dashboard
  requirements, isolated read-only service, no mounted worker interpreter. `view`
  builds and probes actual imports. CI includes its build, offline 512 MiB import
  probe and OS/Python/Rust scan coverage. Actual image results remain pending.
- Bundle source coverage now includes extensionless Dockerfiles, patch/XML inputs,
  CSV fixtures, Compose, Kibana/NiFi resources, Python source package and the public
  AI4I training fixture needed by CG32. The archived model remains externally supplied.
- Extracted source identity verifies all listed file hashes before the fixture runs;
  hashes detect mutation but are not an authenticated approval.
- Live same-event reconciliation follows bounded history cursors, reports absence
  explicitly and rejects a non-advancing cursor.
- Generated read scope pins the model manifest's risk threshold. Server ES/CG15
  filters and offline evaluation use that same threshold. Older configurations
  without a pin keep reads but cannot expose an evaluation matrix.

Elasticsearch's millisecond date sort and restricted replay-validation scope are
explicit in READ_API.md. There is no new claim of real ES latency, long-term archive
capacity, full Docker acceptance or successful browser/SMB/human acceptance.

Full suite after these corrections: **798 passed, 4 skipped, 374 subtests passed**
(61.74s). Focused backend/wiring:63 passed. Changed Python Ruff checks pass.
