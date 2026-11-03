"""Committed CG15 prediction lookup and explicit offline legacy backfill.

GET callers only use read_snapshot/verify_entry; they never create or repair this
index. SQLite counters/triggers detect incomplete coverage, including old writers.
"""

import argparse
import hashlib
import json
import sqlite3
from datetime import UTC, datetime
from functools import lru_cache
from pathlib import Path

VERSION = 1
TABLE = "prediction_read_index"
META = "prediction_read_meta"
FIELDS = (
    "event_key",
    "prediction_path",
    "delivery_id",
    "canonical_sha256",
    "source_uri",
    "model_artifact_sha256",
    "policy",
    "risk_threshold",
    "machine_id",
    "timestamp_us",
    "timestamp",
)
PREDICATE = "substr(path, 1, 11) = 'prediction/'"
TRIGGERS = {
    "cg15_read_object_insert": f"""AFTER INSERT ON objects
        WHEN substr(NEW.path, 1, 11) = 'prediction/' BEGIN
        UPDATE {META} SET objects_count=objects_count+1 WHERE id=1; END""",
    "cg15_read_object_delete": f"""AFTER DELETE ON objects
        WHEN substr(OLD.path, 1, 11) = 'prediction/' BEGIN
        UPDATE {META} SET objects_count=objects_count-1, dirty=1 WHERE id=1; END""",
    "cg15_read_object_move": f"""AFTER UPDATE OF path ON objects BEGIN
        UPDATE {META} SET objects_count=objects_count
          + (substr(NEW.path, 1, 11) = 'prediction/')
          - (substr(OLD.path, 1, 11) = 'prediction/'), dirty=1 WHERE id=1; END""",
    "cg15_read_index_insert": f"""AFTER INSERT ON {TABLE} BEGIN
        UPDATE {META} SET entries_count=entries_count+1 WHERE id=1; END""",
    "cg15_read_index_delete": f"""AFTER DELETE ON {TABLE} BEGIN
        UPDATE {META} SET entries_count=entries_count-1, dirty=1 WHERE id=1; END""",
    "cg15_read_index_update": f"""AFTER UPDATE ON {TABLE} BEGIN
        UPDATE {META} SET dirty=1 WHERE id=1; END""",
}


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def canonical(obj):
    return json.dumps(
        obj, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode()


def instant_us(value):
    stamp = datetime.fromisoformat(value) if isinstance(value, str) else value
    if stamp.tzinfo is None or stamp.utcoffset() is None:
        raise ValueError("Archive timestamp must be timezone aware")
    delta = stamp.astimezone(UTC) - datetime(1970, 1, 1, tzinfo=UTC)
    return (delta.days * 86400 + delta.seconds) * 1_000_000 + delta.microseconds


def bronze_path(delivery):
    return "bronze/" + digest(delivery.encode()) + ".bin"


def index_values(delivery, obj):
    key = digest(
        json.dumps(
            ["prediction", obj["event_id"], obj["model_artifact_sha256"], obj["policy"]]
        ).encode()
    )
    return (
        key,
        f"prediction/date={obj['timestamp'][:10]}/{key}.parquet",
        delivery,
        digest(canonical(obj)),
        obj["source"]["uri"],
        obj["model_artifact_sha256"],
        obj["policy"],
        obj["risk_threshold"],
        obj["machine_id"],
        instant_us(obj["timestamp"]),
        obj["timestamp"],
    )


def ensure_schema(con):
    """Writer/backfill only. No executescript: do not commit the caller's transaction."""
    existing_meta = con.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (META,)
    ).fetchone()
    if existing_meta:
        existing_meta = con.execute(f"SELECT 1 FROM {META} WHERE id=1").fetchone()
    old_triggers = {
        row[0]
        for row in con.execute("SELECT name FROM sqlite_master WHERE type='trigger'")
    }
    con.execute(f"""CREATE TABLE IF NOT EXISTS {TABLE} (
        event_key TEXT PRIMARY KEY, prediction_path TEXT UNIQUE NOT NULL,
        delivery_id TEXT NOT NULL, canonical_sha256 TEXT NOT NULL,
        source_uri TEXT NOT NULL, model_artifact_sha256 TEXT NOT NULL,
        policy TEXT NOT NULL, risk_threshold REAL NOT NULL, machine_id TEXT NOT NULL,
        timestamp_us INTEGER NOT NULL, timestamp TEXT NOT NULL,
        CHECK(prediction_path='prediction/date=' || substr(timestamp,1,10) || '/' || event_key || '.parquet')
    )""")
    con.execute(f"""CREATE TABLE IF NOT EXISTS {META} (
        id INTEGER PRIMARY KEY CHECK(id=1), version INTEGER NOT NULL,
        objects_count INTEGER NOT NULL CHECK(objects_count>=0),
        entries_count INTEGER NOT NULL CHECK(entries_count>=0),
        dirty INTEGER NOT NULL CHECK(dirty IN (0,1))
    )""")
    con.execute(
        f"""INSERT OR IGNORE INTO {META}
        SELECT 1, ?, (SELECT count(*) FROM objects WHERE {PREDICATE}),
          (SELECT count(*) FROM {TABLE}), EXISTS(SELECT 1 FROM {TABLE})""",
        (VERSION,),
    )
    if con.execute(f"SELECT version FROM {META} WHERE id=1").fetchone()[0] != VERSION:
        raise ValueError("Unsupported archive read-index version")
    if existing_meta and not set(TRIGGERS) <= old_triggers:
        # Missing triggers could have allowed untracked older-writer mutations.
        con.execute(f"UPDATE {META} SET dirty=1 WHERE id=1")
    for name, body in TRIGGERS.items():
        con.execute(f"CREATE TRIGGER IF NOT EXISTS {name} {body}")
    for name, tail in (
        ("cg15_read_scope_time", "timestamp_us, event_key"),
        ("cg15_read_scope_machine_time", "machine_id, timestamp_us, event_key"),
    ):
        con.execute(
            f"CREATE INDEX IF NOT EXISTS {name} ON {TABLE} "
            f"(source_uri, model_artifact_sha256, policy, risk_threshold, {tail})"
        )


