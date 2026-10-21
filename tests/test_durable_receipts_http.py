"""Real Uvicorn/HTTP, SQLite and CG15 regressions; synthetic in-memory models."""

import asyncio
import copy
import json
import socket
import sqlite3
import tempfile
import threading
import time
import unittest
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch

import httpx
import pyarrow.parquet as pq
import uvicorn
from test_cg14_durable_pipeline import NAMESPACE, RAW, message
from test_scoring_replay import AnomalyDouble, RiskDouble, manifest

from cg14_validation.validator import parse_csv_event
from scoring.response_ledger import canonical
from scoring.score_api import create_app, json_too_deep
from scripts.archive_consumer import consume as archive
from scripts.durable_pipeline import Pipeline, PipelineBlocked, encoded


def telemetry():
    from scripts.cg14_occurrence import bind_occurrence

    parsed = parse_csv_event(
        RAW.decode(),
        source_uri=f"kafka://{NAMESPACE}/raw",
        record_ref="raw/0/0",
        source_kind="cg14-lab-kafka",
    )
    return bind_occurrence(
        parsed.normalized_event,
        namespace=NAMESPACE,
        topic="raw",
        partition=0,
        offset=0,
        delivery_id=message()[0],
        expected_event_id=parsed.event_id,
        expected_source_kind="cg14-lab-kafka",
        source_kind="lab_fixture",
    )["telemetry"]


@contextmanager
def serving(root):
    app = create_app(root / "absent.json", ledger_path=root / "api.sqlite3")
    risk = RiskDouble()
    app.state.models = {"rf.pkl": risk, "if.pkl": AnomalyDouble()}
    app.state.manifest = manifest()
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        listener.listen()
        url = f"http://127.0.0.1:{listener.getsockname()[1]}/predict"
        server = uvicorn.Server(
            uvicorn.Config(
                app,
                lifespan="off",
                access_log=False,
                log_level="critical",
            )
        )
        thread = threading.Thread(target=server.run, kwargs={"sockets": [listener]})
        thread.start()
        try:
            deadline = time.monotonic() + 10
            while (
                not server.started and thread.is_alive() and time.monotonic() < deadline
            ):
                time.sleep(0.01)
            if not server.started:
                raise RuntimeError("Own Uvicorn did not start")
            yield app, risk, url
        finally:
            server.should_exit = True
            thread.join(10)
            if thread.is_alive():
                raise RuntimeError("Own Uvicorn did not stop")


class DurableReceiptHTTPTests(unittest.TestCase):
    def test_rejected_receipt_never_completes_or_acks_on_repeated_restart(self):
        for stream in ("telemetry", "prediction"):
            with self.subTest(stream=stream), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                with serving(root) as (_, risk, url):
                    asyncio.run(self.rejected(root, risk, url, stream))

    async def rejected(self, root, risk, url, stream):
        event = telemetry()
        async with httpx.AsyncClient(trust_env=False) as client:
            payload = event
            if stream == "prediction":
                reply = await client.post(
                    url,
                    content=encoded(event),
                    headers={"Content-Type": "application/json"},
                )
                self.assertEqual(reply.status_code, 200, reply.text)
                payload = reply.json()
            stale = copy.deepcopy(payload)
            stale["rpm"] = 1501
            target = root / "worker/archive"
            self.assertEqual(
                archive(target, [("prior", stream, encoded(stale))], lambda: None)[
                    "stored"
                ],
                1,
            )
            original = {p: p.read_bytes() for p in target.rglob("*.parquet")}
            acks = []
            for attempt in range(4):
                # Reopen every connection and worker: no cached rejection state.
                worker = Pipeline(
                    root / "worker",
                    client,
                    namespace=NAMESPACE,
                    manifest=manifest(),
                    scoring_url=url,
                )
                with self.subTest(attempt=attempt), self.assertRaises(PipelineBlocked):
                    await worker.consume(
                        [message()], lambda attempt=attempt: acks.append(attempt)
                    )
                with sqlite3.connect(root / "worker/pipeline.sqlite3") as db:
                    self.assertEqual(
                        db.execute("SELECT outcome FROM jobs").fetchall(), [(None,)]
                    )
                with sqlite3.connect(target / "ledger.sqlite") as db:
                    self.assertEqual(
                        db.execute(
                            "SELECT outcome FROM deliveries WHERE id=?",
                            (canonical([message()[0], stream]),),
                        ).fetchone(),
                        ("rejected",),
                    )
            self.assertEqual(acks, [])
            self.assertEqual(risk.calls, 1)
            self.assertEqual(original, {p: p.read_bytes() for p in original})
            row = pq.read_table(next(iter(original))).to_pylist()[0]
            self.assertEqual(json.loads(row["payload_json"])["rpm"], 1501)

    def test_completed_receipts_and_failed_source_commit(self):
        with tempfile.TemporaryDirectory() as tmp, serving(Path(tmp)) as (_, risk, url):
            asyncio.run(self.completed(Path(tmp), risk, url))

    async def completed(self, root, risk, url):
        async with httpx.AsyncClient(trust_env=False) as client:

            def worker():
                return Pipeline(
                    root / "worker",
                    client,
                    namespace=NAMESPACE,
                    manifest=manifest(),
                    scoring_url=url,
                )

            def failed_commit():
                raise RuntimeError("Source commit uncertain")

            with self.assertRaisesRegex(RuntimeError, "commit uncertain"):
                await worker().consume([message()], failed_commit)
            acks = []
            stats = await worker().consume([message()], lambda: acks.append(True))
            self.assertEqual(stats["replay"], 1)
            self.assertEqual(acks, [True])
            self.assertEqual(risk.calls, 1)
            ledger = root / "worker/archive/ledger.sqlite"
            for stream in ("telemetry", "prediction"):
                for outcome in ("rejected", "unknown", None):
                    with self.subTest(stream=stream, outcome=outcome):
                        with sqlite3.connect(ledger) as db:
                            db.execute(
                                "UPDATE deliveries SET outcome=? WHERE id=?",
                                (outcome, canonical([message()[0], stream])),
                            )
                        with self.assertRaises(PipelineBlocked):
                            await worker().consume(
                                [message()], lambda: acks.append(False)
                            )
                        self.assertEqual(acks, [True])
                with sqlite3.connect(ledger) as db:
                    db.execute(
                        "UPDATE deliveries SET outcome='stored' WHERE id=?",
                        (canonical([message()[0], stream]),),
                    )


