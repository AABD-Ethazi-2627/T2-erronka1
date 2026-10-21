#!/usr/bin/env python3
"""Host-only, fail-closed RESTORE E2E. --plan is entirely offline.

No import, deletion, container restart, .env access or automatic producer retry.
An interrupted producer is terminal for --test: use --verify/--stop and retain
its topic. A new execution requires stopped components and explicit new run ID.
"""

from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
import re
import signal
import ssl
import subprocess
import sys
import time
import urllib.request
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path

DEPLOY = Path(__file__).resolve().parents[1]
REPO = DEPLOY.parents[1]
sys.path.insert(0, str(REPO))
import cg14_restore_upload as auth
from cg14_validation.reconciliation import content_hash, dlq_summary, reconciled
from cg14_validation.validator import parse_csv_event

TARGET = "5d4f0539-01a1-1000-4a08-0a3f4c8946d8"
SERVICE = "ce5c27e6-986a-3047-bead-420bdcc8ef65"
NAME = "CNC-GUARD-CG14-RESTORE-TEST"
ORIGINAL = auth.ORIGINAL
BROKER = "cnc-cg14-kafka-test"
BOOTSTRAP = "cg14-kafka-test:9092"
NETWORK = "cg14-nifi"
FLOW = REPO / "nifi-flows/cg14_validation_flow_nifi_2.12.0_restore_safe_20261020.json"
INVENTORY = DEPLOY / "restore-inventory.json"
INVENTORY_SHA256 = "2231b311018f7dc50a9a130dc556a895f20b9959c9ebbf3e213280ca45de32da"
MOCK_SHA256 = "f45dfc70a95e86e71b5800213ce9eaccbec8e4db122f4e72b320de9268fd1bcc"
MOCK_IMAGE = "python:3.13-alpine@sha256:2d9aefe2fef018a7eb2c13064c89c71929800fd2e5dccdbf52ea5da5bb8d929a"
CONSUMER = "ConsumeKafka — CG14 synthetic E2E"
METADATA = "CG14 lab — Kafka source metadata"
HTTP = "InvokeHTTP — local CG14 mock only"
DLQ = "DLQ — durable local file sink"
GuardError = auth.GuardError
require = auth.require


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def resources(run):
    require(
        bool(re.fullmatch(r"[a-z0-9]{8,32}", run)), "run-id: 8–32 caracteres a-z/0-9."
    )
    return {
        "run_id": run,
        "target": TARGET,
        "topic": "cg14-restore-" + run,
        "consumer_group": "cg14-restore-group-" + run,
        "mock": "cg14-restore-mock-" + run,
        "dlq": "/opt/nifi/cg14-dlq/restore-" + run,
        "host_dlq": str(DEPLOY / "data/dlq" / ("restore-" + run)),
    }


def static():
    raw, result = auth.preflight(FLOW)
    flow = json.loads(raw)["flowContents"]
    require(
        hashlib.sha256(INVENTORY.read_bytes()).hexdigest() == INVENTORY_SHA256,
        "Inventario runtime distinto de la evidencia aprobada.",
    )
    require(
        hashlib.sha256((DEPLOY / "scripts/mock_predict.py").read_bytes()).hexdigest()
        == MOCK_SHA256,
        "Mock modificado; revisar contrato antes de ejecutar.",
    )
    inv = json.loads(INVENTORY.read_text())
    require(
        {p["identifier"] for p in inv["processors"]}
        == {p["identifier"] for p in flow["processors"]},
        "Inventario incompleto.",
    )
    require(
        len({p["instanceIdentifier"] for key in inv for p in inv[key]}) == 51,
        "IDs runtime duplicados.",
    )
    require(
        inv["controllerServices"][0]["instanceIdentifier"] == SERVICE, "CS inesperado."
    )
    return flow, inv, result


def desired(flow, inv, r):
    patches = {}
    names = {p["name"]: p["instanceIdentifier"] for p in inv["processors"]}
    patches[names[CONSUMER]] = {
        "Topics": r["topic"],
        "Group ID": r["consumer_group"],
        "Kafka Connection Service": SERVICE,
    }
    patches[names[METADATA]] = {
        "cg14.source.uri": "kafka://cg14-kafka-test/" + r["topic"],
        "cg14.source.kind": "restore-" + r["run_id"],
        "cg14.mock.scenario": "${kafka.key}",
    }
    patches[names[HTTP]] = {
        "HTTP URL": "http://" + r["mock"] + ":8080/predict/${cg14.mock.scenario}",
        "Response Redirects Enabled": "false",
    }
    patches[names[DLQ]] = {"Directory": r["dlq"]}
    return patches


class Api(auth.Api):
    # Keep login/request inherited: strip username only, preserve password,
    # form-urlencoded token POST through the same TLS/no-proxy/no-redirect client.
    def call(self, path, method="GET", payload=None):
        headers = {
            "Accept": "application/json",
            "Authorization": "Bearer " + self.token,
        }
        data = None
        if payload is not None:
            headers["Content-Type"] = "application/json"
            data = json.dumps(payload).encode()
        request = urllib.request.Request(
            auth.API_BASE + path, data=data, headers=headers, method=method
        )
        with self.opener.open(request, timeout=30) as response:
            raw = response.read()
            return json.loads(raw) if raw else {}

    def get(self, path):
        return self.call(path)


def docker(*args, input_bytes=None):
    # No shell, no raw stderr (Docker may include host environment data).
    result = subprocess.run(
        ["docker", *args],
        input=input_bytes,
        capture_output=True,
        timeout=90,
        check=False,
    )
    require(
        result.returncode == 0,
        "Docker falló; inspeccionar desde host (salida omitida).",
    )
    return result.stdout.decode()


