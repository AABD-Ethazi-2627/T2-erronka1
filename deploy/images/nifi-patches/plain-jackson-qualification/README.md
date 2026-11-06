# Plain Jackson component qualification

This directory prepares **read-only component evidence** for four already pinned
Jackson JARs in image
`sha256:03f3e9a19dbce166304ec63a685c44f2da07239e5659d843c798c7f32f7012d5`
(source `12ca2fa95c0e6e94665dc75923f3cbdaa2468b24`). It never produces an applicable
overlay or changes a NAR, source cache, image, existing pins, or approval status.

The only candidate artifacts are `jackson-core` and `jackson-databind`
2.22.2 → 2.22.3 and 3.2.2 → 3.2.3 from `../jackson/pins.json`.
Every official candidate download must match that existing pin. Maven closure and
family validation remain independent mandatory preconditions.

`qualify.py inventory` reads actual image NAR manifests and nested JAR/WAR hashes,
records complete carrier chains, constructs the transitive NAR parent graph and
also verifies the four already corrected bootstrap/toolkit files. Historical stock
inventory paths do not authorize replacements in the final image.

`qualify.py analyze` builds the actual parent-first NAR classpath with JAR filenames
sorted as installed `NarClassLoader` does. It compares old/fixed effective class
surfaces and all consumer constant-pool class/member/descriptor references,
resolving superclass/interface members, constructors, visibility, defining NAR
packages and validated nestmates. Java 21 multi-release entries are selected.
Actual image `java.base` classfiles supply JDK inherited members. Each result
includes known real consumers, nonzero reference counts and a deliberately removed
referenced class as a negative control. Original and candidate baseline gaps remain
explicit. Unresolved baseline symbols prevent a claim of complete linkage.

This remains a conservative symbolic check, not the JVM verifier. Reflection,
method-handle access modes, protected receiver constraints, interface default
conflicts, service/provider discovery and dynamic resources require further proof.
WAR analysis records a parent-first hypothesis; **Jetty webapp delegation is not
verified**, so WAR results cannot authorize promotion.

`runtime.py` builds disposable expanded NAR trees outside the repository from the
actual image JARs. Fixed trees substitute only the four verified public JAR bytes.
These trees are evidence and are never an overlay output. `NarProbe.java` uses the
actual installed `NarClassLoader(File, ClassLoader)` and actual manifest parent
chain. The application classpath contains only actual top-level NiFi JARs and the
launcher. Jackson must be defined by a real `NarClassLoader`; its actual loaded
version and code source are asserted. Existing bounded Jackson old/fixed cases
run inside that loader, including actual Jolt `JsonUtils` roundtrips and safe NiFi
consumer class loading. No processor, NiFi server, external service or network is
started. WAR runtime proof remains separate and pending.

`run_phase.py` is a VM-specific harness for the authorized Benten guest. Caller
must hold `/opt/cnc-guard/evidence/remote-heavy.lock` using `flock -E 75 -w 30`.
One phase is bounded to 165 seconds inside an outer 175-second limit, CPU 0 / one
CPU, 512 MiB cgroup memory without extra swap, JVM heap 256 MiB / metaspace 96 MiB /
direct 32 MiB, no network, no capabilities, no core dump, and a read-only image.
Only its evidence bind mount is writable. Tool, pin and artifact mounts are read
only. Preserve every failed execution and use a fresh output label for reruns.
Only containers named by this invocation may be cleaned up.

Required evidence directory layout on the guest:

- `tools/`: these source files, readable by image UID 1000.
- `pins.json`: byte-identical existing Jackson pin file.
- `probe-template.java.in`: byte-identical existing `../jackson/JacksonProbe.java.in`.
- `cache/`: four fixed official JARs verified against existing pins.
- `inventory.json`: initial actual image graph consumed by analysis/runtime phases.

A successful phase is **component evidence only**. All plans/results must retain
`replacement: null` and `runtime_approved: false`. Promotion also requires complete
consumer coverage, actual Jetty/WAR proof, the family guard, independent QA,
new image creation and both actual image gates. NiFi scheduling, SMB integration,
CI and human acceptance are distinct later gates.

Parent lint cleanup removes unused imports, sorts imports, states the existing
`subprocess.run(check=False)` default explicitly and combines equivalent string
prefix checks. Executable modes now match the shebangs. The committed executable
bytes pass Ruff, seven portable tests, and a fresh twelve-JVM real-NarClassLoader
repeat (20.616 seconds) in `plain-jackson-parent-lint-20261106-01`. The original
13-context static campaign is retained with its own pre-cleanup hashes; it is
not relabeled as a rerun of these bytes. The old `frozen_tools` record is historical.
No occurrence is promoted and no runtime approval changes.
