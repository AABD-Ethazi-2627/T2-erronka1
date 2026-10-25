"""Offline publication/key seam; never a Filebeat registry or Kafka test."""

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.capture_smb import publish_snapshot
from scripts.smb_filebeat_fixture import expected_records, prepare


class FilebeatSeamTests(unittest.TestCase):
    def test_fixture_origin_row_counts_sizes_and_capture_boundaries(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest = prepare(root / "fixture")
            self.assertEqual(
                manifest["source_sha256"],
                "2669b1cb0e5a70d7e7b676cf8f9b81b59bb22ac34db747398450388dc7e10dc3",
            )
            for name, fixture in manifest["fixtures"].items():
                with self.subTest(name=name):
                    raw = (root / "fixture" / name).read_bytes()
                    target = root / "watched" / name
                    if fixture["capture_accepts"]:
                        self.assertTrue(publish_snapshot(raw, target))
                        self.assertEqual(target.read_bytes(), raw)
                    else:
                        with self.assertRaises(ValueError):
                            publish_snapshot(raw, target)
                        self.assertFalse(target.exists())
            fixtures = manifest["fixtures"]
            self.assertEqual(len(fixtures["ten_rows.csv"]["expected_records"]), 10)
            self.assertEqual(len(fixtures["one_row.csv"]["expected_records"]), 1)
            self.assertLess(fixtures["ten_rows.csv"]["bytes"], 1024)
            self.assertGreater(fixtures["tiny_synthetic.csv"]["bytes"], 164)
            self.assertLess(fixtures["tiny_synthetic.csv"]["bytes"], 228)
            with self.assertRaises(FileExistsError):
                prepare(root / "fixture")

    def test_publication_is_complete_at_link_and_rename_replay_keep_expected_keys(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest = prepare(root / "fixture")
            raw = (root / "fixture/ten_rows.csv").read_bytes()
            target = root / "watched/original.csv"
            actual_link = os.link
            checked = []

            def link(stage, destination):
                self.assertFalse(list(target.parent.glob("*.csv")))
                self.assertEqual(Path(stage).read_bytes(), raw)
                checked.append(True)
                actual_link(stage, destination)

            with patch("scripts.capture_smb.os.link", side_effect=link):
                self.assertTrue(publish_snapshot(raw, target))
            self.assertEqual(checked, [True])
            expected = manifest["fixtures"]["ten_rows.csv"]["expected_records"]
            renamed = target.with_name("renamed.csv")
            target.rename(renamed)
            self.assertEqual(expected_records(renamed.read_bytes()), expected)
            self.assertTrue(publish_snapshot(raw, target))
            self.assertEqual(expected_records(target.read_bytes()), expected)
            self.assertFalse(publish_snapshot(raw, target))
            self.assertEqual(len({record["key"] for record in expected}), 10)
            self.assertTrue(
                all(not r["message"].startswith("timestamp,") for r in expected)
            )
            self.assertTrue(expected[0]["key"].endswith(":164"))

    def test_active_config_retains_version_identity_and_raw_key_contract(self):
        config = Path("filebeat/filebeat.yml").read_text()
        compose = Path("docker-compose.yml").read_text()
        dockerfile = Path("deploy/images/filebeat.Dockerfile").read_text()
        self.assertIn("dockerfile: deploy/images/filebeat.Dockerfile", compose)
        self.assertIn("docker.elastic.co/beats/filebeat-wolfi:9.5.5@sha256:", dockerfile)
        self.assertIn("filebeat-data:/usr/share/filebeat/data", compose)
        self.assertIn("/mnt/cnc-smb:ro", compose)
        self.assertEqual(config.count("prospector.scanner.fingerprint.offset: 164"), 2)
        self.assertEqual(config.count("prospector.scanner.fingerprint.length: 64"), 2)
        self.assertEqual(config.count("file_identity.fingerprint: ~"), 2)
        self.assertEqual(config.count("exclude_lines: ['^timestamp,']"), 2)
        self.assertEqual(config.count("clean_removed: false"), 2)
        self.assertIn("fields: [message]", config)
        self.assertIn("method: sha256", config)
        self.assertIn("key: '%{[@metadata.cnc_line_sha256]}:%{[log.offset]}'", config)
        self.assertIn("string: '%{[message]}'", config)
        self.assertIn("topic: cnc-sensors-smb-v1", config)
