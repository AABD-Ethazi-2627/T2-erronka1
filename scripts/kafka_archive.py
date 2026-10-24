"""Synchronous Kafka transport for the CG15 durable archive (optional extra)."""

import argparse
import json
import signal
from pathlib import Path
from threading import Event

from kafka import KafkaConsumer
from kafka.consumer.subscription_state import ConsumerRebalanceListener
from kafka.structs import OffsetAndMetadata

from scripts.archive_consumer import consume
from scripts.platform_io import require_power_loss_durability


class AssignmentLost(RuntimeError):
    """Restart from broker offsets rather than using a revoked batch."""


class ArchiveRebalanceListener(ConsumerRebalanceListener):
    """Callbacks may run on the client's IO thread: never call the client here."""

    def __init__(self):
        self.assigned = Event()
        self.lost = Event()

    def on_partitions_revoked(self, partitions):
        if partitions or self.assigned.is_set():
            self.lost.set()

    def on_partitions_assigned(self, partitions):
        if self.assigned.is_set():
            self.lost.set()
        self.assigned.set()

    def check(self):
        if self.lost.is_set():
            raise AssignmentLost("Kafka assignment changed; restart for durable replay")


def delivery_id(namespace, topic, partition, offset):
    """The namespace identifies the source cluster AND topic incarnation(s)."""
    return json.dumps(
        ["kafka", namespace, topic, partition, offset],
        ensure_ascii=True,
        separators=(",", ":"),
    )


def archive_poll(
    root, consumer, records, streams, namespace, listener, timeout_ms, *, sink=None
):
    """Persist the entire fetched prefix before committing explicit next offsets.

    Kafka can omit numeric offsets (compaction, transactions). The prefix is the
    ordered records delivered by poll, not a promise of consecutive integers.
    Caller must stop and close on ANY exception; continuing would skip this poll.
    """
    listener.check()
    messages, offsets = [], {}
    assignment = consumer.assignment()
    for tp, partition_records in records.items():
        if tp not in assignment or tp.topic not in streams:
            raise AssignmentLost("Poll contains an unassigned or unmapped partition")
        previous = -1
        for record in partition_records:
            if (
                record.topic != tp.topic
                or record.partition != tp.partition
                or not isinstance(record.offset, int)
                or record.offset <= previous
                or not isinstance(record.value, bytes)
            ):
                raise ValueError(
                    "Expected ordered Kafka byte values; tombstones unsupported"
                )
            previous = record.offset
            messages.append(
                (
                    delivery_id(namespace, tp.topic, tp.partition, record.offset),
                    streams[tp.topic],
                    record.value,
                )
            )
            offsets[tp] = OffsetAndMetadata(record.offset + 1, "")
    if not messages:
        return None

    def ack():
        listener.check()
        if not offsets.keys() <= consumer.assignment():
            raise AssignmentLost("Kafka partition revoked before commit")
        # Never commit the client's position: it may include prefetched records.
        consumer.commit(offsets=offsets, timeout_ms=timeout_ms)

    return (sink or consume)(root, messages, ack)


def run(
    root,
    consumer,
    streams,
    namespace,
    stop,
    *,
    max_records=100,
    poll_timeout_ms=1000,
    commit_timeout_ms=30000,
    max_batches=None,
    report=print,
    sink=None,
    max_polls=None,
):
    """Own the consumer on one application thread; close without implicit commits."""
    listener = ArchiveRebalanceListener()
    completed = 0
    polls = 0
    try:
        consumer.subscribe(topics=list(streams), listener=listener)
        while not stop.is_set():
            if max_polls is not None and polls >= max_polls:
                break
            listener.check()
            records = consumer.poll(timeout_ms=poll_timeout_ms, max_records=max_records)
            polls += 1
            listener.check()
            if stop.is_set():
                break  # A fetched, unprocessed poll is left for replay.
            result = archive_poll(
                root,
                consumer,
                records,
                streams,
                namespace,
                listener,
                commit_timeout_ms,
                sink=sink,
            )
            if result is not None:
                completed += 1
                report(json.dumps(result, sort_keys=True))
                if max_batches is not None and completed >= max_batches:
                    break
        return completed
    finally:
        consumer.close(autocommit=False, timeout_ms=commit_timeout_ms)


