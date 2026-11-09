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
The builder verifies CRC, every member SHA and sample extraction/re-read.
The extracted runner verifies all listed member hashes before recording source
identity and rejects added files. Python-generated `__pycache__` entries are
allowed only for listed source modules; compiled bytecode is not authenticated.
Keep new run outputs outside the restored source tree. This detects source-tree
mutation, not an authenticated signature or
approval. Source coverage includes Dockerfiles, XML/patch inputs, CSV fixtures,
Compose, and Kibana resources; external build downloads still require network.
The builder writes a sidecar SHA for the ZIP. A portable package reproduces fixture tests after installing
the locked dependencies; it is not an offline vendored runtime or model package.
Use an independently approved model bundle for the real lab. Restores must generate
new host-specific mounts/config; do not reuse another host's absolute paths.

## Real lab commands — BLOCKED until >=6 GiB RAM and >=20 GiB disk free

Do not lower CG32 budget checks, prune others' resources, or start parallel builds.
`integration_lab` inherits CG32 init/up/run/stop, TLS trust/bootstrap and private
0600 generated credentials. Use a dedicated uv environment including
Kafka and the locked read dependencies. Its interpreter and runtime are mounted
read-only into NiFi; checkout, manifest and run state paths are regenerated for
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
  `kafka://<project>/<run>/<topic>`, RF hash, policy and risk threshold from pinned manifest.
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

The later [image-backed local verification](../evidence/LOCAL_CONTAINERS_20261103.md)
adds actual API/dashboard image builds and scan gates, a migrated copy of the
committed archive, byte-identical POST replay, and the Filebeat/Kafka event verified
through those images into desktop/mobile Chromium. It also records the complete
local test rerun. This supersedes image/browser-pending statements below only for
those exact components, event and limits; the full NiFi/Kibana campaign remains open.

The bounded real HTTP/ES/CG15 rehearsal is documented in
[LOCAL_HTTP.md](LOCAL_HTTP.md) and [its dated evidence](../evidence/LOCAL_HTTP_20261103.md).
Later [pipeline and browser evidence](../evidence/LOCAL_PIPELINE_BROWSER_20261103.md)
extends it with three distinct scopes:

- Actual Chromium four-page/modal, desktop/mobile, automatic refresh and same-session
  ES outage/recovery checks against the HTTP series.
- The real durable worker over staged stdin, with replay and the same event verified
  through API/CG15/ES/GET and browser DOM. See [LOCAL_WORKER.md](LOCAL_WORKER.md).
- Actual Filebeat production into an own Kafka topic, real durable-worker consumption
  and offset commit, then API/CG15/ES/GET reconciliation. Its event is distinct from
  the browser-checked event; its later replay is staged stdin. See
  [LOCAL_KAFKA.md](LOCAL_KAFKA.md).

That producer used digest-pinned vendor Filebeat 9.5.5, not the final patched
Filebeat image. [LOCAL_FILEBEAT.md](LOCAL_FILEBEAT.md) retains the producer setup
and capture commands for a new isolated reproduction.

All use synthetic readings and an explicitly local test model. The bounded stages
ran sequentially; they do not establish full simultaneous stack capacity. The
Filebeat OS target and Kafka candidate were built; the Kafka scan gate also
passed. Security/runtime closure for the other final images remains separate. See [LOCAL_IMAGE_BUILDS.md](LOCAL_IMAGE_BUILDS.md) for
serial builds with bounded Cargo jobs.

Remaining gates include final image build/import/endpoint/RSS validation under the
actual container limits, NiFi interpreter/scheduling execution, Kibana candidate
panel reconciliation, actual read-only mount concurrency and full component
accounting. The latest Kafka event still needs its own browser reconciliation.
`view` builds the dedicated dashboard image and checks imports before starting
API/UI. It uses Python 3.12 from the digest-pinned Wolfi base and
`dashboard_laneki/requirements.txt` with hashes; it never mounts the worker
interpreter or a host virtualenv. The service is read-only with a 64 MiB scratch
mount and a 512 MiB memory limit. CI builds/scans this image and verifies imports
without network under these limits. Successful imports alone do not prove
interactive RSS or visual acceptance.
SMB #111 and human/teacher acceptance are separate and remain pending.

On a real run, the extension drains via CG32 then refreshes the own ES index and
captures a current GET row and matching history event before API shutdown. It
checks the retained worker canonical payload against CG15 and ES `_id/_source`,
then writes `canonical.json`, `get-snapshot.json`, `get-history.json`, `es-live.json`
and `integration-reconciliation.json`. A missing/different stage fails this gate. History cursors are followed until the
selected event is found, with a 100-page bound and explicit absence/cycle errors.
UI remains pending; `view` is a separate parent browser session. The worker and API
manifest bytes must both match the run's reserved manifest SHA before activation.

## Repeat the bounded browser rehearsal

After a successful `integration_fixture` run, in separate local terminals:

```sh
python -m scripts.integration_preview --fixture /absolute/new/fixture-run --port 18271
LANEKI_MODE=api LANEKI_API_URL=http://127.0.0.1:18271/api python -m streamlit run dashboard_laneki/app.py --server.address=127.0.0.1 --server.port=18501
```

Open http://127.0.0.1:18501, check Hasiera, Makinak and its details dialog,
Datuak (including six months), Abisuak, and the refresh button. The preview serves
actual read routes and the pristine CG15 archive over HTTP; Elasticsearch remains
a frozen double and the canonical result was produced with synthetic models.
It exposes no POST inference route. It must never be used as live acceptance.
The event timestamp is frozen in the fixture: an empty last-day history is correct;
select the six-month period to inspect it while it remains in that window.

The first browser attempt on 2026-11-03 failed: the shared preview timed out twice
(15000ms), and another browser path reported `Browser is not available: iab`.
Those attempts produced no visual acceptance. A later isolated Chromium session
successfully exercised the four pages, modal, live refresh, mobile layout and
same-session ES outage/recovery with the real local HTTP/ES setup, followed by a
separate staged-worker event reconciliation. See the
[dated browser evidence](../evidence/LOCAL_PIPELINE_BROWSER_20261103.md) for the
actual artifacts, source identities and limitations. These later checks supersede
the earlier browser-pending status only for their explicitly exercised scopes.
