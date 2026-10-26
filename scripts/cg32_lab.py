"""CG32 private lab: Filebeat -> Kafka -> NiFi-scheduled worker -> API -> CG15/ES.

Commands (all paths absolute, one lab directory per campaign):
  init     create the lab dir, 0600 secrets, ports and budget preflight
  up       start Kafka/ES/NiFi of this project only; install the ES guard
  run      one measured run: new topic/group/root/index/API ledger per run
  model    in-process RF/IF latency of the pinned bundle (no HTTP)
  discover start Kibana, create a data view and screenshot one event by ID
  stop     stop this project's containers (no ``down -v``, nothing deleted)

The lab never touches containers, networks or volumes outside its Compose
project. It does not train, package or modify the bundle: ``--manifest`` must
point at an existing manifest whose artifact hashes match.
"""

import argparse
import hashlib
import itertools
import json
import os
import platform
import re
import secrets
import shutil
import socket
import sqlite3
import ssl
import subprocess
import sys
import threading
import time
import uuid
from contextlib import closing
from pathlib import Path

import httpx
from kafka.errors import KafkaError

from scripts import cg32_load as load
from scripts.build_automatic_graph_flow import build as build_flow

REPO = Path(__file__).resolve().parents[1]
COMPOSE = REPO / "deploy/cg32/compose.yaml"
API_SERVER = REPO / "deploy/cg32/api_server.py"
DELIVERY_RECORD = REPO / "docs/evidence/CG26_REHEARSAL_2026-10-21.json"
TRIGGER = "Schedule bounded source cycle"
# Budget agreed before starting (issue #81 step 6). Exceeding any stops the run.
BUDGET = {
    "min_free_ram_gib": 6,
    "min_free_disk_gib": 20,
    "max_lab_disk_gib": 4,
    "max_drain_s": 900,
    "max_lag": 20000,
}


def now():
    return time.time()


def sh(*args, check=True, env=None, capture=True):
    result = subprocess.run(
        list(args), capture_output=capture, text=True, env=env, check=False
    )
    if check and result.returncode != 0:
        raise RuntimeError(f"{args[0]} {args[1] if len(args) > 1 else ''} failed")
    return result


def free_port():
    with closing(socket.socket()) as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


