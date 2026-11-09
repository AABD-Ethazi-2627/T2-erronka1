# GCP OpenTelemetry qualification — preparation only

Owned scope: this directory and `tests/test_nifi_otel_qualification.py`.
No runtime, Dockerfile, policy, manifests, security exceptions or shared Maven
resolver changes. `replacement: null`, `runtime_approved: false` throughout.

The actual candidate image is `cnc-guard-candidate:nifi-12ca2fa`, image ID
`sha256:03f3e9a19dbce166304ec63a685c44f2da07239e5659d843c798c7f32f7012d5`.
GCP's API 1.62.0 input SHA is
`d58143928c049233653e6bf1282ff8a767ebdd5e6a82b3f336158c30e40b431d`.

Reuse the **existing** official 1.67.0 API/context/common pins from the
Elasticsearch Dockerfile. This is not evidence that Elasticsearch's SDK closure
is compatible with GCP. The GCP closure contains SDK 1.62.0, gRPC instrumentation
1.83.0 and alpha GCP/semantic-convention dependencies. No blanket upgrade.

Before any new POM/source pin or family promotion, the coordinator must confirm
Maven H1/H2 oracle corrections and frozen-closure equality. Qualification then
uses a fresh external proof and the actual image's read-only source. No Maven
plugins or project servers execute.

Planned evidence:

1. Exact GCP NAR plus manifest-parent closure and per-object input hashes.
2. Old/fixed public surface and inherited symbol checks, actual direct consumers,
   explicit incomplete/reflection/resource limits and nonvacuous negative controls.
3. Real installed `NarClassLoader` isolated old/fixed trees, with provenance;
   SDK/trace/context/metrics/log and actual GCP/gRPC class loading controls.
4. Benign propagation checks on the actual 1.62/1.67 implementations; never an
   intentional OOM or service startup. Flat classpath results are component only.
5. Re-read original/code/image hashes after proof. Report component eligibility
   separately from NiFi scheduling, image scans, SMB, CG32 and human acceptance.

All heavy work runs only in the reserved VM phase, one CPU, shared finite lock,
175-second phase wall limit, 512 MiB cgroup RAM (and Python data-phase address limit), Java heap 256 MiB,
metaspace 96 MiB, direct memory 32 MiB, no cores and no network.

The API 1.67 POM requires context 1.67, which requires common 1.67.
The complete published minimum is therefore the aligned API/context/common trio.
The pair with common 1.62 is only an explicitly nonconforming control, never a
candidate even if selected runtime operations pass. In that narrow experiment,
SDK and all other existing GCP libraries remain unchanged. The first failed expectation is retained in the
external original proof; corrected proof uses a new attempt-02 directory.

## Sealed narrow result

See `narrow-result.json`. Actual candidate input: four NARs, 189 direct JARs;
44,499 physical class entries, 740 consumer entries and 8,846 constant-pool
reference records. Both the nonconforming API/context pair and the aligned API/
context/common trio lose ten references to `api.internal.ConfigUtil` from the
unchanged SDK-common, metrics and autoconfigure-SPI 1.62 modules. Neither is
eligible. The missing-API mutation adds 47 failures and detects an empty result.
Counts include physical duplicate/shadowed entries; the symbolic model is not
complete JVM access/default-method/method-handle/descriptor/reflection analysis.

Attempt03 runtime did not reach the NAR probes: the mounted Ubuntu compiler's
absolute `java.security` symlink lacked its read-only `/etc/java-21-openjdk`
configuration mount. This is a harness gap, not an observed SDK runtime failure.
Two earlier harness failures and all their source snapshots/logs are retained.
The sealed VM/local proofs identify the tested source bytes; this README/result
metadata were added afterward and do not relabel those executions.

A separate aligned SDK preparation is authorized after the coordinator's Maven
92ff99e guard correction. It may replace only observed OTel-family artifacts in
isolated proof trees, must derive and compare the published closure with real
Maven, and may not promote any overlay/runtime/profile or unrelated gRPC/alpha
package. The current narrow baseline remains intact.


## Historical aligned SDK result (before independent QA)

Independent QA of `a6bddd0` found an evidence defect: the three previously
selected GCP classes were not demonstrated to consume OTel, and loading with
initialization disabled did not qualify their behavior. The raw result below
is preserved as history. Its SDK/configuration controls remain observations;
its former GCP consumer claim must not be used as acceptance evidence.

See `aligned-result.json`. The frozen batch ran after the VM's authorized RAM
resize to 10 GiB; its resource preflight retained the 6 GiB available / 20 GiB
free gates. The Maven, symbolic and real-loader phases exited 0 in 1.033,
20.533 and 5.647 seconds, respectively, with the same 512 MiB cgroup limit.
The 13 portable guards passed inside the VM before those phases.

Only the nine observed modules move to official 1.67.0 in private proof trees:
API, context, common, SDK, SDK-common, trace, metrics, logs and autoconfigure-SPI.
Their POM closure equals the offline Maven 3.9.11 oracle exactly: eight artifacts
from SDK, nine from SPI, union nine. No unrelated gRPC, alpha or exporter artifact
was upgraded. Existing Google exporter JARs remain consumers in the static scan;
exporter operations were not exercised.

