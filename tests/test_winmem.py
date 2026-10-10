"""The Windows memory probe: a struct that is the right size, and refusals.

This file tests **instrumentation**. Nothing here measures a model, loads one,
spawns a binary, opens a socket, allocates a large buffer, sets a memory limit
or writes an artifact. The one group that touches the real OS
(:class:`TestTheRealApiOnThisProcess`) reads counters for the Python process
already running the test, which proves the struct layout and the call work -
and proves nothing whatsoever about the RAM cost of any model. The CPU RAM
threshold stays pending either way, and
:class:`TestThePrototypeIsNotWiredToAnything` asserts that it does.

Three things are worth testing properly rather than exercising:

**The struct size.** ``SIZE_T`` is 8 bytes on 64-bit Windows and ``c_ulong``
is 4, so the single most likely mistake in a hand-written ctypes struct shifts
every field after the first two and still returns small plausible integers.
``test_a_c_ulong_declaration_would_be_a_different_size`` is the control: it
builds the wrong struct and shows the size assertion separates them.

**Unavailable must not be a number.** A probe that cannot measure raises. An
all-zero struct returned alongside a success code is the realistic shape of a
silently failed call, and it is refused rather than reported as 0 MiB.

**The subject is a handle.** A PID is only the bridge used to obtain one,
because the documentation is explicit that a PID stops identifying a process
once it exits while a handle does not. The mock records every call, so the
tests can show the PID is used once and never again.
"""

from __future__ import annotations

import ast
import ctypes
import os
import pathlib
import subprocess
import sys
from typing import Any

import pytest
from benchmarks import preflight as pf
from benchmarks import winmem
from benchmarks.winmem import (
    BYTES_PER_MIB,
    PROBE_FAILURE_CODES,
    PROCESS_QUERY_LIMITED_INFORMATION,
    MemoryProbeUnavailable,
    ProcessMemory,
    current_process_handle,
    open_process_for_query,
    read_process_memory,
)

from tests.conftest import code_tokens

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
BENCHMARKS = REPO_ROOT / "benchmarks"
WINMEM_SOURCE = BENCHMARKS / "winmem.py"

ERROR_ACCESS_DENIED = 5
ERROR_INVALID_PARAMETER = 87

SIZE_T_FIELDS = (
    "PeakWorkingSetSize",
    "WorkingSetSize",
    "QuotaPeakPagedPoolUsage",
    "QuotaPagedPoolUsage",
    "QuotaPeakNonPagedPoolUsage",
    "QuotaNonPagedPoolUsage",
    "PagefileUsage",
    "PeakPagefileUsage",
    "PrivateUsage",
)
"""The nine ``SIZE_T`` members, in the order psapi.h declares them."""


class FakeApi:
    """A recorded stand-in for the three kernel32 calls.

    Records rather than merely answers, because several assertions here are
    about *what was asked* - which access right, which PID, how many times a
    handle was closed - and an API that only returns values cannot be checked
    for those.
    """

    def __init__(
        self,
        *,
        handle: int = 0x1234,
        query_result: int = 1,
        error: int = 0,
        counters: dict[str, int] | None = None,
    ) -> None:
        self.handle = handle
        self.query_result = query_result
        self.error = error
        self.counters = counters or {
            "PageFaultCount": 1000,
            "WorkingSetSize": 100 * BYTES_PER_MIB,
            "PeakWorkingSetSize": 140 * BYTES_PER_MIB,
            "PagefileUsage": 80 * BYTES_PER_MIB,
            "PeakPagefileUsage": 90 * BYTES_PER_MIB,
        }
        self.opened: list[tuple[int, int]] = []
        self.closed: list[int] = []
        self.queried: list[tuple[int, int]] = []

    def open_process(self, access: int, pid: int) -> int:
        self.opened.append((access, pid))
        return self.handle

    def close_handle(self, handle: int) -> int:
        self.closed.append(handle)
        return 1

    def get_process_memory_info(self, handle: int, counters: Any) -> int:
        self.queried.append((handle, int(counters.cb)))
        if self.query_result:
            for name, value in self.counters.items():
                setattr(counters, name, value)
        return self.query_result

    def last_error(self) -> int:
        return self.error


