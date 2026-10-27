"""Fresh engine-side bind reservation; never starts Docker or Elasticsearch."""

import json
import os
import stat
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from es_runtime import DockerRuntime, reserve_bind_mounts
from es_workspace import reserve_directory

RUN = "1" * 32
SOCKET = "unix:///mnt/d/private/docker.sock"


@unittest.skipUnless(os.name == "posix", "POSIX no-follow filesystem checks run in CI")
class DirectoryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def reserve(self, destination):
        return reserve_directory(
            str(destination), RUN, root=str(self.root), owner=os.geteuid()
        )

    def test_fresh_private_tree_has_only_owned_empty_leaves(self):
        base = self.root / "new"
        sources = self.reserve(base)
        self.assertEqual((base / ".t2-verification").read_text(), RUN + "\n")
        for name, value in sources.items():
            path = Path(value)
            self.assertEqual(path, base / name)
            self.assertEqual(list(path.iterdir()), [])
            self.assertEqual(path.stat().st_uid, os.geteuid())
            self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o700)
        self.assertEqual(stat.S_IMODE(base.stat().st_mode), 0o700)

    def test_every_existing_base_is_rejected_without_modifying_data(self):
        empty = self.root / "empty"
        empty.mkdir()
        used = self.root / "used"
        (used / "data").mkdir(parents=True)
        marker = used / "data/nodes"
        marker.write_bytes(b"untouched ES data")
        leaf_link = used / "logs"
        leaf_link.symlink_to(self.root, target_is_directory=True)
        file = self.root / "file"
        file.write_bytes(b"untouched file")
        for base in (empty, used, file):
            with self.subTest(base=base), self.assertRaises(FileExistsError):
                self.reserve(base)
        self.assertEqual(list(empty.iterdir()), [])
        self.assertEqual(marker.read_bytes(), b"untouched ES data")
        self.assertTrue(leaf_link.is_symlink())
        self.assertEqual(file.read_bytes(), b"untouched file")
        self.assertFalse((used / ".t2-verification").exists())

    def test_live_and_dangling_symlinks_and_linked_ancestors_are_rejected(self):
        target = self.root / "target"
        target.mkdir()
        live = self.root / "live"
        live.symlink_to(target, target_is_directory=True)
        dangling = self.root / "dangling"
        dangling.symlink_to(self.root / "absent", target_is_directory=True)
        for base in (live, dangling, live / "new", dangling / "new"):
            with self.subTest(base=base), self.assertRaises(OSError):
                self.reserve(base)
        self.assertEqual(list(target.iterdir()), [])
        self.assertFalse((self.root / "absent").exists())

    def test_missing_parents_escapes_and_invalid_identity_never_create_trees(self):
        with self.assertRaises(FileNotFoundError):
            self.reserve(self.root / "missing/new")
        self.assertFalse((self.root / "missing").exists())
        for base in (str(self.root / "../escape"), str(self.root / "a,src=x")):
            with self.subTest(base=base), self.assertRaises(ValueError):
                reserve_directory(base, RUN, root=str(self.root), owner=os.geteuid())
        with self.assertRaises(ValueError):
            reserve_directory(str(self.root / "new"), "invalid", root=str(self.root))

    def test_failure_preserves_partial_owned_tree_and_does_not_delete(self):
        base = self.root / "partial"
        with (
            patch("es_workspace.os.fchmod", side_effect=PermissionError),
            self.assertRaises(PermissionError),
        ):
            self.reserve(base)
        self.assertTrue(base.is_dir())
        self.assertTrue((base / ".t2-verification").is_file())
        self.assertEqual(list((base / "data").iterdir()), [])

    def test_shared_nonsticky_ancestor_is_rejected_before_creation(self):
        shared = self.root / "shared"
        private = shared / "private"
        private.mkdir(parents=True)
        shared.chmod(0o777)
        for base in (shared / "new", private / "new"):
            with (
                self.subTest(base=base),
                self.assertRaisesRegex(PermissionError, "ancestors"),
            ):
                self.reserve(base)
            self.assertFalse(base.exists())
        self.assertTrue(private.is_dir())

    def test_trusted_sticky_parent_keeps_operator_tree_protected(self):
        sticky = self.root / "sticky"
        sticky.mkdir()
        sticky.chmod(0o1777)
        base = sticky / "new"
        self.assertEqual(self.reserve(base)["data"], str(base / "data"))


class HostBoundaryTests(unittest.TestCase):
    def test_wsl_runs_reservation_on_engine_host_with_separate_arguments(self):
        runtime = DockerRuntime("local:image", distro="FedoraLinux-43", host=SOCKET)
        base = "/mnt/d/private/new"
        expected = {name: base + "/" + name for name in ("data", "java-temp", "logs")}
        with patch(
            "es_runtime.subprocess.run",
            return_value=subprocess.CompletedProcess([], 0, json.dumps(expected)),
        ) as run:
            self.assertEqual(
                reserve_bind_mounts(
                    runtime, Path("/mnt/d/receipts"), RUN, engine_work_dir=base
                ),
                expected,
            )
        args = run.call_args.args[0]
        self.assertEqual(
            args[:6],
            ["wsl", "-d", "FedoraLinux-43", "--exec", "/usr/bin/python3", "-c"],
        )
        self.assertEqual(args[-2:], [base, RUN])
        self.assertNotIn("shell", run.call_args.kwargs)

    def test_ambiguous_engine_and_unexpected_host_reply_fail_closed(self):
        with self.assertRaisesRegex(ValueError, "explicit local"):
            reserve_bind_mounts(DockerRuntime("local:image"), Path("/mnt/d/work"), RUN)
        runtime = DockerRuntime("local:image", distro="FedoraLinux-43", host=SOCKET)
        with (
            patch(
                "es_runtime.subprocess.run",
                return_value=subprocess.CompletedProcess([], 0, "{}"),
            ),
            self.assertRaises(ValueError),
        ):
            reserve_bind_mounts(
                runtime, Path("/mnt/d/receipts"), RUN, engine_work_dir="/mnt/d/new"
            )

    def test_both_verifiers_stop_before_docker_when_reservation_fails(self):
        import verify_elasticsearch_contract as contract
        import verify_es_ingest_pipeline as ingest

        for module, function in ((contract, contract.run), (ingest, ingest.verify)):
            work = Mock(spec=Path)
            work.resolve.return_value = work
            work.drive = "d:"
            output = Mock(spec=Path)
            output.exists.return_value = False
            with (
                self.subTest(module=module.__name__),
                patch.object(
                    module, "reserve_bind_mounts", side_effect=ValueError("unsafe")
                ) as reserve,
                patch.object(module.subprocess, "run") as run,
                patch.object(module.subprocess, "check_output") as output_command,
                self.assertRaisesRegex(ValueError, "unsafe"),
            ):
                if module is contract:
                    function(output, work, docker_host=SOCKET)
                else:
                    function(work, docker_host=SOCKET)
            reserve.assert_called_once()
            run.assert_not_called()
            output_command.assert_not_called()


if __name__ == "__main__":
    unittest.main()
