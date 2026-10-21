"""CG14 raw CSV -> canonical scoring -> immutable outputs and CG15 archive.

Only the Kafka adapter owns source offsets. A disk journal owns replay between
services; no distributed exactly-once transaction is implied. POSIX local disk.
"""

import asyncio
import fcntl
import json
import math
import sqlite3
from contextlib import closing
from pathlib import Path
from urllib.parse import quote

import httpx
from jsonschema import ValidationError

from cg14_validation.validator import parse_csv_event
from scoring.response_ledger import canonical
from scoring.scope import validate_bundle_scope
from scripts.archive_consumer import consume as archive
from scripts.archive_consumer import digest, durable, event_key, mkdir, sync_dir
from scripts.cg14_occurrence import bind_occurrence
from scripts.validate_contracts import contract_hashes, validators

VERSION = "cg14.durable.v1"


class PipelineBlocked(RuntimeError):
    """Durable evidence retained; stop the poll and leave offsets uncommitted."""


def encoded(value):
    return canonical(value).encode()


class Pipeline:
    def __init__(
        self,
        root,
        client,
        *,
        namespace,
        manifest,
        scoring_url,
        source_kind="lab_fixture",
        legacy_source_kind="cg14-lab-kafka",
        es_url=None,
        es_index=None,
        attempts=3,
        timeout=10.0,
        checkpoint=lambda stage: None,
    ):
        if not namespace.strip() or source_kind not in ("lab_fixture", "smb_csv"):
            raise ValueError("Explicit stable namespace and canonical source required")
        if not isinstance(legacy_source_kind, str) or not legacy_source_kind.strip():
            raise ValueError("Exact legacy parser source kind required")
        if attempts < 1 or not math.isfinite(timeout) or timeout <= 0:
            raise ValueError("Positive finite request budgets required")
        if bool(es_url) != bool(es_index):
            raise ValueError(
                "ES endpoint and concrete index must be configured together"
            )
        for url in (scoring_url, es_url):
            if url and httpx.URL(url).scheme not in ("http", "https"):
                raise ValueError("Explicit HTTP(S) endpoints required")
        if es_index and any(
            c not in "abcdefghijklmnopqrstuvwxyz0123456789-_" for c in es_index
        ):
            raise ValueError(
                "Use a fixed lowercase ES index, never a date/alias pattern"
            )
        validate_bundle_scope(manifest)
        for field in ("policy", "model_version", "risk_threshold", "anomaly_threshold"):
            manifest[field]
        manifest["files"]["rf.pkl"]
        # Bind the complete configuration and schema bytes before accepting raw.
        self.config = {
            "version": VERSION,
            "namespace": namespace,
            "source_kind": source_kind,
            "legacy_source_kind": legacy_source_kind,
            "manifest": json.loads(canonical(manifest)),
            "scoring_url": scoring_url,
            "es_url": es_url,
            "es_index": es_index,
            "contracts": contract_hashes(),
        }
        self.root = Path(root).resolve()
        self.client = client
        self.attempts = attempts
        self.timeout = timeout
        self.checkpoint = checkpoint
        self.schemas = validators(Path(__file__).resolve().parents[1] / "contracts")

    def save(self, con, name, raw):
        durable(self.root / name, raw)
        con.execute("INSERT OR IGNORE INTO objects VALUES (?, ?)", (name, digest(raw)))
        con.commit()
        sync_dir(self.root)

    def evidence(self, con, key, reason, detail):
        raw = encoded({"reason": reason, "detail": detail})
        self.save(con, f"quarantine/{key}/{digest(raw)}.json", raw)

    async def request(self, con, key, method, url, **kwargs):
        """Persist attempts before I/O. Exhaustion blocks rather than discards."""
        for _ in range(self.attempts):
            cursor = con.execute(
                "INSERT INTO attempts (delivery, target) VALUES (?, ?)", (key, url)
            )
            attempt = cursor.lastrowid
            con.commit()
            try:
                # HTTPX timeouts are per operation/inactivity. Also cap total
                # wall time so a slow-drip response cannot outlive the poll budget.
                async with asyncio.timeout(self.timeout):
                    result = await self.client.request(
                        method,
                        url,
                        timeout=self.timeout,
                        follow_redirects=False,
                        **kwargs,
                    )
            except (httpx.TransportError, TimeoutError) as exc:
                status = type(exc).__name__
                result = None
            else:
                status = str(result.status_code)
            con.execute("UPDATE attempts SET result=? WHERE id=?", (status, attempt))
            con.commit()
            self.checkpoint("after_http")
            if result is not None and result.status_code < 500:
                return result
            await asyncio.sleep(0)  # finite retry budget; no background retry loop
        self.evidence(con, key, "HTTP_UNCERTAIN", {"target": url, "last": status})
        raise PipelineBlocked("HTTP exhausted; retain journal and replay same delivery")

    async def consume(self, messages, ack):
        """messages: existing PR58 (delivery_id, 'raw_csv', bytes) tuples."""
        mkdir(self.root)
        with (self.root / "worker.lock").open("a+b") as lock:
            # Nonblocking avoids a second worker waiting past its poll interval.
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            with closing(sqlite3.connect(self.root / "pipeline.sqlite3")) as con:
                con.execute("PRAGMA synchronous=FULL")
                con.executescript(
                    "CREATE TABLE IF NOT EXISTS config (value TEXT NOT NULL);"
                    "CREATE TABLE IF NOT EXISTS objects (path TEXT PRIMARY KEY, hash TEXT NOT NULL);"
                    "CREATE TABLE IF NOT EXISTS jobs (id TEXT PRIMARY KEY, fingerprint TEXT NOT NULL, "
                    "response BLOB, outcome TEXT);"
                    "CREATE TABLE IF NOT EXISTS attempts (id INTEGER PRIMARY KEY, delivery TEXT, "
                    "target TEXT, result TEXT);"
                )
                config = canonical(self.config)
                previous = con.execute("SELECT value FROM config").fetchall()
                if previous and previous != [(config,)]:
                    raise PipelineBlocked(
                        "Configuration changed; reconciliation required"
                    )
                if not previous:
                    con.execute("INSERT INTO config VALUES (?)", (config,))
                    con.commit()
                sync_dir(self.root)
                for name, expected in con.execute("SELECT path, hash FROM objects"):
                    if digest((self.root / name).read_bytes()) != expected:
                        raise PipelineBlocked("Committed journal object corruption")
                counts = {"completed": 0, "rejected": 0, "replay": 0}
                for delivery, kind, raw in messages:
                    outcome = await self.process(con, delivery, kind, raw)
                    counts[outcome] += 1
                self.checkpoint("before_ack")
                ack()  # all required destinations for the entire poll are durable
                return counts

    async def process(self, con, delivery, kind, raw):
        origin = json.loads(delivery)
        if (
            not isinstance(origin, list)
            or len(origin) != 5
            or origin[:2] != ["kafka", self.config["namespace"]]
            or not isinstance(origin[2], str)
            or not origin[2].strip()
            or any(type(v) is not int or v < 0 for v in origin[3:])
            or kind != "raw_csv"
            or not isinstance(raw, bytes)
        ):
            raise ValueError("Expected PR58 delivery coordinates and raw CSV bytes")
        key = digest(delivery.encode())
        fingerprint = digest(raw)
        job = con.execute(
            "SELECT fingerprint, response, outcome FROM jobs WHERE id=?", (delivery,)
        ).fetchone()
        if job and job[0] != fingerprint:
            raise PipelineBlocked("Delivery reused with different raw bytes")
        self.save(con, f"raw/{key}.bin", raw)
        self.save(
            con,
            f"origin/{key}.json",
            encoded({"delivery_id": delivery, "origin": origin}),
        )
        if not job:
            con.execute(
                "INSERT INTO jobs (id, fingerprint) VALUES (?, ?)",
                (delivery, fingerprint),
            )
            con.commit()
        self.checkpoint("after_raw")
        if job and job[2] == "rejected":
            return "replay"
        completed = job is not None and job[2] == "completed"
        if completed and job[1] is None:
            raise PipelineBlocked("Committed canonical response missing")
        _, namespace, topic, partition, offset = origin
        try:
            parsed = parse_csv_event(
                raw.decode("utf-8"),
                source_uri=f"kafka://{namespace}/{topic}",
                record_ref=f"{topic}/{partition}/{offset}",
                source_kind=self.config["legacy_source_kind"],
            )
        except UnicodeError:
            reasons = ["INVALID_UTF8"]
        else:
            reasons = [issue.code for issue in parsed.issues]
        if reasons:
            self.evidence(con, key, "VALIDATION_REJECTED", reasons)
            return self.finish(con, delivery, "rejected")
        bound = bind_occurrence(
            parsed.normalized_event,
            namespace=namespace,
            topic=topic,
            partition=partition,
            offset=offset,
            delivery_id=delivery,
            expected_event_id=parsed.event_id,
            expected_source_kind=self.config["legacy_source_kind"],
            source_kind=self.config["source_kind"],
        )
        event = bound["telemetry"]
        self.save(con, f"identity/{key}.json", encoded(bound))
        self.checkpoint("after_projection")
        if job and job[1] is not None:
            response = bytes(job[1])
        else:
            preconditions = {
                "X-CNC-Manifest-SHA256": digest(encoded(self.config["manifest"])),
                "X-CNC-Contracts-SHA256": digest(encoded(self.config["contracts"])),
            }
            result = await self.request(
                con,
                key,
                "POST",
                self.config["scoring_url"],
                content=encoded(event),
                headers={"Content-Type": "application/json", **preconditions},
            )
            if result.status_code == 422:
                self.evidence(
                    con, key, "HTTP_422", {"body_sha256": digest(result.content)}
                )
                return self.finish(con, delivery, "rejected")
            if not 200 <= result.status_code < 300:
                self.evidence(
                    con,
                    key,
                    "HTTP_BLOCKED",
                    {
                        "status": result.status_code,
                        "body_sha256": digest(result.content),
                    },
                )
                raise PipelineBlocked(
                    "HTTP conflict/configuration error; no source ack"
                )
            try:
                if any(result.headers.get(k) != v for k, v in preconditions.items()):
                    raise ValueError("API did not acknowledge worker preconditions")
                prediction = result.json()
                self.validate_prediction(prediction, event)
                response = encoded(prediction)
            except (ValueError, TypeError, KeyError, ValidationError) as exc:
                self.evidence(
                    con,
                    key,
                    "INVALID_RESPONSE",
                    {"body_sha256": digest(result.content)},
                )
                raise PipelineBlocked(
                    "Noncanonical scoring response; no source ack"
                ) from exc
            con.execute("UPDATE jobs SET response=? WHERE id=?", (response, delivery))
            con.commit()
            self.checkpoint("after_response")
        prediction = json.loads(response)
        self.validate_prediction(prediction, event)
        for stream, payload in (
            ("telemetry", encoded(event)),
            ("prediction", response),
        ):
            obj = json.loads(payload)
            self.save(con, f"outbox/{stream}/{event_key(stream, obj)}.json", payload)
            if completed:
                # Never let consume() create a replacement empty ledger after
                # a committed destination was lost. Verify its receipt read-only
                # before replay, then let CG15 validate hashes and all objects.
                ledger = (self.root / "archive/ledger.sqlite").as_uri() + "?mode=ro"
                with closing(sqlite3.connect(ledger, uri=True)) as receipts:
                    receipt = receipts.execute(
                        "SELECT outcome FROM deliveries WHERE id=?",
                        (canonical([delivery, stream]),),
                    ).fetchone()
                if not receipt or receipt[0] not in ("stored", "duplicate"):
                    raise PipelineBlocked("Committed archive receipt missing")
            # A rejection here is not a successful required archive destination.
            stats = archive(
                self.root / "archive",
                [(canonical([delivery, stream]), stream, payload)],
                lambda: None,
            )
            if stats["rejected"]:
                self.evidence(con, key, "ARCHIVE_REJECTED", {"stream": stream})
                raise PipelineBlocked("CG15 rejected a required output")
            self.checkpoint("after_" + stream + "_archive")
        if self.config["es_url"]:
            await self.index(con, key, prediction, response)
        self.checkpoint("before_done")
        self.finish(con, delivery, "completed")
        return "replay" if completed else "completed"

    def validate_prediction(self, prediction, event):
        self.schemas["prediction"].validate(prediction)
        if any(prediction.get(k) != v for k, v in event.items()):
            raise ValueError("Prediction differs from projected telemetry")
        manifest = self.config["manifest"]
        expected = {
            k: manifest[k]
            for k in ("policy", "model_version", "risk_threshold", "anomaly_threshold")
        }
        expected["model_artifact_sha256"] = manifest["files"]["rf.pkl"]
        if any(prediction.get(k) != v for k, v in expected.items()):
            raise ValueError("Prediction differs from pinned manifest")

    async def index(self, con, key, prediction, raw):
        base = self.config["es_url"].rstrip("/")
        index = self.config["es_index"]
        identity = event_key("prediction", prediction)
        url = f"{base}/{quote(index, safe='')}/_create/{identity}"
        result = await self.request(
            con,
            key,
            "PUT",
            url,
            content=raw,
            headers={"Content-Type": "application/json"},
        )
        if result.status_code == 409:
            result = await self.request(
                con, key, "GET", f"{base}/{index}/_doc/{identity}"
            )
            if (
                result.status_code == 200
                and encoded(result.json().get("_source")) == raw
            ):
                return  # immutable create replay; never overwrite another model
        elif result.status_code == 201:
            body = result.json()
            if (
                body.get("result") == "created"
                and body.get("_shards", {}).get("failed") == 0
                and body.get("_shards", {}).get("successful", 0) >= 1
            ):
                return
        self.evidence(con, key, "ES_BLOCKED", {"status": result.status_code})
        raise PipelineBlocked("ES required destination differs or failed")

    @staticmethod
    def finish(con, delivery, outcome):
        con.execute("UPDATE jobs SET outcome=? WHERE id=?", (outcome, delivery))
        con.commit()
        return outcome
