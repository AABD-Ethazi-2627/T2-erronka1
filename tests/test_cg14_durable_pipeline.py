"""Disk/SQLite/CG15 + real scoring ASGI; Kafka/failed HTTP transports are doubles."""

import asyncio
import copy
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from threading import Event
from unittest.mock import patch

import httpx
from api_client import api_client
from test_kafka_archive import Consumer, record
from test_scoring_replay import AnomalyDouble, RiskDouble, manifest

from cg14_validation.validator import stable_event_id
from scoring.score_api import create_app
from scripts.archive_consumer import digest
from scripts.build_durable_pipeline_flow import build
from scripts.build_durable_pipeline_flow import main as export_flow
from scripts.durable_pipeline import Pipeline, PipelineBlocked
from scripts.kafka_archive import AssignmentLost, delivery_id, run

RAW = b"2026-10-21T08:00:00Z,CNC-001,H,300,310,1500,40,10,1,0,0,0,0,0\n"
NAMESPACE = "synthetic-cluster/topic-generation1"
URL = "http://testserver/predict"


def message(offset=0, raw=RAW):
    return delivery_id(NAMESPACE, "raw", 0, offset), "raw_csv", raw


class LostResponse:
    """Lose a real ASGI success after the server's response ledger committed."""

    def __init__(self, client):
        self.client = client

    async def request(self, *args, **kwargs):
        result = await self.client.request(*args, **kwargs)
        if result.status_code == 200:
            raise httpx.ReadTimeout("Synthetic transport loss after API commit")
        return result


class DurablePipelineTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.config = manifest()
        self.acks = []

    def app(self):
        return create_app(
            self.root / "absent.json", ledger_path=self.root / "api.sqlite3"
        )

    def ready(self, app, config=None):
        risk = RiskDouble()
        app.state.models = {"rf.pkl": risk, "if.pkl": AnomalyDouble()}
        app.state.manifest = config or self.config
        return risk

    def worker(self, client, **kwargs):
        return Pipeline(
            self.root / "worker",
            client,
            namespace=NAMESPACE,
            manifest=self.config,
            scoring_url=URL,
            **kwargs,
        )

    def ack(self):
        with sqlite3.connect(self.root / "worker/pipeline.sqlite3") as con:
            self.assertFalse(
                con.execute("SELECT id FROM jobs WHERE outcome IS NULL").fetchall()
            )
        self.acks.append(True)

    async def test_raw_projection_canonical_outputs_archive_and_distinct_occurrences(
        self,
    ):
        app = self.app()
        async with api_client(app) as client:
            risk = self.ready(app)
            stats = await self.worker(client).consume(
                [message(4), message(8)], self.ack
            )
            self.assertEqual(stats, {"completed": 2, "rejected": 0, "replay": 0})
            self.assertEqual(risk.calls, 2)
            predictions = [
                json.loads(p.read_bytes())
                for p in (self.root / "worker/outbox/prediction").glob("*.json")
            ]
            self.assertEqual(len({p["event_id"] for p in predictions}), 2)
            for offset in (4, 8):
                key = digest(message(offset)[0].encode())
                self.assertEqual(
                    (self.root / f"worker/raw/{key}.bin").read_bytes(), RAW
                )
                bound = json.loads(
                    (self.root / f"worker/identity/{key}.json").read_bytes()
                )
                self.assertEqual(bound["identity"]["delivery_id"], message(offset)[0])
                self.assertEqual(
                    bound["identity"]["legacy_source"]["raw_record"],
                    RAW.decode().rstrip(),
                )
                self.assertEqual(
                    bound["identity"]["legacy_event_id"],
                    stable_event_id(RAW.decode().rstrip(), "cg14-lab-kafka"),
                )
                self.assertNotIn("raw_record", bound["telemetry"]["source"])
                self.assertNotIn("machine_failure", bound["telemetry"])
            self.assertEqual(
                len(list((self.root / "worker/archive").rglob("*.parquet"))), 4
            )
            before = {
                p: p.read_bytes() for p in (self.root / "worker").rglob("*.parquet")
            }
            stats = await self.worker(client).consume(
                [message(4), message(8)], self.ack
            )
            self.assertEqual(stats["replay"], 2)
            self.assertEqual(risk.calls, 2)
            self.assertEqual(before, {p: p.read_bytes() for p in before})
        self.assertEqual(self.acks, [True, True])

    async def test_invalid_csv_utf8_oversize_durable_quarantine_before_ack(self):
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(
                lambda _: self.fail("No HTTP for rejected input")
            )
        ) as client:
            stats = await self.worker(client).consume(
                [message(0, b"bad,csv"), message(1, b"\xff"), message(2, b"a" * 9000)],
                self.ack,
            )
        self.assertEqual(stats["rejected"], 3)
        self.assertEqual(
            len(list((self.root / "worker/quarantine").rglob("*.json"))), 3
        )
        self.assertEqual(len(list((self.root / "worker/raw").glob("*.bin"))), 3)
        self.assertFalse((self.root / "worker/outbox").exists())

    async def test_restart_every_boundary_preserves_prediction_bytes(self):
        stages = [
            "after_raw",
            "after_projection",
            "after_http",
            "after_response",
            "after_telemetry_archive",
            "after_prediction_archive",
            "before_done",
            "before_ack",
        ]
        for stage in stages:
            with self.subTest(stage=stage), tempfile.TemporaryDirectory() as directory:
                self.root = Path(directory)
                self.acks = []
                app = self.app()

                def crash(actual, stage=stage):
                    if actual == stage:
                        raise RuntimeError("Synthetic process boundary")

                async with api_client(app) as client:
                    risk = self.ready(app)
                    with self.assertRaisesRegex(RuntimeError, "process boundary"):
                        await self.worker(client, checkpoint=crash).consume(
                            [message()], self.ack
                        )
                    self.assertFalse(self.acks)
                    called = risk.calls
                restarted = self.app()
                async with api_client(restarted) as client:
                    risk = self.ready(restarted)
                    await self.worker(client).consume([message()], self.ack)
                    self.assertEqual(called + risk.calls, 1)
                    prediction = next(
                        (self.root / "worker/outbox/prediction").glob("*.json")
                    ).read_bytes()
                    with sqlite3.connect(self.root / "api.sqlite3") as con:
                        canonical = (
                            con.execute("SELECT response FROM scoring_responses")
                            .fetchone()[0]
                            .encode()
                        )
                    self.assertEqual(prediction, canonical)
                    self.assertEqual(self.acks, [True])

    async def test_uncertain_success_restarts_using_api_canonical_response(self):
        app = self.app()
        async with api_client(app) as client:
            risk = self.ready(app)
            with self.assertRaises(PipelineBlocked):
                await self.worker(LostResponse(client), attempts=1).consume(
                    [message()], self.ack
                )
            self.assertEqual(risk.calls, 1)
        self.assertFalse(self.acks)
        self.assertTrue(list((self.root / "worker/quarantine").rglob("*.json")))
        app = self.app()
        async with api_client(app) as client:
            risk = self.ready(app)
            await self.worker(client).consume([message()], self.ack)
            self.assertEqual(risk.calls, 0)

    async def test_model_change_after_uncertain_success_fails_before_rescoring(self):
        app = self.app()
        async with api_client(app) as client:
            risk = self.ready(app)
            with self.assertRaises(PipelineBlocked):
                await self.worker(LostResponse(client), attempts=1).consume(
                    [message()], self.ack
                )
            changed = copy.deepcopy(self.config)
            changed["files"]["rf.pkl"] = "c" * 64
            self.ready(app, changed)
            with self.assertRaises(PipelineBlocked):
                await self.worker(client).consume([message()], self.ack)
            self.assertEqual(risk.calls, 1)
            self.assertEqual(app.state.models["rf.pkl"].calls, 0)
        self.assertFalse(self.acks)

    async def test_contract_precondition_and_old_api_without_echo_fail_closed(self):
        app = self.app()
        async with api_client(app) as client:
            risk = self.ready(app)
            worker = self.worker(client)
            worker.config["contracts"]["prediction.schema.json"] = "changed"
            with self.assertRaises(PipelineBlocked):
                await worker.consume([message()], self.ack)
            self.assertEqual(risk.calls, 0)
            # A legacy API that ignores headers must not silently pass.
            with tempfile.TemporaryDirectory() as directory:
                self.root = Path(directory)

                class OldAPI:
                    async def request(self, *args, **kwargs):
                        result = await client.request(*args, **kwargs)
                        del result.headers["X-CNC-Manifest-SHA256"]
                        return result

                with self.assertRaises(PipelineBlocked):
                    await self.worker(OldAPI()).consume([message()], self.ack)
        self.assertFalse(self.acks)

    async def test_es_create_uncertain_success_replay_and_conflict_block_ack(self):
        app = self.app()
        documents = {}
        calls = []
        lose_first = True

        def es(request):
            nonlocal lose_first
            calls.append((request.method, request.url.path))
            key = request.url.path.rsplit("/", 1)[-1]
            if request.method == "GET":
                return httpx.Response(200, json={"_source": documents[key]})
            if key in documents:
                return httpx.Response(409, json={"error": "version_conflict"})
            documents[key] = json.loads(request.content)
            if lose_first:
                lose_first = False
                raise httpx.ReadTimeout("Synthetic lost ES create response")
            return httpx.Response(
                201,
                json={"result": "created", "_shards": {"failed": 0, "successful": 1}},
            )

        async with (
            api_client(app) as client,
            httpx.AsyncClient(transport=httpx.MockTransport(es)) as es_client,
        ):
            risk = self.ready(app)

            class Routing:
                async def request(self, method, url, **kwargs):
                    target = es_client if url.startswith("http://es/") else client
                    return await target.request(method, url, **kwargs)

            worker = self.worker(
                Routing(),
                es_url="http://es",
                es_index="cnc-telemetry-synthetic",
                attempts=1,
            )
            with self.assertRaises(PipelineBlocked):
                await worker.consume([message()], self.ack)
            self.assertFalse(self.acks)
            self.assertEqual(risk.calls, 1)
            await worker.consume([message()], self.ack)
            self.assertEqual(risk.calls, 1)
            self.assertEqual([method for method, _ in calls], ["PUT", "PUT", "GET"])
            self.acks = []
            # Interrupted local transaction after external commit must compare
            # the stored _source, never replace a conflicting remote document.
            with sqlite3.connect(self.root / "worker/pipeline.sqlite3") as con:
                con.execute("UPDATE jobs SET outcome=NULL")
            original = copy.deepcopy(documents)
            next(iter(documents.values()))["scored_at"] = "2000-01-01T00:00:00Z"
            with self.assertRaises(PipelineBlocked):
                await worker.consume([message()], self.ack)
            self.assertFalse(self.acks)
            self.assertNotEqual(documents, original)
            documents.clear()
            documents.update(original)
            document = next(iter(documents.values()))
            document["risk_alert"] = int(document["risk_alert"])
            with self.assertRaises(PipelineBlocked):
                await worker.consume([message()], self.ack)
            self.assertFalse(self.acks)

    async def test_changed_local_manifest_contract_targets_and_raw_fail_closed(self):
        app = self.app()
        async with api_client(app) as client:
            self.ready(app)
            await self.worker(client).consume([message()], self.ack)
            for change in (
                "manifest",
                "contracts",
                "scoring_url",
                "es_url",
                "source_kind",
            ):
                worker = self.worker(client)
                worker.config = copy.deepcopy(worker.config)
                if change == "manifest":
                    worker.config[change]["model_version"] = "different"
                else:
                    worker.config[change] = "different"
                with self.subTest(change=change), self.assertRaises(PipelineBlocked):
                    await worker.consume([message()], self.ack)
            with self.assertRaises(PipelineBlocked):
                await self.worker(client).consume(
                    [message(raw=RAW + b"changed")], self.ack
                )
        self.assertEqual(self.acks, [True])

    async def test_http_status_classes_are_explicit_and_never_fabricate_predictions(
        self,
    ):
        for status in (201, 204, 302, 400, 401, 404, 409, 422, 500, 503):
            with (
                self.subTest(status=status),
                tempfile.TemporaryDirectory() as directory,
            ):
                self.root = Path(directory)
                self.acks = []
                calls = []

                def reply(request, calls=calls, status=status):
                    calls.append(request)
                    return httpx.Response(
                        status, json={"detail": "synthetic HTTP status transport"}
                    )

                async with httpx.AsyncClient(
                    transport=httpx.MockTransport(reply)
                ) as client:
                    if status == 422:
                        stats = await self.worker(client, attempts=2).consume(
                            [message()], self.ack
                        )
                        self.assertEqual(stats["rejected"], 1)
                    else:
                        with self.assertRaises(PipelineBlocked):
                            await self.worker(client, attempts=2).consume(
                                [message()], self.ack
                            )
                        self.assertFalse(self.acks)
                    self.assertEqual(len(calls), 2 if status >= 500 else 1)
                self.assertTrue(list((self.root / "worker/quarantine").rglob("*.json")))
                self.assertFalse((self.root / "worker/outbox/prediction").exists())

    async def test_real_api_unready_503_has_bounded_attempts_no_ack(self):
        async with api_client(self.app()) as client:
            with self.assertRaises(PipelineBlocked):
                await self.worker(client, attempts=2).consume([message()], self.ack)
        with sqlite3.connect(self.root / "worker/pipeline.sqlite3") as con:
            self.assertEqual(
                con.execute("SELECT result FROM attempts").fetchall(),
                [("503",), ("503",)],
            )
        self.assertFalse(self.acks)

    async def test_second_worker_cannot_cross_live_journal_lock(self):
        app = self.app()
        arrived, release = asyncio.Event(), asyncio.Event()
        async with api_client(app) as client:
            self.ready(app)

            class Paused:
                async def request(self, *args, **kwargs):
                    arrived.set()
                    await release.wait()
                    return await client.request(*args, **kwargs)

            first = asyncio.create_task(
                self.worker(Paused()).consume([message()], self.ack)
            )
            try:
                await asyncio.wait_for(arrived.wait(), 10)
                with self.assertRaises(BlockingIOError):
                    await self.worker(client).consume([message()], self.ack)
                self.assertFalse(self.acks)
            finally:
                release.set()
                await first
        self.assertEqual(self.acks, [True])

    async def test_transport_timeout_and_connect_failure_are_bounded(self):
        for error in (httpx.ReadTimeout, httpx.ConnectError):
            with self.subTest(error=error), tempfile.TemporaryDirectory() as directory:
                self.root = Path(directory)
                self.acks = []

                def failed(request, error=error):
                    raise error("Synthetic failure")

                async with httpx.AsyncClient(
                    transport=httpx.MockTransport(failed)
                ) as client:
                    with self.assertRaises(PipelineBlocked):
                        await self.worker(client, attempts=2).consume(
                            [message()], self.ack
                        )
                self.assertFalse(self.acks)
                with sqlite3.connect(self.root / "worker/pipeline.sqlite3") as con:
                    self.assertEqual(
                        con.execute("SELECT count(*) FROM attempts").fetchone()[0], 2
                    )
        with tempfile.TemporaryDirectory() as directory:
            self.root = Path(directory)
            self.acks = []

            async def slow_drip(request):
                await asyncio.sleep(10)
                return httpx.Response(200, json={})

            async with httpx.AsyncClient(
                transport=httpx.MockTransport(slow_drip)
            ) as client:
                with self.assertRaises(PipelineBlocked):
                    await self.worker(client, attempts=2, timeout=0.01).consume(
                        [message()], self.ack
                    )
            with sqlite3.connect(self.root / "worker/pipeline.sqlite3") as con:
                self.assertEqual(
                    con.execute("SELECT result FROM attempts").fetchall(),
                    [("TimeoutError",), ("TimeoutError",)],
                )
            self.assertFalse(self.acks)

    async def test_committed_corruption_and_archive_failure_prevent_ack(self):
        app = self.app()
        async with api_client(app) as client:
            self.ready(app)
            await self.worker(client).consume([message()], self.ack)
            self.acks = []
            raw_path = next((self.root / "worker/raw").glob("*.bin"))
            raw_path.write_bytes(b"corrupt")
            with self.assertRaises(PipelineBlocked):
                await self.worker(client).consume([message()], self.ack)
            raw_path.write_bytes(RAW)
            ledger = self.root / "worker/archive/ledger.sqlite"
            retained = ledger.read_bytes()
            ledger.unlink()
            with self.assertRaises(sqlite3.OperationalError):
                await self.worker(client).consume([message()], self.ack)
            self.assertFalse(ledger.exists())
            ledger.write_bytes(retained)
            with sqlite3.connect(ledger) as con:
                con.execute("DELETE FROM deliveries")
            with self.assertRaises(PipelineBlocked):
                await self.worker(client).consume([message()], self.ack)
            ledger.write_bytes(retained)
            parquet = next((self.root / "worker/archive").rglob("*.parquet"))
            parquet.write_bytes(b"corrupt")
            with self.assertRaisesRegex(ValueError, "archive corruption"):
                await self.worker(client).consume([message()], self.ack)
        self.assertFalse(self.acks)

    async def test_archive_rejection_is_blocking_and_disk_failures_never_ack(self):
        app = self.app()
        async with api_client(app) as client:
            self.ready(app)
            with (
                patch("scripts.durable_pipeline.archive", return_value={"rejected": 1}),
                self.assertRaises(PipelineBlocked),
            ):
                await self.worker(client).consume([message()], self.ack)
            self.assertFalse(self.acks)
            with (
                patch(
                    "scripts.durable_pipeline.durable",
                    side_effect=OSError("synthetic disk full"),
                ),
                self.assertRaises(OSError),
            ):
                await self.worker(client).consume([message()], self.ack)
            self.assertFalse(self.acks)
            await self.worker(client).consume([message()], self.ack)
        self.assertEqual(self.acks, [True])


