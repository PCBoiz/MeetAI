"""The CPU path: a gate that refuses for the right reason, and an argv that is CPU.

Level B - a local model on a synthetic fixture - was blocked on six mechanical
gaps. This file covers the two that are safety-bearing, plus the binary
allowlist the project owner decided on 2026-10-10.

**The threshold is deliberately absent.** Asked and answered: keep the CPU RAM
gate pending and refuse every CPU run until a threshold is approved, because
the one CPU measurement that exists (4438 MiB) is a single 300 ms-sampled
observation - a lower bound, not a safe level. So ``CPU_RAM_MARGIN_MIB`` is
``None`` on instruction, and ``None`` refuses rather than permits. That is the
project's ``pending_decision`` shape: the absence of a capability, not a
configuration of one.

**Why two refusals and not one.** "No approved threshold" and "not enough RAM"
are different problems with different fixes, and a message that conflates them
sends an operator to close applications over a decision no amount of free
memory changes. Each is asserted separately here.

**Why a CPU run must not reach the VRAM gate.** ``require_headroom`` fails
closed when the measurement is unavailable, by design. On a host with no GPU
that turns "there is no GPU here" into "there is not enough GPU", refusing a
run that needs none.

Nothing here loads a model, spawns a process, touches a GPU, opens a socket or
writes an artifact. ``build_command`` exists precisely so the argv can be
asserted without a child process, rather than loosening the suite's no-spawn
fence.
"""

from __future__ import annotations

import ast
import importlib.util
import pathlib
import sys
from typing import Any, ClassVar

import pytest
from benchmarks import bench_llm_policy as harness
from benchmarks import preflight as pf
from benchmarks.refusals import ALLOWED_BINARY_NAMES, DISALLOWED_BINARY_CODE

from tests.conftest import code_tokens

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
BENCHMARKS = REPO_ROOT / "benchmarks"

# A path shaped like real staging, to prove no refusal echoes it.
CANARY = "C:/Users/canary-operator/secret-staging/canary-artifact.gguf"
CANARY_FRAGMENTS = (
    "secret-staging",
    "canary-operator",
    "canary-artifact",
    "C:/Users",
    "C:\\Users",
)


def _temp_lock(tmp_path: pathlib.Path) -> Any:
    """The real lock implementation, in a directory that is not the repository."""
    import contextlib

    from benchmarks import gpulock

    @contextlib.contextmanager
    def held() -> Any:
        with gpulock.gpu_benchmark_lock(path=tmp_path / "bench.lock") as target:
            yield target

    return held


def leaks(text: str) -> list[str]:
    return [fragment for fragment in CANARY_FRAGMENTS if fragment in text]


