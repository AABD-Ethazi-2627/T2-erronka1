"""Reserve fresh ES bind storage on the engine host, without following symlinks."""

import json
import os
import re
import stat
import sys
from pathlib import PurePosixPath

NAMES = ("data", "java-temp", "logs")


def reserve_directory(path, run_id, *, root="/mnt/d", owner=1000):
    # root/owner are injectable for inert filesystem tests; the engine entrypoint
    # below always uses /mnt/d and the image's fixed ES UID 1000.
    base = PurePosixPath(path)
    allowed = PurePosixPath(root)
    if (
        not re.fullmatch(r"[0-9a-f]{32}", run_id)
        or str(base) != path
        or not base.is_relative_to(allowed)
        or base == allowed
        or ".." in base.parts
        or any(char in path for char in ",\x00\r\n")
    ):
        raise ValueError("Invalid private ES workspace path or run identity")
    if os.geteuid() not in (0, owner):
        raise PermissionError("ES workspace must be prepared by root or UID 1000")
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
    parent = os.open("/", flags)
    try:
        info = os.fstat(parent)

        def unsafe_parent(metadata):
            return metadata.st_uid not in (0, os.geteuid()) or (
                metadata.st_mode & 0o022 and not metadata.st_mode & stat.S_ISVTX
            )

        unsafe = unsafe_parent(info)
        # Every parent must already exist. Check links on the engine filesystem,
        # not via Path.resolve() on a different Windows/WSL filesystem view.
        for component in base.parts[1:-1]:
            next_parent = os.open(component, flags, dir_fd=parent)
            next_info = os.fstat(next_parent)
            # A new filesystem's mount root anchors the path: an unprivileged
            # process cannot rename that mounted root via its old ancestors.
            if next_info.st_dev != info.st_dev:
                unsafe = False
            unsafe = unsafe or unsafe_parent(next_info)
            os.close(parent)
            parent = next_parent
            info = next_info
        if unsafe:
            raise PermissionError(
                "ES workspace ancestors can be replaced by other users"
            )
        os.mkdir(base.name, mode=0o700, dir_fd=parent)
        directory = os.open(base.name, flags, dir_fd=parent)
        try:
            info = os.fstat(directory)
            if info.st_uid != os.geteuid() or stat.S_IMODE(info.st_mode) != 0o700:
                raise PermissionError("Filesystem cannot protect the new ES workspace")
            marker = os.open(
                ".t2-verification",
                os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                0o600,
                dir_fd=directory,
            )
            with os.fdopen(marker, "w") as stream:
                stream.write(run_id + "\n")
            for name in NAMES:
                os.mkdir(name, mode=0o700, dir_fd=directory)
                child = os.open(name, flags, dir_fd=directory)
                try:
                    if os.geteuid() == 0:
                        os.fchown(child, owner, 0)
                    os.fchmod(child, 0o700)
                    info = os.fstat(child)
                    if info.st_uid != owner or stat.S_IMODE(info.st_mode) != 0o700:
                        raise PermissionError(
                            "Filesystem cannot protect ES bind storage"
                        )
                finally:
                    os.close(child)
        finally:
            os.close(directory)
    finally:
        os.close(parent)
    # No cleanup on failure: even partial new trees are retained for inspection.
    return {name: str(base / name) for name in NAMES}


if __name__ == "__main__":
    destination, identity = sys.argv[1:]
    print(json.dumps(reserve_directory(destination, identity)))
