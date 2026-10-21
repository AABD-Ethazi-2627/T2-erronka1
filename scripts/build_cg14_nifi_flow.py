"""Build the versionable CG14 NiFi flow from the Groovy single source of truth.

Reads ``nifi-flows/cg14_validate.groovy`` and writes
``nifi-flows/cg14_validation_flow_v0.1.0.json`` (NiFi 1.25.0 template,
``ConsumeKafka -> Parsing -> Validacion -> Enrutamiento -> PublishKafka``).

Topics, servers and budgets are parameters (``CG14-params`` context), never
hardcoded credentials. Nothing is deployed: import the JSON in NiFi and bind
the parameter context before running.
"""

from __future__ import annotations

import json
from pathlib import Path

NIFI_VERSION = "1.25.0"
SCHEMA_VERSION = "0.1.0"
HERE = Path(__file__).resolve().parent.parent / "nifi-flows"
GROOVY = HERE / "cg14_validate.groovy"
FLOW = HERE / "cg14_validation_flow_v0.1.0.json"

KAFKA_BUNDLE = {
    "group": "org.apache.nifi",
    "artifact": "nifi-kafka-2-6-nar",
    "version": NIFI_VERSION,
}
STD_BUNDLE = {
    "group": "org.apache.nifi",
    "artifact": "nifi-standard-nar",
    "version": NIFI_VERSION,
}
SCRIPT_BUNDLE = {
    "group": "org.apache.nifi",
    "artifact": "nifi-scripting-nar",
    "version": NIFI_VERSION,
}


def processor(pid, name, ptype, bundle, props, x, y, autoterminate=()):
    return {
        "identifier": pid,
        "name": name,
        "position": {"x": float(x), "y": float(y)},
        "type": ptype,
        "bundle": bundle,
        "properties": props,
        "autoTerminatedRelationships": list(autoterminate),
        "schedulingStrategy": "TIMER_DRIVEN",
        "schedulingPeriod": "0 sec",
        "executionNode": "ALL",
    }


def connection(cid, src, dst, rels):
    return {
        "identifier": cid,
        "name": "",
        "source": {"id": src, "type": "PROCESSOR"},
        "destination": {"id": dst, "type": "PROCESSOR"},
        "selectedRelationships": list(rels),
    }


