# Wave 1B integration handoff

Base: `c34cabe0c851ba4b7688e1a3a4448d9898002f1e`.
Presentation source inspected: `04d1bb12f0c0c156457ac346ced9385971e17a1a`.
Only dashboard paths changed; no backend, manifests, author branch, SMB or shared services.

## Reconciliation

Imported the collaborator stylesheet and Hasiera fragment composition. Retained the
main app's configuration, selection, theme, navigation and explicit modes; adapted
the searchable/filterable image gallery and details modal to source-preserving
readings. Replaced generated history, fabricated health, 3-class evaluation and
probability-weighted costs with the canonical readers and explicit scenarios.
The image gallery retains decorative images, labelled illustrations, not evidence
of physical machine identity/location. The selector lays out actual rows only.

## Interfaces for Wave 1A

- `LANEKI_MODE=demo` never calls HTTP. `api` calls `LANEKI_API_URL`, default
  `http://127.0.0.1:8001/api`; cache key includes the URL. The standalone `main.py`
  remains the legacy demo server, not the canonical reader. Use the configured
  scoring API URL when assembling the application.
- `GET /makinak`: actual list 0..50, unique `CNC-[0-9]{3}` with positive numeric
  suffix matching `zenbakia`. Core sensors can be null; no finite values are
  rounded/rewritten. All extra provenance/identity fields survive validation.
- `GET /kpis`: display the complete returned object, including coverage, window,
  denominators, age and scope. The compact cards explicitly summarize the local
  snapshot, not physical operation. Missing KPI transport is explicitly degraded.
- `GET /historikoa/{id}`: `datuak` column arrays of equal length, `metadata` object,
  optional opaque `next_cursor`; extra identity columns are retained. Exact columns
  are in `read_contracts.COLUMNS`. Full UTC timestamps required; nulls preserved.
  Next-page requests URL-encode `cursor`. First-page warning prevents implying a
  complete window. No client aggregation of truncated pages.
- `GET /historikoa/{id}/periodoak`: `astea`, `hilabetea`, `sei_hilabete`, each with
  the same `datuak`/`metadata` container. All metadata (coverage/n/bounds/reference
  identity) is displayed, without invented buckets. Backend must label prediction
  record scope and supply verified counts/coverage.
- `GET /model-evaluation`: fail closed unless `available=true`, model version/hash
  match the selected source record, partition/scope/provenance/decision_rule exist,
  threshold is finite in [0,1], labels are [0,1], matrix is nonnegative integer 2x2.
  Backend owns verification of artifact-to-served-model linkage; the client never
  loads the offline artifact or sealed research. Return `available=false` when
  linkage is unavailable. Matrix denominators/metrics are recalculated locally;
  zero denominator produces unavailable, not perfect metrics. Rule and threshold
  are displayed separately from 0.15/0.70 presentation alerts.

The frontend displays raw provenance JSON plus event_id, event_key, timestamp,
scored_at, as_of, age_seconds, prediction_scope and score_semantics when supplied.
It does not derive canonical event_key or invent observation freshness. A missing
field is explicitly unavailable. Composite identity remains available in JSON.
No new runtime dependency is introduced.

## Verification and remaining gates

Python 3.12 locked dashboard environment:

```sh
python -W error -m unittest discover -s dashboard_laneki -p 'test_*.py'
ruff check dashboard_laneki
git diff --check
```

25 tests passed: the original four AppTest regressions, seven original domain
checks (updated empty/location expectations), seven new contract tests and seven
new AppTest cases. Sentinel assertions examine displayed metric values and source
state across all four pages and modal. Tests cover nulls, empty/partial/duplicate/
NaN snapshots, custom API port, provenance, malformed/missing/incompatible binary
evaluation, denominator zero, six-month selection, partial pagination and explicit
cost inputs. Statement tests reject misleading phrases but allow truthful negative
explanations about forecasting. Fixtures are declared, not industrial observations.

These are local fixture/AppTest checks. Browser rendering, keyboard/mobile layout,
real API/ES/CG15 alignment and cross-layer same-event reconciliation remain parent
integration gates; no visual/browser or live pipeline acceptance is claimed here.

## Local live refresh follow-up

Remote rechecked: `origin/feat/dashboard` still points to
`04d1bb12f0c0c156457ac346ced9385971e17a1a`; stylesheet is identical. The collaborator's
presentation was selectively reconciled with canonical current-state semantics.

API mode now enables a Streamlit timer fragment every five seconds. It renews the
shared UTC cutoff and cached reads, invalidates historical pagination, and reruns
the page. Polling is registered before empty/error stops to allow automatic recovery.
The live toggle pauses the timer's reads for inspecting history/details; manual
refresh remains available. This is best-effort periodic HTTP polling while the
session is active, not a five-second ingestion SLA or websocket delivery. Long
queries may delay refresh. Observation time, cutoff and data age remain visible.

Local AppTest verifies changed sensor values, pause, empty source and outage/recovery.
Browser timer behavior and complete live pipeline latency still require acceptance.
Work after this follow-up is local-first; no new push/PR is part of this phase.
