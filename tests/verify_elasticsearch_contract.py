"""Opt-in real ES regression in a disposable container with no network or volumes.

Run from the repository root:
PYTHONPATH=.:tests python tests/verify_elasticsearch_contract.py
Requires the project's ES image already present in the local Docker engine.
Never connects to a host ES endpoint or executes NiFi processors.
"""

import argparse
import asyncio
import copy
import json
import subprocess
import tempfile
import time
import uuid
from pathlib import Path

from api_client import api_client
from test_elasticsearch_contract import ROOT, fixture_bundle

from scoring.score_api import create_app

IMAGE = "docker.elastic.co/elasticsearch/elasticsearch:9.5.4"
BASE = "28a77543bfd67a36b96ddc2f4acc103b13f62c2e"
FIELDS = ["prediction_scope", "temporal_prediction_enabled", "score_semantics"]


def run(output, baseline_ref=BASE):
    if output.exists():
        raise FileExistsError("Refuse replacing verification evidence")
    template = json.loads((ROOT / "elasticsearch/index-template.json").read_text())
    baseline = json.loads(
        subprocess.check_output(
            ["git", "show", f"{baseline_ref}:elasticsearch/index-template.json"],
            cwd=ROOT,
        )
    )
    difference = copy.deepcopy(template)
    for field in FIELDS:
        del difference["template"]["mappings"]["properties"][field]
    assert difference == baseline, "Expected only the three additive field mappings"

    container = subprocess.check_output(
        [
            "docker",
            "run",
            "--detach",
            "--pull=never",
            "--name",
            "t2-es-contract-" + uuid.uuid4().hex,
            "--label",
            "t2.purpose=es-contract-regression",
            "--network=none",
            "--cap-drop=ALL",
            "--security-opt=no-new-privileges",
            "--memory=1280m",
            "--memory-swap=1280m",
            "--cpus=2",
            "--pids-limit=512",
            "--tmpfs",
            "/usr/share/elasticsearch/data:rw,uid=1000,gid=0,size=512m",
            "-e",
            "discovery.type=single-node",
            "-e",
            "network.host=127.0.0.1",
            "-e",
            "xpack.security.enabled=false",
            "-e",
            "ingest.geoip.downloader.enabled=false",
            "-e",
            "ES_JAVA_OPTS=-Xms384m -Xmx384m",
            IMAGE,
        ],
        text=True,
    ).strip()
    evidence = {
        "baseline_ref": baseline_ref,
        "image": IMAGE,
        "operations": [],
        "passed": False,
    }

    def request(method, path, body=None, expected=200):
        result = subprocess.run(
            [
                "docker",
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
        inspection = json.loads(
            subprocess.check_output(["docker", "inspect", container])
        )[0]
        assert inspection["HostConfig"]["NetworkMode"] == "none"
        assert not inspection["HostConfig"].get("PortBindings")
        assert all(m["Type"] == "tmpfs" for m in inspection["Mounts"])
        evidence["isolation"] = {
            "network": "none",
            "published_ports": [],
            "persistent_mounts": [],
        }
        evidence["image_id"] = inspection["Image"]
        deadline = time.monotonic() + 180
        while True:
            ready = subprocess.run(
                [
                    "docker",
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
                break
            if time.monotonic() >= deadline:
                raise TimeoutError("Disposable ES did not start within 180 seconds")
            time.sleep(1)

        with tempfile.TemporaryDirectory() as directory:
            manifest = fixture_bundle(Path(directory))
            documents = {}
            evidence["api_exchanges"] = []

            async def collect_predictions():
                async with api_client(create_app(manifest)) as client:
                    payload = json.loads(
                        (ROOT / "contracts/examples/valid/telemetry.json").read_text()
                    )
                    for kind in ["lab_fixture", "smb_csv"]:
                        payload["source"] = {
                            "kind": kind,
                            "uri": "fixture://es-contract",
                            "record_ref": "synthetic-row-1",
                        }
                        response = await client.post("/predict", json=payload)
                        assert response.status_code == 200, response.text
                        documents[kind] = response.json()
                        assert documents[kind]["anomaly_alert"]
                        evidence["api_exchanges"].append(
                            {
                                "request": copy.deepcopy(payload),
                                "response": documents[kind],
                            }
                        )

            asyncio.run(collect_predictions())

        # Install old template, create one existing index, and reproduce the failure.
        document = documents["lab_fixture"]
        request("PUT", "/_index_template/cnc-contract-test", baseline)
        existing = "cnc-telemetry-contract-existing"
        request("PUT", "/" + existing, {})
        document_path = f"/{existing}/_doc/{document['event_id']}"
        error = request("PUT", document_path, document, expected=400)
        assert "strict_dynamic_mapping_exception" in json.dumps(error)

        # Updating the template alone must not silently fix that existing index.
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
                error = request("PUT", path, unknown, expected=400)
                assert "strict_dynamic_mapping_exception" in json.dumps(error)
                nested = copy.deepcopy(document)
                nested["source"]["unexpected_contract_field"] = True
                error = request("PUT", path, nested, expected=400)
                assert "strict_dynamic_mapping_exception" in json.dumps(error)
                invalid_type = {
                    **document,
                    "temporal_prediction_enabled": "invalid-boolean",
                }
                request("PUT", path, invalid_type, expected=400)
                assert request("GET", path)["_source"] == document
        evidence["passed"] = True
    finally:
        # Only remove the exact container ID created above, including on failure.
        subprocess.run(
            ["docker", "rm", "--force", container], check=True, capture_output=True
        )
        evidence["container_removed"] = True
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(evidence, indent=2) + "\n")
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
    args = parser.parse_args()
    run(args.output, args.baseline_ref)