class TestTheStructMatchesThePublishedLayout:
    """A mis-sized struct returns plausible numbers, so the size is asserted."""

    def test_the_size_is_two_dwords_plus_nine_size_t(self) -> None:
        expected = 2 * ctypes.sizeof(ctypes.c_ulong) + 9 * ctypes.sizeof(ctypes.c_size_t)
        assert ctypes.sizeof(winmem._ProcessMemoryCountersEx) == expected

    def test_a_c_ulong_declaration_would_be_a_different_size(self) -> None:
        """The control: the likely mistake, shown to be distinguishable.

        If ``c_ulong`` and ``c_size_t`` had the same width the assertion above
        would pass either way and give false credit, so this records that on
        this platform they do not.
        """

        class Wrong(ctypes.Structure):
            _fields_ = (
                ("cb", ctypes.c_ulong),
                ("PageFaultCount", ctypes.c_ulong),
                *((name, ctypes.c_ulong) for name in SIZE_T_FIELDS),
            )

        assert ctypes.sizeof(ctypes.c_size_t) == 8
        assert ctypes.sizeof(Wrong) != ctypes.sizeof(winmem._ProcessMemoryCountersEx)

    def test_every_size_t_member_is_declared_c_size_t(self) -> None:
        declared = dict(winmem._ProcessMemoryCountersEx._fields_)
        for name in SIZE_T_FIELDS:
            assert declared[name] is ctypes.c_size_t, name

    def test_the_field_order_is_the_documented_order(self) -> None:
        names = [name for name, _ in winmem._ProcessMemoryCountersEx._fields_]
        assert names == ["cb", "PageFaultCount", *SIZE_T_FIELDS]


class TestBytesToMib:
    """Rounding direction is a safety choice, so it is asserted, not assumed."""

    def test_an_exact_multiple_is_unchanged(self) -> None:
        assert winmem._ceil_mib(7 * BYTES_PER_MIB) == 7

    def test_one_byte_over_rounds_up(self) -> None:
        assert winmem._ceil_mib(7 * BYTES_PER_MIB + 1) == 8

    def test_zero_is_zero(self) -> None:
        assert winmem._ceil_mib(0) == 0

    def test_it_never_reports_less_than_the_floor_division_measure_py_uses(self) -> None:
        """Rounding up is the whole point: these figures are requirements."""
        for value in (1, BYTES_PER_MIB - 1, BYTES_PER_MIB + 1, 4438 * BYTES_PER_MIB + 7):
            assert winmem._ceil_mib(value) >= value // BYTES_PER_MIB


class TestTheRecordIsAnObservation:
    def test_it_is_frozen(self) -> None:
        record = ProcessMemory(1, 2, 3, 4, 5)
        with pytest.raises(AttributeError):
            record.working_set_bytes = 99  # type: ignore[misc]

    def test_the_mib_properties_derive_from_the_stored_bytes(self) -> None:
        record = ProcessMemory(
            page_fault_count=1,
            working_set_bytes=10 * BYTES_PER_MIB + 1,
            peak_working_set_bytes=20 * BYTES_PER_MIB,
            commit_bytes=30 * BYTES_PER_MIB + 1,
            peak_commit_bytes=40 * BYTES_PER_MIB,
        )
        assert (record.working_set_mib, record.peak_working_set_mib) == (11, 20)
        assert (record.commit_mib, record.peak_commit_mib) == (31, 40)


class TestTheRefusalCodesAreAClosedSet:
    def test_an_unknown_code_is_rejected(self) -> None:
        with pytest.raises(ValueError, match="unknown probe failure code"):
            MemoryProbeUnavailable("something-plausible")

    def test_the_message_carries_the_code(self) -> None:
        assert MemoryProbeUnavailable("access-denied").code == "access-denied"
        assert "access-denied" in str(MemoryProbeUnavailable("access-denied"))

    def test_no_code_leaks_a_path_or_a_value(self) -> None:
        """Same rule as ``refusals.py``: shape, never a value.

        These strings are pasted into research notes, so a PID, a handle or a
        staging path in one of them would travel. Nothing numeric belongs in
        a code at all, which is checkable directly.
        """
        for code in PROBE_FAILURE_CODES:
            message = str(MemoryProbeUnavailable(code))
            assert not any(ch.isdigit() for ch in message), code
            assert "/" not in message and "\\" not in message, code
            assert os.getlogin() not in message, code

    def test_every_declared_code_is_actually_raised_somewhere(self) -> None:
        """A code no path can produce is documentation pretending to be a set."""
        tree = ast.parse(WINMEM_SOURCE.read_text(encoding="utf-8"))
        raised = {
            node.args[0].value
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "MemoryProbeUnavailable"
            and node.args
            and isinstance(node.args[0], ast.Constant)
            and isinstance(node.args[0].value, str)
        }
        assert raised == set(PROBE_FAILURE_CODES)