class BoundedValidationHTTPTests(unittest.TestCase):
    def test_depth_limit_escapes_and_internal_errors_propagate(self):
        self.assertFalse(json_too_deep(b"[" * 64 + b"0" + b"]" * 64))
        self.assertTrue(json_too_deep(b"[" * 65 + b"0" + b"]" * 65))
        self.assertFalse(json_too_deep(json.dumps('é[{}]\\"' * 200).encode()))

        async def probe():
            app = create_app()
            middleware = app.user_middleware[0].kwargs["dispatch"]

            class Body:
                async def stream(self):
                    yield b"{}"

            async def next_handler(request):
                self.fail("Do not continue after an internal error")

            for error in (MemoryError("probe"), RuntimeError("internal bug")):
                with (
                    patch("scoring.score_api.json_too_deep", side_effect=error),
                    self.assertRaises(type(error)),
                ):
                    await middleware(Body(), next_handler)

        asyncio.run(probe())

    def test_deep_malformed_fragmented_and_model_unready(self):
        with (
            tempfile.TemporaryDirectory() as tmp,
            serving(Path(tmp)) as (app, risk, url),
        ):
            asyncio.run(self.requests(Path(tmp), app, risk, url))

    async def requests(self, root, app, risk, url):
        async def chunks(raw):
            for pos in range(0, len(raw), 97):
                yield raw[pos : pos + 97]
                await asyncio.sleep(0)

        cases = [
            ("list-2000", b"[" * 2000 + b"0" + b"]" * 2000, 422),
            ("object-2000", b'{"a":' * 2000 + b"0" + b"}" * 2000, 422),
            (
                "mixed",
                b'[{"a":' * 500
                + json.dumps('é\\"[]', ensure_ascii=False).encode()
                + b"}]" * 500,
                422,
            ),
            ("malformed", b'{"a":', 422),
            ("invalid", b'{"rpm":[1]}', 422),
            ("limit", b" " * (32768 - 2) + b"{}", 422),
            ("oversize", b" " * (32769 - 2) + b"{}", 413),
            ("deep-oversize", b"[" * 2000 + b"0" + b"]" * 2000 + b" " * 28768, 413),
            (
                "string-escapes-utf8",
                json.dumps({"marker": 'é[{}]\\"' * 50}, ensure_ascii=False).encode(),
                422,
            ),
        ]
        cases += [
            (f"list-{depth}", b"[" * depth + b"0" + b"]" * depth, 422)
            for depth in (100, 300, 600, 900)
        ]
        async with httpx.AsyncClient(
            trust_env=False, limits=httpx.Limits(max_keepalive_connections=0)
        ) as client:
            for label, raw, status in cases:
                for fragmented in (False, True):
                    with self.subTest(case=label, fragmented=fragmented):
                        reply = await client.post(
                            url,
                            content=chunks(raw) if fragmented else raw,
                            headers={"Content-Type": "application/json"},
                        )
                        self.assertEqual(reply.status_code, status)
                        self.assertLess(len(reply.content), 256)
                        self.assertNotIn(b"input", reply.content)
                        self.assertNotIn(b"marker", reply.content)
                        self.assertFalse((root / "api.sqlite3").exists())
                        self.assertEqual(risk.calls, 0)
            app.state.models = None
            reply = await client.post(
                url,
                content=encoded(telemetry()),
                headers={"Content-Type": "application/json"},
            )
            self.assertEqual(reply.status_code, 503, reply.text)
            self.assertFalse((root / "api.sqlite3").exists())
            self.assertEqual(risk.calls, 0)

    def test_valid_escaped_strings_and_exact_byte_limit(self):
        with tempfile.TemporaryDirectory() as tmp, serving(Path(tmp)) as (_, risk, url):
            asyncio.run(self.valid_limit(Path(tmp), risk, url))

    async def valid_limit(self, root, risk, url):
        event = telemetry()
        event["source"]["uri"] = 'é[{}]\\"' * 50
        body = json.dumps(event, ensure_ascii=False).encode()
        body += b" " * (32768 - len(body))

        async def chunks(raw):
            for pos in range(0, len(raw), 101):
                yield raw[pos : pos + 101]

        async with httpx.AsyncClient(trust_env=False) as client:
            for raw, status in ((body, 200), (body + b" ", 413)):
                reply = await client.post(
                    url,
                    content=chunks(raw),
                    headers={"Content-Type": "application/json"},
                )
                self.assertEqual(reply.status_code, status)
            self.assertEqual(risk.calls, 1)
            with sqlite3.connect(root / "api.sqlite3") as db:
                self.assertEqual(
                    db.execute("SELECT count(*) FROM scoring_responses").fetchone()[0],
                    1,
                )


if __name__ == "__main__":
    unittest.main()
