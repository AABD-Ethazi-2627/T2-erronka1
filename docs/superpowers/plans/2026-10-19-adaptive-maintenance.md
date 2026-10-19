# Adaptive maintenance learning Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans to implement this plan task-by-task in the existing isolated CG17 branch. Do not delegate or create other conversations.

**Goal:** Start a dataset-portable, measurable feedback loop for sensor forecasting; retain the unfulfilled maintenance-time objective explicitly.

**Architecture:** Dataset manifest maps source columns to canonical asset/time/lifecycle/sensors and declares units, provenance, and timestamp meaning. A causal evaluator forecasts the next observation before seeing it, scores predictions against persistence, then updates candidate models. A later shadow registry records candidate selection without deploying models.

**Tech Stack:** Existing Python3.11, numpy/pandas; no new dependencies or background services.

**Spec:** This plan plus docs/evidence/CG17_MAINTENANCE_PLANNER.md (user correction: no invented maintenance deadlines).

## Global constraints

- Timestamp alone is insufficient: physical identity, chronology, sampling and fault onset/censoring determine supported objectives.
- No AI4I timestamps invented; SMB replay never promoted as industrial degradation evidence.
- Dataset changes create new dataset/schema identities. Do not mix histories or compare errors across different units/sensors/horizons.
- Event timestamp must mean observation time, not ingestion time. Respect component/lifecycle boundaries and maintenance resets.
- Models may learn subsequent sensor values without fault labels. Maintenance effectiveness/RUL needs confirmed events and future follow-up.
- Train after evaluating each target; never learn from own predictions as truth.
- Frozen untouched future/asset acceptance data required before promoting a tuned temporal candidate. Progressive exploratory metrics are not that final test.
- No source-code self-rewrite, physical actions, automatic API promotion, calendar sending, issue closure or rubric completion.

## Phases and deliverables

### Phase1 — portable contract and causal evaluator (implement now)
- [x] Test missing/naive timestamp, invalid units/provenance, conflicts, lifecycle isolation and data leakage.
- [x] Implement planning/adaptive.py: strict manifest mapping, chronological per-lifecycle pairs, next-observation persistence and online drift candidates.
- [x] Score with actual elapsed minutes, cap gaps, forecast before target observation, update only after scoring. Metrics per sensor in declared units, paired same observations, warmup excluded.
- [x] Report per-asset counts/gaps, candidate MAE vs persistence, prediction records and selection status. No automatic promotion or ETA.
- [x] CLI reads CSV+manifest and writes new immutable report directory with input/config hashes and evaluation settings.
- [x] Verify reorder invariance, perturb-future causality, resets, repeated-state diagnostics (not replay certification), irregular sampling and known synthetic drift. Commit/push current CG17 PR.

### Phase2 — shadow candidate registry (after Phase1)
Versioned artifacts/config/code hash; minimum evaluation size and paired temporal blocks;
confidence intervals, horizon-specific error, catastrophic regression checks and rollback.
Search learning rates/windows on earlier intervals only; freeze selected candidate before
future/asset acceptance. Human operational capacity remains separate from predicted urgency.

### Phase3 — mechanism forecasts and maintenance proposal
AI4I mechanism margins only for an explicitly AI4I-compatible schema. For a new dataset,
use documented asset-specific limits or learn horizons from confirmed events. Forecast
joint sensor trajectories, uncertainty and first threshold crossing; distinguish crossing
from failure ETA. Validate lead time, false alerts per asset-day and missed events, plus
censoring and maintenance interventions. Avoid extrapolating observed random-walk risk
as monotonic wear. No claims of optimal intervention without outcome/cost evidence.

### Phase4 — continual operation
Only trustworthy new observations enter delayed labels; dedup/replay and identity guards.
Scheduled shadow training, drift monitoring, user-reviewed promotion/rollback and audit.
No promises of monotonically improving performance. Self-improvement means measured
candidate replacement, not unrestricted autonomous code modification.

## Dataset replacement checklist
Source/license/hash; column mapping and units; stable physical asset and component IDs;
observation timestamp timezone, sampling cadence/gaps; lifecycle/repair/reset markers;
fault onset and follow-up horizon; censored runs; chronological/asset partitions.
Missing fields disable unsupported targets; no silent fabrication or unit conversion.

## Review focus
Conflicting same-time samples, mixed machines/components, oversized observation gaps,
source-reported timestamp provenance vs actual evidence, future leakage in drift updates,
reset handling, false improvement on replay, selection bias, negative/zero target scale.

## Phase1 verification outcome

76 tests pass, including10 adaptive tests; Ruff check/format on4 new Python files.
Independent review found cwd-relative hashing and duplicate CSV-header ambiguity;
both reproduced RED, fixed and covered GREEN. Current AI4I temporal objective refuses
missing fields. Phases2–4 remain planned, not implemented. No runtime model changed.
