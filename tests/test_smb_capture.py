import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.capture_smb import capture_once, publish_snapshot
from scripts.check_smb_source import SmbConfig

SAMPLES = Path("docs/requisitos/evidencias/muestras")
NAME = "cnc_batch_20261015_080906_00001.csv"
CONFIG = SmbConfig("192.0.2.1", "fixture", "fixture", "not-a-secret")


def listing(size, name=NAME):
    return f"  {name} N {size} fixture\n"


class CaptureTests(unittest.TestCase):
    def test_listing_failure_leaves_no_output_and_next_invocation_can_recover(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "watched"
            for status in ("NT_STATUS_LOGON_FAILURE", "NT_STATUS_CONNECTION_REFUSED"):
                with (
                    patch(
                        "scripts.capture_smb.smb_command",
                        side_effect=RuntimeError(status),
                    ),
                    self.assertRaisesRegex(RuntimeError, status),
                ):
                    capture_once(CONFIG, target)
                self.assertFalse(target.exists())
            with patch("scripts.capture_smb.smb_command", return_value=""):
                self.assertEqual(capture_once(CONFIG, target)["captured"], [])

    def test_short_download_of_valid_rows_is_not_published(self):
        raw = (SAMPLES / NAME).read_bytes()
        prefix = b"\n".join(raw.split(b"\n")[:2]) + b"\n"

        def remote(config, command, cwd=None):
            if command == "ls":
                return listing(len(raw))
            (Path(cwd) / "sample.csv").write_bytes(prefix)
            return ""

        with (
            tempfile.TemporaryDirectory() as tmp,
            patch("scripts.capture_smb.smb_command", side_effect=remote),
        ):
            with self.assertRaisesRegex(ValueError, "changed|incomplete"):
                capture_once(CONFIG, tmp)
            self.assertFalse(list(Path(tmp).glob("*.csv")))

    def test_missing_final_newline_never_publishes_a_valid_looking_prefix(self):
        raw = (SAMPLES / NAME).read_bytes().rstrip(b"\n")
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / NAME
            with self.assertRaisesRegex(ValueError, "Invalid SMB batch"):
                publish_snapshot(raw, target)
            self.assertFalse(target.exists())

    def test_remote_grows_or_disappears_during_get(self):
        raw = (SAMPLES / NAME).read_bytes()
        for after in (listing(len(raw) + 1), ""):
            with self.subTest(after=after), tempfile.TemporaryDirectory() as tmp:
                snapshots = iter((listing(len(raw)), after))

                def remote(config, command, cwd=None, snapshots=snapshots):
                    if command == "ls":
                        return next(snapshots)
                    (Path(cwd) / "sample.csv").write_bytes(raw)
                    return ""

                with (
                    patch("scripts.capture_smb.smb_command", side_effect=remote),
                    self.assertRaisesRegex(ValueError, "changed|incomplete"),
                ):
                    capture_once(CONFIG, tmp)
                self.assertFalse(list(Path(tmp).glob("*.csv")))

    def test_failed_read_preserves_previous_capture_and_restart_resumes(self):
        raw = (SAMPLES / NAME).read_bytes()
        second = "cnc_batch_20261015_084606_00075.csv"
        raw_second = (SAMPLES / second).read_bytes()
        failed = True
        commands = []

        def remote(config, command, cwd=None):
            commands.append(command)
            if command == "ls":
                return listing(len(raw)) + listing(len(raw_second), second)
            if second in command:
                if failed:
                    (Path(cwd) / "sample.csv").write_bytes(raw_second[:200])
                    raise RuntimeError("SMB operation failed: NT_STATUS_IO_TIMEOUT")
                content = raw_second
            else:
                content = raw
            (Path(cwd) / "sample.csv").write_bytes(content)
            return ""

        with (
            tempfile.TemporaryDirectory() as tmp,
            patch("scripts.capture_smb.smb_command", side_effect=remote),
        ):
            with self.assertRaisesRegex(RuntimeError, "NT_STATUS_IO_TIMEOUT"):
                capture_once(CONFIG, tmp)
            self.assertEqual((Path(tmp) / NAME).read_bytes(), raw)
            self.assertFalse((Path(tmp) / second).exists())
            failed = False
            report = capture_once(CONFIG, tmp)
            self.assertEqual([r["filename"] for r in report["captured"]], [second])
            self.assertEqual(report["remaining_at_listing"], 0)
            self.assertEqual((Path(tmp) / second).read_bytes(), raw_second)
            before = list(commands)
            self.assertFalse(capture_once(CONFIG, tmp)["captured"])
            self.assertEqual(commands[len(before) :], ["ls"])

    def test_link_failure_exposes_no_csv_and_replay_succeeds(self):
        raw = (SAMPLES / NAME).read_bytes()
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / NAME
            with (
                patch("scripts.capture_smb.os.link", side_effect=OSError("disk")),
                self.assertRaises(OSError),
            ):
                publish_snapshot(raw, target)
            self.assertFalse(list(Path(tmp).iterdir()))
            self.assertTrue(publish_snapshot(raw, target))
            self.assertEqual(target.read_bytes(), raw)

    def test_validation_failures_preserve_raw_bytes_outside_watched_glob(self):
        raw = (SAMPLES / NAME).read_bytes()
        cases = [
            raw.split(b"\n")[0] + b"\n",
            raw[:180],
            b"\xef\xbb\xbf" + raw,
            raw.replace(b"CNC-049", b'"CNC-049"'),
            raw.replace(b"300.5", b"NaN", 1),
        ]
        with tempfile.TemporaryDirectory() as tmp:
            for index, invalid in enumerate(cases):
                with self.subTest(raw=invalid[:12]):
                    target = Path(tmp) / f"case-{index}" / NAME
                    with self.assertRaisesRegex(ValueError, "Invalid SMB batch"):
                        publish_snapshot(invalid, target)
                    self.assertFalse(target.exists())
            self.assertEqual(
                {p.read_bytes() for p in Path(tmp).glob("*/quarantine/*.bin")},
                set(cases),
            )

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
                publish_snapshot(raw + b"\n", target)
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