def kafka(tool, *args, input_bytes=None):
    return docker(
        "exec",
        *(["-i"] if input_bytes is not None else []),
        BROKER,
        "/opt/kafka/bin/kafka-" + tool + ".sh",
        "--bootstrap-server",
        BOOTSTRAP,
        *args,
        input_bytes=input_bytes,
    )


def read_offsets(group):
    if group not in kafka("consumer-groups", "--list").splitlines():
        return ""
    return kafka("consumer-groups", "--describe", "--group", group)


def inspect(container):
    return json.loads(docker("inspect", container))[0]


def snapshot(api, inv):
    group = api.get("/process-groups/" + TARGET)["component"]
    require(
        group["id"] == TARGET and group["name"] == NAME and TARGET != ORIGINAL,
        "Grupo destino incorrecto.",
    )
    require(not group.get("parameterContext"), "Parameter Context no permitido.")
    f = api.flow(TARGET)["flow"]
    require(
        not any(
            f.get(k)
            for k in (
                "processGroups",
                "remoteProcessGroups",
                "inputPorts",
                "outputPorts",
                "funnels",
            )
        ),
        "Dependencias externas.",
    )
    ps = {p["component"]["id"]: p for p in f["processors"]}
    cs = {
        s["component"]["id"]: s
        for s in api.get("/flow/process-groups/" + TARGET + "/controller-services")[
            "controllerServices"
        ]
    }
    for key, entities in [("processors", ps), ("controllerServices", cs)]:
        require(
            set(entities) == {p["instanceIdentifier"] for p in inv[key]},
            "IDs de componentes distintos.",
        )
        for p in inv[key]:
            c = entities[p["instanceIdentifier"]]["component"]
            require(c.get("parentGroupId") == TARGET, "Componente fuera de RESTORE.")
            require(
                all(c[k] == p[k] for k in ("name", "type", "bundle")),
                "Tipo/nombre/bundle distinto.",
            )
            cfg = c.get("config", c)
            for key2, desc in cfg.get("descriptors", {}).items():
                require(
                    not (desc.get("sensitive") and cfg.get("properties", {}).get(key2)),
                    "Propiedad sensible configurada; no guardar snapshot.",
                )
    require(
        {c["component"]["id"] for c in f["connections"]}
        == {c["instanceIdentifier"] for c in inv["connections"]},
        "IDs de conexiones distintos.",
    )
    require(
        all(
            c["component"][end]["id"] in ps
            for c in f["connections"]
            for end in ("source", "destination")
        ),
        "Conexión externa.",
    )
    return ps, cs, f


def properties(entity):
    c = entity["component"]
    return c.get("config", c)["properties"]


def configuration_guard(ps, cs, f, flow, inv, r, *, isolated):
    """Only the pinned definition and the explicit isolation patch are accepted."""
    patches = desired(flow, inv, r)
    logical = {
        p["identifier"]: p["instanceIdentifier"]
        for p in inv["processors"] + inv["controllerServices"]
    }
    for key, entities in [("processors", ps), ("controllerServices", cs)]:
        for p in flow[key]:
            cid = logical[p["identifier"]]
            expected = dict(p["properties"])
            if key == "processors" and p["name"] == CONSUMER:
                expected["Kafka Connection Service"] = SERVICE
            current = properties(entities[cid])
            for prop in set(current) | set(expected):
                allowed = [expected.get(prop)]
                if prop in patches.get(cid, {}):
                    allowed.append(patches[cid][prop])
                require(
                    current.get(prop) in allowed,
                    "Propiedad inesperada: " + p["name"] + "/" + prop,
                )
            if isolated:
                require(
                    all(current.get(k) == v for k, v in patches.get(cid, {}).items()),
                    "Aislamiento incompleto: " + p["name"],
                )
            # No automatic retries outside the two explicit RouteOnAttribute retries.
            if key == "processors":
                cfg = entities[cid]["component"]["config"]
                require(
                    not cfg.get("retriedRelationships"), "Retry adicional no permitido."
                )
                require(
                    set(cfg.get("autoTerminatedRelationships", []))
                    == set(p.get("autoTerminatedRelationships", [])),
                    "Auto-terminaciones distintas.",
                )

    def edges(items, export=False):
        return sorted(
            (
                logical[c["source"]["id"]] if export else c["source"]["id"],
                logical[c["destination"]["id"]] if export else c["destination"]["id"],
                sorted(c["selectedRelationships"]),
            )
            for c in items
        )

    require(
        edges([c["component"] for c in f["connections"]])
        == edges(flow["connections"], True),
        "Relaciones de conexiones distintas.",
    )
    require(
        properties(cs[SERVICE])["bootstrap.servers"] == BOOTSTRAP,
        "Broker no autorizado.",
    )


def stopped(ps, cs, f):
    require(
        all(p["component"]["state"] in ("STOPPED", "DISABLED") for p in ps.values()),
        "Hay componentes running/transitorios.",
    )
    require(cs[SERVICE]["component"]["state"] == "DISABLED", "CS debe estar DISABLED.")
    require(
        all(
            int(c.get("status", {}).get("aggregateSnapshot", {}).get("queuedCount", -1))
            == 0
            for c in f["connections"]
        ),
        "Colas no vacías o sin estado.",
    )


