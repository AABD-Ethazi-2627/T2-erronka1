"""Local filesystem primitives; see docs/PLATFORM_SUPPORT.md for guarantees."""

import ctypes
import errno
import os
import time
from contextlib import contextmanager
from pathlib import Path


def durability_profile():
    return "windows-process-recovery" if os.name == "nt" else "posix-fsync"


def require_power_loss_durability():
    """Reject the weaker Windows contract before creating state or accepting work."""
    if os.name == "nt":
        raise OSError(
            errno.ENOTSUP,
            "Power-loss durability requires POSIX local directory fsync; "
            "Windows supports process recovery only",
        )


def sync_directory(path):
    if os.name == "nt":
        # Windows has no unprivileged equivalent of POSIX directory fsync.
        # File data is flushed before installation; metadata/power-loss safety
        # is explicitly outside the Windows process-recovery profile.
        if not Path(path).is_dir():
            raise NotADirectoryError(path)
        return
    fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def replace_file(source, target):
    if os.name != "nt":
        os.replace(source, target)
        return
    from ctypes import wintypes

    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    move = kernel.MoveFileExW
    move.argtypes = [wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.DWORD]
    move.restype = wintypes.BOOL
    # Same-volume installation, never fallback to copy/delete. The source
    # handle has already been flushed and closed by the caller.
    if not move(str(Path(source).absolute()), str(Path(target).absolute()), 0x1 | 0x8):
        raise ctypes.WinError(ctypes.get_last_error())


@contextmanager
def exclusive_lock(path, *, blocking=True):
    """OS-owned lock released on close/process death, without deleting its inode."""
    with Path(path).open("a+b") as handle:
        if os.name == "nt":
            import msvcrt

            while True:
                handle.seek(0)
                try:
                    msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
                    break
                except OSError as exc:
                    if exc.errno not in (errno.EACCES, errno.EAGAIN, errno.EDEADLK):
                        raise
                    if not blocking:
                        raise BlockingIOError(exc.errno, str(exc)) from exc
                    time.sleep(0.05)
            try:
                yield
            finally:
                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl

            flags = fcntl.LOCK_EX | (0 if blocking else fcntl.LOCK_NB)
            fcntl.flock(handle, flags)
            yield


def peak_rss_kib():
    if os.name != "nt":
        import resource
        import sys

        value = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        return value / 1024 if sys.platform == "darwin" else value
    from ctypes import wintypes

    class Counters(ctypes.Structure):
        _fields_ = [
            ("cb", wintypes.DWORD),
            ("PageFaultCount", wintypes.DWORD),
            ("PeakWorkingSetSize", ctypes.c_size_t),
            ("WorkingSetSize", ctypes.c_size_t),
            ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
            ("QuotaPagedPoolUsage", ctypes.c_size_t),
            ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
            ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
            ("PagefileUsage", ctypes.c_size_t),
            ("PeakPagefileUsage", ctypes.c_size_t),
        ]

    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.GetCurrentProcess.restype = wintypes.HANDLE
    psapi = ctypes.WinDLL("psapi", use_last_error=True)
    psapi.GetProcessMemoryInfo.argtypes = [
        wintypes.HANDLE,
        ctypes.POINTER(Counters),
        wintypes.DWORD,
    ]
    psapi.GetProcessMemoryInfo.restype = wintypes.BOOL
    counters = Counters()
    counters.cb = ctypes.sizeof(counters)
    if not psapi.GetProcessMemoryInfo(
        kernel.GetCurrentProcess(), ctypes.byref(counters), counters.cb
    ):
        raise ctypes.WinError(ctypes.get_last_error())
    return counters.PeakWorkingSetSize / 1024
