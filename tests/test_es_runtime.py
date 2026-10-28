"""Opt-in verifiers retain image/engine identity and refuse foreign cleanup."""

import argparse
import json
import subprocess
import unittest
from pathlib import Path
from unittest.mock import patch

from es_runtime import (
    DockerRuntime,
    add_runtime_arguments,
    cluster_uuid,
    docker_prefix,
    mount_source,
    run_identity,
    write_evidence,
)

IMAGE_ID = "sha256:" + "1" * 64
CONTAINER_ID = "2" * 64
RUN_ID = "3" * 32
SOCKET = "unix:///mnt/d/runtime/fs/docker.sock"


class SelectionTests(unittest.TestCase):
    def test_wsl_preserves_newline_argument_without_shell_parsing(self):
        runtime = DockerRuntime(IMAGE_ID, distro="FedoraLinux-43", host=SOCKET)
        with patch("es_runtime.subprocess.run") as run:
            runtime.command(
                ["exec", CONTAINER_ID, "curl", "--write-out", "\n%{http_code}"],
                input=b"data",
            )
        self.assertEqual(
            run.call_args.args[0],
            [
                "wsl",
                "-d",
                "FedoraLinux-43",
                "--exec",
                "/usr/bin/env",
                "-u",
                "DOCKER_CONTEXT",
                "DOCKER_HOST=" + SOCKET,
                "/usr/sbin/docker",
                "--host",
                SOCKET,
                "exec",
                CONTAINER_ID,
                "curl",
                "--write-out",
                "\n%{http_code}",
            ],
        )
        self.assertNotIn("shell", run.call_args.kwargs)
        self.assertEqual(run.call_args.kwargs["input"], b"data")

    def test_remote_engines_and_ambiguous_inputs_are_rejected(self):
        for host in (
            "tcp://remote:2375",
            "ssh://host",
            "unix://relative",
            "unix:///mnt/d/a\n",
        ):
            with self.subTest(host=host), self.assertRaises(ValueError):
                docker_prefix("FedoraLinux-43", host)
        for image in ("", "--help", "image\nother"):
            with self.subTest(image=image), self.assertRaises(ValueError):
                DockerRuntime(image)
        with self.assertRaises(ValueError):
            docker_prefix("Fedora --exec sh")

    def test_native_socket_and_image_selection_are_explicit(self):
        self.assertEqual(docker_prefix(host=SOCKET), ["docker", "--host", SOCKET])
        parser = argparse.ArgumentParser()
        add_runtime_arguments(parser, "default:tag", bind_mounts=True)
        args = parser.parse_args(
            [
                "--image",
                IMAGE_ID,
                "--docker-host",
                SOCKET,
                "--docker-via-wsl",
                "FedoraLinux-43",
                "--engine-work-dir",
                "/mnt/d/runtime/fs/case",
            ]
        )
        self.assertEqual(args.image, IMAGE_ID)
        self.assertEqual(args.docker_host, SOCKET)
        self.assertEqual(args.engine_work_dir, "/mnt/d/runtime/fs/case")

    def test_local_image_is_resolved_without_pull_and_invalid_ids_fail(self):
        runtime = DockerRuntime("built:remediated")
        with patch(
            "es_runtime.subprocess.run",
            return_value=subprocess.CompletedProcess([], 0, IMAGE_ID + "\n"),
        ) as run:
            self.assertEqual(runtime.resolve_image(), IMAGE_ID)
        self.assertEqual(
            run.call_args.args[0],
            ["docker", "image", "inspect", "built:remediated", "--format", "{{.Id}}"],
        )
        with (
            patch.object(
                runtime,
                "command",
                return_value=subprocess.CompletedProcess([], 0, "unexpected"),
            ),
            self.assertRaises(ValueError),
        ):
            runtime.resolve_image()

    def test_engine_ext4_location_is_separate_from_local_evidence(self):
        self.assertEqual(
            mount_source(
                Path("/mnt/d/receipts/case"),
                "data",
                distro="FedoraLinux-43",
                engine_work_dir="/mnt/d/runtime/fs/case",
            ),
            "/mnt/d/runtime/fs/case/data",
        )
        self.assertEqual(
            mount_source(Path("/mnt/d/case"), "logs", distro="FedoraLinux-43"),
            "/mnt/d/case/logs",
        )
        for directory in (
            "/mnt/c/case",
            "/mnt/d/../c/case",
            "relative",
            "/mnt/d/case,src=/mnt/c",
        ):
            with self.subTest(directory=directory), self.assertRaises(ValueError):
                mount_source(Path("/mnt/d/receipts"), "data", engine_work_dir=directory)


