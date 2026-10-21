import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from scoring.score_api import create_app
from scripts.failure_harness import Harness, run
from tests.api_client import api_client


class FailureHarnessTests(unittest.IsolatedAsyncioTestCase):
    def test_restart_replay_backpressure_and_durable_counts(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            report = run(root)
            result = report["snapshots"]
            for crash in report["process_crashes"]:
                self.assertEqual(crash["child_exitcode"], 73)
                self.assertTrue(crash["parquet_bytes_preserved"])
                self.assertEqual(crash["before_replay"]["offset_acknowledged"], 0)
                self.assertEqual(crash["after_replay"]["offset_acknowledged"], 1)
                self.assertEqual(crash["after_replay"]["stored_unique"], 1)
                self.assertEqual(
                    crash["before_replay"]["stored_unique"],
                    int(crash["checkpoint"] == "after_commit"),
                )
            self.assertEqual(result["outage"]["pending"], 5)
            self.assertEqual(result["stored_before_ack"]["stored_unique"], 1)
            self.assertEqual(result["stored_before_ack"]["offset_acknowledged"], 0)
            self.assertEqual(result["restart"], result["stored_before_ack"])
            self.assertEqual(result["backpressure_batch"]["pending"], 3)
            self.assertEqual(
                result["recovered"],
                {
                    "sent": 5,
                    "accepted": 3,
                    "rejected": 2,
                    "pending": 0,
                    "stored_unique": 2,
                    "duplicates": 1,
                    "offset_acknowledged": 5,
                },
            )
            self.assertEqual(result["recovered"], result["replay_noop"])
            h = Harness(root / "journal.sqlite")
            self.assertEqual(h.report(), result["recovered"])
            h.close()
            with self.assertRaises(ValueError):
                run(root)

    def test_conflicting_event_is_rejected_and_raw_payloads_survive(self):
        event = json.loads(Path("contracts/examples/valid/telemetry.json").read_text())
        conflict = dict(event, rpm=event["rpm"] + 1)
        raw = [json.dumps(event), json.dumps(conflict), "{bad json"]
        with tempfile.TemporaryDirectory() as tmp:
            h = Harness(Path(tmp) / "journal.sqlite")
            try:
                h.send(raw)
                h.drain()
                report = h.report()
                self.assertEqual(report["accepted"], 1)
                self.assertEqual(report["rejected"], 2)
                self.assertEqual(report["stored_unique"], 1)
                self.assertEqual(report["duplicates"], 0)
                self.assertEqual(report["offset_acknowledged"], 3)
                self.assertEqual(
                    sorted(
                        p.read_bytes() for p in (h.archive / "bronze").glob("*.bin")
                    ),
                    sorted(s.encode() for s in raw),
                )
                self.assertEqual(len(list((h.archive / "rejected").glob("*.json"))), 2)
            finally:
                h.close()

    def test_sink_failure_does_not_ack_or_overwrite_corrupt_archive(self):
        raw = Path("contracts/examples/valid/telemetry.json").read_text()
        with tempfile.TemporaryDirectory() as tmp:
            h = Harness(Path(tmp) / "journal.sqlite")
            try:
                h.send([raw])
                h.drain(crash_after_store=True)
                target = next(h.archive.rglob("*.parquet"))
                target.write_bytes(b"corruption fixture")
                with self.assertRaisesRegex(ValueError, "Committed archive corruption"):
                    h.drain()
                self.assertEqual(h.report()["pending"], 1)
                self.assertEqual(h.report()["offset_acknowledged"], 0)
                self.assertEqual(target.read_bytes(), b"corruption fixture")
            finally:
                h.close()

    def test_delivery_identity_cannot_be_reused_with_different_bytes(self):
        raw = Path("contracts/examples/valid/telemetry.json").read_text()
        with tempfile.TemporaryDirectory() as tmp:
            h = Harness(Path(tmp) / "journal.sqlite")
            try:
                h.send([raw])
                h.drain(crash_after_store=True)
                with h.db:
                    h.db.execute("UPDATE journal SET payload=?", (raw + " ",))
                with self.assertRaisesRegex(ValueError, "Delivery identity reused"):
                    h.drain()
                self.assertEqual(h.report()["pending"], 1)
                with sqlite3.connect(h.archive / "ledger.sqlite") as ledger:
                    self.assertEqual(
                        ledger.execute("SELECT count(*) FROM deliveries").fetchone()[0],
                        1,
                    )
            finally:
                h.close()

    def test_unrelated_output_and_invalid_batch_limit_are_preserved(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "unrelated.txt").write_bytes(b"preserve")
            with self.assertRaises(ValueError):
                run(root)
            self.assertEqual((root / "unrelated.txt").read_bytes(), b"preserve")
            h = Harness(root / "journal.sqlite")
            try:
                for limit in (-1, 0, True, 1.5):
                    with self.subTest(limit=limit), self.assertRaises(ValueError):
                        h.drain(limit=limit)
            finally:
                h.close()

    def test_existing_report_is_preserved_without_creating_journal(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            report = root / "report.json"
            original = b"existing evidence\n"
            report.write_bytes(original)
            with self.assertRaisesRegex(ValueError, "existing evidence"):
                run(root)
            self.assertEqual(report.read_bytes(), original)
            self.assertFalse((root / "journal.sqlite").exists())

    async def test_real_api_fails_closed_for_missing_and_corrupt_manifest(self):
        payload = json.loads(
            Path("contracts/examples/valid/telemetry.json").read_text()
        )
        with tempfile.TemporaryDirectory() as tmp:
            manifest = Path(tmp) / "manifest.json"
            for content in (None, "{invalid json", "{}"):
                with self.subTest(content=content):
                    if content is not None:
                        manifest.write_text(content)
                    async with api_client(create_app(manifest)) as client:
                        self.assertEqual((await client.get("/health")).status_code, 503)
                        response = await client.post("/predict", json=payload)
                        self.assertEqual(response.status_code, 503)
                        self.assertNotIn("failure_score", response.json())

    async def test_missing_and_tampered_model_artifact_before_deserialization(self):
        import hashlib
        from unittest.mock import patch

        import sklearn

        from scoring.scope import SCOPE

        payload = json.loads(
            Path("contracts/examples/valid/telemetry.json").read_text()
        )
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest = {
                **SCOPE,
                "versions": {"sklearn": sklearn.__version__},
                "files": {
                    "rf.pkl": hashlib.sha256(b"expected").hexdigest(),
                    "if.pkl": hashlib.sha256(b"expected").hexdigest(),
                },
            }
            (root / "manifest.json").write_text(json.dumps(manifest))
            for tampered in (False, True):
                with self.subTest(tampered=tampered):
                    if tampered:
                        (root / "rf.pkl").write_bytes(
                            b"corrupted fixture, never pickle"
                        )
                    with patch("scoring.score_api.joblib.load") as load:
                        async with api_client(
                            create_app(root / "manifest.json")
                        ) as client:
                            self.assertEqual(
                                (await client.get("/health")).status_code, 503
                            )
                            self.assertEqual(
                                (
                                    await client.post("/predict", json=payload)
                                ).status_code,
                                503,
                            )
                        load.assert_not_called()
