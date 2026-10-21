"""Credential handling and strict batch-name parsing for read-only SMB checks."""

import tempfile
import unittest
from pathlib import Path

from scripts.check_smb_source import (
    SmbConfig,
    list_batch_names,
    read_config,
    smb_command,
)


class SmbSourceTests(unittest.TestCase):
    def test_config_reads_secret_without_exposing_it_in_repr(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / ".env"
            path.write_text(
                "SMB_HOST=192.168.75.222\nSMB_SHARE=cnc-stream\nSMB_USERN"
                + 'AME=lab\nSMB_PASSWORD="private value"\nSMB_TIMEOUT=8\n'
            )
            path.chmod(0o600)
            config = read_config(path)
            self.assertEqual(config.password, "private value")
            self.assertNotIn("private value", repr(config))
            path.chmod(0o644)
            with self.assertRaisesRegex(ValueError, "permissions"):
                read_config(path)

    def test_missing_credentials_and_unsafe_share_are_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / ".env"
            for suffix in [
                "SMB_PASSWORD=\n",
                "SMB_PASSWORD=ok\nSMB_SHARE=cnc-stream;del\n",
            ]:
                path.write_text("SMB_HOST=192.168.75.222\nSMB_USERNAME=lab\n" + suffix)
                path.chmod(0o600)
                with self.assertRaises(ValueError):
                    read_config(path)

    def test_remote_write_commands_are_rejected_before_connecting(self):
        config = SmbConfig("192.0.2.1", "example", "fixture", "not-real")
        for command in [
            "del file.csv",
            "put file.csv",
            "ls; del file.csv",
            "get bad;del sample.csv",
        ]:
            with self.assertRaisesRegex(ValueError, "read-only"):
                smb_command(config, command)

    def test_only_safe_csv_batch_names_are_selected(self):
        listing = """  . D 0 today
  cnc_batch_20261015_080906_00001.csv N 850 today
  cnc_batch_20261015_084306_00069.csv N 848 today
  unrelated.csv N 90 today
  cnc_batch_20261015_080906_00001.csv;del N 850 today
"""
        self.assertEqual(
            list_batch_names(listing),
            [
                "cnc_batch_20261015_080906_00001.csv",
                "cnc_batch_20261015_084306_00069.csv",
            ],
        )