def sha_file(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def du(path):
    total = 0
    for root, _, files in os.walk(path):
        for name in files:
            try:
                total += os.lstat(os.path.join(root, name)).st_blocks * 512
            except OSError:
                pass
    return total


class Lab:
    def __init__(self, root):
        self.root = Path(root).resolve()
        self._nifi_ssl_context = None
        self.state_path = self.root / "state.json"
        self.state = (
            json.loads(self.state_path.read_text()) if self.state_path.exists() else {}
        )

    def save(self):
        tmp = self.state_path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.state, indent=2, sort_keys=True))
        tmp.replace(self.state_path)

    def env(self, run=None, bundle=None):
        env = dict(os.environ)
        for line in (self.root / ".env").read_text().splitlines():
            key, _, value = line.partition("=")
            env[key] = value
        env.update(
            CG32_PROJECT=self.state["project"],
            CG32_LAB=str(self.root),
            CG32_REPO=str(REPO),
            CG32_UV_PYTHON=self.state["uv_python"],
            CG32_NIFI_PORT=str(self.state["nifi_port"]),
            CG32_KAFKA_PORT=str(self.state["kafka_port"]),
        )
        if run:
            env["CG32_RUN"] = run
        if bundle:
            env["CG32_BUNDLE"] = str(bundle)
        return env

    def compose(self, *args, run=None, bundle=None, check=True):
        base = ["docker", "compose", "-f", str(COMPOSE), "--env-file", "/dev/null"]
        return sh(*base, *args, env=self.env(run, bundle), check=check)

    # ---------------------------------------------------------------- init/up
    def init(self):
        if self.root.exists():
            raise SystemExit("Lab directory exists; use a new one (never reused)")
        preflight()
        self.root.mkdir(parents=True)
        for name in ("kafka", "es", "runs"):
            (self.root / name).mkdir()
        env = self.root / ".env"
        fd = os.open(env, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "w") as handle:
            handle.write(
                f"NIFI_SENSITIVE_PROPS_KEY={secrets.token_hex(16)}\n"
                f"SINGLE_USER_CREDENTIALS_USERNAME=cg32-{secrets.token_hex(4)}\n"
                f"SINGLE_USER_CREDENTIALS_PASSWORD={secrets.token_urlsafe(24)}\n"
            )
        python = Path(sys.executable)
        self.state = {
            "project": "cg32-" + uuid.uuid4().hex[:8],
            "created_utc": load.utc(now()),
            "nifi_port": free_port(),
            "kafka_port": free_port(),
            "python": str(python),
            # Mount the whole interpreter store: venv links go through a version alias.
            "uv_python": str(Path(os.path.realpath(python)).parents[2]),
            "budget": BUDGET,
            "runs": [],
        }
        self.save()
        print(json.dumps({"lab": str(self.root), "project": self.state["project"]}))

    def up(self):
        self.compose("up", "-d", "kafka", "elasticsearch", "nifi")
        port = self.compose("port", "elasticsearch", "9200").stdout.strip()
        self.state["es_url"] = "http://" + port
        network = self.state["project"] + "_default"
        inspect = json.loads(sh("docker", "network", "inspect", network).stdout)
        self.state["gateway"] = inspect[0]["IPAM"]["Config"][0]["Gateway"]
        self.save()
        wait(lambda: es_ok(self.state["es_url"]), "elasticsearch", 240)
        install_es_guard(self.state["es_url"])
        wait(self.install_nifi_ca, "nifi certificate", 120)
        wait(self.nifi_tls_ready, "nifi TLS", 120)
        wait(lambda: self.nifi_token(), "nifi", 400)
        self.state["versions"] = self.versions()
        self.save()
        print(
            json.dumps({"es": self.state["es_url"], "gateway": self.state["gateway"]})
        )

    def versions(self):
        images = {}
        out = self.compose("images", "--format", "json").stdout
        for item in json.loads(out or "[]"):
            images[item["ContainerName"]] = {
                "repository": item["Repository"],
                "tag": item["Tag"],
                "id": item["ID"],
            }
        return {
            "images": images,
            "python": platform.python_version(),
            "kernel": platform.release(),
            "cpus": os.cpu_count(),
            "git_head": sh("git", "-C", str(REPO), "rev-parse", "HEAD").stdout.strip(),
            "compose_sha256": sha_file(COMPOSE),
            "api_server_sha256": sha_file(API_SERVER),
            "lab_sha256": sha_file(__file__),
            "load_sha256": sha_file(load.__file__),
        }

    # ------------------------------------------------------------------- NiFi
    @property
    def nifi_url(self):
        return f"https://localhost:{self.state['nifi_port']}"

    def nifi_ssl_context(self):
        if self._nifi_ssl_context is None:
            ca_path = self.root / "nifi-ca.pem"
            expected = self.state.get("nifi_ca_sha256")
            if not ca_path.is_file() or sha_file(ca_path) != expected:
                raise RuntimeError("NiFi certificate is absent or has changed")
            self._nifi_ssl_context = ssl.create_default_context(cafile=ca_path)
        return self._nifi_ssl_context

    def nifi_container_id(self):
        identifier = self.compose("ps", "-q", "nifi", check=False).stdout.strip()
        if not re.fullmatch(r"[0-9a-f]{12,64}", identifier):
            return None
        labels = sh(
            "docker",
            "inspect",
            "--format",
            '{{index .Config.Labels "com.docker.compose.project"}}|'
            '{{index .Config.Labels "com.docker.compose.service"}}',
            identifier,
            check=False,
        )
        if (
            labels.returncode
            or labels.stdout.strip() != f"{self.state['project']}|nifi"
        ):
            raise RuntimeError("Refusing certificate from an unexpected container")
        return identifier

    def install_nifi_ca(self):
        ca_path = self.root / "nifi-ca.pem"
        expected = self.state.get("nifi_ca_sha256")
        if ca_path.is_file():
            if not expected or sha_file(ca_path) != expected:
                raise RuntimeError("NiFi certificate is absent or has changed")
            self._nifi_ssl_context = ssl.create_default_context(cafile=ca_path)
            return True

        identifier = self.nifi_container_id()
        if not identifier:
            return False
        export = sh(
            "docker",
            "exec",
            identifier,
            "sh",
            "-c",
            "set -eu; p=/opt/nifi/nifi-current/conf/nifi.properties; "
            "k=$(sed -n 's/^nifi.security.keystore=//p' \"$p\"); "
            "w=$(sed -n 's/^nifi.security.keystorePasswd=//p' \"$p\"); "
            '[ -n "$k" ] && [ -n "$w" ]; '
            'case "$k" in /*) ;; *) k=/opt/nifi/nifi-current/${k#./};; esac; '
            'keytool -list -rfc -keystore "$k" -storepass "$w"',
            check=False,
        )
        if export.returncode:
            return False
        certificates = re.findall(
            r"-----BEGIN CERTIFICATE-----.*?-----END CERTIFICATE-----",
            export.stdout,
            flags=re.DOTALL,
        )
        if not certificates:
            return False
        pem = ("\n".join(certificates) + "\n").encode()
        fd = os.open(ca_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "wb") as handle:
            handle.write(pem)
        self.state["nifi_ca_sha256"] = sha_file(ca_path)
        self.save()
        self._nifi_ssl_context = ssl.create_default_context(cafile=ca_path)
        return True

    def nifi_tls_ready(self):
        try:
            raw = socket.create_connection(
                ("127.0.0.1", self.state["nifi_port"]), timeout=5
            )
        except OSError:
            return False
        try:
            with (
                raw,
                self.nifi_ssl_context().wrap_socket(raw, server_hostname="localhost"),
            ):
                return True
        except ssl.SSLCertVerificationError:
            raise
        except OSError:
            return False

    def nifi_token(self):
        env = self.env()
        try:
            response = httpx.post(
                self.nifi_url + "/nifi-api/access/token",
                data={
                    "username": env["SINGLE_USER_CREDENTIALS_USERNAME"],
                    "password": env["SINGLE_USER_CREDENTIALS_PASSWORD"],
                },
                verify=self.nifi_ssl_context(),
                timeout=10,
            )
        except httpx.HTTPError:
            return None
        return response.text if response.status_code == 201 else None

    def nifi(self, method, path, **kwargs):
        token = self.nifi_token()
        response = httpx.request(
            method,
            self.nifi_url + f"/nifi-api{path}",
            headers={"Authorization": "Bearer " + token},
            verify=self.nifi_ssl_context(),
            timeout=60,
            **kwargs,
        )
        response.raise_for_status()
        return response.json() if response.content else {}

    def processor_state(self, identifier, state):
        entity = self.nifi("GET", "/processors/" + identifier)
        self.nifi(
            "PUT",
            f"/processors/{identifier}/run-status",
            json={"revision": entity["revision"], "state": state},
        )

    def stop_previous_groups(self):
        root = self.nifi("GET", "/flow/process-groups/root")["processGroupFlow"]
        for group in root["flow"]["processGroups"]:
            flow = self.nifi("GET", "/flow/process-groups/" + group["id"])
            for processor in flow["processGroupFlow"]["flow"]["processors"]:
                if processor["component"]["state"] == "RUNNING":
                    self.processor_state(processor["id"], "STOPPED")

    def upload_graph(self, run_dir, period):
        replacements = {
            "WORKER_CHECKOUT": str(REPO),
            "WORKER_PYTHON": self.state["python"],
            "GRAPH_CONFIG": str(run_dir / "graph.json"),
            "PROCESS_TEMP": str(run_dir / "process-temp"),
            "CYCLE_REPORTS": str(run_dir / "cycle-reports"),
        }
        definition = build_flow()
        for processor in definition["flowContents"]["processors"]:
            for key, value in processor["properties"].items():
                for name, actual in replacements.items():
                    value = value.replace("#{" + name + "}", actual)
                processor["properties"][key] = value
            if processor["name"] == TRIGGER:
                processor["schedulingPeriod"] = period
        (run_dir / "nifi-flow.json").write_text(json.dumps(definition, indent=1))
        root = self.nifi("GET", "/flow/process-groups/root")["processGroupFlow"]["id"]
        token = self.nifi_token()
        response = httpx.post(
            self.nifi_url + f"/nifi-api/process-groups/{root}/process-groups/upload",
            headers={"Authorization": "Bearer " + token},
            data={
                "groupName": "CG32 " + run_dir.name,
                "positionX": "0",
                "positionY": str(200 * len(self.state["runs"])),
                "clientId": self.state["project"],
            },
            files={"file": ("flow.json", json.dumps(definition), "application/json")},
            verify=self.nifi_ssl_context(),
            timeout=60,
        )
        response.raise_for_status()
        group = response.json()["id"]
        flow = self.nifi("GET", "/flow/process-groups/" + group)["processGroupFlow"]
        processors = {
            p["component"]["name"]: p["id"] for p in flow["flow"]["processors"]
        }
        for identifier in processors.values():
            self.processor_state(identifier, "STOPPED")

        def valid():
            return all(
                self.nifi("GET", "/processors/" + i)["component"]["validationStatus"]
                == "VALID"
                for i in processors.values()
            )

        wait(valid, "nifi processors valid", 60)
        return group, processors

    # -------------------------------------------------------------------- run
    def run(self, args):
        label = validate_run_label(args.label)
        manifest = verify_bundle(args.manifest)
        expected = load.validate_plan(args.rate, args.duration)
        name = f"{label}-r{args.rate}-{uuid.uuid4().hex[:6]}"
        runs_root = (self.root / "runs").resolve()
        run_dir = (runs_root / name).resolve()
        if run_dir.parent != runs_root:
            raise ValueError("Run directory escapes the lab root")
        for sub in ("input", "process-temp", "cycle-reports", "worker"):
            (run_dir / sub).mkdir(parents=True)
        lines = load.fixture_lines(REPO / "data/ai4i2020_train.csv", expected)
        topic, group = "cg32-" + name, "cg32-" + name
        index = "cnc-alerts-cg32-" + name.lower()
        graph = {
            "root": str(run_dir / "worker"),
            "manifest": str(manifest["path"]),
            "source_namespace": f"{self.state['project']}/{name}",
            "source_kind": "lab_fixture",
            "legacy_source_kind": "cg14-lab-kafka",
            "scoring_url": "http://api:8000/predict",
            "es_url": "http://elasticsearch:9200",
            "es_index": index,
            "bootstrap_servers": "kafka:19092",
            "group_id": group,
            "topic": topic,
            "offset_reset": "earliest",
            "max_records": args.max_records,
            "max_polls": args.max_polls,
            "max_poll_interval_ms": 300000,
            "attempts": args.attempts,
            "timeout": args.timeout,
        }
        # The worker only reads the manifest (never the pickles): pin a byte copy
        # inside the run dir, which is the only lab path mounted into NiFi.
        pinned = run_dir / "pinned-manifest.json"
        pinned.write_bytes(manifest["path"].read_bytes())
        graph["manifest"] = str(pinned)
        (run_dir / "graph.json").write_text(json.dumps(graph, indent=1))
        beat = (
            (REPO / "filebeat/filebeat.yml")
            .read_text()
            .replace("['/mnt/cnc-stream/*.csv']", f"['/lab/runs/{name}/input/*.csv']")
            .replace("['/mnt/cnc-smb/*.csv']", f"['/lab/runs/{name}/unused/*.csv']")
            .replace("hosts: ['kafka:9092']", "hosts: ['kafka:19092']")
            .replace("topic: cnc-sensors-lab-v2", "topic: " + topic)
        )
        (run_dir / "filebeat.yml").write_text(beat)
        self.kafka_topic(topic)
        create_index(self.state["es_url"], index)
        self.compose("stop", "kibana", check=False)  # not part of measured graph
        self.stop_previous_groups()  # single offset owner: one active graph only
        nifi_group, processors = self.upload_graph(run_dir, args.period)
        record = {
            "name": name,
            "label": label,
            "rate": args.rate,
            "duration_s": args.duration,
            "expected": expected,
            "fixture_sha256": load.fixture_hash(lines),
            "manifest_sha256": manifest["sha256"],
            "model_version": manifest["model_version"],
            "graph": graph,
            "nifi": {"period": args.period, "group": nifi_group},
            "filebeat_sha256": load.sha256(beat.encode()),
            "pause": {
                "at_s": args.pause_at,
                "for_s": args.pause_for,
                "kill_at_s": args.kill_at,
            },
            "started_utc": load.utc(now()),
        }
        self.state["runs"].append(name)
        self.save()
        bundle = manifest["path"].parent
        try:
            # Fresh API container per run: own ledger/timing files, same bundle.
            self.compose(
                "up",
                "-d",
                "--no-deps",
                "--force-recreate",
                "api",
                run=name,
                bundle=bundle,
            )
            api_port = self.compose("port", "api", "8000", run=name, bundle=bundle)
            api_url = "http://" + api_port.stdout.strip()
            wait(lambda: api_ready(api_url), "api ready", 90)
            record["health"] = httpx.get(api_url + "/health", timeout=5).json()
            for pname, identifier in processors.items():
                if pname != TRIGGER:
                    self.processor_state(identifier, "RUNNING")
            self.processor_state(processors[TRIGGER], "RUNNING")
            self.compose(
                "up", "-d", "--no-deps", "--force-recreate", "filebeat", run=name
            )
            record.update(self.measure(args, run_dir, lines, graph, processors))
        finally:
            for identifier in processors.values():
                try:
                    self.processor_state(identifier, "STOPPED")
                except httpx.HTTPError:
                    record.setdefault("errors", []).append("nifi stop failed")
            self.compose("stop", "filebeat", run=name, check=False)
            logs = self.compose("logs", "--no-color", "api", run=name, check=False)
            (run_dir / "api.log").write_text(logs.stdout + logs.stderr)
            self.compose("stop", "api", run=name, bundle=bundle, check=False)
            record["finished_utc"] = load.utc(now())
            if sys.exc_info()[0] is None:
                record.update(self.collect(run_dir, graph, record))
            else:
                record["collection"] = {
                    "status": "skipped",
                    "reason": "run_failed_before_measurement_completed",
                }
            load.write_new(run_dir / "run.json", record)
        print(json.dumps(record["metrics"], indent=1))
        return record

    def measure(self, args, run_dir, lines, graph, processors):
        es = self.state["es_url"]
        index = graph["es_index"]
        stop = threading.Event()
        seen, samples, errors = {}, [], []
        observer = KafkaObserver(
            self.state["kafka_port"], graph["topic"], graph["group_id"]
        )

        def poll_es():
            floor = "1970-01-01T00:00:00Z"
            with httpx.Client(trust_env=False, timeout=5) as client:
                while not stop.is_set():
                    try:
                        hits = client.post(
                            f"{es}/{index}/_search",
                            json={
                                "size": 1000,
                                "_source": [
                                    "event_id",
                                    "source.record_ref",
                                    "scored_at",
                                ],
                                "query": {"range": {"scored_at": {"gte": floor}}},
                                "sort": [{"scored_at": "asc"}],
                            },
                        ).json()["hits"]["hits"]
                    except (httpx.HTTPError, KeyError) as exc:
                        errors.append("es poll " + type(exc).__name__)
                        time.sleep(0.5)
                        continue
                    mono, wall = time.monotonic(), now()
                    for hit in hits:
                        ref = hit["_source"]["source"]["record_ref"]
                        if ref not in seen:
                            seen[ref] = {
                                "mono": mono,
                                "utc": load.utc(wall),
                                "event_id": hit["_source"]["event_id"],
                                "scored_at": hit["_source"]["scored_at"],
                            }
                    if hits:
                        floor = hits[-1]["_source"]["scored_at"][:19] + "Z"
                    time.sleep(0.1)

        def sample():
            while not stop.is_set():
                started = time.monotonic()
                item = {"mono": started, "utc": load.utc(now())}
                try:
                    item["kafka"] = observer.lag()
                except (KafkaError, OSError, KeyError) as exc:  # observation only
                    item["kafka_error"] = type(exc).__name__
                item["containers"] = docker_stats(self.state["project"])
                samples.append(item)
                stop.wait(max(0.0, 2.0 - (time.monotonic() - started)))

        threads = [threading.Thread(target=poll_es), threading.Thread(target=sample)]
        for thread in threads:
            thread.start()
        try:
            paused = {}
            offer_thread_result = {}

            def pause_control():
                if args.kill_at is not None:
                    # Crash the worker mid-cycle (after HTTP, before offset commit
                    # when it lands there): its uncommitted poll must be replayed.
                    time.sleep(args.kill_at)
                    deadline = time.monotonic() + 30
                    while time.monotonic() < deadline:
                        killed = self.compose(
                            "exec",
                            "-T",
                            "nifi",
                            "pkill",
                            "-9",
                            "-f",
                            "scripts.run_automatic_graph",
                            check=False,
                        )
                        if killed.returncode == 0:
                            paused["killed_mono"] = time.monotonic()
                            break
                        time.sleep(0.05)
                if args.pause_at is None:
                    return
                time.sleep(args.pause_at)
                paused["stop_mono"] = time.monotonic()
                self.processor_state(processors[TRIGGER], "STOPPED")
                time.sleep(args.pause_for)
                self.processor_state(processors[TRIGGER], "RUNNING")
                paused["resume_mono"] = time.monotonic()

            controller = threading.Thread(target=pause_control)
            controller.start()
            offer_start = time.monotonic()
            offered = load.offer(run_dir / "input" / "load.csv", lines, args.rate)
            offer_thread_result["elapsed_s"] = time.monotonic() - offer_start
            controller.join()
            drain_start = time.monotonic()
            deadline = drain_start + BUDGET["max_drain_s"]
            stopped_by = None
            while True:
                jobs = worker_jobs(graph["root"])
                done = sum(1 for v in jobs.values() if v is not None)
                if len(seen) >= len(lines) or (
                    done >= len(lines) and all(v is not None for v in jobs.values())
                ):
                    time.sleep(3)  # last refresh / final poll
                    break
                if time.monotonic() > deadline:
                    stopped_by = "max_drain_s"
                    break
                lag = samples[-1].get("kafka", {}).get("lag") if samples else None
                if lag is not None and lag > BUDGET["max_lag"]:
                    stopped_by = "max_lag"
                    break
                if du(self.root) > BUDGET["max_lab_disk_gib"] * 2**30:
                    stopped_by = "max_lab_disk"
                    break
                time.sleep(1)
            drain_end = time.monotonic()
        finally:
            stop.set()
            for thread in threads:
                thread.join()
            observer.close()
        (run_dir / "offered.jsonl").write_text(
            "".join(json.dumps(r) + "\n" for r in offered)
        )
        (run_dir / "samples.jsonl").write_text(
            "".join(json.dumps(s) + "\n" for s in samples)
        )
        (run_dir / "es-first-seen.json").write_text(json.dumps(seen, indent=1))
        return {
            "offer_elapsed_s": offer_thread_result["elapsed_s"],
            "drain_s": drain_end - drain_start,
            "first_offer_mono": offered[0]["written_mono"],
            "last_seen_mono": max((v["mono"] for v in seen.values()), default=None),
            "stopped_by_budget": stopped_by,
            "pause_observed": paused or None,
            "observer_errors": sorted(set(errors)),
        }

    def kafka_topic(self, topic):
        self.compose(
            "exec",
            "-T",
            "kafka",
            "/opt/kafka/bin/kafka-topics.sh",
            "--bootstrap-server",
            "kafka:19092",
            "--create",
            "--topic",
            topic,
            "--partitions",
            "1",
            "--replication-factor",
            "1",
        )

    def collect(self, run_dir, graph, record):
        offered = [
            json.loads(x) for x in (run_dir / "offered.jsonl").read_text().splitlines()
        ]
        seen = json.loads((run_dir / "es-first-seen.json").read_text())
        records = dump_topic(self.state["kafka_port"], graph["topic"])
        (run_dir / "kafka-records.jsonl").write_text(
            "".join(json.dumps(r) + "\n" for r in records)
        )
        jobs = worker_jobs(graph["root"])
        es_docs = es_all(self.state["es_url"], graph["es_index"])
        (run_dir / "es-docs.json").write_text(json.dumps(es_docs, indent=1))
        committed = dump_committed(
            self.state["kafka_port"], graph["topic"], graph["group_id"]
        )
        reconciliation = load.reconcile(
            offered, records, jobs, es_docs, committed["committed"]
        )
        timing = [
            json.loads(x)
            for x in (run_dir / "api-timing.jsonl").read_text().splitlines()
        ]
        predict = [t for t in timing if t["path"] == "/predict"]
        http_ok = [t["ms"] for t in predict if t["status"] == 200]
        e2e = load.e2e_latencies(
            offered, records, {ref: v["mono"] for ref, v in seen.items()}
        )
        samples = [
            json.loads(x) for x in (run_dir / "samples.jsonl").read_text().splitlines()
        ]
        lags = [s["kafka"]["lag"] for s in samples if "kafka" in s]
        span = (
            record["last_seen_mono"] - record["first_offer_mono"]
            if record.get("last_seen_mono")
            else None
        )
        http = load.percentiles(http_ok)
        e2e_stats = load.percentiles(e2e)
        metrics = {
            # Achieved offer rate between first and last write (n-1 intervals).
            "offered_eps": (len(offered) - 1)
            / (offered[-1]["written_mono"] - offered[0]["written_mono"])
            if len(offered) > 1
            else None,
            "throughput_eps": len(seen) / span if span else None,
            "http_requests": len(predict),
            "http_non_200": len(predict) - len(http_ok),
            "http_p50_ms": http["p50"],
            "http_p95_ms": http["p95"],
            "e2e_p50_ms": e2e_stats["p50"],
            "e2e_p95_ms": e2e_stats["p95"],
            "e2e_max_ms": e2e_stats["max"],
            "e2e_n": e2e_stats["n"],
            "producer_lag_max_ms": max(r["producer_lag_ms"] for r in offered),
            "lag_initial": lags[0] if lags else None,
            "lag_max": max(lags) if lags else None,
            "lag_final": lags[-1] if lags else None,
            "drain_s": record["drain_s"],
            "cpu_s": cpu_by_container(samples),
            "rss_max_mib": rss_by_container(samples),
            "bytes": {
                "input": (run_dir / "input/load.csv").stat().st_size,
                "worker_root": du(run_dir / "worker"),
                "kafka_topic_values": sum(r["bytes"] for r in records),
                "es_index_store": es_store(self.state["es_url"], graph["es_index"]),
            },
        }
        cycles = sorted((run_dir / "worker/automatic-cycles").glob("*.json"))
        statuses = {}
        for path in cycles:
            status = json.loads(path.read_text())["status"]
            statuses[status] = statuses.get(status, 0) + 1
        # NiFi diagnostics include cycles killed before writing their own report.
        exits = {}
        for path in (run_dir / "cycle-reports/diagnostics").glob("*"):
            code = json.loads(path.read_text()).get("execution.status", "")
            exits[code] = exits.get(code, 0) + 1
        attempts = {}
        database = run_dir / "worker/pipeline.sqlite3"
        if database.exists():
            uri = database.as_uri() + "?mode=ro"
            with closing(sqlite3.connect(uri, uri=True)) as con:
                for result, count in con.execute(
                    "SELECT result, count(*) FROM attempts GROUP BY result"
                ):
                    attempts[str(result)[:80]] = count
        return {
            "metrics": metrics,
            "reconciliation": reconciliation,
            "cycles": statuses,
            "nifi_exit_status": exits,
            "worker_attempts": attempts,
            "http_repeated_posts": len(predict) - reconciliation["observed"],
            "kafka_committed": committed,
        }

    # -------------------------------------------------------------- discover
    def discover(self, args):
        self.compose("up", "-d", "kibana")
        port = self.compose("port", "kibana", "5601").stdout.strip()
        kibana = "http://" + port
        wait(lambda: kibana_ok(kibana), "kibana", 300)
        headers = {"kbn-xsrf": "cg32", "Content-Type": "application/json"}
        view = httpx.post(
            f"{kibana}/api/data_views/data_view",
            headers=headers,
            json={
                "data_view": {
                    "title": args.index,
                    "name": "CG32 " + args.index,
                    "timeFieldName": "timestamp",
                }
            },
            timeout=30,
        )
        view.raise_for_status()
        view_id = view.json()["data_view"]["id"]
        url = (
            f"{kibana}/app/discover#/?_g=(time:(from:'2026-10-22T00:00:00Z',"
            f"to:'2026-10-24T00:00:00Z'))&_a=(dataSource:(dataViewId:'{view_id}',"
            f"type:dataView),query:(language:kuery,query:'event_id:\"{args.event_id}\"'))"
        )
        out = Path(args.output)
        out.mkdir(parents=True)
        (out / "discover-url.txt").write_text(url + "\n")
        sh(
            "chromium",
            "--headless=new",
            "--disable-gpu",
            "--no-first-run",
            f"--user-data-dir={out / 'chromium-profile'}",
            "--window-size=1600,1000",
            "--virtual-time-budget=25000",
            f"--screenshot={out / 'discover.png'}",
            url,
        )
        shutil.rmtree(out / "chromium-profile", ignore_errors=True)
        hit = httpx.post(
            f"{self.state['es_url']}/{args.index}/_search",
            json={"query": {"term": {"event_id": args.event_id}}},
            timeout=10,
        ).json()["hits"]
        load.write_new(out / "es-query.json", hit)
        self.compose("stop", "kibana")  # never leave Kibana running during runs
        print(
            json.dumps({"hits": hit["total"], "screenshot": str(out / "discover.png")})
        )

    def stop(self):
        # Profiled services (api, filebeat, kibana) are only stopped when named.
        self.compose("--profile", "run", "--profile", "dashboard", "stop")


