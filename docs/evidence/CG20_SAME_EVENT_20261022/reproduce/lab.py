"Own labelled isolated lab. No external staging or committing driver."

import hashlib
import json
import os
import signal
import socket
import sqlite3
import subprocess
import sys
import tarfile
import time
import uuid
from contextlib import closing
from pathlib import Path

import httpx
from kafka import KafkaAdminClient, TopicPartition
from kafka.admin import NewTopic
from kafka.errors import KafkaError
from test_scoring_replay import manifest

from scripts.build_automatic_graph_flow import build
from scripts.run_automatic_graph import accounting

E = Path(__file__).resolve().parent
C = E.parents[2] / "_worktrees/t2-cg20-api-kibana-20261022"
ROOT = E / "lab-01"
LABEL = "t2.cg20.run"
STATE = ROOT / "state.json"
STAGE = sys.argv[1]
S = json.loads(STATE.read_text()) if STATE.exists() else {}
client = httpx.Client(trust_env=False, timeout=15)


def save(name, value):
    (ROOT / name).write_text(json.dumps(value, indent=2) + "\n")


def docker(*args, check=True):
    p = subprocess.run(
        ["docker", *args], check=False, capture_output=True, text=True, timeout=100
    )
    with (E / "docker-commands.jsonl").open("a") as log:
        log.write(
            json.dumps(
                {
                    "args": ["docker", *args],
                    "exit": p.returncode,
                    "stdout": p.stdout,
                    "stderr": p.stderr,
                }
            )
            + "\n"
        )
    if check:
        p.check_returncode()
    return p.stdout.strip()


def owned(identity):
    obj = json.loads(docker("inspect", identity))[0]
    assert (
        obj["Id"] in S["ids"].values()
        and obj["Config"]["Labels"].get(LABEL) == S["tag"]
    )
    return obj


def bind(src, dst, ro=False):
    return [
        "--mount",
        "type=bind,src=" + str(src) + ",dst=" + dst + (",readonly" if ro else ""),
    ]


def random_port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def export_defaults(identity, prefix, target):
    "Docker export exposes the underlying image directory behind volume binds."
    process = subprocess.Popen(
        ["docker", "export", identity], stdout=subprocess.PIPE, stderr=subprocess.PIPE
    )
    with tarfile.open(fileobj=process.stdout, mode="r|") as archive:
        for item in archive:
            if item.isfile() and item.name.startswith(prefix + "/"):
                relative = Path(item.name).relative_to(prefix)
                assert ".." not in relative.parts and not relative.is_absolute()
                destination = target / relative
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_bytes(archive.extractfile(item).read())
    process.stdout.close()
    error = process.stderr.read().decode()
    process.stderr.close()
    result = process.wait(timeout=100)
    with (E / "docker-commands.jsonl").open("a") as log:
        log.write(
            json.dumps(
                {
                    "args": ["docker", "export", identity],
                    "exit": result,
                    "extracted_prefix": prefix,
                    "stderr": error,
                }
            )
            + "\n"
        )
    assert result == 0


def create(name, image_tag, args, defaults=None):
    image = json.loads(docker("image", "inspect", image_tag))[0]
    save(name + "-image.json", image)
    # Override EVERY image VOLUME with an explicit D: bind, never an anonymous volume.
    mounts = []
    for index, destination in enumerate(image["Config"].get("Volumes") or {}):
        if any(
            "dst=" + destination in arg.split(",")
            for arg in args
            if isinstance(arg, str)
        ):
            continue
        source = ROOT / name / ("volume-" + str(index))
        source.mkdir(parents=True)
        mounts += bind(source, destination)
        if defaults and destination == defaults:
            default_target = source
    suffix = ""
    if name in S["ids"]:
        previous = owned(S["ids"][name])
        assert not previous["State"]["Running"]
        attempt = 1
        while name + "-attempt" + str(attempt) in S["ids"]:
            attempt += 1
        S["ids"][name + "-attempt" + str(attempt)] = previous["Id"]
        suffix = "-r" + str(attempt + 1)
    identity = docker(
        "create",
        "--pull=never",
        "--name",
        S["tag"] + "-" + name + suffix,
        "--label",
        LABEL + "=" + S["tag"],
        "--read-only",
        "--cap-drop=ALL",
        "--security-opt=no-new-privileges:true",
        "--network",
        S["network"],
        "--network-alias",
        name,
        *mounts,
        *args,
        image["Id"],
        *COMMANDS[name],
    )
    S["ids"][name] = identity
    save("state.json", S)
    obj = owned(identity)
    assert all(m["Type"] == "bind" for m in obj["Mounts"])
    assert all(
        not m["RW"] or Path(m["Source"]).is_relative_to(ROOT) for m in obj["Mounts"]
    )
    save(name + "-created.json", obj)
    if defaults:
        export_defaults(identity, defaults.lstrip("/"), default_target)
    return identity


