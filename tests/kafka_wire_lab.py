"""Opt-in, loopback Kafka protocol lab using librdkafka's mock cluster.

Run: uv run --locked --extra kafka --with confluent-kafka==2.16.0 \
    python tests/kafka_wire_lab.py
This is a protocol mock, NOT an Apache Kafka broker acceptance test.
"""

import ctypes
import hashlib
import json
import logging
import os
import signal
import sqlite3
import subprocess
import sys
import tempfile
import time
from contextlib import closing
from pathlib import Path

import confluent_kafka
from kafka import KafkaConsumer, KafkaProducer
from kafka.structs import TopicPartition


def library():
    candidates = list(
        (Path(confluent_kafka.__file__).parent.parent / "confluent_kafka.libs").glob(
            "librdkafka-*.so*"
        )
    )
    if len(candidates) != 1:
        raise RuntimeError(
            "lab requires the Linux confluent-kafka wheel with librdkafka"
        )
    lib = ctypes.CDLL(str(candidates[0]))
    void, integer, string = ctypes.c_void_p, ctypes.c_int, ctypes.c_char_p
    signatures = {
        "rd_kafka_conf_new": (void, []),
        "rd_kafka_conf_set": (integer, [void, string, string, string, ctypes.c_size_t]),
        "rd_kafka_new": (void, [integer, void, string, ctypes.c_size_t]),
        "rd_kafka_destroy": (None, [void]),
        "rd_kafka_mock_cluster_new": (void, [void, integer]),
        "rd_kafka_mock_cluster_destroy": (None, [void]),
        "rd_kafka_mock_cluster_bootstraps": (string, [void]),
        "rd_kafka_mock_topic_create": (integer, [void, string, integer, integer]),
    }
    for name, (restype, argtypes) in signatures.items():
        function = getattr(lib, name)
        function.restype, function.argtypes = restype, argtypes
    return lib


def wait_until(predicate, timeout=20):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(0.05)
    raise TimeoutError("isolated Kafka lab condition not reached")


def count_deliveries(root):
    if not (root / "ledger.sqlite").exists():
        return 0
    with closing(sqlite3.connect(root / "ledger.sqlite")) as db, db:
        try:
            return db.execute("SELECT count(*) FROM deliveries").fetchone()[0]
        except sqlite3.OperationalError:
            return 0  # Startup can expose the database before schema creation.


def catches_sigterm(process):
    if process.poll() is not None:
        raise RuntimeError("CLI exited before installing its signal handlers")
    status = Path(f"/proc/{process.pid}/status").read_text()
    mask = next(
        line.split()[1] for line in status.splitlines() if line.startswith("SigCgt:")
    )
    return bool(int(mask, 16) & (1 << (signal.SIGTERM - 1)))


def cli(bootstrap, root, group, *extra):
    return [
        sys.executable,
        "-m",
        "scripts.archive_consumer",
        "--bootstrap-servers",
        bootstrap,
        "--group-id",
        group,
        "--source-namespace",
        "isolated-librdkafka-mock/generation-1",
        "--api-version",
        "2.0",
        "--topic",
        "cg15-normalized=telemetry",
        "--root",
        str(root),
        "--offset-reset",
        "earliest",
        "--poll-timeout-ms",
        "100",
        "--commit-timeout-ms",
        "10000",
        *extra,
    ]