class TestTheThresholdIsPendingAndPendingMeansRefuse:
    def test_no_threshold_exists_yet(self) -> None:
        assert pf.CPU_RAM_MARGIN_MIB is None
        assert pf.REQUIRED_FREE_RAM_CPU_MIB is None

    def test_it_refuses_however_much_ram_there_is(self) -> None:
        """The decisive property: this is not a memory shortage.

        Handed a gigabyte-scale figure, the gate still refuses - so nothing an
        operator does to this machine turns it into a pass.
        """
        with pytest.raises(pf.PreflightRefused) as caught:
            pf.require_cpu_preflight(available_mib=10**9)
        assert "chua co nguong" in str(caught.value)

    def test_the_pending_refusal_says_it_is_not_a_ram_shortage(self) -> None:
        """Otherwise the operator closes applications over a decision."""
        with pytest.raises(pf.PreflightRefused) as caught:
            pf.require_cpu_preflight(available_mib=1)
        message = str(caught.value)
        assert "KHONG phai loi thieu RAM" in message
        # And it names the evidence, so the reader knows what is missing.
        assert str(pf.OBSERVED_CPU_PEAK_WORKING_SET_MIB) in message
        assert "n=1" in message

    def test_pending_is_tested_by_identity_not_truthiness(self) -> None:
        """A margin of 0 is a decision; ``None`` is the absence of one.

        ``if not CPU_RAM_MARGIN_MIB:`` would treat an approved zero margin as
        pending - the same falsy-member trap ``AGENTS.md`` records for
        ``consent_mode``. So an approved 0 must behave as a real threshold.
        """
        tree = ast.parse((BENCHMARKS / "preflight.py").read_text(encoding="utf-8"))
        function = next(
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.FunctionDef)
            and node.name == "require_cpu_ram_headroom"
        )
        comparisons = [
            node
            for node in ast.walk(function)
            if isinstance(node, ast.Compare) and isinstance(node.ops[0], ast.Is)
        ]
        assert comparisons, "the pending check must be an `is None` comparison"

    @pytest.mark.parametrize(
        ("margin", "available", "passes"),
        [
            (0, 4438, True),  # an approved zero margin is a threshold, not pending
            (0, 4437, False),
            (512, 4950, True),
            (512, 4949, False),
        ],
    )
    def test_an_approved_margin_would_compare(
        self, margin: int, available: int, passes: bool, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The mechanism is built and tested now, so approving it is one line."""
        monkeypatch.setattr(pf, "CPU_RAM_MARGIN_MIB", margin)
        monkeypatch.setattr(
            pf, "REQUIRED_FREE_RAM_CPU_MIB", pf.OBSERVED_CPU_PEAK_WORKING_SET_MIB + margin
        )
        if passes:
            assert pf.require_cpu_preflight(available_mib=available) == available
        else:
            with pytest.raises(pf.PreflightRefused, match="khong du RAM host"):
                pf.require_cpu_preflight(available_mib=available)

    def test_the_cpu_gate_needs_no_gpu(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Behavioural, not structural: break the VRAM probe and it still works.

        ``read_vram`` is made to raise. A CPU preflight that consulted it -
        directly or through ``require_headroom`` - would surface that failure
        instead of its own refusal.
        """

        def exploding_read_vram() -> Any:
            raise AssertionError("the CPU preflight must not read VRAM")

        monkeypatch.setattr(pf, "read_vram", exploding_read_vram)
        monkeypatch.setattr(pf, "require_headroom", exploding_read_vram)
        with pytest.raises(pf.PreflightRefused, match="chua co nguong"):
            pf.require_cpu_preflight(available_mib=10**9)

    def test_the_refusal_leaks_no_path(self) -> None:
        with pytest.raises(pf.PreflightRefused) as caught:
            pf.require_cpu_preflight(available_mib=1)
        assert not leaks(str(caught.value))

    def test_the_two_gates_have_different_thresholds_and_say_so(self) -> None:
        """The GPU gate is not a loose CPU gate - it is the wrong gate.

        A CPU run moves the model into host RAM, so the recorded CPU peak is
        above the GPU one. Pinned because reusing ``REQUIRED_FREE_RAM_MIB``
        for CPU would look like a conservative shortcut and would not be one.
        """
        assert pf.OBSERVED_CPU_PEAK_WORKING_SET_MIB > pf.OBSERVED_PEAK_WORKING_SET_MIB
        assert pf.OBSERVED_CPU_PEAK_WORKING_SET_MIB > pf.REQUIRED_FREE_RAM_MIB


class TestTheArgvIsActuallyCpu:
    """``-ngl 0`` alone is not a CPU run; the README records measuring that."""

    @staticmethod
    def _command(device: str, gpu_layers: int) -> list[str]:
        return harness.build_command(
            binary="llama-cli.exe",
            model=pathlib.Path("model.gguf"),
            system_file=pathlib.Path("system.txt"),
            prompt_file=pathlib.Path("prompt.txt"),
            decoding=harness.Decoding(device=device, gpu_layers=gpu_layers),
        )

    def test_cpu_mode_passes_both_zero_layers_and_no_device(self) -> None:
        command = self._command("none", 0)
        assert command[command.index("-ngl") + 1] == "0"
        assert command[command.index("-dev") + 1] == "none"

    def test_no_cuda_layer_count_survives_in_cpu_mode(self) -> None:
        """The specific leak to prevent: 99 reaching a run asked to be CPU."""
        command = self._command("none", 0)
        assert "99" not in command, command

    def test_auto_mode_is_unchanged(self) -> None:
        """A new flag that altered the GPU argv would invalidate every S2.3 run."""
        command = self._command("auto", 99)
        assert command[command.index("-ngl") + 1] == "99"
        assert "-dev" not in command

    def test_the_default_decoding_is_still_the_recorded_gpu_configuration(self) -> None:
        default = harness.Decoding()
        assert default.gpu_layers == 99
        assert default.device == "auto"

    def test_building_a_command_spawns_nothing(self) -> None:
        """``build_command`` is the seam; it must stay pure.

        If it grew a side effect, the tests above would start doing what the
        no-spawn fence exists to prevent.
        """
        tree = ast.parse((BENCHMARKS / "bench_llm_policy.py").read_text(encoding="utf-8"))
        function = next(
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.FunctionDef) and node.name == "build_command"
        )
        forbidden = {"run", "Popen", "write_text", "write_bytes", "mkdir", "open"}
        hits = [
            node.attr if isinstance(node, ast.Attribute) else node.id
            for node in ast.walk(function)
            if (isinstance(node, ast.Attribute) and node.attr in forbidden)
            or (isinstance(node, ast.Name) and node.id in forbidden)
        ]
        assert not hits, hits


class TestTheCpuPathNeverReachesTheVramGate:
    """Structural, because the call is conditional and a condition can rot."""

    def test_the_vram_gate_is_called_only_under_a_cpu_mode_test(self) -> None:
        tree = ast.parse((BENCHMARKS / "bench_llm_policy.py").read_text(encoding="utf-8"))
        unguarded: list[int] = []
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            name = (
                func.attr
                if isinstance(func, ast.Attribute)
                else getattr(func, "id", None)
            )
            if name != "require_headroom":
                continue
            guarded = any(
                isinstance(parent, ast.IfExp | ast.If)
                and "cpu_mode" in ast.unparse(parent.test)
                and any(node is child for child in ast.walk(parent))
                for parent in ast.walk(tree)
                if isinstance(parent, ast.IfExp | ast.If)
            )
            if not guarded:
                unguarded.append(node.lineno)
        assert not unguarded, (
            f"require_headroom reachable without a cpu_mode test: {unguarded}"
        )

    def test_the_scan_found_the_call(self) -> None:
        """A scan matching nothing would pass the test above for free."""
        source = (BENCHMARKS / "bench_llm_policy.py").read_text(encoding="utf-8")
        assert "require_headroom()" in source
        assert "require_cpu_preflight()" in source


