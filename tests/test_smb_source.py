"""Credential handling and strict batch-name parsing for read-only SMB checks."""

import os
import subprocess
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.check_smb_source import (
    SmbConfig,
    list_batch_names,
    list_batch_sizes,
    read_config,
    smb_command,
)
from scripts.private_files import open_private_text, private_text_file


class SmbSourceTests(unittest.TestCase):
    def test_listing_sizes_ignore_partial_names_and_reject_conflicting_sizes(self):
        name = "cnc_batch_20261015_080906_00001.csv"
        self.assertEqual(
            list_batch_sizes(f"  {name} N 850 fixture\n  {name}.part N 100 fixture\n"),
            {name: 850},
        )
        with self.assertRaisesRegex(ValueError, "conflicting"):
            list_batch_sizes(f"  {name} N 850 fixture\n  {name} N 200 fixture\n")

    def test_connection_authentication_and_read_statuses_fail_without_secrets(self):
        config = SmbConfig("192.0.2.1", "fixture", "private-user", "private-password")
        for status in (
            "NT_STATUS_CONNECTION_REFUSED",
            "NT_STATUS_LOGON_FAILURE",
            "NT_STATUS_ACCESS_DENIED",
            "NT_STATUS_IO_TIMEOUT",
        ):
            for returncode in (0, 1):
                with self.subTest(status=status, code=returncode):
                    auth_paths = []

                    def process(
                        args,
                        status=status,
                        returncode=returncode,
                        auth_paths=auth_paths,
                        **kwargs,
                    ):
                        self.assertNotIn(config.username, args)
                        self.assertNotIn(config.password, args)
                        auth = Path(args[args.index("-A") + 1])
                        auth_paths.append(auth)
                        with open_private_text(auth) as handle:
                            self.assertIn(config.password, handle.read())
                        self.assertEqual(args[args.index("-s") + 1], os.devnull)
                        self.assertFalse(kwargs["check"])
                        self.assertEqual(kwargs["timeout"], config.timeout + 5)
                        return subprocess.CompletedProcess(
                            args, returncode, config.username, status + config.password
                        )

                    with (
                        patch(
                            "scripts.check_smb_source.subprocess.run",
                            side_effect=process,
                        ),
                        self.assertRaises(RuntimeError) as caught,
                    ):
                        smb_command(config, "ls")
                    self.assertIn(status, str(caught.exception))
                    self.assertNotIn(config.username, str(caught.exception))
                    self.assertNotIn(config.password, str(caught.exception))
                    self.assertTrue(auth_paths)
                    self.assertTrue(all(not p.exists() for p in auth_paths))

    def test_timeout_cleans_auth_and_withholds_subprocess_output(self):
        config = SmbConfig("192.0.2.1", "fixture", "private-user", "private-password")
        auth_paths = []

        def timeout(args, **kwargs):
            auth_paths.append(Path(args[args.index("-A") + 1]))
            raise subprocess.TimeoutExpired(args, kwargs["timeout"], config.password)

        with (
            patch("scripts.check_smb_source.subprocess.run", side_effect=timeout),
            self.assertRaisesRegex(RuntimeError, "timed out") as caught,
        ):
            smb_command(config, "ls")
        self.assertNotIn(config.password, str(caught.exception))
        self.assertTrue(all(not p.exists() for p in auth_paths))

    def test_config_reads_secret_without_exposing_it_in_repr(self):
        with private_text_file(
            "SMB_HOST=192.168.75.222\nSMB_SHARE=cnc-stream\nSMB_USERN"
            + 'AME=lab\nSMB_PASSWORD="private value"\nSMB_TIMEOUT=8\n'
        ) as path:
            config = read_config(path)
            self.assertEqual(config.password, "private value")
            self.assertNotIn("private value", repr(config))

    def test_missing_credentials_and_unsafe_share_are_rejected(self):
        for suffix in [
            "SMB_PASSWORD=\n",
            "SMB_PASSWORD=ok\nSMB_SHARE=cnc-stream;del\n",
        ]:
            with (
                private_text_file(
                    "SMB_HOST=192.168.75.222\nSMB_USERNAME=lab\n" + suffix
                ) as path,
                self.assertRaises(ValueError),
            ):
                read_config(path)

    def test_auth_is_readable_by_real_child_and_cleaned_after_success(self):
        config = SmbConfig("192.0.2.1", "fixture", "private-user", "private-password")
        auth_paths = []
        run_child = subprocess.run

        def process(args, **kwargs):
            auth = Path(args[args.index("-A") + 1])
            auth_paths.append(auth)
            self.assertEqual(args[args.index("-s") + 1], os.devnull)
            child = run_child(
                [
                    sys.executable,
                    "-B",
                    "-c",
                    (
                        "import pathlib,sys; sys.stdout.buffer.write("
                        "pathlib.Path(sys.argv[1]).read_bytes())"
                    ),
                    str(auth),
                ],
                check=True,
                capture_output=True,
                text=True,
                timeout=15,
            )
            self.assertEqual(
                child.stdout,
                f"username = {config.username}\npassword = {config.password}\n",
            )
            return subprocess.CompletedProcess(args, 0, "listing", "")

        with patch("scripts.check_smb_source.subprocess.run", side_effect=process):
            self.assertEqual(smb_command(config, "ls"), "listing")
        self.assertTrue(auth_paths)
        self.assertTrue(
            all(not p.exists() and not p.parent.exists() for p in auth_paths)
        )

    def test_launch_failure_cleans_auth(self):
        config = SmbConfig("192.0.2.1", "fixture", "private-user", "private-password")
        auth_paths = []

        def fail(args, **kwargs):
            auth_paths.append(Path(args[args.index("-A") + 1]))
            raise FileNotFoundError("smbclient unavailable")

        with (
            patch("scripts.check_smb_source.subprocess.run", side_effect=fail),
            self.assertRaises(FileNotFoundError),
        ):
            smb_command(config, "ls")
        self.assertTrue(auth_paths)
        self.assertTrue(
            all(not p.exists() and not p.parent.exists() for p in auth_paths)
        )

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
