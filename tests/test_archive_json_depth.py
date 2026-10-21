"""Untrusted JSON depth must not bypass durable rejection or stop a batch."""

import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.archive_consumer import consume, digest, durable, sync_dir
from scripts.validate_contracts import validators


def deep_json(depth=1100):
    return b"[" * depth + b"0" + b"]" * depth


def objects(root):
    return {
        str(path.relative_to(root)): path.read_bytes()
        for folder in ("bronze", "rejected", "telemetry")
        for path in (root / folder).rglob("*")
        if path.is_file()
    }


class JsonDepthTests(unittest.TestCase):
    def test_deep_rejection_durable_before_ack_continues_and_replays(self):
        valid = Path("contracts/examples/valid/telemetry.json").read_bytes()
        for depth in (400, 1100, 10000):
            with self.subTest(depth=depth), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                raw = deep_json(depth)
                messages = [("deep", "telemetry", raw), ("valid", "telemetry", valid)]
                synced = []
                stages = []
                acks = []

                def sync(path, synced=synced):
                    sync_dir(path)
                    synced.append(path)

                def ack(root=root, raw=raw, synced=synced, stages=stages, acks=acks):
                    self.assertEqual(stages[-1], "after_commit")
                    self.assertEqual(synced[-1], root)
                    self.assertIn(root / "rejected", synced)
                    with sqlite3.connect(root / "ledger.sqlite") as db:
                        self.assertEqual(
                            dict(db.execute("SELECT id,outcome FROM deliveries")),
                            {"deep": "rejected", "valid": "stored"},
                        )
                        for name, expected in db.execute(
                            "SELECT path,hash FROM objects"
                        ):
                            self.assertEqual(
                                digest((root / name).read_bytes()), expected
                            )
                    self.assertEqual(
                        (root / "bronze" / (digest(b"deep") + ".bin")).read_bytes(), raw
                    )
                    rejection = json.loads(
                        next((root / "rejected").glob("*.json")).read_bytes()
                    )
                    self.assertEqual(rejection["bronze_sha256"], digest(raw))
                    self.assertIn(
                        rejection["reason"], ("ValueError", "ValidationError")
                    )
                    self.assertTrue(rejection["detail"])
                    acks.append(1)

                with patch("scripts.archive_consumer.sync_dir", sync):
                    result = consume(root, messages, ack, stages.append)
                    self.assertEqual((result["rejected"], result["stored"]), (1, 1))
                    before = objects(root)
                    replay = consume(root, messages, ack, stages.append)
                self.assertEqual(replay["replay"], 2)
                self.assertEqual(objects(root), before)
                self.assertEqual(acks, [1, 1])

    def test_rejection_write_failure_aborts_without_ack_then_recovers(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            acks = []

            def fail(path, raw):
                if path.parent.name == "rejected":
                    raise OSError("quarantine disk full")
                durable(path, raw)

            with (
                patch("scripts.archive_consumer.durable", fail),
                self.assertRaisesRegex(OSError, "quarantine disk full"),
            ):
                consume(
                    root, [("deep", "telemetry", deep_json())], lambda: acks.append(1)
                )
            self.assertEqual(acks, [])
            with sqlite3.connect(root / "ledger.sqlite") as db:
                self.assertEqual(
                    db.execute("SELECT count(*) FROM deliveries").fetchone()[0], 0
                )
            result = consume(
                root, [("deep", "telemetry", deep_json())], lambda: acks.append(1)
            )
            self.assertEqual(result["rejected"], 1)
            self.assertEqual(acks, [1])

    def test_deep_rejection_interruption_replays_stable_files(self):
        for stage in ("after_write", "before_commit", "after_commit"):
            with self.subTest(stage=stage), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                acks = []

                def interrupt(current, stage=stage):
                    if current == stage:
                        raise RuntimeError("interrupted")

                message = [("deep", "telemetry", deep_json())]
                with self.assertRaisesRegex(RuntimeError, "interrupted"):
                    consume(root, message, lambda acks=acks: acks.append(1), interrupt)
                self.assertEqual(acks, [])
                before = objects(root)
                self.assertEqual(len(before), 2)
                result = consume(root, message, lambda acks=acks: acks.append(1))
                self.assertEqual(result["replay"], int(stage == "after_commit"))
                self.assertEqual(objects(root), before)
                self.assertEqual(acks, [1])

    def test_recursion_from_schema_validation_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch("scripts.archive_consumer.validators") as factory:
                factory.return_value["telemetry"].validate.side_effect = RecursionError(
                    "schema depth"
                )
                result = consume(tmp, [("schema", "telemetry", b"{}")], lambda: None)
            self.assertEqual(result["rejected"], 1)

    def test_memory_and_unexpected_validation_errors_propagate(self):
        for seam in ("parser", "schema"):
            for error in (MemoryError, RuntimeError):
                with (
                    self.subTest(seam=seam, error=error),
                    tempfile.TemporaryDirectory() as tmp,
                ):
                    acks = []
                    schemas = validators()
                    target = (
                        patch(
                            "scripts.archive_consumer.json.loads",
                            side_effect=error("injected"),
                        )
                        if seam == "parser"
                        else patch.object(type(schemas["telemetry"]), "validate")
                    )
                    with (
                        patch(
                            "scripts.archive_consumer.validators", return_value=schemas
                        ),
                        target as factory,
                    ):
                        if seam == "schema":
                            factory.side_effect = error("injected")
                        with self.assertRaises(error):
                            consume(
                                tmp,
                                [("failure", "telemetry", b"{}")],
                                lambda acks=acks: acks.append(1),
                            )
                    self.assertEqual(acks, [])
                    self.assertFalse((Path(tmp) / "rejected").exists())

    def test_large_shallow_invalid_input_retains_original_bytes(self):
        raw = json.dumps("x" * 131072).encode()
        with tempfile.TemporaryDirectory() as tmp:
            result = consume(tmp, [("large", "telemetry", raw)], lambda: None)
            self.assertEqual(result["rejected"], 1)
            self.assertEqual(
                next((Path(tmp) / "bronze").glob("*.bin")).read_bytes(), raw
            )

    def test_recursion_outside_input_validation_propagates(self):
        valid = Path("contracts/examples/valid/telemetry.json").read_bytes()
        with tempfile.TemporaryDirectory() as tmp:
            acks = []
            with (
                patch(
                    "scripts.archive_consumer.json.dumps",
                    side_effect=RecursionError("internal bug"),
                ),
                self.assertRaisesRegex(RecursionError, "internal bug"),
            ):
                consume(tmp, [("valid", "telemetry", valid)], lambda: acks.append(1))
            self.assertEqual(acks, [])
            self.assertFalse((Path(tmp) / "rejected").exists())
