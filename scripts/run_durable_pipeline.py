"""Bounded opt-in CG14 worker; never starts services or creates Kafka topics."""

import argparse
import asyncio
import json
import math
import signal
import sys
from pathlib import Path
from threading import Event

import httpx

from scripts.durable_pipeline import Pipeline


def positive(value):
    number = int(value)
    if number < 1:
        raise argparse.ArgumentTypeError("must be positive")
    return number


def parser():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--root", required=True, type=Path)
    cli.add_argument("--manifest", required=True, type=Path)
    cli.add_argument("--source-namespace", required=True)
    cli.add_argument(
        "--legacy-source-kind",
        default="cg14-lab-kafka",
        help="Exact original CG14 parser kind",
    )
    cli.add_argument(
        "--source-kind", choices=("smb_csv", "lab_fixture"), default="lab_fixture"
    )
    cli.add_argument(
        "--scoring-url", required=True, help="Exact authorized /predict URL"
    )
    cli.add_argument("--es-url")
    cli.add_argument(
        "--es-index",
        help="Optional required ES prediction destination; fixed concrete index",
    )
    cli.add_argument("--attempts", type=positive, default=3)
    cli.add_argument("--timeout", type=float, default=10)
    mode = cli.add_subparsers(dest="mode", required=True)
    kafka = mode.add_parser("kafka", help="Own source offsets with the PR58 adapter")
    kafka.add_argument("--bootstrap-servers", required=True)
    kafka.add_argument("--group-id", required=True)
    kafka.add_argument("--topic", required=True)
    kafka.add_argument("--api-version", default="3.7")
    kafka.add_argument("--offset-reset", choices=("none", "earliest"), default="none")
    kafka.add_argument("--max-records", type=positive, default=1)
    kafka.add_argument("--max-polls", type=positive, default=10)
    kafka.add_argument("--max-poll-interval-ms", type=positive, default=300000)
    staged = mode.add_parser(
        "stdin", help="One staged CSV + original coordinates; no Kafka ack"
    )
    staged.add_argument("--topic", required=True)
    staged.add_argument("--partition", required=True, type=int)
    staged.add_argument("--offset", required=True, type=int)
    return cli


def main(argv=None):
    cli = parser()
    args = cli.parse_args(argv)
    if not args.manifest.is_file():
        cli.error(
            "Pinned manifest must exist; "
            "no models are generated or loaded by this worker"
        )
    if not math.isfinite(args.timeout) or args.timeout <= 0:
        cli.error("timeout must be positive and finite")
    if args.mode == "stdin" and (args.partition < 0 or args.offset < 0):
        cli.error("original coordinates must be nonnegative")
    # --help needs no Kafka installation; both modes reuse PR58's ID encoding.
    from scripts.kafka_archive import api_version, delivery_id, run

    stop = Event()
    handlers = {}
    with asyncio.Runner() as runner:
        client = httpx.AsyncClient(trust_env=False)
        try:
            pipeline = Pipeline(
                args.root,
                client,
                namespace=args.source_namespace,
                manifest=json.loads(args.manifest.read_text()),
                scoring_url=args.scoring_url,
                source_kind=args.source_kind,
                legacy_source_kind=args.legacy_source_kind,
                es_url=args.es_url,
                es_index=args.es_index,
                attempts=args.attempts,
                timeout=args.timeout,
            )
            if args.mode == "stdin":
                raw = sys.stdin.buffer.read(1048577)
                if len(raw) > 1048576:
                    cli.error(
                        "staged record exceeds 1 MiB; original input must be retained"
                    )
                stats = runner.run(
                    pipeline.consume(
                        [
                            (
                                delivery_id(
                                    args.source_namespace,
                                    args.topic,
                                    args.partition,
                                    args.offset,
                                ),
                                "raw_csv",
                                raw,
                            )
                        ],
                        lambda: None,
                    )
                )
                print(
                    json.dumps(
                        {"transport": "staged-stdin", "source_ack": False, **stats}
                    )
                )
                return 0
            budget = (
                args.max_records
                * args.attempts
                * args.timeout
                * (3 if args.es_url else 1)
            )
            if args.max_poll_interval_ms <= (budget + 60) * 1000:
                cli.error(
                    "max poll interval must exceed HTTP budget plus 60s disk margin"
                )
            from kafka import KafkaConsumer

            for signum in (signal.SIGINT, signal.SIGTERM):
                handlers[signum] = signal.signal(signum, lambda *_: stop.set())
            consumer = KafkaConsumer(
                bootstrap_servers=args.bootstrap_servers,
                group_id=args.group_id,
                api_version=api_version(args.api_version),
                client_id="cg14-durable-pipeline",
                enable_auto_commit=False,
                auto_offset_reset=args.offset_reset,
                allow_auto_create_topics=False,
                isolation_level="read_committed",
                max_poll_records=args.max_records,
                max_poll_interval_ms=args.max_poll_interval_ms,
                request_timeout_ms=30000,
                bootstrap_timeout_ms=30000,
            )

            def sink(root, messages, ack):
                return runner.run(pipeline.consume(messages, ack))

            run(
                args.root,
                consumer,
                {args.topic: "raw_csv"},
                args.source_namespace,
                stop,
                max_records=args.max_records,
                max_polls=args.max_polls,
                sink=sink,
            )
            return 0
        finally:
            runner.run(client.aclose())
            for signum, handler in handlers.items():
                signal.signal(signum, handler)


if __name__ == "__main__":
    raise SystemExit(main())