class KafkaPipelineBoundaryTests(unittest.TestCase):
    """PR58's consumer double + real pipeline disk sinks and ASGI, not Kafka."""

    def test_commit_uncertain_rebalance_and_required_destinations(self):
        from kafka.structs import TopicPartition

        tp = TopicPartition("raw", 0)
        for failure in ("commit", "rebalance", "later_record"):
            with (
                self.subTest(failure=failure),
                tempfile.TemporaryDirectory() as directory,
            ):
                root = Path(directory)
                app = create_app(root / "absent.json", ledger_path=root / "api.sqlite3")
                risk = RiskDouble()
                app.state.models = {"rf.pkl": risk, "if.pkl": AnomalyDouble()}
                app.state.manifest = manifest()

                def on_commit(offsets, root=root):
                    self.assertEqual(offsets[tp].offset, 8)
                    self.assertEqual(
                        len(list((root / "worker/archive").rglob("*.parquet"))), 4
                    )
                    raise RuntimeError("Synthetic uncertain commit")

                consumer = Consumer(
                    [{tp: [record(4, RAW, tp), record(7, RAW, tp)]}],
                    assignment=(tp,),
                    on_commit=on_commit,
                )
                with asyncio.Runner() as runner:
                    client = httpx.AsyncClient(
                        transport=httpx.ASGITransport(app=app), base_url=URL
                    )

                    def checkpoint(
                        stage, failure=failure, consumer=consumer, risk=risk
                    ):
                        if failure == "rebalance" and stage == "before_ack":
                            consumer.listener.on_partitions_revoked([tp])
                        if (
                            failure == "later_record"
                            and stage == "after_prediction_archive"
                            and risk.calls == 2
                        ):
                            raise RuntimeError("Synthetic later record failure")

                    def sink(
                        target, messages, ack, client=client, checkpoint=checkpoint
                    ):
                        return runner.run(
                            Pipeline(
                                target,
                                client,
                                namespace=NAMESPACE,
                                manifest=manifest(),
                                scoring_url=URL,
                                checkpoint=checkpoint,
                            ).consume(messages, ack)
                        )

                    expected = (
                        AssignmentLost if failure == "rebalance" else RuntimeError
                    )
                    try:
                        with self.assertRaises(expected):
                            run(
                                root / "worker",
                                consumer,
                                {"raw": "raw_csv"},
                                NAMESPACE,
                                consumer.stop,
                                sink=sink,
                                max_polls=1,
                                report=lambda _: None,
                            )
                        self.assertFalse(consumer.commits)
                        self.assertEqual(
                            consumer.closed,
                            [{"autocommit": False, "timeout_ms": 30000}],
                        )
                        replay = Consumer(
                            [{tp: [record(4, RAW, tp), record(7, RAW, tp)]}],
                            assignment=(tp,),
                        )

                        def healthy(target, messages, ack, client=client):
                            return runner.run(
                                Pipeline(
                                    target,
                                    client,
                                    namespace=NAMESPACE,
                                    manifest=manifest(),
                                    scoring_url=URL,
                                ).consume(messages, ack)
                            )

                        run(
                            root / "worker",
                            replay,
                            {"raw": "raw_csv"},
                            NAMESPACE,
                            replay.stop,
                            sink=healthy,
                            max_polls=1,
                            report=lambda _: None,
                        )
                        self.assertEqual(replay.commits[0][tp].offset, 8)
                        self.assertEqual(risk.calls, 2)
                    finally:
                        runner.run(client.aclose())

    def test_empty_polls_are_bounded(self):
        consumer = Consumer([{}, {}, {}])
        run("unused", consumer, {"raw": "raw_csv"}, NAMESPACE, Event(), max_polls=2)
        self.assertFalse(consumer.commits)
        self.assertTrue(consumer.closed)

    def test_export_disabled_staged_bridge_preserves_all_relationships_no_overwrite(
        self,
    ):
        flow = build()["flowContents"]
        self.assertTrue(
            all(p["scheduledState"] == "DISABLED" for p in flow["processors"])
        )
        self.assertTrue(all(p["executionNode"] == "ALL" for p in flow["processors"]))
        self.assertTrue(
            all(
                p["scheduledState"] == "DISABLED"
                for p in flow["inputPorts"] + flow["outputPorts"]
            )
        )
        self.assertTrue(all(p["bulletinLevel"] == "WARN" for p in flow["processors"]))
        self.assertTrue(
            all(isinstance(p["propertyDescriptors"], dict) for p in flow["processors"])
        )
        self.assertTrue(all(type(c["labelIndex"]) is int for c in flow["connections"]))
        self.assertFalse(any("Kafka" in p["type"] for p in flow["processors"]))
        self.assertTrue(
            all(not p["autoTerminatedRelationships"] for p in flow["processors"])
        )
        relationships = {
            r for c in flow["connections"] for r in c["selectedRelationships"]
        }
        self.assertTrue(
            {"original", "output stream", "nonzero status", "completed", "unmatched"}
            <= relationships
        )
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "flow.json"
            export_flow(["--output", str(output)])
            self.assertEqual(json.loads(output.read_text()), build())
            with self.assertRaises(FileExistsError):
                export_flow(["--output", str(output)])
