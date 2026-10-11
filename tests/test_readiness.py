"""The level-B readiness report: does it agree with the gates it describes?

The report is prose-shaped, so the temptation is to test the prose. These
tests do the opposite wherever they can: for every gate listed, they ask the
**real gate function** whether it refuses, and require the report to say the
same thing. A report that hardcoded "pending" would satisfy that half - every
gate is pending today - so the approved direction is driven through an
injected source, and the two halves together are what pin the behaviour.

Why not assert against the constants: a test that reads
``preflight.CPU_RAM_MARGIN_MIB`` and checks the report agrees is a test that
restates the implementation, and it passes whatever the implementation
becomes. The gate functions are the contract; the constants are how they are
currently spelled.
"""

from __future__ import annotations

import ast
import dataclasses
import json
import pathlib
import subprocess
from collections.abc import Callable

import pytest
from benchmarks import artifacts, preflight, readiness
from benchmarks.artifacts import DigestNotPinned
from benchmarks.preflight import PreflightRefused
from benchmarks.readiness import (
    EXIT_ALL_APPROVED,
    EXIT_GATE_PENDING,
    GATE_IDS,
    GateSource,
)

REPO = pathlib.Path(__file__).resolve().parent.parent
MODULE = REPO / "benchmarks" / "readiness.py"

#: An amount of RAM no machine in scope has, passed so the RAM gates never
#: read host memory. Both gates refuse *before* measuring while the threshold
#: is pending, so if a policy refusal ever became a memory refusal this figure
#: is what would expose it.
ABSURD_RAM_MIB = 10**9


def _probe_llm_cpu_ram() -> None:
    preflight.require_cpu_ram_headroom(available_mib=ABSURD_RAM_MIB)


def _probe_asr_cpu_ram() -> None:
    preflight.require_asr_cpu_preflight(available_mib=ABSURD_RAM_MIB)


def _probe_model_digest() -> None:
    for role in readiness.MODEL_ROLES:
        artifacts.require_role_is_pinned(role)


def _probe_egress() -> None:
    preflight.require_egress_isolation()


#: One behavioural probe per gate id. Keyed by gate id on purpose: the
#: completeness test below compares these keys with :data:`GATE_IDS`, so a
#: fifth gate cannot be added to the report without someone stating how to
#: observe it refusing. That is the half a list of four strings cannot check.
PROBES: dict[str, Callable[[], None]] = {
    "llm-cpu-ram": _probe_llm_cpu_ram,
    "asr-cpu-ram": _probe_asr_cpu_ram,
    "model-digest": _probe_model_digest,
    "egress-isolation": _probe_egress,
}

ALL_APPROVED = GateSource(
    llm_cpu_ram_required_mib=4950,
    asr_cpu_ram_required_mib=2048,
    pinned_model_digests=dict.fromkeys(readiness.MODEL_ROLES, "0" * 64),
    egress_isolation_attested=True,
)
"""A source in which every gate holds an approved value.

The numbers are not proposals and nothing reads them as thresholds - they
exist so the report has something non-``None`` to render. Picking them here
rather than in :mod:`benchmarks.preflight` is the point: a test may invent a
number, a gate may not.
"""