def main():
    if os.environ.get("CG15_KAFKA_LAB_DEBUG"):
        logging.basicConfig(level=logging.DEBUG)
    lib = library()
    error = ctypes.create_string_buffer(512)
    conf = lib.rd_kafka_conf_new()
    assert lib.rd_kafka_conf_set(conf, b"log_level", b"0", error, len(error)) == 0
    owner = lib.rd_kafka_new(0, conf, error, len(error))
    assert owner, error.value
    cluster = lib.rd_kafka_mock_cluster_new(owner, 1)
    assert cluster
    try:
        bootstrap = lib.rd_kafka_mock_cluster_bootstraps(cluster).decode()
        assert all(address.startswith("127.0.0.1:") for address in bootstrap.split(","))
        assert lib.rd_kafka_mock_topic_create(cluster, b"cg15-normalized", 1, 1) == 0
        raw = Path("contracts/examples/valid/telemetry.json").read_bytes()
        producer = KafkaProducer(
            bootstrap_servers=bootstrap,
            acks="all",
            bootstrap_timeout_ms=5000,
            api_version=(2, 0),
        )
        try:
            for value in (raw, raw, b"{invalid"):
                producer.send("cg15-normalized", value=value, partition=0).get(
                    timeout=10
                )
        finally:
            producer.close(timeout=10)

        with tempfile.TemporaryDirectory(prefix="cg15-wire-") as directory:
            root = Path(directory) / "archive"
            command = cli(
                bootstrap, root, "cg15-wire", "--max-records", "1", "--max-batches", "3"
            )
            result = subprocess.run(
                command, capture_output=True, text=True, timeout=40, check=True
            )
            reports = [json.loads(line) for line in result.stdout.splitlines()]
            assert sum(row["stored"] for row in reports) == 1, reports
            assert sum(row["duplicate"] for row in reports) == 1, reports
            assert sum(row["rejected"] for row in reports) == 1, reports
            assert count_deliveries(root) == 3
            before = {
                str(p): hashlib.sha256(p.read_bytes()).hexdigest()
                for p in root.rglob("*.parquet")
            }

            inspector = KafkaConsumer(
                bootstrap_servers=bootstrap,
                api_version=(2, 0),
                group_id="cg15-wire",
                enable_auto_commit=False,
            )
            try:
                assert (
                    inspector.committed(
                        TopicPartition("cg15-normalized", 0), timeout_ms=10000
                    )
                    == 3
                )
            finally:
                inspector.close(autocommit=False)

            # A fresh group replays the same source IDs without adding Parquet.
            result = subprocess.run(
                cli(
                    bootstrap,
                    root,
                    "cg15-replay",
                    "--max-records",
                    "1",
                    "--max-batches",
                    "3",
                ),
                capture_output=True,
                text=True,
                timeout=40,
                check=True,
            )
            replay = [json.loads(line) for line in result.stdout.splitlines()]
            assert sum(row["replay"] for row in replay) == 3, replay
            assert count_deliveries(root) == 3
            assert before == {
                str(p): hashlib.sha256(p.read_bytes()).hexdigest()
                for p in root.rglob("*.parquet")
            }

            # Real SIGTERM after handler installation, with no new data available.
            with tempfile.TemporaryFile(mode="w+") as output:
                process = subprocess.Popen(
                    cli(bootstrap, root, "cg15-wire"),
                    stdout=output,
                    stderr=output,
                    env=dict(os.environ, PYTHONUNBUFFERED="1"),
                )
                try:
                    wait_until(lambda: catches_sigterm(process))
                    time.sleep(1)
                    process.send_signal(signal.SIGTERM)
                    exit_code = process.wait(timeout=15)
                    output.seek(0)
                    captured = output.read().strip()
                    assert exit_code == 0, (exit_code, captured)
                    assert not captured, captured
                finally:
                    if process.poll() is None:
                        process.kill()
                        process.wait(timeout=10)
            print(
                json.dumps(
                    {
                        "client": "kafka-python==3.0.11",
                        "mock": confluent_kafka.libversion()[0],
                        "reports": reports,
                        "replay": replay,
                        "committed_offset": 3,
                        "sigterm_exit": 0,
                        "parquet_hashes_preserved": True,
                    }
                )
            )
    finally:
        lib.rd_kafka_mock_cluster_destroy(cluster)
        lib.rd_kafka_destroy(owner)


if __name__ == "__main__":
    main()
