"""Local durable archive sink. Transport adapters must disable automatic ack."""

import hashlib
import json
import os
import sqlite3
import tempfile
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq
from jsonschema import ValidationError

from scripts.validate_contracts import validators


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def sync_dir(path):
    fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def mkdir(path):
    # Normalize lexical .. components and follow symlinks before walking parents.
    # Existing directories can be leftovers from a process interrupted after
    # mkdir but before fsync(parent); existence is not evidence of durability.
    path = Path(path).resolve()
    if path == path.parent:
        return  # Filesystem root has no directory entry in a distinct parent.
    mkdir(path.parent)
    path.mkdir(exist_ok=True)
    sync_dir(path.parent)


def durable(path, raw):
    """Atomic immutable installation; replay reconciles pre-commit orphan files."""
    mkdir(path.parent)
    if path.exists():
        if path.read_bytes() != raw:
            raise ValueError("Archive object differs: reconciliation required")
        # A previous process may have died between rename and directory fsync.
        sync_dir(path.parent)
        return
    fd, name = tempfile.mkstemp(prefix=".pending-", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(raw)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(name, path)
        sync_dir(path.parent)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def parquet(row):
    sink = pa.BufferOutputStream()
    pq.write_table(pa.Table.from_pylist([row]), sink)
    return sink.getvalue().to_pybytes()


def consume(root, messages, ack, checkpoint=lambda stage: None):
    """messages: (delivery_id, kind, bytes). ack called only after durable commit.

    delivery_id must be stable and globally namespaced (cluster/topic/partition/offset
    for Kafka, persistent FlowFile identity for NiFi). No broker is contacted here.
    """
    root = Path(root).absolute()
    mkdir(root)
    schemas = validators()
    con = sqlite3.connect(root / "ledger.sqlite")
    try:
        con.execute("PRAGMA synchronous=FULL")
        con.execute(
            "CREATE TABLE IF NOT EXISTS deliveries "
            "(id TEXT PRIMARY KEY, hash TEXT, outcome TEXT)"
        )
        con.execute(
            "CREATE TABLE IF NOT EXISTS events (id TEXT PRIMARY KEY, hash TEXT)"
        )
        con.execute(
            "CREATE TABLE IF NOT EXISTS objects (path TEXT PRIMARY KEY, hash TEXT)"
        )
        con.commit()
        sync_dir(root)
        con.execute(
            "BEGIN IMMEDIATE"
        )  # Single writer across processes, including files.
        for name, expected in con.execute("SELECT path, hash FROM objects"):
            path = root / name
            if not path.is_file() or digest(path.read_bytes()) != expected:
                raise ValueError(
                    "Committed archive corruption: reconciliation required"
                )

        def write(path, raw):
            durable(path, raw)
            con.execute(
                "INSERT OR IGNORE INTO objects VALUES (?, ?)",
                (str(path.relative_to(root)), digest(raw)),
            )

        counts = {"sent": 0, "stored": 0, "rejected": 0, "duplicate": 0, "replay": 0}
        for delivery, kind, raw in messages:
            if (
                not isinstance(delivery, str)
                or not delivery
                or not isinstance(raw, bytes)
            ):
                raise ValueError("Stable delivery ID and bytes required")
            counts["sent"] += 1
            fingerprint = digest(kind.encode() + b"\0" + raw)
            previous = con.execute(
                "SELECT hash FROM deliveries WHERE id=?", (delivery,)
            ).fetchone()
            if previous and previous[0] != fingerprint:
                raise ValueError("Delivery identity reused with different content")
            write(root / "bronze" / (digest(delivery.encode()) + ".bin"), raw)
            if previous:
                counts["replay"] += 1
                continue
            outcome = "rejected"
            try:
                if kind not in ("telemetry", "prediction"):
                    raise ValueError("Unknown stream")
                obj = json.loads(
                    raw,
                    parse_constant=lambda value: (_ for _ in ()).throw(
                        ValueError("Nonfinite JSON")
                    ),
                )
                schemas[kind].validate(obj)
                canonical = json.dumps(
                    obj, sort_keys=True, separators=(",", ":"), allow_nan=False
                ).encode()
                identity = [kind, obj["event_id"]]
                if kind == "prediction":
                    identity += [obj["model_artifact_sha256"], obj["policy"]]
                key = digest(json.dumps(identity).encode())
                existing = con.execute(
                    "SELECT hash FROM events WHERE id=?", (key,)
                ).fetchone()
                if existing and existing[0] != digest(canonical):
                    raise ValueError("Event identity content conflict")
            except (ValueError, UnicodeError, ValidationError) as exc:
                write(
                    root / "rejected" / (digest(delivery.encode()) + ".json"),
                    json.dumps(
                        {
                            "delivery_id": delivery,
                            "kind": kind,
                            "reason": type(exc).__name__,
                            "detail": str(exc).splitlines()[0],
                            "bronze_sha256": digest(raw),
                        }
                    ).encode(),
                )
            else:
                target = (
                    root / kind / ("date=" + obj["timestamp"][:10]) / (key + ".parquet")
                )
                row = {
                    "event_id": obj["event_id"],
                    "machine_id": obj["machine_id"],
                    "timestamp": obj["timestamp"],
                    "payload_json": canonical.decode(),
                }
                if target.exists():
                    # Writer upgrades may change encoding without changing data.
                    # Committed hashes were verified above; reconcile orphans by
                    # schema and values, then retain their original bytes/hash.
                    archived = target.read_bytes()
                    if not pq.read_table(pa.BufferReader(archived)).equals(
                        pa.Table.from_pylist([row])
                    ):
                        raise ValueError(
                            "Archive object differs: reconciliation required"
                        )
                else:
                    archived = parquet(row)
                write(target, archived)
                outcome = "duplicate" if existing else "stored"
                con.execute(
                    "INSERT OR IGNORE INTO events VALUES (?, ?)",
                    (key, digest(canonical)),
                )
            counts[outcome] += 1
            con.execute(
                "INSERT INTO deliveries VALUES (?, ?, ?)",
                (delivery, fingerprint, outcome),
            )
            checkpoint("after_write")
        checkpoint("before_commit")
        con.commit()
        sync_dir(root)
        checkpoint("after_commit")
        ack()
        return counts
    finally:
        con.close()


if __name__ == "__main__":
    try:
        from scripts.kafka_archive import main
    except ModuleNotFoundError as exc:
        if exc.name != "kafka":
            raise
        raise SystemExit(
            "Kafka adapter requires: uv sync --locked --extra kafka"
        ) from exc
    raise SystemExit(main())