class TestTheReportAgreesWithTheGates:
    """Each row must match what the gate function actually does."""

    def test_every_gate_has_a_behavioural_probe(self) -> None:
        """Completeness, in the direction that can rot.

        ``GATE_IDS`` is hand-written, so the risk is a gate being added to
        ``preflight`` and never reaching the report - or reaching it as a row
        nobody checked against real behaviour. Requiring a probe per id means
        the second cannot happen quietly.
        """
        assert set(PROBES) == set(GATE_IDS), (
            f"probes {sorted(PROBES)} vs GATE_IDS {sorted(GATE_IDS)}. "
            "A gate was added or renamed. Add a probe that calls the real gate "
            "function and observes it refusing, not just a row in the report."
        )

    def test_the_report_lists_each_gate_once_in_order(self) -> None:
        gates = readiness.level_b_gates()
        assert tuple(gate.gate_id for gate in gates) == GATE_IDS

    @pytest.mark.parametrize("gate_id", GATE_IDS)
    def test_a_gate_the_report_calls_pending_really_refuses(self, gate_id: str) -> None:
        """The load-bearing assertion of this file.

        If the report says a gate is open, the gate must refuse. Not asserted
        against the constant - asserted against the function a benchmark
        actually calls, so the report cannot drift from enforcement while both
        still look consistent with the same stale constant.
        """
        gate = next(g for g in readiness.level_b_gates() if g.gate_id == gate_id)
        if gate.approved:
            pytest.skip(f"{gate_id} is approved; the pending direction is moot")
        with pytest.raises((PreflightRefused, DigestNotPinned)):
            PROBES[gate_id]()

    def test_all_four_gates_are_open_today(self) -> None:
        """A snapshot of the current state, and a tripwire if it changes.

        Deliberately not written as "the report matches the constants". If any
        of these flips, that is an owner decision landing, and the right
        response is to record it in the runbook and in PROJECT_STATE - not to
        update this number.
        """
        findings = readiness.report()
        assert findings["pending_gate_ids"] == list(GATE_IDS)
        assert findings["all_listed_gates_approved"] is False


class TestNothingIsHardcoded:
    """The approved direction, which the live constants cannot exercise."""

    def test_an_approved_source_flips_every_row(self) -> None:
        gates = readiness.level_b_gates(ALL_APPROVED)
        assert [gate.approved for gate in gates] == [True] * len(GATE_IDS)
        assert readiness.report(ALL_APPROVED)["pending_gate_ids"] == []

    def test_an_approved_source_renders_without_the_pending_marker(self) -> None:
        rendered = readiness.render(ALL_APPROVED)
        assert "CHUA" not in rendered, rendered

    @pytest.mark.parametrize("gate_id", GATE_IDS)
    def test_one_gate_still_pending_keeps_the_report_pending(self, gate_id: str) -> None:
        """Approval is not a single switch, so neither is the report.

        Each gate is turned back off on its own against an otherwise approved
        source. Without this, a report that ``and``-ed the wrong pair, or read
        one gate twice, would pass every test above.
        """
        withdraw: dict[str, Callable[[], GateSource]] = {
            "llm-cpu-ram": lambda: dataclasses.replace(
                ALL_APPROVED, llm_cpu_ram_required_mib=None
            ),
            "asr-cpu-ram": lambda: dataclasses.replace(
                ALL_APPROVED, asr_cpu_ram_required_mib=None
            ),
            "model-digest": lambda: dataclasses.replace(
                ALL_APPROVED, pinned_model_digests={}
            ),
            "egress-isolation": lambda: dataclasses.replace(
                ALL_APPROVED, egress_isolation_attested=False
            ),
        }
        source = withdraw[gate_id]()
        findings = readiness.report(source)
        assert findings["pending_gate_ids"] == [gate_id]
        assert findings["all_listed_gates_approved"] is False

    def test_a_digest_pinned_for_only_one_role_is_not_enough(self) -> None:
        """Per-role, because the ledger is per-role.

        Pinning the LLM model and running ASR would otherwise pass a gate that
        never saw the file it was supposed to approve.
        """
        source = dataclasses.replace(
            ALL_APPROVED, pinned_model_digests={"llm-model": "0" * 64}
        )
        gate = next(
            g for g in readiness.level_b_gates(source) if g.gate_id == "model-digest"
        )
        assert gate.approved is False
        assert "asr-model" in gate.state


