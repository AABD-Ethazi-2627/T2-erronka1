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
prefix checks. Executable modes now match the shebangs. The executable
bytes at `1bb4811` passed Ruff, seven portable tests, and a twelve-JVM real-NarClassLoader
repeat (20.616 seconds) in `plain-jackson-parent-lint-20261106-01`. The original
13-context static campaign is retained with its own pre-cleanup hashes; it is
not relabeled as a rerun of these bytes. The old `frozen_tools` record is historical.
No occurrence is promoted and no runtime approval changes.

## Corrections after independent review (not VM-verified yet)

The original 92-context inventory is historical and is not a closure criterion.
Inventory schema 2 includes inherited-only WARs, their `WEB-INF/classes`, and
implicit Jetty parents for dependency-free NARs. Old inventories are rejected;
regenerate `inventory.json` before the next static or runtime phase. WAR order
remains a provisional static model, not verified Jetty webapp delegation.

The corrected Java probe checks parent identity and exact defining loader/code
source for mapper/core/databind. Prepared fixed JARs use their official new
filenames. These are disposable experiment trees, not an applicable archive
writer plan. Current VM execution, actual denominator and AWS memory remain
pending. No promotion is enabled.

NiFi processor `Class.forName(..., false, ...)` records only class loading without
initialization, not processor execution or complete linkage. Only Jolt JsonUtils
is executed in the existing consumer probes. The 854 old unresolved records are
preexisting absent references; optionality was not established.

The bounded phase runner now accepts `--proof-root /ABS/FRESH/DIRECTORY` for
repetitions without an undeclared wrapper. It refuses any existing output,
stdout, stderr or execution record, including under Python `-O`. All source
changes after `1bb4811` have 33 portable tests and Ruff passing; previous VM
results retain their original hashes and are not relabeled as current execution.

## Prepared real Jetty WAR component probe (not executed)

`JettyWarProbe.java`, `war_runtime.py` and `war-runtime-inputs.json` prepare a
separate **component** experiment for all five schema-2 WAR contexts, original
and fixed. The 95-context symbolic campaign retains its original source and
provisional parent-first WAR hypothesis. It is not relabeled as a measurement
of Jetty's default child-first policy.

The new probe constructs the installed ee11 `WebAppContext` and actual
`WebAppClassLoader(parent, context)`, sets a fresh private temporary directory,
and invokes the installed `WebInfConfiguration.preConfigure/configure` to add
`WEB-INF/classes` and JARs. It checks the default parent-priority flag is false,
sets/restores TCCL explicitly, and asserts the exact effective mapper/core/
databind loader, file origin and version. It performs a benign mapper roundtrip
per WAR. The framework and UpdateAttribute `ObjectMapperResolver` constructors,
`getContext(Class)` and returned mapper `readValue` bodies are invoked; content
viewer initialization is labeled only initialization. A parent-first mutation
of the fixed Jolt context must fail specifically at the Jackson origin check.

The installed-class signatures of both actual resolvers were inspected read-only
in the unchanged `03f…` image: each has a public no-argument constructor and
`getContext(Class)`. This is API preparation, not an execution result. Official
NiFi `JettyServer.loadWar` and Jetty 12.1.13 configuration source hashes/URLs are
recorded in the inputs file; no source-to-installed-bytecode equivalence is
claimed. Complete server/environment matcher configuration, servlet/filter/
listener lifecycle, HTTP behavior and NiFi UI acceptance remain unproved.

The script verifies the exact inventory/pins, unchanged supporting qualifier and
NAR probe, compiler/JVM files and compiler security configuration before use.
Extraction rejects ambiguous/escaping paths, duplicate effective names, symlinks,
file/directory conflicts, directory payloads, source/replacement drift and size
budgets. Existing evidence is not overwritten. The five expected WARs and actual
selected consumer files cannot silently disappear. Both status and metadata
retain `replacement:null`, `runtime_approved:false`, `promotion_eligible:false`.

Portable verification currently passes **20 tests**, plus Ruff, without a JVM.
Compilation and all new WAR executions remain pending. Root must provide a fresh
proof with unchanged schema-2 `inventory.json`, `pins.json`, and the four official
fixed JARs under `cache/`; stage this directory as `tools/`. Keep the complete
proof and failure logs separate from previous campaigns. A coordinator-owned
wrapper must verify image identity and unchanged 6 GiB/20 GiB resource gate,
acquire the common finite lock, and use the following container shape:

```sh
# Run only after the coordinator grants this exact phase its VM slot.
# CNC_JETTY_PROOF is a fresh absolute directory; CNC_PYHOME is the resolved
# existing Python3.11 distribution used in the earlier image experiments.
timeout --signal=TERM --kill-after=5s 175s docker run --rm --pull=never \
  --name cnc-jetty-war-UNIQUE --network none --cpus 1 --cpuset-cpus 0 \
  --memory 512m --memory-swap 512m --pids-limit 64 --read-only \
  --cap-drop ALL --security-opt no-new-privileges --user 1000:1000 \
  --ulimit core=0:0 --tmpfs /tmp:rw,nosuid,nodev,noexec,size=64m \
  --mount "type=bind,src=$CNC_PYHOME,dst=$CNC_PYHOME,readonly" \
  --mount "type=bind,src=$CNC_JETTY_PROOF,dst=/proof" \
  --mount "type=bind,src=$CNC_JETTY_PROOF/tools,dst=/proof/tools,readonly" \
  --mount "type=bind,src=$CNC_JETTY_PROOF/cache,dst=/proof/cache,readonly" \
  --mount type=bind,src=/usr/lib/jvm/java-21-openjdk-amd64,dst=/jdk,readonly \
  --mount type=bind,src=/etc/java-21-openjdk,dst=/etc/java-21-openjdk,readonly \
  --env PYTHONDONTWRITEBYTECODE=1 --entrypoint "$CNC_PYHOME/bin/python3.11" \
  sha256:03f3e9a19dbce166304ec63a685c44f2da07239e5659d843c798c7f32f7012d5 \
  -B /proof/tools/war_runtime.py --proof /proof
```

The outer wrapper must remove only its unique container even on timeout and
capture before/after source/image identities. JVMs use heap256/metaspace96/
direct32/code-cache32/compressed-class-space32 MiB, one active CPU and no cores.
No server, servlet, exporter, NiFi scheduling, SMB or image build is started by
this script. A successful component result cannot alone approve the four JARs,
family writer, final image, security gates or deployment.
