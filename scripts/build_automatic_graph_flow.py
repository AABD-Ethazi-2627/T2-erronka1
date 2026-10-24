"""Disabled NiFi 2.12 autonomous scheduler for the single Kafka offset owner."""

import argparse
import json
from pathlib import Path

from scripts.build_durable_pipeline_flow import identifier as staged_identifier


def identifier(name):
    return staged_identifier("automatic-v1/" + name)


def build():
    group = identifier("group")

    def processor(name, kind, props, x, y, terminated=()):
        return {
            "identifier": identifier(name),
            "name": name,
            "type": "org.apache.nifi.processors.standard." + kind,
            "bundle": {
                "group": "org.apache.nifi",
                "artifact": "nifi-standard-nar",
                "version": "2.12.0",
            },
            "position": {"x": float(x), "y": float(y)},
            "properties": props,
            "propertyDescriptors": {},
            "scheduledState": "DISABLED",
            "schedulingStrategy": "TIMER_DRIVEN",
            "schedulingPeriod": "5 sec",
            "concurrentlySchedulableTaskCount": 1,
            "executionNode": "ALL",
            "bulletinLevel": "WARN",
            "penaltyDuration": "30 sec",
            "yieldDuration": "1 sec",
            "runDurationMillis": 0,
            "autoTerminatedRelationships": list(terminated),
        }

    def connection(name, source, target, relationship):
        return {
            "identifier": identifier(name),
            "name": name,
            "source": {"id": identifier(source), "type": "PROCESSOR", "groupId": group},
            "destination": {
                "id": identifier(target),
                "type": "PROCESSOR",
                "groupId": group,
            },
            "selectedRelationships": [relationship],
            "labelIndex": 0,
            "zIndex": 0,
            "bends": [],
            "prioritizers": [],
            "loadBalanceStrategy": "DO_NOT_LOAD_BALANCE",
            "loadBalanceCompression": "DO_NOT_COMPRESS",
            "backPressureObjectThreshold": 1,
            "backPressureDataSizeThreshold": "1 MB",
            "flowFileExpiration": "0 sec",
        }

    trigger = processor(
        "Schedule bounded source cycle",
        "GenerateFlowFile",
        {
            "File Size": "0B",
            "Batch Size": "1",
            "Data Format": "Text",
            "Unique FlowFiles": "false",
        },
        0,
        0,
    )
    trigger["schedulingPeriod"] = "30 sec"
    execute = processor(
        "Single Kafka owner",
        "ExecuteStreamCommand",
        {
            "Working Directory": "#{WORKER_CHECKOUT}",
            "Command Path": "#{WORKER_PYTHON}",
            "Command Arguments Strategy": "Command Arguments Property",
            "Command Arguments": (
                "-B;-m;scripts.run_automatic_graph;--config;#{GRAPH_CONFIG}"
            ),
            "Argument Delimiter": ";",
            "Ignore STDIN": "true",
            "TMPDIR": "#{PROCESS_TEMP}",
            "TMP": "#{PROCESS_TEMP}",
            "TEMP": "#{PROCESS_TEMP}",
            "PYTHONDONTWRITEBYTECODE": "1",
            "PYTHONUNBUFFERED": "1",
        },
        350,
        0,
    )
    attributes = processor(
        "Capture cycle exit diagnostics",
        "AttributesToJSON",
        {
            "Attributes List": (
                "uuid,filename,execution.status,execution.error,"
                "execution.command,execution.command.args"
            ),
            "Destination": "flowfile-content",
            "Include Core Attributes": "true",
        },
        700,
        200,
    )
    sinks = [
        processor(
            name,
            "PutFile",
            {
                "Directory": "#{CYCLE_REPORTS}/" + directory,
                "Conflict Resolution Strategy": "fail",
                "Create Missing Directories": "true",
            },
            1050,
            y,
            ("success",),
        )
        for name, directory, y in (
            ("Retain cycle output", "output", 0),
            ("Retain cycle diagnostics", "diagnostics", 200),
        )
    ]
    return {
        "flowContents": {
            "identifier": group,
            "name": "CG14 automatic durable graph (single node)",
            "comments": "NiFi schedules the built-in Kafka worker. "
            "Only that worker commits explicit offsets after CG15/required ES. "
            "No ConsumeKafka, archive consumer or second owner on the raw group. "
            "Single node; preserve root, API ledger and Kafka generation. "
            "FlowFile outputs are diagnostics, never authorization to ACK Kafka.",
            "position": {"x": 0.0, "y": 0.0},
            "processGroups": [],
            "remoteProcessGroups": [],
            "controllerServices": [],
            "funnels": [],
            "labels": [],
            "inputPorts": [],
            "outputPorts": [],
            "processors": [trigger, execute, attributes, *sinks],
            "connections": [
                connection("tick", trigger["name"], execute["name"], "success"),
                connection("exit", execute["name"], attributes["name"], "original"),
                connection(
                    "output", execute["name"], sinks[0]["name"], "output stream"
                ),
                connection(
                    "error", execute["name"], sinks[0]["name"], "nonzero status"
                ),
                connection(
                    "diagnostics", attributes["name"], sinks[1]["name"], "success"
                ),
                connection(
                    "retry-diagnostics",
                    attributes["name"],
                    attributes["name"],
                    "failure",
                ),
                *[
                    connection(
                        "retry-" + sink["name"], sink["name"], sink["name"], "failure"
                    )
                    for sink in sinks
                ],
            ],
        }
    }


def main(argv=None):
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--output", required=True, type=Path)
    args = cli.parse_args(argv)
    with args.output.open("x", encoding="utf-8", newline="\n") as handle:
        json.dump(build(), handle, ensure_ascii=False, indent=2)
        handle.write("\n")


if __name__ == "__main__":
    main()