# ------------------------------------------------------------------ helpers
def preflight():
    meminfo = dict(
        line.split(":", 1) for line in Path("/proc/meminfo").read_text().splitlines()
    )
    available = int(meminfo["MemAvailable"].split()[0]) / 2**20
    disk = shutil.disk_usage(Path.home()).free / 2**30
    if available < BUDGET["min_free_ram_gib"] or disk < BUDGET["min_free_disk_gib"]:
        raise SystemExit(
            f"Budget preflight failed: RAM {available:.1f} GiB, disk {disk:.1f} GiB"
        )


def verify_bundle(path):
    path = Path(path).resolve()
    identity = json.loads(DELIVERY_RECORD.read_bytes())
    manifest_bytes = path.read_bytes()
    manifest_sha256 = hashlib.sha256(manifest_bytes).hexdigest()
    if manifest_sha256 != identity["manifest_sha256"]:
        raise SystemExit("Bundle manifest differs from the sealed CG26 delivery")
    manifest = json.loads(manifest_bytes)
    if manifest.get("files") != identity["model_hashes"]:
        raise SystemExit("Bundle file identities differ from the sealed CG26 delivery")
    for name, expected in identity["model_hashes"].items():
        if sha_file(path.parent / name) != expected:
            raise SystemExit(f"Bundle artifact hash mismatch: {name}")
    return {
        "path": path,
        "sha256": manifest_sha256,
        "model_version": manifest.get("model_version"),
    }


