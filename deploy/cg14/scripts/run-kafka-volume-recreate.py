#!/usr/bin/env python3
"""Recreate only a fresh labelled Kafka 3.7 broker on retained D: bind storage.

Needs the repository Kafka extra. No pull, shared broker, NiFi or old lab
mutation. Logs every Docker command and exit; retains data and stopped broker.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import socket
import subprocess
import time
import uuid
from pathlib import Path

HERE = Path(__file__).resolve().parent
LABEL = "t2.kafka.volume.run"


def storage_root(value: str) -> Path:
    path = Path(value).resolve()
    if not str(path).startswith("/mnt/d/") or path.is_symlink():
        raise ValueError("Run in WSL with a physical evidence directory under /mnt/d/")
    return path


class Lab:
    def __init__(self, root: Path):
        self.root = root
        self.run = "t2-volume-" + uuid.uuid4().hex[:12]
        self.name = self.run + "-kafka"
        self.ids: list[str] = []
        self.layer_baselines: dict[str, str] = {}
        self.root.mkdir(parents=True, exist_ok=False)
        for folder in (
            "storage",
            "storage/data",
            "storage/metadata",
            "runtime",
            "process-temp",
            "readonly-runtime",
            "secrets",
            "shared-config",
        ):
            (self.root / folder).mkdir()
        os.environ.update(
            dict.fromkeys(("TMPDIR", "TEMP", "TMP"), str(self.root / "process-temp"))
        )

    def save(self, name, value):
        (self.root / name).write_text(json.dumps(value, indent=2) + "\n")

    def docker(self, *args, check=True):
        result = subprocess.run(
            ["docker", *args], capture_output=True, text=True, timeout=60, check=False
        )
        with (self.root / "commands.jsonl").open("a") as stream:
            stream.write(
                json.dumps(
                    {
                        "args": ["docker", *args],
                        "exit": result.returncode,
                        "stdout": result.stdout,
                        "stderr": result.stderr,
                    }
                )
                + "\n"
            )
        if check:
            result.check_returncode()
        return (result.stdout + (result.stderr if args[0] == "logs" else "")).strip()

    def inspect(self, identity):
        return json.loads(self.docker("inspect", identity))[0]

    def owned(self, identity):
        obj = self.inspect(identity)
        if obj["Id"] not in self.ids or obj["Config"]["Labels"].get(LABEL) != self.run:
            raise RuntimeError("Container identity/ownership mismatch")
        return obj

    def create(self, image, port, readonly=False):
        runtime = self.root / ("readonly-runtime" if readonly else "runtime")
        args = [
            "create",
            "--pull=never",
            "--name",
            self.name + ("-readonly" if readonly else ""),
            "--label",
            f"{LABEL}={self.run}",
            "--read-only",
            "--cap-drop=ALL",
            "--security-opt=no-new-privileges:true",
            "--memory=1g",
            "--cpus=1",
            "--publish",
            f"127.0.0.1:{port}:9092",
            "--env",
            "CLUSTER_ID=CG14volumeRetained001xx",
            "--env",
            "KAFKA_HEAP_OPTS=-Xms256m -Xmx512m",
            "--env",
            "TMPDIR=/lab/runtime",
            "--env",
            "TEMP=/lab/runtime",
            "--env",
            "TMP=/lab/runtime",
            "--env",
            "LOG_DIR=/lab/runtime/logs",
            "--env",
            "KAFKA_OPTS=-Djava.io.tmpdir=/lab/runtime -XX:-UsePerfData",
            "--mount",
            f"type=bind,src={self.root / 'storage'},dst=/var/lib/kafka"
            + (",readonly" if readonly else ""),
            "--mount",
            f"type=bind,src={self.root / 'storage/data'},dst=/var/lib/kafka/data"
            + (",readonly" if readonly else ""),
            "--mount",
            f"type=bind,src={self.root / 'secrets'},dst=/etc/kafka/secrets,readonly",
            "--mount",
            f"type=bind,src={self.root / 'shared-config'},"
            "dst=/mnt/shared/config,readonly",
            "--mount",
            f"type=bind,src={runtime},dst=/lab/runtime",
            "--mount",
            f"type=bind,src={self.root / 'server.properties'},"
            "dst=/lab/server.properties,readonly",
            "--mount",
            f"type=bind,src={HERE / 'kafka-volume-start.sh'},"
            "dst=/lab/start.sh,readonly",
            "--entrypoint",
            "/bin/bash",
            image,
            "/lab/start.sh",
        ]
        identity = self.docker(*args)
        self.ids.append(identity)
        self.save("owned.json", {"label": self.run, "ids": self.ids})
        obj = self.owned(identity)
        mounts = {m["Destination"]: m for m in obj["Mounts"]}
        if any(
            m["Type"] != "bind"
            or (m["RW"] and not m["Source"].startswith(str(self.root) + "/"))
            for m in mounts.values()
        ):
            raise RuntimeError("Implicit volume or storage outside the evidence root")
        if mounts["/var/lib/kafka/data"]["Source"] != str(self.root / "storage/data"):
            raise RuntimeError("Image VOLUME shadows the retained data bind")
        self.save(
            ("readonly" if readonly else f"created-{len(self.ids)}") + ".json", obj
        )
        self.docker("start", identity)
        # Docker materializes mount points on start, not create. PID1 has a
        # read-only root; reject any addition other than the declared mounts.
        baseline = self.docker("diff", identity)
        allowed = {
            "A /lab",
            "A /lab/runtime",
            "A /lab/server.properties",
            "A /lab/start.sh",
        }
        if set(baseline.splitlines()) - allowed:
            raise RuntimeError("Unexpected container layer change at startup")
        self.layer_baselines[identity] = baseline
        self.save("layer-baselines.json", self.layer_baselines)
        return identity

    def ready(self, identity, endpoint):
        from kafka import KafkaAdminClient

        deadline = time.monotonic() + 90
        while time.monotonic() < deadline:
            if not self.owned(identity)["State"]["Running"]:
                self.docker("logs", identity)
                raise RuntimeError("Broker exited before readiness")
            try:
                client = KafkaAdminClient(
                    bootstrap_servers=endpoint,
                    request_timeout_ms=3000,
                )
            except Exception as exc:
                # Bounded readiness only; no produce/commit retries.
                (self.root / "readiness-last-error.txt").write_text(repr(exc))
                time.sleep(1)
                continue
            client.close()
            return
        raise TimeoutError("Broker API readiness timed out")

    def storage(self):
        result = {}
        for name in ("data", "metadata"):
            path = self.root / "storage" / name / "meta.properties"
            result[name] = {
                "text": path.read_text(),
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            }
        if not list((self.root / "storage/data").glob("__consumer_offsets-*")):
            raise RuntimeError("Group coordinator storage absent from the bind")
        return result

    def stop_cleanly(self, identity, evidence):
        self.owned(identity)
        self.docker("stop", "--time", "30", identity)
        obj = self.owned(identity)
        self.save(evidence, obj)
        logs = self.docker("logs", identity)
        # JVM PID 1 exits 128+SIGTERM even after Kafka's shutdown hook completes.
        if (
            obj["State"]["ExitCode"] not in (0, 143)
            or obj["State"]["OOMKilled"]
            or "[BrokerServer id=1] shut down completed" not in logs
        ):
            raise RuntimeError("Broker shutdown did not complete cleanly")

    def execute(self):
        from kafka import KafkaAdminClient, KafkaConsumer, KafkaProducer, TopicPartition
        from kafka.admin import NewTopic
        from kafka.structs import OffsetAndMetadata

        before = self.docker("ps", "-aq", "--no-trunc").splitlines()
        self.save("container-ids-before.json", before)
        image = json.loads(self.docker("image", "inspect", "apache/kafka:3.7.2"))[0]
        self.save("image.json", image)
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            port = sock.getsockname()[1]
        config = (
            (HERE / "kafka-volume.properties")
            .read_text()
            .replace("1@cg14-kafka-test:9093", "1@localhost:9093")
            .replace(
                "PLAINTEXT://cg14-kafka-test:9092", f"PLAINTEXT://127.0.0.1:{port}"
            )
        )
        (self.root / "server.properties").write_text(config)
        endpoint = f"127.0.0.1:{port}"
        first = self.create(image["Id"], port)
        self.ready(first, endpoint)
        topic, group = self.run + "-events", self.run + "-group"
        admin = KafkaAdminClient(bootstrap_servers=endpoint)
        try:
            admin.create_topics([NewTopic(topic, 1, 1)])
        finally:
            admin.close()
        messages = [f"{self.run}-event-{i}".encode() for i in range(6)]
        producer = KafkaProducer(bootstrap_servers=endpoint, acks="all", retries=0)
        try:
            produced = [
                producer.send(topic, key=str(i).encode(), value=value)
                .get(timeout=15)
                .offset
                for i, value in enumerate(messages)
            ]
            if produced != list(range(6)):
                raise RuntimeError("Unexpected produced offsets")
        finally:
            producer.close()
        tp = TopicPartition(topic, 0)

        def consumer(group_id):
            return KafkaConsumer(
                topic,
                bootstrap_servers=endpoint,
                group_id=group_id,
                enable_auto_commit=False,
                auto_offset_reset="earliest",
                max_poll_records=3,
                request_timeout_ms=15000,
            )

        def receive(client, count):
            rows, deadline = [], time.monotonic() + 30
            while len(rows) < count and time.monotonic() < deadline:
                for batch in client.poll(
                    timeout_ms=1000, max_records=count - len(rows)
                ).values():
                    rows.extend(
                        (r.offset, r.key.decode(), r.value.decode()) for r in batch
                    )
            if len(rows) != count:
                raise RuntimeError("Expected message count not received")
            return rows

        client = consumer(group)
        try:
            first_rows = receive(client, 3)
            if [r[2].encode() for r in first_rows] != messages[:3]:
                raise RuntimeError("Initial message identity mismatch")
            client.commit({tp: OffsetAndMetadata(3, "volume-check", -1)})
            if client.committed(tp) != 3:
                raise RuntimeError("Initial group commit not confirmed")
        finally:
            client.close()
        self.stop_cleanly(first, "first-stopped.json")
        before_storage = self.storage()
        self.save("storage-before.json", before_storage)
        self.docker("logs", first)
        self.owned(first)
        self.docker("rm", first)  # Only this exact newly-created stopped ID.
        second = self.create(image["Id"], port)
        if second == first:
            raise RuntimeError("Recreation did not produce a distinct container")
        self.ready(second, endpoint)
        after_storage = self.storage()
        if before_storage != after_storage:
            raise RuntimeError("KRaft identity changed on recreation")
        self.save("storage-after.json", after_storage)
        client = consumer(group)
        try:
            if client.committed(tp) != 3:
                raise RuntimeError("Committed group offset lost after recreation")
            recovered = receive(client, 3)
            if [r[0] for r in recovered] != [3, 4, 5] or [
                r[2].encode() for r in recovered
            ] != messages[3:]:
                raise RuntimeError("Group resume did not start at retained offset")
            client.commit({tp: OffsetAndMetadata(6, "volume-check", -1)})
            if client.committed(tp) != 6:
                raise RuntimeError("Recreated group coordinator could not commit")
        finally:
            client.close()
        client = consumer(self.run + "-replay")
        try:
            replay = receive(client, 6)
            expected = [(i, str(i), value.decode()) for i, value in enumerate(messages)]
            if replay != expected:
                raise RuntimeError("Replay identity/order mismatch")
        finally:
            client.close()
        self.save(
            "persistence-results.json",
            {
                "first_id": first,
                "recreated_id": second,
                "before_rows": first_rows,
                "resumed_rows": recovered,
                "replay_rows": replay,
                "offset_before": 3,
                "offset_after": 6,
                "kraft_metadata_identical": True,
            },
        )
        self.save("second-running.json", self.owned(second))
        if self.docker("diff", second) != self.layer_baselines[second]:
            raise RuntimeError("Unexpected write into the container layer")
        self.stop_cleanly(second, "second-stopped.json")
        # The same retained bind must fail closed when made read-only.
        probe = self.create(image["Id"], port, readonly=True)
        exit_code = self.docker("wait", probe)
        self.save("readonly-stopped.json", self.owned(probe))
        log = self.docker("logs", probe)
        if (
            exit_code == "0"
            or self.owned(probe)["State"]["Running"]
            or "Read-only file system" not in log
        ):
            raise RuntimeError("Read-only storage did not fail closed")
        # docker logs can place the diagnostic on stderr; full command log retains it.
        self.save("readonly-result.json", {"exit": exit_code, "stdout": log})
        if self.storage() != after_storage:
            raise RuntimeError("Read-only probe altered metadata")
        after = self.docker("ps", "-aq", "--no-trunc").splitlines()
        if set(before) - set(after):
            raise RuntimeError("A pre-existing container disappeared")
        self.save("container-ids-after.json", after)
        self.save(
            "results.json",
            {
                "result": "PASSED",
                "run": self.run,
                "first_id": first,
                "recreated_id": second,
                "readonly_probe_id": probe,
                "retained_bind": str(self.root / "storage"),
                "produced_offsets": produced,
                "before_rows": first_rows,
                "resumed_rows": recovered,
                "replay_rows": replay,
                "group_offset_before": 3,
                "group_offset_after": 6,
                "same_kraft_metadata": True,
                "readonly_exit": exit_code,
                "prior_container_count": len(before),
                "preserved_prior_containers": len(set(before) & set(after)),
                "limits": [
                    "single broker; clean stop/recreate, not power loss",
                    "no NiFi/ES rerun; transport evidence is historical",
                ],
            },
        )

    def stop_owned(self):
        for identity in self.ids:
            # The first ID was deliberately removed; never substitute a name.
            if not self.docker("ps", "-aq", "--no-trunc", "--filter", f"id={identity}"):
                continue
            if self.owned(identity)["State"]["Running"]:
                self.docker("stop", "--time", "30", identity)
            self.docker("logs", identity)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence-dir", required=True)
    args = parser.parse_args()
    lab = Lab(storage_root(args.evidence_dir))
    try:
        lab.execute()
    finally:
        lab.stop_owned()


if __name__ == "__main__":
    main()
