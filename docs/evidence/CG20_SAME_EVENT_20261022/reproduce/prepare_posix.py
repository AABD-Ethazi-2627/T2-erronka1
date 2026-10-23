import json
import os
import subprocess
from pathlib import Path

E = Path(__file__).resolve().parent
tools = E.parent / "kafka-volume-fix/ext4-tools"
executable = tools / "usr/bin/mke2fs"
assert executable.is_file()
image = E / "es-posix-runtime.ext4"
with image.open("xb") as stream:
    stream.truncate(256 * 1024 * 1024)
args = [
    str(executable),
    "-t",
    "ext4",
    "-F",
    "-q",
    "-E",
    "lazy_itable_init=0,lazy_journal_init=0",
    str(image),
]
result = subprocess.run(
    args,
    check=False,
    capture_output=True,
    text=True,
    env={
        **os.environ,
        "LD_LIBRARY_PATH": str(tools / "usr/lib64"),
        "MKE2FS_CONFIG": str(tools / "etc/mke2fs.conf"),
    },
)
(E / "posix-format.json").write_text(
    json.dumps(
        {
            "args": args,
            "exit": result.returncode,
            "stdout": result.stdout,
            "stderr": result.stderr,
        },
        indent=2,
    )
    + "\n"
)
result.check_returncode()
(E / "lab-01/es-posix").mkdir(exist_ok=False)