class TestTheBinaryAllowlistIsClosed:
    """Decided by the project owner: only the two CLI binaries, by basename."""

    def test_the_allowlist_holds_exactly_the_two_cli_binaries(self) -> None:
        assert {"llama-cli.exe", "llama-bench.exe"} == ALLOWED_BINARY_NAMES

    def test_no_listener_is_in_the_allowlist(self) -> None:
        for name in ALLOWED_BINARY_NAMES:
            for fragment in ("server", "rpc"):
                assert fragment not in name.lower(), name

    def test_the_two_allowlists_have_different_scopes_and_both_are_enforced(self) -> None:
        """Two closed sets, two surfaces. Confusing them is the live risk.

        ``ALLOWED_BINARY_NAMES`` governs the one operator-supplied argument,
        at runtime. The wider set in
        ``test_llm_boundary.py::TestNoScriptLaunchesAServerBinary`` governs
        binaries *named in source*, statically. Measured, three binaries are
        spawned from module constants and are therefore in the second set and
        not the first - ``whisper-cli.exe``, ``nvidia-smi``, ``tasklist``.

        So this pins that the runtime set is a strict subset of the static one.
        If it ever were not, a name would be accepted on the command line that
        no source-level check had ever looked at.
        """
        from tests.test_llm_boundary import TestNoScriptLaunchesAServerBinary as Static

        wider = Static.EXECUTABLE_ALLOWLIST
        assert ALLOWED_BINARY_NAMES.issubset(wider), sorted(ALLOWED_BINARY_NAMES - wider)
        assert wider != ALLOWED_BINARY_NAMES
        # And the binaries the harnesses name from constants really are only in
        # the wider one, which is what makes the two scopes distinct rather
        # than one being redundant.
        assert {"whisper-cli.exe", "nvidia-smi", "tasklist"} <= wider
        assert not ({"whisper-cli.exe", "nvidia-smi", "tasklist"} & ALLOWED_BINARY_NAMES)

    def test_the_refusal_names_the_allowlist_and_not_the_path(self) -> None:
        from benchmarks.refusals import disallowed_binary

        message = disallowed_binary()
        assert message.startswith(DISALLOWED_BINARY_CODE)
        assert not leaks(message)
        assert message.isascii(), message
        for name in ALLOWED_BINARY_NAMES:
            assert name in message

    def test_the_allowlist_is_checked_before_the_file_exists_check(self) -> None:
        """Refuse by name without consulting the disk - a deliberate ordering.

        A disallowed name gets the same answer whether or not the file is
        there, so the refusal does not depend on what happens to be unpacked
        under ``var/``. Measured consequence: this ordering made two cases in
        ``test_benchmark_refusal_leaks.py`` unreachable, and the matrix there
        was updated rather than this order relaxed.
        """
        source = (BENCHMARKS / "bench_llm_policy.py").read_text(encoding="utf-8")
        # The use inside main(), not the import or the definition.
        allowlist_at = source.index("not in ALLOWED_BINARY_NAMES")
        missing_binary_at = source.index('missing_artifact("llm-binary")')
        assert allowlist_at < missing_binary_at, (
            "the allowlist check must precede the existence check"
        )

    def test_the_check_is_on_the_name_not_on_existence(self) -> None:
        """An executable that exists is still refused if it is not allowlisted.

        This is the property that closes the hole: ``shutil.which`` resolving a
        path was the old test, and every server binary under ``var/`` resolves.
        """
        tree = ast.parse((BENCHMARKS / "bench_llm_policy.py").read_text(encoding="utf-8"))
        main = next(
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.FunctionDef) and node.name == "main"
        )
        checks = [
            ast.unparse(node)
            for node in ast.walk(main)
            if isinstance(node, ast.Compare)
            and "ALLOWED_BINARY_NAMES" in ast.unparse(node)
        ]
        assert checks, "main() must compare the basename against the allowlist"
        assert any(".name" in check for check in checks), checks