def wait(predicate, what, seconds):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        try:
            if predicate():
                return
        except (httpx.HTTPError, KeyError, ValueError, TypeError):
            pass  # service still starting; the deadline bounds the wait
        time.sleep(2)
    raise TimeoutError(what)


def es_ok(url):
    return httpx.get(url + "/_cluster/health", timeout=5).json()["status"] in (
        "green",
        "yellow",
    )


def kibana_ok(url):
    return (
        httpx.get(url + "/api/status", timeout=5).json()["status"]["overall"]["level"]
        == "available"
    )


def api_ready(url):
    return httpx.get(url + "/health", timeout=2).status_code == 200


def install_es_guard(url):
    with httpx.Client(trust_env=False, timeout=30) as client:
        pipeline = json.loads((REPO / "elasticsearch/ingest-pipeline.json").read_text())
        client.put(
            f"{url}/_ingest/pipeline/cnc-prediction-v1", json=pipeline
        ).raise_for_status()
        template = json.loads((REPO / "elasticsearch/index-template.json").read_text())
        client.put(
            f"{url}/_index_template/cnc-lab-v1", json=template
        ).raise_for_status()


def create_index(url, index):
    httpx.put(f"{url}/{index}", timeout=30).raise_for_status()


def es_all(url, index):
    httpx.post(f"{url}/{index}/_refresh", timeout=30).raise_for_status()
    docs, after = {}, None
    while True:
        body = {
            "size": 1000,
            "_source": ["event_id", "source.record_ref"],
            "sort": [{"event_id": "asc"}],
        }
        if after:
            body["search_after"] = after
        hits = httpx.post(f"{url}/{index}/_search", json=body, timeout=30).json()[
            "hits"
        ]["hits"]
        if not hits:
            return docs
        for hit in hits:
            ref = hit["_source"]["source"]["record_ref"]
            if ref in docs:
                docs[ref + "#dup"] = hit["_source"]["event_id"]
            docs[ref] = hit["_source"]["event_id"]
        after = hits[-1]["sort"]


