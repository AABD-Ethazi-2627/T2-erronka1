# Local image, archive and browser verification — 2026-11-03

This supplements the earlier [pipeline/browser report](LOCAL_PIPELINE_BROWSER_20261103.md).
The coordinator built and exercised the API and dashboard images against the real
local Elasticsearch service and the retained Filebeat/Kafka event. The model and
CSV are explicit local test inputs. No SMB, NiFi campaign, approved industrial
model, human acceptance or full simultaneous stack acceptance is inferred.

## Actual source and images

The archive selection change is committed at
`b5d5d545646ad3ba447be2312d9ae9c5b4d1b8e8`. Its API image contains the verified
scoring files and all three copied Python helpers, including the new read index.
The parent independently ran 130 focused tests and 126 subtests; Ruff passed.
An initial `pytest` executable invocation failed collection because the repository
root was absent from its import path; `python -m pytest` is the successful command.
After stopping the services, the full repository suite passed **894 tests and
374 subtests, with four skips** (59.59 s). The locked dashboard environment passed
**29 tests with `-W error`**. These are local results at the stated source head,
not CI or human acceptance.

| Image | Actual ID | Verification |
| --- | --- | --- |
| `cnc-guard-local:api-index` | `sha256:65071be5769f160f7bb6c00dd9e26993e8ae345aadff3759f4a7d76215a1c8ba` | Offline DuckDB/Arrow/HTTPX/JSON probe; serving HTTP below; Trivy gate passes, three targets |
| `cnc-guard-local:dashboard` | `sha256:ff6187e5f4a7e892ec896d27224c03db124a92a166330cd0df6ed26681b12bab` | Locked imports and actual Streamlit/browser session; Trivy gate passes, three targets |

Both ran as UID 65532 with read-only root filesystems, 512 MiB memory and swap
limits, `/tmp` bounded to 64 MiB, dropped capabilities and no-new-privileges.
The offline dependency probes used `network=none`. The HTTP/browser phase used
an internal Docker network and loopback-only host bridges. The API had only its
own response-ledger volume writable; model, config and archive mounts were read-only.
No source checkout or host virtualenv was mounted into either serving container.

The final resource snapshot reports API 190.6 MiB, dashboard 152.9 MiB and ES
611.3 MiB. These are one instant, not peak RSS or a concurrency/load benchmark.
Both serving containers stopped with exit 0 and `OOMKilled=false`; ES stopped
intentionally with exit 143 and `OOMKilled=false`. Volumes and evidence remain.

## Producer, committed archive and same-event verification

The documented [Filebeat runbook](../integration/LOCAL_FILEBEAT.md) was executed
in a new isolated namespace. Filebeat produced one 72-byte record at partition 0,
offset 0. Payload SHA-256:
`33067ff45c666c8cc5baab6778515d6e2b8cc341e553cb3f23fb6094cf95eecd`.
Run 03 used restored, hash-verified source `723ab6b29451578b27d7befdb4c8526310e6ae23`:
one completed worker job, broker commit 1, staged stdin replay without advancing
that commit, and exact KPI count 1. This is not forced broker redelivery.

The coordinator copied run 03's archive, migrated that copy with the explicit
offline read-index backfill, and verified that original object bytes and all
rows of `objects`, `events` and `deliveries` were unchanged. The original run
archive was not modified. GET never backfills or repairs storage.

The first image GET returned 503 because host-owned private 0600 bronze files
were unreadable by UID 65532. The rehearsal was corrected by copying the same
bytes into a private volume owned by that image user, mounted read-only to serve.
Original file permissions were preserved. The CG32 Compose already runs its
API and writer as UID 1000; this rehearsal's default image user differs.

The serving image then returned HTTP 200 for health, snapshot, history, periods,
KPI and evaluation. Evaluation correctly returned `available=false`. A `/predict`
replay against the copied canonical response ledger returned byte-identical output.
An initial verification script used the wrong periods URL and got 404; the actual
route `/api/historikoa/CNC-004/periodoak` passed. Both attempt logs are retained.

The same canonical event was checked in POST replay, ES, migrated CG15, snapshot,
history and browser text:

- Event ID: `b872e51a8980ba9623fe8f83d5152becbc286ce09d5f8103fbaf28ff347e9e93`.
- Event key: `cf2431835bd7bf3c426ba8f0097ec0371a2820bcd1f02b36a015ece321185745`.
- Canonical SHA-256: `11e1d51b8acf81cb89405a23caa2032e7e76d8d7b8bb32381cbb30bca91cf7fb`.
- Local test model manifest SHA-256: `3a78dff85e705b57c5d5e11c84f5a020f797ed70b59f4486671152e71034e6f9`.