def compare_original(api, ps, r):
    original, _services = auth.components(api, ORIGINAL)
    for e in original["processors"]:
        p = properties(e)
        if e["component"]["type"].endswith("ConsumeKafka"):
            topics = p.get("Topics") or ""
            group = p.get("Group ID") or ""
            require(
                p.get("Topic Format") == "names"
                and "${" not in topics
                and "#{" not in topics,
                "Topics originales dinámicos: no se puede demostrar exclusividad.",
            )
            require(
                r["topic"] not in {t.strip() for t in topics.split(",")},
                "Topic compartido con original.",
            )
            require(
                "${" not in group and "#{" not in group,
                "Consumer group original dinámico.",
            )
            require(group.strip() != r["consumer_group"], "Consumer group compartido.")
        if e["component"]["type"].endswith("PutFile"):
            original_dir = p.get("Directory", "").rstrip("/")
            require(original_dir != r["dlq"], "DLQ compartida.")
        if e["component"]["type"].endswith("InvokeHTTP"):
            require(
                r["mock"] not in p.get("HTTP URL", ""), "Mock compartido con original."
            )
    require(
        all(
            p["component"]["id"]
            not in {e["component"]["id"] for e in original["processors"]}
            for p in ps.values()
        ),
        "IDs compartidos con original.",
    )


def runtime_guard(r, mock_required=False):
    nifi, broker = inspect("cnc-cg14-nifi"), inspect(BROKER)
    for obj in (nifi, broker):
        require(obj["State"]["Running"], "Contenedor base detenido.")
        require(NETWORK in obj["NetworkSettings"]["Networks"], "Red incorrecta.")
    require(
        broker["Config"]["Image"].startswith("apache/kafka:4.3.1@sha256:"),
        "Imagen broker distinta.",
    )
    require(
        not any(broker["NetworkSettings"]["Ports"].values()), "Kafka publica puertos."
    )
    https_ports = [
        v.split("=", 1)[1]
        for v in nifi["Config"]["Env"]
        if v.startswith("NIFI_WEB_HTTPS_PORT=")
    ]
    require(
        len(https_ports) == 1 and https_ports[0].isdigit(),
        "Puerto HTTPS NiFi no identificado.",
    )
    published = {k: v for k, v in nifi["NetworkSettings"]["Ports"].items() if v}
    require(
        published
        == {https_ports[0] + "/tcp": [{"HostIp": "127.0.0.1", "HostPort": "18443"}]},
        "Publicación NiFi distinta.",
    )
    km = [m for m in broker["Mounts"] if m["Destination"] == "/tmp/kraft-combined-logs"]
    require(
        len(km) == 1
        and km[0]["Type"] == "bind"
        and km[0]["RW"]
        and Path(km[0]["Source"]).resolve() == (DEPLOY / "data/kafka-test").resolve(),
        "Persistencia Kafka distinta.",
    )
    aliases = broker["NetworkSettings"]["Networks"][NETWORK].get("Aliases", [])
    require(
        "cg14-kafka-test" in aliases
        or broker["Config"]["Hostname"] == "cg14-kafka-test",
        "DNS broker incorrecto.",
    )
    env = broker["Config"]["Env"]
    require(
        "KAFKA_ADVERTISED_LISTENERS=PLAINTEXT://cg14-kafka-test:9092" in env,
        "Listeners broker distintos.",
    )
    mounts = [m for m in nifi["Mounts"] if m["Destination"] == "/opt/nifi/cg14-dlq"]
    require(
        len(mounts) == 1
        and mounts[0]["Type"] == "bind"
        and mounts[0]["RW"]
        and Path(mounts[0]["Source"]).resolve() == (DEPLOY / "data/dlq").resolve(),
        "Bind DLQ distinto.",
    )
    require(not (DEPLOY / "data/dlq").is_symlink(), "DLQ symlink.")
    require(not Path(r["host_dlq"]).is_symlink(), "DLQ exclusiva symlink.")
    if mock_required:
        mock_guard(inspect(r["mock"]), r)
        mock_ready(r)


def mock_ready(r):
    deadline = time.monotonic() + 15
    while True:
        try:
            docker(
                "exec",
                r["mock"],
                "python",
                "-c",
                "import json,urllib.request; r=urllib.request.urlopen('http://127.0.0.1:8080/healthz', timeout=2); "
                "ok=r.status==200 and json.load(r)=={'mock':True,'status':'ready'}; "
                "raise SystemExit(0 if ok else 1)",
            )
            return
        except GuardError:
            if time.monotonic() >= deadline:
                raise GuardError("Mock no responde a healthz.") from None
            time.sleep(0.5)


def mock_guard(obj, r, *, running=True):
    require(
        obj["Name"] == "/" + r["mock"] and (obj["State"]["Running"] or not running),
        "Mock no disponible.",
    )
    require(
        obj["Config"]["Labels"].get("cg14.restore.run") == r["run_id"],
        "Mock ajeno/con estado compartido.",
    )
    require(
        obj["Config"]["Image"] == MOCK_IMAGE
        and obj["Config"]["Cmd"] == ["python", "-u", "/app/mock_predict.py"],
        "Mock inesperado.",
    )
    require(
        set(obj["NetworkSettings"]["Networks"]) == {NETWORK}
        and not any(obj["NetworkSettings"]["Ports"].values()),
        "Mock publica puertos/red distinta.",
    )
    require(
        obj["HostConfig"]["ReadonlyRootfs"] and len(obj["Mounts"]) == 1,
        "Mock no aislado.",
    )
    cfg, host = obj["Config"], obj["HostConfig"]
    require(
        cfg.get("User") == "65534:65534"
        and not cfg.get("Entrypoint")
        and not host.get("Privileged")
        and host.get("NetworkMode") == NETWORK
        and not host.get("PortBindings")
        and host.get("RestartPolicy", {}).get("Name") == "no"
        and "ALL" in (host.get("CapDrop") or [])
        and "no-new-privileges:true" in (host.get("SecurityOpt") or []),
        "Ejecución mock distinta.",
    )
    m = obj["Mounts"][0]
    require(
        m.get("Type") == "bind"
        and not m["RW"]
        and m["Destination"] == "/app/mock_predict.py"
        and Path(m["Source"]).resolve()
        == (DEPLOY / "scripts/mock_predict.py").resolve(),
        "Mount mock distinto.",
    )


