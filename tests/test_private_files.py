"""Real filesystem/ACL checks; platform branches exercise their native contract."""

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.check_smb_source import read_config
from scripts.nifi_client import private_token
from scripts.private_files import open_private_text, private_text_file


def _windows_dacl(path, dacl):
    """Independent native fixture setup; never chmod a Windows secret."""
    import ctypes
    from ctypes import wintypes

    advapi = ctypes.WinDLL("advapi32", use_last_error=True)
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    convert = advapi.ConvertStringSecurityDescriptorToSecurityDescriptorW
    convert.argtypes = [
        wintypes.LPCWSTR,
        wintypes.DWORD,
        ctypes.POINTER(wintypes.LPVOID),
        ctypes.POINTER(wintypes.DWORD),
    ]
    convert.restype = wintypes.BOOL
    apply = advapi.SetFileSecurityW
    apply.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.LPVOID]
    apply.restype = wintypes.BOOL
    kernel.LocalFree.argtypes = [wintypes.LPVOID]
    kernel.LocalFree.restype = wintypes.LPVOID
    descriptor = wintypes.LPVOID()
    if not convert(dacl, 1, ctypes.byref(descriptor), None):
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        if not apply(str(path), 0x80000004, descriptor):  # protected DACL
            raise ctypes.WinError(ctypes.get_last_error())
    finally:
        kernel.LocalFree(descriptor)