def es_store(url, index):
    stats = httpx.get(f"{url}/{index}/_stats/store", timeout=30).json()
    return stats["_all"]["primaries"]["store"]["size_in_bytes"]


def worker_jobs(root):
    """record_ref -> outcome from the worker journal (read-only)."""
    database = Path(root) / "pipeline.sqlite3"
    if not database.exists():
        return {}
    try:
        with closing(sqlite3.connect(database.as_uri() + "?mode=ro", uri=True)) as con:
            rows = con.execute("SELECT id, outcome FROM jobs").fetchall()
    except sqlite3.OperationalError:
        return {}
    jobs = {}
    for delivery, outcome in rows:
        _, _, topic, partition, offset = json.loads(delivery)
        jobs[f"{topic}/{partition}/{offset}"] = outcome
    return jobs


class KafkaObserver:
    """Read-only: committed offset of the worker group vs log end.

    ``committed()`` is an OffsetFetch; without subscribe/assign/poll this
    client never joins the group, so it cannot trigger a rebalance of the worker.
    """

    def __init__(self, port, topic, group):
        from kafka import KafkaConsumer, TopicPartition

        self.partition = TopicPartition(topic, 0)
        self.consumer = KafkaConsumer(
            bootstrap_servers=f"127.0.0.1:{port}",
            group_id=group,
            enable_auto_commit=False,
        )

    def lag(self):
        end = self.consumer.end_offsets([self.partition])[self.partition]
        position = self.consumer.committed(self.partition) or 0
        return {"end": end, "committed": position, "lag": end - position}

    def close(self):
        self.consumer.close(autocommit=False)