def store_prediction(con, delivery, obj):
    values = index_values(delivery, obj)
    old = con.execute(
        f"SELECT {','.join(FIELDS)} FROM {TABLE} WHERE event_key=?", (values[0],)
    ).fetchone()
    if old is None:
        con.execute(
            f"INSERT INTO {TABLE} VALUES ({','.join('?' for _ in FIELDS)})", values
        )
    elif tuple(old[:2]) + tuple(old[3:]) != values[:2] + values[3:]:
        raise ValueError("Committed prediction index conflicts with canonical event")
    # An identical duplicate retains the first accepted representative delivery.


def require_complete(con):
    state = con.execute(
        f"SELECT version, objects_count, entries_count, dirty FROM {META} WHERE id=1"
    ).fetchone()
    triggers = {
        row[0]
        for row in con.execute("SELECT name FROM sqlite_master WHERE type='trigger'")
    }
    if (
        not state
        or state[0] != VERSION
        or state[1] != state[2]
        or state[3]
        or not set(TRIGGERS) <= triggers
    ):
        raise ValueError(
            "Archive prediction index incomplete or dirty; offline backfill required"
        )


def _select(con, where, params, limit, *, latest=False):
    con.create_function("cg15_bronze_path", 1, bronze_path, deterministic=True)
    direction = "DESC" if latest else "ASC"
    query = f"""SELECT r.*, o.hash AS object_sha256, e.hash AS event_sha256,
        d.hash AS receipt_sha256, d.outcome AS receipt_outcome,
        b.hash AS bronze_sha256
        FROM {TABLE} r
        LEFT JOIN objects o ON o.path=r.prediction_path
        LEFT JOIN events e ON e.id=r.event_key
        LEFT JOIN deliveries d ON d.id=r.delivery_id
        LEFT JOIN objects b ON b.path=cg15_bronze_path(r.delivery_id)
        WHERE {where} ORDER BY r.timestamp_us {direction}, r.event_key LIMIT ?"""
    return [dict(row) for row in con.execute(query, (*params, limit))]


def read_snapshot(root, scope, start=None, end=None, machine_id=None, *, limit):
    """Snapshot only metadata; close the SQLite read transaction before object I/O."""
    con = sqlite3.connect(
        (Path(root) / "ledger.sqlite").as_uri() + "?mode=ro", uri=True
    )
    con.row_factory = sqlite3.Row
    try:
        con.execute("PRAGMA busy_timeout=1000")
        con.execute("BEGIN")
        require_complete(con)
        clauses = ["r.source_uri=?", "r.model_artifact_sha256=?", "r.policy=?"]
        params = [scope.source_uri, scope.model_artifact_sha256, scope.policy]
        if scope.risk_threshold is not None:
            clauses.append("r.risk_threshold=?")
            params.append(scope.risk_threshold)
        if machine_id is not None:
            clauses.append("r.machine_id=?")
            params.append(machine_id)
        if start is not None:
            clauses.extend(["r.timestamp_us>=?", "r.timestamp_us<?"])
            params.extend([instant_us(start), instant_us(end)])
        return _select(
            con,
            " AND ".join(clauses),
            params,
            limit,
            latest=start is None and machine_id is not None,
        )
    finally:
        con.close()