def main() -> None:
    script = GROOVY.read_text(encoding="utf-8")
    processors = [
        processor(
            "cg14-consume-kafka",
            "ConsumeKafka — raw (CG14)",
            "org.apache.nifi.processors.kafka.pubsub.ConsumeKafka_2_6",
            KAFKA_BUNDLE,
            {
                "bootstrap.servers": "#{CG14_BOOTSTRAP_SERVERS}",
                "topic": "#{CG14_RAW_TOPIC}",
                "topic_type": "names",
                "group.id": "#{CG14_CONSUMER_GROUP}",
                "auto.offset.reset": "earliest",
                "security.protocol": "#{CG14_SECURITY_PROTOCOL}",
            },
            100,
            300,
        ),
        processor(
            "cg14-source-meta",
            "UpdateAttribute — procedencia",
            "org.apache.nifi.processors.standard.UpdateAttribute",
            STD_BUNDLE,
            {
                "cg14.source.kind": "nifi-cg14",
                "cg14.source.uri": "kafka://${kafka.topic}/${kafka.partition}/${kafka.offset}",
                "cg14.record.ref": "${kafka.topic}/${kafka.partition}/${kafka.offset}",
                "cg14.max.line.bytes": "#{CG14_MAX_LINE_BYTES}",
                "cg14.max.field.chars": "#{CG14_MAX_FIELD_CHARS}",
                "cg14.schema.version": "#{CG14_SCHEMA_VERSION}",
            },
            340,
            300,
        ),
        processor(
            "cg14-validate",
            "ExecuteScript — validación CG14 (Groovy)",
            "org.apache.nifi.processors.script.ExecuteScript",
            SCRIPT_BUNDLE,
            {"Script Engine": "Groovy", "Script Body": script},
            580,
            300,
        ),
        processor(
            "cg14-route",
            "RouteOnAttribute — válidos/rechazados",
            "org.apache.nifi.processors.standard.RouteOnAttribute",
            STD_BUNDLE,
            {
                "Routing Strategy": "Route to Property Name",
                "valid": "${cg14.valid:equals('true')}",
                "rejected": "${cg14.valid:equals('false')}",
            },
            820,
            300,
        ),
        processor(
            "cg14-tag-valid",
            "UpdateAttribute — marca destino validated",
            "org.apache.nifi.processors.standard.UpdateAttribute",
            STD_BUNDLE,
            {"cg14.retry.topic": "#{CG14_VALIDATED_TOPIC}"},
            940,
            180,
        ),
        processor(
            "cg14-tag-rejected",
            "UpdateAttribute — marca destino rejected",
            "org.apache.nifi.processors.standard.UpdateAttribute",
            STD_BUNDLE,
            {"cg14.retry.topic": "#{CG14_REJECTED_TOPIC}"},
            940,
            420,
        ),
        processor(
            "cg14-publish-valid",
            "PublishKafka — cnc.telemetry.validated",
            "org.apache.nifi.processors.kafka.pubsub.PublishKafka_2_6",
            KAFKA_BUNDLE,
            {
                "bootstrap.servers": "#{CG14_BOOTSTRAP_SERVERS}",
                "topic": "#{CG14_VALIDATED_TOPIC}",
                "delivery.guarantee": "Guarantee Replicated Delivery",
                "security.protocol": "#{CG14_SECURITY_PROTOCOL}",
            },
            1180,
            180,
            autoterminate=("success",),
        ),
        processor(
            "cg14-publish-rejected",
            "PublishKafka — cnc.rejected",
            "org.apache.nifi.processors.kafka.pubsub.PublishKafka_2_6",
            KAFKA_BUNDLE,
            {
                "bootstrap.servers": "#{CG14_BOOTSTRAP_SERVERS}",
                "topic": "#{CG14_REJECTED_TOPIC}",
                "delivery.guarantee": "Guarantee Replicated Delivery",
                "security.protocol": "#{CG14_SECURITY_PROTOCOL}",
            },
            1180,
            420,
            autoterminate=("success",),
        ),
        processor(
            "cg14-retry-count",
            "UpdateAttribute — intentos de publicación",
            "org.apache.nifi.processors.standard.UpdateAttribute",
            STD_BUNDLE,
            {
                "cg14.publish.attempts": "${cg14.publish.attempts:replaceNull('0'):toNumber():plus(1)}",
            },
            1420,
            300,
        ),
        processor(
            "cg14-retry-route",
            "RouteOnAttribute — reintento acotado",
            "org.apache.nifi.processors.standard.RouteOnAttribute",
            STD_BUNDLE,
            {
                "Routing Strategy": "Route to Property Name",
                "retry": "${cg14.publish.attempts:toNumber():le(#{CG14_MAX_PUBLISH_ATTEMPTS})}",
            },
            1660,
            300,
        ),
        processor(
            "cg14-retry-target",
            "PublishKafka — reintento al destino original",
            "org.apache.nifi.processors.kafka.pubsub.PublishKafka_2_6",
            KAFKA_BUNDLE,
            {
                "bootstrap.servers": "#{CG14_BOOTSTRAP_SERVERS}",
                "topic": "${cg14.retry.topic}",
                "delivery.guarantee": "Guarantee Replicated Delivery",
                "security.protocol": "#{CG14_SECURITY_PROTOCOL}",
            },
            1900,
            300,
            autoterminate=("success",),
        ),
        processor(
            "cg14-dead-letter",
            "LogAttribute — dead-letter auditable",
            "org.apache.nifi.processors.standard.LogAttribute",
            STD_BUNDLE,
            {
                "Log Level": "warn",
                "Attributes to Log Regex": "cg14.*|kafka.*",
                "Log Payload": "false",
            },
            1900,
            520,
            autoterminate=("success",),
        ),
        processor(
            "cg14-engine-errors",
            "LogAttribute — errores del motor",
            "org.apache.nifi.processors.standard.LogAttribute",
            STD_BUNDLE,
            {
                "Log Level": "error",
                "Attributes to Log Regex": "cg14.*|kafka.*",
                "Log Payload": "false",
            },
            820,
            520,
            autoterminate=("success",),
        ),
    ]
    connections = [
        connection("c1", "cg14-consume-kafka", "cg14-source-meta", ["success"]),
        connection("c2", "cg14-source-meta", "cg14-validate", ["success"]),
        connection("c3", "cg14-validate", "cg14-route", ["success"]),
        connection("c4", "cg14-validate", "cg14-engine-errors", ["failure"]),
        connection("c5", "cg14-route", "cg14-tag-valid", ["valid"]),
        connection("c6", "cg14-route", "cg14-tag-rejected", ["rejected"]),
        connection("c7", "cg14-route", "cg14-dead-letter", ["unmatched"]),
        connection("c8", "cg14-tag-valid", "cg14-publish-valid", ["success"]),
        connection("c9", "cg14-tag-rejected", "cg14-publish-rejected", ["success"]),
        connection("c10", "cg14-publish-valid", "cg14-retry-count", ["failure"]),
        connection("c11", "cg14-publish-rejected", "cg14-retry-count", ["failure"]),
        connection("c12", "cg14-retry-count", "cg14-retry-route", ["success"]),
        connection("c13", "cg14-retry-route", "cg14-retry-target", ["retry"]),
        connection("c14", "cg14-retry-route", "cg14-dead-letter", ["unmatched"]),
        connection("c15", "cg14-retry-target", "cg14-retry-count", ["failure"]),
    ]

    def params(items):
        return {
            name: {
                "name": name,
                "value": value,
                "description": desc,
                "sensitive": False,
            }
            for name, value, desc in items
        }

    flow = {
        "encodingVersion": {"majorVersion": 2, "minorVersion": 0},
        "externalControllerServices": {},
        "parameterContexts": {
            "cg14-params-001": {
                "name": "CG14-params",
                "parameters": params(
                    [
                        (
                            "CG14_BOOTSTRAP_SERVERS",
                            "kafka:9092",
                            "CG13: broker propuesto",
                        ),
                        (
                            "CG14_RAW_TOPIC",
                            "cnc-sensors-raw",
                            "CG13: topic de entrada propuesto",
                        ),
                        (
                            "CG14_VALIDATED_TOPIC",
                            "cnc.telemetry.validated",
                            "CG13: propuesto",
                        ),
                        ("CG14_REJECTED_TOPIC", "cnc.rejected", "CG13: propuesto"),
                        ("CG14_CONSUMER_GROUP", "cnc-nifi-cg14", "grupo dedicado NiFi"),
                        (
                            "CG14_SECURITY_PROTOCOL",
                            "PLAINTEXT",
                            "CG13: subir a SASL_SSL con TLS",
                        ),
                        ("CG14_SCHEMA_VERSION", SCHEMA_VERSION, "propuesta CG14/CG03"),
                        ("CG14_MAX_LINE_BYTES", "8192", "presupuesto por línea"),
                        ("CG14_MAX_FIELD_CHARS", "512", "presupuesto por campo"),
                        ("CG14_MAX_PUBLISH_ATTEMPTS", "3", "reintentos acotados"),
                    ]
                ),
            }
        },
        "flowContents": {
            "identifier": "cnc-guard-cg14",
            "name": "CNC Guard — CG14 validación y rechazo (propuesta v0.1.0)",
            "comments": "Generado por scripts/build_cg14_nifi_flow.py desde nifi-flows/cg14_validate.groovy. NO desplegado ni probado en vivo: BLOCKED por CG03/CG13 e infra.",
            "position": {"x": 0.0, "y": 0.0},
            "processGroups": [
                {
                    "identifier": "cg14-group-001",
                    "name": "CG14 — validación y rechazo",
                    "position": {"x": 0.0, "y": 0.0},
                    "parameterContextName": "CG14-params",
                    "processGroups": [],
                    "remoteProcessGroups": [],
                    "processors": processors,
                    "connections": connections,
                    "labels": [],
                }
            ],
            "remoteProcessGroups": [],
            "processors": [],
            "connections": [],
            "labels": [],
        },
    }
    FLOW.write_text(
        json.dumps(flow, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(f"wrote {FLOW} ({FLOW.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
