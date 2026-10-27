"""Opt-in real ES regression with constructed fixtures, no training/inference.

Run from the repository root:
PYTHONPATH=.:tests python tests/verify_elasticsearch_contract.py --work-dir D:/lab/es1
Requires the project's ES image already present in the local Docker engine.
Never connects to a host ES endpoint or executes NiFi processors.
"""

import argparse
import copy
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
    reserve_bind_mounts,
    run_identity,
    write_evidence,
)
from test_es_ingest_pipeline import synthetic_prediction

from scripts.build_es_ingest_pipeline import ROOT
from scripts.image_inventory import image
from scripts.validate_contracts import validators

IMAGE = image("elasticsearch")
BASE = "28a77543bfd67a36b96ddc2f4acc103b13f62c2e"
FIELDS = ["prediction_scope", "temporal_prediction_enabled", "score_semantics"]


def run(
    output,
    work,
    baseline_ref=BASE,
    distro=None,
    image_ref=IMAGE,
    docker_host=None,
    engine_work_dir=None,
):
    runtime = DockerRuntime(image_ref, distro=distro, host=docker_host)
    if output.exists():
        raise FileExistsError("Refuse replacing verification evidence")
    work = work.resolve()
    if not (work.drive.lower() == "d:" or str(work).startswith("/mnt/d/")):
        raise ValueError("Lab data/evidence must be on D:")
    work.mkdir(parents=True, exist_ok=False)
    run_id = uuid.uuid4().hex
    sources = reserve_bind_mounts(
        runtime, work, run_id, engine_work_dir=engine_work_dir
    )
    mounts = []
    for name in ("data", "java-temp", "logs"):
        source = sources[name]
        mounts += [
            "--mount",
            f"type=bind,src={source},dst=/usr/share/elasticsearch/{name}",
        ]
    docker = runtime.prefix
    template = json.loads((ROOT / "elasticsearch/index-template.json").read_text())
    baseline = json.loads(
        subprocess.check_output(
            ["git", "show", f"{baseline_ref}:elasticsearch/index-template.json"],
            cwd=ROOT,
        )
    )
    difference = copy.deepcopy(template)
    del difference["template"]["settings"]["index.final_pipeline"]
    for field in FIELDS:
        del difference["template"]["mappings"]["properties"][field]
    assert difference == baseline, "Expected three additive mappings and final pipeline"

    image_id = runtime.resolve_image()
    container = subprocess.check_output(
        docker
        + [
            "run",
            "--detach",
            "--pull=never",
            "--name",
            "t2-es-contract-" + uuid.uuid4().hex,
            "--label",
            "t2.purpose=es-contract-regression",
            "--network=none",
            *run_identity(run_id),
            "--cap-drop=ALL",
            "--security-opt=no-new-privileges",
            "--log-driver=none",
            "--memory=1280m",
            "--memory-swap=1280m",
            "--cpus=2",
            "--pids-limit=512",
            *mounts,
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
        ],
        text=True,
    ).strip()
    evidence = {
        "baseline_ref": baseline_ref,
        "image": image_ref,
        "image_id": image_id,
        "docker_command": docker,
        "verification_id": run_id,
        "engine_work_dir": engine_work_dir,
        "engine_mounts": sources,
        "operations": [],
        "passed": False,
    }

    def request(method, path, body=None, expected=200):
        result = subprocess.run(
            docker
            + [
                "exec",
                "-i",
                container,
                "curl",
                "--silent",
                "--show-error",
                "--max-time",
                "5",
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
            input=json.dumps(body) if body is not None else "",
            text=True,
            capture_output=True,
            timeout=15,
            check=True,
        )
        text, status = result.stdout.rsplit("\n", 1)
        result_body = json.loads(text)
        evidence["operations"].append(
            {
                "method": method,
                "path": path,
                "status": int(status),
                "response": result_body,
            }
        )
        assert int(status) == expected, (path, status, result_body)
        return result_body

    try:
        inspection = runtime.verify_owned(container, run_id, image_id)
        assert inspection["HostConfig"]["NetworkMode"] == "none"
        assert not inspection["HostConfig"].get("PortBindings")
        assert len(inspection["Mounts"]) == 3
        assert all(
            m["Type"] == "bind" and m["Source"].startswith("/mnt/d/")
            for m in inspection["Mounts"]
        )
        evidence["isolation"] = {
            "network": "none",
            "published_ports": [],
            "persistent_mounts": inspection["Mounts"],
            "container_id": container,
        }
        evidence["image_id"] = inspection["Image"]
        deadline = time.monotonic() + 180
        while True:
            ready = subprocess.run(
                docker
                + [
                    "exec",
                    container,
                    "curl",
                    "--silent",
                    "--fail",
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
            if time.monotonic() >= deadline:
                raise TimeoutError("Disposable ES did not start within 180 seconds")
            time.sleep(1)

        documents = {}
        for kind in ("lab_fixture", "smb_csv"):
            document = synthetic_prediction()
            document["source"]["kind"] = kind
            validators(ROOT / "contracts")["prediction"].validate(document)
            documents[kind] = document
        evidence["fixtures"] = {
            "kind": "constructed contract documents, NOT API inference",
            "documents": documents,
        }

        # Install old template, create one existing index, and reproduce the failure.
        document = documents["lab_fixture"]
        request("PUT", "/_index_template/cnc-contract-test", baseline)
        existing = "cnc-telemetry-contract-existing"
        request("PUT", "/" + existing, {})
        document_path = f"/{existing}/_doc/{document['event_id']}"
        error = request("PUT", document_path, document, expected=400)
        assert "strict_dynamic_mapping_exception" in json.dumps(error)

        # Updating the template alone must not silently fix that existing index.
        request(
            "PUT",
            "/_ingest/pipeline/cnc-prediction-v1",
            json.loads((ROOT / "elasticsearch/ingest-pipeline.json").read_text()),
        )
        request("PUT", "/_index_template/cnc-contract-test", template)
        request("PUT", document_path, document, expected=400)
        additive = {
            field: template["template"]["mappings"]["properties"][field]
            for field in FIELDS
        }
        request(
            "PUT",
            f"/{existing}/_mapping",
            {"dynamic": "strict", "properties": additive},
        )
        request("PUT", document_path, document, expected=201)
        assert request("GET", document_path)["_source"] == document

        # New indices in both families, selected as in the inspected NiFi routes.
        for kind, suffix in [("lab_fixture", "lab-v2"), ("smb_csv", "smb-v1")]:
            document = documents[kind]
            for family in ["telemetry", "alerts"]:
                index = f"cnc-{family}-{suffix}"
                path = f"/{index}/_doc/{document['event_id']}"
                request("PUT", "/" + index, {})
                request("PUT", path + "?refresh=true", document, expected=201)
                request("PUT", path + "?refresh=true", document)
                assert request("GET", path)["_source"] == document
                assert request("GET", f"/{index}/_count")["count"] == 1
                unknown = {**document, "unexpected_contract_field": True}
                nested = copy.deepcopy(document)
                nested["source"]["unexpected_contract_field"] = True
                # The final guard runs before mapping, including pipeline=_none.
                for value in (unknown, nested):
                    rejected = f"/{index}/_doc/guard-rejected"
                    error = request("PUT", rejected + "?pipeline=_none", value, 400)
                    assert error["error"]["type"] == "script_exception", error
                    reason = error["error"]["caused_by"]
                    assert reason["type"] == "illegal_argument_exception", error
                    assert reason["reason"] == (
                        "CG18 unknown field: unexpected_contract_field"
                    ), error
                    assert request("GET", rejected, expected=404)["found"] is False
                    assert request("GET", path)["_source"] == document
                # Isolate strict mapping rather than attributing a guard error to it.
                strict = index + "-strict"
                request(
                    "PUT", "/" + strict, {"settings": {"index.final_pipeline": "_none"}}
                )
                settings = request("GET", f"/{strict}/_settings")[strict]["settings"]
                assert settings["index"]["final_pipeline"] == "_none"
                control_path = f"/{strict}/_doc/mapping-rejected"
                for scope, value in (("_doc", unknown), ("source", nested)):
                    error = request("PUT", control_path, value, expected=400)
                    assert "strict_dynamic_mapping_exception" in json.dumps(error)
                    assert error["error"]["type"] == "strict_dynamic_mapping_exception"
                    assert "[unexpected_contract_field]" in error["error"]["reason"]
                    assert f"within [{scope}]" in error["error"]["reason"]
                    assert "CG18 unknown field" not in json.dumps(error), error
                    assert request("GET", control_path, expected=404)["found"] is False
                assert request("GET", f"/{strict}/_count")["count"] == 0
                invalid_type = {
                    **document,
                    "temporal_prediction_enabled": "invalid-boolean",
                }
                request("PUT", path, invalid_type, expected=400)
                assert request("GET", path)["_source"] == document
        evidence["passed"] = True
    finally:
        primary_error = sys.exc_info()[1]
        try:
            runtime.cleanup(container, run_id, image_id, evidence, primary_error)
        finally:
            write_evidence(output, evidence, primary_error or sys.exc_info()[1])
    print(
        "PASS: old mapping rejected, additive migration and both strict index "
        "families verified; disposable container removed."
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output", type=Path, default=ROOT / "outputs/es-contract/live.json"
    )
    parser.add_argument("--baseline-ref", default=BASE)
    parser.add_argument("--work-dir", required=True, type=Path)
    add_runtime_arguments(parser, IMAGE, bind_mounts=True)
    args = parser.parse_args()
    os.environ.setdefault("PYTHONDONTWRITEBYTECODE", "1")
    run(
        args.output,
        args.work_dir,
        args.baseline_ref,
        args.docker_via_wsl,
        args.image,
        args.docker_host,
        args.engine_work_dir,
    )
