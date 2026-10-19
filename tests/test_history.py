import tempfile
import unittest
from pathlib import Path

import duckdb

from scripts.build_history import retain


class HistoryTests(unittest.TestCase):
    def test_preserves_bytes_and_collisions_and_is_idempotent(self):
        sample = next(
            Path("docs/requisitos/evidencias/muestras").glob("*20261015_080906*.csv")
        )
        original = sample.read_bytes()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            report = retain([sample], root)
            self.assertEqual(report["rows"], 10)
            bronze = list((root / "bronze").glob("*.csv"))
            self.assertEqual(bronze[0].read_bytes(), original)
            self.assertEqual(retain([sample], root), report)
            with duckdb.connect() as con:
                rows, ids = con.execute(
                    "SELECT count(*), count(DISTINCT record_id) FROM read_parquet(?)",
                    [str(root / "silver/**/*.parquet")],
                ).fetchone()
            self.assertEqual((rows, ids), (10, 10))
            self.assertEqual(len(list((root / "silver").rglob("*.parquet"))), 1)

    def test_invalid_input_does_not_write_partial_history(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "bad.csv"
            source.write_text("timestamp,machine_id\nnot-a-date,CNC-001\n")
            with self.assertRaises(ValueError):
                retain([source], Path(tmp) / "out")
            self.assertFalse((Path(tmp) / "out").exists())
