"""Coordinator-reserved aligned SDK phases; no image mutation or publication."""

import datetime
import hashlib
import json
import subprocess
import time
import uuid
from pathlib import Path

BASE = Path("/opt/cnc-guard/evidence/otel-aligned-qualification-20261106")
TOOLS = BASE / "source/deploy/images/nifi-patches/otel-qualification"
BASELINE = Path("/opt/cnc-guard/evidence/otel-qualification-20261106")
MAVEN = Path("/opt/cnc-guard/evidence/maven-ce3c1d7/inputs")
IMAGE = "sha256:03f3e9a19dbce166304ec63a685c44f2da07239e5659d843c798c7f32f7012d5"
JDK = Path("/usr/lib/jvm/java-21-openjdk-amd64")
CONFIG = Path("/etc/java-21-openjdk")
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
image = json.loads(subprocess.check_output(["docker", "image", "inspect", IMAGE]))[0]
assert image["Id"] == IMAGE and (CONFIG / "security/java.security").is_file()
assert not (BASE / "aligned-reserved-result.json").exists()
report = {
    "status": "started",
    "started_utc": datetime.datetime.now(datetime.UTC).isoformat(),
    "image_before": image,
    "replacement": None,
    "runtime_approved": False,
    "commands": [],
    "source_sha256": {
        str(f.relative_to(BASE / "source")): sha(f)
        for f in (BASE / "source").rglob("*")
        if f.is_file()
    },
}


def save():
    (BASE / "aligned-reserved-result.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n"
    )


save()
try:
    with (BASE / "guards-green.log").open("w") as f:
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
        t = subprocess.run(
            test, stdout=f, stderr=subprocess.STDOUT, timeout=35, check=False
        )
    report["commands"].append(
        {"phase": "portable-guards", "command": test, "returncode": t.returncode}
    )
    save()
    if t.returncode:
        raise ValueError("portable guards failed")
    for phase in ("oracle", "static", "runtime"):
        name = "cnc-otel-aligned-" + phase + "-" + uuid.uuid4().hex[:10]
        cmd = [
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
            f"type=bind,src={BASELINE},dst=/baseline,readonly",
            "--mount",
            f"type=bind,src={BASE},dst=/proof",
            "--mount",
            f"type=bind,src={MAVEN},dst=/maven,readonly",
            "--mount",
            f"type=bind,src={JDK},dst=/jdk,readonly",
            "--mount",
            f"type=bind,src={CONFIG},dst={CONFIG},readonly",
            "--env",
            "PYTHONDONTWRITEBYTECODE=1",
            "--entrypoint",
            "python3",
            IMAGE,
            "-B",
            "/tools/aligned.py",
            phase,
            "--proof",
            "/proof",
        ]
        start = time.monotonic()
        timed = False
        with (
            (BASE / (phase + ".stdout")).open("w") as so,
            (BASE / (phase + ".stderr")).open("w") as se,
        ):
            p = subprocess.Popen(cmd, stdout=so, stderr=se)
            try:
                rc = p.wait(timeout=175)
            except subprocess.TimeoutExpired:
                timed = True
                p.kill()
                p.wait(timeout=10)
                rc = 124
            finally:
                cleanup = subprocess.run(
                    ["docker", "rm", "-f", "-v", name],
                    capture_output=True,
                    text=True,
                    timeout=20,
                    check=False,
                )
        result = {
            "phase": phase,
            "command": cmd,
            "returncode": rc,
            "elapsed_seconds": round(time.monotonic() - start, 3),
            "phase_wall_seconds": 175,
            "timed_out": timed,
            "rss_measured": False,
            "cleanup_returncode": cleanup.returncode,
            "cleanup_stderr": cleanup.stderr,
        }
        report["commands"].append(result)
        save()
        print(
            json.dumps(
                {k: result[k] for k in ("phase", "returncode", "elapsed_seconds")}
            ),
            flush=True,
        )
        if rc:
            raise ValueError("aligned phase failed " + phase)
    report["status"] = "aligned-qualification-phases-passed-not-runtime-approval"
except (ValueError, OSError, AssertionError, subprocess.SubprocessError) as error:
    report.update(
        status="blocked-aligned-qualification",
        error=type(error).__name__ + ": " + str(error),
    )
finally:
    after = json.loads(subprocess.check_output(["docker", "image", "inspect", IMAGE]))[
        0
    ]
    report["image_identity_unchanged"] = (
        after["Id"] == image["Id"] and after["RootFS"] == image["RootFS"]
    )
    report["source_unchanged"] = report["source_sha256"] == {
        str(f.relative_to(BASE / "source")): sha(f)
        for f in (BASE / "source").rglob("*")
        if f.is_file()
    }
    report["remaining_owned_containers"] = subprocess.check_output(
        [
            "docker",
            "ps",
            "-a",
            "--filter",
            "name=cnc-otel-aligned-",
            "--format",
            "{{.Names}}",
        ],
        text=True,
    ).splitlines()
    report["finished_utc"] = datetime.datetime.now(datetime.UTC).isoformat()
    save()
    print(
        json.dumps(
            {
                "status": report["status"],
                "image_unchanged": report["image_identity_unchanged"],
                "source_unchanged": report["source_unchanged"],
                "containers_remaining": report["remaining_owned_containers"],
            }
        ),
        flush=True,
    )
