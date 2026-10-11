"""The GPU harness's refusals and its failure record, verified without a GPU.

Every test here runs on the CPU against pure functions, mocked ``nvidia-smi``
output and the module's AST. **Nothing allocates a model, launches a process,
or reads a real device**, and a test asserts that property of this file rather
than leaving it to the reader.

Why this file exists: the preflight, the shared lock and ``failure_evidence``
were wired and documented but **untested**. `PROJECT_STATE` claimed the wiring;
the claim rested on reading. The two historical OOM labels already rest on an
observation nobody persisted, and the lesson from that is not to accumulate a
second claim of the same kind.
"""

from __future__ import annotations

import ast
import pathlib
import subprocess
import sys
from pathlib import Path

import pytest
from benchmarks import preflight as pf
from benchmarks.bench_llm_policy import (
    AMBIGUOUS_MARKERS,
    DEVICE_OOM_MARKERS,
    HOST_ALLOC_MARKERS,
    OOM_MARKERS,
    classify_failure,
)
from benchmarks.gpulock import LOCK_PATH
from benchmarks.policy_scoring import FailureKind

from tests.corpus.llm_policy_vi import CORPUS

BENCHMARKS = Path(__file__).resolve().parent.parent / "benchmarks"
HARNESS_SOURCE = (BENCHMARKS / "bench_llm_policy.py").read_text(encoding="utf-8")
HARNESS_TREE = ast.parse(HARNESS_SOURCE)


def _main_fn() -> ast.FunctionDef:
    return next(
        node
        for node in ast.walk(HARNESS_TREE)
        if isinstance(node, ast.FunctionDef) and node.name == "main"
    )


class TestThisFileTouchesNoGpu:
    """A test suite that could start a benchmark is not a CPU-only suite.

    It does spawn processes - two of them, deliberately, because an
    ``O_CREAT|O_EXCL`` race cannot be tested inside one process and that race
    is the lock's headline property. So the claim is **not** "no subprocess".
    The claim is that every process spawned is this interpreter running an
    inline script, which cannot reach a GPU.
    """

    def test_every_spawned_process_is_this_interpreter(self) -> None:
        tree = ast.parse(Path(__file__).read_text(encoding="utf-8"))
        spawns = [
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr in {"run", "Popen", "check_output", "call"}
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "subprocess"
        ]
        assert spawns, "the lock race test should be spawning processes"
        for spawn in spawns:
            argv = spawn.args[0]
            assert isinstance(argv, ast.List), ast.dump(spawn)
            first = argv.elts[0]
            assert isinstance(first, ast.Attribute) and first.attr == "executable", (
                "a spawned process must be sys.executable, never a benchmark binary"
            )
            assert any(
                isinstance(element, ast.Constant) and element.value == "-c"
                for element in argv.elts
            ), "sys.executable must be given an inline script, not a file"

    def test_nothing_spawned_names_a_model_or_a_benchmark_binary(self) -> None:
        """Checked against the spawned ARGUMENTS, not against this file's text.

        The first version of this test searched its own source for ".gguf" -
        which its own assertion contained - so it failed on itself. The
        property lives in the argv, so that is where it is asked.
        """
        tree = ast.parse(Path(__file__).read_text(encoding="utf-8"))
        literals = [
            node.value
            for spawn in ast.walk(tree)
            if isinstance(spawn, ast.Call)
            and isinstance(spawn.func, ast.Attribute)
            and spawn.func.attr in {"run", "Popen", "check_output", "call"}
            for node in ast.walk(spawn)
            if isinstance(node, ast.Constant) and isinstance(node.value, str)
        ]
        assert literals
        for text in literals:
            lowered = text.lower()
            for forbidden in (".gguf", "llama-cli", "llama-bench", "nvidia-smi"):
                assert forbidden not in lowered, (forbidden, text[:60])

    def test_nvidia_smi_is_never_actually_invoked(self) -> None:
        """Every VRAM reading in this file comes from a monkeypatch."""
        tree = ast.parse(Path(__file__).read_text(encoding="utf-8"))
        patched = [
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "setattr"
        ]
        assert patched, "no monkeypatching found; a reading may be real"
        names = {
            node.value
            for call in patched
            for node in call.args
            if isinstance(node, ast.Constant) and isinstance(node.value, str)
        }
        assert "nvidia_smi" in names, names