class TestOpeningAHandleFailsClosed:
    def test_access_denied_is_its_own_reason(self) -> None:
        api = FakeApi(handle=0, error=ERROR_ACCESS_DENIED)
        with pytest.raises(MemoryProbeUnavailable) as caught:  # noqa: SIM117
            with open_process_for_query(4321, api=api):
                pytest.fail("the body must not run")
        assert caught.value.code == "access-denied"

    def test_an_exited_or_absent_pid_is_a_different_reason(self) -> None:
        """Not collapsed into "access-denied": the fixes are opposites.

        ``ERROR_INVALID_PARAMETER`` is what the documentation says an absent
        PID gives, and it means the counters are gone for good. Telling an
        operator to adjust permissions for a process that already exited sends
        them to work that cannot succeed.
        """
        api = FakeApi(handle=0, error=ERROR_INVALID_PARAMETER)
        with pytest.raises(MemoryProbeUnavailable) as caught:  # noqa: SIM117
            with open_process_for_query(4321, api=api):
                pytest.fail("the body must not run")
        assert caught.value.code == "no-such-process"

    def test_any_other_error_is_still_a_refusal_not_a_number(self) -> None:
        api = FakeApi(handle=0, error=1234)
        with pytest.raises(MemoryProbeUnavailable) as caught:  # noqa: SIM117
            with open_process_for_query(4321, api=api):
                pytest.fail("the body must not run")
        assert caught.value.code == "query-failed"

    def test_the_access_right_is_the_documented_limited_one(self) -> None:
        """The literal from the documentation, not the module's own constant.

        Found by mutation: the assertion below used to read
        ``PROCESS_QUERY_LIMITED_INFORMATION`` on both sides, so changing the
        constant to ``PROCESS_QUERY_INFORMATION`` (0x0400) left the suite
        green - it pinned that the constant was passed, not which right was
        asked for. Asking for more than is needed is exactly the kind of
        quiet widening this project does not want to discover later.
        """
        assert PROCESS_QUERY_LIMITED_INFORMATION == 0x1000
        assert PROCESS_QUERY_LIMITED_INFORMATION != 0x0400

    def test_it_asks_for_the_least_privilege_and_no_inheritance(self) -> None:
        api = FakeApi()
        with open_process_for_query(4321, api=api):
            pass
        assert api.opened == [(0x1000, 4321)]

    def test_the_handle_is_closed_even_when_the_body_raises(self) -> None:
        api = FakeApi()
        with pytest.raises(ZeroDivisionError), open_process_for_query(1, api=api):
            raise ZeroDivisionError
        assert api.closed == [api.handle]

    def test_the_pid_is_used_once_and_the_handle_thereafter(self) -> None:
        """The attributability claim, stated as a check on the calls made.

        A PID "is valid from the time the process is created until the process
        has been terminated"; a handle is "valid until closed, even after the
        process ... has been terminated". So the PID appears in exactly one
        call and the reads go to the handle.
        """
        api = FakeApi()
        with open_process_for_query(4321, api=api) as handle:
            read_process_memory(handle, api=api)
            read_process_memory(handle, api=api)
        assert len(api.opened) == 1
        assert [queried for queried, _ in api.queried] == [api.handle, api.handle]