def save(path, state):
    temp = path.with_suffix(".tmp")
    with temp.open("w", encoding="utf-8") as f:
        os.chmod(temp, 0o600)
        json.dump(state, f, indent=2, ensure_ascii=False)
        f.write("\n")
        f.flush()
        os.fsync(f.fileno())
    os.replace(temp, path)
    fd = os.open(path.parent, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


@contextmanager
def lock():
    # One lock for the fixed target, regardless of run-id. Never unlink the inode.
    root = DEPLOY / "data/evidence/restore-e2e"
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    with (root / "target.lock").open("a") as f:
        try:
            fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise GuardError("Otro runner posee RESTORE.") from None
        yield root


class Runner:
    def __init__(self, api, flow, inv, r, path, state):
        self.api, self.flow, self.inv, self.r = api, flow, inv, r
        self.path, self.s = path, state

    def persist(self):
        save(self.path, self.s)

    def unused_run(self):
        require(
            self.r == resources(self.r["run_id"]) and self.s.get("resources") == self.r,
            "Recursos del run distintos.",
        )
        require(
            self.s.get("prepared") and self.s.get("resources_intent"),
            "Run no preparado.",
        )
        require(
            self.s.get("functional") == "NOT_TESTED"
            and not any(
                self.s.get(k)
                for k in ("test_intent", "producer", "activated", "service_intent")
            ),
            "Ejecución anterior o incierta.",
        )

    def unused_data(self):
        require(
            self.r["consumer_group"]
            not in kafka("consumer-groups", "--list").splitlines(),
            "Consumer group ya utilizado.",
        )
        directory = Path(self.r["host_dlq"])
        require(
            directory.is_dir()
            and not directory.is_symlink()
            and not any(directory.iterdir()),
            "DLQ exclusiva ausente o no vacía.",
        )
        docker(
            "exec",
            "cnc-cg14-nifi",
            "sh",
            "-c",
            'test -d "$1" && test -w "$1"',
            "restore",
            self.r["dlq"],
        )

    def resume(self):
        """Resume only the existing owned mock; reconcile uncertain start by reads only."""
        record = self.s.setdefault("mock_resume", {})
        starting = False
        checking_health = False
        try:
            self.unused_run()
            require(
                self.s.get("pending") in (None, "resume-owned-mock"),
                "Otra operación pendiente.",
            )
            require(
                self.s.get("pending") is None or record.get("start_attempted"),
                "Intención de reanudación incompleta.",
            )
            recovering = self.s.get("pending") == "resume-owned-mock"
            ps, cs, f = snapshot(self.api, self.inv)
            configuration_guard(ps, cs, f, self.flow, self.inv, self.r, isolated=True)
            compare_original(self.api, ps, self.r)
            runtime_guard(self.r)
            stopped(ps, cs, f)
            require(
                auth.original_fingerprint(self.api) == self.s["original_sha256"],
                "Original cambió.",
            )
            self.topic_guard()
            self.unused_data()
            obj = inspect(
                self.r["mock"]
            )  # Missing container: never create a replacement.
            mock_guard(obj, self.r, running=False)
            cid = obj.get("Id")
            require(
                bool(re.fullmatch(r"[a-f0-9]{64}", cid or "")), "ID Docker no válido."
            )
            require(
                not record.get("container_id") or record["container_id"] == cid,
                "Mock reemplazado.",
            )
            state = obj["State"]
            require(
                state.get("Status") in ("running", "exited", "created")
                and state["Running"] == (state["Status"] == "running")
                and not state.get("Paused")
                and not state.get("Restarting"),
                "Estado mock no reanudable.",
            )
            was_running = state["Running"]
            require(
                was_running
                or not record.get("start_attempted")
                or (
                    record.get("stop_confirmed")
                    and self.s.get("stopped")
                    and not recovering
                ),
                "Arranque anterior fallido/incierto: no repetir automáticamente.",
            )
            record["container_id"] = cid
            if not was_running:
                # Intent fsynced before Docker; a crash cannot cause a blind second start.
                record.update(
                    start_attempted=True,
                    stop_confirmed=False,
                    start_attempts=record.get("start_attempts", 0) + 1,
                    status="FAILED",
                    phase="START_OUTCOME_UNCERTAIN",
                )
                self.s["pending"] = "resume-owned-mock"
                self.s["stopped"] = (
                    False  # May already be running if the response is lost.
                )
                self.persist()
                starting = True
                docker("start", cid)
                record["phase"] = "START_RESPONDED"
                self.persist()
            observed = inspect(self.r["mock"])
            require(observed.get("Id") == cid, "Mock reemplazado durante reanudación.")
            mock_guard(observed, self.r)
            checking_health = True
            mock_ready(self.r)
            record.pop("error_kind", None)
            record.update(
                status="STARTED"
                if not was_running or recovering
                else "ALREADY_RUNNING",
                phase="HEALTHY",
                stop_confirmed=False,
                at=datetime.now(UTC).isoformat(),
            )
            self.s["pending"] = None
            self.s["stopped"] = False
            self.persist()
        except (
            OSError,
            ValueError,
            KeyError,
            TypeError,
            RuntimeError,
            subprocess.SubprocessError,
            KeyboardInterrupt,
        ) as error:
            record.update(
                status="FAILED" if starting or checking_health else "BLOCKED",
                error_kind=type(error).__name__,
            )
            self.persist()  # Preserve pending and start_attempted on uncertain outcomes.
            raise

    def action(self, label, function):
        self.s["pending"] = label
        self.persist()  # Intent durable BEFORE mutation. Never retry producer.
        result = function()
        self.s["pending"] = None
        self.persist()
        return result

    def guard(self, isolated=False, idle=False):
        ps, cs, f = snapshot(self.api, self.inv)
        configuration_guard(ps, cs, f, self.flow, self.inv, self.r, isolated=isolated)
        compare_original(self.api, ps, self.r)
        runtime_guard(self.r, mock_required=isolated)
        require(
            auth.original_fingerprint(self.api) == self.s["original_sha256"],
            "Original cambió: detener e inspeccionar.",
        )
        if idle:
            stopped(ps, cs, f)
        return ps, cs, f

    def patch(self, cid, patch):
        require(
            cid in {p["instanceIdentifier"] for p in self.inv["processors"]},
            "ID PUT no autorizado.",
        )
        e = self.api.get("/processors/" + cid)
        require(e["component"]["parentGroupId"] == TARGET, "PUT fuera del destino.")
        if all(properties(e).get(k) == v for k, v in patch.items()):
            return
        self.action(
            "properties:" + cid,
            lambda: self.api.call(
                "/processors/" + cid,
                "PUT",
                {
                    "revision": e["revision"],
                    "component": {"id": cid, "config": {"properties": patch}},
                },
            ),
        )

    def apply(self):
        self.guard(idle=True)
        require(
            not self.s.get("test_intent"), "Ejecución ya consumida: sólo verify/stop."
        )
        # Collision checks before the first resource creation. Ownership is journaled.
        topics = kafka("topics", "--list").splitlines()
        groups = kafka("consumer-groups", "--list").splitlines()
        require(self.r["consumer_group"] not in groups, "Consumer group ya existe.")
        if not self.s.get("resources_intent"):
            require(
                self.r["topic"] not in topics,
                "Topic ya existe, sin propiedad registrada.",
            )
            require(
                self.r["mock"]
                not in docker("ps", "-a", "--format", "{{.Names}}").splitlines(),
                "Mock ya existe sin propiedad registrada.",
            )
            require(
                not Path(self.r["host_dlq"]).exists(),
                "DLQ ya existe sin propiedad registrada.",
            )
            self.s["resources_intent"] = True
            self.persist()
        if self.r["topic"] not in topics:
            self.action(
                "create-topic",
                lambda: kafka(
                    "topics",
                    "--create",
                    "--topic",
                    self.r["topic"],
                    "--partitions",
                    "1",
                    "--replication-factor",
                    "1",
                    "--config",
                    "retention.ms=86400000",
                ),
            )
        self.topic_guard()
        if (
            self.r["mock"]
            not in docker("ps", "-a", "--format", "{{.Names}}").splitlines()
        ):
            self.action(
                "create-mock",
                lambda: docker(
                    "run",
                    "-d",
                    "--name",
                    self.r["mock"],
                    "--label",
                    "cg14.restore.run=" + self.r["run_id"],
                    "--network",
                    NETWORK,
                    "--pull=never",
                    "--read-only",
                    "--user",
                    "65534:65534",
                    "--cap-drop=ALL",
                    "--security-opt=no-new-privileges:true",
                    "--memory=128m",
                    "--cpus=0.25",
                    "-v",
                    str(DEPLOY / "scripts/mock_predict.py")
                    + ":/app/mock_predict.py:ro",
                    MOCK_IMAGE,
                    "python",
                    "-u",
                    "/app/mock_predict.py",
                ),
            )
        mock_guard(inspect(self.r["mock"]), self.r)
        mock_ready(self.r)
        # Create with NiFi's own UID through its existing bind mount. No container restart.
        self.action(
            "mkdir-dlq",
            lambda: docker(
                "exec",
                "cnc-cg14-nifi",
                "sh",
                "-c",
                'umask 077; mkdir -p "$1" && test -d "$1" && test -w "$1"',
                "restore",
                self.r["dlq"],
            ),
        )
        for cid, patch in desired(self.flow, self.inv, self.r).items():
            self.patch(cid, patch)
        self.guard(isolated=True, idle=True)
        self.s["prepared"] = True
        self.persist()

    def topic_guard(self):
        desc = kafka("topics", "--describe", "--topic", self.r["topic"])
        require(
            "PartitionCount: 1" in desc
            and "ReplicationFactor: 1" in desc
            and "retention.ms=86400000" in desc,
            "Configuración topic distinta.",
        )

    def state(self, cid, state, service=False):
        allowed = {p["instanceIdentifier"] for p in self.inv["processors"]}
        require(
            cid == SERVICE if service else cid in allowed, "ID state no autorizado."
        )
        if state in ("ENABLED", "RUNNING"):
            self.guard(isolated=True)
        kind = "controller-services" if service else "processors"
        e = self.api.get("/" + kind + "/" + cid)
        require(e["component"]["parentGroupId"] == TARGET, "State fuera de RESTORE.")
        if state == "RUNNING":
            deadline = time.monotonic() + 30
            while (
                e["component"].get("validationStatus") == "VALIDATING"
                and time.monotonic() < deadline
            ):
                time.sleep(0.3)
                e = self.api.get("/" + kind + "/" + cid)
            require(
                e["component"].get("validationStatus") == "VALID", "Processor no VALID."
            )
        if e["component"]["state"] != state:
            self.action(
                state + ":" + cid,
                lambda: self.api.call(
                    "/" + kind + "/" + cid + "/run-status",
                    "PUT",
                    {"revision": e["revision"], "state": state},
                ),
            )
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline:
            observed = self.api.get("/" + kind + "/" + cid)
            c = observed["component"]
            if c["state"] == state:
                if (
                    state in ("ENABLED", "RUNNING")
                    and c.get("validationStatus") != "VALID"
                ):
                    require(
                        c.get("validationStatus") != "INVALID", "Componente INVALID."
                    )
                    time.sleep(0.3)
                    continue
                if state == "STOPPED" and observed.get("status", {}).get(
                    "aggregateSnapshot", {}
                ).get("activeThreadCount", 0):
                    time.sleep(0.3)
                    continue
                self.s.setdefault("transitions", []).append(
                    {
                        "component_id": cid,
                        "state": state,
                        "validation": c.get("validationStatus"),
                        "at": datetime.now(UTC).isoformat(),
                    }
                )
                self.persist()
                return
            time.sleep(0.3)
        raise GuardError("Estado no confirmado en 30s; usar --stop.")

    def stop(self):
        # Identity checks remain mandatory; isolation/config drift must not prevent stopping owned IDs.
        ps, _cs, _ = snapshot(self.api, self.inv)
        errors = []
        for cid in reversed(self.s.get("activated", [])):
            try:
                if ps[cid]["component"]["state"] != "DISABLED":
                    self.state(cid, "STOPPED")
                self.state(cid, "DISABLED")
            except (
                OSError,
                ValueError,
                KeyError,
                TypeError,
                RuntimeError,
                subprocess.SubprocessError,
            ):
                errors.append(cid)
        if self.s.get("service_intent"):
            try:
                self.state(SERVICE, "DISABLED", service=True)
            except (
                OSError,
                ValueError,
                KeyError,
                TypeError,
                RuntimeError,
                subprocess.SubprocessError,
            ):
                errors.append(SERVICE)
        require(not errors, "Stop parcial; conservar manifiesto y repetir --stop.")
        if self.s.get("resources_intent"):
            names = docker("ps", "-a", "--format", "{{.Names}}").splitlines()
            if self.r["mock"] in names:
                obj = inspect(self.r["mock"])
                mock_guard(obj, self.r, running=False)
                if obj["State"]["Running"]:
                    self.action(
                        "stop-owned-mock", lambda: docker("stop", self.r["mock"])
                    )
                confirmed = inspect(self.r["mock"])
                mock_guard(confirmed, self.r, running=False)
                require(
                    confirmed.get("Id") == obj.get("Id")
                    and not confirmed["State"]["Running"]
                    and confirmed["State"].get("Status") in ("exited", "created"),
                    "Stop mock no confirmado.",
                )
                if self.s.get("mock_resume"):
                    self.s["mock_resume"]["stop_confirmed"] = True
                    if self.s.get("pending") == "resume-owned-mock":
                        self.s["pending"] = (
                            None  # Explicit stop resolved start uncertainty by observation.
                        )
        self.s["stopped"] = True
        self.persist()

    def rollback(self):
        # A rollback restores properties only; all touched components remain DISABLED.
        self.stop()
        ps, cs, f = snapshot(self.api, self.inv)
        stopped(ps, cs, f)
        configuration_guard(ps, cs, f, self.flow, self.inv, self.r, isolated=False)
        for cid, patch in desired(self.flow, self.inv, self.r).items():
            self.patch(
                cid, {key: self.s["prior_properties"][cid].get(key) for key in patch}
            )
        self.s["rolled_back"] = True
        self.s["prepared"] = False
        self.persist()

    def collect(self):
        ps, cs, f = snapshot(self.api, self.inv)
        configuration_guard(
            ps,
            cs,
            f,
            self.flow,
            self.inv,
            self.r,
            isolated=self.s.get("prepared", False),
        )
        compare_original(self.api, ps, self.r)
        runtime_guard(self.r)
        mock_evidence = None
        if self.s.get("resources_intent"):
            obj = inspect(self.r["mock"])
            mock_guard(obj, self.r, running=False)
            if obj["State"]["Running"]:
                mock_ready(self.r)
            mock_evidence = {
                "container_id": obj.get("Id"),
                "running": obj["State"]["Running"],
                "healthz": "READY"
                if obj["State"]["Running"]
                else "NOT_CHECKED_STOPPED",
            }
            self.topic_guard()
        status = self.api.get(
            "/flow/process-groups/" + TARGET + "/status?recursive=true"
        )
        offsets = read_offsets(self.r["consumer_group"])
        files = []
        directory = Path(self.r["host_dlq"])
        require(not directory.is_symlink(), "DLQ symlink.")
        if directory.exists():
            for p in sorted(directory.iterdir()):
                require(p.is_file() and not p.is_symlink(), "Entrada DLQ inesperada.")
                files.append(dlq_summary(p.name, p.read_bytes()))
        events = []
        complete = False
        qid = self.s.get("provenance_query")
        if qid:
            result = self.api.get("/provenance/" + qid)["provenance"]
            if result.get("finished"):
                results = result.get("results", {})
                listed = results.get("provenanceEvents", [])
                complete = not results.get("errors") and int(
                    results.get("totalCount", -1)
                ) == len(listed)
                for event in listed:
                    if event.get("id") is not None:
                        event = self.api.get("/provenance-events/" + str(event["id"]))[
                            "provenanceEvent"
                        ]
                    if event.get("componentId") not in ps:
                        continue
                    attrs = event.get("attributes") or []
                    if isinstance(attrs, list):
                        attrs = {a["name"]: a.get("value") for a in attrs}
                    if attrs.get("kafka.topic") != self.r["topic"]:
                        continue
                    safe = {
                        k: attrs[k]
                        for k in (
                            "kafka.topic",
                            "kafka.partition",
                            "kafka.offset",
                            "cg14.valid",
                            "cg14.code",
                            "cg14.event.id",
                            "cg14.mock.scenario",
                            "cg14.http.attempt",
                            "invokehttp.status.code",
                            "invokehttp.java.exception.class",
                            "filename",
                        )
                        if k in attrs
                    }
                    events.append(
                        {
                            "event_id": int(event["eventId"]),
                            "component_id": event["componentId"],
                            "type": event.get("eventType"),
                            "relationship": event.get("relationship"),
                            "attributes": safe,
                        }
                    )
        events.sort(key=lambda event: event["event_id"])
        evidence = {
            "provenance_complete": complete,
            "expected_deliveries": self.s.get("expected_deliveries"),
            "target": TARGET,
            "topic": self.r["topic"],
            "mock": mock_evidence,
            "processors": {
                cid: {
                    "state": e["component"]["state"],
                    "validation": e["component"].get("validationStatus"),
                }
                for cid, e in ps.items()
            },
            "service_state": cs[SERVICE]["component"]["state"],
            "queue": int(
                status["processGroupStatus"]["aggregateSnapshot"]["flowFilesQueued"]
            ),
            "offsets": offsets,
            "dlq": files,
            "provenance": events,
            "expected_event_ids": self.s.get("expected_event_ids"),
            "transitions": self.s.get("transitions", []),
            "original_unchanged": auth.original_fingerprint(self.api)
            == self.s["original_sha256"],
        }
        self.s["evidence"] = evidence
        if self.s.get("test_intent"):
            self.s["functional"] = (
                "VERIFIED" if functional_pass(evidence, self.inv) else "NOT_VERIFIED"
            )
        self.persist()
        return evidence

    def test(self):
        require(self.s.get("prepared"), "Ejecutar --apply primero.")
        require(
            not self.s.get("test_intent"),
            "Test enviado o incierto; no se repetirá. Usar --verify/--stop.",
        )
        require(
            self.s.get("pending") is None, "Operación pendiente: no ejecutar fixtures."
        )
        self.unused_run()
        ps, _cs, _f = self.guard(isolated=True, idle=True)
        self.topic_guard()
        self.unused_data()
        # All five Kafka records use scenario keys; no GenerateFlowFile is enabled.
        ids = {e["component"]["name"]: cid for cid, e in ps.items()}
        active = [
            cid
            for cid, e in ps.items()
            if not e["component"]["type"].endswith("GenerateFlowFile")
            and e["component"]["name"] != "Unused Groovy API probe — no input"
        ]
        active.remove(ids[CONSUMER])
        active.append(ids[CONSUMER])
        self.s["test_intent"] = True
        self.persist()
        try:
            self.s["service_intent"] = True
            self.persist()
            self.state(SERVICE, "ENABLED", service=True)
            for cid in active:
                self.s.setdefault("activated", []).append(cid)
                self.persist()
                self.state(cid, "STOPPED")
                self.state(cid, "RUNNING")
            rows, deliveries = fixture_manifest(self.r, self.s["fixture_time"])
            # Persist the complete five-delivery manifest before the one producer call.
            self.s["expected_deliveries"] = deliveries
            self.s["expected_event_ids"] = [
                d["event_id"] for d in deliveries if d["event_id"]
            ]
            self.s["producer"] = "OUTCOME_UNCERTAIN"
            self.persist()
            self.action(
                "produce-once",
                lambda: kafka(
                    "console-producer",
                    "--topic",
                    self.r["topic"],
                    "--producer-property",
                    "acks=all",
                    "--producer-property",
                    "enable.idempotence=true",
                    "--property",
                    "parse.key=true",
                    "--property",
                    "key.separator=|",
                    input_bytes="".join(rows).encode(),
                ),
            )
            self.s["producer"] = "RESPONDED"
            self.persist()
            deadline = time.monotonic() + 120
            while time.monotonic() < deadline:
                status = self.api.get("/flow/process-groups/" + TARGET + "/status")[
                    "processGroupStatus"
                ]["aggregateSnapshot"]
                off = read_offsets(self.r["consumer_group"])
                offset = offset_row(off, self.r["topic"])
                if (
                    offset == (5, 5, 0)
                    and int(status["flowFilesQueued"]) == 0
                    and downstream_idle(status, ids[CONSUMER])
                    and len(list(Path(self.r["host_dlq"]).glob("*.json"))) == 4
                ):
                    break
                time.sleep(2)
            else:
                raise GuardError("No se confirmó drenaje/offset 5 en 120s.")
        finally:
            self.stop()
        # Query only this component, then filter by topic and target IDs before persisting.
        time.sleep(3)
        query = self.action(
            "provenance-query",
            lambda: self.api.call(
                "/provenance",
                "POST",
                {
                    "provenance": {
                        "request": {
                            "maxResults": 1000,
                            "summarize": False,
                            "incrementalResults": False,
                        }
                    }
                },
            ),
        )
        self.s["provenance_query"] = query["provenance"]["id"]
        self.persist()
        deadline = time.monotonic() + 45
        while time.monotonic() < deadline:
            if self.api.get("/provenance/" + self.s["provenance_query"])[
                "provenance"
            ].get("finished"):
                break
            time.sleep(1)
        evidence = self.collect()
        require(
            functional_pass(evidence, self.inv),
            "Evidencia funcional insuficiente; no declarar VERIFIED.",
        )
        self.s["functional"] = "VERIFIED"
        self.persist()


def downstream_idle(status, consumer_id):
    rows = status.get("processorStatusSnapshots", [])
    return bool(rows) and all(
        int(p["processorStatusSnapshot"].get("activeThreadCount", -1)) == 0
        for p in rows
        if p["processorStatusSnapshot"]["id"] != consumer_id
    )


def offset_row(text, topic):
    for line in text.splitlines():
        fields = line.split()
        if len(fields) >= 6 and fields[1] == topic and fields[2] == "0":
            try:
                return tuple(map(int, fields[3:6]))
            except ValueError:
                return None
    return None


def fixture_manifest(r, fixture_time):
    valid = (REPO / "tests/fixtures/cg14/valid_event.csv").read_text().strip()
    rows, deliveries = [], []
    for i, scenario in enumerate(("2xx", "422", "5xx", "timeout", "invalid")):
        timestamp = (
            (datetime.fromisoformat(fixture_time) + timedelta(seconds=i))
            .isoformat(timespec="microseconds")
            .replace("+00:00", "Z")
        )
        raw = timestamp + "," + valid.split(",", 1)[1]
        if scenario == "invalid":
            raw = raw.rsplit(",", 1)[0]
        source = {
            "kind": "restore-" + r["run_id"],
            "uri": "kafka://cg14-kafka-test/" + r["topic"],
            "record_ref": r["topic"] + "/0/" + str(i),
        }
        result = parse_csv_event(
            raw,
            source_uri=source["uri"],
            record_ref=source["record_ref"],
            source_kind=source["kind"],
        )
        require(result.valid == (scenario != "invalid"), "Fixture incompatible.")
        deliveries.append(
            {
                "scenario": scenario,
                "topic": r["topic"],
                "partition": "0",
                "offset": str(i),
                "record_ref": source["record_ref"],
                "source": source,
                "event_id": result.event_id,
                "raw_sha256": hashlib.sha256(raw.encode()).hexdigest(),
                "body_sha256": content_hash(result.normalized_event)
                if result.valid
                else None,
            }
        )
        rows.append(("2xx" if scenario == "invalid" else scenario) + "|" + raw + "\n")
    return rows, deliveries


def functional_pass(e, inv):
    return offset_row(e.get("offsets", ""), e.get("topic", "")) == (
        5,
        5,
        0,
    ) and reconciled(e, inv)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group(required=True)
    for mode in ("plan", "apply", "verify", "test", "stop", "rollback", "resume"):
        modes.add_argument("--" + mode, action="store_true")
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--cert", type=Path, default=DEPLOY / "secrets/nifi-local.crt")
    args = parser.parse_args(argv)
    flow, inv, checks = static()
    r = resources(args.run_id)
    if args.plan:
        print(
            json.dumps(
                {
                    "status": "STATIC_PLAN_ONLY",
                    "network_used": False,
                    "mutations": False,
                    "functional": "NOT_TESTED",
                    "preflight": checks,
                    "resources": r,
                    "patches": desired(flow, inv, r),
                    "host_gates": "NOT_TESTED",
                },
                indent=2,
                ensure_ascii=False,
            )
        )
        return 0
    if not args.apply:
        require(
            (DEPLOY / "data/evidence/restore-e2e" / (r["run_id"] + ".json")).is_file(),
            "Sin manifiesto: no crear recursos; ejecutar --apply primero.",
        )
    with lock() as root:
        path = root / (r["run_id"] + ".json")
        api = Api(ssl.create_default_context(cafile=str(args.cert)))
        api.login()
        try:
            if path.exists():
                s = json.loads(path.read_text())
                require(
                    s["resources"] == r and s["inventory_sha256"] == digest(inv),
                    "Manifiesto incompatible.",
                )
            else:
                require(args.apply, "Sin manifiesto: sólo --apply puede crearlo.")
                ps, cs, f = snapshot(api, inv)
                stopped(ps, cs, f)
                configuration_guard(ps, cs, f, flow, inv, r, isolated=False)
                compare_original(api, ps, r)
                runtime_guard(r)
                # Save only allowlisted configuration: exact pinned baseline, no secrets.
                s = {
                    "resources": r,
                    "inventory_sha256": digest(inv),
                    "pending": None,
                    "fixture_time": datetime.now(UTC).isoformat(),
                    "functional": "NOT_TESTED",
                    "original_sha256": auth.original_fingerprint(api),
                    "prior_properties": {cid: properties(e) for cid, e in ps.items()},
                    "prior_states": {
                        cid: e["component"]["state"] for cid, e in ps.items()
                    },
                    "prior_service_state": cs[SERVICE]["component"]["state"],
                }
                save(path, s)
            runner = Runner(api, flow, inv, r, path, s)
            if args.apply:
                runner.apply()
            elif args.resume:
                runner.resume()
            elif args.test:
                runner.test()
            elif args.stop:
                runner.stop()
            elif args.rollback:
                runner.rollback()
            else:
                runner.collect()  # GET/read-only Docker; no new query, topic or group.
            print(
                json.dumps(
                    {
                        "manifest": str(path),
                        "functional": s["functional"],
                        "pending": s.get("pending"),
                        "mock_resume": s.get("mock_resume", {}).get("status"),
                    },
                    ensure_ascii=False,
                )
            )
        finally:
            api.token = None
    return 0


if __name__ == "__main__":

    def interrupted(signum, frame):
        raise KeyboardInterrupt

    signal.signal(signal.SIGTERM, interrupted)
    try:
        raise SystemExit(main())
    except (
        OSError,
        ValueError,
        KeyError,
        TypeError,
        RuntimeError,
        subprocess.SubprocessError,
        KeyboardInterrupt,
    ) as error:
        # No exception bodies from HTTP/Docker/server or credential prompts.
        print(
            "RESTORE detenido: "
            + (str(error) if isinstance(error, GuardError) else type(error).__name__)
            + "; inspeccionar manifiesto y usar --verify/--stop.",
            file=sys.stderr,
        )
        raise SystemExit(2)