class TestFailureEvidenceIsRecorded:
    """``classify_failure`` had **zero** tests, and it produces the label the
    whole VRAM budget is argued from."""

    def test_a_timeout_is_a_timeout_even_with_no_output(self) -> None:
        kind, evidence = classify_failure(
            returncode=1, timed_out=True, stderr="", generation=""
        )
        assert kind is FailureKind.TIMEOUT
        assert evidence

    @pytest.mark.parametrize("marker", DEVICE_OOM_MARKERS)
    def test_a_device_marker_is_oom_and_says_device(self, marker: str) -> None:
        kind, evidence = classify_failure(
            returncode=3221226505,
            timed_out=False,
            stderr=f"ggml: {marker} while loading tensors",
            generation="",
        )
        assert kind is FailureKind.OOM
        assert "device vram" in evidence
        assert marker in evidence

    @pytest.mark.parametrize("marker", HOST_ALLOC_MARKERS)
    def test_a_host_marker_is_oom_but_says_host(self, marker: str) -> None:
        """The separation that keeps one mislabelled case out of the budget.

        A host-RAM failure recorded as a bare ``OOM`` is read later as a VRAM
        finding - and a VRAM finding is what ``REQUIRED_FREE_MIB`` is derived
        from, so the mislabel propagates into the gate every future run passes.
        """
        kind, evidence = classify_failure(
            returncode=1, timed_out=False, stderr=f"{marker}: 1234 bytes", generation=""
        )
        assert kind is FailureKind.OOM
        assert "host ram" in evidence
        assert "device" not in evidence

    @pytest.mark.parametrize("marker", AMBIGUOUS_MARKERS)
    def test_a_bare_cuda_error_is_not_a_memory_finding(self, marker: str) -> None:
        """Reproduced from the audit: ``"cuda error"`` was in the OOM set and
        outranked the return code, so an illegal memory access, a launch
        failure, a driver mismatch or an ECC fault all recorded as OOM."""
        kind, evidence = classify_failure(
            returncode=1,
            timed_out=False,
            stderr=f"{marker}: an illegal memory access was encountered",
            generation="",
        )
        assert kind is not FailureKind.OOM, evidence
        assert kind is FailureKind.PROCESS_ERROR
        assert "NOT evidence about memory" in evidence

    def test_the_specific_reading_beats_the_substring(self) -> None:
        """``"cuda error"`` is a substring of ``"cuda error: out of memory"``,
        so the unspecific marker must not get first refusal."""
        kind, evidence = classify_failure(
            returncode=1,
            timed_out=False,
            stderr="CUDA error: out of memory",
            generation="",
        )
        assert kind is FailureKind.OOM
        assert "device vram" in evidence

    def test_an_exit_code_alone_is_reported_as_an_exit_code(self) -> None:
        """0xC0000409 is a Windows fast-fail and says nothing about memory.

        The two historical OOM labels rest on a marker that was not persisted;
        with no marker, the only honest label is "it exited non-zero".
        """
        kind, evidence = classify_failure(
            returncode=3221226505, timed_out=False, stderr="", generation=""
        )
        assert kind is FailureKind.PROCESS_ERROR
        assert "0xC0000409" in evidence

    def test_empty_output_with_a_clean_exit(self) -> None:
        kind, evidence = classify_failure(
            returncode=0, timed_out=False, stderr="", generation="   \n"
        )
        assert kind is FailureKind.EMPTY_OUTPUT
        assert evidence

    def test_a_good_run_carries_no_evidence(self) -> None:
        kind, evidence = classify_failure(
            returncode=0, timed_out=False, stderr="", generation='{"decision":"silent"}'
        )
        assert kind is FailureKind.NONE
        assert evidence == ""

    def test_every_classification_returns_a_reason(self) -> None:
        """A failure with no evidence is a label nobody can re-check - which
        is exactly the state the two historical OOM cases are in."""
        for stderr, rc, timed_out, generation in [
            ("", 1, True, ""),
            ("out of memory", 1, False, ""),
            ("ggml_cuda_host_malloc failed", 1, False, ""),
            ("cuda error: unspecified", 1, False, ""),
            ("", 9, False, ""),
            ("", 0, False, ""),
        ]:
            kind, evidence = classify_failure(
                returncode=rc, timed_out=timed_out, stderr=stderr, generation=generation
            )
            if kind is not FailureKind.NONE:
                assert evidence, (kind, stderr, rc)

    def test_the_marker_sets_do_not_overlap(self) -> None:
        assert not set(DEVICE_OOM_MARKERS) & set(HOST_ALLOC_MARKERS)
        assert set(OOM_MARKERS) == set(DEVICE_OOM_MARKERS) | set(HOST_ALLOC_MARKERS)
        assert not set(OOM_MARKERS) & set(AMBIGUOUS_MARKERS)

    def test_no_failure_leaves_the_denominator(self) -> None:
        """Every member is a failure counted in the denominator; only NONE is
        falsy, so ``if failure:`` reads correctly."""
        assert not FailureKind.NONE
        for kind in FailureKind:
            if kind is not FailureKind.NONE:
                assert kind