class PrivateFilesTests(unittest.TestCase):
    def assert_consumers_reject(self, path, message):
        with self.assertRaisesRegex(ValueError, message), open_private_text(path):
            self.fail("unsafe file opened")
        with self.assertRaisesRegex(ValueError, message):
            read_config(path)
        with (
            patch.dict(os.environ, {"CNC_NIFI_TOKEN_FILE": str(path)}),
            self.assertRaisesRegex(ValueError, message),
        ):
            private_token()

    def test_private_utf8_file_child_access_and_cleanup(self):
        with private_text_file("private-ñ\n") as path:
            directory = path.parent
            with open_private_text(path) as handle:
                self.assertEqual(handle.read(), "private-ñ\n")
            if os.name == "posix":
                self.assertEqual(path.stat().st_mode & 0o777, 0o600)
                self.assertEqual(directory.stat().st_mode & 0o777, 0o700)
            child = subprocess.run(
                [
                    sys.executable,
                    "-B",
                    "-c",
                    (
                        "import pathlib,sys; sys.stdout.buffer.write("
                        "pathlib.Path(sys.argv[1]).read_bytes())"
                    ),
                    str(path),
                ],
                check=True,
                capture_output=True,
                timeout=15,
            )
            self.assertEqual(child.stdout, "private-ñ\n".encode())
        self.assertFalse(path.exists())
        self.assertFalse(directory.exists())

    def test_cleanup_on_consumer_exception(self):
        with (
            self.assertRaisesRegex(RuntimeError, "fixture failure"),
            private_text_file("fixture") as path,
        ):
            raise RuntimeError("fixture failure")
        self.assertFalse(path.exists())
        self.assertFalse(path.parent.exists())

    def test_public_permissions_rejected_by_all_consumers(self):
        with private_text_file("fixture") as path:
            if os.name == "nt":
                from scripts.private_files import _current_sid

                user = _current_sid()
                for grant in ("FR", "FW", "RC"):
                    _windows_dacl(path, f"D:P(A;;FA;;;{user})(A;;{grant};;;WD)")
                    self.assert_consumers_reject(path, "permissions")
            else:
                for mode in (0o604, 0o620, 0o601):
                    path.chmod(mode)
                    self.assert_consumers_reject(path, "permissions")

    def test_native_owner_rejection(self):
        if os.name == "nt":
            path = Path(os.environ["SystemRoot"]) / "win.ini"
        elif os.getuid() == 0:
            with private_text_file("fixture") as path:
                os.chown(path, 1, -1)
                self.assert_consumers_reject(path, "owned by this user")
            return
        else:
            path = Path("/etc/passwd")
        self.assert_consumers_reject(path, "owned by this user")

    def test_non_regular_files_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)
            self.assert_consumers_reject(path, "regular file")
            if os.name == "posix":
                fifo = path / "fifo"
                os.mkfifo(fifo, 0o600)
                self.assert_consumers_reject(fifo, "regular file")
            else:
                self.assert_consumers_reject(
                    Path(os.devnull).absolute(), "local Windows disk path"
                )

    def test_final_link_or_reparse_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            link = Path(tmp) / "link"
            if os.name == "nt":
                # A junction exercises real reparse rejection without requiring
                # Developer Mode or SeCreateSymbolicLinkPrivilege.
                subprocess.run(
                    ["cmd", "/d", "/c", "mklink", "/J", str(link), tmp],
                    check=True,
                    capture_output=True,
                    timeout=15,
                )
                try:
                    self.assert_consumers_reject(link, "reparse")
                finally:
                    link.rmdir()
            else:
                with private_text_file("fixture") as target:
                    link.symlink_to(target)
                    with self.assertRaises(OSError), open_private_text(link):
                        self.fail("symlink opened")
                    with self.assertRaises(OSError):
                        read_config(link)
                    with (
                        patch.dict(os.environ, {"CNC_NIFI_TOKEN_FILE": str(link)}),
                        self.assertRaises(OSError),
                    ):
                        private_token()

    def test_platform_specific_permissions_contract(self):
        with private_text_file("fixture") as path:
            if os.name == "nt":
                from scripts.private_files import _current_sid

                user = _current_sid()
                _windows_dacl(path, f"D:P(A;;FA;;;{user})(A;;FA;;;SY)(A;;FA;;;BA)")
                with open_private_text(path) as handle:
                    self.assertEqual(handle.read(), "fixture")
                # A conditional allow is an unsupported effective ACE even if
                # its condition would currently be false.
                _windows_dacl(
                    path,
                    f'D:P(A;;FA;;;{user})(XA;;FR;;;WD;(@User.Title == "Manager"))',
                )
                self.assert_consumers_reject(path, "unsupported ACE")
                _windows_dacl(path, "D:NO_ACCESS_CONTROL")
                self.assert_consumers_reject(path, "null DACL")
            else:
                path.chmod(0o400)
                with open_private_text(path) as handle:
                    self.assertEqual(handle.read(), "fixture")

    def test_no_permission_check_to_read_path_reopen(self):
        with private_text_file("original") as path, open_private_text(path) as handle:
            if os.name == "nt":
                # Denying delete/write sharing pins the file and directory.
                with self.assertRaises(PermissionError):
                    path.unlink()
                with self.assertRaises(PermissionError):
                    path.parent.rename(
                        path.parent.with_name(path.parent.name + "-moved")
                    )
            else:
                # Replacing the name cannot replace the checked descriptor.
                replacement = path.with_name("replacement")
                replacement.write_text("replacement", encoding="utf-8")
                replacement.chmod(0o600)
                replacement.replace(path)
            self.assertEqual(handle.read(), "original")

    def test_out_of_contract_windows_paths_rejected_before_open(self):
        if os.name == "nt":
            for path in (
                Path(r"\\server.invalid\share\secret"),
                Path(r"\\.\pipe\private-fixture"),
                Path(r"C:\private-fixture:stream"),
            ):
                self.assert_consumers_reject(path, "local Windows disk path")
        else:
            # POSIX supports ordinary relative paths for the SMB env file;
            # NiFi separately enforces absolute configured paths.
            with private_text_file("fixture") as path:
                relative = os.path.relpath(path)
                with open_private_text(relative) as handle:
                    self.assertEqual(handle.read(), "fixture")


if __name__ == "__main__":
    unittest.main()
