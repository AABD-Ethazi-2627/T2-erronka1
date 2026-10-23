# Dependency Refresh Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Fix the approved dependency findings and deliver one PR with a complete, evidence-backed lock review.

**Architecture:** uv.lock remains the source of Python versions. The API uses a hashed runtime export; official container images use immutable digests. Independent API and scientific comparisons determine updates rather than a blanket upgrade.

**Tech Stack:** Python 3.11/3.12, uv 0.13.5, Docker Compose, GitHub Actions, PyPI and Trivy.

**Spec:** docs/superpowers/specs/2026-10-23-dependency-refresh.md

## Global Constraints

- Python >=3.11,<3.13; preserve the current-state model/data contract.
- Work only in the isolated B-taldea branch; preserve historical evidence.
- No main push, merge, deployment or existing-volume/service changes.
- Fail closed on audit errors, missing hashes or dependency-export drift.

## Review Focus

- Optional/marker-only/local wheel packages must not disappear from the audit.
- A failed or withdrawn advisory lookup must not be mistaken for a clean scan.
- API image resolution must match the lock, without optional research extras.
- A changed NiFi bundle must be importable with controller services disabled.
- Image updates must not imply safe in-place rollback of stateful data.

### Task 1: Select and lock compatible Python updates

**Files:** `pyproject.toml`, `uv.lock`, `scoring/requirements.txt`, `scripts/export_runtime.py`, `tests/test_dependency_runtime.py`, dependency review evidence.

**Interfaces:** Produces the `runtime` dependency group and deterministic `python -m scripts.export_runtime --check` command, consumed by the image and CI.

- [x] Compare candidate release metadata/notes and run numerical/API candidate checks in separate environments.
- [x] Add meaningful export-drift, complete-transitive and hash requirements tests; run them before implementing the export command.
- [x] Select compatible direct updates, regenerate the lock and hashed runtime export.
- [x] Run framework, columnar, model serialization and export checks. Expected: passing contracts or a documented reason to retain the scientific baseline.
- [x] Commit the selected Python/runtime changes and record evidence.

### Task 2: Update the active infrastructure and retire unsafe entry points

**Files:** `docker-compose.yml`, `deploy/cg14/compose.yaml`, `scoring/Dockerfile`, active NiFi export, relevant verification scripts, `docs/templates/infra/`, README and migration guidance.

**Interfaces:** Consumes Task 1's hashed runtime export; produces pinned official images and an explicitly disabled historical template.

- [x] Resolve published digests for Elastic 9.5.5, Kafka 4.3.1, NiFi 2.12.0 and Python 3.11.16 slim; record references.
- [x] Update images, active flow bundles and runtime build, preserving historical exports/evidence.
- [x] Make historical Compose require an explicit archival-use override; verify the default cannot start it.
- [x] Validate Compose paths and isolated image/flow/contract smokes. Expected: compatible new configuration, no use of existing state.
- [x] Commit infrastructure and documentation changes.

### Task 3: Prevent stale dependencies and publish the complete assessment

**Files:** `scripts/audit_dependencies.py`, `tests/test_dependency_audit.py`, `.github/workflows/`, `.github/dependabot.yml`, `docs/evidence/DEPENDENCY_REVIEW_20261023.md` and JSON evidence.

**Interfaces:** Consumes the selected lock and runtime export; produces fail-closed audit JSON and recurring validation without deployment.

- [x] Test active/withdrawn advisories, lookup failures, every source type and complete package coverage before implementing the auditor.
- [x] Implement bounded official PyPI queries, local-wheel provenance checks and CI tool inspection; fail on active advisories or incomplete results.
- [x] Update pinned CI tooling/actions and add PR/weekly audits, image scans and update proposals.
- [x] Write decisions for every original lock entry and each newly introduced package, with sources and measured limits.
- [x] Run auditor and workflow/export checks. Expected: no unresolved active advisories and complete coverage, or explicit external-image exceptions supported by provider applicability evidence.
- [x] Commit prevention and assessment.

### Task 4: Validate, review and publish one PR

**Files:** final evidence and PR description.

**Interfaces:** Consumes Tasks 1-3; produces one branch/PR with verified head SHA and precise validation limits.

- [x] Run frozen 3.11/3.12 suites, lint, immutable data audit, runtime export checks and applicable container smokes.
- [x] Obtain a fresh whole-branch review; fix important findings with focused regressions.
- [ ] Review the final diff, push this feature branch, create one PR against main and register it with T3.
- [ ] Report the PR, chosen versions, retained scientific packages and pending CI/operational checks.
