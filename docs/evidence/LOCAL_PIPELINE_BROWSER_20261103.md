# Bounded local pipeline and browser evidence — 2026-11-03

The coordinator exercised real local services and Chromium with synthetic CSV
readings and an explicitly local test model. These results extend the earlier
[HTTP rehearsal](LOCAL_HTTP_20261103.md). They do not establish SMB access,
NiFi scheduling, final-image security closure, approved-model suitability or
human/teacher acceptance. The full CG32 resource guard remains unchanged.

## Executed scopes

| Scope | Verified outcome | Boundary |
| --- | --- | --- |
| HTTP/API/CG15/ES → Chromium | Four pages, details modal, six-month history, automatic refresh, pause/resume, desktop and mobile; same browser session shows degradation after ES stops and recovers after ES restarts | Synthetic samples; HTTP harness writes this series, not Kafka |
| Actual durable worker over stdin → API/CG15/ES/GET → Chromium | One completed job, one replay, one scoring request, stable event and exact KPI; canonical identity and sensor values match browser DOM | Synthetic source coordinates; no Kafka ACK |
| Actual Filebeat → Kafka → durable worker → API/CG15/ES/GET | Captured producer payload matches worker input; real worker commits offset 1 after consuming offset 0; subsequent staged replay keeps commit and KPI unchanged | Kafka event has not been checked in a browser; replay is stdin, not a broker redelivery |
| Filebeat OS target | Actual build passes, including `krb5-conf` update | Target removes Filebeat binary; previous permission failure was not reproduced and its historical cause remains unproven |
| Kafka candidate | Actual candidate image built, ran the broker used above and passed its image scan gate | This covers Kafka; other final images remain separate |

These are sequential bounded stages on the same host. They are not evidence that
the full simultaneous CG32/NiFi/Kibana stack fits the host's resources.

## Browser observations and fixes

Evidence root: `/home/tears/.cache/cnc-local-browser-20261103/`.
After two shared-preview timeouts, the coordinator used an isolated headless
Chromium session through `agent-browser`; no HTTP/API/DOM mocks were installed.
The initial wrapper launch failed, then `/usr/lib/chromium/chromium` with an
explicit headless configuration worked. These failures are not successful checks.

The coordinator observed an automatically updated 2003 RPM reading without a
refresh click. Opening details paused live reads; a later 2004 RPM sample remained
unseen while paused, then became visible after resuming. Browser work found and
fixed an overlapping header, clipped page content and mobile wrapping. The final
UI permits scrolling to the Abisuak cost controls at 390 × 844. Full canonical
identity is available in an expander; observation time and age remain visible.
The previous lost-click timer fix is retained. The final AppTest log reports
28 tests passing with `-W error` (`dashboard-final-tests.log`).

Selected artifacts (other intermediate or failed-click screenshots are retained
for diagnosis, not promoted as acceptance):

- `hasiera-live-2003.png`, `modal-verified.png`, `datuak-six-month.png`:
  live sample, details and six-month period.
- `abisuak-mobile-flow.png`, `abisuak-mobile-costs.png`: mobile layout and
  reachable lower controls after restoring vertical scrolling.
- `es-down-same-session.png`, `es-recovered-same-session.png`: actual ES stop
  and restart, with the same browser session left live.
- `canonical-identity-mobile.png`, `final-dom.json`: recovered Abisuak page;
  at `2026-11-03T10:11:07.252Z`, live=true, degraded=false, zero exceptions,
  visible canonical key and viewport 390 × 844.
- `console-including-restart.log` retains expected transport errors from
  intentional restarts. `console-normal-after-clear.log` and `console-final.log`
  are empty; this does not erase or negate the earlier errors.

The HTTP browser series ends at event key
`56eb72886ff0e30c03621c787c7a154878317a22765a2560afcc95caf7fcbb29`.
Its canonical data are in `live-2004-canonical.json` and `live-2004.json`.
The browser sequence spans several local UI commits; individual screenshots must
not all be attributed to the final HEAD. The earlier HTTP run-03 archive was
extended for these browser samples; its previously produced ZIP remains historical
and is not silently replaced by this expanded host directory.

## Durable-worker event checked in the browser

`/home/tears/.cache/cnc-local-worker-20261103/run-01/result.json` records clean
source `5b484c641535db8ce79876b467425c431e7c5e24`, real staged-stdin worker
execution and no service doubles. The original result correctly says browser
pending because the browser was checked afterwards. Separate evidence is in the
browser root: `worker-dom.json`, `worker-event-desktop.png` and
`worker-browser-reconciliation.json`.

The observed event key is
`72e4cdb23853b04db3bbb8d409570c5bf2bb33c752d1b1b26c6676602afa3f98`;
canonical bytes SHA-256 is
`5e7a1d6978d51679d8acc5b58ed6ed968d4fd68036aa06f84f4fcc4a5cebdf9c`.
DOM sensors match the canonical GET: process temperature 36.65 °C, ambient
27.35 °C, speed 1345 RPM, torque 62.7 Nm and tool wear 153 min. The same-event
verifier accepts the separate screenshot/DOM evidence. It is not the Kafka event.
See [LOCAL_WORKER.md](../integration/LOCAL_WORKER.md) for reproduction and limits.

