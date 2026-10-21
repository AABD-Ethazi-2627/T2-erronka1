import json
import os
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import pyarrow.parquet as pq

from scripts.archive_consumer import consume


def batch():
    return [
        (kind, kind, Path(f"contracts/examples/valid/{kind}.json").read_bytes())
        for kind in ("telemetry", "prediction")
    ] + [("bad", "telemetry", b"{bad")]


class ArchiveTests(unittest.TestCase):
    def test_replay_separation_and_reconciliation(self):
        with tempfile.TemporaryDirectory() as tmp:
            ack = []
            self.assertEqual(
                consume(tmp, batch(), lambda: ack.append(1)),
                {"sent": 3, "stored": 2, "rejected": 1, "duplicate": 0, "replay": 0},
            )
            self.assertEqual(consume(tmp, batch(), lambda: ack.append(1))["replay"], 3)
            duplicate = [("new-delivery", "telemetry", batch()[0][2])]
            self.assertEqual(consume(tmp, duplicate, lambda: None)["duplicate"], 1)
            for kind in ("telemetry", "prediction"):
                files = list((Path(tmp) / kind).rglob("*.parquet"))
                self.assertEqual(len(files), 1)
                self.assertEqual(pq.ParquetFile(files[0]).metadata.num_rows, 1)
            self.assertEqual(len(ack), 2)

    def test_process_crash_before_and_after_commit(self):
        for stage in ("after_write", "before_commit", "after_commit"):
            with self.subTest(stage=stage), tempfile.TemporaryDirectory() as tmp:
                code = """
import os, sys
from tests.test_archive_consumer import batch
from scripts.archive_consumer import consume
consume(sys.argv[1], batch(), lambda: open(sys.argv[1]+'/ACK', 'w').close(),
        lambda stage: os._exit(73) if stage == sys.argv[2] else None)
"""
                # tests is not a package: import via explicit local test path.
                code = code.replace(
                    "from tests.test_archive_consumer", "from test_archive_consumer"
                )
                env = dict(
                    os.environ,
                    PYTHONPATH=str(Path("tests").absolute())
                    + os.pathsep
                    + str(Path.cwd()),
                )
                child = subprocess.run(
                    [sys.executable, "-c", code, tmp, stage], check=False, env=env
                )
                self.assertEqual(child.returncode, 73)
                self.assertFalse((Path(tmp) / "ACK").exists())
                result = consume(tmp, batch(), lambda: None)
                self.assertEqual(result["replay"], 3 if stage == "after_commit" else 0)
                with sqlite3.connect(Path(tmp) / "ledger.sqlite") as db:
                    self.assertEqual(
                        db.execute("SELECT count(*) FROM deliveries").fetchone()[0], 3
                    )
                    self.assertEqual(
                        db.execute("SELECT count(*) FROM events").fetchone()[0], 2
                    )
                self.assertEqual(len(list(Path(tmp).rglob("*.parquet"))), 2)

    def test_conflict_and_write_failure_never_ack(self):
        with tempfile.TemporaryDirectory() as tmp:
            consume(tmp, batch(), lambda: None)
            ack = []
            with self.assertRaises(ValueError):
                consume(
                    tmp, [("telemetry", "telemetry", b"changed")], lambda: ack.append(1)
                )
            next((Path(tmp) / "telemetry").rglob("*.parquet")).write_bytes(b"corrupt")
            with self.assertRaises(ValueError):
                consume(
                    tmp, [("new", "telemetry", batch()[0][2])], lambda: ack.append(1)
                )
            self.assertEqual(ack, [])

    def test_event_conflict_quarantined(self):
        with tempfile.TemporaryDirectory() as tmp:
            consume(tmp, batch(), lambda: None)
            obj = json.loads(batch()[0][2])
            obj["rpm"] += 1
            result = consume(
                tmp, [("conflict", "telemetry", json.dumps(obj).encode())], lambda: None
            )
            self.assertEqual(result["rejected"], 1)

    def test_io_failure_and_ack_failure_recovery(self):
        with tempfile.TemporaryDirectory() as tmp:
            ack = []
            with (
                patch(
                    "scripts.archive_consumer.durable", side_effect=OSError("disk full")
                ),
                self.assertRaises(OSError),
            ):
                consume(tmp, batch(), lambda: ack.append(1))
            self.assertEqual(ack, [])

            def failed_ack():
                raise RuntimeError("transport disconnected")

            with self.assertRaises(RuntimeError):
                consume(tmp, batch(), failed_ack)
            self.assertEqual(consume(tmp, batch(), lambda: None)["replay"], 3)
