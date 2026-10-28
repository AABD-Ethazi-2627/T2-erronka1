"""Opt-in real loopback HTTP + isolated ES; no Apache Kafka/NiFi or training.

PYTHONPATH=.:tests python tests/verify_durable_pipeline.py --output NEW.json
Requires an existing ES image in the local Docker engine; never pulls images.
"""

import argparse
import asyncio
import copy
import json
import socket
import subprocess
import sys
import tempfile
import time
import uuid
from contextlib import closing
from pathlib import Path
from threading import Thread
from urllib.parse import urlsplit

import httpx
import uvicorn
from es_runtime import (
    DockerRuntime,
    add_runtime_arguments,
    cluster_uuid,
    run_identity,
    write_evidence,
)
from test_cg14_durable_pipeline import NAMESPACE, RAW, message
from test_scoring_replay import AnomalyDouble, RiskDouble, manifest

from scoring.score_api import create_app
from scripts.archive_consumer import consume as archive
from scripts.archive_consumer import digest, event_key
from scripts.durable_pipeline import Pipeline, PipelineBlocked, encoded
from scripts.image_inventory import image

IMAGE = image("elasticsearch")


async def verify(output, distro=None, image_ref=IMAGE, docker_host=None):
    runtime = DockerRuntime(image_ref, distro=distro, host=docker_host)
    run_id = uuid.uuid4().hex
    if output.exists():
        raise FileExistsError("Refuse replacing verification evidence")
    # Reserve the evidence filename before starting any process/container.
    with output.open("x") as handle:
        handle.write('{"status":"RUNNING"}\n')
    evidence = {
        "status": "RUNNING",
        "image": image_ref,
        "docker_command": runtime.prefix,
        "verification_id": run_id,
        "transport": "real-loopback-http+docker-exec-es",
        "kafka": "NOT_EXECUTED",
        "nifi": "NOT_EXECUTED",
        "models": "in-memory-synthetic-doubles-no-training",
        "operations": [],
    }
    evidence["python"] = sys.version
    evidence["execution_files_sha256"] = {
        name: digest(Path(name).read_bytes())
        for name in (
            "tests/verify_durable_pipeline.py",
            "tests/es_runtime.py",
            "scripts/durable_pipeline.py",
            "scripts/run_durable_pipeline.py",
            "scripts/kafka_archive.py",
            "scripts/archive_consumer.py",
            "scripts/cg14_occurrence.py",
            "scripts/cg14_scoring_bridge.py",
            "cg14_validation/validator.py",
            "scripts/validate_contracts.py",
            "scoring/score_api.py",
            "scoring/response_ledger.py",
        )
    }
    container = None
    server = None
    thread = None
    listener = socket.socket()

    def command(args, **kwargs):
        if args[0] == "docker":
            args = runtime.prefix + args[1:]
        return subprocess.run(
            args, capture_output=True, check=True, timeout=30, **kwargs
        )

    try:
        image_id = runtime.resolve_image()
        evidence["image_id"] = image_id
        container = command(
            [
                "docker",
                "run",
                "--detach",
                "--pull=never",
                "--name",
                "t2-durable-" + uuid.uuid4().hex,
                "--label",
                "t2.purpose=durable-pipeline-verification",
                "--network=none",
                *run_identity(run_id),
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
                image_id,
            ],
            text=True,
        ).stdout.strip()
        evidence["container"] = container
        info = runtime.verify_owned(container, run_id, image_id)
        assert info["HostConfig"]["NetworkMode"] == "none"
        assert not info["HostConfig"].get("PortBindings")
        assert all(m["Type"] == "tmpfs" for m in info["Mounts"])
        assert set(info["HostConfig"].get("Tmpfs", {})) == {
            "/usr/share/elasticsearch/data"
        }
        evidence["isolation"] = {
            "network": "none",
            "published_ports": [],
            "mounts": info["Mounts"],
            "tmpfs": info["HostConfig"]["Tmpfs"],
        }

        def es(method, path, raw=b""):
            result = command(
                [
                    "docker",
                    "exec",
                    "-i",
                    container,
                    "curl",
                    "--silent",
                    "--show-error",
                    "--max-time",
                    "10",
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
                input=raw,
            )
            body, status = result.stdout.rsplit(b"\n", 1)
            response = httpx.Response(int(status), content=body)
            evidence["operations"].append(
                {"method": method, "path": path, "status": int(status)}
            )
            return response

        deadline = time.monotonic() + 180
        while True:
            try:
                ready = await asyncio.to_thread(es, "GET", "/")
                if ready.status_code == 200:
                    evidence["es_version"] = ready.json()["version"]["number"]
                    evidence["cluster_uuid"] = cluster_uuid(ready.json())
                    break
            except subprocess.CalledProcessError:
                pass  # fresh disposable server is still booting, bounded below
            if time.monotonic() > deadline:
                raise TimeoutError("Isolated ES did not start in 180s")
            await asyncio.sleep(1)
        pipeline = Path("elasticsearch/ingest-pipeline.json").read_bytes()
        assert (
            await asyncio.to_thread(
                es, "PUT", "/_ingest/pipeline/cnc-prediction-v1", pipeline
            )
        ).status_code == 200
        template = json.loads(Path("elasticsearch/index-template.json").read_text())
        assert (
            await asyncio.to_thread(
                es, "PUT", "/_index_template/cnc-durable", json.dumps(template).encode()
            )
        ).status_code == 200
        index = "cnc-telemetry-durable-test"
        settings = {
            "settings": {
                "number_of_replicas": 0,
                "index.translog.durability": "request",
            }
        }
        assert (
            await asyncio.to_thread(
                es, "PUT", "/" + index, json.dumps(settings).encode()
            )
        ).status_code == 200
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config = manifest()
            app = create_app(root / "absent.json", ledger_path=root / "api.sqlite3")
            risk = RiskDouble()
            app.state.models = {"rf.pkl": risk, "if.pkl": AnomalyDouble()}
            app.state.manifest = config
            listener.bind(("127.0.0.1", 0))
            listener.listen()
            address = f"http://127.0.0.1:{listener.getsockname()[1]}"
            server = uvicorn.Server(
                uvicorn.Config(app, lifespan="off", log_level="error", access_log=False)
            )
            thread = Thread(
                target=server.run, kwargs={"sockets": [listener]}, daemon=True
            )
            thread.start()
            async with httpx.AsyncClient(trust_env=False) as client:
                for _ in range(100):
                    if server.started:
                        break
                    await asyncio.sleep(0.05)
                assert server.started

                class Transport:
                    async def request(self, method, url, **kwargs):
                        if url.startswith("http://isolated-es/"):
                            parsed = urlsplit(url)
                            path = parsed.path + (
                                "?" + parsed.query if parsed.query else ""
                            )
                            return await asyncio.to_thread(
                                es, method, path, kwargs.get("content", b"")
                            )
                        return await client.request(method, url, **kwargs)

                worker = Pipeline(
                    root / "worker",
                    Transport(),
                    namespace=NAMESPACE,
                    manifest=config,
                    scoring_url=address + "/predict",
                    es_url="http://isolated-es",
                    es_index=index,
                )
                acks = []
                first = await worker.consume(
                    [message(0), message(1), message(2, b"bad,csv")],
                    lambda: acks.append(True),
                )
                assert first == {"completed": 2, "rejected": 1, "replay": 0}
                assert risk.calls == 2
                outputs = list((root / "worker/outbox/prediction").glob("*.json"))
                assert len(outputs) == 2
                before = {
                    p: p.read_bytes() for p in (root / "worker").rglob("*.parquet")
                }
                # Simulate crash after ES create but before the local done commit.
                import sqlite3

                with (
                    closing(sqlite3.connect(root / "worker/pipeline.sqlite3")) as con,
                    con,
                ):
                    con.execute(
                        "UPDATE jobs SET outcome=NULL WHERE outcome='completed'"
                    )
                replay = await worker.consume(
                    [message(0), message(1), message(2, b"bad,csv")],
                    lambda: acks.append(True),
                )
                assert replay == {"completed": 2, "rejected": 0, "replay": 1}
                assert risk.calls == 2
                assert acks == [True, True]
                assert before == {p: p.read_bytes() for p in before}
                for path in outputs:
                    prediction = json.loads(path.read_bytes())
                    identity = event_key("prediction", prediction)
                    result = await asyncio.to_thread(
                        es, "GET", f"/{index}/_doc/{identity}"
                    )
                    assert (
                        result.status_code == 200
                        and result.json()["_source"] == prediction
                    )
                assert (
                    root / f"worker/raw/{digest(message(0)[0].encode())}.bin"
                ).read_bytes() == RAW
                pinned = root / "pinned-manifest.json"
                pinned.write_text(json.dumps(config))
                staged_args = [
                    sys.executable,
                    "-B",
                    "-m",
                    "scripts.run_durable_pipeline",
                    "--root",
                    str(root / "staged-worker"),
                    "--manifest",
                    str(pinned),
                    "--source-namespace",
                    NAMESPACE,
                    "--scoring-url",
                    address + "/predict",
                    "stdin",
                    "--topic",
                    "raw",
                    "--partition",
                    "0",
                    "--offset",
                    "0",
                ]
                receipts = []
                for _ in range(2):
                    child = await asyncio.to_thread(command, staged_args, input=RAW)
                    receipts.append(json.loads(child.stdout))
                assert receipts[0]["completed"] == 1 and receipts[1]["replay"] == 1
                assert all(receipt["source_ack"] is False for receipt in receipts)
                assert risk.calls == 2
                failure_cases = []
                for stream in ("telemetry", "prediction"):
                    conflict_root = root / ("conflict-" + stream)
                    payload = json.loads(
                        next(
                            (root / "worker/outbox" / stream).glob("*.json")
                        ).read_bytes()
                    )
                    # Match the selected occurrence, regardless of directory order.
                    offset = (
                        0
                        if payload["event_id"]
                        == json.loads(
                            (
                                root
                                / "worker/identity"
                                / (digest(message(0)[0].encode()) + ".json")
                            ).read_bytes()
                        )["telemetry"]["event_id"]
                        else 1
                    )
                    stale = copy.deepcopy(payload)
                    stale["rpm"] = 1501
                    assert (
                        archive(
                            conflict_root / "archive",
                            [("prior", stream, encoded(stale))],
                            lambda: None,
                        )["stored"]
                        == 1
                    )
                    blocked_acks = []
                    operations = len(evidence["operations"])
                    for _ in range(4):
                        blocked = Pipeline(
                            conflict_root,
                            Transport(),
                            namespace=NAMESPACE,
                            manifest=config,
                            scoring_url=address + "/predict",
                            es_url="http://isolated-es",
                            es_index=index,
                        )
                        try:
                            await blocked.consume(
                                [message(offset)],
                                lambda blocked_acks=blocked_acks: blocked_acks.append(
                                    True
                                ),
                            )
                        except PipelineBlocked:
                            pass
                        else:
                            raise AssertionError("Rejected receipt became successful")
                    assert not blocked_acks and risk.calls == 2
                    assert len(evidence["operations"]) == operations
                    failure_cases.append(
                        {"stream": stream, "attempts": 4, "acks": 0, "es_calls": 0}
                    )
                # A real ES content conflict must block even a completed job.
                prediction = json.loads(outputs[0].read_bytes())
                identity = event_key("prediction", prediction)
                stale = copy.deepcopy(prediction)
                stale["rpm"] = 1501
                assert (
                    await asyncio.to_thread(
                        es, "PUT", f"/{index}/_doc/{identity}", encoded(stale)
                    )
                ).status_code == 200
                before_failed_ack = len(acks)
                try:
                    await worker.consume(
                        [message(0), message(1)], lambda: acks.append(False)
                    )
                except PipelineBlocked:
                    pass
                else:
                    raise AssertionError("ES conflict became successful")
                assert len(acks) == before_failed_ack and risk.calls == 2
                failure_cases.append(
                    {
                        "stream": "es",
                        "acks": 0,
                        "conflict": "real _create 409 and GET mismatch",
                    }
                )
                evidence.update(
                    status="PASSED",
                    first=first,
                    replay=replay,
                    source_ack_calls=len(acks),
                    synthetic_inference_calls=risk.calls,
                    archive_objects=len(before),
                    prediction_hashes=[digest(p.read_bytes()) for p in outputs],
                    raw_sha256=digest(RAW),
                    scoring_transport="HTTP over 127.0.0.1 ephemeral port",
                    staged_process_receipts=receipts,
                    required_destination_failures=failure_cases,
                )
    except BaseException as exc:
        evidence.update(status="FAILED", error=type(exc).__name__ + ": " + str(exc))
        raise
    finally:
        primary_error = sys.exc_info()[1]
        if server:
            server.should_exit = True
        if thread:
            await asyncio.to_thread(thread.join, 10)
            evidence["http_server_stopped"] = not thread.is_alive()
            if not evidence["http_server_stopped"]:
                evidence["status"] = "FAILED"
        listener.close()
        try:
            if container:
                await asyncio.to_thread(
                    runtime.cleanup,
                    container,
                    run_id,
                    image_id,
                    evidence,
                    primary_error,
                )
        finally:
            write_evidence(output, evidence, primary_error or sys.exc_info()[1])
        if primary_error is None and (
            not evidence.get("container_removed", True)
            or not evidence.get("http_server_stopped", True)
        ):
            raise RuntimeError(
                "Disposable verification resources did not stop cleanly; "
                "inspect evidence"
            )


if __name__ == "__main__":
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--output", required=True, type=Path)
    add_runtime_arguments(cli, IMAGE)
    args = cli.parse_args()
    asyncio.run(verify(args.output, args.docker_via_wsl, args.image, args.docker_host))