class TestReadingCountersFailsClosed:
    def test_a_zero_return_is_a_refusal(self) -> None:
        api = FakeApi(query_result=0, error=1234)
        with pytest.raises(MemoryProbeUnavailable) as caught:
            read_process_memory(0x1234, api=api)
        assert caught.value.code == "query-failed"

    def test_a_zero_return_with_access_denied_says_so(self) -> None:
        api = FakeApi(query_result=0, error=ERROR_ACCESS_DENIED)
        with pytest.raises(MemoryProbeUnavailable) as caught:
            read_process_memory(0x1234, api=api)
        assert caught.value.code == "access-denied"

    def test_cb_is_set_from_sizeof_before_the_call(self) -> None:
        api = FakeApi()
        read_process_memory(0x1234, api=api)
        assert api.queried == [(0x1234, ctypes.sizeof(winmem._ProcessMemoryCountersEx))]

    def test_an_all_zero_struct_with_a_success_code_is_refused(self) -> None:
        """The realistic shape of a silent failure, and the reason to raise.

        Had this returned a record, the artifact would have carried
        ``working_set_mib: 0`` - a number that reads as "measured, and tiny"
        rather than "not measured". Zero is not a working set a live process
        can have.
        """
        api = FakeApi(
            counters=dict.fromkeys(
                (
                    "PageFaultCount",
                    "WorkingSetSize",
                    "PeakWorkingSetSize",
                    "PagefileUsage",
                    "PeakPagefileUsage",
                ),
                0,
            )
        )
        with pytest.raises(MemoryProbeUnavailable) as caught:
            read_process_memory(0x1234, api=api)
        assert caught.value.code == "implausible-counters"

    def test_a_peak_below_the_current_value_is_refused(self) -> None:
        api = FakeApi(
            counters={
                "PageFaultCount": 10,
                "WorkingSetSize": 100 * BYTES_PER_MIB,
                "PeakWorkingSetSize": 50 * BYTES_PER_MIB,
                "PagefileUsage": 10 * BYTES_PER_MIB,
                "PeakPagefileUsage": 10 * BYTES_PER_MIB,
            }
        )
        with pytest.raises(MemoryProbeUnavailable) as caught:
            read_process_memory(0x1234, api=api)
        assert caught.value.code == "implausible-counters"

    def test_a_commit_peak_below_the_current_commit_is_refused(self) -> None:
        api = FakeApi(
            counters={
                "PageFaultCount": 10,
                "WorkingSetSize": 100 * BYTES_PER_MIB,
                "PeakWorkingSetSize": 100 * BYTES_PER_MIB,
                "PagefileUsage": 90 * BYTES_PER_MIB,
                "PeakPagefileUsage": 10 * BYTES_PER_MIB,
            }
        )
        with pytest.raises(MemoryProbeUnavailable) as caught:
            read_process_memory(0x1234, api=api)
        assert caught.value.code == "implausible-counters"

    def test_a_zero_commit_is_accepted_because_old_windows_reports_zero(self) -> None:
        """A zero commit is a documented platform fact, not a broken read.

        The documentation says of "Windows 7 and Windows Server 2008 R2 and
        earlier: **PagefileUsage** is always zero".
        Requiring it to be nonzero would report an old OS as untrustworthy and
        hide the real distinction this module is for.
        """
        api = FakeApi(
            counters={
                "PageFaultCount": 10,
                "WorkingSetSize": 100 * BYTES_PER_MIB,
                "PeakWorkingSetSize": 100 * BYTES_PER_MIB,
                "PagefileUsage": 0,
                "PeakPagefileUsage": 0,
            }
        )
        assert read_process_memory(0x1234, api=api).commit_mib == 0

    def test_a_plausible_struct_is_reported_exactly(self) -> None:
        api = FakeApi()
        record = read_process_memory(0x1234, api=api)
        assert record == ProcessMemory(
            page_fault_count=1000,
            working_set_bytes=100 * BYTES_PER_MIB,
            peak_working_set_bytes=140 * BYTES_PER_MIB,
            commit_bytes=80 * BYTES_PER_MIB,
            peak_commit_bytes=90 * BYTES_PER_MIB,
        )