class TestTheReportClaimsNothingItCannotSupport:
    """The hazard here is a readiness report that reads as a green light."""

    #: Words that would turn this report into a permission. Checked as
    #: substrings of the lowercased output, so a longer phrase containing one
    #: is caught too.
    FORBIDDEN = (
        "san sang",
        "ready",
        "duoc phep chay",
        "co the chay model",
        "da dong het",
    )

    @pytest.mark.parametrize("source", [None, ALL_APPROVED], ids=["live", "approved"])
    def test_no_rendering_claims_readiness(self, source: GateSource | None) -> None:
        """Asked of the approved source too, which is the dangerous one.

        With every gate green the obvious next sentence is "ready to run", and
        that sentence would be false: choosing a measurement method, choosing
        a model and permitting a supervised run are not constants and are not
        in this report.
        """
        lowered = readiness.render(source).lower()
        for word in self.FORBIDDEN:
            assert word not in lowered, f"{word!r} in the report: {lowered}"

    def test_the_json_states_it_is_not_a_permission(self) -> None:
        """As a field, because a JSON consumer never sees the prose."""
        for source in (None, ALL_APPROVED):
            findings = readiness.report(source)
            assert findings["is_permission_to_run"] is False
            assert findings["level_a_depends_on_these_gates"] is False

    def test_the_report_never_prints_a_digest_value(self) -> None:
        """A digest fingerprints a file on the owner's machine.

        The report names roles and says pinned or not. Driven with a canary
        digest through both renderings, so an implementation that helpfully
        showed what it compared against fails here.
        """
        canary = "deadbeef" * 8
        source = dataclasses.replace(
            ALL_APPROVED, pinned_model_digests={"llm-model": canary}
        )
        assert canary not in readiness.render(source)
        assert canary not in json.dumps(readiness.report(source))

    def test_the_human_output_is_ascii(self) -> None:
        """A Windows console code page is usually not UTF-8."""
        for source in (None, ALL_APPROVED):
            rendered = readiness.render(source)
            assert rendered.isascii(), [c for c in rendered if not c.isascii()]

    def test_every_gate_field_is_ascii(self) -> None:
        for source in (None, ALL_APPROVED):
            for gate in readiness.level_b_gates(source):
                for field in (gate.gate_id, gate.title, gate.state, gate.unblocked_by):
                    assert field.isascii(), field


