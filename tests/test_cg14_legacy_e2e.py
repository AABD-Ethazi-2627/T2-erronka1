"""Legacy runner diagnostics must never certify the RESTORE acceptance gate."""

import copy
import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "legacy_lab_test", ROOT / "deploy/cg14/scripts/run-kafka-lab-e2e.py"
)
m = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(m)


@pytest.mark.parametrize(
    "provenance", ["outage", "empty", "partial", "foreign", "complete"]
)
def test_legacy_main_cannot_accept_drain_without_reconciliation(
    tmp_path, monkeypatch, provenance
):
    export = json.loads(
        (
            ROOT
            / "nifi-flows/cg14_validation_flow_nifi_2.12.0_restore_safe_20261020.json"
        ).read_text()
    )["flowContents"]

    class Api:
        def __init__(self):
            self.sent = False
            self.topic = None
            self.rows = {
                p["name"]: {
                    "id": p["identifier"],
                    "name": p["name"],
                    "state": "STOPPED",
                    "config": {"properties": copy.deepcopy(p["properties"])},
                }
                for p in export["processors"]
            }

        def components(self):
            return self.rows

        def set_state(self, cid, state):
            next(p for p in self.rows.values() if p["id"] == cid)["state"] = state

        def call(self, path, method="GET", payload=None):
            if method == "PUT":
                return {}
            cid = path.rsplit("/", 1)[1]
            return {
                "revision": {"version": 0},
                "component": copy.deepcopy(
                    next(p for p in self.rows.values() if p["id"] == cid)
                ),
            }

        def metrics(self):
            return {
                p["id"]: {
                    k: 5 if self.sent else 0
                    for k in (
                        "flowFilesIn",
                        "flowFilesOut",
                        "taskCount",
                        "bytesIn",
                        "bytesOut",
                    )
                }
                for p in self.rows.values()
            }, 0

        def group_flow(self):
            return {"processors": [{"component": p} for p in self.rows.values()]}

    api = Api()

    def docker(*args, **kwargs):
        if args[0] == "inspect":
            return "healthy"
        if "kafka-console-producer.sh" in " ".join(args):
            api.sent = True
        if "--describe" in args:
            api.topic = args[args.index("--group") + 1].replace(
                "cg14-nifi-e2e-", "cg14-e2e-"
            )
            return "group " + api.topic + " 0 5 5 0"
        return ""

    def query(_api, topic):
        if provenance == "outage":
            raise TimeoutError("Synthetic provenance outage")
        count = {"empty": 0, "partial": 4}.get(provenance, 5)
        return [
            {
                "eventType": "RECEIVE",
                "componentName": "ConsumeKafka — CG14 synthetic E2E",
                "flowFileUuid": "delivery-" + str(i),
                "attributes": {
                    "kafka.topic": "other-topic" if provenance == "foreign" else topic,
                    "kafka.partition": "0",
                    "kafka.offset": str(i),
                },
            }
            for i in range(count)
        ]

    monkeypatch.setattr(m, "docker", docker)
    monkeypatch.setattr(m, "NifiApi", lambda env: api)
    monkeypatch.setattr(m, "read_env", dict)
    monkeypatch.setattr(m, "provenance_query", query)
    monkeypatch.setattr(m.time, "sleep", lambda seconds: None)
    monkeypatch.setattr(m, "DEPLOY", tmp_path)
    monkeypatch.setattr(sys, "argv", [str(m.__file__)])
    (tmp_path / "data/dlq").mkdir(parents=True)
    code = m.main()
    (report_path,) = (tmp_path / "data/evidence").rglob("e2e-summary.json")
    report = json.loads(report_path.read_text())
    assert api.sent and report["queue_flowfiles_after"] == 0
    assert report["offsets_after"]["lag"] == 0
    assert report["run_status"] != "VERIFIED"
    assert report["acceptance"] == "NOT_EVALUATED"
    assert report["acceptance_runner"] == "run-restore-e2e.py"
    assert code == (0 if provenance == "complete" else 1)
    assert report["run_status"] == (
        "DRAIN_OBSERVED" if provenance == "complete" else "EVIDENCE_INCOMPLETE"
    )
    assert bool(report["run_error"]) is (provenance != "complete")
