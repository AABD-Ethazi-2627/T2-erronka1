# Jackson candidate: independent parent reproduction

Child `06c2b21` is incorporated locally as `16b86b5`, then adjusted by the
parent. No runtime archive, Dockerfile, scanner policy or gate is modified.
This remains **component-prepared**, with no classloader or image acceptance.

The parent copies only the **86 pinned Maven inputs** and separately pinned
upstream evidence into a fresh owned cache, checks their hashes, and reruns the
verifier offline. All **15 Java/javac commands pass**. The **12 portable guard
tests pass**; with the existing dependency guards, **24 tests and four subtests
pass**. Ruff passes on the candidate verifier and its root tests.

The four plain scan objects match official Jackson binaries. Two other objects,
Hazelcast and Parquet wrappers, retain **null replacements**. The same-minor
research pairs are 2.21.2→2.21.7, 2.22.2→2.22.3, 3.1.2→3.1.7 and 3.2.2→3.2.3.
Only the 2.22 and 3.2 plain objects are replacement candidates; probes of the
other versions do not establish wrapper compatibility. Symbolic ABI changes
remain blocking where recorded. Sixteen of nineteen advisory IDs have upstream
evidence without a local runtime reproduction; three have bounded local probes.

Parent corrections include full outer/ancestry hashes in each plan occurrence,
bounded hash-checked downloads with exclusive creation and dangling-symlink
rejection before network access, and explicit record-ignore expectations for
both sides of the control. Inverting the expected ignore result is accepted by
the original child probe but rejected by the corrected probe on both old and
fixed 2.21 binaries. Old 2.22/3.2 already contains this earlier ignore fix and is
treated as a positive control. No hostile native/OOM cases or services run.

The current `candidate-plan.json` and `verification-summary.json` identify this
parent execution. The original child versions remain in git and their cache.
[Exact source hashes, command proof and artifact hashes](NIFI_JACKSON_PARENT_20261104.json)
bind the tested bytes; source hashes are captured before execution and checked
afterward. All **156 original public lib files** still match the acquisition
snapshot byte for byte. This is the copied stock `nifi-current/lib` scope, not
the full runtime image, toolkit or inheritance of every NAR/WAR.

Independent review, actual ABI reference/linkage checks, full extension closures,
all consumer/classloader tests and wrapper-specific rebuilds remain pending.
The completed earlier nested scan's **59 tuples** and Kibana's **two findings**
remain blocking. The later NiFi disk-export failure produces no replacement
nested report. Fresh CI, protected review, final image scans, CG32 resources,
NiFi/SMB and human acceptance are separate gates.
