# Next bounded GCP qualification batch — prepared, not executed

This source advances the immutable `8429e12` component proof. It does not
relabel that proof, close a CVE, select an occurrence, change a serving image,
or approve runtime. `replacement:null`, `runtime_approved:false` remain.
The current NiFi security gate and the independent Elasticsearch task remain
outside this experiment.

The future batch retains the existing runner's three phases and their exact
success status names. It must run once from a fresh proof directory, only after
the coordinator grants the common VM slot. Use the exact frozen source snapshot,
not a live bind of an editing checkout. Resource/network/core/deadline limits
remain unchanged. No NiFi server or processor is started by this batch.

1. **Oracle:** reverify the 189 original direct JARs, 16 launcher JARs, all four
   original NAR root hashes/manifests, exact parent TSV and the pinned JDK jmod.
   Repeat the existing offline Maven equality (SDK eight/SPI nine/union nine).
2. **Static:** retain the exact caller/symbol optional boundary exported from the
   reviewed `8429e12` proof (old 66+one inherited path; aligned 50). Unknowns fail
   closed. Pure `gate_static` also checks the narrow ten-reference control, the
   inverse eight-reference control, missing API control, external ABI impacts
   and the actual nine canonical external consumers. No blanket incubator
   allowance exists. Their class/JAR origins are independently fixed from
   `known-inputs.json` and the observed-version mapping.
3. **Runtime:** build only proof helper classes. Extract read-only pinned Jetty
   (47 JARs) and framework (162 JARs) from the unchanged actual image into private
   proof trees. Framework uses the already installed Guava replacement bytes;
   its original ZIP entry name is preserved, as in the existing overlay. Verify
   the exact roots, manifests and each leaf, and reject OTel namespaces in those
   two parent NARs. Instantiate the actual `InstanceClassLoader` implementation
   through the real framework NAR loader, in pass-through mode with GCP as its
   parent; set/restore TCCL explicitly. The four declared GCP NAR edges plus the
   Jetty root and framework sibling are modeled; this is not NiFi-managed
   instance cloning, service lifecycle or scheduling.

Run old, narrow, aligned and aligned-without-`AttributeKey` in separate bounded
JVMs. Record `-Xlog:class+load` and actual consumer origin hashes. Old/aligned
must each initialize all nine observed consumers and instantiate the explicit
SPI provider, with exact parity. The narrow control must fail specifically on
its actual `ConfigUtil` path before claiming later coverage. The new private,
non-candidate mutation removes only `AttributeKey.class` from the pinned aligned
API JAR: `TelemetryMetrics` must report an initialization failure, demonstrating
that `initialize=true` matters.

Four **functional** old/aligned comparisons are separate from initialization:

- Actual GAX `OpenTelemetryMetricsRecorder` records four measurements into a
  real SDK meter provider with a local capturing `MetricReader`. Assert actual
  sums/counts/attributes; exclude timestamps from the canonical comparison.
- Actual gRPC `OpenTelemetryMetricSink` creates and records a long counter,
  including required/optional labels, into that real SDK. No channel or server.
- Actual Google `MetricTranslator.mapMetric` converts benign string/long
  attributes into a protobuf metric. No exporter/network operation.
- Actual `GCPResourceProvider.getAttributes`, `createResource` and `shouldApply`
  execute against an explicitly injected local detector stub with fixed GCE
  data. The stub overrides detection and performs no metadata HTTP operation;
  actual Google detector/resource JARs are untouched. This is resource mapping
  behavior, not GCP detection or service acceptance.

Each functional result must pass and match exactly. Equal initialization
failures cannot be reported as success. Summary output distinguishes passed and
failed initializations. The sealer cross-checks runner/phase source hashes and
refuses any failed/missing/unapproved/symlink phase. The versioned positive export
writes the exact snapshotted source and named raw outputs/class-load logs; it
does not claim that unrelated files in a proof directory are approved.

Remaining qualification: network exporters against a dedicated local fixture,
other consumer methods, incubator-present paths, full NiFi-managed lifecycle and
instance cloning, reflection/JVM access beyond the model, image/scan selection,
CG32/SMB/model and any required human decisions. Source API references were read
from official Maven sources for the same already observed component versions;
no dependency version was changed:

- `org.apache.nifi:nifi-nar-utils:2.12.0` (NarClassLoaders Jetty parent logic).
- Apache NiFi tag `rel/nifi-2.12.0`, `nifi-framework-nar-utils/.../InstanceClassLoader.java`.
- `io.opentelemetry.contrib:opentelemetry-gcp-resources:1.37.0-alpha`.
- `com.google.api:gax:2.85.0`, `com.google.cloud.opentelemetry:exporter-metrics:0.33.0`.
- gRPC Java tag `v1.83.0`, `OpenTelemetryMetricSink.java`.

Downloads/hashes are retained externally at
`/home/tears/.cache/cnc-benten-vm-20261105/otel-behavior-preparation-20261106/`.
