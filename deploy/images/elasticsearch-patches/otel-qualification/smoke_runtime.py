"""Finite, isolated real ES smoke with security and entitlements left enabled."""

import argparse
import hashlib
import json
import subprocess
import time
import uuid
from pathlib import Path


def docker(*args, timeout=30, check=True):
    return subprocess.run(
        ["docker", *args], capture_output=True, text=True, timeout=timeout, check=check
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("image")
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    image = json.loads(docker("image", "inspect", args.image).stdout)[0]["Id"]
    daemon = json.loads(docker("info", "--format", "{{json .ID}}").stdout)
    name = "cnc-closeout-es-smoke-" + uuid.uuid4().hex[:10]
    report = {
        "daemon_id": daemon,
        "image_id": image,
        "container": name,
        "status": "started",
        "production_acceptance": False,
    }
    created = False
    try:
        docker(
            "run",
            "-d",
            "--name",
            name,
            "--hostname",
            "localhost",
            "--network",
            "none",
            "--cpus",
            "2",
            "--memory",
            "2g",
            "--memory-swap",
            "2g",
            "--pids-limit",
            "512",
            "--cap-drop",
            "ALL",
            "--security-opt",
            "no-new-privileges",
            "-e",
            "discovery.type=single-node",
            "-e",
            "ES_JAVA_OPTS=-Xms512m",
            "-e",
            "xpack.security.enabled=true",
            image,
        )
        created = True
        deadline = time.monotonic() + 100
        while True:
            probe = docker(
                "exec",
                name,
                "curl",
                "-s",
                "-o",
                "/dev/null",
                "-w",
                "%{http_code}",
                "http://localhost:9200",
                check=False,
            )
            if probe.stdout == "401":
                break
            if time.monotonic() >= deadline:
                raise TimeoutError("ES did not reject anonymous access with HTTP 401")
            time.sleep(1)
        # Private ephemeral file realm only; this fixed synthetic password is
        # never used outside this network-none container and is not a secret.
        docker(
            "exec",
            name,
            "bin/elasticsearch-users",
            "useradd",
            "cnc_smoke",
            "-p",
            "SyntheticOnly_119_2026",
            "-r",
            "superuser",
        )

        def request(path, *extra):
            return docker(
                "exec",
                name,
                "curl",
                "-fsS",
                "--max-time",
                "15",
                "-u",
                "cnc_smoke:SyntheticOnly_119_2026",
                *extra,
                "http://localhost:9200/" + path,
                check=False,
            )

        while True:
            health = request("_cluster/health?wait_for_status=yellow&timeout=10s")
            if health.returncode == 0:
                break
            if time.monotonic() >= deadline:
                raise TimeoutError("synthetic file-realm authentication not ready")
            time.sleep(1)
        report["health"] = json.loads(health.stdout)
        if report["health"]["timed_out"] or report["health"]["status"] == "red":
            raise AssertionError("cluster health")
        payload = {"message": "synthetic closeout", "count": 7}
        write = request(
            "cnc-closeout-synthetic/_doc/1",
            "-X",
            "PUT",
            "-H",
            "Content-Type: application/json",
            "-d",
            json.dumps(payload),
        )
        if write.returncode:
            raise AssertionError("synthetic write: " + write.stderr)
        read = request("cnc-closeout-synthetic/_doc/1")
        if read.returncode or json.loads(read.stdout)["_source"] != payload:
            raise AssertionError("synthetic read did not preserve source")
        report["anonymous_http"] = 401
        report["synthetic_document_roundtrip"] = True
        report["status"] = "document-roundtrip-passed"
    except Exception as error:
        report["status"] = "failed"
        report["error"] = str(error)
        raise
    finally:
        if created:
            logs = docker("logs", name).stdout
            (args.output / "server.log").write_text(logs, encoding="utf-8")
            report["server_log_sha256"] = hashlib.sha256(logs.encode()).hexdigest()
            report["entitlement_agent_attached"] = "Entitlement agent attached" in logs
            if report["status"] == "document-roundtrip-passed":
                report["status"] = (
                    "passed" if report["entitlement_agent_attached"] else "failed"
                )
            docker("stop", "-t", "20", name)
            docker("rm", name)
        (args.output / "result.json").write_text(json.dumps(report, indent=2) + "\n")
    if not report["entitlement_agent_attached"]:
        raise AssertionError("missing real entitlement-agent startup")


if __name__ == "__main__":
    main()
