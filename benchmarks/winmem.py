"""Prototype: read one process's memory counters from the OS, by handle.

**Not wired to anything.** No benchmark imports this, ``measure.py`` does not
call it, and no artifact field comes from it. It exists so the instrumentation
can be reviewed and tested before any decision is made about using it, and so
that decision is not entangled with a measurement run.

Why a prototype at all - the three defects it is built to answer, each
measured in ``measure.py`` rather than supposed:

**1. We sample a number the OS already maintains exactly.**
``measure.peak_working_set_mib`` spawns ``tasklist`` every 300 ms and takes
``max()`` of the readings, so the recorded 4438 MiB is a lower bound of the
true peak, and low by an unknown amount. Windows maintains
``PeakWorkingSetSize`` - "The peak working set size, in bytes" - continuously,
for free. A sampled lower bound of an exactly-tracked quantity is an
unnecessary one.

**2. The current helper identifies its subject by image name, so the figure is
not attributable.** It passes ``IMAGENAME eq llama-cli.exe`` and keeps the
largest match, which means a second process of the same name - another
benchmark, a leftover, an unrelated tool - changes the answer silently, and a
*correct-looking* number can describe the wrong process. A handle cannot do
that: "The handles are valid until closed, even after the process or thread
they represent has been terminated", whereas "The identifier is valid from the
time the process is created until the process has been terminated". So a
handle opened once and held is the only identifier that stays bound to one
process for a whole run. This module therefore takes a **handle** and never a
name; :func:`open_process_for_query` exists to turn a PID into one, and even
that is a narrower window than a name lookup.

**3. We record only working set, and the quantities that matter differ.**
Established 2026-10-10 from the Windows documentation: a Job object limit acts
on **commit**, our RAM gate compares against **available physical**, and our
one measurement is **working set** - three different things. Commit is
reported here as well, so a future decision about a job limit can be checked
against the quantity such a limit would actually bound. ``PageFaultCount`` is
included for the same reason: a hard working-set maximum is enforced by
trimming, which converts a shortage into paging rather than a failure, and
page faults are the only signal that this happened.

What this module does **not** do, deliberately: it allocates nothing, sets no
limit, spawns no process, resolves no image name, reads no model, and has no
``main()`` - there is no way to aim it at an arbitrary process from a command
line. Reading counters is the whole of it.

Everything here is instrumentation. It produces **no** figure about any model,
and running its tests measures nothing but this code. The CPU RAM threshold
stays pending; see ``docs/research/2026-10-10-gioi-han-ram-windows-cho-cpu.md``.
"""

from __future__ import annotations

import ctypes
import sys
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Protocol

BYTES_PER_MIB = 1024 * 1024

PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
"""Least privilege that answers the question.

``GetProcessMemoryInfo`` documents "The handle must have the
**PROCESS_QUERY_INFORMATION** or **PROCESS_QUERY_LIMITED_INFORMATION** access
right", so the weaker of the two is enough. It is also the one not refused by
a protected process, and it cannot be escalated the way ``PROCESS_DUP_HANDLE``
can. Asking for more would buy nothing and would make this module a worse
neighbour than ``tasklist``.
"""

ERROR_ACCESS_DENIED = 5
ERROR_INVALID_PARAMETER = 87

PROBE_FAILURE_CODES: frozenset[str] = frozenset(
    {
        "platform-not-windows",
        "api-unavailable",
        "access-denied",
        "no-such-process",
        "query-failed",
        "implausible-counters",
    }
)
"""Every reason this module can decline to produce a number.

A closed set for the same reason ``refusals.ARTIFACT_ROLES`` is one: the codes
reach stderr and get pasted into notes, so they must describe the *shape* of
the failure and never a path, a PID or a raw OS error string. Distinguished
rather than collapsed because the fixes differ - "access-denied" wants a
different account, "no-such-process" means the subject is already gone and its
counters are unrecoverable, and "implausible-counters" means do not trust this
build at all.
"""


class MemoryProbeUnavailable(RuntimeError):
    """No measurement could be made, and no substitute is offered.

    The point of raising instead of returning zeros, ``-1`` or ``"?"``: a
    sentinel that fits in an int field gets averaged, compared and written to
    an artifact as though it were observed. This project already had that bug
    once, where an unavailable VRAM reading became the string ``"?"`` and
    reached ``int()``. An exception cannot be mistaken for a measurement.
    """

    def __init__(self, code: str) -> None:
        if code not in PROBE_FAILURE_CODES:
            raise ValueError(f"unknown probe failure code ({len(code)} chars)")
        super().__init__(f"process-memory-probe-unavailable: {code}")
        self.code = code


