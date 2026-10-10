"""One lock shared by every MeetAI GPU benchmark.

There is a single lock rather than one per script because the resource being
protected is **the GPU**, not a script. Two different benchmarks overlapping is
exactly as damaging as the same one twice: this session had two ASR passes
contend for nine minutes, which silently invalidates every latency and RTF
figure, and the co-residency harness had no lock at all while the ASR harness
had its own.

Three behaviours, each of which exists because the obvious shortcut is wrong:

**Acquire is atomic.** ``O_CREAT | O_EXCL`` makes the check and the create one
step, so two processes racing cannot both win. A "does it exist, then create
it" sequence has a window.

**A stale lock is reclaimed only after the owner is verified gone.** The lock
records the owning PID, and reclaiming happens only when that PID is confirmed
dead. An unconditional "delete and take it" would defeat the lock the first
time a run was slow, and a lock whose owner cannot be determined is refused
rather than assumed stale - refusing costs a message, guessing costs a
corrupted measurement.

**Release happens on every exit path.** Success, exception and timeout all go
through ``finally``. A lock that outlives its process turns the next legitimate
run into a false refusal.
"""

from __future__ import annotations

import contextlib
import os
import pathlib
import sys
from collections.abc import Iterator

_REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
LOCK_PATH = _REPO_ROOT / "var" / ".meetai-gpu-benchmark.lock"
"""Anchored to the repository, not to the working directory.

A relative path meant that running a harness from any other directory created
a **second, independent lock** - and because the acquire path does
``mkdir(parents=True, exist_ok=True)``, it did so silently, with no error and
no refusal. Mutual exclusion that a ``cd`` can dissolve is not mutual
exclusion, and it dissolved invisibly in exactly the situation the lock exists
for: two benchmarks running at once.
"""
"""One path for all GPU benchmarks. Ignored by an exact-name rule: a broad
``*.lock`` pattern was tried and it swallowed the tracked ``uv.lock``."""


class GpuBenchmarkBusyError(RuntimeError):
    """Another GPU benchmark holds the lock.

    The message names the lock path and the owning PID - both metadata. It
    never carries a measurement or any file content.
    """


_STILL_ACTIVE = 259
_ERROR_INVALID_PARAMETER = 87
_PROCESS_QUERY_LIMITED_INFORMATION = 0x1000


def _pid_alive_windows(pid: int) -> bool | None:
    """Liveness via Win32, because ``os.kill(pid, 0)`` does not answer this.

    Measured: ``os.kill(pid, 0)`` succeeded for a PID whose process had
    already exited and been reaped, so the lock refused to reclaim a genuinely
    stale lock. Windows keeps a PID openable while a handle to the exited
    process remains, so the only reliable answer is the exit code.
    """
    import ctypes
    from ctypes import wintypes

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    handle = kernel32.OpenProcess(_PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
    if not handle:
        # No such process is a definite "dead"; anything else is unknown, and
        # unknown must not reclaim.
        return False if ctypes.get_last_error() == _ERROR_INVALID_PARAMETER else None
    try:
        code = wintypes.DWORD()
        if not kernel32.GetExitCodeProcess(handle, ctypes.byref(code)):
            return None
        return code.value == _STILL_ACTIVE
    finally:
        kernel32.CloseHandle(handle)


def _pid_alive(pid: int) -> bool | None:
    """True, False, or None when it cannot be determined.

    The three-way answer is the point: ``None`` means **do not reclaim**.
    Guessing "dead" on an unknown owner would defeat the lock the first time a
    run was merely slow.
    """
    if pid <= 0:
        return None
    if sys.platform == "win32":
        try:
            return _pid_alive_windows(pid)
        except OSError:
            return None
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return None
    return True


def _read_owner(path: pathlib.Path) -> int | None:
    try:
        text = path.read_text(encoding="ascii").strip()
    except (OSError, UnicodeDecodeError):
        return None
    return int(text) if text.isdigit() else None


@contextlib.contextmanager
def gpu_benchmark_lock(path: pathlib.Path | None = None) -> Iterator[pathlib.Path]:
    """Hold the GPU benchmark lock for the duration of the block.

    Raises :class:`GpuBenchmarkBusyError` if another benchmark holds it, or if
    the holder cannot be verified dead.
    """
    target = path or LOCK_PATH
    target.parent.mkdir(parents=True, exist_ok=True)

    try:
        handle = os.open(str(target), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        owner = _read_owner(target)
        alive = _pid_alive(owner) if owner is not None else None
        if alive is not False:
            detail = f"pid {owner}" if owner is not None else "chu so huu khong doc duoc"
            raise GpuBenchmarkBusyError(
                f"mot benchmark GPU khac dang giu lock {target} ({detail}). "
                "Khong tu xoa lock khi chua xac minh chu so huu da chet."
            ) from None
        # Owner verified dead, so the lock is stale and may be reclaimed.
        target.unlink(missing_ok=True)
        try:
            handle = os.open(str(target), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            raise GpuBenchmarkBusyError(
                f"lock {target} bi chiem lai trong luc reclaim"
            ) from None

    try:
        os.write(handle, str(os.getpid()).encode("ascii"))
    finally:
        os.close(handle)

    try:
        yield target
    finally:
        # Every exit path: success, exception, timeout. A lock that outlives
        # its process makes the next legitimate run a false refusal.
        with contextlib.suppress(OSError):
            if _read_owner(target) == os.getpid():
                target.unlink(missing_ok=True)
