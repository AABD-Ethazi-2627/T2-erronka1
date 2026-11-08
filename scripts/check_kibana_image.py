"""Finite authenticated Kibana/ES smoke in a disposable private Docker network."""

import argparse
import hashlib
import json
import os
import re
import subprocess
import time
import uuid
from pathlib import Path


def docker(*args, timeout=45, check=True, env=None):
    return subprocess.run(
        ["docker", *args],
        capture_output=True,
        text=True,
        timeout=timeout,
        check=check,
        env=env,
    )


def run(es_image, kibana_image, output):
    output.mkdir(parents=True, exist_ok=False)
    prefix = "cnc-closeout-pair-" + uuid.uuid4().hex[:10]
    es, kibana = prefix + "-es", prefix + "-kibana"
    images = {
        name: json.loads(docker("image", "inspect", ref).stdout)[0]["Id"]
        for name, ref in (("es", es_image), ("kibana", kibana_image))
    }
    report = {
        "status": "started",
        "images": images,
        "daemon_id": docker("info", "--format", "{{.ID}}").stdout.strip(),
        "network": prefix,
        "production_acceptance": False,
        "security_enabled": True,
        "public_ports": [],
        "harness_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    }
    created, network_created, token = [], False, ""
    # Only valid inside these fresh, unpublished disposable test containers.
    synthetic_auth = "cnc_pair:SyntheticOnly_119_2026"
    try:
        docker("network", "create", "--internal", prefix)
        network_created = True
        docker(
            "run",
            "-d",
            "--name",
            es,
            "--network",
            prefix,
            "--network-alias",
            "es",
            "--memory",
            "2g",
            "--memory-swap",
            "2g",
            "--cpus",
            "2",
            "--pids-limit",
            "512",
            "--cap-drop",
            "ALL",
            "--security-opt",
            "no-new-privileges",
            "-e",
            "discovery.type=single-node",
            "-e",
            "ES_JAVA_OPTS=-Xms512m -Xmx512m",
            "-e",
            "xpack.security.enabled=true",
            images["es"],
        )
        created.append(es)
        print("ES created; waiting for authenticated service", flush=True)

        def es_request(path, auth=True):
            args = [
                "exec",
                es,
                "curl",
                "-sS",
                "--max-time",
                "8",
                "-w",
                "\n%{http_code}",
            ]
            if auth:
                args += ["-u", synthetic_auth]
            result = docker(*args, "http://localhost:9200/" + path, check=False)
            body, _, code = result.stdout.rpartition("\n")
            return code, body

        deadline = time.monotonic() + 180
        while es_request("", auth=False)[0] != "401":
            if time.monotonic() > deadline:
                raise TimeoutError("ES anonymous request did not return 401")
            time.sleep(2)
        report["es_anonymous_http"] = 401
        docker(
            "exec",
            es,
            "bin/elasticsearch-users",
            "useradd",
            "cnc_pair",
            "-p",
            "SyntheticOnly_119_2026",
            "-r",
            "superuser",
        )
        while True:
            code, body = es_request("_cluster/health?wait_for_status=yellow&timeout=5s")
            if code == "200" and not json.loads(body)["timed_out"]:
                report["es_health"] = json.loads(body)
                break
            if time.monotonic() > deadline:
                raise TimeoutError("ES file-realm authentication did not become ready")
            time.sleep(2)
        absent = ".workflows-cnc-smoke-absent/_mapping?allow_no_indices=true"
        missing_code, _ = es_request(absent)
        ignored_code, ignored_body = es_request(absent + "&ignore_unavailable=true")
        if (
            missing_code != "404"
            or ignored_code != "200"
            or json.loads(ignored_body) != {}
        ):
            raise AssertionError("Missing explicit mapping control changed")
        report["missing_stream_mapping_control"] = {
            "allow_no_indices_only": 404,
            "with_ignore_unavailable": 200,
            "mapping": {},
        }
        issued = docker(
            "exec",
            es,
            "bin/elasticsearch-service-tokens",
            "create",
            "elastic/kibana",
            "cnc-pair",
        ).stdout.strip()
        token = issued.rsplit(" = ", 1)[-1]
        if " = " not in issued or not token:
            raise ValueError(
                "Service token creation did not return its expected format"
            )
        env = {**os.environ, "ELASTICSEARCH_SERVICEACCOUNTTOKEN": token}
        docker(
            "run",
            "-d",
            "--name",
            kibana,
            "--network",
            prefix,
            "--memory",
            "2g",
            "--memory-swap",
            "2g",
            "--cpus",
            "2",
            "--pids-limit",
            "512",
            "--cap-drop",
            "ALL",
            "--security-opt",
            "no-new-privileges",
            "-e",
            "ELASTICSEARCH_HOSTS=http://es:9200",
            "-e",
            "ELASTICSEARCH_SERVICEACCOUNTTOKEN",
            "-e",
            "TELEMETRY_OPTIN=false",
            "-e",
            "TELEMETRY_ALLOWCHANGINGOPTIN=false",
            "-e",
            "XPACK_FLEET_ISAIRGAPPED=true",
            "-e",
            "XPACK_ENCRYPTEDSAVEDOBJECTS_ENCRYPTIONKEY=SyntheticPairOnly119Key0123456789",
            "-e",
            "XPACK_SECURITY_ENCRYPTIONKEY=SyntheticPairOnly119Key0123456789",
            "-e",
            "XPACK_REPORTING_ENCRYPTIONKEY=SyntheticPairOnly119Key0123456789",
            "-e",
            "NODE_OPTIONS=--max-old-space-size=1024",
            images["kibana"],
            env=env,
        )
        created.append(kibana)
        print("Kibana created; waiting for plugins and Fleet", flush=True)

        def kibana_request(path, auth=True):
            code = (
                "const headers={'kbn-xsrf':'cnc-pair-smoke'};"
                + (
                    "headers.Authorization='Basic '+Buffer.from("
                    + json.dumps(synthetic_auth)
                    + ").toString('base64');"
                    if auth
                    else ""
                )
                + "fetch('http://localhost:5601'+process.argv[1],"
                "{headers,signal:AbortSignal.timeout(8000)}).then(async r=>{"
                "const text=await r.text();let body;try{body=JSON.parse(text)}catch{body=text};"
                "console.log(JSON.stringify({status:r.status,body}));})"
                ".catch(()=>process.exit(2));"
            )
            reply = docker(
                "exec",
                kibana,
                "/usr/share/kibana/node/default/bin/node",
                "-e",
                code,
                path,
                timeout=20,
                check=False,
            )
            return json.loads(reply.stdout) if reply.returncode == 0 else None

        deadline = time.monotonic() + 360
        while True:
            reply = kibana_request("/api/status")
            if reply and reply["status"] == 200:
                level = reply["body"]["status"]["overall"]["level"]
                if level == "available":
                    report["kibana_status"] = reply
                    break
            if time.monotonic() > deadline:
                raise TimeoutError("Kibana did not reach available: " + str(reply))
            time.sleep(3)
        fleet = kibana_request("/api/fleet/agent_policies?perPage=10")
        if (
            not fleet
            or fleet["status"] != 200
            or not isinstance(fleet["body"].get("items"), list)
        ):
            raise AssertionError(
                "Authenticated Fleet list did not return its real list contract"
            )
        report["fleet_agent_policies"] = fleet
        anonymous = kibana_request("/api/fleet/agent_policies?perPage=10", auth=False)
        if not anonymous or anonymous["status"] != 401:
            raise AssertionError("Anonymous Fleet request was not rejected")
        report["fleet_anonymous_http"] = anonymous["status"]
        for name in created:
            actual = json.loads(docker("inspect", name).stdout)[0]["Image"]
            if actual != images["es" if name == es else "kibana"]:
                raise AssertionError("Container image identity drifted")
        runtime_errors = []
        for name in created:
            logs = docker("logs", name)
            runtime_errors.extend(
                line.replace(token, "<REDACTED_EPHEMERAL_TOKEN>")
                for line in (logs.stdout + logs.stderr).splitlines()
                if re.search(r'\[ERROR\s*\]|"log.level"\s*:\s*"ERROR"', line)
            )
        report["runtime_error_lines"] = runtime_errors
        if runtime_errors:
            raise AssertionError("Runtime ERROR records remain; inspect preserved logs")
        report["status"] = "passed"
        print(
            "Authenticated status, Fleet and negative access controls passed",
            flush=True,
        )
    except Exception as error:
        report.update(
            status="failed", error_type=type(error).__name__, error=str(error)
        )
        raise
    finally:
        cleanup_errors = []
        for name in reversed(created):
            logs = docker("logs", name, check=False)
            content = logs.stdout + logs.stderr
            if token:
                content = content.replace(token, "<REDACTED_EPHEMERAL_TOKEN>")
            file = output / ("elasticsearch.log" if name == es else "kibana.log")
            file.write_text(content, encoding="utf-8")
            report[file.name + "_sha256"] = hashlib.sha256(
                file.read_bytes()
            ).hexdigest()
            removed = docker("rm", "-f", "-v", name, check=False)
            if removed.returncode:
                cleanup_errors.append("container " + name)
        if network_created and docker("network", "rm", prefix, check=False).returncode:
            cleanup_errors.append("network " + prefix)
        report["cleanup_errors"] = cleanup_errors
        if cleanup_errors:
            report["status"] = "failed"
        (output / "result.json").write_text(
            json.dumps(report, indent=2) + "\n", encoding="utf-8"
        )
    if report["status"] != "passed":
        raise RuntimeError("Connected smoke or owned resource cleanup failed")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("es_image")
    parser.add_argument("kibana_image")
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    result = run(args.es_image, args.kibana_image, args.output)
    print(json.dumps({"status": result["status"], "images": result["images"]}))