def dump_topic(port, topic):
    from kafka import KafkaConsumer, TopicPartition

    partition = TopicPartition(topic, 0)
    consumer = KafkaConsumer(
        bootstrap_servers=f"127.0.0.1:{port}", enable_auto_commit=False
    )
    consumer.assign([partition])
    consumer.seek_to_beginning(partition)
    end = consumer.end_offsets([partition])[partition]
    records = []
    while consumer.position(partition) < end:
        for batch in consumer.poll(timeout_ms=1000).values():
            for message in batch:
                line = message.value.decode("utf-8", errors="replace")
                records.append(
                    {
                        "topic": topic,
                        "partition": 0,
                        "offset": message.offset,
                        "key": load.line_key(line),
                        "bytes": len(message.value),
                        "timestamp_ms": message.timestamp,
                    }
                )
    consumer.close()
    return records


def dump_committed(port, topic, group):
    observer = KafkaObserver(port, topic, group)
    try:
        return observer.lag()
    finally:
        observer.close()


def docker_stats(project):
    out = sh(
        "docker",
        "stats",
        "--no-stream",
        "--format",
        "{{json .}}",
        check=False,
    ).stdout
    stats = {}
    for line in out.splitlines():
        item = json.loads(line)
        if item["Name"].startswith(project + "-"):
            stats[item["Name"][len(project) + 1 :]] = {
                "cpu_pct": float(item["CPUPerc"].rstrip("%") or 0),
                "mem": item["MemUsage"].split("/")[0].strip(),
            }
    return stats


