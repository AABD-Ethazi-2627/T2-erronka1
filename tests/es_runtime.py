"""Explicit local Docker selection for opt-in disposable ES verifiers.

--engine-work-dir selects a NEW engine-side directory under /mnt/d, with an
existing parent (which may be on ext4). A host-side preflight reserves private
data, java-temp and logs directories; local --work-dir keeps the receipts.
This option neither formats storage nor claims that an arbitrary D: path is ext4.
"""

import json
import os
import re
import subprocess
import sys
from pathlib import Path, PurePosixPath


def add_runtime_arguments(parser, default_image, *, bind_mounts=False):
    parser.add_argument(
        "--image",
        default=default_image,
        help="Existing local image ID/reference; never pulled",
    )
    parser.add_argument(
        "--docker-via-wsl", help="Run Docker in this WSL distribution via --exec"
    )
    parser.add_argument(
        "--docker-host", help="Explicit local unix:// or npipe:// Docker socket"
    )
    if bind_mounts:
        parser.add_argument(
            "--engine-work-dir",
            help="New engine-side /mnt/d directory; parent must exist, no symlinks",
        )


def docker_prefix(distro=None, host=None):
    if distro is not None and not re.fullmatch(r"[A-Za-z0-9_.-]+", distro):
        raise ValueError("Invalid WSL distribution name")
    if host is not None and (
        any(char.isspace() for char in host)
        or not (
            host.startswith("unix:///")
            or (not distro and host.startswith("npipe:////./pipe/"))
        )
    ):
        raise ValueError("Docker host must be an explicit local socket")
    if distro:
        prefix = ["wsl", "-d", distro, "--exec"]
        if host:
            prefix += ["/usr/bin/env", "-u", "DOCKER_CONTEXT", "DOCKER_HOST=" + host]
        prefix += ["/usr/sbin/docker"]
        return prefix + ["--host", host] if host else prefix
    return ["docker", "--host", host] if host else ["docker"]


def mount_source(work, name, *, distro=None, engine_work_dir=None):
    if name not in ("data", "java-temp", "logs"):
        raise ValueError("Unknown ES bind mount")
    if engine_work_dir is not None:
        base = PurePosixPath(engine_work_dir)
        if (
            not base.is_absolute()
            or not str(base).startswith("/mnt/d/")
            or ".." in base.parts
            or any(char in engine_work_dir for char in ",\x00\r\n")
        ):
            raise ValueError("Engine work directory must be an absolute /mnt/d path")
        return str(base / name)
    path = Path(work) / name
    if distro:
        if path.drive.lower() == "d:":
            return "/mnt/d/" + path.as_posix()[3:]
        if path.as_posix().startswith("/mnt/d/"):
            return path.as_posix()
        raise ValueError("WSL bind source must be on D:")
    return str(path)


def reserve_bind_mounts(runtime, work, run_id, *, engine_work_dir=None):
    """Reserve storage on the explicitly selected local engine host before run."""
    run_identity(run_id)
    if runtime.host is None or not runtime.host.startswith("unix:///"):
        raise ValueError(
            "Bind verification requires an explicit local Unix Docker socket"
        )
    if runtime.distro:
        python = ["wsl", "-d", runtime.distro, "--exec", "/usr/bin/python3"]
    elif os.name == "posix":
        python = [sys.executable]
    else:
        raise ValueError("Windows bind verification requires --docker-via-wsl")
    base = engine_work_dir
    if base is None:
        parent = PurePosixPath(mount_source(work, "data", distro=runtime.distro)).parent
        base = str(parent / ("engine-" + run_id))
    # Apply the same lexical restrictions before asking the engine host to walk
    # and exclusively create the path. Do not trust a pre-existing directory.
    expected = {
        name: mount_source(work, name, distro=runtime.distro, engine_work_dir=base)
        for name in ("data", "java-temp", "logs")
    }
    script = Path(__file__).with_name("es_workspace.py").read_text(encoding="utf-8")
    result = subprocess.run(
        python + ["-c", script, base, run_id],
        check=True,
        capture_output=True,
        text=True,
        timeout=30,
    )
    if json.loads(result.stdout) != expected:
        raise ValueError("Engine returned unexpected ES bind workspace paths")
    return expected


def run_identity(run_id):
    if not re.fullmatch(r"[0-9a-f]{32}", run_id):
        raise ValueError("Invalid verification run ID")
    hostname = "cnc-es-" + run_id
    return [
        "--label",
        "t2.verification=" + run_id,
        "--hostname",
        hostname,
        "--add-host",
        hostname + ":127.0.0.1",
    ]


class DockerRuntime:
    def __init__(self, image, *, distro=None, host=None):
        if (
            not isinstance(image, str)
            or not image
            or image.startswith("-")
            or any(c.isspace() for c in image)
        ):
            raise ValueError("Image must be a single local image ID or reference")
        self.image = image
        self.distro = distro
        self.host = host
        self.prefix = docker_prefix(distro, host)

    def command(self, arguments, **kwargs):
        return subprocess.run(
            self.prefix + arguments,
            capture_output=True,
            check=True,
            timeout=30,
            **kwargs,
        )

    def resolve_image(self):
        identity = self.command(
            ["image", "inspect", self.image, "--format", "{{.Id}}"], text=True
        ).stdout.strip()
        if not re.fullmatch(r"sha256:[0-9a-f]{64}", identity):
            raise ValueError("Docker returned an invalid local image ID")
        return identity

    def verify_owned(self, container, run_id, image_id):
        if not re.fullmatch(r"[0-9a-f]{64}", container):
            raise ValueError("Docker returned an invalid container ID")
        info = json.loads(self.command(["inspect", container], text=True).stdout)[0]
        if (
            info.get("Id") != container
            or info.get("Image") != image_id
            or info.get("Config", {}).get("Labels", {}).get("t2.verification") != run_id
        ):
            raise ValueError(
                "Refuse operating on a container outside this verification"
            )
        return info

    def cleanup(self, container, run_id, image_id, evidence, primary_error=None):
        try:
            self.verify_owned(container, run_id, image_id)
            self.command(["rm", "--force", container])
            evidence["container_removed"] = True
        except (
            OSError,
            subprocess.SubprocessError,
            ValueError,
            KeyError,
            IndexError,
        ) as exc:
            evidence["container_removed"] = False
            evidence["cleanup_error_type"] = type(exc).__name__
            if "passed" in evidence:
                evidence["passed"] = False
            if "status" in evidence:
                evidence["status"] = "FAILED"
            if primary_error is None:
                raise
            primary_error.add_note(
                "ES verification cleanup failed: " + type(exc).__name__
            )


def cluster_uuid(server):
    identity = server.get("cluster_uuid")
    if (
        not isinstance(identity, str)
        or not re.fullmatch(r"[A-Za-z0-9_-]+", identity)
        or identity == "_na_"
    ):
        raise ValueError("Isolated Elasticsearch has no established cluster UUID")
    return identity


def write_evidence(output, evidence, primary_error=None):
    try:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(
            json.dumps(evidence, indent=2) + "\n", encoding="utf-8", newline="\n"
        )
    except (OSError, TypeError, ValueError) as exc:
        if primary_error is None:
            raise
        primary_error.add_note(
            "ES verification evidence persistence failed: " + type(exc).__name__
        )
