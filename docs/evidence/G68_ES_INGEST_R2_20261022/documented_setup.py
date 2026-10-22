"""Independent read-only PR review probes. Only own labelled ES and D: files."""

import json
import os
import subprocess
import sys
import time
import uuid
from pathlib import Path

OUT = Path(__file__).resolve().parent
ROOT = Path("D:\\github\\_worktrees\\t2-es-ingest-20261022")
os.environ["TMP"] = os.environ["TEMP"] = str(OUT / "temp")
os.environ["PYTHONDONTWRITEBYTECODE"] = "1"
sys.path[:0] = [str(ROOT), str(ROOT / "tests")]

DOCKER = ["wsl", "-d", "FedoraLinux-43", "--exec", "/usr/sbin/docker"]
IMAGE = "docker.elastic.co/elasticsearch/elasticsearch:9.5.4"
LABEL = "t2.review=g68-pr74-fix-r2-20261022"
result = {"passed": False, "operations": [], "checks": []}
cid = None


def command(args, **kwargs):
    p = subprocess.run(
        DOCKER + args, capture_output=True, text=True, timeout=35, check=False, **kwargs
    )
    if p.returncode:
        raise RuntimeError({"command": args, "code": p.returncode, "stderr": p.stderr})
    return p.stdout.strip()


def request(method, path, body=None, raw=None, expected=None, ctype="application/json"):
    if raw is None:
        raw = "" if body is None else json.dumps(body, ensure_ascii=False)
    response = command(
        [
            "exec",
            "-i",
            cid,
            "curl",
            "-sS",
            "--max-time",
            "10",
            "-X",
            method,
            "-H",
            "Content-Type: " + ctype,
            "--data-binary",
            "@-",
            "-w",
            "\n%{http_code}",
            "http://127.0.0.1:9200" + path,
        ],
        input=raw,
    )
    text, code = response.rsplit("\n", 1)
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        data = text
    result["operations"].append(
        {
            "method": method,
            "path": path,
            "request": raw,
            "status": int(code),
            "response": data,
        }
    )
    if expected is not None:
        assert int(code) == expected, (path, code, data)
    return int(code), data


def check(name):
    result["checks"].append(name)
    print("PASS:", name, flush=True)


def put(path, doc, expected=200):
    return request("PUT", path, doc, expected=expected)[1]