def wait(predicate, description, seconds=180):
    deadline = time.monotonic() + seconds
    last = None
    while time.monotonic() < deadline:
        try:
            result = predicate()
            if result:
                return result
        except (
            httpx.TransportError,
            KafkaError,
            OSError,
            sqlite3.OperationalError,
        ) as exc:
            last = str(exc)
        if (
            description.startswith("NiFi")
            and not owned(S["ids"]["nifi"])["State"]["Running"]
        ):
            raise RuntimeError("Own NiFi exited; inspect retained logs")
        time.sleep(0.5)
    raise RuntimeError("Timed out: " + description + " last=" + str(last))


def api(method, path, **kwargs):
    response = client.request(
        method, "http://127.0.0.1:" + str(S["nifi_port"]) + "/nifi-api" + path, **kwargs
    )
    with (E / "nifi-operations.jsonl").open("a") as log:
        log.write(
            json.dumps(
                {
                    "method": method,
                    "path": path,
                    "status": response.status_code,
                    "body": response.text if response.is_error else None,
                }
            )
            + "\n"
        )
    response.raise_for_status()
    return response.json() if response.content else None


def es(method, path, **kwargs):
    response = client.request(
        method, "http://127.0.0.1:" + str(S["es_port"]) + path, **kwargs
    )
    with (E / "es-operations.jsonl").open("a") as log:
        log.write(
            json.dumps(
                {
                    "method": method,
                    "path": path,
                    "status": response.status_code,
                    "body": response.json(),
                }
            )
            + "\n"
        )
    return response


def processor_state(identifier, state):
    entity = api("GET", "/processors/" + identifier)
    return api(
        "PUT",
        "/processors/" + identifier + "/run-status",
        json={
            "revision": entity["revision"],
            "state": state,
            "disconnectedNodeAcknowledged": False,
        },
    )


def broker_offset():
    # Administrative read only: this client never subscribes, polls or commits.
    admin = KafkaAdminClient(
        bootstrap_servers="127.0.0.1:" + str(S["kafka_port"]), api_version=(3, 7)
    )
    try:
        offsets = admin.list_group_offsets(S["group"])[S["group"]]
        entry = offsets.get(TopicPartition(S["topic"], 0))
        return entry.offset if entry and entry.offset >= 0 else None
    finally:
        admin.close()


def snapshot(name):
    data = {"offset": broker_offset(), "accounting": accounting(ROOT / "worker")}
    database = ROOT / "worker/archive/ledger.sqlite"
    if database.exists():
        with closing(sqlite3.connect(database.as_uri() + "?mode=ro", uri=True)) as con:
            data["archive"] = con.execute(
                "SELECT id, hash, outcome FROM deliveries ORDER BY id"
            ).fetchall()
    data["parquet_hashes"] = {
        str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in (ROOT / "worker").rglob("*.parquet")
    }
    assert es("POST", "/" + S["index"] + "/_refresh").status_code == 200
    response = es("GET", "/" + S["index"] + "/_search?size=100")
    assert response.status_code == 200
    data["es"] = response.json()
    api_database = ROOT / "api.sqlite3"
    if api_database.exists() and (ROOT / "worker/pipeline.sqlite3").exists():
        with closing(
            sqlite3.connect(api_database.as_uri() + "?mode=ro", uri=True)
        ) as con:
            canonical_responses = {
                row[0].encode()
                for row in con.execute("SELECT response FROM scoring_responses")
            }
        with closing(
            sqlite3.connect(
                (ROOT / "worker/pipeline.sqlite3").as_uri() + "?mode=ro", uri=True
            )
        ) as con:
            worker_responses = {
                bytes(row[0])
                for row in con.execute(
                    "SELECT response FROM jobs WHERE response IS NOT NULL"
                )
            }
        assert worker_responses <= canonical_responses
        for hit in data["es"]["hits"]["hits"]:
            encoded = json.dumps(
                hit["_source"],
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=False,
            ).encode()
            assert encoded in canonical_responses
        data["canonical_response_count"] = len(canonical_responses)
        data["worker_response_count"] = len(worker_responses)
    save(name + ".json", data)
    return data


def write_lines(name, lines):
    target = ROOT / "input" / (name + ".csv")
    assert not target.exists()
    # Product filestream fingerprints content. Give each file a distinct
    # fingerprint window while retaining equal rows within that file.
    ordinal = (
        len((ROOT / "sent.jsonl").read_text().splitlines()) + 1
        if (ROOT / "sent.jsonl").exists()
        else 1
    )
    lines = [
        raw.replace(b"CNC-001", f"CNC-{ordinal:03d}".encode()) if raw == RAW else raw
        for raw in lines
    ]
    target.write_bytes(b"".join(lines))
    with (ROOT / "sent.jsonl").open("a") as log:
        for raw in lines:
            log.write(
                json.dumps(
                    {
                        "file": target.name,
                        "sha256": hashlib.sha256(raw.rstrip(b"\n")).hexdigest(),
                    }
                )
                + "\n"
            )