@dataclass(frozen=True)
class ProcessMemory:
    """Five counters for one process, in bytes, as the OS reported them.

    Bytes, not MiB, are the stored form: the conversion loses information and
    doing it once at the edge means two callers cannot disagree about it.
    Frozen because these are observations of a moment; a counter that can be
    reassigned invites a later "correction" that is really a guess.
    """

    page_fault_count: int
    working_set_bytes: int
    peak_working_set_bytes: int
    commit_bytes: int
    peak_commit_bytes: int

    @property
    def working_set_mib(self) -> int:
        return _ceil_mib(self.working_set_bytes)

    @property
    def peak_working_set_mib(self) -> int:
        return _ceil_mib(self.peak_working_set_bytes)

    @property
    def commit_mib(self) -> int:
        return _ceil_mib(self.commit_bytes)

    @property
    def peak_commit_mib(self) -> int:
        return _ceil_mib(self.peak_commit_bytes)


def _ceil_mib(value: int) -> int:
    """Bytes to MiB, rounded **up**.

    Deliberately different from ``measure.peak_working_set_mib``, which floors
    (``kib // 1024``). These numbers are read as "how much was needed", and
    flooring a requirement reports slightly less than was actually used - on
    the unsafe side, every time, for a quantity whose whole purpose is to keep
    a host from running out. Rounding up costs at most 1 MiB of pessimism.
    """
    return -(-value // BYTES_PER_MIB)


class _ProcessMemoryCountersEx(ctypes.Structure):
    """``PROCESS_MEMORY_COUNTERS_EX`` exactly as psapi.h declares it.

    ``SIZE_T`` is :class:`ctypes.c_size_t`, not ``c_ulong``: on 64-bit Windows
    ``c_ulong`` is 4 bytes, so declaring it that way would mis-size the struct,
    make ``cb`` wrong, and shift every field after the first two - producing
    numbers that look plausible and are not. ``tests/test_winmem.py`` pins the
    size against ``sizeof(c_size_t)`` so this cannot regress quietly.

    ``PrivateUsage`` is declared because the struct layout requires it, and is
    deliberately not exposed: the documentation says it is "Same as
    **PagefileUsage**", and two names for one number is how a reader comes to
    believe two things were measured.
    """

    _fields_ = (
        ("cb", ctypes.c_ulong),
        ("PageFaultCount", ctypes.c_ulong),
        ("PeakWorkingSetSize", ctypes.c_size_t),
        ("WorkingSetSize", ctypes.c_size_t),
        ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
        ("QuotaPagedPoolUsage", ctypes.c_size_t),
        ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
        ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
        ("PagefileUsage", ctypes.c_size_t),
        ("PeakPagefileUsage", ctypes.c_size_t),
        ("PrivateUsage", ctypes.c_size_t),
    )


class _Api(Protocol):
    """The three calls this module makes, so tests can supply them.

    A seam rather than a patched ``ctypes``: monkeypatching ``ctypes.WinDLL``
    globally would change what every other test in the suite is running on.
    This keeps the fake local to the call.
    """

    def get_process_memory_info(
        self, handle: int, counters: _ProcessMemoryCountersEx
    ) -> int: ...

    def open_process(self, access: int, pid: int) -> int: ...

    def close_handle(self, handle: int) -> int: ...

    def last_error(self) -> int: ...


class _Kernel32Api:
    """The real thing: ``kernel32`` via ctypes, with explicit prototypes.

    The prototypes are not decoration. ``ctypes`` defaults ``restype`` to
    ``c_int``, which is 32-bit; a ``HANDLE`` from ``OpenProcess`` is a pointer,
    so leaving the default would truncate it on 64-bit Windows and then pass
    the truncated value back in - a bug that fails sometimes rather than
    always, which is the worst kind to have in a measurement path.
    """

    def __init__(self) -> None:
        if sys.platform != "win32":
            raise MemoryProbeUnavailable("platform-not-windows")
        try:
            # Documented to live in Kernel32.dll from Windows 7 onwards; the
            # Psapi.dll wrapper is only needed for pre-7 targets.
            dll = ctypes.WinDLL("kernel32", use_last_error=True)
            self._get = dll.K32GetProcessMemoryInfo
            self._open = dll.OpenProcess
            self._close = dll.CloseHandle
        except (AttributeError, OSError) as exc:
            raise MemoryProbeUnavailable("api-unavailable") from exc
        self._get.argtypes = (
            ctypes.c_void_p,
            ctypes.POINTER(_ProcessMemoryCountersEx),
            ctypes.c_ulong,
        )
        self._get.restype = ctypes.c_int
        self._open.argtypes = (ctypes.c_ulong, ctypes.c_int, ctypes.c_ulong)
        self._open.restype = ctypes.c_void_p
        self._close.argtypes = (ctypes.c_void_p,)
        self._close.restype = ctypes.c_int

    def get_process_memory_info(
        self, handle: int, counters: _ProcessMemoryCountersEx
    ) -> int:
        return int(
            self._get(
                ctypes.c_void_p(handle),
                ctypes.byref(counters),
                ctypes.sizeof(counters),
            )
        )

    def open_process(self, access: int, pid: int) -> int:
        # bInheritHandle is FALSE: a child must not silently inherit the right
        # to query a process it was never given.
        return int(self._open(access, 0, pid) or 0)

    def close_handle(self, handle: int) -> int:
        return int(self._close(ctypes.c_void_p(handle)))

    def last_error(self) -> int:
        return ctypes.get_last_error()


def load_api() -> _Api:
    """The real API, or a refusal. Never a stub that returns zeros.

    Separate from :func:`read_process_memory` so a caller on a non-Windows
    host finds out at load time, with the reason, rather than receiving a
    number-shaped answer.
    """
    return _Kernel32Api()


def current_process_handle() -> int:
    """The pseudo-handle for this process.

    ``GetCurrentProcess`` returns a pseudo handle that "is valid only for the
    calling process", documented as ``(HANDLE)-1``; it needs no access request
    and must not be closed. Used only to smoke-test the instrumentation
    against a process we already are - which proves the struct and the call
    work, and nothing whatsoever about any model.
    """
    # int() because typeshed widens `int ** int` to Any: the exponent could be
    # negative in general, which would make the result a float.
    return int(2 ** (8 * ctypes.sizeof(ctypes.c_void_p))) - 1


@contextmanager
def open_process_for_query(pid: int, *, api: _Api | None = None) -> Iterator[int]:
    """Open a handle for querying, and close it. Fails closed on every error.

    The PID is only ever used *here*, to obtain the handle; the handle is what
    the caller holds afterwards. That matters because a PID "is valid from the
    time the process is created until the process has been terminated" and may
    then describe someone else, while a handle stays bound to the one process
    even after it exits. So this is the narrow bridge between the two, not a
    lookup to be repeated per sample.

    The error mapping is not cosmetic. An exited or never-existing PID gives
    ``ERROR_INVALID_PARAMETER``; a live process we may not query gives
    ``ERROR_ACCESS_DENIED``. Collapsing them would send an operator to fix
    permissions for a process that is simply gone.
    """
    resolved = load_api() if api is None else api
    handle = resolved.open_process(PROCESS_QUERY_LIMITED_INFORMATION, pid)
    if not handle:
        error = resolved.last_error()
        if error == ERROR_ACCESS_DENIED:
            raise MemoryProbeUnavailable("access-denied")
        if error == ERROR_INVALID_PARAMETER:
            raise MemoryProbeUnavailable("no-such-process")
        raise MemoryProbeUnavailable("query-failed")
    try:
        yield handle
    finally:
        resolved.close_handle(handle)


def read_process_memory(handle: int, *, api: _Api | None = None) -> ProcessMemory:
    """Read the five counters for the process behind ``handle``.

    ``cb`` is set from ``sizeof`` rather than a literal, because the kernel
    uses it to decide which struct version it was handed; a stale literal is
    how a caller gets a short read filled with whatever was on the stack.
    """
    resolved = load_api() if api is None else api
    counters = _ProcessMemoryCountersEx()
    counters.cb = ctypes.sizeof(_ProcessMemoryCountersEx)
    if not resolved.get_process_memory_info(handle, counters):
        error = resolved.last_error()
        if error == ERROR_ACCESS_DENIED:
            raise MemoryProbeUnavailable("access-denied")
        raise MemoryProbeUnavailable("query-failed")
    return _validated(counters)


def _validated(counters: _ProcessMemoryCountersEx) -> ProcessMemory:
    """Turn the struct into a record, or refuse it.

    These checks are what stops a failed call from becoming a measurement of
    zero. ``GetProcessMemoryInfo`` can return nonzero while the struct is
    wrong - a mis-sized ``cb``, a shim, an emulation layer - and every such
    outcome arrives as small plausible integers. A live process always has a
    nonzero working set, and a peak is never below the current value, so both
    are checkable without knowing anything about the workload.

    Commit is checked for ordering but **not** required to be nonzero: the
    documentation records that on "Windows 7 and Windows Server 2008 R2 and
    earlier: **PagefileUsage** is always zero". Demanding a nonzero commit
    would report an old OS as a broken one.
    """
    page_faults = int(counters.PageFaultCount)
    working_set = int(counters.WorkingSetSize)
    peak_working_set = int(counters.PeakWorkingSetSize)
    commit = int(counters.PagefileUsage)
    peak_commit = int(counters.PeakPagefileUsage)
    plausible = (
        working_set > 0
        and page_faults >= 0
        and commit >= 0
        and peak_working_set >= working_set
        and peak_commit >= commit
    )
    if not plausible:
        raise MemoryProbeUnavailable("implausible-counters")
    return ProcessMemory(
        page_fault_count=page_faults,
        working_set_bytes=working_set,
        peak_working_set_bytes=peak_working_set,
        commit_bytes=commit,
        peak_commit_bytes=peak_commit,
    )


__all__ = [
    "BYTES_PER_MIB",
    "PROBE_FAILURE_CODES",
    "PROCESS_QUERY_LIMITED_INFORMATION",
    "MemoryProbeUnavailable",
    "ProcessMemory",
    "current_process_handle",
    "load_api",
    "open_process_for_query",
    "read_process_memory",
]
