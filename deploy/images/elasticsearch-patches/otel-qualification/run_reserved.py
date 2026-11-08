"""One finite, coordinator-reserved metadata phase; default is a dry-run plan."""

import argparse
import datetime
import hashlib
import json
import shutil
import subprocess
import sys
import time
import uuid
from pathlib import Path

HERE = Path(__file__).resolve().parent
IMAGE = "sha256:2005cca9747e88288e27d18a2f7352486ab0e2a09acd46ee229e9d2bb889ccb4"
BASE = Path("/opt/cnc-guard/evidence/es-otel-qualification-20261106")
LOCK = Path("/opt/cnc-guard/evidence/remote-heavy.lock")
JAVA_OPTIONS = [
    "-Xmx256m",
    "-XX:MaxMetaspaceSize=96m",
    "-XX:MaxDirectMemorySize=32m",
    "-XX:ReservedCodeCacheSize=32m",
    "-XX:CompressedClassSpaceSize=32m",
    "-XX:ActiveProcessorCount=1",
    "-XX:-CreateCoredumpOnCrash",
]


def command(name, tools):
    return [
        "docker",
        "run",
        "--rm",
        "--pull=never",
        "--name",
        name,
        "--label",
        "cnc.es-otel-qualification=inventory",
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
        f"type=bind,src={tools},dst=/tools,readonly",
        "--entrypoint",
        "/usr/share/elasticsearch/jdk/bin/java",
        IMAGE,
        *JAVA_OPTIONS,
        "/tools/ModuleAudit.java",
        "/usr/share/elasticsearch",
    ]


def source_hashes():
    return {
        p.name: hashlib.sha256(p.read_bytes()).hexdigest()
        for p in HERE.iterdir()
        if p.is_file()
    }


def available_memory():
    rows = dict(
        line.split(":", 1) for line in Path("/proc/meminfo").read_text().splitlines()
    )
    return int(rows["MemAvailable"].split()[0]) * 1024


def preflight():
    if not Path("/opt/cnc-guard").is_dir() or not LOCK.parent.is_dir():
        raise ValueError("VM-only execution path absent")
    memory, disk = available_memory(), shutil.disk_usage(LOCK.parent).free
    if memory < 6 * 1024**3 or disk < 20 * 1024**3:
        raise ValueError("resource gate requires 6 GiB available / 20 GiB free")
    return {"available_memory_bytes": memory, "disk_free_bytes": disk}


def inspect_image():
    row = json.loads(
        subprocess.check_output(["docker", "image", "inspect", IMAGE], timeout=10)
    )[0]
    if row["Id"] != IMAGE:
        raise ValueError("image identity drift")
    return {"Id": row["Id"], "RootFS": row["RootFS"]}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--execute-reserved",
        action="store_true",
        help="only after the coordinator has granted this concrete phase its slot",
    )
    parser.add_argument("--attempt", default="inventory-01")
    args = parser.parse_args()
    if not args.execute_reserved:
        print(
            json.dumps(
                {
                    "status": "prepared-not-executed",
                    "replacement": None,
                    "runtime_approved": False,
                    "phase": "inventory-only",
                    "phase_wall_seconds": 175,
                    "lock": str(LOCK),
                    "command": command("cnc-es-otel-inventory-PLAN", HERE),
                },
                indent=2,
            )
        )
        return 0
    if not args.attempt or any(
        c not in "abcdefghijklmnopqrstuvwxyz0123456789-" for c in args.attempt
    ):
        raise ValueError("unsafe attempt name")
    # Never occupy an idle reservation. A busy lock returns 75 once, without retry.
    # Planning and portable contract tests need no POSIX lock. Execution remains
    # Linux-only and must fail closed if flock is unavailable.
    import fcntl

    with LOCK.open("a+") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            print("remote-heavy lock busy; phase was not started", file=sys.stderr)
            return 75
        resources = preflight()
        before = inspect_image()
        proof = BASE / args.attempt
        proof.mkdir(parents=True, exist_ok=False)
        report = {
            "status": "started",
            "replacement": None,
            "runtime_approved": False,
            "preflight": resources,
            "image_before": before,
            "source_before": source_hashes(),
            "started_utc": datetime.datetime.now(datetime.UTC).isoformat(),
            "phase_wall_seconds": 175,
        }

        def save():
            (proof / "run-result.json").write_text(
                json.dumps(report, indent=2, sort_keys=True) + "\n"
            )

        save()
        name = "cnc-es-otel-inventory-" + uuid.uuid4().hex[:10]
        cmd = command(name, HERE)
        report["command"] = cmd
        start = time.monotonic()
        rc = 1
        try:
            with (
                (proof / "audit.tsv").open("w") as out,
                (proof / "audit.stderr").open("w") as err,
            ):
                process = subprocess.Popen(cmd, stdout=out, stderr=err)
                try:
                    rc = process.wait(timeout=175)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5)
                    rc = 124
            report["returncode"] = rc
            if rc:
                raise ValueError("metadata audit failed")
            cmd_parse = [
                sys.executable,
                "-B",
                str(HERE / "qualify.py"),
                "inventory",
                "--audit",
                str(proof / "audit.tsv"),
                "--output",
                str(proof / "inventory.json"),
            ]
            parsed = subprocess.run(
                cmd_parse, capture_output=True, text=True, timeout=10, check=False
            )
            report["parse_returncode"] = parsed.returncode
            (proof / "parse.stderr").write_text(parsed.stderr)
            if parsed.returncode:
                raise ValueError("metadata parser failed")
            report["status"] = "inventory-complete-linkage-and-runtime-pending"
        except (OSError, ValueError, subprocess.SubprocessError) as error:
            report.update(
                status="failed-preserved-proof",
                error=type(error).__name__ + ": " + str(error),
            )
            rc = rc or 1
        finally:
            # This command can only remove the unique container created by this run.
            cleanup = subprocess.run(
                ["docker", "rm", "-f", "-v", name],
                capture_output=True,
                text=True,
                timeout=10,
                check=False,
            )
            report["cleanup_returncode"] = cleanup.returncode
            report["elapsed_seconds"] = round(time.monotonic() - start, 3)
            report["source_unchanged"] = report["source_before"] == source_hashes()
            report["image_unchanged"] = before == inspect_image()
            report["remaining_owned_containers"] = subprocess.check_output(
                [
                    "docker",
                    "ps",
                    "-a",
                    "--filter",
                    "name=" + name,
                    "--format",
                    "{{.Names}}",
                ],
                text=True,
                timeout=10,
            ).splitlines()
            if (
                not report["source_unchanged"]
                or not report["image_unchanged"]
                or report["remaining_owned_containers"]
            ):
                rc = 1
                report["status"] = "failed-preservation-or-cleanup"
            save()
        print(
            json.dumps(
                {
                    k: report.get(k)
                    for k in (
                        "status",
                        "returncode",
                        "parse_returncode",
                        "elapsed_seconds",
                        "image_unchanged",
                        "source_unchanged",
                    )
                }
            )
        )
        return rc


if __name__ == "__main__":
    sys.exit(main())