RAW = b"2026-10-21T08:00:00Z,CNC-001,H,300,310,1500,40,10,1,0,0,0,0,0\n"
COMMANDS = {
    "kafka": ["/lab/start.sh"],
    "nifi": ["/lab/nifi-start.sh"],
    "es": [],
    "kibana": [],
    "filebeat": [
        "-e",
        "--strict.perms=false",
        "-c",
        "/lab/filebeat.yml",
        "--path.data",
        "/lab/registry",
        "--path.logs",
        "/lab/runtime",
    ],
}


def configure():
    venv = Path("/home/Fedora/t2-real-lab-20261022/venv")
    root_id = api("GET", "/flow/process-groups/root")["processGroupFlow"]["id"]
    definition = build()
    replacements = {
        "WORKER_CHECKOUT": "/opt/checkout",
        "WORKER_PYTHON": str(venv / "bin/python"),
        "GRAPH_CONFIG": str(ROOT / "graph.json"),
        "PROCESS_TEMP": str(ROOT / "process-temp"),
        "CYCLE_REPORTS": str(ROOT / "cycle-reports"),
    }
    for processor in definition["flowContents"]["processors"]:
        for key, value in processor["properties"].items():
            for parameter, actual in replacements.items():
                value = value.replace("#{" + parameter + "}", actual)
            processor["properties"][key] = value
        if processor["name"] == "Schedule bounded source cycle":
            processor["schedulingPeriod"] = "2 sec"
    save("source-configured-flow.json", definition)
    upload = api(
        "POST",
        "/process-groups/" + root_id + "/process-groups/upload",
        data={
            "groupName": "Own automatic product graph",
            "positionX": "0",
            "positionY": "0",
            "clientId": S["tag"],
        },
        files={
            "file": ("flow.json", json.dumps(definition).encode(), "application/json")
        },
    )
    if "group_id" in S:
        S.setdefault("retained_disabled_groups", []).append(S["group_id"])
    S["group_id"] = upload["id"]
    save("state.json", S)
    flow = api("GET", "/flow/process-groups/" + S["group_id"])["processGroupFlow"][
        "flow"
    ]
    S["processors"] = {p["component"]["name"]: p["id"] for p in flow["processors"]}
    save("state.json", S)
    for identifier in S["processors"].values():
        processor_state(identifier, "STOPPED")
    time.sleep(2)
    for identifier in S["processors"].values():
        api("GET", "/processors/" + identifier)["component"]
        wait(
            lambda identifier=identifier: (
                api("GET", "/processors/" + identifier)["component"]["validationStatus"]
                == "VALID"
            ),
            "processor validation",
            seconds=30,
        )
    save(
        "nifi-configured-validation.json",
        api("GET", "/flow/process-groups/" + S["group_id"]),
    )
    beat_config = (
        (C / "filebeat/filebeat.yml")
        .read_text()
        .replace("paths: ['/mnt/cnc-stream/*.csv']", "paths: ['/lab/input/*.csv']")
        .replace("paths: ['/mnt/cnc-smb/*.csv']", "paths: ['/lab/unused/*.csv']")
        .replace("hosts: ['kafka:9092']", "hosts: ['kafka:19092']")
        .replace("topic: cnc-sensors-lab-v2", "topic: " + S["topic"])
    )
    # Fixtures below are long enough for the product's 228-byte fingerprint window.
    (ROOT / "filebeat.yml").write_text(beat_config)
    beat = create(
        "filebeat",
        "docker.elastic.co/beats/filebeat:9.5.4",
        [
            "--memory=256m",
            "--user=1000:1000",
            *bind(ROOT / "registry", "/lab/registry"),
            *bind(ROOT / "filebeat-runtime", "/lab/runtime"),
            *bind(ROOT / "input", "/lab/input", True),
            *bind(ROOT / "filebeat.yml", "/lab/filebeat.yml", True),
            "--entrypoint",
            "/usr/share/filebeat/filebeat",
        ],
    )
    docker("start", beat)
    for name, identifier in S["processors"].items():
        if name != "Schedule bounded source cycle":
            processor_state(identifier, "RUNNING")
    processor_state(S["processors"]["Schedule bounded source cycle"], "RUNNING")
    print(json.dumps(S))