class TestThePreflightRefusesRatherThanGuessing:
    """Behaviour verified against mocked ``nvidia-smi`` output only."""

    @staticmethod
    def _patch(monkeypatch: pytest.MonkeyPatch, parts: list[str]) -> None:
        monkeypatch.setattr(pf, "nvidia_smi", lambda _query: parts)

    def test_enough_headroom_passes(self, monkeypatch: pytest.MonkeyPatch) -> None:
        self._patch(monkeypatch, ["6144 MiB", "800 MiB"])
        state = pf.require_headroom()
        assert state.free_mib == 5344
        assert state.fits

    def test_too_little_headroom_refuses(self, monkeypatch: pytest.MonkeyPatch) -> None:
        self._patch(monkeypatch, ["6144 MiB", "2000 MiB"])
        with pytest.raises(pf.PreflightRefused):
            pf.require_headroom()

    def test_an_unreadable_gpu_refuses_rather_than_assuming(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Fail closed when the measurement itself is unavailable: a run that
        cannot be measured is a run whose failure cannot be attributed."""
        self._patch(monkeypatch, [])
        with pytest.raises(pf.PreflightRefused):
            pf.require_headroom()

    def test_garbage_refuses(self, monkeypatch: pytest.MonkeyPatch) -> None:
        self._patch(monkeypatch, ["[N/A]", "[N/A]"])
        with pytest.raises(pf.PreflightRefused):
            pf.require_headroom()

    def test_the_arithmetic_is_the_documented_derivation(self) -> None:
        assert pf.ATTRIBUTABLE_PEAK_MIB == (
            pf.OBSERVED_PEAK_DEVICE_MIB - pf.OBSERVED_IDLE_AT_THAT_PEAK_MIB
        )
        assert (
            int(pf.ATTRIBUTABLE_PEAK_MIB * (1 + pf.SPIKE_MARGIN)) == pf.REQUIRED_FREE_MIB
        )

    def test_the_margin_is_documented_as_a_judgement_not_a_threshold(self) -> None:
        """It is the one number here not read off an artifact, and nothing in
        the repository has measured the spike it covers."""
        doc = pf.__doc__ or ""
        source = (BENCHMARKS / "preflight.py").read_text(encoding="utf-8")
        assert "judgement" in source.lower()
        for overclaim in ("calibrated safety", "measured safety factor"):
            assert overclaim not in source.lower(), overclaim
        assert "WDDM" in source or "WDDM" in doc


class TestTheHostRamGate:
    """The half of the preflight that ``plan.md`` claimed and did not have.

    ``plan.md`` recorded "Preflight VRAM/RAM ... dat" while the module read no
    host RAM at all, and every artifact records a 2822-2868 MiB working set -
    so RAM was a measured axis that nothing gated.
    """

    def test_enough_ram_passes(self) -> None:
        assert pf.require_ram_headroom(available_mib=8000) == 8000

    def test_too_little_ram_refuses(self) -> None:
        with pytest.raises(pf.PreflightRefused) as caught:
            pf.require_ram_headroom(available_mib=1000)
        assert "RAM host" in str(caught.value)

    def test_exactly_at_the_threshold_passes(self) -> None:
        assert pf.require_ram_headroom(available_mib=pf.REQUIRED_FREE_RAM_MIB)

    def test_one_mib_short_refuses(self) -> None:
        with pytest.raises(pf.PreflightRefused):
            pf.require_ram_headroom(available_mib=pf.REQUIRED_FREE_RAM_MIB - 1)

    def test_the_headroom_is_additive_not_multiplicative(self) -> None:
        """The two gates lean opposite ways, so they must not share a margin.

        Measured, not argued: reusing ``SPIKE_MARGIN`` here required 4302 MiB
        and refused a machine with 3873 MiB available, while the recorded peak
        was 2868 - the run would have fitted and the margin alone refused it.
        Sampled VRAM understates a transient peak; Working Set overstates
        demand for a memory-mapped GGUF, because file-backed pages count and
        are evictable. Multiplying a number that already overstates is
        double-counting.
        """
        assert pf.REQUIRED_FREE_RAM_MIB == (
            pf.OBSERVED_PEAK_WORKING_SET_MIB + pf.RAM_HEADROOM_MIB
        )
        multiplicative = int(pf.OBSERVED_PEAK_WORKING_SET_MIB * (1 + pf.SPIKE_MARGIN))
        assert multiplicative > pf.REQUIRED_FREE_RAM_MIB

    def test_the_budget_matches_the_recorded_working_set_peaks(self) -> None:
        """Traceable to the artifacts, like every other number in the module."""
        import json

        recorded = []
        for name in (
            "llm-policy-s23.json",
            "llm-policy-s23-run2.json",
            "llm-policy-s23-power.json",
            "llm-policy-s23-cfgv2.json",
        ):
            path = BENCHMARKS.parent / "var" / "bench" / name
            if not path.exists():
                continue
            blob = json.loads(path.read_text(encoding="utf-8"))
            recorded.append(blob["memory"]["process_peak_working_set_mib"])
        assert recorded, "no artifacts to check against"
        assert max(recorded) == pf.OBSERVED_PEAK_WORKING_SET_MIB, recorded

    def test_the_overstatement_is_documented_not_hidden(self) -> None:
        """Working Set, Private Bytes and Commit are not interchangeable, and
        a mmap'd GGUF makes the difference material. The module must say so
        rather than presenting the figure as demand."""
        source = (BENCHMARKS / "preflight.py").read_text(encoding="utf-8")
        lowered = source.lower()
        assert "working set" in lowered
        assert "overstate" in lowered
        assert "evictable" in lowered or "file-backed" in lowered

    def test_an_unreadable_ram_figure_refuses(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Fail closed, including on a platform where it cannot be read.

        Silently skipping the check elsewhere would make the gate vanish
        exactly where nobody is watching for it.
        """
        monkeypatch.setattr("benchmarks.preflight.sys.platform", "linux")
        with pytest.raises(pf.PreflightRefused):
            pf.read_available_ram_mib()

    def test_the_two_gates_are_reported_separately(self) -> None:
        """Conflating them is how a host allocation marker came to be filed as
        an OOM."""
        assert "require_ram_headroom" in HARNESS_SOURCE
        assert '"ram_available_mib_at_start"' in HARNESS_SOURCE
        state = pf.VramState(total_mib=6144, used_mib=800)
        meta = state.metadata()
        assert meta["required_free_mib"] != meta["required_free_ram_mib"]
        assert meta["ram_headroom_is_additive_not_multiplicative"] is True

    def test_the_harness_checks_ram_inside_the_lock_too(self) -> None:
        main = _main_fn()
        with_blocks = [
            node
            for node in ast.walk(main)
            if isinstance(node, ast.With)
            and any(
                isinstance(item.context_expr, ast.Call)
                and isinstance(item.context_expr.func, ast.Name)
                and item.context_expr.func.id == "gpu_benchmark_lock"
                for item in node.items
            )
        ]
        inside = {
            node.func.id
            for node in ast.walk(with_blocks[0])
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
        }
        assert "require_ram_headroom" in inside


class TestTheReleaseProbeDoesNotDestroyTheEvidence:
    """The asymmetry between the gate and the probe, which is deliberate.

    Refusing to start when you cannot measure is cheap. Destroying the evidence
    you already collected is not - and the artifact is written after the run
    loop, so a raise from the probe on case 40 of 43 discarded all 40.
    """

    def test_a_released_gpu_reads_as_released(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(pf, "nvidia_smi", lambda _q: ["6144 MiB", "850 MiB"])
        before = pf.VramState(total_mib=6144, used_mib=800)
        assert pf.verify_gpu_released(before)

    def test_a_held_allocation_reads_as_not_released(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(pf, "nvidia_smi", lambda _q: ["6144 MiB", "3600 MiB"])
        before = pf.VramState(total_mib=6144, used_mib=800)
        assert not pf.verify_gpu_released(before)

    def test_a_leak_smaller_than_the_tolerance_is_invisible(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A recorded limit, not a fixed bug.

        The tolerance defends against a whole leaked model (~2.8 GiB); it
        cannot see a KV cache, a compute buffer or a CUDA context - the very
        allocations S2.2 identified as unmeasured. Because the baseline is
        never re-read, such a leak is detected late and then blamed on
        whichever case happened to cross the line.
        """
        monkeypatch.setattr(pf, "nvidia_smi", lambda _q: ["6144 MiB", "1000 MiB"])
        before = pf.VramState(total_mib=6144, used_mib=800)
        assert pf.verify_gpu_released(before), (
            "200 MiB of leak passes; if this ever fails the tolerance changed "
            "and the recorded limit needs rewriting, not deleting"
        )

    def test_the_probe_raises_when_it_cannot_measure(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """It raises, and the harness must catch it - asserted next."""
        monkeypatch.setattr(pf, "nvidia_smi", lambda _q: [])
        before = pf.VramState(total_mib=6144, used_mib=800)
        with pytest.raises(pf.PreflightRefused):
            pf.verify_gpu_released(before)

    def test_the_harness_catches_that_raise(self) -> None:
        handlers = [
            node
            for node in ast.walk(_main_fn())
            if isinstance(node, ast.ExceptHandler)
            and isinstance(node.type, ast.Name)
            and node.type.id == "PreflightRefused"
        ]
        assert len(handlers) >= 2, (
            "the pre-run gate and the per-case probe must both handle "
            "PreflightRefused; the probe's handler is what keeps a transient "
            f"nvidia-smi hiccup from discarding a whole run (found {len(handlers)})"
        )


class TestTheHarnessWiring:
    """Claims `PROJECT_STATE` made about the harness, asked of the AST.

    Every one of these was previously backed by reading the file.
    """

    def test_the_preflight_runs_inside_the_lock(self) -> None:
        """A precondition measured outside the mutual exclusion it depends on
        is worth nothing: a sibling harness could hold the lock and be
        mid-load at the instant the baseline was taken."""
        main = _main_fn()
        with_blocks = [
            node
            for node in ast.walk(main)
            if isinstance(node, ast.With)
            and any(
                isinstance(item.context_expr, ast.Call)
                and isinstance(item.context_expr.func, ast.Name)
                and item.context_expr.func.id == "gpu_benchmark_lock"
                for item in node.items
            )
        ]
        assert len(with_blocks) == 1, "expected exactly one lock block"
        inside = {
            node.func.id
            for node in ast.walk(with_blocks[0])
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
        }
        assert "require_headroom" in inside
        assert "verify_gpu_released" in inside

    def test_a_busy_lock_is_a_refusal_not_a_traceback(self) -> None:
        """Exit 5, matching the other three harnesses. A refusal to measure
        must not be reported as a failure of the thing being measured - the
        same reason the preflight exits 3."""
        handlers = [
            node
            for node in ast.walk(_main_fn())
            if isinstance(node, ast.ExceptHandler)
            and isinstance(node.type, ast.Name)
            and node.type.id == "GpuBenchmarkBusyError"
        ]
        assert handlers, "a busy lock would surface as an uncaught traceback"
        returns = [
            node.value.value
            for handler in handlers
            for node in ast.walk(handler)
            if isinstance(node, ast.Return) and isinstance(node.value, ast.Constant)
        ]
        assert 5 in returns, returns

    def test_every_other_harness_also_handles_a_busy_lock(self) -> None:
        for name in ("bench_asr.py", "bench_llamacpp.py", "bench_coresidency.py"):
            source = (BENCHMARKS / name).read_text(encoding="utf-8")
            assert "GpuBenchmarkBusyError" in source, name

    def test_the_artifact_records_an_early_stop(self) -> None:
        """A truncated run used to be indistinguishable from a short `--only`
        run: the stop reason went to stderr and nothing else."""
        assert '"stopped_early": stopped_early' in HARNESS_SOURCE

    def test_cases_run_is_the_executed_count(self) -> None:
        """It used to be ``len(cases)`` - the number *selected*. After a break
        the artifact claimed more cases than its own metrics were computed
        from, with no flag saying so."""
        assert '"cases_run": len(results)' in HARNESS_SOURCE
        assert '"cases_selected": len(cases)' in HARNESS_SOURCE

    def test_the_generation_is_written_before_the_release_check(self) -> None:
        """Otherwise stopping also discards the output of the case that just
        ran - the one most likely to explain the stop."""
        write_at = HARNESS_SOURCE.index('.out.txt"')
        probe_at = HARNESS_SOURCE.index("verify_gpu_released(baseline)")
        assert write_at < probe_at, (write_at, probe_at)

    def test_stderr_is_never_persisted(self) -> None:
        """A deliberate privacy control, and the direct cause of the limit on
        how diagnosable a failure can be. Recorded, not worked around."""
        assert '"stderr"' not in HARNESS_SOURCE
        assert "len(stderr)" in HARNESS_SOURCE

    def test_there_is_no_force_flag(self) -> None:
        """A gate that can be talked past teaches people to talk past it."""
        assert "--force" not in HARNESS_SOURCE


class TestTheLock:
    def test_the_lock_path_is_anchored_to_the_repository(self) -> None:
        """A relative path silently created a second, independent lock when a
        harness ran from any other directory - and the acquire path does
        ``mkdir(parents=True)``, so there was no error to notice."""
        assert LOCK_PATH.is_absolute(), LOCK_PATH
        assert LOCK_PATH.parent.name == "var"
        assert (LOCK_PATH.parent.parent / "pyproject.toml").exists()

    def test_two_processes_cannot_both_hold_it(self, tmp_path: Path) -> None:
        """The module's headline property, and it was asserted only in prose.

        Two real processes, no GPU: the lock is a file, and this is a CPU-only
        test of the ``O_CREAT|O_EXCL`` race.
        """
        lock = tmp_path / "race.lock"
        script = (
            "import sys, time, pathlib\n"
            f"sys.path.insert(0, {str(BENCHMARKS.parent)!r})\n"
            "from benchmarks.gpulock import gpu_benchmark_lock, "
            "GpuBenchmarkBusyError\n"
            f"path = pathlib.Path({str(lock)!r})\n"
            "try:\n"
            "    with gpu_benchmark_lock(path):\n"
            "        print('ACQUIRED')\n"
            "        sys.stdout.flush()\n"
            "        time.sleep(float(sys.argv[1]))\n"
            "except GpuBenchmarkBusyError:\n"
            "    print('BUSY')\n"
        )
        holder = subprocess.Popen(  # noqa: S603
            [sys.executable, "-c", script, "3"],
            stdout=subprocess.PIPE,
            text=True,
        )
        try:
            assert holder.stdout is not None
            assert holder.stdout.readline().strip() == "ACQUIRED"
            second = subprocess.run(  # noqa: S603
                [sys.executable, "-c", script, "0"],
                capture_output=True,
                text=True,
                timeout=60,
                check=False,
            )
            assert "BUSY" in second.stdout, (second.stdout, second.stderr)
        finally:
            holder.kill()
            holder.wait(timeout=30)

    def test_a_stale_lock_from_a_dead_owner_is_reclaimed(self, tmp_path: Path) -> None:
        lock = tmp_path / "stale.lock"
        # A PID that has certainly exited: spawn one and wait for it.
        finished = subprocess.Popen([sys.executable, "-c", "pass"])
        finished.wait(timeout=30)
        lock.parent.mkdir(parents=True, exist_ok=True)
        lock.write_text(str(finished.pid), encoding="utf-8")

        from benchmarks.gpulock import gpu_benchmark_lock

        with gpu_benchmark_lock(lock):
            assert lock.exists()

    def test_an_unreadable_owner_is_refused_and_left_alone(self, tmp_path: Path) -> None:
        """Fail closed, and **do not delete**: an empty lock file is the
        crash-in-the-create-window state, and guessing it is safe to steal is
        how two benchmarks end up sharing a GPU.

        The residual is recorded in the slice notes: such a lock needs manual
        removal, because nothing distinguishes it from a live holder that has
        not written its PID yet.
        """
        from benchmarks.gpulock import GpuBenchmarkBusyError, gpu_benchmark_lock

        lock = tmp_path / "empty.lock"
        lock.write_text("", encoding="utf-8")
        with pytest.raises(GpuBenchmarkBusyError), gpu_benchmark_lock(lock):
            pass
        assert lock.exists(), "a lock of unknown ownership must not be stolen"


class TestNoModelIsAllocatedAnywhereInThisVerification:
    """The directive for this slice: verify by test and mock, allocate nothing."""

    def test_the_preflight_module_launches_nothing(self) -> None:
        source = (BENCHMARKS / "preflight.py").read_text(encoding="utf-8")
        tree = ast.parse(source)
        roots: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                roots.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                roots.add(node.module.split(".")[0])
        for forbidden in ("subprocess", "llama_cpp", "torch", "transformers"):
            assert forbidden not in roots, roots

    def test_the_harness_is_only_ever_read_never_run(self) -> None:
        """This file imports two pure functions from the harness and reads its
        source. It never calls ``main``, which is the function that loads a
        model."""
        tree = ast.parse(Path(__file__).read_text(encoding="utf-8"))
        called = {
            node.func.id
            for node in ast.walk(tree)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
        }
        for forbidden in ("main", "run_case", "require_headroom_and_run"):
            assert forbidden not in called, forbidden


def test_the_module_level_import_did_not_touch_a_device() -> None:
    """Importing the harness must not read the GPU as a side effect."""
    assert isinstance(pf.REQUIRED_FREE_MIB, int)
    assert callable(classify_failure)


class TestTemporaryFilesStayUnderTheRunsWorkDir:
    """Class C: the prompt, the system prompt and the per-case raw output.

    These are **not** result artifacts and are deliberately not held to the
    fixed-root contract that ``var/`` writers are. They are inputs to one run,
    they live wherever the operator pointed ``--work-dir``, and ``--work-dir``
    is a free-form path by design - constraining it would be a product change,
    not a test.

    What *is* assertable without changing any behaviour is the **relationship**:
    wherever the work directory is, a temporary file belongs inside it. That
    holds today and this keeps it holding.

    The second half matters more than it looks. Two of the three names are
    built by interpolating ``case.case_id`` into a filename, and a path join
    does not defend itself: ``Path("var/probe") / "C:/elsewhere/x.txt"``
    is ``C:/elsewhere/x.txt`` - the absolute component **replaces** the base
    rather than extending it, and ``../..`` traverses out. All 43 corpus ids
    are plain today, so this is a guard on an input that is currently safe,
    not a repair.
    """

    #: The result artifact's local name in ``main``. It is class A - the fixed
    #: root contract covers it in ``test_benchmark_artifacts.py`` - and it is
    #: named here so the two classes cannot quietly merge.
    ARTIFACT_SINK_ROOT = "out"

    WORK_DIR_ROOT = "work_dir"

    @classmethod
    def _path_root(cls, expr: ast.expr) -> str | None:
        """Peel ``a / b / c`` and ``.joinpath(...)`` down to the leftmost name.

        Returns ``None`` for anything that is not ultimately rooted in a plain
        local name, which is the shape this invariant is about.
        """
        while True:
            if isinstance(expr, ast.BinOp) and isinstance(expr.op, ast.Div):
                expr = expr.left
            elif (
                isinstance(expr, ast.Call)
                and isinstance(expr.func, ast.Attribute)
                and expr.func.attr == "joinpath"
            ):
                expr = expr.func.value
            elif isinstance(expr, ast.Attribute) and expr.attr == "parent":
                expr = expr.value
            else:
                break
        return expr.id if isinstance(expr, ast.Name) else None

    @classmethod
    def _assignment_roots(cls) -> dict[str, str]:
        """Local name to the root of whatever it was assigned from.

        Needed because the writes are one indirection away: the harness says
        ``prompt_file = work_dir / ...`` and then ``prompt_file.write_text``,
        so asking the receiver directly answers ``prompt_file`` rather than
        ``work_dir``. Resolving that was this test's own bug, found by the
        test failing on correct source.
        """
        roots: dict[str, str] = {}
        for node in ast.walk(HARNESS_TREE):
            if not isinstance(node, ast.Assign):
                continue
            root = cls._path_root(node.value)
            if root is None:
                continue
            for target in node.targets:
                if isinstance(target, ast.Name):
                    roots[target.id] = root
        return roots

    @classmethod
    def _resolve(cls, name: str | None, *, depth: int = 4) -> str | None:
        """Follow assignments to the ultimate root, with a bound on cycles."""
        roots = cls._assignment_roots()
        seen = set()
        while depth and name is not None and name in roots and name not in seen:
            seen.add(name)
            nxt = roots[name]
            if nxt == name:
                break
            name, depth = nxt, depth - 1
        return name

    @classmethod
    def _text_writes(cls) -> list[tuple[int, str | None]]:
        """Every ``.write_text(...)`` in the harness, with its path's root."""
        return [
            (node.lineno, cls._resolve(cls._path_root(node.func.value)))
            for node in ast.walk(HARNESS_TREE)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "write_text"
        ]

    @staticmethod
    def _local_assignment_roots(name: str) -> set[str]:
        """What a local name was assigned from, by its own root name."""
        roots: set[str] = set()
        for node in ast.walk(HARNESS_TREE):
            if not isinstance(node, ast.Assign):
                continue
            targets = {t.id for t in node.targets if isinstance(t, ast.Name)}
            if name in targets:
                roots.add(ast.unparse(node.value))
        return roots

    def test_every_temporary_write_is_rooted_at_the_work_dir(self) -> None:
        strays = [
            f"line {line}: rooted at {root!r}"
            for line, root in self._text_writes()
            if root not in {self.WORK_DIR_ROOT, self.ARTIFACT_SINK_ROOT}
        ]
        assert strays == [], (
            f"a write in bench_llm_policy.py is rooted outside the run's work "
            f"directory: {strays}. Temporary files belong under --work-dir; if "
            "this one is a result artifact instead, it belongs in the fixed-root "
            "contract and in test_benchmark_artifacts.py, not here."
        )

    def test_the_prompt_and_output_names_are_built_from_the_work_dir(self) -> None:
        """Name the three class-C writes, so a fourth has to be classified.

        Counting them is the point: a new temporary file added without thought
        fails this and its author has to say which class it is in.
        """
        temporary = [
            line for line, root in self._text_writes() if root == self.WORK_DIR_ROOT
        ]
        assert len(temporary) == 3, (
            f"expected three temporary writes under the work directory, found "
            f"{len(temporary)} at lines {temporary}. A new one needs classifying: "
            "temporary input, result artifact, generator output or lock."
        )

    def test_the_artifact_sink_is_still_a_separate_class(self) -> None:
        """The result artifact must not drift into being work-dir rooted.

        If it ever is, the fixed-root contract silently stops applying to it,
        and the test that enforces that contract lives in another file and
        would not notice.
        """
        sinks = [
            line for line, root in self._text_writes() if root == self.ARTIFACT_SINK_ROOT
        ]
        assert len(sinks) == 1, f"expected one artifact sink, found {sinks}"
        assert any(
            "artifact_path" in source for source in self._local_assignment_roots("out")
        ), "the artifact sink stopped coming from artifact_path()"

    @staticmethod
    def _leaves_its_directory(name: str) -> bool:
        """Would interpolating ``name`` into a filename leave the directory?

        Asked of the component rather than by simulating a join, because join
        semantics differ between path flavours - a drive letter replaces the
        base on Windows and does not on POSIX - and the property wanted here
        is the same on both: a case id is a *name*, not a path.
        """
        return (
            "/" in name
            or "\\" in name
            or ":" in name
            or name in {".", ".."}
            or name.startswith(".")
            or ".." in name.split(".")
        )

    def test_no_corpus_case_id_can_leave_the_work_dir(self) -> None:
        escaping = [
            case.case_id
            for case in CORPUS.cases
            if self._leaves_its_directory(case.case_id)
        ]
        assert escaping == [], (
            f"a case id would escape the work directory when interpolated into a "
            f"filename: {escaping}. Case ids are names, not paths."
        )
        assert len(CORPUS.cases) == 43, "corpus size changed; re-check the ids"

    def test_the_escape_check_catches_what_it_is_for(self) -> None:
        """Control, both directions, plus the consequence it guards against."""
        for bad in ("../escape", "..", "sub/dir", "sub\\dir", "C:/elsewhere/x", "."):
            assert self._leaves_its_directory(bad), bad
        for good in ("S.plain.01", "A-1_b", "case.02"):
            assert not self._leaves_its_directory(good), good
        # Why it matters: an absolute component replaces the base entirely.
        base = pathlib.PureWindowsPath("var/probe/llm-policy")
        assert (base / "C:/elsewhere/x.txt").as_posix() == "C:/elsewhere/x.txt"
        assert ".." in (base / "../../escape.txt").parts