class TestAnUnsupportedPlatformRefusesRatherThanGuesses:
    def test_a_non_windows_host_gets_a_reason_not_a_zero(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Patched on the `sys` module itself, which is the same object
        # ``winmem`` reads - it does ``import sys``, not ``from sys import``.
        monkeypatch.setattr(sys, "platform", "linux")
        with pytest.raises(MemoryProbeUnavailable) as caught:
            winmem.load_api()
        assert caught.value.code == "platform-not-windows"


@pytest.mark.skipif(sys.platform != "win32", reason="the probe is Windows-only")
class TestTheRealApiOnThisProcess:
    """Instrumentation check against the process running the tests.

    This spawns nothing and allocates nothing: it reads counters for a process
    that already exists because it is us. It demonstrates that the struct,
    the prototypes and the error mapping work against the real kernel. It is
    **not** a measurement of any model, and no threshold may be derived from
    any number it produces.
    """

    def test_the_pseudo_handle_reads_back_a_live_working_set(self) -> None:
        record = read_process_memory(current_process_handle())
        assert record.working_set_bytes > 0
        assert record.peak_working_set_bytes >= record.working_set_bytes
        assert record.page_fault_count > 0

    def test_a_real_handle_for_our_own_pid_agrees_that_we_are_running(self) -> None:
        with open_process_for_query(os.getpid()) as handle:
            record = read_process_memory(handle)
        assert record.working_set_mib >= 1

    def test_the_pseudo_handle_is_the_documented_all_ones_value(self) -> None:
        # Derived from the documentation, not from the implementation: the
        # pseudo handle is ``(HANDLE)-1``, so every bit is set. Written as
        # all-ones bytes rather than by repeating the module's own expression,
        # which would pass no matter what that expression became - the same
        # tautology the access-right test above was found to have.
        all_bits = int.from_bytes(b"\xff" * ctypes.sizeof(ctypes.c_void_p), "little")
        assert current_process_handle() == all_bits
        if ctypes.sizeof(ctypes.c_void_p) == 8:
            assert current_process_handle() == 0xFFFFFFFFFFFFFFFF

    def test_the_idle_process_is_reported_absent_not_measured_as_zero(self) -> None:
        """PID 0 is documented to fail with ``ERROR_INVALID_PARAMETER``.

        A real refusal from the real kernel, which is what makes the mapping in
        the mocked tests above more than an agreement with itself.
        """
        with pytest.raises(MemoryProbeUnavailable) as caught:  # noqa: SIM117
            with open_process_for_query(0):
                pytest.fail("PID 0 must not open")
        assert caught.value.code == "no-such-process"


class TestThePrototypeIsNotWiredToAnything:
    """Scope, asserted rather than promised.

    The slice's boundary was that this module is a prototype: not connected to
    ``measure.py``, not reachable from a benchmark, not able to change what an
    artifact contains, and not able to move the RAM gate. Each of those is
    checkable now, and each would otherwise be re-argued later from memory.
    """

    def test_no_benchmark_module_imports_it(self) -> None:
        importers = []
        for path in sorted(BENCHMARKS.glob("*.py")):
            if path.name == "winmem.py":
                continue
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    names = [alias.name for alias in node.names]
                elif isinstance(node, ast.ImportFrom) and node.module:
                    names = [node.module]
                else:
                    continue
                if any(name.split(".")[-1] == "winmem" for name in names):
                    importers.append(f"{path.name}:{node.lineno}")
        assert importers == []

    def test_the_importer_scan_would_catch_one(self) -> None:
        """Control for the scan above, which passes for free if it sees nothing.

        A scan over files that happen not to contain the thing it looks for is
        a test that cannot fail. This runs the same matching over a source
        that does contain it.
        """
        tree = ast.parse("from benchmarks.winmem import read_process_memory\n")
        found = [
            node.module
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom) and node.module
            if node.module.split(".")[-1] == "winmem"
        ]
        assert found == ["benchmarks.winmem"]

    def test_it_has_no_entry_point_to_aim_at_an_arbitrary_process(self) -> None:
        tree = ast.parse(WINMEM_SOURCE.read_text(encoding="utf-8"))
        functions = {
            node.name for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)
        }
        assert "main" not in functions
        tokens = code_tokens(tree)
        assert "argparse" not in tokens
        assert "__main__" not in tokens

    def test_it_spawns_nothing_and_sets_no_limit(self) -> None:
        """The reads are the whole of it: no spawn, no quota, no allocation.

        Named individually because each is a different way this prototype
        could stop being read-only - and the job and working-set setters are
        exactly the two calls the research note decided not to use yet.

        Over :func:`code_tokens` rather than the raw text, for the reason the
        A12 scanner already had to learn: this module's own docstring explains
        that ``measure.py`` spawns ``tasklist``, and a substring scan cannot
        tell an explanation of a thing from the thing.
        """
        tokens = code_tokens(ast.parse(WINMEM_SOURCE.read_text(encoding="utf-8")))
        for forbidden in (
            "subprocess",
            "system",
            "tasklist",
            "SetProcessWorkingSetSize",
            "SetInformationJobObject",
            "CreateJobObject",
            "VirtualAlloc",
            "AssignProcessToJobObject",
        ):
            assert forbidden not in tokens, forbidden

    def test_the_token_scan_sees_code_and_ignores_prose(self) -> None:
        """Control for the shared :func:`code_tokens`, in both directions.

        A scan that ignored everything would pass the test above for free, and
        one that read prose would fail it for free. So: a call and a data
        string are seen, and a docstring saying the same words is not.
        """
        tokens = code_tokens(
            ast.parse(
                '"""This module must never call tasklist or subprocess."""\n'
                "import subprocess\n"
                'subprocess.run(["tasklist"])\n'
            )
        )
        assert {"subprocess", "run", "tasklist"} <= tokens
        prose_only = code_tokens(
            ast.parse('"""We do not call tasklist, and never import subprocess."""\n')
        )
        assert prose_only == set()

    def test_the_ram_gate_is_still_pending_and_unmoved(self) -> None:
        """This slice changed no threshold, and could not have.

        The prototype is about how a number would be *read*; whether a CPU run
        is permitted is a policy decision that is still the owner's. Asserted
        here so adding instrumentation can never be mistaken for approval.
        """
        assert pf.CPU_RAM_MARGIN_MIB is None
        assert pf.REQUIRED_FREE_RAM_CPU_MIB is None
        assert pf.ASR_CPU_RAM_MARGIN_MIB is None
        assert pf.REQUIRED_FREE_RAM_ASR_CPU_MIB is None
        assert pf.OBSERVED_ASR_CPU_PEAK_WORKING_SET_MIB is None