class TestTheExitCode:
    """``$?`` is what a script reads, so it carries the state."""

    def test_pending_gates_exit_non_zero(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        assert readiness.main([]) == EXIT_GATE_PENDING
        assert "cong" in capsys.readouterr().out

    def test_json_mode_exits_the_same_way(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Same verdict through a different renderer.

        The exit code is computed from the report rather than from the text,
        so the two modes cannot disagree - which is worth an assertion because
        a ``--json`` branch that returned 0 unconditionally would be invisible
        in the human path.
        """
        assert readiness.main(["--json"]) == EXIT_GATE_PENDING
        parsed = json.loads(capsys.readouterr().out)
        assert parsed["all_listed_gates_approved"] is False
        assert parsed["level"] == "B"

    def test_exit_zero_is_reachable_only_with_every_gate_approved(self) -> None:
        """The other branch, proved without touching a constant.

        ``main`` reads the live source, so this exercises the decision rather
        than the command: an exit rule that ignored one gate, or returned 0 on
        "the report rendered", differs here.
        """
        findings = readiness.report(ALL_APPROVED)
        approved = findings["all_listed_gates_approved"]
        assert (EXIT_ALL_APPROVED if approved is True else EXIT_GATE_PENDING) == 0
        pending = readiness.report()
        assert pending["all_listed_gates_approved"] is not True


class TestItOnlyReads:
    """The constraint that makes this safe to run at any time."""

    FORBIDDEN_IMPORTS = frozenset(
        {"subprocess", "socket", "urllib", "http", "ctypes", "shutil", "os"}
    )

    def test_the_module_imports_nothing_that_can_act(self) -> None:
        """AST, not grep: an import is a statement node, not a word.

        ``preflight`` and ``artifacts`` are imported and those do reach
        ``subprocess`` and ``ctypes`` - which is why this checks what *this*
        module can reach directly, and the test below checks that none of it
        runs.
        """
        tree = ast.parse(MODULE.read_text(encoding="utf-8"))
        imported: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module.split(".")[0])
        offenders = imported & self.FORBIDDEN_IMPORTS
        assert not offenders, f"readiness.py imports {sorted(offenders)}"

    def test_the_live_source_reads_its_attributes_directly(self) -> None:
        """A structural guard, and the reason it has to be structural.

        ``getattr(preflight, "CPU_RAM_MARGIN_MIB", None)`` would survive a
        rename and report "pending" forever - a refusal-shaped lie that no
        behavioural test in this file can catch, because the behavioural
        probes refuse today too, so the report and the gate would agree while
        both were wrong about the same renamed constant.

        Measured: mutating ``live_source`` to read a misspelled attribute
        through ``getattr`` with a default left every other test in this file
        passing. This is the one place where asserting on the shape of the
        code is the only assertion available.
        """
        tree = ast.parse(MODULE.read_text(encoding="utf-8"))
        function = next(
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.FunctionDef) and node.name == "live_source"
        )
        calls = [
            node.func.id
            for node in ast.walk(function)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
        ]
        assert "getattr" not in calls, (
            "live_source reads a constant through getattr. A default turns a "
            "renamed constant into a permanent 'pending', which looks safe and "
            "is false. Read the attribute directly and let it raise."
        )

    def test_no_subprocess_runs_and_no_memory_is_read(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Behavioural, because an import check is a proxy.

        Every way the benchmark package starts a process or reads host memory
        is replaced with something that fails the test if called. A report
        that quietly called ``nvidia-smi`` for context, or printed how much
        RAM is free beside a policy refusal, stops here.

        Reading free memory is forbidden rather than merely unnecessary: all
        four gates fail on the absence of an approved policy, and no amount of
        free memory changes that. Printing a memory figure next to such a
        refusal is how an operator comes to close applications and retry.
        """

        def forbidden(*args: object, **kwargs: object) -> object:
            raise AssertionError("readiness must not start a process or read memory")

        monkeypatch.setattr(subprocess, "run", forbidden)
        monkeypatch.setattr(subprocess, "Popen", forbidden)
        monkeypatch.setattr(preflight, "read_available_ram_mib", forbidden)
        monkeypatch.setattr(preflight, "read_vram", forbidden)

        assert readiness.main([]) == EXIT_GATE_PENDING
        assert readiness.main(["--json"]) == EXIT_GATE_PENDING
        assert capsys.readouterr().out

    def test_running_the_report_changes_no_file_under_the_repo(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """A snapshot either side, over the tracked source tree.

        Limited to ``benchmarks/``, ``src/`` and ``var/`` rather than the whole
        repository: that is where this module could plausibly write, and
        walking the virtualenv would make the test slow enough to be skipped.
        ``__pycache__`` is excluded - bytecode is not data, and the first cold
        run writes it.
        """

        def snapshot() -> dict[str, float]:
            seen: dict[str, float] = {}
            for root in ("benchmarks", "src", "var"):
                base = REPO / root
                if not base.exists():
                    continue
                for path in base.rglob("*"):
                    if "__pycache__" in path.parts or not path.is_file():
                        continue
                    seen[str(path)] = path.stat().st_mtime
            return seen

        before = snapshot()
        readiness.main([])
        readiness.main(["--json"])
        capsys.readouterr()
        after = snapshot()

        assert set(after) - set(before) == set(), "a file was created"
        assert set(before) - set(after) == set(), "a file was removed"
        assert [k for k in before if after[k] != before[k]] == [], "a file changed"


class TestLevelADoesNotDependOnTheseGates:
    """The report says so, so it has to be true."""

    def test_no_module_under_src_imports_the_benchmark_package(self) -> None:
        """The dependency direction, by AST over the whole package.

        ``benchmarks`` imports ``meetai``; the reverse would mean the level-A
        commands could be blocked by a benchmark gate, and the report's
        statement that they are not would be false. Checked structurally
        rather than by reading the two entry points, because a new module
        under ``src/`` is the way this would change.
        """
        offenders: list[str] = []
        for path in sorted((REPO / "src").rglob("*.py")):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    names = [alias.name for alias in node.names]
                elif isinstance(node, ast.ImportFrom):
                    names = [node.module or ""]
                else:
                    continue
                if any(name.split(".")[0] == "benchmarks" for name in names):
                    offenders.append(f"{path.name}:{node.lineno}")
        assert offenders == [], (
            f"src/ now imports benchmarks at {offenders}. The readiness report "
            "states that level A does not pass through these gates; either that "
            "is no longer true, or the import is a mistake."
        )
