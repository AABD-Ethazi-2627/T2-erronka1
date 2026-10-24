"""UTC instants, units and NULLs across the DuckDB 2.0 Arrow boundary."""

import tempfile
import unittest
from pathlib import Path

import duckdb
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from scripts.duckdb_output import to_pandas_utc


class DuckDBOutputTests(unittest.TestCase):
    def test_parquet_ns_offsets_dst_nulls_and_aggregates(self):
        instants = pd.to_datetime(
            [
                "2026-03-29T01:59:59.123456789+01:00",
                "2026-03-29T03:00:00.000000001+02:00",
                "2026-10-25T02:59:59.999999999+02:00",
                "2026-10-25T02:00:00.000000001+01:00",
                "1969-12-31T23:59:59.999999999Z",
                None,
            ],
            utc=True,
            format="mixed",
        )
        expected = pd.DataFrame(
            {"instant": instants, "value": [1.0, 2.0, 3.0, 4.0, 5.0, None]}
        )
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "UTC ñ 工具.parquet"
            expected.to_parquet(path, index=False)
            self.assertEqual(
                pq.read_schema(path).field("instant").type, pa.timestamp("ns", tz="UTC")
            )
            with duckdb.connect() as con:
                for zone in ("UTC", "Europe/Madrid", "America/New_York"):
                    with self.subTest(zone=zone):
                        con.execute(f"SET TimeZone='{zone}'")
                        relation = con.sql(
                            "SELECT * FROM read_parquet(?)", params=[str(path)]
                        )
                        self.assertEqual(str(relation.types[0]), "TIMESTAMPTZ_NS")
                        arrow = relation.to_arrow_table()
                        self.assertEqual(arrow.schema.field("instant").type.unit, "ns")
                        self.assertIsNotNone(arrow.schema.field("instant").type.tz)
                        self.assertEqual(
                            arrow.column("instant").cast(pa.int64()).to_pylist(),
                            [None if pd.isna(t) else t.value for t in instants],
                        )
                        restored = to_pandas_utc(relation)
                        self.assertEqual(
                            str(restored.instant.dtype), "datetime64[ns, UTC]"
                        )
                        self.assertTrue(pd.isna(restored.instant.iloc[-1]))
                        pd.testing.assert_frame_equal(restored, expected)
                        aggregates = to_pandas_utc(
                            con.sql(
                                "SELECT count(*) n, count(instant) present, "
                                "sum(value) total, avg(value) mean "
                                "FROM read_parquet(?)",
                                params=[str(path)],
                            )
                        )
                        self.assertEqual(aggregates.iloc[0].tolist(), [6, 5, 15, 3])
                        self.assertEqual(
                            aggregates.columns.tolist(),
                            ["n", "present", "total", "mean"],
                        )
                        self.assertEqual(
                            aggregates.dtypes.astype(str).tolist(),
                            ["int64", "int64", "float64", "float64"],
                        )

    def test_units_aware_microseconds_and_naive_nanoseconds(self):
        with duckdb.connect() as con:
            con.execute("SET TimeZone='Europe/Madrid'")
            relation = con.sql(
                "SELECT TIMESTAMPTZ '2026-01-01 01:00:00.123456+01' aware, "
                "TIMESTAMP_NS '2026-01-01 00:00:00.123456789' naive, "
                "CAST(NULL AS TIMESTAMPTZ_NS) missing"
            )
            frame = to_pandas_utc(relation)
            self.assertEqual(str(frame.aware.dtype), "datetime64[us, UTC]")
            self.assertEqual(
                frame.aware.iloc[0], pd.Timestamp("2026-01-01T00:00:00.123456Z")
            )
            self.assertEqual(str(frame.naive.dtype), "datetime64[ns]")
            self.assertEqual(
                frame.naive.iloc[0].value,
                pd.Timestamp("2026-01-01T00:00:00.123456789").value,
            )
            self.assertEqual(str(frame.missing.dtype), "datetime64[ns, UTC]")
            self.assertTrue(pd.isna(frame.missing.iloc[0]))

    def test_empty_result_retains_temporal_types(self):
        with duckdb.connect() as con:
            frame = to_pandas_utc(
                con.sql(
                    "SELECT CAST(NULL AS TIMESTAMPTZ_NS) instant, "
                    "CAST(NULL AS TIMESTAMP_NS) naive WHERE false"
                )
            )
            self.assertTrue(frame.empty)
            self.assertEqual(str(frame.instant.dtype), "datetime64[ns, UTC]")
            self.assertEqual(str(frame.naive.dtype), "datetime64[ns]")