def main():
    global cid
    OUT.joinpath("temp").mkdir(exist_ok=True)
    lab = OUT / "setup-lab"
    lab.mkdir(exist_ok=False)
    for name in ("data", "java-temp", "logs"):
        (lab / name).mkdir()
    result["containers_before"] = command(["ps", "-aq"]).splitlines()
    result["image"] = json.loads(command(["image", "inspect", IMAGE]))[0]["Id"]
    mounts = []
    for name in ("data", "java-temp", "logs"):
        src = "/mnt/d/" + (lab / name).as_posix()[3:]
        mounts += [
            "--mount",
            f"type=bind,src={src},dst=/usr/share/elasticsearch/{name}",
        ]
    cid = command(
        [
            "run",
            "-d",
            "--pull=never",
            "--name",
            "pr74-review-" + uuid.uuid4().hex,
            "--label",
            LABEL,
            "--cap-drop=ALL",
            "--security-opt=no-new-privileges",
            "--log-driver=none",
            "--memory=1280m",
            "--memory-swap=1280m",
            "--cpus=2",
            "--pids-limit=512",
            "-p",
            "127.0.0.1::9200",
            *mounts,
            "-e",
            "ES_LOG_STYLE=file",
            "-e",
            "ES_TMPDIR=/usr/share/elasticsearch/java-temp",
            "-e",
            "discovery.type=single-node",
            "-e",
            "network.host=0.0.0.0",
            "-e",
            "xpack.security.enabled=false",
            "-e",
            "xpack.ml.enabled=false",
            "-e",
            "ingest.geoip.downloader.enabled=false",
            "-e",
            "ES_JAVA_OPTS=-Xms384m -Xmx384m",
            IMAGE,
        ]
    )
    inspected = json.loads(command(["inspect", cid]))[0]
    assert inspected["Config"]["Labels"]["t2.review"] == LABEL.split("=", 1)[1]
    assert all(
        m["Type"] == "bind" and m["Source"].startswith("/mnt/d/")
        for m in inspected["Mounts"]
    )
    assert (
        inspected["HostConfig"]["PortBindings"]["9200/tcp"][0]["HostIp"] == "127.0.0.1"
    )
    result["isolation"] = {
        "id": cid,
        "mounts": inspected["Mounts"],
        "ports": inspected["NetworkSettings"]["Ports"],
        "label": LABEL,
    }
    deadline = time.monotonic() + 150
    while True:
        p = subprocess.run(
            DOCKER
            + ["exec", cid, "curl", "-sf", "--max-time", "2", "http://127.0.0.1:9200"],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        if p.returncode == 0:
            assert json.loads(p.stdout)["version"]["number"] == "9.5.4"
            break
        assert time.monotonic() < deadline, "Own ES not ready after 150s"
        time.sleep(1)

    from test_es_ingest_pipeline import synthetic_prediction

    from scripts.validate_contracts import validators

    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    instructions = readme[
        readme.index("En un laboratorio autorizado, instalar primero") :
    ]
    assert (
        instructions.index("PUT /_ingest/pipeline/cnc-prediction-v1")
        < instructions.index("GET /_ingest/pipeline/cnc-prediction-v1")
        < instructions.index("PUT /_index_template/cnc-lab-v1")
    )
    assert (
        "elasticsearch/README.md#instalación-y-rollback-en-un-laboratorio-propio"
        in instructions
    )
    assert request("GET", "/_ingest/pipeline/cnc-prediction-v1", expected=404)[0] == 404
    assert request("GET", "/_index_template/cnc-lab-v1", expected=404)[0] == 404
    pipeline = json.loads((ROOT / "elasticsearch/ingest-pipeline.json").read_text())
    template = json.loads((ROOT / "elasticsearch/index-template.json").read_text())
    put("/_ingest/pipeline/cnc-prediction-v1", pipeline)
    got = request("GET", "/_ingest/pipeline/cnc-prediction-v1", expected=200)[1][
        "cnc-prediction-v1"
    ]
    for name in ("created_date_millis", "modified_date_millis"):
        assert isinstance(got.pop(name), int)
    assert got == pipeline and got["version"] == 1
    put("/_index_template/cnc-lab-v1", template)
    doc = synthetic_prediction()
    validators(ROOT / "contracts")["prediction"].validate(doc)
    for family in ("telemetry", "alerts"):
        index = "cnc-" + family + "-documented"
        put("/" + index, {})
        settings = request("GET", "/" + index + "/_settings", expected=200)[1]
        assert (
            settings[index]["settings"]["index"]["final_pipeline"]
            == "cnc-prediction-v1"
        )
        mapping = request("GET", "/" + index + "/_mapping", expected=200)[1]
        assert mapping[index]["mappings"]["dynamic"] == "strict"
        sim = request(
            "POST",
            "/_ingest/pipeline/cnc-prediction-v1/_simulate",
            {"docs": [{"_index": index, "_id": "valid", "_source": doc}]},
            expected=200,
        )[1]
        assert sim["docs"][0]["doc"]["_source"] == doc
        put("/" + index + "/_doc/valid?refresh=true", doc, expected=201)
        assert (
            request("GET", "/" + index + "/_doc/valid", expected=200)[1]["_source"]
            == doc
        )
        assert request("GET", "/" + index + "/_count", expected=200)[1]["count"] == 1
    result["passed"] = True
    result["source"] = (
        "README.md + elasticsearch/README.md, actual ordered requests from clean own ES"
    )


if __name__ == "__main__":
    try:
        main()
    finally:
        if cid:
            command(["rm", "--force", cid])
        result["containers_after"] = command(["ps", "-aq"]).splitlines()
        assert sorted(result["containers_before"]) == sorted(result["containers_after"])
        result["container_removed"] = True
        (OUT / "setup-result.json").write_text(
            json.dumps(result, indent=2) + "\n", encoding="utf-8"
        )
