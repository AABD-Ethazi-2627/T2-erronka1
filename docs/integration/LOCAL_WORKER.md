# Bounded local durable-worker rehearsal

This supplements `LOCAL_HTTP.md`: the canonical CSV adapter and durable worker
write CG15 and Elasticsearch themselves. The harness does not substitute direct
archive/index writes for the worker. This is staged-stdin transport, with synthetic
isolated topic/partition/offset coordinates. No Kafka record is consumed or ACKed;
Filebeat, NiFi scheduling, SMB and browser acceptance remain unexecuted.

Prerequisites: the normal backend `.venv` with its pinned Kafka dependency, a trusted
local test model bundle, and an Elasticsearch instance owned exclusively by this
rehearsal on a loopback port. Do not use a production/shared cluster or untrusted
pickle bundle. The runner uses the same supplied manifest for API and worker,
including the existing manifest/contract precondition checks. It does not generate
or approve a model. Resource planning and ES lifecycle remain the parent's job;
this command never starts Docker or changes the full CG32 preflight.

```sh
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 \
.venv/bin/python -m scripts.integration_worker_local \
  --output /absolute/new/local-worker-run \
  --manifest outputs/api/manifest.json \
  --es-url http://127.0.0.1:18272 --owned-es
```

The output directory must not exist. The runner creates unique local namespace,
topic and concrete ES index names. It installs the pinned ES final pipeline only
when absent and refuses an existing different guard; the strict mapping is copied
from the repository. No shared alias, source topic or existing index is changed.
It reserves its own ephemeral loopback API socket, starts uvicorn using the current
interpreter and supplied model, and always attempts to stop that own process.
It retains ES/index, output directory and every generated artifact on success/failure.

One row comes from `tests/fixtures/cg14/valid_event.csv`. Only timestamp (current
UTC) and machine ID (`CNC-004`) change; sensors and historical labels are retained.
These remain fixture readings, never physical observations. The fixture's original
hash, the changed input bytes and resulting hash are recorded. Two subprocess
invocations execute the real `scripts.run_durable_pipeline stdin` CLI with exactly
the same bytes, namespace, topic, partition 0 and offset 0.

Success requires:

- first call: one completed delivery; second call: one replay; neither rejects;
- both calls report `transport=staged-stdin` and `source_ack=false`;
- the worker journal retains one completed job, unchanged raw fingerprint,
  canonical response bytes and committed journal objects;
- only one scoring request is recorded across both invocations; the replay reuses
  the recorded response and verifies the ES immutable-create conflict;
- the worker's committed CG15 prediction, ES document, snapshot and history refer
  to the same event and sensor values; the exact KPI counts one event after replay.

The CLI rejects non-loopback/credential/path/query URLs. Each worker subprocess has
a 90-second bound; API readiness has 30 seconds; HTTP requests are bounded. Failures
preserve stdout/stderr, input, journal and `result.json` with error type/message.
Source identity records the actual Git revision and dirty flag; uncommitted work is
not relabelled as a clean revision. `canonical.json` and `canonical-replay.json`
are the exact canonical BLOB bytes retained by the worker, not an assertion that
an arbitrary HTTP wire serialization was captured. GET response bodies are retained
as `.response` before status/schema assertions, alongside readable JSON on success.

Useful artifacts include `worker-command.json`, `initial.stdout`/`.stderr`,
`replay.stdout`/`.stderr`, `initial-journal.json`, `replay-journal.json`,
`worker/pipeline.sqlite3`, `worker/archive/`, `api.log`, `read.json`, and `result.json`.
The read scope is `kafka://local-worker-<UUID>/cnc-local-raw-<UUID>`; the URI is the
canonical occurrence convention, not proof that a Kafka broker was used.
To inspect reads later, use the retained `read.json`, the same trusted model manifest
and canonical ledger when restarting an own API, as described in `LOCAL_HTTP.md`.
The companion HTTP dashboard probe expects two samples and cannot be used unchanged
for this one-event worker fixture.

Unit checks require no services or network:

```sh
.venv/bin/python -m pytest tests/test_integration_worker_local.py -q
ruff check scripts/integration_worker_local.py tests/test_integration_worker_local.py
```

These unit checks exercise guards, fixtures, journal validation and retained errors
with explicit subprocess doubles. They are not live integration evidence. A successful
actual invocation is additional local worker evidence, not full pipeline, final-image,
source ACK, browser, SMB or rubric acceptance.
