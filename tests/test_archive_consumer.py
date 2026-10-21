import hashlib
import json
import os
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import pyarrow as pa
import pyarrow.parquet as pq

from scripts.archive_consumer import consume, mkdir, sync_dir


def batch():
    return [
        (kind, kind, Path(f"contracts/examples/valid/{kind}.json").read_bytes())
        for kind in ("telemetry", "prediction")
    ] + [("bad", "telemetry", b"{bad")]


class ArchiveTests(unittest.TestCase):
    def test_duplicate_preserves_verified_alternate_parquet_encoding(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            consume(root, batch(), lambda: None)
            target = next((root / "telemetry").rglob("*.parquet"))
            pq.write_table(pq.ParquetFile(target).read(), target, compression=None)
            original = target.read_bytes()
            # Model an intact archive committed by a different Parquet writer.
            with sqlite3.connect(root / "ledger.sqlite") as db:
                db.execute(
                    "UPDATE objects SET hash=? WHERE path=?",
                    (
                        hashlib.sha256(original).hexdigest(),
                        str(target.relative_to(root)),
                    ),
                )
            ack = []
            result = consume(
                root,
                [("new-delivery", "telemetry", batch()[0][2])],
                lambda: ack.append(1),
            )
            self.assertEqual(result["duplicate"], 1)
            self.assertEqual(ack, [1])
            self.assertEqual(target.read_bytes(), original)

    def test_orphan_alternate_encoding_reconciles_before_ack(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)

            def interrupt(stage):
                if stage == "before_commit":
                    raise RuntimeError("interrupted before commit")

            ack = []
            with self.assertRaisesRegex(RuntimeError, "before commit"):
                consume(root, batch()[:1], lambda: ack.append(1), interrupt)
            self.assertEqual(ack, [])
            target = next((root / "telemetry").rglob("*.parquet"))
            pq.write_table(pq.ParquetFile(target).read(), target, compression=None)
            original = target.read_bytes()
            result = consume(root, batch()[:1], lambda: ack.append(1))
            self.assertEqual(result["stored"], 1)
            self.assertEqual(ack, [1])
            self.assertEqual(target.read_bytes(), original)
            with sqlite3.connect(root / "ledger.sqlite") as db:
                self.assertEqual(
                    db.execute(
                        "SELECT hash FROM objects WHERE path=?",
                        (str(target.relative_to(root)),),
                    ).fetchone()[0],
                    hashlib.sha256(original).hexdigest(),
                )

    def test_orphan_content_or_schema_conflict_never_ack(self):
        for field in ("payload_json", "extra_column"):
            with self.subTest(field=field), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)

                def interrupt(stage):
                    if stage == "before_commit":
                        raise RuntimeError("interrupted")

                with self.assertRaisesRegex(RuntimeError, "interrupted"):
                    consume(root, batch()[:1], lambda: None, interrupt)
                target = next((root / "telemetry").rglob("*.parquet"))
                table = pq.ParquetFile(target).read()
                row = table.to_pylist()[0]
                row[field] = "changed"
                pq.write_table(pa.Table.from_pylist([row]), target)
                original = target.read_bytes()
                ack = []
                with self.assertRaises(ValueError):
                    consume(root, batch()[:1], lambda ack=ack: ack.append(1))
                self.assertEqual(ack, [])
                self.assertEqual(target.read_bytes(), original)
                with sqlite3.connect(root / "ledger.sqlite") as db:
                    self.assertEqual(
                        db.execute("SELECT count(*) FROM deliveries").fetchone()[0], 0
                    )

    def test_restart_repairs_existing_directory_links_before_ack(self):
        for interrupted in ("ancestor", "root", "bronze"):
            with (
                self.subTest(interrupted=interrupted),
                tempfile.TemporaryDirectory() as tmp,
            ):
                root = Path(tmp) / "ancestor" / "archive"
                target = {
                    "ancestor": root.parent,
                    "root": root,
                    "bronze": root / "bronze",
                }[interrupted]

                def interrupt_after_mkdir(
                    path, *args, original_mkdir=Path.mkdir, target=target, **kwargs
                ):
                    original_mkdir(path, *args, **kwargs)
                    if path == target:
                        raise OSError("interrupted before parent fsync")

                with (
                    patch.object(Path, "mkdir", interrupt_after_mkdir),
                    self.assertRaisesRegex(OSError, "before parent fsync"),
                ):
                    mkdir(target)
                self.assertTrue(target.is_dir())
                synced = []

                def record_sync(path, synced=synced):
                    sync_dir(path)
                    synced.append(path)

                def ack(target=target, root=root, synced=synced):
                    self.assertIn(target.parent, synced)
                    self.assertIn(root.parent.parent, synced)

                with patch("scripts.archive_consumer.sync_dir", record_sync):
                    consume(root, [("bad", "telemetry", b"{bad")], ack)

    def test_recovery_parent_sync_failure_prevents_ack(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "archive"
            root.mkdir()
            ack = []

            def fail_parent(path):
                if path == root.parent:
                    raise OSError("parent fsync failed")
                sync_dir(path)

            with (
                patch("scripts.archive_consumer.sync_dir", fail_parent),
                self.assertRaisesRegex(OSError, "parent fsync failed"),
            ):
                consume(root, [("bad", "telemetry", b"{bad")], lambda: ack.append(1))
            self.assertEqual(ack, [])

    def test_mkdir_path_boundaries(self):
        with patch("scripts.archive_consumer.sync_dir") as sync:
            mkdir(Path("/"))
            sync.assert_not_called()
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            (base / "real").mkdir()
            (base / "alias").symlink_to(base / "real", target_is_directory=True)
            with patch("scripts.archive_consumer.sync_dir", wraps=sync_dir) as sync:
                mkdir(base / "alias" / ".." / "real" / "child")
            self.assertTrue((base / "real" / "child").is_dir())
            self.assertIn(unittest.mock.call(base / "real"), sync.call_args_list)
            self.assertIn(unittest.mock.call(base), sync.call_args_list)

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
