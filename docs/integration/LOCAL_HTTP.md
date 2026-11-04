# Bounded local HTTP rehearsal

This runner is separate from the full CG32 lab. It uses actual HTTP, the canonical
API and its loaded local test bundle, durable response ledger, CG15 receipts and
Parquet, and actual Elasticsearch. Filebeat, Kafka, NiFi, SMB and browser acceptance
are not covered. No synthetic model or ES transport doubles are substituted.
The supplied bundle must be trusted; local generated test models are not approved
industrial model identities. Do not pass an untrusted pickle directory.

Prerequisite: an ES instance owned exclusively by this rehearsal, exposed on an
explicit loopback port and using the resource budget chosen by the coordinator.
The CLI does not start Docker, alter watermarks, remove indexes or stop ES. It
creates a unique `cnc-local-<UUID>` index with the checked-in strict mapping and
pinned final ingest guard; an existing different guard causes failure, not replacement.

```sh
.venv/bin/python -m scripts.integration_http \
  --output /absolute/new/local-http-run \
  --manifest outputs/api/manifest.json \
  --es-url http://127.0.0.1:18272 --owned-es
```

The runner reserves its own ephemeral API TCP socket, starts uvicorn with the
current interpreter and actual model lifecycle, sends two current-dated sensor
samples, checks byte-identical prediction replay and reconciles canonical response,
committed CG15, ES document, snapshot, history and exact KPI. Raw JSON, startup log,
read configuration and final result remain in the output directory. The API process
is stopped even on failure; ES and its index are retained. Unit tests of URL/index
protection use MockTransport and are explicitly not live evidence.

To inspect the resulting API with the dashboard, restart only the same owned API:

```sh
MODEL_MANIFEST="$PWD/outputs/api/manifest.json" \
SCORING_LEDGER=/absolute/local-http-run/canonical.sqlite3 \
CNC_READ_CONFIG=/absolute/local-http-run/read.json \
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 \
.venv/bin/python -m uvicorn scoring.score_api:app --host 127.0.0.1 --port 18271

LANEKI_MODE=api LANEKI_API_URL=http://127.0.0.1:18271/api \
/absolute/locked-dashboard-venv/bin/python -m streamlit run dashboard_laneki/app.py \
  --server.address=127.0.0.1 --server.port=18501
```

Keep ES alive for that inspection; verify the exact event keys in the retained
snapshot/history JSON against the rendered readings. Further new POST responses
must be committed to CG15 and indexed with the same canonical identity before
read routes can see them; the API is not itself an ingestion/ES worker. Stop only
these owned processes after inspection. A browser or AppTest result must describe
which path was actually exercised, never imply full industrial traversal.

## Verify the UI against that real API

With the owned API and ES running, use the locked dashboard interpreter:

```sh
/absolute/locked-dashboard-venv/bin/python -W error -m scripts.integration_dashboard_probe \
  --api-url http://127.0.0.1:18271 --run-dir /absolute/local-http-run \
  --output /absolute/new/dashboard-http.json
```

This uses Streamlit AppTest with real loopback HTTP. It verifies the earlier UTC
cutoff, advances the refresh state, then checks sensor values and exact event keys
on all four pages and the machine details modal. It does not exercise a browser
or wait for a browser's wall-clock timer. Outputs use exclusive creation.

Stop only the rehearsal's own ES, then repeat with a new output filename and
`--expect-unavailable ES`. Restart that same ES with its retained volume, wait for
readiness, and repeat the normal probe with another output filename. Finally stop
the own API and repeat with `--expect-unavailable API`. These outage probes require
degraded UI, no metric cards and an enabled refresh toggle. They do not themselves
stop/restart services. An ES recovery probe starts a new AppTest session; the
same-session refresh/recovery logic is separately covered by dashboard unit tests.

The two samples must remain inside the read window. This is a fresh-run rehearsal,
not an indefinitely replayable frozen-date UI fixture. See the dated result in
`docs/evidence/LOCAL_HTTP_20261103.md` for the scope actually exercised.
