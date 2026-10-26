"""Opt-in real ES guard/replay regression; owns one new container and D: data.

No training, inference, delivery dataset, host ES, NiFi or shared volumes.
Run with PYTHONPATH=.:tests and --work-dir pointing to a NEW D: directory.
On Windows with the Fedora Docker engine add --docker-via-wsl FedoraLinux-43.
"""

import argparse
import copy
import hashlib
import json
import os
import subprocess
import sys
import time
import uuid
from pathlib import Path

from es_runtime import (
    DockerRuntime,
    add_runtime_arguments,
    cluster_uuid,
    mount_source,
    run_identity,
    write_evidence,
)
from test_es_ingest_pipeline import synthetic_prediction

from scripts.archive_consumer import event_key
from scripts.build_es_ingest_pipeline import EXPORT, PIPELINE_ID, ROOT
from scripts.image_inventory import image
from scripts.validate_contracts import validators

IMAGE = image("elasticsearch")


def verify(work, distro=None, image_ref=IMAGE, docker_host=None, engine_work_dir=None):
    runtime = DockerRuntime(image_ref, distro=distro, host=docker_host)
    work = work.resolve()
    if not (work.drive.lower() == "d:" or str(work).startswith("/mnt/d/")):
        raise ValueError("Lab data/evidence must be on D:")
    work.mkdir(parents=True, exist_ok=False)
    for name in ("data", "java-temp", "logs"):
        (work / name).mkdir()
    docker = runtime.prefix

    def command(args, **kwargs):
        return subprocess.run(
            docker + args,
            capture_output=True,
            text=True,
            check=True,
            timeout=30,
            **kwargs,
        ).stdout.strip()

    def mount(name):
        return mount_source(work, name, distro=distro, engine_work_dir=engine_work_dir)

    pipeline = json.loads(EXPORT.read_text(encoding="utf-8"))
    template_path = ROOT / "elasticsearch/index-template.json"
    template = json.loads(template_path.read_text())
    doc = synthetic_prediction()
    identity = event_key("prediction", doc)
    evidence = {
        "passed": False,
        "image": image_ref,
        "docker_command": docker,
        "engine_work_dir": engine_work_dir,
        "fixture": {
            "kind": "constructed v4 contract fixture, NOT API inference",
            "document": doc,
        },
        "artifact_sha256": {
            str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in (EXPORT, template_path)
        },
        "operations": [],
        "containers_before": command(["ps", "-aq"]).splitlines(),
    }
    container = None
    run_id = uuid.uuid4().hex
    evidence["verification_id"] = run_id

    def request(method, path, body=None, expected=200):
        raw = command(
            [
                "exec",
                "-i",
                container,
                "curl",
                "--silent",
                "--show-error",
                "--max-time",
                "8",
                "--request",
                method,
                "--header",
                "Content-Type: application/json",
                "--data-binary",
                "@-",
                "--write-out",
                "\n%{http_code}",
                "http://127.0.0.1:9200" + path,
            ],
            input="" if body is None else json.dumps(body),
        )
        response, status = raw.rsplit("\n", 1)
        response = json.loads(response)
        evidence["operations"].append(
            {
                "method": method,
                "path": path,
                "request": body,
                "status": int(status),
                "response": response,
            }
        )
        assert int(status) == expected, (path, status, response)
        return response

    def simulate(value, failure=None):
        response = request(
            "POST",
            f"/_ingest/pipeline/{PIPELINE_ID}/_simulate",
            {
                "docs": [
                    {"_index": "cnc-telemetry-g68", "_id": identity, "_source": value}
                ]
            },
        )["docs"][0]
        if failure:
            assert failure in json.dumps(response["error"]), response
        else:
            assert response["doc"]["_source"] == value, response
            assert response["doc"]["_id"] == identity
            assert response["doc"]["_index"] == "cnc-telemetry-g68"
            return response["doc"]["_source"]

    def exported_pipeline():
        installed = request("GET", f"/_ingest/pipeline/{PIPELINE_ID}")[PIPELINE_ID]
        # ES 9.5.4 adds server-managed lifecycle metadata to GET responses.
        for key in ("created_date_millis", "modified_date_millis"):
            assert isinstance(installed.pop(key), int)
        return installed

    try:
        image_id = runtime.resolve_image()
        evidence["image_id"] = image_id
        container = command(
            [
                "run",
                "--detach",
                "--pull=never",
                "--name",
                "t2-g68-" + uuid.uuid4().hex,
                "--label",
                "t2.purpose=g68-es-ingest-20261022",
                "--network=none",
                *run_identity(run_id),
                "--cap-drop=ALL",
                "--security-opt=no-new-privileges",
                "--log-driver=none",
                "--memory=1280m",
                "--memory-swap=1280m",
                "--cpus=2",
                "--pids-limit=512",
                "--mount",
                f"type=bind,src={mount('data')},dst=/usr/share/elasticsearch/data",
                "--mount",
                f"type=bind,src={mount('java-temp')},dst=/usr/share/elasticsearch/java-temp",
                "--mount",
                f"type=bind,src={mount('logs')},dst=/usr/share/elasticsearch/logs",
                "-e",
                "ES_LOG_STYLE=file",
                "-e",
                "ES_TMPDIR=/usr/share/elasticsearch/java-temp",
                "-e",
                "discovery.type=single-node",
                "-e",
                "network.host=127.0.0.1",
                "-e",
                "xpack.security.enabled=false",
                "-e",
                "xpack.ml.enabled=false",
                "-e",
                "ingest.geoip.downloader.enabled=false",
                "-e",
                "ES_JAVA_OPTS=-Xms384m -Xmx384m",
                image_id,
            ]
        )
        inspection = runtime.verify_owned(container, run_id, image_id)
        assert inspection["HostConfig"]["NetworkMode"] == "none"
        assert not inspection["HostConfig"].get("PortBindings")
        assert len(inspection["Mounts"]) == 3
        assert all(
            m["Type"] == "bind" and m["Source"].startswith("/mnt/d/")
            for m in inspection["Mounts"]
        )
        evidence["isolation"] = {
            "container_id": container,
            "network": "none",
            "published_ports": [],
            "mounts": inspection["Mounts"],
            "log_driver": "none",
        }
        deadline = time.monotonic() + 150
        while True:
            ready = subprocess.run(
                docker
                + [
                    "exec",
                    container,
                    "curl",
                    "-sf",
                    "--max-time",
                    "2",
                    "http://127.0.0.1:9200",
                ],
                capture_output=True,
                text=True,
                timeout=10,
                check=False,
            )
            if ready.returncode == 0:
                evidence["server"] = json.loads(ready.stdout)
                assert evidence["server"]["version"]["number"] == "9.5.5"
                evidence["cluster_uuid"] = cluster_uuid(evidence["server"])
                break
            state = json.loads(command(["inspect", container]))[0]["State"]
            if not state["Running"]:
                evidence["startup_failure"] = state
                raise RuntimeError(f"Own ES exited; inspect {work / 'logs'}")
            if time.monotonic() > deadline:
                raise TimeoutError("Own ES container not ready after 150s")
            time.sleep(1)

        # Negative control: strict mapping alone accepts wrong current-state semantics.
        baseline = copy.deepcopy(template)
        del baseline["template"]["settings"]["index.final_pipeline"]
        request("PUT", "/cnc-telemetry-g68-control", baseline["template"])
        invalid = {**doc, "temporal_prediction_enabled": True}
        request("PUT", "/cnc-telemetry-g68-control/_doc/control", invalid, expected=201)
        evidence["negative_control"] = (
            "Mapping alone accepted forbidden temporal semantics"
        )

        request("PUT", f"/_ingest/pipeline/{PIPELINE_ID}", pipeline)
        request("PUT", f"/_ingest/pipeline/{PIPELINE_ID}", pipeline)
        assert exported_pipeline() == pipeline
        conflict = request(
            "PUT",
            f"/_ingest/pipeline/{PIPELINE_ID}?if_version=999",
            pipeline,
            expected=400,
        )
        assert "version conflict" in conflict["error"]["reason"]
        assert exported_pipeline() == pipeline
        assert simulate(simulate(doc)) == doc
        for kind in ("smb_csv", "statement_example"):
            simulate({**doc, "source": {**doc["source"], "kind": kind}})
        full = {
            **doc,
            "machine_type": "L",
            "air_temp_K": 298.1,
            "process_temp_K": 308.6,
            "rpm": 1551.0,
            "torque_Nm": 42.8,
            "tool_wear_min": 0.0,
            "alert_level": "OK",
        }
        validators(ROOT / "contracts")["prediction"].validate(full)
        simulate(full)
        bad_cases = [
            (invalid, "CG18 const"),
            ({**doc, "machine_failure": 1}, "CG18 unknown field"),
            ({**doc, "ground_truth": "invalid-test-field"}, "CG18 unknown field"),
            ({**doc, "unexpected": True}, "CG18 unknown field"),
            (
                {**doc, "source": {**doc["source"], "raw_record": "forbidden"}},
                "CG18 unknown field",
            ),
            (
                {**doc, "source": {**doc["source"], "unexpected": True}},
                "CG18 unknown field",
            ),
            ({**doc, "failure_score": "0.2"}, "CG18 type"),
            ({**doc, "risk_alert": "false"}, "CG18 type"),
            ({**doc, "failure_score": 1.1}, "CG18 range"),
            (
                {**doc, "source": {**doc["source"], "kind": "physical-ground-truth"}},
                "CG18 enum",
            ),
            ({**doc, "prediction_scope": "24h"}, "CG18 const"),
            ({**doc, "score_semantics": "calibrated_probability"}, "CG18 const"),
            ({k: v for k, v in doc.items() if k != "scored_at"}, "CG18 required"),
        ]
        for value, failure in bad_cases:
            simulate(value, failure)

        request("PUT", "/_index_template/cnc-g68", template)
        # New indices fail closed if the configured final pipeline is missing.
        request("DELETE", f"/_ingest/pipeline/{PIPELINE_ID}")
        request("PUT", "/cnc-telemetry-g68-missing/_doc/missing", doc, expected=400)
        request("PUT", f"/_ingest/pipeline/{PIPELINE_ID}", pipeline)
        for family in ("telemetry", "alerts"):
            index = f"cnc-{family}-g68"
            request("PUT", "/" + index, {})
            path = f"/{index}/_create/{identity}?refresh=true"
            request("PUT", path, doc, expected=201)
            request("PUT", path, doc, expected=409)
            # Same immutable identity with different bytes must never overwrite.
            changed = {**doc, "scored_at": "2026-10-15T08:47:12Z"}
            request("PUT", path, changed, expected=409)
            assert request("GET", f"/{index}/_doc/{identity}")["_source"] == doc
            assert request("GET", f"/{index}/_count")["count"] == 1
            for value, failure in bad_cases:
                response = request(
                    "PUT", f"/{index}/_doc/rejected?pipeline=_none", value, expected=400
                )
                assert failure in json.dumps(response), response
            # Mapping layer is independently strict even when no pipeline is configured.
            strict = index + "-strict"
            request(
                "PUT", "/" + strict, {"settings": {"index.final_pipeline": "_none"}}
            )
            for value in (
                {**doc, "unknown": True},
                {**doc, "source": {**doc["source"], "unknown": True}},
            ):
                error = request("PUT", f"/{strict}/_doc/bad", value, expected=400)
                assert "strict_dynamic_mapping_exception" in json.dumps(error)
            request(
                "PUT",
                f"/{strict}/_doc/bad",
                {**doc, "failure_score": "bad-double"},
                expected=400,
            )
            assert request("GET", f"/{strict}/_count")["count"] == 0
            assert request("GET", f"/{index}/_count")["count"] == 1
            alternate = {**doc, "model_artifact_sha256": "a" * 64}
            alternate_id = event_key("prediction", alternate)
            assert alternate_id != identity
            request(
                "PUT",
                f"/{index}/_create/{alternate_id}?refresh=true",
                alternate,
                expected=201,
            )
            assert request("GET", f"/{index}/_doc/{identity}")["_source"] == doc
            assert request("GET", f"/{index}/_count")["count"] == 2
            legacy = index + "-nifi"
            legacy_path = f"/{legacy}/_doc/{doc['event_id']}?refresh=true"
            request("PUT", legacy_path, doc, expected=201)
            request("PUT", legacy_path, doc)
            assert request("GET", f"/{legacy}/_doc/{doc['event_id']}")["_source"] == doc
            assert request("GET", f"/{legacy}/_count")["count"] == 1
        evidence["passed"] = True
    finally:
        primary_error = sys.exc_info()[1]
        try:
            if container:
                runtime.cleanup(container, run_id, image_id, evidence, primary_error)
            try:
                evidence["containers_after"] = command(["ps", "-aq"]).splitlines()
            except (OSError, subprocess.SubprocessError) as exc:
                evidence["passed"] = False
                evidence["containers_after_error_type"] = type(exc).__name__
                if primary_error is None:
                    raise
                primary_error.add_note(
                    "ES post-cleanup inventory failed: " + type(exc).__name__
                )
        finally:
            write_evidence(
                work / "result.json", evidence, primary_error or sys.exc_info()[1]
            )
    print(
        "PASS: real ES simulate, final guard, strict mapping and immutable replay; "
        "own container removed"
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--work-dir", required=True, type=Path)
    add_runtime_arguments(parser, IMAGE, bind_mounts=True)
    args = parser.parse_args()
    os.environ.setdefault("PYTHONDONTWRITEBYTECODE", "1")
    verify(
        args.work_dir,
        args.docker_via_wsl,
        args.image,
        args.docker_host,
        args.engine_work_dir,
    )
