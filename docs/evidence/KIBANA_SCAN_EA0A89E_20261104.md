# Kibana image scan after the Trivy transport repair

Run: [41804381933, job 126487658290](https://github.com/AABD-Ethazi-2627/T2-erronka1/actions/runs/41804381933/job/126487658290), source `ea0a89edf73c764a9a8827286f086de5d37d6b65`.

The image build, direct checksum-pinned Trivy installation and scan completed.
The vulnerability gate failed. This is a dependency finding, rather than the
earlier installer DNS failure.

Downloaded artifact `image-kibana/image-scan.json` has SHA-256
`226698dbec45f4a0c1d15cfb9cbf99f8a57f5a1017d41d2ab305941ee4d76937`.
The reported image ID is
`sha256:e2ebb960e8cd24afc60c48da1b390be99ed06dbc5d5b022215c27e50d62ac2fe`.

The complete Node inventory contains only `node-forge` 1.4.1. Its replacement
was already implemented and tested in the image, but the gate still required
the old 1.4.0 backport finding. The obsolete allowance is removed. In its place,
the gate requires the reviewed upstream 1.4.1 inventory; absent, old-only and
mixed inventories fail. The old vulnerability tuple is also rejected.

Applying the corrected gate to the actual artifact still fails with exactly:

| Finding | Package | Installed | Scanner fixed version |
| --- | --- | --- | --- |
| CVE-2026-118773 | glob | 10.5.0 | 14.0.2 |
| CVE-2026-118764 | minimatch | 10.2.4 | 11.0.1 |
| CVE-2026-118764 | minimatch | 9.0.9 | 11.0.1 |
| CVE-2026-118764 | minimatch | 3.1.5 | 11.0.1 |

The existing two verified `extract-zip` findings remain unchanged. There are
no new allowances for Glob or Minimatch. Their official fixes and consumer
compatibility require further work; an unsupported major replacement is not
established by this scan. The 3.x implementation lacks the preprocessing path
described by the Minimatch advisory, but this observation alone does not close
the finding or authorize a scanner exception.

Verification: `pytest -q tests/test_image_scan_gate.py tests/test_dependency_infra.py`
passes 15 tests and 21 subtests. Revalidating the downloaded report produces the
four failures above, with the upstream Forge inventory accepted. No new image
build, Kibana runtime acceptance, security exception or merge is claimed.