## Filebeat producer and actual Kafka ACK

Producer evidence root: `/home/tears/.cache/cnc-local-ingress-20261103/`.
`state.json`, `filebeat.yml`, `input/sample.csv`, `filebeat.log`, `captured.json`
and `captured.bin` retain the own-topic setup, input, config and actual observation.
The producer is digest-pinned vendor Filebeat 9.5.5, not the unfinished patched
final Filebeat image. The broker uses built candidate image
`sha256:237c458201614df0f5430b95cdd30f2dc61016ea189720388fa87306c079ecd4`.
The source is an own local CSV directory. The unused SMB input points at an empty
own mount; no SMB connection is established by this rehearsal.

Filebeat's retained monitoring reports one published/acked output event. A reader
with auto-commit disabled captures one 72-byte message at partition 0, offset 0,
end offset 1 of `cnc-local-raw-11feee702228`. Its SHA-256 is
`e5bc9731a18463833d1c104e60c671a15796bd9b1f6c942546138770148333f9`.
This equals `broker-record.json.raw_sha256` in the worker evidence, linking the
producer capture to the actual consumed bytes rather than inferring provenance
from a CSV payload alone.

Worker evidence root:
`/home/tears/.cache/cnc-local-kafka-worker-20261103/run-02/`.
`result.json` records clean source
`5685f7a067d5cbb88d7512c56c84660b6e340ebb`, one completed Kafka delivery,
no rejects, `source_ack_verified=true`, and no doubles. The real group
`cnc-local-worker-e4f6278b69e942abbee2c1716c6f8f45` observes committed offset 1.
The staged replay reports one replay, `source_ack=false`, no additional scoring
request and an immutable ES create conflict; the broker commit remains 1.
The canonical event, committed CG15 prediction, ES, snapshot, history and exact
KPI reconcile. This establishes bounded at-least-once handling, not Kafka
transactional exactly-once delivery or a forced real broker redelivery.

Kafka event key:
`b15d917e906ffb8f7613c0d56ef80fde4dc80ad56824587345f3418f3698b31c`.
Canonical SHA-256:
`a1cc0c6d8de68461033714ce8fbaa7724e185dd2df89b7efc395b2f8e99bfbe6`.
The earlier run-01 retains its actual dirty-source flag; run-02 is the clean-source
repeat, not a relabelling of run-01. See [LOCAL_KAFKA.md](../integration/LOCAL_KAFKA.md).

Both worker stages use local test manifest SHA-256
`3a78dff85e705b57c5d5e11c84f5a020f797ed70b59f4486671152e71034e6f9`.
This is model identity, not an approved deployment or offline evaluation binding.

## Image evidence and outstanding gates

`/home/tears/.cache/cnc-filebeat-local-20261103/filebeat-os-result.json` records
successful OS-only image
`sha256:732818bc0e622778dda35991efdb54c6091ca9f4f3aeec28faf2d98b091ef1e5`;
`filebeat-os.log` and `kafka-build.log` retain the actual build output.
The previous Filebeat `krb5-conf: Permission denied` is not reproduced, rather
than being declared diagnosed or permanently repaired.

The same Kafka candidate passed Trivy scanning and
`enforce_image_scan.validate(expected_artifact="cnc-guard-local:kafka")`.
`/home/tears/.cache/cnc-local-images-20261103/kafka-scan.json` and
`kafka-gate.json` retain the scan and gate result (two analyzed targets, no gate
errors, image ID matching the broker candidate). `focused-tests.log` in that
directory records 51 passing focused runner/build tests.

API/dashboard builds are a separate ongoing coordinator step; this report does
not assert their completion. Use [LOCAL_IMAGE_BUILDS.md](../integration/LOCAL_IMAGE_BUILDS.md)
for serial builds with bounded Cargo jobs. Final builds/scans, constrained-image
runtime/RSS, full NiFi execution, Kibana panel reconciliation and the simultaneous
full-stack campaign still require their own evidence. SMB, approved model and
human/teacher gates remain open. No PR/push is part of this local evidence phase.

Selected artifact integrity, computed after capture (not a timestamped attestation
of every executed source byte):

| Artifact under cache root | SHA-256 |
| --- | --- |
| `cnc-local-browser-20261103/worker-event-desktop.png` | `5e9d838480134aaf7596686a49e232af9a022653bbe50e87ea5acc2fe9f16cfb` |
| `cnc-local-browser-20261103/worker-browser-reconciliation.json` | `66b7cc8b3e530b7aadf3c9991dcbce17355ae329462cdf21f99e747edcde911a` |
| `cnc-local-kafka-worker-20261103/run-02/result.json` | `b1612799409fc23dd00f1f045f991b8c3190d819e04bb181b49cc3189fda7ea8` |

Cache paths are local evidence locations, not claims that the source ZIP includes
these raw captures. A later evidence package must separately select and verify
them; the source bundle's existing fixture evidence remains a different artifact.
