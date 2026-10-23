"""Account bounded postprocessing separately from the immutable training runner."""

import argparse
import ctypes
import os
import subprocess
import sys
import time
from datetime import UTC, datetime

import psutil

from scripts.ml_study import ROOT, accounting, write_json
from scripts.report_ml_study import verify_evidence


def measured(root, module, arguments):
    allowed = {
        "scripts.report_ml_study",
        "scripts.audit_ml_study",
        "scripts.explain_ml_study",
        "scripts.export_ml_study_package",
        "scripts.verify_ml_study_scores",
        "scripts.business_ml_study",
    }
    if module not in allowed:
        raise ValueError("Only read/packaging study modules are admitted")
    manifest = verify_evidence(root)
    used = accounting(root)
    timeout = 300
    if used["benchmark"] + timeout > 3600:
        raise RuntimeError("Benchmark/postprocessing CPU reservation exhausted")
    unit = (
        root / "units" / ("analysis-" + datetime.now(UTC).strftime("%Y%m%dT%H%M%S%f"))
    )
    unit.mkdir(exist_ok=False)
    write_json(
        unit / "task.json",
        {
            "model": "_analysis",
            "phase": "analysis",
            "fold": 0,
            "fit": [],
            "held": [],
            "module": module,
            "arguments": arguments,
        },
    )
    handles = {}
    kernel = None
    if os.name == "nt":
        from ctypes import wintypes

        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        kernel.OpenProcess.restype = wintypes.HANDLE
        kernel.GetProcessTimes.argtypes = [wintypes.HANDLE] + [
            ctypes.POINTER(wintypes.FILETIME)
        ] * 4
        kernel.GetProcessTimes.restype = wintypes.BOOL
        kernel.CloseHandle.argtypes = [wintypes.HANDLE]
        kernel.CloseHandle.restype = wintypes.BOOL
    start = time.perf_counter()
    own_cpu = time.process_time()
    peak_rss = cpu_sample = 0
    max_threads = 1
    status = "complete_analysis"
    with (
        (unit / "stdout.log").open("x") as stdout,
        (unit / "stderr.log").open("x") as stderr,
    ):
        child_env = os.environ.copy()
        child_env.update(
            {
                k: "1"
                for k in (
                    "OMP_NUM_THREADS",
                    "OPENBLAS_NUM_THREADS",
                    "MKL_NUM_THREADS",
                    "NUMEXPR_NUM_THREADS",
                )
            }
        )
        process = subprocess.Popen(
            [sys.executable, "-m", module] + arguments,
            cwd=ROOT,
            env=child_env,
            stdout=stdout,
            stderr=stderr,
        )
        observed = psutil.Process(process.pid)
        while process.poll() is None:
            try:
                tree = [observed] + observed.children(recursive=True)
                if kernel:
                    for p in tree:
                        if p.pid not in handles:
                            handle = kernel.OpenProcess(0x1000, False, p.pid)
                            if handle:
                                handles[p.pid] = handle
                peak_rss = max(peak_rss, sum(p.memory_info().rss for p in tree))
                cpu_sample = max(
                    cpu_sample,
                    sum(p.cpu_times().user + p.cpu_times().system for p in tree),
                )
                max_threads = max(max_threads, sum(p.num_threads() for p in tree))
                if (
                    time.perf_counter() - start > timeout
                    or peak_rss > manifest["budgets"]["rss_bytes"]
                    or psutil.virtual_memory().available
                    < manifest["budgets"]["host_available_bytes"]
                ):
                    status = "analysis_resource_limit"
                    for p in reversed(tree):
                        p.kill()
                    break
            except psutil.NoSuchProcess:
                pass
            time.sleep(0.1)
        code = process.wait()
    exact_cpu = 0.0
    if kernel:
        for handle in handles.values():
            timestamps = [wintypes.FILETIME() for _ in range(4)]
            if kernel.GetProcessTimes(handle, *[ctypes.byref(t) for t in timestamps]):
                exact_cpu += sum(
                    (t.dwHighDateTime * 2**32 + t.dwLowDateTime) / 1e7
                    for t in timestamps[2:]
                )
            kernel.CloseHandle(handle)
    charged = (
        max(exact_cpu, cpu_sample) + max_threads * 0.1 + time.process_time() - own_cpu
    )
    if code and status == "complete_analysis":
        status = "analysis_error"
    write_json(
        unit / "accounting.json",
        {
            "stage": "benchmark",
            "status": status,
            "exit_code": code,
            "cpu_seconds": charged,
            "gpu_seconds": 0,
            "wall_seconds": time.perf_counter() - start,
            "peak_rss_bytes": peak_rss,
            "exact_process_tree_cpu_seconds": exact_cpu if kernel else None,
            "method": "retained Windows handles plus sampling/own-process margin"
            if kernel
            else "sampled process tree plus tail/own-process margin",
        },
    )
    print(
        {"module": module, "status": status, "cpu_seconds": charged, "log": str(unit)}
    )
    if code or status != "complete_analysis":
        raise RuntimeError("Postprocessing failed; inspect preserved logs")


if __name__ == "__main__":
    from pathlib import Path

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--module", required=True)
    parser.add_argument("arguments", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    arguments = args.arguments[1:] if args.arguments[:1] == ["--"] else args.arguments
    measured(args.root, args.module, arguments)
