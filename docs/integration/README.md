# Opt-in integration candidate (#109/#110)

This extends CG32, not the accepted CG14/CG19 exports. One worker owns offsets;
NiFi schedules `run_automatic_graph` and does not run a second ConsumeKafka.
Source is `lab_fixture`, acquired from a local directory, never SMB. No approved
model evaluation binding is manufactured. Missing evaluation stays unavailable.

## Bounded local reproduction (no Docker)

Use the assembled locked environment with kafka extras and read runtime packages.
The child used `/tmp/cnc-backend-311/bin/python`, installing only the repository's
vendored kafka wheel into that existing environment (no dependency commits).

```sh
python -m scripts.integration_fixture --output /absolute/new/fixture-run
python -m pytest -q tests/test_integration_wiring.py tests/test_cg14_durable_pipeline.py tests/test_automatic_graph.py tests/test_scoring_replay.py tests/test_read_api.py
python -m scripts.integration_bundle --evidence /absolute/new/fixture-run --output /absolute/new/evidence.zip
```

Runner retains the raw response, source sentinel, actual canonical SQLite ledger,
CG15 receipts/Parquet, raw GET JSON and ES-double document. Before the deliberate
corruption test it copies only its own archive to `pristine-archive`. Use
`same_event(raw_bytes, pristine_archive, es_hit, snapshot_row, history_event,
ui=None)` to recheck. Tampering any sensor/key/canonical receipt fails. Optional
UI evidence must supply event_key, exact snapshot and separately captured artifact
hash. It is **not** browser verification by itself. Parent must attach/render and
review the artifact and all four pages/modal. No UI completion is inferred.

The six bounded scenarios distinguish model/ES/ASGI doubles from actual storage.
Worker tests separately cover CSV rejection, API transport loss, uncertain ES
create, required-destination failures, corruption and offset ownership. A 503
unready API fixture is not an actual stopped container. Sent=accepted+rejected+
pending in result.json describes requests, including replay, not Kafka offsets;
real CG32 run.json and worker journals provide separate occurrence/offset counts.

ZIP inputs are tracked allowlisted source/lock/config, these six result JSON files,
and the pristine synthetic archive. No venv/cache/credentials/private model trees.
The builder verifies CRC, every member SHA and sample extraction/re-read; writes a
sidecar SHA for the ZIP. A portable package reproduces fixture tests after installing
the locked dependencies; it is not an offline vendored runtime or model package.
Use an independently approved model bundle for the real lab. Restores must generate
new host-specific mounts/config; do not reuse another host's absolute paths.

## Real lab commands — BLOCKED until >=6 GiB RAM and >=20 GiB disk free

Do not lower CG32 budget checks, prune others' resources, or start parallel builds.
`integration_lab` inherits CG32 init/up/run/stop, TLS trust/bootstrap and private
0600 generated credentials. Use a dedicated uv environment including Streamlit,
Kafka and the locked read dependencies. Its interpreter and runtime are mounted
read-only into NiFi/UI; checkout, manifest and run state paths are regenerated for
this host. The API has two read-only archive mounts so the writable parent run
mount does not expose an alternate writable archive path.

```sh
python -m scripts.integration_lab --lab /absolute/new/private-lab init
python -m scripts.integration_lab --lab /absolute/new/private-lab up
python -m scripts.integration_lab --lab /absolute/new/private-lab run --manifest /approved/bundle/manifest.json --label integration --rate 1 --duration 10
# Candidate bundles require the existing --identity-record mechanism.
# After successful run, use its recorded run name:
python -m scripts.integration_lab view --lab /absolute/new/private-lab --run RUN_NAME --bundle /approved/bundle
python -m scripts.integration_lab --lab /absolute/new/private-lab stop
```

The run stops its own ingestion and API through CG32 finalization. `view` restarts
only that API and Streamlit, leaving the worker stopped. It verifies the historical
bundle pin; candidate view also accepts `--identity-record`.
Ports are allocated on loopback; inspect `docker compose port` or the returned
port output. Never `down -v`. Stop retains run state, offsets, ledgers and archives.
Do not change an initialized campaign's namespace, group or model.

Explicit wiring generated per run:

- Filebeat and worker: `kafka:19092`; HOST observation listener loopback:9092.
- POST: `http://api:8000/predict`; ES: `http://elasticsearch:9200`.
- Concrete write index: `cnc-alerts-cg32-<unique-run>`; new read alias `<index>-read`.
- GET config `CNC_READ_CONFIG=<run>/read.json`, archive `/archive`, scope source URI
  `kafka://<project>/<run>/<topic>`, RF hash and policy from pinned manifest.
- UI `LANEKI_MODE=api`, `LANEKI_API_URL=http://api:8000/api`.
- `candidate-data-view.json` uses only that alias. Import explicitly into own
  Kibana via POST `/api/data_views/data_view` with `kbn-xsrf: true`; no historical
  data view/export is replaced. Parent must verify CG19 candidate panels use it.

Before API/ingestion activation the extension requires actual image imports from
`/app` (not the host checkout), DuckDB 2.0.0, the copied output helper, graph scope,
manifest, ES strict mapping/final pipeline, read-only archive and resolved Compose
listeners/mounts. The image is supplied by the dependency child's scoring Dockerfile;
no duplicate lock or service-specific dependency export is added here.

## Remaining acceptance gates

The generated configuration is a candidate until actually exercised on sufficient
resources. Full image build/import/endpoint/RSS validation, NiFi interpreter execution,
Filebeat→Kafka→worker→ES→GET reconciliation, actual read-only mount concurrency,
UI four-page/modal browser checks, real API/ES outage/recovery and all component
accounting remain parent gates. `view` uses a Python slim container with a mounted
locked host environment; validate ABI/imports on the target host before acceptance.
SMB #111 and human/teacher acceptance are separate and remain pending.
