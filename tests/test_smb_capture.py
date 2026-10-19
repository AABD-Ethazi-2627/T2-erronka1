import tempfile
import unittest
from pathlib import Path

from scripts.capture_smb import publish_snapshot


class CaptureTests(unittest.TestCase):
    def test_publish_complete_bytes_idempotently_and_reject_mutation(self):
        raw = next(
            Path("docs/requisitos/evidencias/muestras").glob("*.csv")
        ).read_bytes()
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "batch.csv"
            self.assertTrue(publish_snapshot(raw, target))
            self.assertEqual(target.read_bytes(), raw)
            self.assertFalse(publish_snapshot(raw, target))
            with self.assertRaises(ValueError):
                publish_snapshot(raw.replace(b"300", b"301"), target)
            self.assertEqual(target.read_bytes(), raw)

    def test_invalid_batch_never_becomes_visible_csv(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "bad.csv"
            with self.assertRaises(ValueError):
                publish_snapshot(b"bad,columns\n1,2\n", target)
            self.assertFalse(target.exists())
            rejected = list((Path(tmp) / "quarantine").glob("*.bin"))
            self.assertEqual(len(rejected), 1)
            self.assertEqual(rejected[0].read_bytes(), b"bad,columns\n1,2\n")
