import tempfile
import unittest
from pathlib import Path

from scripts.build_history import retain
from scripts.verify_history import verify


class RecoveryTests(unittest.TestCase):
    def test_detects_changed_raw_bytes(self):
        source = next(Path("docs/requisitos/evidencias/muestras").glob("*.csv"))
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            retain([source], root)
            self.assertTrue(verify(root))
            raw = next((root / "bronze").glob("*.csv"))
            raw.write_bytes(raw.read_bytes() + b"\n")
            self.assertFalse(verify(root))
