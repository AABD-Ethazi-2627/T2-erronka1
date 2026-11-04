# Trivy installer transport failure — PR119, 2026-11-04

On head `d7cfa18`, dependency run41798173890 failed API job126467169141 and
Kafka job126467169029. Both image builds succeeded. API also passed its offline
runtime probe. Both failed inside the pinned Trivy action's installation of
v0.76.1, before any scan, with curl exit6 (host resolution). Missing scan-artifact
upload errors followed that installation failure. They are not vulnerability-gate
results or evidence that either image is scanner-clean.

[API job](https://github.com/AABD-Ethazi-2627/T2-erronka1/actions/runs/41798173890/job/126467169141)
· [Kafka job](https://github.com/AABD-Ethazi-2627/T2-erronka1/actions/runs/41798173890/job/126467169029).
The exact pinned installer source at upstream commit75c4dc0 calls curl without
retry options, then checks HTTP status and downloaded SHA256 checksums. A later
HEAD request for the exact binary URL returned200. GitHub rejected immediate job
reruns with403 because the parent workflow was still running.

The workflow installs a job-local curl shim just before the pinned Trivy action.
It invokes `/usr/bin/curl` with three retries, including transport errors, two-second
backoff, a120-second retry budget,15-second connect timeout and90-second transfer
timeout. Original arguments, status output, HTTP handling and installer checksum
verification remain in force. Scanner version/action pins, all severities, report
coverage and the vulnerability gate remain unchanged. Persistent installation
failure still fails the job; no scan report is synthesized or skipped as success.

The actual curl binary/shim was tested against a loopback HTTP server returning
503 twice then200. Three requests occur; the downloaded file contains only the
final artifact bytes and stdout is exactly the HTTP200 status expected by the
upstream caller. Focused regression:16 tests and18 subtests pass. This verifies
retry behavior, not recovery of GitHub runner DNS; the new CI execution must
confirm the original path. Earlier raw/sanitized job logs and test output remain
under `/home/tears/.cache/cnc-integration-audit-20261103/`.