def mib(text):
    value, unit = float(text[:-3]), text[-3:]
    scale = {"KiB": 1 / 1024, "MiB": 1, "GiB": 1024}.get(unit)
    if scale is None:
        value, unit = float(text[:-1]), text[-1]
        scale = 1 / 2**20
    return value * scale


def cpu_by_container(samples):
    """Integrated CPU-seconds from 2 s docker stats samples (approximation)."""
    totals = {}
    for previous, current in itertools.pairwise(samples):
        interval = current["mono"] - previous["mono"]
        for name, item in current.get("containers", {}).items():
            totals[name] = totals.get(name, 0) + item["cpu_pct"] / 100 * interval
    return totals


def rss_by_container(samples):
    peaks = {}
    for sample in samples:
        for name, item in sample.get("containers", {}).items():
            peaks[name] = max(peaks.get(name, 0), mib(item["mem"]))
    return peaks


def model_latency(manifest_path, count, output):
    """In-process RF+IF latency, one event at a time as the API does."""
    import joblib
    import pandas as pd

    bundle = verify_bundle(manifest_path)
    models = {
        name: joblib.load(bundle["path"].parent / name) for name in ("rf.pkl", "if.pkl")
    }
    rows = load.nominal_rows(REPO / "data/ai4i2020_train.csv", count)
    columns = ["machine_type", *load.SENSORS]
    frames = [
        pd.DataFrame(
            [{c: (r[c] if c == "machine_type" else float(r[c])) for c in columns}]
        )
        for r in rows
    ]
    for frame in frames[:20]:  # warm-up, excluded
        models["rf.pkl"].predict_proba(frame)
        models["if.pkl"].score_samples(frame)
    values = []
    for frame in frames:
        start = time.perf_counter()
        models["rf.pkl"].predict_proba(frame)
        models["if.pkl"].score_samples(frame)
        values.append((time.perf_counter() - start) * 1000)
    result = {
        "manifest_sha256": bundle["sha256"],
        "model_version": bundle["model_version"],
        "measure": "predict_proba(RF)+score_samples(IF), 1 row DataFrame, perf_counter",
        "warmup_excluded": 20,
        **load.percentiles(values),
        "values_ms": values,
    }
    load.write_new(output, result)
    print(json.dumps({k: v for k, v in result.items() if k != "values_ms"}))


