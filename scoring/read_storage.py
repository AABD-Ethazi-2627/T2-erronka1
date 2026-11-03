"""Explicit read sources. Never initialize, repair, or write an archive."""

import hashlib
import json
import sqlite3
from pathlib import Path


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def canonical(obj):
    return json.dumps(
        obj, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode()


def compatible(obj, scope):
    return (
        obj.get("source", {}).get("uri") == scope.source_uri
        and obj.get("model_artifact_sha256") == scope.model_artifact_sha256
        and obj.get("policy") == scope.policy
    )


class ElasticsearchReader:
    """One PIT per request, exact scope filters, no approximate cardinality."""

    def __init__(self, url, index, *, client=None, max_events=100000):
        import httpx

        if not url or not index or "/" in index or index in (".", ".."):
            raise ValueError("Explicit ES URL and index required")
        self.url, self.index = url.rstrip("/"), index
        self.client = client or httpx.Client(timeout=15)
        self.max_events = max_events

    def rows(self, scope, start, end):
        pit = None
        try:
            response = self.client.post(
                f"{self.url}/{self.index}/_pit", params={"keep_alive": "1m"}
            )
            response.raise_for_status()
            pit = response.json()["id"]
            query = {
                "size": 1000,
                "pit": {"id": pit, "keep_alive": "1m"},
                "sort": [
                    {"timestamp": "desc"},
                    {"event_id": "asc"},
                    {"_shard_doc": "asc"},
                ],
                "query": {
                    "bool": {
                        "filter": [
                            {"term": {"source.uri": scope.source_uri}},
                            {
                                "term": {
                                    "model_artifact_sha256": scope.model_artifact_sha256
                                }
                            },
                            {"term": {"policy": scope.policy}},
                            {
                                "range": {
                                    "timestamp": {
                                        "gte": start.isoformat(),
                                        "lt": end.isoformat(),
                                    }
                                }
                            },
                        ]
                    }
                },
            }
            rows = []
            while True:
                response = self.client.post(f"{self.url}/_search", json=query)
                response.raise_for_status()
                data = response.json()
                pit = data.get("pit_id", pit)
                query["pit"]["id"] = pit
                if data.get("timed_out") or data.get("_shards", {}).get("failed", 0):
                    raise ValueError("Incomplete ES search")
                hits = data["hits"]["hits"]
                rows.extend(h["_source"] for h in hits)
                if len(rows) > self.max_events:
                    raise ValueError("Configured event capacity exceeded")
                if not hits:
                    return rows
                query["search_after"] = hits[-1]["sort"]
        finally:
            if pit:
                self.client.request("DELETE", f"{self.url}/_pit", json={"id": pit})


class ArchiveReader:
    def __init__(self, root, *, max_objects=20000, max_bytes=64 * 1024 * 1024):
        self.max_objects, self.max_bytes = max_objects, max_bytes
        self.root = Path(root).resolve()

    def rows(self, scope, start, end):
        import duckdb
        import pyarrow as pa
        import pyarrow.parquet as pq

        from scripts.duckdb_output import to_pandas_utc

        root = self.root
        # mode=ro forbids accidental creation; normal SQLite locking sees committed state.
        con = sqlite3.connect((root / "ledger.sqlite").as_uri() + "?mode=ro", uri=True)
        try:
            con.execute("PRAGMA busy_timeout=1000")
            con.execute("BEGIN")
            objects = con.execute(
                "SELECT path, hash FROM objects ORDER BY path LIMIT ?",
                (self.max_objects + 1,),
            ).fetchall()
            if len(objects) > self.max_objects:
                raise ValueError("Archive object capacity exceeded")
            if (
                con.execute("SELECT count(*) FROM deliveries").fetchone()[0]
                > self.max_objects
            ):
                raise ValueError("Archive receipt capacity exceeded")
            if (
                con.execute("SELECT count(*) FROM events").fetchone()[0]
                > self.max_objects
            ):
                raise ValueError("Archive event capacity exceeded")
            events = dict(con.execute("SELECT id, hash FROM events"))
            accepted = {
                h
                for h, outcome in con.execute("SELECT hash, outcome FROM deliveries")
                if outcome in ("stored", "duplicate")
            }
            if len(objects) > self.max_objects:
                raise ValueError("Archive object capacity exceeded")
            rows = []
            accepted_keys = set()
            total_bytes = 0
            for name, expected in objects:
                path = (root / name).resolve()
                if not path.is_relative_to(root) or path == root:
                    raise ValueError("Archive path escapes root")
                size = path.stat().st_size
                total_bytes += size
                if total_bytes > self.max_bytes:
                    raise ValueError("Archive byte capacity exceeded")
                with path.open("rb") as handle:
                    raw = handle.read(size + 1)
                if len(raw) != size:
                    raise ValueError("Archive changed during read")
                if digest(raw) != expected:
                    raise ValueError("Committed archive corruption")
                if (
                    name.startswith("bronze/")
                    and digest(b"prediction\0" + raw) in accepted
                ):
                    accepted_keys.add(digest(canonical(json.loads(raw))))
                if not name.startswith("prediction/date=") or not name.endswith(
                    ".parquet"
                ):
                    continue
                table = pq.read_table(pa.BufferReader(raw))
                for row in table.to_pylist():
                    obj = json.loads(row["payload_json"])
                    key = digest(
                        json.dumps(
                            [
                                "prediction",
                                obj["event_id"],
                                obj["model_artifact_sha256"],
                                obj["policy"],
                            ]
                        ).encode()
                    )
                    if (
                        path.stem != key
                        or events.get(key) != digest(canonical(obj))
                        or any(
                            row[k] != obj[k]
                            for k in ("event_id", "machine_id", "timestamp")
                        )
                    ):
                        raise ValueError("Archive event receipt mismatch")
                    # The accepted delivery hashes bind original bronze bytes, which need
                    # not have canonical whitespace. Resolve their exact payload below.
                    rows.append(obj)
            if any(digest(canonical(row)) not in accepted_keys for row in rows):
                raise ValueError("No accepted delivery receipt")
        finally:
            con.close()
        # Read verified bytes via Arrow, not a second unverified filesystem scan.
        scoped = [r for r in rows if compatible(r, scope)]
        if not scoped:
            return []
        table = pa.Table.from_pylist(
            [{"payload_json": canonical(r).decode()} for r in scoped]
        )
        with duckdb.connect(
            ":memory:",
            config={
                "threads": 1,
                "memory_limit": "128MB",
                "temp_directory": "",
                "autoinstall_known_extensions": False,
                "autoload_known_extensions": False,
            },
        ) as db:
            db.execute("SET enable_external_access=false")
            db.register("committed", table)
            frame = to_pandas_utc(db.sql("SELECT payload_json FROM committed"))
        return [json.loads(v) for v in frame.payload_json]
