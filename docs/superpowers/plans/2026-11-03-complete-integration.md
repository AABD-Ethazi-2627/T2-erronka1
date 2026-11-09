# Complete integration implementation plan

> For agentic workers: implement assigned tasks with focused tests and commits. Parent coordinates independent isolated worktrees and Claude reviews; children do not delegate.

Goal: integrate the pending dashboard and canonical read paths, resolve CI/dependency blockers, verify the assembled lab and map evidence to all 40 rubric descriptors.
Architecture: preserve the scoring write contract and canonical ledger. Add opt-in typed GET routes backed by explicit ES scope and committed CG15 Parquet. Dashboard retains its new presentation while preserving real/null/degraded/demo provenance. A dedicated opt-in lab configuration joins existing components and a reproducible fixture acquisition replaces only SMB.
Tech stack: existing Python 3.11/3.12, FastAPI/Pydantic, DuckDB 2.0, PyArrow, Streamlit, Kafka/NiFi/Filebeat/ES/Kibana and uv lock.
Spec: GitHub issues #104–#111, https://github.com/AABD-Ethazi-2627/T2-erronka1/issues/104 and linked subissues. User authorized execution and subagents after the integration audit; no further plan approval needed.

## Constraints

AI4I_CURRENT_STATE_ONLY; temporal_prediction_enabled=false; uncalibrated_current_state_score. No future probability, ETA/RUL, fabricated health/sensors/history/evaluation. No modification of sealed research, raw sources or collaborator dashboard branch. Preserve dirty parent and infrastructure worktree. New PR branches, no force push. Source URI/model hash/policy explicit and shared across current/history/evaluation. No new files in contracts/*.schema.json. No production/OT/SMB server mutation or destructive cleanup.

## Review focus

- Partial/empty/invalid/duplicate snapshots and nullable readings: UI tests, no demo fallback.
- Cross-model/source/policy contamination and time boundary/tie handling: backend tests with UTC/cursors/limit overflow.
- Uncommitted/orphaned/corrupt archive and immutable reads: ledger/hash validation and SQL/path tests.
- Absent/unverified evaluation identity: available=false, never synthetic matrix or threshold-derived forecast.
- Same-event replay/HTTP uncertainty and required downstream failures: integrated event accounting, no premature ACK.

## Wave 1A — backend (#106, #107, backend #108)

Owner: backend child. Files: scoring read models/router/readers/projection modules, create_app hook, focused tests, backend contract docs. Do not edit dashboard or dependency manifests yet; report runtime additions for Wave 2.
Interfaces: exact GET URLs and field names in issues. /api/makinak list; /api/kpis metadata; /api/historikoa/{id} container datuak, metadata, next_cursor; /periodoak keys astea, hilabetea, sei_hilabete; /api/model-evaluation identity-verified offline payload. Keep storage injection testable, source selection explicit.
- [ ] Reproduce missing GET behavior and add acceptance regressions.
- [ ] Implement current snapshot and KPI with stable scope/time/identity semantics.
- [ ] Implement committed read-only Parquet history and UTC period aggregations/cursors.
- [ ] Implement verified offline evaluation and unavailable behavior.
- [ ] Run focused tests and existing scoring/replay regressions; commit and return SHA/interface/runtime requirements.

## Wave 1B — dashboard (#105, frontend #108, consumer #107)

Owner: dashboard child. Files: dashboard_laneki only plus scoped documentation. Reconcile six changed files from origin/feat/dashboard into own worktree, retaining improvements with main invariants. Do not overwrite collaborator branch or backend code.
Interfaces: consume Wave 1A issue-defined API contract, LANEKI configuration using existing LANEKI_MODE/LANEKI_API_URL names, never infer from presentation ids.
- [ ] Pin existing four AppTest regressions plus empty/single/duplicate/NaN/null/sentinel scenarios.
- [ ] Reconcile new pages/CSS and provenance-aware selection/modal.
- [ ] Consume history containers/period coverage and binary evaluation, display unavailable inputs honestly.
- [ ] Test all four pages/modal and costs as explicit scenarios; commit and return SHA.

## Wave 1C — Claude independent rubric/design audit

Owner: Claude reviewer, read-only. Read source rubric descriptors, current evidence and issue contracts. Deliver an actionable criterion-to-evidence matrix, likely integration hazards and missing acceptance gates. Do not implement or claim grade/acceptance. Later a new Claude task reviews actual final diffs.

## Wave 2 — dependencies and assembly (#109)

Parent coordinates after Wave 1 completions. Separate dependency worker starts when slot frees. Recover only relevant unpublished infra fixes after comparing them with main. Inspect all #112–#118; fix runtime exports and actual image closure, build/scan/runtime verify rather than suppress scan findings. Keep changes independently reviewable.
Assemble API+UI commits on an integration branch, add effective runtime packages/hashed exports and opt-in lab wiring. Tests reject hostname/port/index/mount/dependency/manifest mismatch. Preserve TLS, loopback and single offset ownership.

## Wave 3 — integration and quality (#110)

Run local normal/invalid/replay-uncertain/API-down/ES-down/corruption scenarios. Reconcile same event across Filebeat/Kafka/worker/API/CG15/ES/GET/UI with explicit identities and all doubles stated. Test real own lab when resources allow; no shared disruption. Browser inspection of pages/modal separate from AppTest. Create portable evidence ZIP, verify CRC/hash/sample restore. New Claude full-diff review; fix small findings directly and request a fresh delegated re-review if needed.

## Delivery and external gates

Push own branches, link each PR immediately, run CI and integrate normally when checks/review permit. If waiting on PR use watch and yield. Never bypass protection or fabricate review. Update traceable rubric/evidence state. #111 requires actual authorized lab/SMB access and new batch; human defense/teacher acceptance remain explicit until observed. Aim for all advanced rubric descriptors, never promise a grade.