def validate_run_label(value):
    if not re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{0,30}[a-z0-9])?", value):
        raise argparse.ArgumentTypeError(
            "label must be 1-32 lowercase ASCII letters, digits or internal hyphens"
        )
    return value


def main(argv=None):
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--lab", type=Path, required=True)
    sub = cli.add_subparsers(dest="command", required=True)
    sub.add_parser("init")
    sub.add_parser("up")
    sub.add_parser("stop")
    run = sub.add_parser("run")
    run.add_argument("--manifest", type=Path, required=True)
    run.add_argument("--label", required=True, type=validate_run_label)
    run.add_argument("--rate", type=int, required=True)
    run.add_argument("--duration", type=int, required=True)
    run.add_argument("--period", default="2 sec", help="NiFi trigger period")
    run.add_argument("--max-records", type=int, default=1)
    run.add_argument("--max-polls", type=int, default=3)
    run.add_argument("--attempts", type=int, default=1)
    run.add_argument("--timeout", type=float, default=0.5)
    run.add_argument("--pause-at", type=float)
    run.add_argument("--pause-for", type=float, default=0)
    run.add_argument("--kill-at", type=float, help="SIGKILL the worker after N s")
    model = sub.add_parser("model")
    model.add_argument("--manifest", type=Path, required=True)
    model.add_argument("--count", type=int, default=600)
    model.add_argument("--output", type=Path, required=True)
    disc = sub.add_parser("discover")
    disc.add_argument("--index", required=True)
    disc.add_argument("--event-id", required=True)
    disc.add_argument("--output", type=Path, required=True)
    args = cli.parse_args(argv)
    lab = Lab(args.lab)
    if args.command == "model":
        model_latency(args.manifest, args.count, args.output)
    elif args.command == "run":
        lab.run(args)
    elif args.command == "discover":
        lab.discover(args)
    else:
        getattr(lab, args.command)()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
