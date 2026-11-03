# Local HTTP and dashboard integration, 2026-11-03

Local-only follow-up to `6c5a056267dffec1a66b11c89d30a772c5dc1b19`.
No push or PR action in this phase. Original main and unrelated worktrees preserved.
Dashboard presentation comes from remote `feat/dashboard` at
`04d1bb12f0c0c156457ac346ced9385971e17a1a`, rechecked during this phase.
The stylesheet is retained; data/history/evaluation semantics are adapted to the
canonical API. API mode now polls every five seconds, with pause, shared UTC cutoff,
visible observation age and explicit unavailable state. This is not an ingestion SLA.

## Independently exercised local path

Evidence directory: `/home/tears/.cache/cnc-local-http-20261103/`.
Authoritative inference/storage run: `run-02/result.json`; the earlier `run-01`
is retained but superseded because its serialized canonical evidence was corrected
to preserve the actual HTTP response bytes before run-02.

- Actual uvicorn model lifecycle and HTTP POST inference using the locally generated
  sklearn test bundle. Manifest SHA-256:
  `3a78dff85e705b57c5d5e11c84f5a020f797ed70b59f4486671152e71034e6f9`.
  This bundle is not an approved industrial model.
- Two fresh telemetry samples, CNC-004, 1801 then 1902 RPM. Byte-identical POST
  replay; real CG15 receipt/Parquet and duplicate delivery; real Elasticsearch
  create-conflict replay; canonical bytes/CG15/ES/GET identity reconciliation.
- Actual ES PIT/composite reads and exact KPI count: one machine, two events after
  replay, still two events after ES restart. No ES transport or model doubles.
- `dashboard-http.json`: actual loopback HTTP into Streamlit AppTest; earlier
  cutoff shows 1801 RPM, renewed cutoff shows 1902 RPM. The four pages and details
  modal preserve the same event key, 21°C process temperature, 5 Nm torque and
  7 minutes tool wear. Timer elapsed state is triggered explicitly, not observed
  in a browser over wall-clock time.
- `dashboard-es-down.json`: own ES stopped, API returns unavailable, UI degraded
  without demo. `dashboard-recovered.json`: restart preserves data and restores
  all four pages/modal. First bounded readiness attempt timed out; later real
  readiness and recovery passed. No claim of fast restart or same-session browser
  recovery. `recovery-runtime.json` records green cluster and `OOMKilled=false`.
- `dashboard-api-down.json`: own API stopped, real transport failure produces
  degraded UI without metric cards; live refresh control remains enabled.

For the latest sample the exact event key is
`7b6e2a052486dd2e51fb1433f23e7def910dae2299d7a1b186f4fb55f968d4f7`.
The two measured POST-through-verified-read durations were approximately 1453 and
991 ms, with explicit ES refresh and direct archive/index writes by the harness.
Two samples do not establish throughput, p95, or full pipeline latency.

## Runtime and limits

Own ES container/network/volume: `cnc-local-es-20261103`, `cnc-local-20261103`,
`cnc-local-es-20261103`. Vendor ES 9.5.5 cached image:
`docker.elastic.co/elasticsearch/elasticsearch-wolfi@sha256:c2cce72acf8dc0510c04fd5926123f630859019082edf9827daef82b6a46c9c1`.
768 MiB container limit, 256 MiB heap, one CPU, internal Docker network, loopback
socat bridge on 18272; own API on loopback 18271. The isolated lab uses the existing
CG32 unauthenticated ES convention and absolute disk watermarks 4/2/1 GiB. It is
not a production configuration or validation of the patched final image.
API, bridge and ES were stopped after verification. Volume, index and evidence
are retained; nothing pruned. The full lab's 6 GiB RAM / 20 GiB disk preflight
minimum was not changed. Host resources remain insufficient for that full lab.

Local checks: 27 dashboard tests with `-W error`, 11 HTTP harness tests, targeted
Ruff and `git diff --check` pass. The prior full-suite result remains historical;
it was not rerun for this bounded follow-up. Runbook: `docs/integration/LOCAL_HTTP.md`.

Still unverified: Filebeat/Kafka/NiFi traversal, final image builds/scans and
read-only container RSS/concurrency, browser layout and real timer acceptance,
SMB access, independently bound offline evaluation, and human rubric acceptance.
The bounded local path is verified; complete project integration is not claimed.