## Browser and failure boundaries

An isolated Chromium session visited `http://127.0.0.1:18501`, the real dashboard
image, at 1400 × 1000 and 390 × 844. It exercised Hasiera, Makinak, its details
dialog, Datuak with six-month selection, and Abisuak. Desktop DOM extraction
retains the actual event ID and key, rather than only booleans asserting presence.
The modal showed 36.65 °C process temperature, 27.35 °C air temperature, 1345 RPM,
62.7 Nm and 153 minutes of tool wear. Mobile document width was 390 with no
horizontal overflow; inspected pages had no Streamlit exceptions.

The real timer advanced the displayed query cut from `2026-11-03T12:10:13.681046Z`
to `2026-11-03T12:10:24.130836Z` without a refresh click. No new telemetry was
published during this browser run. The earlier report separately records live
sample changes and ES outage/recovery; those are not relabelled as this image run.
Off-screen controls required scrolling into view before clicking. The retained
`machine-modal.png` is an unsuccessful early click; `modal-visible.png` is the
successful dialog capture. The browser was closed after verification.

A separate run stopped the real Kafka broker after its worker completed. The
observer raised `KafkaConnectionError`, retained a failed result and shut down
its API. About 10.94 seconds between broker exit and result-file modification is
wall-clock evidence of prompt failure, not a monotonic timeout measurement.
The injection script expected `KafkaTimeoutError`, so its final assertions did
not execute. `source_ack_verified=false` means unverified, not absent ACK.

## Evidence locations and remaining work

- `/home/tears/.cache/cnc-local-container-integration-20261103/`: exact preparation
  and correction scripts/commands, migration, HTTP bodies, image source hashes,
  browser DOM/screenshots, runtime identities, logs and shutdown state.
- `/home/tears/.cache/cnc-local-images-20261103/`: actual build logs, runtime probes,
  image scans and gates; API baseline evidence is retained separately.
- `/home/tears/.cache/cnc-ingress-VFYbx1/`: executed Filebeat runbook and captured record.
- `/home/tears/.cache/cnc-local-kafka-worker-20261103/run-03/`: successful frozen-source
  broker worker run. `run-04-broker-timeout/` and `BROKER_FAILURE_20261103.*` retain
  the failed observer experiment without changing its outcome.

The first Claude archive-index review was killed for memory exhaustion; a bounded
recheck initially hit the provider's API rate limit. That recheck subsequently
resumed and completed: no blocking correctness findings in `b5d5d54` versus
`723ab6b`. It inspected five source files, including only test names, and executed
no tests, builds, services or network operations. It did not inspect journal-mode
behavior or the contract/platform helper implementations. The report is retained
at `/home/tears/.cache/cnc-integration-audit-20261103/CLAUDE_ARCHIVE_INDEX_RECHECK.md`.
Its two observations are documented: accepted duplicate deliveries can complete
legacy index coverage, and direct ledger/trigger SQL writes remain trusted.
This code review does not independently repeat the parent's runtime evidence or
approve unrelated changes. Previous reviews remain scoped to their exact heads.
Complete ES consumer compatibility, NiFi/Kibana candidate image closure, NiFi execution, full-stack
capacity, sustained rates, SMB and human acceptance remain separate gates. The
full CG32 minimum of 6 GiB available RAM and 20 GiB free disk is unchanged.
No push or PR belongs to this local verification phase.

## Subsequent serial checks: Elasticsearch and TLS

The Elasticsearch candidate built successfully in 60 seconds from the cached
Maven stages. Image ID:
`sha256:ca84bbcccce962ff8507db208865935e2330fce800e6264a82345e02cd80d6a0`.
Its normal image gate passes with 74 installed OS packages and 952 JAR package
records. Trivy warned about 144 mismatched PURL references. A separate comparison
confirmed that all 74 installed APK names, versions and origins are present in the
report; the filtered references are duplicate SBOM metadata, not missing installs.
Because the image identifies Chainguard while its repository is Wolfi, an additional
OS-only scan explicitly used `--distro wolfi/20230201` on the same immutable image.
Both advisory feeds reported zero vulnerabilities. The OS-only complement is not
passed off as a complete JAR scan or used to bypass the normal gate.

