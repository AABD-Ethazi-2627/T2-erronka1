# Dependency maintenance for B-taldea

The user requests one pull request that fixes the 23 October dependency audit
and evaluates every entry of `uv.lock`, including transitive and optional
packages. Newer does not automatically mean better for this workload.

The approved maintenance scope is:

- Remove the vulnerable uv 0.13.1 CI pin; use 0.13.5 (fixed since 0.13.4).
- Move the active Elastic services to 9.5.5 with verified image digests.
- Converge the main lab with Kafka 4.3.1 and official NiFi 2.12.0; pin
  their images and adapt the active NiFi export while preserving old evidence.
- Export the API's complete runtime from the canonical uv lock, with hashes;
  use a pinned Python 3.11 image and reject an obsolete runtime export.
- Audit all locked Python versions, including development/research, in PRs
  and on a weekly schedule. Automate update proposals without auto-merge or
  deployments. Scan the actual API image and declared infrastructure images.
- Record each original lock entry, latest observed version, Python support,
  benefit, compatibility risk and update/retain decision with primary sources.
- Test API updates separately from the numerical/ML stack. Promote newer
  numerical packages only if compatibility and a material workload benefit are
  demonstrated; otherwise record a concrete reason and migration conditions.
- Retain the historical template as explicitly non-deployable history. It must
  not offer an accidental second entry point to vulnerable services.

Constraints: Python >=3.11,<3.13; six AI4I current-state features; approved
8,000-row source unchanged; the old inspected 1,200-row test is excluded.
No ETA/RUL/forecasting, new training sources, operational model replacement,
shared-volume migration, service interruption, merge or deployment.
Tests may start isolated containers with fresh storage and loopback ports.

Acceptance: reproducible frozen installations on Python 3.11/3.12, full unit
and relevant contract checks, deterministic runtime export, reviewed dependency
decisions for every original lock entry, static Compose/workflow checks and
honest separation of local tests, container evidence and CI status. Preserve
the dirty parent checkout. Deliver one reviewable PR against `main`.
