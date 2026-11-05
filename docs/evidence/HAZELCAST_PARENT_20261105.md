# Parent verification of the Hazelcast candidate

Status: **locally reproduced preparation; independent QA and runtime gates pending**.
No runtime plan, image, security exception, merge or external acceptance is approved.

Child `f5fadedd` was incorporated as `0a45aaa`. Before changing its executable
sources, the parent reproduced its JAR SHA-256 `73e56b7bb0565be3feeaaec611e8290f527b15ff97229de40e1e59ae40faabc0`
and verified all 88 recorded child artifact hashes. The parent then removed
three unused imports and one unused assignment in `6b8d4fd`. The consumed
class-file access word is still read; linkage semantics remain unchanged.

The final parent reconstruction and probes use clean source `6b8d4fd`.
The new JAR SHA-256 is `3c8e5d805a65ce91e2efe586f50fa1b9c482665f4d96c9e2384f066ea26cae85`.
Comparing every entry against the child candidate finds only one changed entry:
`META-INF/cnc-hazelcast-jackson-fork.json`, which records the updated preparation
source hashes. Library code/resources are identical between these candidates.
Both explicitly retain `runtime_approved=false`.

Parent checks pass:

- Nine bounded compiler/shader commands reproduce the official old shaded
  components and reconstruct both core/databind pairs, 2.21.7 and 3.1.7.
- Twelve bounded Java compiler/probe commands exercise actual old/fixed wrappers.
  Loaded code sources and versions agree with their hash-bound JARs. Normal
  JSON, Jackson jr and standalone Hazelcast serialization controls pass.
- The six affected Python test modules pass **97 tests and 43 subtests**.
  Two warnings come from intentionally duplicated ZIP fixtures. This is a
  focused rerun, not a new full-suite result.
- Ruff checks `F,E9` and `git diff --check` pass.
- All 215 public source archives remain unchanged. Direct base-class analysis
  examines 10,881 unchanged consumer classes and finds no direct references to
  41 removed classes or 14 removed declared members.

The linkage check excludes multi-release dispatch and does not resolve inherited
members, reflection, serialization or NiFi classloader/resource/service behavior.
Those limits remain open. Of the 37 Hazelcast scanner tuples, six have bounded
old/fixed probes and 31 have primary upstream evidence only. No fresh image
scan was run: the last CI still blocks NiFi on 59 tuples and Kibana on two.
Parquet, plain Jackson candidates and the AWS/Azure carriers remain separate.

The child `candidate-plan.json` and `verification-summary.json` remain historical
records for its original artifact. The parent artifact/source bindings, commands,
logs and limits are in [the parent verification record](HAZELCAST_PARENT_20261105.json).
Neither artifact is selected in a runtime replacement plan.

Separately, the parent repeated the Kibana diagnostic incorporated in `a0126da`:
36,000 comparisons reproduce 216 differences and the actual just-bash witness.
This adds a compatibility regression, not an installed migration or a green gate.
