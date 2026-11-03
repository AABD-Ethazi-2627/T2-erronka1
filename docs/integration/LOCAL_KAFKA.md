# Local Kafka worker and ACK rehearsal

This extends `LOCAL_WORKER.md` with an actual broker input and worker-owned commit.
The coordinator prepares an isolated broker/topic and external producer first; the
runner never creates topics, publishes messages, starts/stops containers, or changes
CG32's full-lab resource guard. Its only offset mutation is the real durable
worker's commit for a fresh unique group after required destinations persist.

Prerequisites:

- An owned broker exposing one loopback HOST listener. Advertised broker metadata
  must also use loopback. A single existing `cnc-local-raw-*` topic has partition 0
  and exactly one retained CSV message. No producer may append during the run.
- A source namespace beginning `local-kafka-`, identifying this own broker/log
  generation. Preserve it for replay; do not reuse it for a different log.
- The message is valid CG14 CSV for `CNC-004`, with a recent UTC timestamp so GET
  history and the 24-hour KPI can include it. The harness does not rewrite bytes.
- An owned loopback Elasticsearch, the trusted local model bundle and backend venv.
  Stop the external Filebeat process before the worker phase if sequencing resources.
  Filebeat provenance/digest/config/logs are separate evidence; the runner cannot
  infer which producer wrote a broker message just by examining its contents.

```sh
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 \
.venv/bin/python -m scripts.integration_kafka_worker_local \
  --output /absolute/new/local-kafka-worker-run \
  --manifest outputs/api/manifest.json \
  --es-url http://127.0.0.1:18272 --owned-es \
  --bootstrap-servers 127.0.0.1:19094 --owned-broker \
  --source-namespace local-kafka-YOUR-LOWERCASE-ID \
  --topic cnc-local-raw-YOUR-LOWERCASE-ID
```

Replace the uppercase placeholders with lower-case alphanumerics/hyphens. For the
coordinator's run prepared on 2026-11-03 the source namespace is
`local-kafka-11feee702228`, topic `cnc-local-raw-11feee702228`; these identify that
retained log, not a reusable default for unrelated future runs. The output directory
must not exist. Each invocation creates a new worker group and ES concrete index;
using the same namespace/topic again retains occurrence identity but is a separate
isolated sink rehearsal, not a claim of global cross-index deduplication.

The first consumer uses manual assign/seek with `group_id=None`, auto-commit and
automatic topic creation disabled. It captures exact bytes, key, partition, offset,
timestamp, start/end offsets and hashes. The own worker group must initially have
no committed offset. The runner starts its own ephemeral loopback API with the same
manifest, strict scoped read configuration and trusted local model. It executes the
real `scripts.run_durable_pipeline kafka` CLI, one record per poll, at most 12 polls
and a 90-second subprocess deadline. Each offset lookup (beginning, end and group
commit) has its own 15-second timeout, including observations after the worker.
Advertised broker metadata is rechecked on each observation against loopback.
The single-message precondition is rechecked
through the end offset after processing; a new append fails acceptance.

Success requires one completed worker delivery and a broker `committed` offset
exactly equal to the captured offset plus one. The observer uses OffsetFetch/log-end
queries without subscribe, assign, poll or commit, so it cannot join/rebalance the
worker's group. The actual source ACK is distinguished from the subsequent replay:
`run_durable_pipeline stdin` receives the exact captured bytes and coordinates,
reports `source_ack=false`, reuses the canonical response, issues no extra scoring
POST, verifies an ES 409 immutable-create replay, and leaves the committed offset
unchanged. CG15/ES/snapshot/history must reconcile through `same_event`; the exact
KPI remains one event. No Kafka exactly-once transaction is claimed.

Key artifacts:

- `input.csv`, `input.key.bin`, `broker-record.json`: exact captured source; null key
  is explicitly marked separately from empty key bytes.
- `broker-before.json`, `broker-after-kafka.json`, `broker-after-staged.json`:
  observed offset state and stable log end.
- `kafka-command.json`, `replay-command.json`, worker stdout/stderr, API log,
  canonical blobs and initial/replay journal snapshots.
- `worker/pipeline.sqlite3`, `worker/archive/`, `read.json`, GET/ES responses and
  `result.json`: retained source identity, model hash, accounting and reconciliation.

Failures/timeouts retain generated evidence and error details. Consumer closes
explicitly disable autocommit. The runner stops only its own API and preserves the
broker, ES, topic, group state, index, journals and evidence. A failed result's
`source_ack_verified=false` means ACK was not verified by the runner; it is not
proof that the worker never committed before failing. Inspect retained broker and
journal evidence before any retry. A new output/group does not repair an old run.

Unit verification uses declared doubles and no services:

```sh
.venv/bin/python -m pytest tests/test_integration_kafka_worker_local.py -q
ruff check scripts/integration_kafka_worker_local.py tests/test_integration_kafka_worker_local.py
```

Actual success establishes this bounded Kafka/worker/API/CG15/ES/GET path. NiFi
scheduling, image security closure, browser, SMB and approved-model/human rubric
acceptance remain distinct gates. Source identity preserves the actual Git dirty
flag; freeze the runner in a local commit before collecting a clean-source result.
