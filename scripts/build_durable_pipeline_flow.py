"""Export a disabled NiFi 2.12 staged-input bridge; never a Kafka offset owner."""

import argparse
import json
import uuid
from pathlib import Path


def identifier(name):
    return str(uuid.uuid5(uuid.NAMESPACE_URL, "urn:cnc:cg14:durable-staged:v1:" + name))


def build():
    group = identifier("group")
    bundle = {
        "group": "org.apache.nifi",
        "artifact": "nifi-standard-nar",
        "version": "2.12.0",
    }

    def port(name, kind, y):
        return {
            "identifier": identifier(name),
            "name": name,
            "type": kind,
            "position": {"x": 900.0 if kind == "OUTPUT_PORT" else 0.0, "y": y},
            "scheduledState": "DISABLED",
            "concurrentlySchedulableTaskCount": 1,
        }

    def processor(name, kind, props, x):
        return {
            "identifier": identifier(name),
            "name": name,
            "type": "org.apache.nifi.processors.standard." + kind,
            "bundle": bundle,
            "position": {"x": x, "y": 100.0},
            "properties": props,
            "propertyDescriptors": {},
            "scheduledState": "DISABLED",
            "schedulingStrategy": "TIMER_DRIVEN",
            "schedulingPeriod": "1 sec",
            "concurrentlySchedulableTaskCount": 1,
            "executionNode": "ALL",
            "bulletinLevel": "WARN",
            "penaltyDuration": "30 sec",
            "yieldDuration": "1 sec",
            "runDurationMillis": 0,
            "autoTerminatedRelationships": [],
        }

    def connection(name, source, source_type, target, target_type, relationship):
        return {
            "identifier": identifier(name),
            "name": name,
            "source": {"id": identifier(source), "type": source_type, "groupId": group},
            "destination": {
                "id": identifier(target),
                "type": target_type,
                "groupId": group,
            },
            "selectedRelationships": [relationship],
            "labelIndex": 0,
            "zIndex": 0,
            "bends": [],
            "prioritizers": [],
            "loadBalanceStrategy": "DO_NOT_LOAD_BALANCE",
            "loadBalanceCompression": "DO_NOT_COMPRESS",
            "backPressureObjectThreshold": 100,
            "backPressureDataSizeThreshold": "10 MB",
            "flowFileExpiration": "0 sec",
        }

    args = [
        "-m",
        "scripts.run_durable_pipeline",
        "--root",
        "#{DURABLE_ROOT}",
        "--manifest",
        "#{PINNED_MANIFEST}",
        "--source-namespace",
        "#{SOURCE_NAMESPACE}",
        "--source-kind",
        "#{SOURCE_KIND}",
        "--scoring-url",
        "#{SCORING_URL}",
        "stdin",
        "--topic",
        "${kafka.topic}",
        "--partition",
        "${kafka.partition}",
        "--offset",
        "${kafka.offset}",
    ]
    execute = processor(
        "Durable staged CSV",
        "ExecuteStreamCommand",
        {
            "Working Directory": "#{WORKER_CHECKOUT}",
            "Command Path": "#{WORKER_PYTHON}",
            "Command Arguments Strategy": "Command Arguments Property",
            "Command Arguments": ";".join(args),
            "Argument Delimiter": ";",
            "Ignore STDIN": "false",
        },
        250.0,
    )
    route = processor(
        "Retain original by exit status",
        "RouteOnAttribute",
        {
            "Routing Strategy": "Route to Property name",
            "completed": "${execution.status:equals('0')}",
        },
        550.0,
    )
    return {
        "flowContents": {
            "identifier": group,
            "name": "CG14 durable staged bridge (opt-in)",
            "comments": "Disabled staged-input bridge. "
            "Worker disk journal/archive own durability. "
            "No ConsumeKafka and no source offset acknowledgement. "
            "Retain originals and failures. "
            "Configure all parameters and original coordinates "
            "before enabling in an isolated lab. "
            "No ES configured in this export; "
            "use the primary Kafka worker for optional ES.",
            "position": {"x": 0.0, "y": 0.0},
            "processGroups": [],
            "remoteProcessGroups": [],
            "controllerServices": [],
            "funnels": [],
            "labels": [],
            "inputPorts": [port("staged-csv", "INPUT_PORT", 100.0)],
            "outputPorts": [
                port(name, "OUTPUT_PORT", float(i * 150))
                for i, name in enumerate(
                    (
                        "completed-original",
                        "failed-original",
                        "durable-receipt",
                        "failed-receipt",
                    )
                )
            ],
            "processors": [execute, route],
            "connections": [
                connection(
                    "input",
                    "staged-csv",
                    "INPUT_PORT",
                    "Durable staged CSV",
                    "PROCESSOR",
                    "",
                ),
                connection(
                    "original",
                    "Durable staged CSV",
                    "PROCESSOR",
                    "Retain original by exit status",
                    "PROCESSOR",
                    "original",
                ),
                connection(
                    "completed",
                    "Retain original by exit status",
                    "PROCESSOR",
                    "completed-original",
                    "OUTPUT_PORT",
                    "completed",
                ),
                connection(
                    "failed",
                    "Retain original by exit status",
                    "PROCESSOR",
                    "failed-original",
                    "OUTPUT_PORT",
                    "unmatched",
                ),
                connection(
                    "receipt",
                    "Durable staged CSV",
                    "PROCESSOR",
                    "durable-receipt",
                    "OUTPUT_PORT",
                    "output stream",
                ),
                connection(
                    "error",
                    "Durable staged CSV",
                    "PROCESSOR",
                    "failed-receipt",
                    "OUTPUT_PORT",
                    "nonzero status",
                ),
            ],
        }
    }


def main(argv=None):
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--output", required=True, type=Path)
    args = cli.parse_args(argv)
    # Caller chooses a fresh file; never replace a reviewed/runtime definition.
    with args.output.open("x", encoding="utf-8", newline="\n") as handle:
        json.dump(build(), handle, indent=2, ensure_ascii=False)
        handle.write("\n")


if __name__ == "__main__":
    main()
