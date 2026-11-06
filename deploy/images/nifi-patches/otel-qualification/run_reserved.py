"""Run only with the coordinator's VM heavy slot and existing common lock."""

import datetime
import hashlib
import json
import os
import subprocess
import sys
import time
import uuid
from pathlib import Path

BASE = Path(
    os.environ.get(
        "CNC_OTEL_PROOF_ROOT", "/opt/cnc-guard/evidence/otel-qualification-20261106"
    )
).absolute()
ALLOWED = Path("/opt/cnc-guard/evidence/otel-qualification-20261106")
if BASE != ALLOWED and ALLOWED not in BASE.parents:
    raise ValueError("proof root must stay in owned evidence tree")
TOOLS = BASE / "source/deploy/images/nifi-patches/otel-qualification"
IMAGE = "sha256:03f3e9a19dbce166304ec63a685c44f2da07239e5659d843c798c7f32f7012d5"
JDK = Path("/usr/lib/jvm/java-21-openjdk-amd64")
RESULT = BASE / "reserved-result.json"
PHASES = [sys.argv[1]] if len(sys.argv) > 1 else ["extract", "static", "runtime"]
if any(p not in ("extract", "static", "runtime") for p in PHASES):
    raise ValueError("unknown phase")
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()


def save(value):
    RESULT.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


image = json.loads(subprocess.check_output(["docker", "image", "inspect", IMAGE]))[0]
assert image["Id"] == IMAGE
assert (JDK / "bin/javac").is_file()
report = {
    "started_utc": datetime.datetime.now(datetime.UTC).isoformat(),
    "image_before": image,
    "base_source_commit": "12ca2fa95c0e6e94665dc75923f3cbdaa2468b24",
    "guard_precondition_commit": "92ff99e",
    "replacement": None,
    "runtime_approved": False,
    "commands": [],
    "source_sha256": {
        str(p.relative_to(BASE / "source")): sha(p)
        for p in (BASE / "source").rglob("*")
        if p.is_file()
    },
}
if RESULT.exists():
    previous = json.loads(RESULT.read_text())
    if previous["source_sha256"] != report["source_sha256"]:
        raise ValueError(
            "phase resume source drift; preserve evidence and use a fresh proof"
        )
    report = previous
save(report)
try:
    start = time.monotonic()
    with (BASE / "green.log").open("w") as log:
        test = [
            "/opt/cnc-guard/venvs/py311/bin/python",
            "-B",
            "-m",
            "unittest",
            "discover",
            "-s",
            str(BASE / "source/tests"),
            "-p",
            "test_nifi_otel_qualification.py",
            "-v",
        ]
        r = subprocess.run(
            test, check=False, stdout=log, stderr=subprocess.STDOUT, timeout=35
        )
    report["commands"].append(
        {
            "phase": "unit-green",
            "command": test,
            "returncode": r.returncode,
            "elapsed_seconds": time.monotonic() - start,
        }
    )
    save(report)
    if r.returncode:
        raise ValueError("unit guards failed")
    for phase in PHASES:
        name = "cnc-otel-" + phase + "-" + uuid.uuid4().hex[:10]
        command = [
            "docker",
            "run",
            "--rm",
            "--pull=never",
            "--name",
            name,
            "--network",
            "none",
            "--cpus",
            "1",
            "--cpuset-cpus",
            "0",
            "--memory",
            "512m",
            "--memory-swap",
            "512m",
            "--pids-limit",
            "64",
            "--read-only",
            "--cap-drop",
            "ALL",
            "--security-opt",
            "no-new-privileges",
            "--user",
            "1000:1000",
            "--ulimit",
            "core=0:0",
            "--tmpfs",
            "/tmp:rw,nosuid,nodev,noexec,size=64m",
            "--mount",
            f"type=bind,src={TOOLS},dst=/tools,readonly",
            "--mount",
            f"type=bind,src={BASE}/public-cache,dst=/cache,readonly",
            "--mount",
            f"type=bind,src={BASE},dst=/proof",
            "--mount",
            f"type=bind,src={JDK},dst=/jdk,readonly",
            "--env",
            "PYTHONDONTWRITEBYTECODE=1",
            "--env",
            "OPENBLAS_NUM_THREADS=1",
            "--entrypoint",
            "python3",
            IMAGE,
            "-B",
            "/tools/run_phase.py",
            phase,
            "--proof",
            "/proof",
        ]
        start = time.monotonic()
        timed = False
        with (
            (BASE / (phase + ".stdout")).open("w") as stdout,
            (BASE / (phase + ".stderr")).open("w") as stderr,
        ):
            process = subprocess.Popen(command, stdout=stdout, stderr=stderr)
            try:
                rc = process.wait(timeout=175)
            except subprocess.TimeoutExpired:
                timed = True
                process.kill()
                process.wait(timeout=10)
                rc = 124
            finally:
                cleanup = subprocess.run(
                    ["docker", "rm", "-f", "-v", name],
                    check=False,
                    capture_output=True,
                    text=True,
                    timeout=20,
                )
        execution = {
            "phase": phase,
            "command": command,
            "returncode": rc,
            "timed_out": timed,
            "elapsed_seconds": round(time.monotonic() - start, 3),
            "cleanup_returncode": cleanup.returncode,
            "cleanup_stderr": cleanup.stderr,
            "phase_wall_limit_seconds": 175,
            "rss_measured": False,
        }
        report["commands"].append(execution)
        save(report)
        print(
            json.dumps(
                {k: execution[k] for k in ("phase", "returncode", "elapsed_seconds")}
            ),
            flush=True,
        )
        if rc:
            raise ValueError("phase failed: " + phase)
    completed = {x["phase"] for x in report["commands"] if x["returncode"] == 0}
    report["status"] = (
        "bounded-component-qualification-phases-passed"
        if {"extract", "static", "runtime"} <= completed
        else "bounded-requested-phase-passed"
    )
except (ValueError, OSError, AssertionError, subprocess.SubprocessError) as error:
    report.update(
        status="qualification-blocked-or-failed",
        error=type(error).__name__ + ": " + str(error),
    )
finally:
    image_after = json.loads(
        subprocess.check_output(["docker", "image", "inspect", IMAGE])
    )[0]
    report["image_after"] = image_after
    report["image_identity_unchanged"] = (
        image_after["Id"] == image["Id"] and image_after["RootFS"] == image["RootFS"]
    )
    after = {
        str(p.relative_to(BASE / "source")): sha(p)
        for p in (BASE / "source").rglob("*")
        if p.is_file()
    }
    report["source_unchanged"] = after == report["source_sha256"]
    report["remaining_owned_containers"] = subprocess.check_output(
        ["docker", "ps", "-a", "--filter", "name=cnc-otel-", "--format", "{{.Names}}"],
        text=True,
    ).splitlines()
    report["finished_utc"] = datetime.datetime.now(datetime.UTC).isoformat()
    save(report)
    print(
        json.dumps(
            {
                "status": report["status"],
                "image_unchanged": report["image_identity_unchanged"],
                "source_unchanged": report["source_unchanged"],
                "owned_containers": report["remaining_owned_containers"],
            }
        ),
        flush=True,
    )