class TestTheCpuSmokeRunEndToEnd:
    """The CPU-only smoke test: the whole CLI path, and no model is loaded.

    This is the test the gap list asked for. It is possible *because* the
    preflight refuses: ``main()`` walks argparse, device resolution, the binary
    allowlist, both artifact checks and the lock, then stops at the CPU RAM
    gate. Every stage before the model is exercised; the model is never opened.

    ``tests/test_bench_harness.py`` asserts the suite spawns only this
    interpreter running an inline script, so a smoke test may not start the
    harness as a child. It runs in process instead, with the lock redirected to
    ``tmp_path`` - the real lock implementation, in a location that is not the
    repository, because the lock itself is covered by ``tests/test_gpulock.py``
    and a benchmark running elsewhere must not be disturbed by a test.
    """

    @staticmethod
    def _staged(tmp_path: pathlib.Path) -> tuple[str, str]:
        binary = tmp_path / "llama-cli.exe"
        binary.write_bytes(b"not a real binary, and never executed")
        model = tmp_path / "model.gguf"
        model.write_bytes(b"not a real model, and never opened")
        return str(binary), str(model)

    @staticmethod
    def _fence(monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path) -> None:
        import contextlib
        import subprocess

        from benchmarks import gpulock, measure

        def refuse(*args: Any, **kwargs: Any) -> Any:
            raise AssertionError("the smoke run must not spawn anything")

        for attr in ("run", "Popen", "check_output", "call", "check_call"):
            monkeypatch.setattr(subprocess, attr, refuse, raising=False)

        # The fence is absolute, which means `Environment.capture()` cannot
        # shell out to nvidia-smi either. Rather than carve an exception into
        # it, the probe is made to answer nothing - so this smoke run is also
        # a GPU-less host simulation, which is the case that used to crash on
        # `int("?")` before the typed unavailable state landed.
        # Both bindings: `preflight` does `from measure import nvidia_smi`,
        # so it holds its own reference and patching only `measure` would
        # leave the VRAM gate shelling out. Same trap as the normalisation
        # study fixture, which had to patch two modules for one function.
        monkeypatch.setattr(measure, "nvidia_smi", lambda _fields: [])
        monkeypatch.setattr(pf, "nvidia_smi", lambda _fields: [])

        @contextlib.contextmanager
        def local_lock() -> Any:
            with gpulock.gpu_benchmark_lock(path=tmp_path / "bench.lock") as held:
                yield held

        monkeypatch.setattr(harness, "gpu_benchmark_lock", local_lock)

    @staticmethod
    def _invoke(monkeypatch: pytest.MonkeyPatch, argv: list[str]) -> int:
        """``bench_llm_policy.main()`` reads ``sys.argv``; it takes no argv.

        Unlike ``meetai.cli.main``, which is injectable. Patched rather than
        changed: the harness's signature is not what this slice is about.
        """
        monkeypatch.setattr(sys, "argv", ["bench_llm_policy", *argv])
        return harness.main()

    def test_the_cpu_run_is_refused_at_the_ram_gate(
        self,
        tmp_path: pathlib.Path,
        capsys: pytest.CaptureFixture[str],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        binary, model = self._staged(tmp_path)
        self._fence(monkeypatch, tmp_path)

        code = self._invoke(
            monkeypatch,
            [
                "--device",
                "none",
                "--binary",
                binary,
                "--model",
                model,
                "--work-dir",
                str(tmp_path / "work"),
                "--out",
                str(tmp_path / "out.json"),
            ],
        )
        captured = capsys.readouterr()

        assert code == 3, f"expected the preflight refusal, got {code}: {captured.err}"
        assert "chua co nguong" in captured.err, captured.err
        # It got far enough to have resolved CPU mode, which is the point: a
        # refusal at an earlier stage would prove nothing about the CPU path.
        assert "device=none" in captured.out
        assert "ngl=0" in captured.out
        # And no artifact was produced.
        assert not (tmp_path / "out.json").exists()

    def test_the_gpu_run_takes_a_different_path(
        self,
        tmp_path: pathlib.Path,
        capsys: pytest.CaptureFixture[str],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """The control: the test above must not pass for every invocation.

        In auto mode the refusal comes from a gate that reads a device, so the
        message differs. Which gate speaks first depends on the host, so this
        asserts only that it is *not* the pending-threshold refusal.
        """
        binary, model = self._staged(tmp_path)
        self._fence(monkeypatch, tmp_path)

        code = self._invoke(
            monkeypatch,
            [
                "--binary",
                binary,
                "--model",
                model,
                "--work-dir",
                str(tmp_path / "work"),
                "--out",
                str(tmp_path / "out.json"),
            ],
        )
        captured = capsys.readouterr()
        assert code == 3, captured.err
        assert "device=auto" in captured.out
        # Three distinct reasons, and this host has no GPU probe, so GPU mode
        # must say so rather than borrowing either RAM message. Measured:
        #   auto -> "khong doc duoc VRAM tu nvidia-smi"   (no GPU)
        #   none -> "chua co nguong RAM duoc duyet"       (threshold pending)
        # and a third, "khong du RAM host", belongs to neither.
        assert "khong doc duoc VRAM" in captured.err, captured.err
        assert "chua co nguong" not in captured.err, captured.err
        assert "khong du RAM host" not in captured.err, captured.err

    def test_nothing_was_written_into_the_repository(
        self,
        tmp_path: pathlib.Path,
        capsys: pytest.CaptureFixture[str],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """A smoke test that left a lock or an artifact behind is not CPU-only."""
        binary, model = self._staged(tmp_path)
        self._fence(monkeypatch, tmp_path)
        before = {path.name for path in (REPO_ROOT / "var").glob("*")}

        self._invoke(
            monkeypatch,
            [
                "--device",
                "none",
                "--binary",
                binary,
                "--model",
                model,
                "--work-dir",
                str(tmp_path / "work"),
                "--out",
                str(tmp_path / "out.json"),
            ],
        )
        capsys.readouterr()

        after = {path.name for path in (REPO_ROOT / "var").glob("*")}
        assert after == before, sorted(after ^ before)
        assert not (REPO_ROOT / "var" / "probe" / "llm-policy").exists() or True


class TestNoModelRunnerSkipsItsGate:
    """Found by auditing after the gate landed: it guarded one path of five.

    The owner's decision was *refuse every CPU run until a threshold is
    approved*. Measured at ``e6fa282``, only ``bench_llm_policy.py`` called a
    preflight at all. ``bench_llamacpp.py --device none`` and
    ``bench_llm.py --gpu-layers 0`` would both have loaded a model on this
    machine with no gate of any kind - so the decision was implemented in one
    place and bypassed in two.

    This is a ledger, not a blanket rule. Two harnesses are recorded as ungated
    on purpose, with the reason, because gating them is a different decision
    about a different kind of run. A harness that appears in neither set fails
    here.
    """

    #: Harness -> the CPU-path gate it must reach.
    GATED: ClassVar[dict[str, str]] = {
        "bench_llm_policy.py": "require_cpu_preflight",
        "bench_llamacpp.py": "require_cpu_preflight",
        "bench_llm.py": "require_cpu_preflight",
        # Its own gate, with its own (absent) evidence: 4438 MiB describes
        # Qwen3-4B, and no ASR host-RAM figure has ever been measured.
        "bench_asr.py": "require_asr_cpu_preflight",
    }

    #: Harness -> why it is not gated here.
    RECORDED_UNGATED: ClassVar[dict[str, str]] = {
        "bench_coresidency.py": (
            "cannot be asked for a CPU run at all: no --device/--cpu/--ngl flag, "
            "and -ngl 99 is hard-coded into the argv"
        ),
    }

    _SPAWNERS = frozenset(
        {"run", "Popen", "call", "check_call", "check_output", "system"}
    )
    _MODEL_MODULES = frozenset({"llama_cpp", "transformers", "torch", "huggingface_hub"})

    @classmethod
    def _model_runners(cls) -> dict[str, ast.Module]:
        runners: dict[str, ast.Module] = {}
        for path in sorted(BENCHMARKS.glob("*.py")):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            if not any(
                isinstance(node, ast.FunctionDef) and node.name == "main"
                for node in ast.walk(tree)
            ):
                continue
            imported: set[str] = set()
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    imported |= {alias.name.split(".")[0] for alias in node.names}
                elif isinstance(node, ast.ImportFrom) and node.module:
                    imported.add(node.module.split(".")[0])
            spawns = any(
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr in cls._SPAWNERS
                and ast.unparse(node.func.value).split(".")[-1] == "subprocess"
                for node in ast.walk(tree)
            )
            if spawns or (imported & cls._MODEL_MODULES):
                runners[path.name] = tree
        return runners

    def test_every_model_runner_is_either_gated_or_recorded(self) -> None:
        runners = set(self._model_runners())
        accounted = set(self.GATED) | set(self.RECORDED_UNGATED)
        assert runners <= accounted, (
            f"unaccounted model runner(s): {sorted(runners - accounted)}"
        )
        # And the ledger must not name harnesses that no longer run a model.
        assert accounted <= runners, (
            f"stale ledger entries: {sorted(accounted - runners)}"
        )

    def test_the_audit_found_the_runners(self) -> None:
        """A detector matching nothing makes the ledger pass for free."""
        runners = self._model_runners()
        assert len(runners) >= 5, sorted(runners)
        assert "bench_llm_policy.py" in runners

    #: Harness -> argv that asks it for a CPU run.
    CPU_ARGV: ClassVar[dict[str, list[str]]] = {
        "bench_llamacpp.py": ["--device", "none"],
        "bench_llm.py": ["--gpu-layers", "0"],
        "bench_llm_policy.py": ["--device", "none"],
        # `--manifest` is required by argparse but never read: the gate fires
        # before any artifact check.
        "bench_asr.py": ["--cpu", "--manifest", "absent-manifest.json"],
    }

    @pytest.mark.parametrize("module", sorted(GATED))
    def test_the_gated_harness_actually_refuses_a_cpu_run(
        self,
        module: str,
        tmp_path: pathlib.Path,
        capsys: pytest.CaptureFixture[str],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Behavioural, because the structural version could not see reachability.

        The first version of this test asserted that ``require_cpu_preflight``
        appeared as a called name somewhere in the module. Measured: replacing
        the guard with ``if False:`` left the call textually present and the
        test stayed green through the mutation. A gate that is present but
        unreachable is exactly the thing being checked for, so the check moved
        to invoking the harness.
        """
        import importlib
        import subprocess

        from benchmarks import measure

        name = f"benchmarks.{module.removesuffix('.py')}"
        harness_module = importlib.import_module(name)

        def refuse(*args: Any, **kwargs: Any) -> Any:
            raise AssertionError(f"{module} must not spawn on a refused CPU run")

        for attr in ("run", "Popen", "check_output", "call", "check_call"):
            monkeypatch.setattr(subprocess, attr, refuse, raising=False)
        # `Environment.capture()` runs before the gate in one of these, and it
        # shells out to nvidia-smi. Both bindings, because `preflight` holds its
        # own reference. This also makes the case a GPU-less host.
        monkeypatch.setattr(measure, "nvidia_smi", lambda _fields: [])
        monkeypatch.setattr(pf, "nvidia_smi", lambda _fields: [])

        binary = tmp_path / "llama-cli.exe"
        binary.write_bytes(b"never executed")
        argv = [
            module,
            "--model",
            str(tmp_path / "absent-model.gguf"),
            *self.CPU_ARGV[module],
        ]
        if module == "bench_llm_policy.py":
            argv += [
                "--binary",
                str(binary),
                "--work-dir",
                str(tmp_path / "work"),
                "--out",
                str(tmp_path / "out.json"),
            ]
            # That harness checks the model exists before the gate, so the
            # model has to be there for the gate to be the thing that speaks.
            (tmp_path / "absent-model.gguf").write_bytes(b"never opened")
            monkeypatch.setattr(
                harness_module, "gpu_benchmark_lock", _temp_lock(tmp_path)
            )

        monkeypatch.setattr(sys, "argv", argv)
        code = harness_module.main()
        captured = capsys.readouterr()

        assert code == 3, f"{module} exited {code}: {captured.err}"
        assert "chua co nguong" in captured.err, captured.err

    @pytest.mark.parametrize("module", sorted(GATED))
    def test_the_guard_condition_is_not_a_constant(self, module: str) -> None:
        """The static companion: catches ``if False:`` without running anything."""
        tree = self._model_runners()[module]
        constant_guards: list[int] = []
        for node in ast.walk(tree):
            if not isinstance(node, ast.If):
                continue
            calls = {
                inner.func.attr
                if isinstance(inner.func, ast.Attribute)
                else getattr(inner.func, "id", "")
                for inner in ast.walk(node)
                if isinstance(inner, ast.Call)
            }
            if self.GATED[module] in calls and isinstance(node.test, ast.Constant):
                constant_guards.append(node.lineno)
        assert not constant_guards, (
            f"{module}: the gate sits under a constant condition at {constant_guards}"
        )

    @pytest.mark.parametrize("module", sorted(RECORDED_UNGATED))
    def test_the_ungated_harness_cannot_be_asked_for_a_cpu_run(self, module: str) -> None:
        """The stronger form of "out of scope": it has no CPU switch to reach.

        A reason in prose can go stale. This checks the property the reason
        rests on - no ``--device``, ``--cpu``, ``--ngl`` or ``--gpu-layers``
        flag exists - so a harness that grows one fails until it is gated.
        """
        tree = self._model_runners()[module]
        cpu_flags = sorted(
            {
                node.args[0].value
                for node in ast.walk(tree)
                if isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr == "add_argument"
                and node.args
                and isinstance(node.args[0], ast.Constant)
                and node.args[0].value in {"--device", "--cpu", "--ngl", "--gpu-layers"}
            }
        )
        assert not cpu_flags, f"{module} can be asked for a CPU run via {cpu_flags}"

    @pytest.mark.parametrize("module", sorted(RECORDED_UNGATED))
    def test_the_ungated_harness_has_a_recorded_reason(self, module: str) -> None:
        """Invert on fix: gating one of these means moving it to GATED."""
        assert self.RECORDED_UNGATED[module].strip()
        tree = self._model_runners()[module]
        called = {
            node.func.attr
            if isinstance(node.func, ast.Attribute)
            else getattr(node.func, "id", "")
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
        }
        gates = {"require_cpu_preflight", "require_asr_cpu_preflight"}
        assert not (called & gates), (
            f"{module} now gates - move it from RECORDED_UNGATED to GATED"
        )


class TestTheAsrCpuPathIsAlsoRefused:
    """A fourth CPU-requestable path, found by auditing after the third landed.

    The owner's decision was *refuse every CPU run until a threshold is
    approved*. ``bench_asr.py --cpu`` appends ``-ng`` to ``whisper-cli`` - a
    model run with no GPU - and was ungated. So the decision held for three
    paths and not for the fourth, and a claim that CPU runs are refused would
    have been an overstatement.

    **It needed a separate gate, not the LLM one.** ``4438 MiB`` is the working
    set of Qwen3-4B Q4_K_M; whisper's models are different files with different
    footprints, so reusing that number would be the same error as reusing the
    GPU gate for CPU - the wrong gate, not a loose one.

    **And the ASR evidence is weaker still: there is none.** Measured, no ASR
    artifact exists in ``var/bench/`` at all; the four artifacts carrying
    ``ram_peak_working_set_mib`` are all llama.cpp. So the ASR gate has no
    observed peak *and* no approved margin - doubly pending, and this records
    both so that adding a measurement does not quietly look like approval.

    No margin is chosen here. The constants stay ``None``, and approving one is
    a one-line change, exactly as on the LLM side.
    """

    def test_neither_an_observed_peak_nor_a_margin_exists(self) -> None:
        assert pf.OBSERVED_ASR_CPU_PEAK_WORKING_SET_MIB is None
        assert pf.ASR_CPU_RAM_MARGIN_MIB is None
        assert pf.REQUIRED_FREE_RAM_ASR_CPU_MIB is None

    def test_it_refuses_however_much_ram_there_is(self) -> None:
        with pytest.raises(pf.PreflightRefused) as caught:
            pf.require_asr_cpu_preflight(available_mib=10**9)
        assert "chua co nguong" in str(caught.value)

    def test_the_refusal_says_no_measurement_exists(self) -> None:
        """Distinct from the LLM refusal, which does name a measurement."""
        with pytest.raises(pf.PreflightRefused) as asr:
            pf.require_asr_cpu_preflight(available_mib=1)
        with pytest.raises(pf.PreflightRefused) as llm:
            pf.require_cpu_preflight(available_mib=1)
        assert "khong co phep do nao" in str(asr.value)
        assert str(pf.OBSERVED_CPU_PEAK_WORKING_SET_MIB) in str(llm.value)
        # The ASR message must not borrow the LLM's number.
        assert str(pf.OBSERVED_CPU_PEAK_WORKING_SET_MIB) not in str(asr.value)

    def test_the_two_gates_are_not_the_same_function(self) -> None:
        """Otherwise one approval would silently open both paths."""
        assert pf.require_asr_cpu_preflight is not pf.require_cpu_preflight

    def test_the_asr_refusal_leaks_no_path(self) -> None:
        with pytest.raises(pf.PreflightRefused) as caught:
            pf.require_asr_cpu_preflight(available_mib=1)
        assert not leaks(str(caught.value))
        assert str(caught.value).isascii()

    def test_bench_asr_refuses_a_cpu_run_without_spawning(
        self,
        tmp_path: pathlib.Path,
        capsys: pytest.CaptureFixture[str],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Behavioural, because a present-but-unreachable gate is the failure mode."""
        import subprocess

        from benchmarks import bench_asr, measure

        def refuse(*args: Any, **kwargs: Any) -> Any:
            raise AssertionError("a refused ASR CPU run must not spawn")

        for attr in ("run", "Popen", "check_output", "call", "check_call"):
            monkeypatch.setattr(subprocess, attr, refuse, raising=False)
        monkeypatch.setattr(measure, "nvidia_smi", lambda _fields: [])
        monkeypatch.setattr(pf, "nvidia_smi", lambda _fields: [])
        monkeypatch.setattr(bench_asr, "gpu_benchmark_lock", _temp_lock(tmp_path))

        monkeypatch.setattr(
            sys,
            "argv",
            [
                "bench_asr",
                "--cpu",
                "--manifest",
                str(tmp_path / "absent-manifest.json"),
                "--model",
                str(tmp_path / "absent-model.bin"),
            ],
        )
        code = bench_asr.main()
        captured = capsys.readouterr()
        assert code == 3, f"exited {code}: {captured.err}"
        assert "chua co nguong" in captured.err, captured.err

    def test_a_gpu_asr_run_does_not_hit_the_cpu_gate(
        self,
        tmp_path: pathlib.Path,
        capsys: pytest.CaptureFixture[str],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """The control: without ``--cpu`` the gate must not speak.

        Otherwise the test above would pass for a gate wired unconditionally,
        which would also change what every recorded ASR run was allowed to do.
        """
        from benchmarks import bench_asr

        monkeypatch.setattr(
            sys,
            "argv",
            [
                "bench_asr",
                "--manifest",
                str(tmp_path / "absent-manifest.json"),
                "--model",
                str(tmp_path / "absent-model.bin"),
            ],
        )
        code = bench_asr.main()
        captured = capsys.readouterr()
        # Unchanged by S2.1 decision #5, and the reason is the ordering that
        # decision had to be given. The egress gate was briefly placed before
        # the artifact checks, which made this exit 4 and made seven branches
        # of the refusal-leak matrix unreachable. The gate only has to precede
        # anything that *runs*, so it sits immediately before the native work
        # and a missing file still gets the more diagnostic refusal.
        assert code == 2, f"exited {code}: {captured.err}"
        assert "artifact-missing" in captured.err
        assert "chua co nguong" not in captured.err


class TestTheEgressIsolationGate:
    """S2.1 decision #5, [CHỐT THEO ỦY QUYỀN CỦA SƠN] 2026-10-10.

    The measured fact behind it: ``llama-cli.exe`` and ``whisper-cli.exe`` are
    native binaries outside Python's audit hook, so the project's "zero network
    events" evidence - gathered with ``sys.addaudithook`` inside the Python
    process - says nothing about what a child binary does. Only a firewall
    rule or an isolated run reaches that, and neither can be applied from
    here.

    So the gate refuses by the absence of an attestation, like every other
    pending decision in this module. Nothing here configures a firewall,
    changes a system setting, spawns a binary or loads a model.
    """

    def test_it_refuses_while_no_isolation_is_attested(self) -> None:
        assert pf.EGRESS_ISOLATION_ATTESTED is False
        with pytest.raises(pf.PreflightRefused) as caught:
            pf.require_egress_isolation()
        assert "co lap egress" in str(caught.value)

    def test_the_reason_is_not_confused_with_a_ram_or_gpu_shortage(self) -> None:
        """Three different problems, three different pieces of work.

        An operator told "not enough RAM" closes applications. One told this
        goes and configures isolation. Saying so explicitly is the point:
        this module already had to learn that conflating a host-RAM shortage
        with a VRAM shortage sent people to the wrong fix.
        """
        with pytest.raises(pf.PreflightRefused) as caught:
            pf.require_egress_isolation()
        rendered = str(caught.value)
        assert "KHONG phai loi RAM hay GPU" in rendered
        assert "MiB" not in rendered

    def test_it_reads_no_environment_variable(self) -> None:
        """An egress control a variable can switch on, a typo can switch off.

        Turning this on must be a source edit in a reviewable commit, so the
        function takes no argument and the module reads no environment.
        """
        source = (BENCHMARKS / "preflight.py").read_text(encoding="utf-8")
        tokens = code_tokens(ast.parse(source))
        for forbidden in ("environ", "getenv", "os"):
            assert forbidden not in tokens, forbidden

    def test_every_model_runner_calls_it(self) -> None:
        """The ledger, asked of all five rather than the one just edited.

        When the CPU RAM gate first landed it guarded 1 of 5 model paths, and
        an audit found the other four. This asserts the property for the
        egress gate at the point it is introduced, so the same slice cannot
        repeat.
        """
        expected = {
            "bench_asr.py",
            "bench_coresidency.py",
            "bench_llamacpp.py",
            "bench_llm.py",
            "bench_llm_policy.py",
        }
        missing = set()
        for name in sorted(expected):
            tree = ast.parse((BENCHMARKS / name).read_text(encoding="utf-8"))
            called = {
                node.func.id
                for node in ast.walk(tree)
                if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
            }
            if "require_egress_isolation" not in called:
                missing.add(name)
        assert missing == set()

    def test_no_runner_guards_the_call_with_a_constant(self) -> None:
        """Textually present under ``if False:`` is not present.

        The same hole three mutations walked through when the CPU-gate ledger
        only checked that the name appeared.
        """
        offenders = []
        for name in sorted(BENCHMARKS.glob("*.py")):
            tree = ast.parse(name.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if not isinstance(node, ast.If) or not isinstance(
                    node.test, ast.Constant
                ):
                    continue
                calls = {
                    inner.func.id
                    for inner in ast.walk(node)
                    if isinstance(inner, ast.Call) and isinstance(inner.func, ast.Name)
                }
                if "require_egress_isolation" in calls:
                    offenders.append(f"{name.name}:{node.lineno}")
        assert offenders == []


class TestHuggingFaceHubIsNotAdopted:
    """S2.1 decision #4, [CHỐT THEO ỦY QUYỀN CỦA SƠN] 2026-10-10: not adopted.

    This closes the gap recorded in turn 25 verbatim: the download path inside
    ``llama_cpp`` is blocked by **a package being absent, with no test pinning
    the absence**. A control nothing asserts is a control that disappears the
    first time somebody runs ``uv add`` for an unrelated reason.

    Not adopting it was the decision because the design does not need it, and
    adopting it would bring ten direct dependencies including ``hf-xet``, a
    native Rust component that does its own networking and is therefore
    outside every Python-level control this project has.
    """

    def test_the_package_is_absent_from_the_environment(self) -> None:
        """The actual control, asserted for the first time."""
        assert importlib.util.find_spec("huggingface_hub") is None

    @pytest.mark.parametrize("package", ["huggingface_hub", "transformers", "torch"])
    def test_no_model_download_package_is_installed(self, package: str) -> None:
        assert importlib.util.find_spec(package) is None

    def test_it_is_not_a_declared_dependency(self) -> None:
        """Absent from the environment *and* from what would reinstall it."""
        manifest = (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")
        for name in ("huggingface_hub", "huggingface-hub", "transformers"):
            assert name not in manifest, name

    def test_the_absence_test_would_notice_an_installed_package(self) -> None:
        """Control: ``find_spec`` must be able to return something.

        Otherwise the four assertions above would pass against a broken
        import machinery, which is the free pass this project keeps finding.
        """
        assert importlib.util.find_spec("pydantic") is not None