The symbolic model inspected 44,499 physical classes, 740 consumer entries and
9,021 reference records after alignment. It found zero newly broken modeled
references. Its missing-API mutation produced 37 failures, and the narrow
old-SDK control reproduced the ten `ConfigUtil` losses. The 205 unresolved current
references remain explicit; the model does not fully resolve inherited JDK
methods, JVM access, descriptors, method handles, default methods or reflection.
Zero newly broken references is not complete ABI approval.

Using the installed `NarClassLoader` and actual four-NAR parent chain:

| Private proof tree | Observed result |
| --- | --- |
| Original OTel 1.62 modules | SDK config conversion and exercise pass |
| API/context/common 1.67, old SDK 1.62 | Fails specifically with missing `api.internal.ConfigUtil` |
| All nine observed modules 1.67 | Config conversion, SDK trace/context/baggage/metrics/log and benign propagation pass |

The historical probe checks nine loaded class origins and JAR hashes, and loads
selected classes without initialization. This is not evidence of actual GCP
consumer execution. The launcher TCCL is not changed; SPI/resource-provider
traversal, exporter operations, NiFi scheduling/server and GCP operations were
unqualified in that run. Actual image NAR hashes, image identity and tested sources remain
unchanged, with no owned containers left behind.

The historical aligned component underwent independent QA, which required a
corrected experiment before occurrence/overlay selection. `replacement:null`
and `runtime_approved:false` remain enforced in
result metadata. No fresh image scan, CG32, SMB, model or human acceptance follows
from this proof. The earlier narrow failures and their immutable proof stay
available. This section and `aligned-result.json` were added after execution;
the compact evidence includes the exact earlier source snapshot that ran.

The separate ES inventory observation is conditional: its APM directory contains
old 1.62 SDK modules beside the new triple, but the ES loader/exporter/agent
closure has not been qualified. This GCP nine-module result does not qualify ES.

## Corrected experiment prepared after QA

The corrected source selects nine actual external OTel consumers, records their
initialization outcomes instead of presumed loading, requires old/aligned
parity, and traverses ResourceProvider SPI with the explicit NAR loader. A
matching failure in both versions is recorded as a failure, not qualified
consumer behavior. Exporter operations, provider attributes, processor TCCL and
NiFi services remain outside this experiment.

All 189 expanded direct JARs and 16 launcher inputs are verified independently
before and after each phase. Unknown unresolved references fail the symbolic
gate; inherited JDK members and internal optional incubator references are
classified by caller and symbol. A reversed SDK-new/API-old control must expose
eight ConfigUtil references. Declared ABI changes and external impacts are
reported separately. The actual encoding source diff and bytecode markers must
discriminate; benign propagation tests do not establish CVE closure.

The runner now fails on blocked phases, source/image drift and cleanup errors.
Its versioned summary generator refuses incomplete reports and existing output.
The first corrected batch (`e4c5751`) passed the oracle and 49 portable tests,
then failed closed on eight original references. Two bounded diagnostics found
seven inherited JDK methods and one internal SDK-logs call through the absent
incubator interface. That failed attempt and diagnostics are preserved.

The next source reads exact public method declarations and ancestors from the
mounted compiler JDK21 `java.base.jmod`, recording its hash and scope separately
from the image JVM. Only the one exact old internal incubator caller/member/path
is classified as optional inheritance; external or changed signatures still
fail. Classified rows are saved before the gate, including on failure. Both
portable suites pass locally: 52 tests and 3 subtests.

## Corrected bounded VM result

Frozen source `8429e12` passed those 52 tests and 3 subtests, followed by Maven
(1.179 s), symbolic analysis (30.554 s) and real-loader controls (5.491 s), with
the original limits unchanged. The versioned sealer generated `summary.json`.
The downloaded archive SHA-256 is
`54896f8f44cf5c3d142055387bb0dbe52a3c7a2120810438e5050af1396a4749`;
all 54 payload hashes were checked after download. It is retained at
`/home/tears/.cache/cnc-benten-vm-20261105/otel-aligned-reviewfix-8429e12/`.

All nine selected external classes initialized successfully in both original
and aligned trees. One ResourceProvider was instantiated through explicit
ServiceLoader traversal in each. The narrow control failed at ConfigUtil before
claiming any later initialization. SDK configuration and benign propagation
controls passed in original/aligned trees. Provider attributes, exporter
operations, actual NiFi processor TCCL and scheduling remain unexecuted.

The 205 current unresolved references classify as 155 inherited JDK members and
50 internal optional incubator references; none is unclassified. The old 228
classify as 161 JDK, 66 optional incubator and the one exact old inherited
incubator member. The reverse SDK-new/API-old control exposes eight unknown
ConfigUtil references and is rejected. ABI differences include 10 new abstract
members, 29 declared removals, 22 access restrictions and one static change,
with zero modeled external impacts. This remains a bounded symbolic model.
Its 144 external classes include descriptor-only users; the earlier review's
110 counted constant-pool users, so those denominators are not interchangeable.

All 189 expanded JARs, 16 launcher JARs, original image NARs, source bytes and
image identity were verified unchanged, with no owned probe containers left.
No serving image, archive replacement or approval flag changed. Independent
recheck and remaining service/image/acceptance gates still apply; this result
does not close the CVE, qualify ES, or reduce the current NiFi scan count.
