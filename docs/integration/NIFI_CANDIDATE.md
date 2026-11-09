# Opt-in NiFi candidate assembly

This is a local candidate procedure. It does not approve runtime, deployment,
SMB, CG32, the model, an exception or a merge. Preserve all originals and prior
outputs. The full lab still requires at least 6 GiB available RAM and 20 GiB disk.
Use adequately resourced authorized machinery before attempting the image build.

The current private proof is under
`/home/tears/.cache/cnc-combined-candidate-20261105-01`.
It combines 22 exact leaf replacements into 16 rewritten NARs. Never copy
independent family overlays over each other: four NARs share the library groups.

1. Reproduce the wrapper/Hadoop artifacts using their pinned preparation scripts.
   Stock source must match all 215 acquired archives. `map_candidates.py` accepts
   explicit `--hadoop-candidate`, `--hazelcast-candidate` and `--parquet-candidate`
   paths, checks their exact hashes, and still produces unapproved metadata.
2. `emit_plan.py --families ... --review-record ...` requires a record tied to
   that exact candidate file and selected families. Its reference must explicitly
   identify bounded candidate assembly when runtime is not approved. Hadoop and
   all nine Snappy replacements must be selected together.
3. Apply the single plan using `scripts/patch_nested_jars.py SOURCE --plan PLAN
   --output FRESH_OVERLAY --apply`. It snapshots and verifies every source and
   replacement, preserves unrelated siblings, and publishes with no replacement.
4. Prepare the image context outside the repository and inputs:

```sh
python3 scripts/nifi_candidate_context.py prepare \
  --source ORIGINAL_STOCK_ROOT --overlay FRESH_OVERLAY \
  --inventory INVENTORY_JSON --candidate CANDIDATE_JSON \
  --plan PLAN_JSON --review REVIEW_JSON --context FRESH_IMAGE_CONTEXT
```

The context has five JSON metadata files plus exactly the changed archive paths
under `payload/`. It contains public dependency code, not operator archives,
credentials, models or private telemetry. Verification pins the canonical stock
inventory, library-root bytes, review/candidate/plan identity, all occurrences,
coupled hashes, payloads, sibling contents/metadata and the exact changed leaves.
The context and writer share one policy validator. The context also freezes
the six exact replacement families and occurrence counts in code and requires
the complete 22-target profile, rather than trusting a locally written review
JSON to authorize arbitrary or partial replacements. Candidate/inventory identity
must also match. The tests fix all six literal profiles, the coupled Hadoop/Snappy
pins and all three blocked inputs, and exercise sibling-content corruption. Its
CLI wall deadline is 180 seconds. See the [bounded guard verification](../evidence/NIFI_GUARD_CORRECTIONS_20261105.md).
The existing four bootstrap/toolkit Jackson updates are the only accepted base
deviation. Unknown archives or a different base fail closed before layer mutation.

On adequately resourced machinery, use BuildKit's named context explicitly:

```sh
docker buildx build --load --pull=false -f deploy/images/nifi.Dockerfile \
  --build-context nifi_candidate_overlay=/ABS/FRESH_IMAGE_CONTEXT \
  --target candidate-runtime -t cnc-guard-audit:nifi .
trivy image --image-src docker --parallel 1 --scanners vuln --format json \
  --list-all-pkgs --output FRESH_IMAGE_SCAN.json cnc-guard-audit:nifi
python3 scripts/enforce_image_scan.py nifi FRESH_IMAGE_SCAN.json

docker buildx build --load --pull=false -f deploy/images/nifi.Dockerfile \
  --build-context nifi_candidate_overlay=/ABS/FRESH_IMAGE_CONTEXT \
  --target candidate-archive-audit -t cnc-guard-audit:nifi-archives .
trivy image --image-src docker --parallel 1 --scanners vuln --format json \
  --list-all-pkgs --output FRESH_NESTED_SCAN.json cnc-guard-audit:nifi-archives
python3 scripts/enforce_image_scan.py nifi-archives FRESH_NESTED_SCAN.json
```

These build/scan commands are future steps, not executed evidence. Retain any
previous image IDs before retagging. The default `final` target does not install
the experimental overlay. Neither a frontend `--check`, a source bundle, a
fixture nor a flat-classpath probe constitutes image or real NAR acceptance.
Compare actual fresh scan tuples and test real classloader/service behavior
before considering promotion. No scanner policy changes are part of this flow.


## Post-review source and limits

The [Benten shared-policy review](../evidence/CLAUDE_NIFI_SHARED_POLICY_BENTEN_RECHECK_20261105.md)
covers `a098a86`, not the later changes. Correction `caec8a9` moves the inherited
scope ambiguity check before scope exclusion, rejects inherited managed keys
whose interpolation changes in the child, and rejects required type/classifier
properties. The Jackson support lock is updated with the same source change.
These are fixes for reproduced forms within a bounded Maven subset; they do not
prove a complete Maven model or justify a new family/re-pin without review.

Post-review scratch tests pass 122 tests and 71 subtests on each Python 3.11/3.12.
The source was bound to the committed correction after execution; that observation
is not a contemporaneous immutable-run certificate. Offline Maven checks give
9 equal/9 rejected for the earlier 18 rows, 11 equal/4 rejected for the new 15 and
13 rejected for the other 13. Four rows overlap between the two new drivers.
All eight frozen Jackson closures and 13 RabbitMQ 5.37.0 coordinates match;
RabbitMQ 5.35.0 fails closed on its unpinned old Netty POM. The first driver failed
because its harness expected a missing TALLY line; that failure is retained.

The original 22-target context and overlay bytes remain frozen. P1, actual
`verify`/`install` with the latest guard against the real image tree, remains
pending. A base pull, including its intentionally interrupted attempt, is not
an installed candidate, image build, scan or NAR/classloader acceptance. Last
attributed nested CI remains 59 distinct tuples/63 records. Do not infer a new
scan count from the replacement plan. See the [coordinator record](../evidence/INTEGRATION_CANDIDATES_20261105.json)
for exact source/artifact bindings and later phase results.
