"""Tests for the shared GPU benchmark lock (S2.2).

The lock exists because this session lost a measurement to overlapping runs:
two ASR passes contended for nine minutes, which invalidates every latency and
RTF figure, and the co-residency harness had no lock at all while the ASR
harness had its own private one. One lock protects the GPU, which is the
resource actually being shared.

Each test corresponds to a way the obvious implementation goes wrong.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "benchmarks"))

from gpulock import GpuBenchmarkBusyError, gpu_benchmark_lock


def _try_acquire(lock: Path) -> bool:
    """True if the lock could be taken (and was released again).

    A helper rather than a nested ``with``: what is under test is whether a
    *second* acquisition succeeds while the first is held, and expressing that
    as a boolean keeps every test one level deep.
    """
    try:
        with gpu_benchmark_lock(lock):
            return True
    except GpuBenchmarkBusyError:
        return False


def _refusal_message(lock: Path) -> str:
    """The message from a refused acquisition."""
    try:
        with gpu_benchmark_lock(lock):
            pytest.fail("acquire should have been refused")
    except GpuBenchmarkBusyError as error:
        return str(error)
    raise AssertionError("unreachable")


class TestSecondRunIsRefused:
    def test_second_acquire_is_refused_while_held(self, tmp_path: Path) -> None:
        lock = tmp_path / "gpu.lock"
        with gpu_benchmark_lock(lock):
            assert not _try_acquire(lock)

    def test_refusal_message_names_the_lock_and_owner(self, tmp_path: Path) -> None:
        """Metadata only: a path and a PID, never a measurement or content."""
        lock = tmp_path / "gpu.lock"
        with gpu_benchmark_lock(lock):
            message = _refusal_message(lock)
        assert "gpu.lock" in message
        assert str(os.getpid()) in message

    def test_a_live_foreign_owner_is_refused(self, tmp_path: Path) -> None:
        """A long-running sibling benchmark must block us.

        Uses a real child process so the liveness check is exercised rather
        than mocked.
        """
        lock = tmp_path / "gpu.lock"
        child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"])
        try:
            lock.write_text(str(child.pid), encoding="ascii")
            assert not _try_acquire(lock)
        finally:
            child.kill()
            child.wait(timeout=10)


class TestReleaseOnEveryExitPath:
    def test_released_after_success(self, tmp_path: Path) -> None:
        lock = tmp_path / "gpu.lock"
        with gpu_benchmark_lock(lock):
            assert lock.exists()
        assert not lock.exists()

    def test_released_after_exception(self, tmp_path: Path) -> None:
        """A lock surviving a crash turns the next legitimate run into a false
        refusal."""
        lock = tmp_path / "gpu.lock"
        with pytest.raises(RuntimeError), gpu_benchmark_lock(lock):
            raise RuntimeError("boom")
        assert not lock.exists()

    def test_released_after_timeout_style_exception(self, tmp_path: Path) -> None:
        lock = tmp_path / "gpu.lock"
        with pytest.raises(subprocess.TimeoutExpired), gpu_benchmark_lock(lock):
            raise subprocess.TimeoutExpired(cmd="x", timeout=1)
        assert not lock.exists()

    def test_a_second_run_succeeds_after_release(self, tmp_path: Path) -> None:
        lock = tmp_path / "gpu.lock"
        with gpu_benchmark_lock(lock):
            pass
        assert _try_acquire(lock)


class TestStaleLockIsNotReclaimedBlindly:
    """The dangerous shortcut: delete whatever is there and take the lock."""

    def test_unreadable_owner_is_refused_not_reclaimed(self, tmp_path: Path) -> None:
        """A lock whose owner cannot be determined is refused.

        Refusing costs a message; guessing costs a corrupted measurement.
        """
        lock = tmp_path / "gpu.lock"
        lock.write_text("not-a-pid", encoding="ascii")
        assert not _try_acquire(lock)
        # And it is still there: we did not delete somebody else's lock.
        assert lock.exists()

    def test_empty_lock_is_refused(self, tmp_path: Path) -> None:
        lock = tmp_path / "gpu.lock"
        lock.write_text("", encoding="ascii")
        assert not _try_acquire(lock)
        assert lock.exists()

    def test_verified_dead_owner_is_reclaimed(self, tmp_path: Path) -> None:
        """Only after the owner is confirmed gone.

        A real process is started and reaped so the PID is genuinely dead
        rather than merely unused. This is also the case that proved
        ``os.kill(pid, 0)`` is not a liveness check on Windows: it succeeded
        for an exited process, so the lock refused to reclaim a genuinely
        stale lock until the Win32 exit-code path was added.
        """
        child = subprocess.Popen([sys.executable, "-c", "pass"])
        child.wait(timeout=30)

        lock = tmp_path / "gpu.lock"
        lock.write_text(str(child.pid), encoding="ascii")
        with gpu_benchmark_lock(lock):
            assert lock.read_text(encoding="ascii").strip() == str(os.getpid())
        assert not lock.exists()


class TestOwnershipOnRelease:
    def test_does_not_delete_a_lock_owned_by_someone_else(self, tmp_path: Path) -> None:
        """If another process took over the path, release must leave it alone."""
        lock = tmp_path / "gpu.lock"
        with gpu_benchmark_lock(lock):
            lock.write_text("999999", encoding="ascii")
        assert lock.exists()
        assert lock.read_text(encoding="ascii").strip() == "999999"
