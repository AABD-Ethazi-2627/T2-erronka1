"""Offline transport failures with the real CG15 sink; no broker is contacted."""

import json
import signal
import sqlite3
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Barrier, Event
from types import SimpleNamespace
from unittest.mock import patch

try:
    from kafka.structs import TopicPartition
except ModuleNotFoundError as exc:
    if exc.name != "kafka":
        raise
    raise unittest.SkipTest(
        "optional Kafka transport: uv sync --locked --extra kafka"
    ) from exc

from scripts.archive_consumer import consume
from scripts.kafka_archive import (
    ArchiveRebalanceListener,
    AssignmentLost,
    archive_poll,
    delivery_id,
    main,
    run,
)

TP = TopicPartition("normalized", 0)
STREAMS = {"normalized": "telemetry", "predictions": "prediction"}
RAW = Path("contracts/examples/valid/telemetry.json").read_bytes()


def record(offset=0, value=RAW, tp=TP):
    return SimpleNamespace(
        topic=tp.topic, partition=tp.partition, offset=offset, value=value
    )


class Consumer:
    def __init__(self, polls=(), assignment=(TP,), on_commit=None):
        self.polls = iter(polls)
        self.owned = set(assignment)
        self.commits = []
        self.closed = []
        self.on_commit = on_commit
        self.stop = Event()

    def subscribe(self, *, topics, listener):
        self.topics = topics
        self.listener = listener
        listener.on_partitions_revoked([])  # Initial join is not loss.
        listener.on_partitions_assigned(self.owned)

    def poll(self, **kwargs):
        value = next(self.polls, None)
        if value is None:
            self.stop.set()
            return {}
        if callable(value):
            return value(self)
        return value

    def assignment(self):
        return self.owned

    def commit(self, *, offsets, timeout_ms):
        if self.on_commit:
            self.on_commit(offsets)
        self.commits.append(offsets)

    def close(self, **kwargs):
        self.closed.append(kwargs)