if STAGE in (
    "start",
    "resume-start",
    "resume-es",
    "resume-es3",
    "resume-es4",
    "resume-nifi",
    "resume-nifi2",
    "resume-nifi3",
):
    if not STAGE.startswith("resume-nifi"):
        if STAGE == "start":
            assert not STATE.exists(), "Never replay start over an existing run"
            ROOT.mkdir(exist_ok=True)
            for name in (
                "input",
                "process-temp",
                "kafka-storage/data",
                "kafka-storage/metadata",
                "kafka-runtime",
                "nifi-runtime",
                "nifi-work",
                "nifi-run",
                "es-runtime",
                "es-logs",
                "es-config",
                "es-data",
                "registry",
                "filebeat-runtime",
                "cycle-reports",
            ):
                (ROOT / name).mkdir(parents=True, exist_ok=True)
            S.update(
                tag="t2-cg20-" + uuid.uuid4().hex[:10],
                ids={},
                kafka_port=random_port(),
                nifi_port=random_port(),
                es_port=random_port(),
                api_port=random_port(),
            )
            S["network"] = docker(
                "network", "create", "--label", LABEL + "=" + S["tag"], S["tag"]
            )
            S["gateway"] = json.loads(docker("network", "inspect", S["network"]))[0][
                "IPAM"
            ]["Config"][0]["Gateway"]
            S.update(
                topic="cnc-sensors-automatic-v1",
                group="cg14-auto-" + S["tag"],
                index="cnc-alerts-automatic-v4",
            )
            save("state.json", S)
            properties = (
                (C / "deploy/cg14/scripts/kafka-volume.properties")
                .read_text()
                .replace(
                    "controller.quorum.voters=1@cg14-kafka-test:9093",
                    "controller.quorum.voters=1@kafka:9093",
                )
                .replace(
                    (
                        "listener.security.protocol.map=CONTROLLE"
                        "R:PLAINTEXT,PLAINTEXT:PLAINTEXT"
                    ),
                    (
                        "listener.security.protocol.map=CONTROLLE"
                        "R:PLAINTEXT,INTERNAL:PLAINTEXT,EXTERNAL:"
                        "PLAINTEXT"
                    ),
                )
                .replace(
                    "listeners=PLAINTEXT://:9092,CONTROLLER://:9093",
                    ("listeners=EXTERNAL://:9092,INTERNAL://:19092,CONTROLLER://:9093"),
                )
                .replace(
                    "advertised.listeners=PLAINTEXT://cg14-kafka-test:9092",
                    "advertised.listeners=EXTERNAL://127.0.0.1:"
                    + str(S["kafka_port"])
                    + ",INTERNAL://kafka:19092",
                )
                .replace(
                    "inter.broker.listener.name=PLAINTEXT",
                    "inter.broker.listener.name=INTERNAL",
                )
            )
            (ROOT / "server.properties").write_text(properties)
            kafka = create(
                "kafka",
                "apache/kafka:3.7.2",
                [
                    "--memory=1g",
                    "--publish",
                    "127.0.0.1:" + str(S["kafka_port"]) + ":9092",
                    "--env",
                    "CLUSTER_ID=CG14automaticRetained01",
                    "--env",
                    "KAFKA_HEAP_OPTS=-Xms256m -Xmx512m",
                    *bind(ROOT / "kafka-storage", "/var/lib/kafka"),
                    *bind(ROOT / "kafka-storage/data", "/var/lib/kafka/data"),
                    *bind(ROOT / "kafka-runtime", "/lab/runtime"),
                    *bind(ROOT / "server.properties", "/lab/server.properties", True),
                    *bind(
                        C / "deploy/cg14/scripts/kafka-volume-start.sh",
                        "/lab/start.sh",
                        True,
                    ),
                    "--entrypoint",
                    "/bin/bash",
                ],
            )
            docker("start", kafka)
        kafka = S["ids"]["kafka"]

        def kafka_ready():
            admin = KafkaAdminClient(
                bootstrap_servers="127.0.0.1:" + str(S["kafka_port"]),
                api_version=(3, 7),
                request_timeout_ms=2000,
            )
            admin.close()
            return True

        wait(kafka_ready, "Kafka")
        admin = KafkaAdminClient(
            bootstrap_servers="127.0.0.1:" + str(S["kafka_port"]), api_version=(3, 7)
        )
        if not STAGE.startswith("resume-es"):
            admin.create_topics([NewTopic(S["topic"], 1, 1)])
        admin.close()
        elastic = create(
            "es",
            "docker.elastic.co/elasticsearch/elasticsearch:9.5.4",
            [
                "--memory=1280m",
                "--publish",
                "127.0.0.1:" + str(S["es_port"]) + ":9200",
                "--env",
                "discovery.type=single-node",
                "--env",
                "xpack.security.enabled=false",
                "--env",
                "ingest.geoip.downloader.enabled=false",
                "--env",
                "ES_TMPDIR=/lab/runtime",
                "--env",
                (
                    "ES_JAVA_OPTS=-Xms384m -Xmx384m -Djava.io"
                    ".tmpdir=/lab/runtime -XX:-UsePerfData"
                ),
                "--env",
                ("CLI_JAVA_OPTS=-Djava.io.tmpdir=/lab/runtime -XX:-UsePerfData"),
                *bind(ROOT / "es-posix", "/lab/runtime"),
                *bind(ROOT / "es-posix", "/tmp"),
                *bind(ROOT / "es-logs", "/usr/share/elasticsearch/logs"),
                *bind(ROOT / "es-config", "/usr/share/elasticsearch/config"),
                *bind(ROOT / "es-data", "/usr/share/elasticsearch/data"),
            ],
        )
        # ES has no config VOLUME: copy underlying image defaults to a retained bind.
        export_defaults(elastic, "usr/share/elasticsearch/config", ROOT / "es-config")
        # Image configuration is read-only; pass explicit -E flags.
        docker("start", elastic)
        wait(
            lambda: (
                client.get("http://127.0.0.1:" + str(S["es_port"])).status_code == 200
            ),
            "Elasticsearch",
        )
        assert (
            es(
                "PUT",
                "/_ingest/pipeline/cnc-prediction-v1",
                json=json.loads(
                    (C / "elasticsearch/ingest-pipeline.json").read_bytes()
                ),
            ).status_code
            == 200
        )
        assert (
            es(
                "PUT",
                "/_index_template/cnc-lab-v1",
                json=json.loads((C / "elasticsearch/index-template.json").read_bytes()),
            ).status_code
            == 200
        )
        assert es("PUT", "/" + S["index"]).status_code == 200
        save("es-settings.json", es("GET", "/" + S["index"] + "/_settings").json())
        assert (
            es("GET", "/" + S["index"] + "/_settings").json()[S["index"]]["settings"][
                "index"
            ]["final_pipeline"]
            == "cnc-prediction-v1"
        )
        save("pinned-manifest.json", manifest())
        (ROOT / "api-mode.txt").write_text("normal")
        api_log = (ROOT / "api.log").open("ab")
        api_process = subprocess.Popen(
            [sys.executable, "-B", str(E / "fixture_api.py"), str(ROOT)],
            cwd=C,
            env={
                **os.environ,
                "PYTHONPATH": str(C) + ":" + str(C / "tests"),
                "TMPDIR": str(ROOT / "process-temp"),
            },
            stdout=api_log,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
        api_log.close()
        S["api_pid"] = api_process.pid
        save("state.json", S)
        wait(
            lambda: (
                client.get(
                    "http://127.0.0.1:" + str(S["api_port"]) + "/metrics"
                ).status_code
                == 200
            ),
            "canonical API",
        )
        config = json.loads(
            (C / "deploy/cg14/automatic-graph.example.json").read_bytes()
        )
        config.update(
            root=str(ROOT / "worker"),
            manifest=str(ROOT / "pinned-manifest.json"),
            source_namespace=S["tag"] + "/generation-1",
            source_kind="lab_fixture",
            scoring_url="http://"
            + S["gateway"]
            + ":"
            + str(S["api_port"])
            + "/predict",
            es_url="http://es:9200",
            es_index=S["index"],
            bootstrap_servers="kafka:19092",
            topic=S["topic"],
            group_id=S["group"],
            offset_reset="earliest",
            attempts=1,
            timeout=0.5,
            max_polls=3,
        )
        save("graph.json", config)
        boot = (
            "set -euo pipefail\nconf=/opt/nifi/nifi-cu"
            "rrent/conf\nsed -i -e 's|^nifi.web.https."
            "port=.*|nifi.web.https.port=|' -e 's|^ni"
            "fi.web.https.host=.*|nifi.web.https.host"
            "=|' -e 's|^nifi.web.http.host=.*|nifi.we"
            "b.http.host=0.0.0.0|' -e 's|^nifi.web.ht"
            "tp.port=.*|nifi.web.http.port=8080|' -e "
            "'s|^nifi.remote.input.secure=.*|nifi.rem"
            "ote.input.secure=false|' -e 's|^nifi.sec"
            "urity.user.login.identity.provider=.*|ni"
            "fi.security.user.login.identity.provider"
            "=|' -e 's|^nifi.security.keystore=.*|nif"
            "i.security.keystore=|' -e 's|^nifi.secur"
            "ity.truststore=.*|nifi.security.truststo"
            're=|\' "$conf/nifi.properties"\nsed -i -e '
            "'s|^java.arg.2=.*|java.arg.2=-Xms256m|' "
            "-e 's|^java.arg.3=.*|java.arg.3=-Xmx768m"
            "|' \"$conf/bootstrap.conf\"\nsed -i -e 's|^"
            "nifi.asset.manager.properties.directory="
            ".*|nifi.asset.manager.properties.directo"
            "ry=./work/assets|' -e 's|^nifi.connector"
            ".asset.manager.properties.directory=.*|n"
            "ifi.connector.asset.manager.properties.d"
            "irectory=./work/connector_assets|' -e 's"
            "|^nifi.nar.persistence.provider.properti"
            "es.directory=.*|nifi.nar.persistence.pro"
            "vider.properties.directory=./work/nar_re"
            "pository|' -e 's|^nifi.status.repository"
            ".questdb.persist.location=.*|nifi.status"
            ".repository.questdb.persist.location=./w"
            "ork/status_repository|' -e 's|^nifi.diag"
            "nostics.on.shutdown.directory=.*|nifi.di"
            "agnostics.on.shutdown.directory=./work/d"
            "iagnostics|' -e 's|^nifi.nar.library.aut"
            "oload.directory=.*|nifi.nar.library.auto"
            "load.directory=./nar_extensions|' \"$conf"
            '/nifi.properties"\nexec /opt/nifi/nifi-cu'
            "rrent/bin/nifi.sh run\n"
        )
        (ROOT / "nifi-start.sh").write_text(boot)
        runtime = Path(
            "/home/Fedora/.local/share/uv/python/cpython-3.12.15-linux-x86_64-gnu"
        )
        venv = Path("/home/Fedora/t2-real-lab-20261022/venv")
        assert runtime.is_dir() and (venv / "bin/python").is_file()
        nifi = create(
            "nifi",
            "apache/nifi:2.12.0",
            [
                "--memory=2304m",
                "--publish",
                "127.0.0.1:" + str(S["nifi_port"]) + ":8080",
                "--env",
                ("JAVA_TOOL_OPTIONS=-Djava.io.tmpdir=/lab/runtime -XX:-UsePerfData"),
                "--env",
                "TMPDIR=/lab/runtime",
                "--env",
                "TEMP=/lab/runtime",
                "--env",
                "TMP=/lab/runtime",
                *bind(ROOT, str(ROOT)),
                *bind(C, "/opt/checkout", True),
                *bind(venv, str(venv), True),
                *bind(runtime, str(runtime), True),
                *bind(ROOT / "nifi-runtime", "/lab/runtime"),
                *bind(ROOT / "nifi-work", "/opt/nifi/nifi-current/work"),
                *bind(ROOT / "nifi-run", "/opt/nifi/nifi-current/run"),
                *bind(ROOT / "nifi-start.sh", "/lab/nifi-start.sh", True),
                "--entrypoint",
                "/bin/bash",
            ],
            defaults="/opt/nifi/nifi-current/conf",
        )
    else:
        nifi = S["ids"]["nifi"]
        venv = Path("/home/Fedora/t2-real-lab-20261022/venv")
        configuration = next(
            m["Source"]
            for m in owned(nifi)["Mounts"]
            if m["Destination"] == "/opt/nifi/nifi-current/conf"
        )
        if not (Path(configuration) / "nifi.properties").exists():
            export_defaults(nifi, "opt/nifi/nifi-current/conf", Path(configuration))
    docker("start", nifi)
    wait(
        lambda: (
            client.get(
                "http://127.0.0.1:" + str(S["nifi_port"]) + "/nifi-api/flow/about"
            ).status_code
            == 200
        ),
        "NiFi",
        seconds=240,
    )
    configure()

elif STAGE in ("configure", "configure-r3"):
    configure()

elif STAGE in ("repair-beat", "repair-beat2"):
    beat = create(
        "filebeat",
        "docker.elastic.co/beats/filebeat:9.5.4",
        [
            "--memory=256m",
            "--user=1000:1000",
            *bind(ROOT / "registry", "/lab/registry"),
            *bind(ROOT / "filebeat-runtime", "/lab/runtime"),
            *bind(ROOT / "input", "/lab/input", True),
            *bind(ROOT / "filebeat.yml", "/lab/filebeat.yml", True),
            "--entrypoint",
            "/usr/share/filebeat/filebeat",
        ],
    )
    docker("start", beat)

elif STAGE in ("normal", "normal-resume", "normal-resume2"):
    # Four equal valid lines are four occurrences, not one content-deduplicated event.
    if STAGE == "normal":
        write_lines("normal", [RAW] * 4 + [b"bad,csv\n"])
    wait(lambda: broker_offset() == 5, "automatic Filebeat/NiFi offset5", seconds=150)
    result = snapshot("normal")
    assert result["accounting"] == {
        "observed": 5,
        "saved": 4,
        "rejected": 1,
        "pending": 0,
    }
    assert len(result["archive"]) == 8 and all(
        row[2] == "stored" for row in result["archive"]
    )
    assert result["es"]["hits"]["total"]["value"] == 4
    save(
        "normal-pass.json",
        {
            "passed": True,
            "source_owner": "NiFi scheduled product Kafka adapter; no lab commit",
        },
    )

elif STAGE.startswith("status-"):
    status = STAGE.split("-")[1]
    before = broker_offset()
    (ROOT / "api-mode.txt").write_text(status)
    write_lines("status-" + status, [RAW] * 4)
    if status == "422":
        wait(lambda: broker_offset() == before + 4, "durable terminal422")
    else:
        wait(lambda: accounting(ROOT / "worker")["pending"] >= 1, "blocked job")
        time.sleep(8)
        assert broker_offset() == before
    failed = snapshot(STAGE + "-blocked")
    (ROOT / "api-mode.txt").write_text("normal")
    wait(lambda: broker_offset() == before + 4, "automatic status recovery")
    recovered = snapshot(STAGE + "-recovered")
    save(
        STAGE + "-pass.json",
        {
            "passed": True,
            "before": before,
            "blocked_offset": failed["offset"],
            "recovered_offset": recovered["offset"],
        },
    )

elif STAGE == "es-setup":
    before = broker_offset()
    observed = accounting(ROOT / "worker")["observed"]
    assert (
        es(
            "PUT",
            "/" + S["index"] + "/_settings",
            json={"index.final_pipeline": "_none"},
        ).status_code
        == 200
    )
    write_lines("missing-final-guard", [RAW] * 4)
    time.sleep(12)
    assert broker_offset() == before
    assert accounting(ROOT / "worker")["observed"] == observed
    reports = [
        json.loads(p.read_bytes())
        for p in (ROOT / "worker/automatic-cycles").glob("*.json")
    ]
    assert any(p.get("error_type") == "ValueError" for p in reports)
    assert (
        es(
            "PUT",
            "/" + S["index"] + "/_settings",
            json={"index.final_pipeline": "cnc-prediction-v1"},
        ).status_code
        == 200
    )
    wait(lambda: broker_offset() == before + 4, "restored required final guard")
    snapshot("es-setup-recovered")
    save(
        "es-setup-pass.json",
        {
            "passed": True,
            "before": before,
            "after": broker_offset(),
            "no_consumption_with_missing_guard": True,
        },
    )

elif STAGE == "es-failure":
    before = broker_offset()
    # Real ES write block (403); API and CG15 still run and retain canonical bytes.
    assert (
        es(
            "PUT", "/" + S["index"] + "/_settings", json={"index.blocks.write": True}
        ).status_code
        == 200
    )
    write_lines("es-blocked", [RAW] * 4)
    wait(lambda: accounting(ROOT / "worker")["pending"] >= 1, "ES blocked job")
    time.sleep(8)
    assert broker_offset() == before
    failed = snapshot("es-blocked")
    assert len(failed["archive"]) >= 2
    # Restart the scheduler itself while the required ES output is blocked.
    docker("stop", "--time", "40", owned(S["ids"]["nifi"])["Id"])
    assert (
        es(
            "PUT", "/" + S["index"] + "/_settings", json={"index.blocks.write": False}
        ).status_code
        == 200
    )
    docker("start", owned(S["ids"]["nifi"])["Id"])
    wait(
        lambda: (
            client.get(
                "http://127.0.0.1:" + str(S["nifi_port"]) + "/nifi-api/flow/about"
            ).status_code
            == 200
        ),
        "NiFi blocked-job restart",
        seconds=240,
    )
    wait(lambda: broker_offset() == before + 4, "automatic ES recovery")
    recovered = snapshot("es-recovered")
    assert all(
        recovered["parquet_hashes"][name] == value
        for name, value in failed["parquet_hashes"].items()
    )
    save(
        "es-failure-pass.json",
        {
            "passed": True,
            "blocked_offset": before,
            "recovered_offset": recovered["offset"],
        },
    )

elif STAGE == "lost-response":
    before = broker_offset()
    metrics = "http://127.0.0.1:" + str(S["api_port"]) + "/metrics"
    calls_before = client.get(metrics).json()["risk_calls"]
    (ROOT / "api-mode.txt").write_text("lost-after-commit")
    write_lines("lost-response", [RAW] * 4)
    wait(lambda: accounting(ROOT / "worker")["pending"] >= 1, "uncertain API response")
    time.sleep(8)
    assert broker_offset() == before
    assert client.get(metrics).json()["risk_calls"] == calls_before + 1
    snapshot("lost-response-blocked")
    (ROOT / "api-mode.txt").write_text("normal")
    wait(lambda: broker_offset() == before + 4, "lost response canonical replay")
    assert client.get(metrics).json()["risk_calls"] == calls_before + 4
    snapshot("lost-response-recovered")
    save(
        "lost-response-pass.json",
        {
            "passed": True,
            "no_repeat_inference": True,
            "before": before,
            "after": broker_offset(),
        },
    )

elif STAGE == "restart":
    trigger = S["processors"]["Schedule bounded source cycle"]
    processor_state(trigger, "STOPPED")
    wait(
        lambda: (
            api("GET", "/processors/" + S["processors"]["Single Kafka owner"])[
                "status"
            ]["aggregateSnapshot"]["activeThreadCount"]
            == 0
        ),
        "worker exit",
    )
    before = snapshot("before-restart")
    meta = {
        str(p.relative_to(ROOT)): p.read_bytes().hex()
        for p in (ROOT / "kafka-storage").rglob("meta.properties")
    }
    for name in ("filebeat", "nifi", "es", "kafka"):
        docker("stop", "--time", "40", owned(S["ids"][name])["Id"])
    for name in ("kafka", "es", "nifi", "filebeat"):
        docker("start", owned(S["ids"][name])["Id"])
    wait(
        lambda: (
            client.get(
                "http://127.0.0.1:" + str(S["nifi_port"]) + "/nifi-api/flow/about"
            ).status_code
            == 200
        ),
        "NiFi restart",
        seconds=240,
    )
    wait(
        lambda: client.get("http://127.0.0.1:" + str(S["es_port"])).status_code == 200,
        "ES restart",
    )
    after = snapshot("after-restart")
    assert (
        after["offset"] == before["offset"]
        and after["accounting"] == before["accounting"]
        and after["parquet_hashes"] == before["parquet_hashes"]
    )
    assert meta == {
        str(p.relative_to(ROOT)): p.read_bytes().hex()
        for p in (ROOT / "kafka-storage").rglob("meta.properties")
    }
    processor_state(trigger, "RUNNING")
    write_lines("after-restart-input", [RAW] * 4)
    wait(
        lambda: broker_offset() == before["offset"] + 4,
        "automatic source after restart",
    )
    save(
        "restart-pass.json",
        {
            "passed": True,
            "metadata": meta,
            "before": before["offset"],
            "after": broker_offset(),
        },
    )

elif STAGE == "finish":
    trigger = S["processors"]["Schedule bounded source cycle"]
    processor_state(trigger, "STOPPED")
    time.sleep(5)
    for name, identifier in S["processors"].items():
        processor_state(identifier, "STOPPED")
    save("final-snapshot.json", snapshot("final"))
    export = client.get(
        "http://127.0.0.1:"
        + str(S["nifi_port"])
        + "/nifi-api/process-groups/"
        + S["group_id"]
        + "/download"
    )
    export.raise_for_status()
    (ROOT / "runtime-export.json").write_bytes(export.content)
    save("final-nifi-flow.json", api("GET", "/flow/process-groups/" + S["group_id"]))
    order = sorted(
        S["ids"],
        key=lambda name: {"filebeat": 0, "nifi": 1, "es": 2, "kafka": 3}.get(name, 4),
    )
    for name in order:
        identifier = S["ids"][name]
        owned(identifier)
        docker("stop", "--time", "40", identifier)
        save(name + "-final.json", owned(identifier))
        (ROOT / (name + "-logs.txt")).write_text(docker("logs", identifier))
        (ROOT / (name + "-diff.txt")).write_text(docker("diff", identifier))
    pid = S["api_pid"]
    assert (
        str(E / "fixture_api.py").encode()
        in Path("/proc/" + str(pid) + "/cmdline").read_bytes()
    )
    os.kill(pid, signal.SIGTERM)
    save("finished.json", {"stopped_ids": S["ids"], "data_retained": True})
elif STAGE == "inspect":
    types = api("GET", "/flow/processor-types")
    save(
        "processor-types-focal.json",
        [
            p
            for p in types["processorTypes"]
            if p["type"].endswith(
                (
                    "AttributesToJSON",
                    "ExecuteStreamCommand",
                    "GenerateFlowFile",
                    "PutFile",
                )
            )
        ],
    )
    save(
        "processors-diagnostic.json",
        [
            api("GET", "/processors/" + identity)
            for identity in S["processors"].values()
        ],
    )
elif STAGE == "diagnose":
    save(
        "processors-diagnostic-r2.json",
        [
            api("GET", "/processors/" + identity)
            for identity in S["processors"].values()
        ],
    )
elif STAGE == "es-probe":
    save(
        "installed-guard.json", es("GET", "/_ingest/pipeline/cnc-prediction-v1").json()
    )
elif STAGE.startswith(("kb-", "cg20-")):
    pass
else:
    raise ValueError(STAGE)
