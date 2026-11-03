# Bounded integration evidence, 2026-11-03

Current assembled source: `9aaeb8cb67401b84ce86c4118ac2fe6c5a1972f2`.
Previous complete suite: 798 tests + 374 subtests pass, 4 skipped.
After the final low-severity corrections, the 63 affected tests pass. Dashboard: 26 AppTests previously passed;
no UI application change in this follow-up. Current ZIP: `integration-final.zip`,
417 members, SHA-256 `dd56e56c0ebf51dcaa28e4f16f6ba5770a2e2aafc434ea6ac7c81e2263a38502`.
See `bundle-verification.json` for CRC/hash/restore results and source identity.
Full extraction verifies 23 local Docker COPY inputs, image inventory and refreshed
NiFi flow, then reproduces all 6 fixture scenarios. The restored CG14/scope suites pass 20 tests with 1 skip. No containers were started.
Image builds/scans/runtime/browser/SMB/human acceptance remain pending.

## Initial child snapshot (historical)

The following results and `fixture-result.json` describe the original child only.
Its ZIP verification is preserved as `bundle-verification-initial.json`.


Implementation tested: `75fb2f0345c52f4d769c05f334881a510e939c15`.
Fixture result records exact script hashes, contracts, synthetic model identity,
request accounting, sensor/event reconciliation and the current resource block.

- CPython 3.11.17, backend environment + repository vendored Kafka wheel.
- Read/replay/worker/automatic/new wiring suite: 78 passed, 50 subtests.
- New wiring + CG32 control/cleanup/load suite: 50 passed, 9 subtests.
- Final new wiring suite including sentinel tamper regressions: 9 passed.
- Ruff and git diff --check passed.
- Actual `docker compose config --format json` rendered/checked with dummy
  credentials inside the test; no daemon startup, images or services launched.
- One inherited Starlette TestClient deprecation warning; no suppressed failures.

The initial broader attempt lacked kafka in the backend-only environment (59
passed, 2 failed, 1 skipped). Installing the existing vendored wheel resolved this;
the subsequent broader run above had no failures or skips. No project dependency
file or parent dependency commit was changed/cherry-picked.

Archive on this shared host:
`/tmp/cnc-integration-75fb2f0-20261103.zip` (274 allowlisted members plus hash manifest).
SHA-256: `2b9e079dbfbe84922d2ce5244b86240326aff743752408933bda2e0abab48807`.
CRC, every member hash and fixture extraction/re-read passed. Restore source,
locked dependencies and vendored Kafka wheel are included, no private model.
Unpacked own fixture: `/tmp/cnc-integration-75fb2f0`.

Not established: real Docker/image endpoint/import/RSS acceptance, NiFi Python ABI,
real Filebeat/Kafka/ES/GET/UI traversal, browser four pages/modal, actual outage
recovery or SMB. The configured real runner and view command need parent execution
when resources permit. Resource snapshot here measured 1.412 GiB available RAM and
2.187 GiB free disk; minima remain 6/20 GiB. No cleanup/pruning or budget bypass.