class OwnershipTests(unittest.TestCase):
    def info(self):
        return {
            "Id": CONTAINER_ID,
            "Image": IMAGE_ID,
            "Config": {"Labels": {"t2.verification": RUN_ID}},
        }

    def test_network_none_gets_own_loopback_hostname_and_label(self):
        args = run_identity(RUN_ID)
        hostname = args[args.index("--hostname") + 1]
        self.assertIn(hostname + ":127.0.0.1", args)
        self.assertIn("t2.verification=" + RUN_ID, args)

    def test_cleanup_verifies_label_container_and_image_before_removal(self):
        runtime = DockerRuntime(IMAGE_ID)
        for field in ("Id", "Image", "label"):
            info = self.info()
            if field == "label":
                info["Config"]["Labels"]["t2.verification"] = "foreign"
            else:
                info[field] = "foreign"
            with patch.object(
                runtime,
                "command",
                return_value=subprocess.CompletedProcess([], 0, json.dumps([info])),
            ) as command:
                with self.subTest(field=field), self.assertRaises(ValueError):
                    runtime.cleanup(CONTAINER_ID, RUN_ID, IMAGE_ID, {})
                self.assertEqual(command.call_count, 1)
                self.assertEqual(command.call_args.args[0][0], "inspect")

    def test_owned_cleanup_records_success_and_preserves_primary_on_failure(self):
        runtime = DockerRuntime(IMAGE_ID)
        evidence = {}
        with patch.object(
            runtime,
            "command",
            side_effect=[
                subprocess.CompletedProcess([], 0, json.dumps([self.info()])),
                subprocess.CompletedProcess([], 0),
            ],
        ) as command:
            runtime.cleanup(CONTAINER_ID, RUN_ID, IMAGE_ID, evidence)
        self.assertTrue(evidence["container_removed"])
        self.assertEqual(command.call_args.args[0], ["rm", "--force", CONTAINER_ID])
        primary = RuntimeError("primary verification failure")
        evidence.update(passed=True, status="PASSED")
        with patch.object(runtime, "command", side_effect=OSError("unavailable")):
            runtime.cleanup(CONTAINER_ID, RUN_ID, IMAGE_ID, evidence, primary)
        self.assertFalse(evidence["container_removed"])
        self.assertEqual(evidence["cleanup_error_type"], "OSError")
        self.assertFalse(evidence["passed"])
        self.assertEqual(evidence["status"], "FAILED")
        self.assertEqual(primary.__notes__, ["ES verification cleanup failed: OSError"])

    def test_cluster_uuid_is_required_and_retained(self):
        self.assertEqual(
            cluster_uuid({"cluster_uuid": "local_own-cluster"}), "local_own-cluster"
        )
        for value in (None, "", "_na_", "\n"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                cluster_uuid({"cluster_uuid": value})

    def test_unwritable_receipt_preserves_primary_but_fails_without_one(self):
        primary = ValueError("primary validation failure")
        with patch.object(Path, "write_text", side_effect=OSError("unavailable")):
            write_evidence(Path("result.json"), {}, primary)
            with self.assertRaises(OSError):
                write_evidence(Path("result.json"), {})
        self.assertEqual(
            primary.__notes__, ["ES verification evidence persistence failed: OSError"]
        )