class KafkaArchiveTests(unittest.TestCase):
    def execute(self, root, consumer, **kwargs):
        return run(
            root,
            consumer,
            STREAMS,
            "cluster-A/topic-epoch-1",
            consumer.stop,
            report=lambda _: None,
            **kwargs,
        )

    def test_next_offsets_explicit_only_after_ledger_and_raw_are_durable(self):
        other = TopicPartition("predictions", 2)
        prediction = Path("contracts/examples/valid/prediction.json").read_bytes()
        with tempfile.TemporaryDirectory() as root:

            def verify(offsets):
                with sqlite3.connect(Path(root) / "ledger.sqlite") as db:
                    self.assertEqual(
                        db.execute("SELECT count(*) FROM deliveries").fetchone()[0], 3
                    )
                self.assertEqual(len(list((Path(root) / "bronze").glob("*.bin"))), 3)
                self.assertEqual(
                    {tp: offset.offset for tp, offset in offsets.items()},
                    {TP: 8, other: 11},
                )

            client = Consumer(
                [
                    {
                        TP: [record(5), record(7, b"{invalid")],
                        other: [record(10, prediction, other)],
                    }
                ],
                assignment=(TP, other),
                on_commit=verify,
            )
            self.assertEqual(self.execute(root, client), 1)
            self.assertEqual(
                client.closed, [{"autocommit": False, "timeout_ms": 30000}]
            )
            self.assertEqual(len(client.commits), 1)

    def test_commit_failure_restart_replays_without_overwrite(self):
        with tempfile.TemporaryDirectory() as root:

            def disconnected(offsets):
                raise RuntimeError("commit outcome unknown")

            client = Consumer([{TP: [record()]}], on_commit=disconnected)
            with self.assertRaisesRegex(RuntimeError, "outcome unknown"):
                self.execute(root, client)
            self.assertEqual(client.commits, [])
            self.assertTrue(client.closed)
            before = {str(p): p.read_bytes() for p in Path(root).rglob("*.parquet")}
            replay = Consumer([{TP: [record()]}])
            reports = []
            run(
                root,
                replay,
                STREAMS,
                "cluster-A/topic-epoch-1",
                replay.stop,
                report=lambda line: reports.append(json.loads(line)),
            )
            self.assertEqual(reports[0]["replay"], 1)
            self.assertEqual(
                before, {str(p): p.read_bytes() for p in Path(root).rglob("*.parquet")}
            )
            self.assertEqual(len(replay.commits), 1)

    def test_persistence_failure_never_commits_or_polls_further(self):
        for stage in ("durable", "sync_dir"):
            with self.subTest(stage=stage), tempfile.TemporaryDirectory() as root:
                client = Consumer([{TP: [record()]}, {TP: [record(1)]}])
                with (
                    patch(
                        f"scripts.archive_consumer.{stage}",
                        side_effect=OSError("disk failure"),
                    ),
                    self.assertRaisesRegex(OSError, "disk failure"),
                ):
                    self.execute(root, client)
                self.assertEqual(client.commits, [])
                self.assertTrue(client.closed)
                self.assertEqual(next(client.polls)[TP][0].offset, 1)

    def test_rebalance_during_persistence_blocks_commit_and_restart_replays(self):
        with tempfile.TemporaryDirectory() as root:
            client = Consumer([{TP: [record()]}])

            def revoked(root, messages, ack):
                def after_commit(stage):
                    if stage == "after_commit":
                        client.listener.on_partitions_revoked([TP])
                        client.listener.on_partitions_assigned([TP])

                return consume(root, messages, ack, after_commit)

            with (
                patch("scripts.kafka_archive.consume", revoked),
                self.assertRaises(AssignmentLost),
            ):
                self.execute(root, client)
            self.assertEqual(client.commits, [])
            replay = Consumer([{TP: [record()]}])
            self.assertEqual(self.execute(root, replay), 1)
            with sqlite3.connect(Path(root) / "ledger.sqlite") as db:
                self.assertEqual(
                    db.execute("SELECT count(*) FROM deliveries").fetchone()[0], 1
                )

    def test_idle_rebalance_does_not_commit_positions(self):
        def revoke(client):
            client.listener.on_partitions_revoked([TP])
            return {TP: [record()]}

        with tempfile.TemporaryDirectory() as root:
            client = Consumer([revoke])
            with self.assertRaises(AssignmentLost):
                self.execute(root, client)
            self.assertEqual(client.commits, [])
            self.assertFalse((Path(root) / "ledger.sqlite").exists())

    def test_assignment_loss_without_callback_still_blocks_ack(self):
        with tempfile.TemporaryDirectory() as root:
            client = Consumer([{TP: [record()]}])

            def lose_assignment(root, messages, ack):
                client.owned.clear()
                return consume(root, messages, ack)

            with (
                patch("scripts.kafka_archive.consume", lose_assignment),
                self.assertRaises(AssignmentLost),
            ):
                self.execute(root, client)
            self.assertEqual(client.commits, [])

    def test_bad_polls_fail_before_any_persistence(self):
        unknown = TopicPartition("unmapped", 0)
        for records in (
            {TP: [record(1), record(0)]},
            {TP: [record(0), record(0)]},
            {TP: [record(-1)]},
            {TP: [record(value=None)]},
            {TP: [record(value="decoded")]},
            {TP: [record(tp=TopicPartition("wrong", 0))]},
            {TopicPartition("normalized", 9): [record()]},
            {unknown: [record(tp=unknown)]},
        ):
            with self.subTest(records=records), tempfile.TemporaryDirectory() as root:
                client = Consumer([records], assignment=(TP, unknown))
                with self.assertRaises((ValueError, AssignmentLost)):
                    self.execute(root, client)
                self.assertEqual(client.commits, [])
                self.assertFalse((Path(root) / "ledger.sqlite").exists())

    def test_delivery_identity_namespaces_and_duplicate_events(self):
        ids = {
            delivery_id(*args)
            for args in (
                ("a/b", "c", 0, 0),
                ("a", "b/c", 0, 0),
                ("a/b", "c", 1, 0),
                ("a/b", "c", 0, 1),
            )
        }
        self.assertEqual(len(ids), 4)
        with tempfile.TemporaryDirectory() as root:
            listener = ArchiveRebalanceListener()
            client = Consumer()
            first = archive_poll(
                root, client, {TP: [record()]}, STREAMS, "a", listener, 1000
            )
            other = archive_poll(
                root, client, {TP: [record()]}, STREAMS, "b", listener, 1000
            )
            self.assertEqual(first["stored"], 1)
            self.assertEqual(other["duplicate"], 1)
            with sqlite3.connect(Path(root) / "ledger.sqlite") as db:
                self.assertEqual(
                    db.execute("SELECT count(*) FROM deliveries").fetchone()[0], 2
                )

    def test_identity_conflict_and_corruption_never_commit(self):
        for corruption in (False, True):
            with (
                self.subTest(corruption=corruption),
                tempfile.TemporaryDirectory() as root,
            ):
                self.execute(root, Consumer([{TP: [record()]}]))
                if corruption:
                    next(Path(root).rglob("*.parquet")).write_bytes(b"corrupt")
                client = Consumer([{TP: [record(value=b"changed")]}])
                with self.assertRaises(ValueError):
                    self.execute(root, client)
                self.assertEqual(client.commits, [])

    def test_two_consumers_same_delivery_serialize_without_duplicate_parquet(self):
        with tempfile.TemporaryDirectory() as root:
            barrier = Barrier(2)

            def worker():
                client = Consumer([{TP: [record()]}])
                barrier.wait(timeout=10)
                self.execute(root, client)
                return len(client.commits)

            with ThreadPoolExecutor(max_workers=2) as pool:
                futures = [pool.submit(worker) for _ in range(2)]
                self.assertEqual([f.result(timeout=30) for f in futures], [1, 1])
            self.assertEqual(len(list(Path(root).rglob("*.parquet"))), 1)
            with sqlite3.connect(Path(root) / "ledger.sqlite") as db:
                self.assertEqual(
                    db.execute("SELECT count(*) FROM deliveries").fetchone()[0], 1
                )

    def test_stop_after_poll_leaves_unprocessed_batch_uncommitted(self):
        def stop(client):
            client.stop.set()
            return {TP: [record()]}

        with tempfile.TemporaryDirectory() as root:
            client = Consumer([stop])
            self.assertEqual(self.execute(root, client), 0)
            self.assertEqual(client.commits, [])
            self.assertTrue(client.closed)
            self.assertFalse((Path(root) / "ledger.sqlite").exists())

    def test_concurrent_identity_conflict_cannot_overwrite_or_commit_loser(self):
        with tempfile.TemporaryDirectory() as root:
            barrier = Barrier(2)

            def worker(value):
                client = Consumer([{TP: [record(value=value)]}])
                barrier.wait(timeout=10)
                try:
                    self.execute(root, client)
                except ValueError:
                    return value, len(client.commits), "conflict"
                return value, len(client.commits), "stored"

            with ThreadPoolExecutor(max_workers=2) as pool:
                futures = [pool.submit(worker, value) for value in (RAW, b"{invalid")]
                results = [future.result(timeout=30) for future in futures]
            self.assertEqual(
                sorted((r[1], r[2]) for r in results), [(0, "conflict"), (1, "stored")]
            )
            winner = next(value for value, _, outcome in results if outcome == "stored")
            self.assertEqual(
                next((Path(root) / "bronze").glob("*.bin")).read_bytes(), winner
            )
            with sqlite3.connect(Path(root) / "ledger.sqlite") as db:
                self.assertEqual(
                    db.execute("SELECT count(*) FROM deliveries").fetchone()[0], 1
                )

    def test_stop_during_persistence_finishes_only_current_batch(self):
        with tempfile.TemporaryDirectory() as root:
            client = Consumer([{TP: [record()]}, {TP: [record(1)]}])

            def stop(root, messages, ack):
                client.stop.set()
                return consume(root, messages, ack)

            with patch("scripts.kafka_archive.consume", stop):
                self.assertEqual(self.execute(root, client), 1)
            self.assertEqual(len(client.commits), 1)
            self.assertEqual(next(client.polls)[TP][0].offset, 1)

    def test_poll_failure_closes_without_commit(self):
        def disconnected(client):
            raise RuntimeError("poll disconnected")

        with tempfile.TemporaryDirectory() as root:
            client = Consumer([disconnected])
            with self.assertRaisesRegex(RuntimeError, "poll disconnected"):
                self.execute(root, client)
            self.assertEqual(client.commits, [])
            self.assertTrue(client.closed)

    def test_empty_poll_never_commits_and_finite_run_stops_at_batch_boundary(self):
        with tempfile.TemporaryDirectory() as root:
            client = Consumer([{}, {TP: [record()]}, {TP: [record(1)]}])
            self.assertEqual(self.execute(root, client, max_batches=1), 1)
            self.assertEqual(len(client.commits), 1)
            self.assertEqual(next(client.polls)[TP][0].offset, 1)

    def test_cli_constructs_safe_client_and_restores_signal_handlers(self):
        client = Consumer([{TP: [record()]}])
        args = [
            "--bootstrap-servers",
            "127.0.0.1:19092",
            "--group-id",
            "unit-test",
            "--source-namespace",
            "fixture-cluster/topic-v1",
            "--root",
            "unused",
            "--topic",
            "normalized=telemetry",
            "--max-batches",
            "1",
        ]
        handlers = {s: signal.getsignal(s) for s in (signal.SIGINT, signal.SIGTERM)}
        with (
            patch(
                "scripts.kafka_archive.KafkaConsumer", return_value=client
            ) as factory,
            patch("scripts.kafka_archive.run") as execute,
        ):
            self.assertEqual(main(args), 0)
        config = factory.call_args.kwargs
        self.assertIs(config["enable_auto_commit"], False)
        self.assertIs(config["allow_auto_create_topics"], False)
        self.assertEqual(config["isolation_level"], "read_committed")
        self.assertEqual(config["auto_offset_reset"], "none")
        self.assertEqual(config["api_version"], (3, 7))
        self.assertEqual(execute.call_args.args[2], {"normalized": "telemetry"})
        self.assertEqual(handlers, {s: signal.getsignal(s) for s in handlers})

    def test_cli_invalid_mapping_never_connects(self):
        args = [
            "--bootstrap-servers",
            "127.0.0.1:19092",
            "--group-id",
            "unit-test",
            "--source-namespace",
            "fixture",
            "--root",
            "unused",
        ]
        for extra in (
            ["--topic", "raw=csv"],
            ["--topic", "=telemetry"],
            ["--topic", "a=telemetry", "--topic", "a=prediction"],
            ["--topic", "a=telemetry", "--max-records", "0"],
        ):
            with (
                self.subTest(extra=extra),
                patch("scripts.kafka_archive.KafkaConsumer") as factory,
            ):
                with self.assertRaises(SystemExit) as error:
                    main(args + extra)
                self.assertEqual(error.exception.code, 2)
                factory.assert_not_called()