class ObjectBudget:
    def __init__(self, max_objects, max_bytes):
        self.max_objects, self.max_bytes = max_objects, max_bytes
        self.paths = set()
        self.bytes = 0

    def read(self, root, name, expected):
        if not isinstance(name, str) or not isinstance(expected, str):
            raise TypeError("Missing committed object receipt")
        path = (root / name).resolve()
        if not path.is_relative_to(root) or path == root:
            raise ValueError("Archive path escapes root")
        size = path.stat().st_size
        if name not in self.paths:
            self.paths.add(name)
            self.bytes += size
        if len(self.paths) > self.max_objects or self.bytes > self.max_bytes:
            raise ValueError("Selected archive object/byte capacity exceeded")
        with path.open("rb") as handle:
            raw = handle.read(size + 1)
        if len(raw) != size or digest(raw) != expected:
            raise ValueError("Committed archive corruption")
        return raw


@lru_cache(maxsize=1)
def prediction_validator():
    from scripts.validate_contracts import validators

    return validators()["prediction"]


def verify_entry(root, entry, budget):
    import pyarrow as pa
    import pyarrow.parquet as pq

    if entry["receipt_outcome"] not in ("stored", "duplicate"):
        raise ValueError("No accepted prediction delivery receipt")
    raw = budget.read(root, bronze_path(entry["delivery_id"]), entry["bronze_sha256"])
    if digest(b"prediction\0" + raw) != entry["receipt_sha256"]:
        raise ValueError("Prediction delivery fingerprint mismatch")
    obj = json.loads(raw)
    prediction_validator().validate(obj)
    values = index_values(entry["delivery_id"], obj)
    if (
        tuple(entry[field] for field in FIELDS) != values
        or entry["event_sha256"] != values[3]
    ):
        raise ValueError("Prediction index/event metadata mismatch")
    parquet = budget.read(root, entry["prediction_path"], entry["object_sha256"])
    table = pq.read_table(pa.BufferReader(parquet))
    if table.num_rows != 1:
        raise ValueError("Expected one committed prediction per object")
    row = table.to_pylist()[0]
    if any(
        row[field] != obj[field] for field in ("event_id", "machine_id", "timestamp")
    ) or canonical(json.loads(row["payload_json"])) != canonical(obj):
        raise ValueError("Prediction Parquet differs from accepted receipt")
    return obj


def backfill(root):
    """Explicit offline operation: preserve every existing object/receipt byte."""
    from scripts.platform_io import sync_directory

    root = Path(root).resolve()
    con = sqlite3.connect(
        (root / "ledger.sqlite").as_uri() + "?mode=rw", uri=True, timeout=0
    )
    con.row_factory = sqlite3.Row
    try:
        con.execute("PRAGMA synchronous=FULL")
        con.execute("BEGIN IMMEDIATE")
        ensure_schema(con)
        for receipt in con.execute(
            "SELECT id, hash FROM deliveries WHERE outcome IN ('stored','duplicate') ORDER BY id"
        ):
            name = bronze_path(receipt["id"])
            recorded = con.execute(
                "SELECT hash FROM objects WHERE path=?", (name,)
            ).fetchone()
            raw = ObjectBudget(1, 64 * 1024 * 1024).read(
                root, name, recorded[0] if recorded else None
            )
            if digest(b"telemetry\0" + raw) == receipt["hash"]:
                continue
            if digest(b"prediction\0" + raw) != receipt["hash"]:
                raise ValueError("Accepted delivery fingerprint is invalid")
            obj = json.loads(raw)
            prediction_validator().validate(obj)
            store_prediction(con, receipt["id"], obj)
        # Validate every resulting index entry, including previously indexed rows.
        for row in con.execute(f"SELECT event_key FROM {TABLE} ORDER BY event_key"):
            entry = _select(con, "r.event_key=?", [row[0]], 1)[0]
            verify_entry(root, entry, ObjectBudget(2, 64 * 1024 * 1024))
        objects = con.execute(
            f"SELECT count(*) FROM objects WHERE {PREDICATE}"
        ).fetchone()[0]
        entries = con.execute(f"SELECT count(*) FROM {TABLE}").fetchone()[0]
        if objects != entries:
            raise ValueError("Committed predictions lack accepted indexed receipts")
        con.execute(
            f"UPDATE {META} SET objects_count=?, entries_count=?, dirty=0 WHERE id=1",
            (objects, entries),
        )
        require_complete(con)
        con.commit()
        sync_directory(root)
        return {"status": "verified", "predictions": entries, "index_version": VERSION}
    finally:
        con.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path)
    parser.add_argument(
        "--writer-stopped",
        action="store_true",
        required=True,
        help="Confirm all writers are stopped; preserves object bytes and receipts",
    )
    args = parser.parse_args()
    print(json.dumps(backfill(args.root), indent=2))
