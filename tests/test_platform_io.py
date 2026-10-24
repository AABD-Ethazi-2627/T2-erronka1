"""Execute native filesystem/lock/RSS boundaries, including process death."""

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from scripts.archive_consumer import consume, durable
from scripts.platform_io import (
    durability_profile,
    exclusive_lock,
    peak_rss_kib,
    require_power_loss_durability,
    sync_directory,
)


class PlatformIoTests(unittest.TestCase):
    def test_profile_and_power_loss_requirement_are_explicit(self):
        expected = "windows-process-recovery" if os.name == "nt" else "posix-fsync"
        self.assertEqual(durability_profile(), expected)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "archive"
            acks = []
            if os.name == "nt":
                with self.assertRaisesRegex(OSError, "requires POSIX"):
                    consume(
                        root,
                        [],
                        lambda: acks.append(True),
                        require_power_loss_durability=True,
                    )
                self.assertFalse(root.exists())
                self.assertEqual(acks, [])
            else:
                require_power_loss_durability()
                consume(
                    root,
                    [],
                    lambda: acks.append(True),
                    require_power_loss_durability=True,
                )
                self.assertEqual(acks, [True])

    def test_unicode_paths_replay_and_conflict_preserve_bytes(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "espacio ñ" / "archivo.bin"
            durable(target, b"original")
            durable(target, b"original")
            with self.assertRaisesRegex(ValueError, "differs"):
                durable(target, b"conflicting")
            self.assertEqual(target.read_bytes(), b"original")
            self.assertEqual(list(target.parent.glob(".pending-*")), [])
            sync_directory(target.parent)
            with self.assertRaises(OSError):
                sync_directory(target)

    def test_native_peak_rss_is_positive(self):
        self.assertGreater(peak_rss_kib(), 0)

    def test_nonblocking_lock_contends_and_releases_on_close(self):
        with tempfile.TemporaryDirectory() as directory:
            lock = Path(directory) / "worker.lock"
            with (
                exclusive_lock(lock),
                self.assertRaises(BlockingIOError),
                exclusive_lock(lock, blocking=False),
            ):
                self.fail("concurrent owner acquired the lock")
            with exclusive_lock(lock, blocking=False):
                pass

    def test_process_death_releases_native_lock(self):
        with tempfile.TemporaryDirectory() as directory:
            lock = Path(directory) / "worker.lock"
            code = (
                "import sys; from scripts.platform_io import exclusive_lock; "
                "guard=exclusive_lock(sys.argv[1]); guard.__enter__(); "
                "print('locked',flush=True); sys.stdin.read()"
            )
            child = subprocess.Popen(
                [sys.executable, "-B", "-c", code, str(lock)],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            try:
                self.assertEqual(child.stdout.readline().strip(), "locked")
                with (
                    self.assertRaises(BlockingIOError),
                    exclusive_lock(lock, blocking=False),
                ):
                    self.fail("live child lock was ignored")
                child.kill()
                child.communicate(timeout=10)
                with exclusive_lock(lock, blocking=False):
                    pass
            finally:
                if child.poll() is None:
                    child.kill()
                child.communicate(timeout=10)
