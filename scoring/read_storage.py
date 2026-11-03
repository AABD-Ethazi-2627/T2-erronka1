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

    def __init__(
        self, url, index, *, client=None, max_events=100000, max_count_pages=1000
    ):
        import httpx

        if not url or not index or "/" in index or index in (".", ".."):
            raise ValueError("Explicit ES URL and index required")
        self.url, self.index = url.rstrip("/"), index
        self.client = client or httpx.Client(timeout=15)
        self.max_events = max_events
        if any(type(n) is not int or n < 1 for n in (max_events, max_count_pages)):
            raise ValueError("Read capacities must be positive integers")
        self.max_count_pages = max_count_pages

    @staticmethod
    def _filters(scope, start, end):
        return [
            {"term": {"source.uri": scope.source_uri}},
            {"term": {"model_artifact_sha256": scope.model_artifact_sha256}},
            {"term": {"policy": scope.policy}},
            {"range": {"timestamp": {"gte": start.isoformat(), "lt": end.isoformat()}}},
        ]

    def _search(self, pit, body):
        response = self.client.post(
            f"{self.url}/_search",
            json={**body, "pit": {"id": pit["id"], "keep_alive": "1m"}},
            params={"allow_partial_search_results": "false"},
        )
        response.raise_for_status()
        data = response.json()
        pit["id"] = data.get("pit_id", pit["id"])
        if data.get("timed_out") or data.get("_shards", {}).get("failed", 0):
            raise ValueError("Incomplete ES search")
        return data

    def _verify_events(self, pit, filters, identities):
        """Check all copies of selected identities, including alias/index replays."""
        if not identities:
            return {}
        query = {
            "size": 1000,
            "query": {
                "bool": {"filter": [*filters, {"terms": {"event_id": identities}}]}
            },
            "sort": [{"event_id": "asc"}, {"_shard_doc": "asc"}],
        }
        unique = {}
        expected = set(identities)
        seen = 0
        while True:
            hits = self._search(pit, query)["hits"]["hits"]
            seen += len(hits)
            if seen > self.max_events:
                raise ValueError("Duplicate validation capacity exceeded")
            for hit in hits:
                row = hit["_source"]
                key = row["event_id"]
                if key not in expected:
                    raise ValueError("ES returned an unexpected identity")
                value = canonical(row)
                if key in unique and unique[key] != value:
                    raise ValueError("Conflicting event identity")
                unique[key] = value
            if not hits:
                if set(unique) != expected:
                    raise ValueError("ES identity missing from PIT")
                return unique
            query["search_after"] = hits[-1]["sort"]

    def snapshot(self, scope, start, end, *, include_event_count=False):
        """Bound payload transfer by machines; count only 24h of compact identities."""
        from datetime import timedelta

        pit = {}
        try:
            response = self.client.post(
                f"{self.url}/{self.index}/_pit",
                params={"keep_alive": "1m", "allow_partial_search_results": "false"},
            )
            response.raise_for_status()
            opened = response.json()
            pit["id"] = opened["id"]
            if opened.get("_shards", {}).get("failed", 0):
                raise ValueError("Incomplete ES PIT")
            filters = self._filters(scope, start, end)
            data = self._search(
                pit,
                {
                    "size": 0,
                    "query": {"bool": {"filter": filters}},
                    "aggs": {
                        "machines": {
                            "composite": {
                                "size": 51,
                                "sources": [
                                    {"machine": {"terms": {"field": "machine_id"}}}
                                ],
                            },
                            "aggs": {
                                "latest": {
                                    "top_hits": {
                                        "size": 1,
                                        "sort": [
                                            {"timestamp": "desc"},
                                            {"event_id": "asc"},
                                        ],
                                    }
                                },
                            },
                        },
                        "invalid_identity": {
                            "filter": {
                                "bool": {
                                    "should": [
                                        {
                                            "bool": {
                                                "must_not": {
                                                    "exists": {"field": "event_id"}
                                                }
                                            }
                                        },
                                        {
                                            "bool": {
                                                "must_not": {
                                                    "exists": {"field": "machine_id"}
                                                }
                                            }
                                        },
                                    ],
                                    "minimum_should_match": 1,
                                }
                            },
                        },
                    },
                },
            )["aggregations"]
            if data["invalid_identity"]["doc_count"]:
                raise ValueError("ES prediction lacks identity")
            buckets = data["machines"]["buckets"]
            if len(buckets) > 50:
                raise ValueError("Configured scope exceeds 50 machines")
            rows = [
                bucket["latest"]["hits"]["hits"][0]["_source"] for bucket in buckets
            ]
            if len({r["machine_id"] for r in rows}) != len(rows) or any(
                bucket["key"]["machine"] != row["machine_id"]
                for bucket, row in zip(buckets, rows, strict=True)
            ):
                raise ValueError("Invalid ES machine buckets")
            copies = self._verify_events(pit, filters, [r["event_id"] for r in rows])
            if any(copies[row["event_id"]] != canonical(row) for row in rows):
                raise ValueError("Snapshot differs from identity lookup")
            count = None
            if include_event_count:
                recent = self._filters(scope, end - timedelta(days=1), end)
                query = {
                    "size": 0,
                    "query": {"bool": {"filter": recent}},
                    "aggs": {
                        "events": {
                            "composite": {
                                "size": 10000,
                                "sources": [
                                    {"event": {"terms": {"field": "event_id"}}}
                                ],
                            }
                        }
                    },
                }
                count = 0
                previous = None
                for _ in range(self.max_count_pages):
                    events = self._search(pit, query)["aggregations"]["events"]
                    page = events["buckets"]
                    keys = [b["key"]["event"] for b in page]
                    if any(
                        not isinstance(key, str)
                        or len(key) != 64
                        or not set(key) <= set("0123456789abcdef")
                        for key in keys
                    ) or any(
                        type(b["doc_count"]) is not int or b["doc_count"] < 1
                        for b in page
                    ):
                        raise ValueError("Invalid ES event identity buckets")
                    if keys != sorted(set(keys)) or (
                        keys and previous is not None and keys[0] <= previous
                    ):
                        raise ValueError("ES event aggregation did not advance")
                    self._verify_events(
                        pit,
                        recent,
                        [b["key"]["event"] for b in page if b["doc_count"] > 1],
                    )
                    count += len(page)
                    if not page or "after_key" not in events:
                        break
                    after = events["after_key"]
                    if after["event"] < keys[-1]:
                        raise ValueError("Invalid ES event continuation")
                    previous = after["event"]
                    query["aggs"]["events"]["composite"]["after"] = after
                else:
                    raise ValueError("Exact event count page budget exceeded")
            return {"rows": rows, "event_count": count}
        finally:
            if pit.get("id"):
                self.client.request(
                    "DELETE", f"{self.url}/_pit", json={"id": pit["id"]}
                )

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
        finally:
            # Snapshot immutable receipt metadata, then release the SQLite read lock.
            # Object bytes are immutable and verified against that snapshot below.
            con.close()
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
            if name.startswith("bronze/") and digest(b"prediction\0" + raw) in accepted:
                accepted_keys.add(digest(canonical(json.loads(raw))))
            if not name.startswith("prediction/date=") or not name.endswith(".parquet"):
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
