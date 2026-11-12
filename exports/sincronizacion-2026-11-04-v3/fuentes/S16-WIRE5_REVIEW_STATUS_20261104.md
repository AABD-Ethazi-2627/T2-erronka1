# Wire 5 candidate: review and subsequent verification

This is preparation for review, **not an integrated NiFi repair**. No NiFi image,
classpath, scanner gate or finding exception is changed by this candidate.

Claude reviewed the initial five-file candidate identified by
`wire5-final-handoff.json`. It found no concrete reader bypass in the reviewed
paths, but blocked promotion on scanner identity, unexamined artifact occurrences,
upstream/generated-consumer comparison, inadequate regression coverage,
inconsistent evidence references and missing verification pins. The review was
read-only; it ran no tests, build, network or scan. Its full report remains at
`/home/tears/.cache/cnc-nifi-ci-remediation-20261104/CLAUDE_WIRE5_REVIEW.md`.
The initial handoff's claim that Maven identity was preserved was incorrect:
upstream had no Maven properties. A changed JAR hash alone could lose recognition.

The implementer started addressing those findings, then its session was denied
because it lacked hardware-key authentication. The coordinator retained those
edits and continued verification from the authorized parent session.

## Subsequent parent results

- Explicit, truthful Maven coordinates identify a fork at `5.2.0+cncguard.1`.
  A real Trivy **rootfs** scan still identifies the hash-renamed JAR and reports
  CVE-2026-45799. The standalone inventory helper rejects missing targets,
  packages, findings and mismatched paths. No image exception is added.
- The other reported artifact, SHA-256 `a497c6a643234025da2dfe81b73eb3a0197b2c07eec699f1dca727f1aa64a288`,
  is official Wire-runtime5.2 KMP metadata with zero JVM classes. This does not
  enumerate every reader occurrence or classloader in NiFi.
- Unsigned tag extraction follows upstream6.4.5. A streaming preallocation
  estimate additionally caps at buffered bytes/64KiB; this is a documented local
  divergence. The valid70000-element packed control still decodes all values.
- The expanded suite passes44 tests; original5.2 fails9. It includes a
  discriminating negative128 payload, nested/packed/empty/ten-byte valid input,
  boundary negatives and512 seeded cases per reader. This finite corpus does not
  establish complete fuzz or mutation coverage.
- The actual schema5.2 consumer roundtrip passes. Public reader ABI remains the
  same;129 of132 original entries are byte-identical. Only3 class payloads differ;
 5 generated classes are allowlisted for overlay. Two entries add provenance and
  explicit fork coordinates.
- Input, dependency, Maven/JDK/Kotlin toolchain and output hashes are pinned.
  Modified input is rejected before a build starts. Pins are exact local
  toolchain evidence, not a universally portable JDK specification.

Candidate SHA-256:
`cd7e75b111f9c9043311bb76f1622fbf44ebe9f0cb00018aa8c759dcc21b6d53`.
Recipe and limits: [candidate README](../../deploy/images/nifi-patches/wire5/README.md).
The corrected parent workspace is `parent-wire5-v2-pinned` under the evidence
root above. Earlier JAR hashes/workspaces remain historical and are not relabelled.

## Still blocking promotion

V2 has not received renewed independent approval. Full upstream/generated-consumer
comparison, actual nested NiFi inventory and consumers, image assembly and both
scans remain pending. The standalone scan is not a substitute for those gates;
absence of another advisory tuple is not proof of correction. No complete NiFi
security closure or green PR is asserted. Full CI and required GitHub review are
still mandatory before merge.