class RecordingApi:
    """Delegates to the real kernel32 and counts what was asked.

    Needed because the claim under test is about *how many times* the PID is
    used, and a wrapper that only returned values could not answer that. It
    adds no behaviour of its own: every call is forwarded unchanged.
    """

    def __init__(self) -> None:
        self._real = winmem.load_api()
        self.opened: list[tuple[int, int]] = []
        self.closed: list[int] = []
        self.queried: list[int] = []

    def open_process(self, access: int, pid: int) -> int:
        self.opened.append((access, pid))
        return self._real.open_process(access, pid)

    def close_handle(self, handle: int) -> int:
        self.closed.append(handle)
        return self._real.close_handle(handle)

    def get_process_memory_info(self, handle: int, counters: Any) -> int:
        self.queried.append(handle)
        return self._real.get_process_memory_info(handle, counters)

    def last_error(self) -> int:
        return self._real.last_error()


# A child that exits on its own, promptly, having done nothing but start up.
# Deliberately not given a workload: this file tests the instrumentation, and
# a child that allocated would invite reading its numbers as a measurement of
# something. `-c` with an inline script, never a file and never a binary.
IDLE_CHILD = "import sys; sys.exit(0)"


@pytest.mark.skipif(sys.platform != "win32", reason="the probe is Windows-only")
class TestARealChildProcess:
    """M2: the probe against a child, which is the case it is actually for.

    The previous slice could only read the counters of the process it already
    was, which left two claims resting on documentation alone: that a handle
    opened from a PID works, and that it stays valid after the process exits.
    Both are measured here.

    The child is this interpreter running ``-c`` with a script that exits
    immediately. No model, no binary, no allocation worth the name, no job
    object, no limit set, and nothing written to disk.
    """

    @staticmethod
    def _spawn() -> subprocess.Popen[bytes]:
        return subprocess.Popen(  # noqa: S603
            [sys.executable, "-c", IDLE_CHILD],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

    def test_every_spawn_in_this_file_is_this_interpreter_with_an_inline_script(
        self,
    ) -> None:
        """The fence, scoped to this file, because this file now spawns.

        ``test_bench_harness.py`` asserts the same property about itself only,
        so adding a spawn here would otherwise be outside every fence. Checked
        against the argv in the source, not against the file's prose.
        """
        tree = ast.parse(pathlib.Path(__file__).read_text(encoding="utf-8"))
        spawns = [
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr in {"run", "Popen", "check_output", "call"}
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "subprocess"
        ]
        assert spawns, "this class should be spawning a child"
        for spawn in spawns:
            argv = spawn.args[0]
            assert isinstance(argv, ast.List), ast.dump(spawn)
            first = argv.elts[0]
            assert isinstance(first, ast.Attribute) and first.attr == "executable", (
                "a spawned process must be sys.executable, never a binary"
            )
            assert any(
                isinstance(element, ast.Constant) and element.value == "-c"
                for element in argv.elts
            ), "sys.executable must be given an inline script, not a file"

    def test_the_pid_opens_one_handle_and_every_read_goes_to_it(self) -> None:
        """The attributability claim, now against a real child rather than a mock.

        One ``OpenProcess`` for the whole run, many reads, one ``CloseHandle``.
        That is the shape ``measure.py`` does not have: it re-resolves an image
        name on every sample, so each sample could land on a different process.
        """
        api = RecordingApi()
        child = self._spawn()
        try:
            with open_process_for_query(child.pid, api=api) as handle:
                first = read_process_memory(handle, api=api)
                second = read_process_memory(handle, api=api)
        finally:
            child.wait(timeout=60)

        assert api.opened == [(0x1000, child.pid)]
        assert api.queried == [handle, handle]
        assert api.closed == [handle]
        for record in (first, second):
            assert record.working_set_bytes > 0
            assert record.peak_working_set_bytes >= record.working_set_bytes
            assert record.peak_commit_bytes >= record.commit_bytes
            assert record.page_fault_count > 0

    def test_the_handle_stays_readable_after_the_child_has_exited(self) -> None:
        """Measured, where the last slice could only cite the documentation.

        "The handles are valid until closed, even after the process or thread
        they represent has been terminated." This is why the sampler should
        hold a handle for the whole run: the counters of a process that has
        just finished are still readable, so a run's peak cannot be lost by
        reading a moment too late.
        """
        child = self._spawn()
        with open_process_for_query(child.pid) as handle:
            assert read_process_memory(handle).working_set_bytes > 0
            assert child.wait(timeout=60) == 0
            after = read_process_memory(handle)
        assert after.peak_working_set_bytes >= after.working_set_bytes
        assert after.page_fault_count > 0

    def test_the_handle_is_closed_even_when_the_body_raises(self) -> None:
        api = RecordingApi()
        child = self._spawn()
        try:
            with pytest.raises(ZeroDivisionError):  # noqa: SIM117
                with open_process_for_query(child.pid, api=api):
                    raise ZeroDivisionError
        finally:
            child.wait(timeout=60)
        assert len(api.opened) == 1
        assert len(api.closed) == 1

    def test_the_handle_is_closed_even_when_the_child_exits_first(self) -> None:
        """Exit order must not change the cleanup, and it does not."""
        api = RecordingApi()
        child = self._spawn()
        child.wait(timeout=60)
        with open_process_for_query(child.pid, api=api) as handle:
            read_process_memory(handle, api=api)
        assert api.closed == [handle]

    def test_current_is_never_a_substitute_for_peak(self) -> None:
        """The property that makes the OS counter worth having.

        Asserted as the inequality, not as a gap: a gap of a particular size
        depends on timing and on what the child did, and a test that asserted
        one would be asserting the machine's mood. Measured separately on
        2026-10-10 and recorded in the research note: on a short child the
        working set at exit was **0.03 MiB** while the peak was **5.23 MiB**,
        so reading the current value late tells you almost nothing - which is
        exactly what a sampler reading *current* risks.
        """
        child = self._spawn()
        with open_process_for_query(child.pid) as handle:
            child.wait(timeout=60)
            final = read_process_memory(handle)
        assert final.peak_working_set_bytes >= final.working_set_bytes
        assert final.peak_working_set_mib >= final.working_set_mib
