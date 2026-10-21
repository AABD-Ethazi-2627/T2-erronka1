"""Small persisted-data contracts; never read delivery models or the final set."""

import hashlib
import io
import json
import tempfile
import unittest
import zipfile
from pathlib import Path

import duckdb
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from scripts.audit_cg02 import TRAIN_COLUMNS
from scripts.build_history import retain
from scripts.package_seasonal_v2 import package
from scripts.verify_history import verify


def columnar_frame():
    return pd.DataFrame(
        {
            "record_id": ["a", "a", "b", "c"],
            "machine_id": ["CNC-001", "CNC-001", "CNC-002", "CNC-003"],
            "timestamp": pd.to_datetime(["2026-01-01T00:00:00Z"] * 4, utc=True),
            "rpm": [60.0, 60.0, float("nan"), 90.0],
            "machine_failure": [0, 0, 1, 0],
            "note": ["ñ", "ñ", None, "工具"],
        }
    )


def write_fixture(root):
    """Also used to create inert archives with the previous PyArrow runtime."""
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    frame = columnar_frame()
    frame.to_parquet(root / "frame.parquet", index=False)
    datasets = {}
    for name in ("train", "validation", "evaluation", "stress"):
        path = root / f"{name}.parquet"
        path.write_bytes((root / "frame.parquet").read_bytes())
        datasets[name] = {"sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
    (root / "report.json").write_text(
        json.dumps(
            {
                "scenario": {"fixture_only": True},
                "datasets": datasets,
                "ai4i_source_sha256": "synthetic-fixture-no-ai4i",
                "selection": {"selected_by_validation_ap": "fixture-no-model"},
            }
        )
    )
    package(root)
    source = root / "batch.csv"
    source.write_text(
        ",".join(["timestamp"] + TRAIN_COLUMNS)
        + "\n"
        + "2026-01-01T00:00:00Z,CNC-001,M,300,310,60,10,5,0,0,0,0,0,0\n"
        # Same timestamp and machine, distinct source ordinal: retain both rows.
        + "2026-01-01T00:00:00Z,CNC-001,M,300,310,90,10,5,1,1,0,0,0,0\n"
    )
    retain([source, source], root / "history")


class ColumnarUpgradeContractTests(unittest.TestCase):
    def check_fixture(self, root):
        path = root / "frame.parquet"
        pd.testing.assert_frame_equal(pd.read_parquet(path), columnar_frame())
        self.assertEqual(
            pq.read_schema(path).remove_metadata(),
            pa.schema(
                [
                    ("record_id", pa.string()),
                    ("machine_id", pa.string()),
                    ("timestamp", pa.timestamp("ns", tz="UTC")),
                    ("rpm", pa.float64()),
                    ("machine_failure", pa.int64()),
                    ("note", pa.string()),
                ]
            ),
        )
        with duckdb.connect() as con:
            counts = con.execute(
                "SELECT count(*), count(DISTINCT record_id), count(rpm), "
                "sum(machine_failure) FROM read_parquet(?)",
                [str(path)],
            ).fetchone()
            self.assertEqual(counts, (4, 3, 3, 1))
            restored = con.execute("SELECT * FROM read_parquet(?)", [str(path)]).df()
        # DuckDB represents TIMESTAMPTZ in microseconds, pandas/Arrow in ns.
        restored["timestamp"] = restored.timestamp.astype("datetime64[ns, UTC]")
        pd.testing.assert_frame_equal(restored, columnar_frame())

        history = root / "history"
        self.assertTrue(verify(history))
        before = (history / "manifest.json").read_bytes()
        retain([root / "batch.csv"], history)
        self.assertEqual((history / "manifest.json").read_bytes(), before)
        self.assertEqual(json.loads(before)["rows"], 2)
        self.assertEqual(len(list((history / "silver").rglob("*.parquet"))), 1)

        archive = root / "dataset_bundle.zip"
        original = archive.read_bytes()
        self.assertEqual(package(root), archive)
        self.assertEqual(archive.read_bytes(), original)
        with zipfile.ZipFile(archive) as bundle:
            self.assertIsNone(bundle.testzip())
            for name in ("train", "validation", "evaluation", "stress"):
                data = bundle.read(f"{name}.parquet")
                self.assertEqual(data, (root / f"{name}.parquet").read_bytes())
                pd.testing.assert_frame_equal(
                    pd.read_parquet(io.BytesIO(data)), columnar_frame()
                )

    def test_roundtrip_schema_dedupe_history_and_archive(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write_fixture(root)
            self.check_fixture(root)

    def test_identical_ingest_preserves_an_alternate_parquet_encoding(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write_fixture(root)
            history = root / "history"
            summary = history / "gold/machine_summary.parquet"
            frame = pd.read_parquet(summary)
            # Model a previously verified artifact produced by a different writer.
            frame.to_parquet(summary, index=False, compression=None)
            original = summary.read_bytes()
            manifest_path = history / "manifest.json"
            manifest = json.loads(manifest_path.read_text())
            manifest["files"][str(summary.relative_to(history))] = hashlib.sha256(
                original
            ).hexdigest()
            manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
            before = manifest_path.read_bytes()
            self.assertTrue(verify(history))
            retain([root / "batch.csv"], history)
            self.assertEqual(summary.read_bytes(), original)
            self.assertEqual(manifest_path.read_bytes(), before)

            # A genuinely new batch must still update Gold and the manifest.
            extra = root / "extra.csv"
            extra.write_bytes(
                (root / "batch.csv").read_bytes().replace(b",90,", b",120,")
            )
            report = retain([extra], history)
            self.assertEqual(report["rows"], 4)
            self.assertNotEqual(summary.read_bytes(), original)
            self.assertTrue(verify(history))
