# Wire 5 reader backport — unpromoted candidate

This subtree is a verification/review artifact. It does not change the NiFi
Dockerfile, runtime classpath, scanner gate or exceptions. Do not interpret its
unit tests or a missing scanner finding as NiFi acceptance.

## Source and scope

The official Wire-runtime-jvm 5.2.0 source JAR is pinned to SHA-256
`7be3ac3d239e532c62becb6195602f0770d7b8de11d8793b9fc01702dea2ecd8`.
The official 6.4.5 sources inspected for comparison hash to
`41cd91b6dd275d43fe8ac71f2702d75dd6930f0abdd46dedd325186eb95b6bac`.
The parent retains these in its evidence cache. Published fixes differ:
[negative skipped-group length](https://github.com/square/wire/security/advisories/GHSA-7xpr-hc2w-34m9)
starts at 6.3.0; [positive overflow and related reader boundaries](https://github.com/square/wire/security/advisories/GHSA-9rm7-3qhh-h2mc)
starts at 6.4.5. A 6.3-only upgrade would not close both.

The candidate checks lengths before cursor arithmetic and keeps scalar/group
reads inside their logical message bounds. Unsigned tag shifts match the 6.4.5
reader behavior. It also **diverges from upstream** by bounding the streaming
`nextFieldMinLengthInBytes` preallocation estimate to buffered bytes and 64 KiB.
This limits the estimate, not the message: a valid packed 70,000-element control
still decodes every element. Further generated-consumer review is required.

Only two Kotlin sources are compiled, allowing five generated reader classes.
Of the 132 original ZIP entries, 129 remain byte-identical; only three class
payloads actually differ. `RuntimeMessageAdapter` and the schema consumer ABI
remain unchanged. The other two generated class payloads are identical to upstream.
Two new entries identify provenance and explicit Maven coordinates
`com.squareup.wire:wire-runtime-jvm:5.2.0+cncguard.1`. This identity truthfully
marks a fork; it is not an upstream release or evidence of scanner recognition.
The standalone rootfs scan identified this fork after hash renaming and still reported
CVE-2026-45799. `verify_scan.py` checks that every reader artifact in that
experiment matches the pinned bytes, package identity and expected finding.
This is not a full NiFi inventory or an image gate.

The separately reported `wire-runtime` 5.2.0 artifact with SHA-256
`a497c6a643234025da2dfe81b73eb3a0197b2c07eec699f1dca727f1aa64a288`
was retrieved from Maven Central and contains zero JVM classes. It is KMP
metadata, not another copy of these reader classes. This does not establish all
NiFi archive occurrences/classloaders; real nested image inventory remains open.

## Reproduce this exact candidate

```sh
python deploy/images/nifi-patches/wire5/verify.py \
  --work-dir /absolute/new/wire5-verification \
  --mvn /absolute/apache-maven-3.9.11/bin/mvn \
  --java-home /usr/lib/jvm/java-21-openjdk \
  --maven-repo /absolute/private/maven-repository
```

The toolchain is JDK21, Maven3.9.11, Kotlin2.0.21; builds use one job and 512 MiB
heap, Java tests 256 MiB. `verification-pins.json` pins the reviewed input bytes,
resolved test dependencies, Maven distribution JARs, JDK modules/executables,
Kotlin compiler and resulting candidate bytes. These are exact local toolchain
pins: another JDK distribution or patch release may correctly be rejected.
Changing pins requires reviewing the changed inputs and output; do not recompute
them merely to make verification pass. The verifier itself is covered by Git/source
review, not self-authenticated by its adjacent pin file.

The Maven distribution was fetched from its official Maven Central URL and checked
against SHA-512
`bcfe4fe305c962ace56ac7b5fc7a08b87d5abd8b7e89027ab251069faebee516b0ded8961445d6d91ec1985dfe30f8153268843c89aa392733d1a3ec956c9978`.
The corrected Kotlin friend path references the actual Maven classpath JAR, rather
than its byte-identical dependency-copy path. The old recipe failed visibility
checks; its failure log is retained.

## Observed verification and review limits

Parent run `parent-wire5-v2-pinned` completed 44 tests; the original fails nine.
Controls include the discriminating -128 advisory payload, positive overflow,
valid nested/empty/packed/ten-byte values, nested tag/string/skip/group boundaries,
truncated fixed values, the large packed message, preallocation estimate, the
actual Wire-schema5.2 adapter roundtrip, and 512 seeded malformed/small inputs
per reader. The corpus is finite, not exhaustive fuzzing or a mutation score.
Valid-input controls also pass on the original. Modifying a pinned test input is
rejected before creating the work directory or invoking build/network operations.
The original 6.3 runtime plus schema5.2 separately reproduced `NoSuchMethodError`;
that historical control is not part of this verifier's repeatable assertions.

Candidate SHA-256:
`cd7e75b111f9c9043311bb76f1622fbf44ebe9f0cb00018aa8c759dcc21b6d53`.
Evidence: `/home/tears/.cache/cnc-nifi-ci-remediation-20261104/`, specifically
`parent-wire5-v2-pinned/verification.json`, its complete logs and
`parent-wire5-v2-summary.json`.

Claude's **v1** review blocked promotion: scanner identity, missing archive
inventory, incomplete tests/upstream comparison and insufficient pins. The parent
expanded the tests and pins and corrected identity/documentation after that review;
**v2 has not received renewed independent approval**. The original handoff and
its earlier JAR hashes remain historical, not aliases for this candidate.

Remaining gates include full upstream/generated-consumer comparison, actual
nested NiFi inventory, full-image scanner coverage, real NiFi consumers,
hash-pinned image assembly and both scans, and a reviewed treatment of any Wire
findings. No gate change, final-image acceptance or green CI is implied here.


The real rootfs report and coverage result are retained as `wire5-v2-rootfs-scan.json`
and `wire5-v2-scan-coverage.json` in the evidence root. Plain `trivy fs` reported
zero analyzed language files and was rejected as lacking coverage. Download attempts
also encountered a mirror404 and a /tmp quota failure. The successful rootfs run
used official GHCR databases and a private on-disk TMPDIR; logs remain distinct.
No package finding was suppressed. The observed JVM-coordinate finding is
CVE-2026-45799; absence of another advisory tuple is not proof of its correction.