def positive(value):
    parsed = int(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError("must be positive")
    return parsed


def api_version(value):
    try:
        version = tuple(int(part) for part in value.split("."))
    except ValueError as exc:
        raise argparse.ArgumentTypeError("expected Kafka version such as 3.7") from exc
    if len(version) != 2 or version < (2, 0) or any(part < 0 for part in version):
        raise argparse.ArgumentTypeError("expected Kafka major.minor >= 2.0")
    return version


def parser():
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument(
        "--bootstrap-servers",
        required=True,
        help="Explicit broker endpoints; no default/shared broker",
    )
    result.add_argument("--group-id", required=True)
    result.add_argument(
        "--api-version",
        type=api_version,
        default=(3, 7),
        help="Broker protocol major.minor; default 3.7 matches repository Kafka",
    )
    result.add_argument(
        "--source-namespace",
        required=True,
        help="Stable cluster identity + topic incarnation; see CG15 guide",
    )
    result.add_argument(
        "--topic",
        action="append",
        required=True,
        metavar="TOPIC=KIND",
        help="Repeat for telemetry/prediction JSON topics (not raw CSV)",
    )
    result.add_argument(
        "--root",
        type=Path,
        required=True,
        help=(
            "Local archive; POSIX fsync or Windows process recovery "
            "(PLATFORM_SUPPORT.md)"
        ),
    )
    result.add_argument(
        "--offset-reset",
        choices=("none", "earliest"),
        default="none",
        help="Default fails if offsets are missing/expired",
    )
    result.add_argument("--max-records", type=positive, default=100)
    result.add_argument("--poll-timeout-ms", type=positive, default=1000)
    result.add_argument("--max-poll-interval-ms", type=positive, default=300000)
    result.add_argument("--commit-timeout-ms", type=positive, default=30000)
    result.add_argument(
        "--require-power-loss-durability",
        action="store_true",
        help="Fail before connecting on Windows; requires POSIX directory fsync",
    )
    result.add_argument(
        "--max-batches",
        type=positive,
        help="Optional finite run; empty polls do not count",
    )
    return result


def main(argv=None):
    cli = parser()
    args = cli.parse_args(argv)
    streams = {}
    for spec in args.topic:
        topic, sep, kind = spec.partition("=")
        if (
            not sep
            or not topic
            or kind not in ("telemetry", "prediction")
            or topic in streams
        ):
            cli.error("--topic requires a unique TOPIC=telemetry or TOPIC=prediction")
        streams[topic] = kind
    if any(
        not value.strip()
        for value in (args.bootstrap_servers, args.group_id, args.source_namespace)
    ):
        cli.error("broker endpoints, group and namespace must not be blank")
    if args.poll_timeout_ms >= args.max_poll_interval_ms:
        cli.error("poll timeout must be shorter than max poll interval")
    if args.require_power_loss_durability:
        require_power_loss_durability()
    stop = Event()
    handlers = {}
    try:
        for signum in (signal.SIGINT, signal.SIGTERM):
            handlers[signum] = signal.signal(signum, lambda *_: stop.set())
        consumer = KafkaConsumer(
            bootstrap_servers=args.bootstrap_servers,
            api_version=args.api_version,
            group_id=args.group_id,
            client_id="cg15-durable-archive",
            enable_auto_commit=False,
            auto_offset_reset=args.offset_reset,
            allow_auto_create_topics=False,
            isolation_level="read_committed",
            max_poll_records=args.max_records,
            max_poll_interval_ms=args.max_poll_interval_ms,
            request_timeout_ms=args.commit_timeout_ms,
            bootstrap_timeout_ms=args.commit_timeout_ms,
        )
        run(
            args.root,
            consumer,
            streams,
            args.source_namespace,
            stop,
            max_records=args.max_records,
            poll_timeout_ms=args.poll_timeout_ms,
            commit_timeout_ms=args.commit_timeout_ms,
            max_batches=args.max_batches,
        )
        return 0
    finally:
        for signum, handler in handlers.items():
            signal.signal(signum, handler)


if __name__ == "__main__":
    raise SystemExit(main())