Both scans reused the vulnerability DB updated `2026-11-03T01:30:30Z` and the Java
artifact-identification index updated `2026-10-26T00:59:12Z`. Their metadata and
report hashes are retained in `elasticsearch-scan-union.json`. This is not a claim
that a fresh Java index was downloaded during this phase.

Three runtime attempts remain distinguishable:

1. A `network=none` harness omitted an explicit hostname mapping and ES exited
   before startup. Its logs/result are retained.
2. With the hostname mapped to loopback, ES started and installed the real ingest
   pipeline and mapping template, but index creation timed out. Its logs show the
   disk flood-stage protection at 95%: the host had about 6 GiB free, only 2.5%.
   No disk threshold or allocation protection was reduced or disabled.
3. A new isolated container used a bounded **256 MiB volatile tmpfs** for its own
   data and a 1 GiB memory limit. Twelve operations passed: current pipeline and
   template installation, retained canonical-event create/read, replay 409, three
   invalid-document rejections even with `pipeline=_none`, exact count, ES|QL count
   and cluster-health request. It then stopped without OOM. This verifies the
   exercised compatibility path, not disk durability, throughput, full-stack
   capacity or all patched Parquet/Iceberg/GCS/APM consumers.

Artifacts are `elasticsearch-build-serial.*`, `elasticsearch-runtime*.{json,log}`,
the exact `probe_es_candidate*.py` scripts, both scans and `es-os-coverage-*` in
the image evidence directory. The previous API/browser run used the pinned vendor
ES image; it is not relabelled as this candidate's end-to-end run.

The existing opt-in TLS test was repeated with the cached pinned HAProxy image:
`CNC_RUN_LAN_TLS_TESTS=1 .venv/bin/python -m pytest tests/test_lan_ca_rotation.py -q`.
It passed **one test and 60 subtests in 7.66 seconds**, checking the generated test
CA rotation across all frontends and retiring old clients/sessions. Certificates
were synthetic and isolated; no production certificate changed. This successful
repeat does not diagnose the earlier startup/cleanup failure. The retained log is
`lan-rotation-retry.log` in the image evidence directory.

## Final Filebeat candidate

The final image built in 549 seconds with `GO_BUILD_JOBS=1`, from the reviewed
Dockerfile at `fedde9ab06ccc50b59a2be50631b0d7fb74728d1`, retaining the pinned
Beats source and Go toolchain. Image ID:
`sha256:86fc7b9e3f573b3fe2c9963e70f314873b7e8fc4c79369431ad20ff3e81eda5a`.
Its actual binary reports Filebeat/libbeat 9.5.5. A single compiler process was
observed above 2 GiB RSS; one job limits parallelism, not peak memory.

The existing image gate passes with OS and Go-binary coverage. Trivy still reports
the specifically allowlisted module finding `GO-2026-5932` in `golang.org/x/crypto`
v0.58.0; it has not been silently removed or described as patched. The exact binary
was extracted and checked by the workflow's pinned
`golang.org/x/vuln/cmd/govulncheck@v1.9.0 -mode=binary`, using the pinned Go image.
The tool exited 0: zero reachable vulnerabilities and one module-only finding.
Binary SHA-256:
`430e6ae01e65ea07157d2626cad7362ad4f5158a93c440dee2b2e8d55bf4aad5`.

The Filebeat runbook was executed again in a fresh isolated namespace with only
the vendor producer image replaced by this immutable candidate. Its registry and
Kafka data were new. The actual captured record was partition 0, offset 0, end 1,
72 bytes; payload SHA-256:
`6d908aaec1191c9783a4682741d0864f20e0786793abc0dbcb92b57205af766e`.
The payload and field-aware fingerprint/offset key matched the expected CSV.
Filebeat's final monitoring recorded one output event, one ACK and zero failures.
Both owned containers and their loopback bridge were stopped; data were retained.

This producer-only stage does not repeat the worker/model/browser chain for the
new event. The earlier contiguous run used vendor Filebeat and its distinct event;
component checks must not be concatenated into a fabricated single final-image
campaign. Evidence is in `final-filebeat-*`, `filebeat-final-*` and
`filebeat-build-serial.*` under the image evidence directory, plus
`/home/tears/.cache/cnc-ingress-gnGuKF/`. The exact executed shell blocks are saved.

The API runtime preflight now imports the archive reader/index helpers as well as
probing DuckDB/JSON/Arrow. That actual image probe and 11 wiring tests passed.
