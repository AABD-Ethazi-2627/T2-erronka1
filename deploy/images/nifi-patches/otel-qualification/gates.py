"""Pure qualification decisions, exercised without containers or Java."""

import importlib.util
from pathlib import Path

s = importlib.util.spec_from_file_location(
    "_otel_gate_coverage", Path(__file__).with_name("coverage.py")
)
c = importlib.util.module_from_spec(s)
s.loader.exec_module(c)
EXTERNAL_CONSUMERS = (
    "io.grpc.opentelemetry.GrpcOpenTelemetry",
    "io.grpc.opentelemetry.OpenTelemetryMetricSink",
    "com.google.cloud.opentelemetry.metric.MetricTranslator",
    "com.google.cloud.opentelemetry.metric.InternalMetricExporter",
    "com.google.cloud.storage.OpenTelemetryBootstrappingUtils",
    "com.google.cloud.bigquery.storage.v1.TelemetryMetrics",
    "com.google.cloud.pubsub.v1.OpenTelemetryPubsubTracer",
    "com.google.api.gax.tracing.OpenTelemetryMetricsRecorder",
    "io.opentelemetry.contrib.gcp.resource.GCPResourceProvider",
)
EXTERNAL_JARS = {'io.grpc.opentelemetry.GrpcOpenTelemetry': 'grpc-opentelemetry-1.83.0.jar', 'io.grpc.opentelemetry.OpenTelemetryMetricSink': 'grpc-opentelemetry-1.83.0.jar', 'com.google.cloud.opentelemetry.metric.MetricTranslator': 'exporter-metrics-0.33.0.jar', 'com.google.cloud.opentelemetry.metric.InternalMetricExporter': 'exporter-metrics-0.33.0.jar', 'com.google.cloud.storage.OpenTelemetryBootstrappingUtils': 'google-cloud-storage-2.73.0.jar', 'com.google.cloud.bigquery.storage.v1.TelemetryMetrics': 'google-cloud-bigquerystorage-3.33.0.jar', 'com.google.cloud.pubsub.v1.OpenTelemetryPubsubTracer': 'google-cloud-pubsub-1.155.0.jar', 'com.google.api.gax.tracing.OpenTelemetryMetricsRecorder': 'gax-2.85.0.jar', 'io.opentelemetry.contrib.gcp.resource.GCPResourceProvider': 'opentelemetry-gcp-resources-1.37.0-alpha.jar'}

BEHAVIORS = (
    "gax-metrics",
    "metric-translator",
    "grpc-metrics",
    "gcp-resource-getAttributes",
)


def expected_consumer_origins(known,pins):
    return [{"class":name,"jar":EXTERNAL_JARS[name],"sha256":c.expected_origin(known,pins,EXTERNAL_JARS[name])} for name in EXTERNAL_CONSUMERS]


def require_consumer_origins(known,pins,records):
    if records!=expected_consumer_origins(known,pins):raise ValueError("independent consumer origin pins changed")


def gate_static(r):
    for field, scenario in [
        ("unresolved_old", "old"),
        ("unresolved_current_references", "aligned"),
        ("unresolved_including_api_family", "aligned-all-family-including-api"),
    ]:
        c.require_closed(r[field])
        c.require_optional_boundary(r[field], scenario)
    if r["newly_broken_references"] or r["abi_delta"]["external_impacts"]:
        raise ValueError("observed symbolic or external ABI impact")
    if len(r["narrow_negative_control"]) != 10:
        raise ValueError("narrow negative control coverage")
    inverse = r["reversed_sdk_api_negative_control"]
    if len(inverse) != 8 or any(
        x["category"] != "unknown"
        or x["reference"][0] != "io/opentelemetry/common/impl/ConfigUtil"
        for x in inverse
    ):
        raise ValueError("inverse ConfigUtil negative control coverage")
    if r["missing_api_negative_new_failures"] <= 0:
        raise ValueError("API negative control vacuous")
    if tuple(r["selected_external_consumers"]) != EXTERNAL_CONSUMERS or not set(
        EXTERNAL_CONSUMERS
    ) <= set(r["observed_external_class_names"]):
        raise ValueError("real external consumer selection changed")
    return r


def initialization_counts(rows):
    return {
        "consumer_init_passed": sorted(
            k for k, v in rows.items() if v["status"] == "PASS"
        ),
        "consumer_init_failed": {
            k: v["cause"] for k, v in rows.items() if v["status"] == "FAIL"
        },
    }


def gate_runtime(r):
    outcomes = {x["variant"]: x for x in r["outcomes"]}
    if set(outcomes) != {"old", "narrow", "aligned", "aligned-missing-attributekey"}:
        raise ValueError("runtime variant coverage")
    old, new = outcomes["old"], outcomes["aligned"]
    c.require_consumer_parity(
        old["observed_external_consumer_initialization"],
        new["observed_external_consumer_initialization"],
        EXTERNAL_CONSUMERS,
    )
    for row in (old, new):
        if row["returncode"] != 0 or not row["configutil_consumer_passed"]:
            raise ValueError("SDK runtime control incomplete")
        counts = initialization_counts(row["observed_external_consumer_initialization"])
        if counts["consumer_init_failed"] or len(counts["consumer_init_passed"]) != 9:
            raise ValueError("external initialization failures remain")
        if not row["service_provider_lines"] or not row["class_load_otel_count"]:
            raise ValueError("SPI/class-load coverage missing")
        if row["loader_model"] != "real-instance-pass-through-tccl-with-jetty-parent":
            raise ValueError("loader model unobserved")
        if set(row["behavior_results"]) != set(BEHAVIORS) or any(
            x["status"] != "PASS" for x in row["behavior_results"].values()
        ):
            raise ValueError("functional behavior coverage incomplete")
    if (
        old["service_provider_lines"] != new["service_provider_lines"]
        or old["behavior_results"] != new["behavior_results"]
    ):
        raise ValueError("SPI or functional behavior parity changed")
    narrow = outcomes["narrow"]
    if (
        narrow["returncode"] == 0
        or not narrow["expected_configutil_failure"]
        or narrow["observed_external_consumer_initialization"]
    ):
        raise ValueError("narrow actual failure is not discriminating")
    negative = outcomes["aligned-missing-attributekey"]
    rows = negative["observed_external_consumer_initialization"]
    target = "com.google.cloud.bigquery.storage.v1.TelemetryMetrics"
    if (
        negative["returncode"] == 0
        or set(rows) != {target}
        or rows[target]["status"] != "FAIL"
        or not negative["expected_attribute_key_failure"]
    ):
        raise ValueError(
            "external initialization negative control is not discriminating"
        )
    return r
