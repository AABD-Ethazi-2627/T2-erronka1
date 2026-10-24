"""CG02 audit regressions: preserve input, disclose bad data and avoid invented time."""

import csv
import hashlib
import json
import tempfile
import unittest
from pathlib import Path, PurePosixPath, PureWindowsPath
from unittest.mock import patch

from scripts.audit_cg02 import (
    TRAIN_COLUMNS,
    audit_csv,
    build_inventory,
    compare_signatures,
)

ROOT = Path(__file__).resolve().parents[1]


class AuditTests(unittest.TestCase):
    def test_quality_and_label_disagreements_are_measured_without_repairs(self):
        first = [
            "CNC-001",
            "L",
            "300",
            "310",
            "1500",
            "40",
            "100",
            "1",
            "0",
            "0",
            "0",
            "0",
            "0",
        ]
        second = [
            "CNC-002",
            "M",
            "",
            "310",
            "1500",
            "nan",
            "200",
            "0",
            "0",
            "0",
            "0",
            "0",
            "1",
        ]
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "training.csv"
            with path.open("w", newline="") as f:
                writer = csv.writer(f)
                writer.writerow(TRAIN_COLUMNS)
                writer.writerows([first, second, first])
            original = path.read_bytes()
            r = audit_csv(path, "training")
            self.assertEqual(r["rows"], 3)
            self.assertEqual(r["duplicate_rows"], 1)
            self.assertEqual(r["missing"]["air_temp_K"], 1)
            self.assertEqual(r["invalid_numeric"]["torque_Nm"], 1)
            self.assertEqual(r["failure_without_subtype"], 2)
            self.assertEqual(r["subtype_without_failure"], 1)
            self.assertIsNone(r["time"])
            self.assertEqual(path.read_bytes(), original)
            self.assertEqual(r["sha256"], hashlib.sha256(original).hexdigest())

    def test_same_machine_and_time_can_have_conflicting_sensor_states(self):
        rows = [
            [
                "2026-10-16T06:00:00Z",
                "CNC-001",
                "L",
                "300",
                "310",
                "1500",
                "40",
                "100",
                "0",
                "0",
                "0",
                "0",
                "0",
                "0",
            ],
            [
                "2026-10-16T06:00:00Z",
                "CNC-001",
                "L",
                "300",
                "310",
                "1500",
                "41",
                "100",
                "0",
                "0",
                "0",
                "0",
                "0",
                "0",
            ],
        ]
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "batch.csv"
            with path.open("w", newline="") as f:
                writer = csv.writer(f)
                writer.writerow(["timestamp"] + TRAIN_COLUMNS)
                writer.writerows(rows)
            r = audit_csv(path, "batch")
            self.assertEqual(r["time"]["duplicate_machine_timestamp_rows"], 1)
            self.assertEqual(r["time"]["conflicting_machine_timestamp_groups"], 1)
            self.assertEqual(r["duplicate_rows"], 0)

    def test_impossible_or_non_utc_dates_are_not_accepted_as_coverage(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "batch.csv"
            row = [
                "CNC-001",
                "L",
                "300",
                "310",
                "1500",
                "40",
                "100",
                "0",
                "0",
                "0",
                "0",
                "0",
                "0",
            ]
            with path.open("w", newline="") as f:
                writer = csv.writer(f)
                writer.writerow(["timestamp"] + TRAIN_COLUMNS)
                for ts in ["2026-02-30T06:00:00Z", "2026-10-16T06:00:00+02:00"]:
                    writer.writerow([ts] + row)
            r = audit_csv(path, "batch")
            self.assertEqual(r["time"]["invalid_or_non_utc_rows"], 2)
            self.assertIsNone(r["time"]["min"])

    def test_overlap_ignores_event_time_and_machine_assignment(self):
        row = dict(
            zip(
                TRAIN_COLUMNS,
                [
                    "CNC-001",
                    "L",
                    "300",
                    "310",
                    "1500",
                    "40",
                    "100",
                    "0",
                    "0",
                    "0",
                    "0",
                    "0",
                    "0",
                ],
            )
        )
        first = {
            **row,
            "machine_id": "CNC-002",
            "timestamp": "2026-10-15T00:00:00Z",
            "air_temp_K": "300.0",
        }
        second = {**first, "timestamp": "2026-10-16T00:00:00Z"}
        third = {**first, "torque_Nm": "41"}
        result = compare_signatures([row], [first, second, third])
        self.assertEqual(result["distinct_sensor_label_signatures"], 2)
        self.assertEqual(result["repeated_rows_beyond_first_signature"], 1)
        self.assertEqual(result["rows_matching_training_signature"], 2)

    def test_unexpected_header_fails_explicitly(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "wrong.csv"
            path.write_text("x,y\n1,2\n")
            with self.assertRaisesRegex(ValueError, "columns"):
                audit_csv(path, "training")

    def test_frozen_evidence_keeps_training_and_operational_sources_separate(self):
        r = build_inventory(ROOT)
        self.assertEqual(r["training"]["rows"], 8000)
        self.assertEqual(
            r["training"]["label_counts"]["machine_failure"], {"0": 7729, "1": 271}
        )
        self.assertEqual(len(r["batches"]), 4)
        self.assertEqual(sum(x["rows"] for x in r["batches"]), 40)
        self.assertEqual(r["decision"]["forecast_24h"], "not_validated")

    def test_frozen_inventory_matches_saved_measurements(self):
        expected = json.loads((ROOT / "docs/cg02/inventory.json").read_text())
        self.assertEqual(build_inventory(ROOT), expected)

    def test_inventory_paths_are_portable_for_both_path_flavours(self):
        expected = json.loads((ROOT / "docs/cg02/inventory.json").read_text())
        relative_to = type(ROOT).relative_to
        for flavour in (PurePosixPath, PureWindowsPath):
            with self.subTest(flavour=flavour.__name__):
                # Keep real file I/O; exercise Windows separators even on Linux.
                def relative_path(path, *other, flavour=flavour):
                    return flavour(relative_to(path, *other))

                with patch.object(type(ROOT), "relative_to", relative_path):
                    actual = build_inventory(ROOT)
                self.assertEqual(actual, expected)


if __name__ == "__main__":
    unittest.main()
