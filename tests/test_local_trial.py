"""What Son can actually run today, pinned as properties of the run itself.

Son chose the local synthetic level for an early trial: ``meetai dry-run`` and
``meetai status``, CPU-only, no model, no audio, no Discord, no persistence.
The success criteria agreed were safety, answering only on evidence,
repeatability, and an explicit statement of what the run does **not** prove.
``tests/test_dryrun.py`` already covers the first two thoroughly. This file
covers the two nobody had measured:

**Repeatability.** Nothing asserted that two runs produce the same bytes.
Measured by hand it was true, but a hand measurement is not a guarantee, and a
report Son is asked to trust has to be reproducible before any number in it
means anything.

**Writing nothing.** ``test_dryrun.py::test_the_module_opens_no_file`` carries
the docstring *"No persistence, and nothing to leave behind on disk"*, which is
stronger than what it checks: it parses ``dryrun.py`` alone, looks for ``open``
only as a bare name, and forbids four attribute names. Measured at ``b814271``,
``pathlib.Path(p).open("w")`` followed by ``fh.write(...)`` passes it - ``open``
appears as an *attribute*, and ``write`` is not on the list. It also says
nothing about ``cli.py`` or ``logging_setup.py``, and a ``FileHandler``
configured in either would persist data without touching ``dryrun.py`` at all.

So the claim is re-made here against the running process rather than one
module's syntax: no write entry point is called, and the repository tree is
byte-identical afterwards.

Nothing here loads a model, touches a GPU, opens a socket, joins Discord or
processes audio. Every case runs ``cli.main`` in process.
"""

from __future__ import annotations

import builtins
import json
import os
import pathlib
from typing import Any

import pytest

from meetai import cli

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent

# The invocations Son is being told he can run. Kept in one place so a new
# documented command cannot quietly escape these properties.
LOCAL_COMMANDS: tuple[tuple[str, ...], ...] = (
    ("dry-run",),
    ("dry-run", "--json"),
    ("status",),
    ("status", "--json"),
)

# Snapshot cost is ~0.4 s per pass over ~8900 paths, so the tree check runs
# once for all commands rather than once per command.
_SNAPSHOT_SKIP = frozenset(
    {".git", "__pycache__", ".venv", ".mypy_cache", ".ruff_cache", ".pytest_cache"}
)


def _run(
    argv: tuple[str, ...], capsys: pytest.CaptureFixture[str]
) -> tuple[int, str, str]:
    code = cli.main(list(argv))
    captured = capsys.readouterr()
    return code, captured.out, captured.err


def _snapshot() -> dict[str, tuple[int, int]]:
    """Path -> (size, mtime_ns) for the whole repository.

    ``__pycache__`` is excluded because bytecode is not data: a cold first run
    legitimately writes it. Everything else is included, ``var/`` and
    ``models/`` among them, because those are exactly where a stray artifact
    would land.
    """
    out: dict[str, tuple[int, int]] = {}
    for path in REPO_ROOT.rglob("*"):
        if any(part in _SNAPSHOT_SKIP for part in path.parts):
            continue
        try:
            stat = path.stat()
        except OSError:  # a file that vanished under us is not our write
            continue
        out[str(path.relative_to(REPO_ROOT))] = (stat.st_size, stat.st_mtime_ns)
    return out


class _WriteRecorder:
    """Records every call that could put bytes on disk.

    Reads are deliberately allowed: loading configuration opens ``.env``, and a
    recorder that fired on reads would have to be weakened until it fired on
    nothing.
    """

    def __init__(self) -> None:
        self.calls: list[str] = []

    def install(self, monkeypatch: pytest.MonkeyPatch) -> None:
        real_open = builtins.open
        real_path_open = pathlib.Path.open
        real_os_open = os.open

        def guarded_open(file: Any, mode: str = "r", *args: Any, **kwargs: Any) -> Any:
            if any(flag in mode for flag in "wax+"):
                self.calls.append(f"open(mode={mode!r})")
            return real_open(file, mode, *args, **kwargs)

        def guarded_path_open(
            self_: pathlib.Path, mode: str = "r", *args: Any, **kwargs: Any
        ) -> Any:
            if any(flag in mode for flag in "wax+"):
                self.calls.append(f"Path.open(mode={mode!r})")
            return real_path_open(self_, mode, *args, **kwargs)

        def guarded_os_open(path: Any, flags: int, *args: Any, **kwargs: Any) -> Any:
            writing = flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_APPEND)
            if writing:
                self.calls.append(f"os.open(flags={flags})")
            return real_os_open(path, flags, *args, **kwargs)

        monkeypatch.setattr(builtins, "open", guarded_open)
        monkeypatch.setattr(pathlib.Path, "open", guarded_path_open)
        monkeypatch.setattr(os, "open", guarded_os_open)

        # The convenience wrappers do not all route through the three above on
        # every platform, so each is recorded in its own right.
        for owner, attr in (
            (pathlib.Path, "write_text"),
            (pathlib.Path, "write_bytes"),
            (pathlib.Path, "mkdir"),
            (pathlib.Path, "touch"),
            (pathlib.Path, "unlink"),
            (pathlib.Path, "rename"),
            (pathlib.Path, "replace"),
            (os, "makedirs"),
            (os, "mkdir"),
            (os, "remove"),
            (os, "rename"),
        ):
            name = f"{getattr(owner, '__name__', owner)}.{attr}"

            def record(*args: Any, _name: str = name, **kwargs: Any) -> None:
                self.calls.append(_name)
                raise AssertionError(f"the run called {_name}")

            monkeypatch.setattr(owner, attr, record, raising=False)


class TestTheRunIsRepeatable:
    """A number Son is asked to trust has to come back the same way twice."""

    @pytest.mark.parametrize(
        "argv", LOCAL_COMMANDS, ids=[" ".join(a) for a in LOCAL_COMMANDS]
    )
    def test_the_report_is_byte_identical_across_three_runs(
        self, argv: tuple[str, ...], capsys: pytest.CaptureFixture[str]
    ) -> None:
        results = [_run(argv, capsys) for _ in range(3)]
        codes = {code for code, _, _ in results}
        assert codes == {0}, f"{argv} exited {codes}"
        outputs = {out for _, out, _ in results}
        assert len(outputs) == 1, f"{argv} produced {len(outputs)} different reports"
        # And it has to have said something, or "identical" is trivially true.
        assert results[0][1].strip(), f"{argv} printed nothing"

    def test_the_json_report_has_a_stable_key_set(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Byte equality already implies this, but it localises a failure.

        If a future report grows a timestamp, byte equality fails with a diff
        of the whole document; this says which key moved.
        """
        first = json.loads(_run(("dry-run", "--json"), capsys)[1])
        second = json.loads(_run(("dry-run", "--json"), capsys)[1])
        assert sorted(first) == sorted(second)
        assert first == second

    def test_the_comparison_would_notice_a_difference(self) -> None:
        """The control: a green suite above must mean the check can fail."""
        # Built from variables rather than written twice: a literal duplicate
        # in a set is a lint error, and the point here is the collapse, not
        # the spelling.
        same = "a\n"
        differs_by_one_space = "a \n"
        assert len({same, same}) == 1
        assert len({same, differs_by_one_space}) == 2

    def test_the_human_report_names_every_case_and_its_total(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Readability as a property: the text must not silently drop a case.

        The JSON form is complete by construction; the human form is assembled
        by hand, and a report that omitted a case would read as though the run
        were smaller than it was.
        """
        from meetai import dryrun

        _code, out, _err = _run(("dry-run",), capsys)
        missing = [case.case_id for case in dryrun.CASES if case.case_id not in out]
        assert not missing, f"the rendered report omits {missing}"
        assert f"Tong: {len(dryrun.CASES)} case" in out


class TestTheTrialCanActuallyFail:
    """The whole value of the trial is that a deviation exits non-zero.

    ``test_dryrun.py::test_a_deviation_exits_non_zero`` carries the docstring
    *"A check whose failure exits 0 is a check nobody notices"* and then
    asserts only ``EXIT_DRYRUN_UNEXPECTED != EXIT_OK`` - two constants being
    different. Measured at ``b814271``, nothing drove a deviating case through
    ``cli.main``, in either output mode. So the one property Son is being asked
    to rely on - run it, and a zero exit means the cases behaved - rested on
    reading the wiring rather than exercising it.

    Two links, measured separately: that a real deviation is *detected*, and
    that detection reaches the *exit code*.
    """

    def test_a_real_deviation_is_detected_by_the_real_machinery(self) -> None:
        import dataclasses

        from meetai import dryrun

        # A genuine case with the wrong expectation written beside it: the
        # pipeline is untouched, only the claim about where it should land.
        wrong = dataclasses.replace(
            dryrun.CASES[0], expected_stage=dryrun.CASES[1].expected_stage
        )
        results, sink = dryrun.run(cases=(wrong,))
        findings = dryrun.report(results, emitted=dryrun.emitted_count(sink))

        assert results[0].matches_expectation is False
        assert findings["unexpected"] == [wrong.case_id]

    @pytest.mark.parametrize(
        "argv", [("dry-run",), ("dry-run", "--json")], ids=["text", "json"]
    )
    def test_a_deviation_reaches_the_exit_code(
        self,
        argv: tuple[str, ...],
        capsys: pytest.CaptureFixture[str],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """The link the constant comparison could not see.

        ``cli._dry_run`` calls ``run()`` and ``dryrun.main()`` with no
        arguments, and ``run``'s ``cases`` default is bound at definition
        time - so ``monkeypatch.setattr(dryrun, "CASES", ...)`` silently
        changes nothing. Measured. The two entry points are stubbed instead,
        which is the right seam anyway: the detection logic is covered by the
        test above, and what is under test here is the wiring to the exit code.
        """
        import dataclasses

        from meetai import dryrun

        wrong = dataclasses.replace(
            dryrun.CASES[0], expected_stage=dryrun.CASES[1].expected_stage
        )
        real_run = dryrun.run

        def deviating_run(**kwargs: Any) -> Any:
            kwargs.pop("cases", None)
            return real_run(cases=(wrong,), **kwargs)

        def deviating_main() -> tuple[str, bool]:
            results, sink = real_run(cases=(wrong,))
            findings = dryrun.report(results, emitted=dryrun.emitted_count(sink))
            unexpected = findings["unexpected"]
            return dryrun.render(findings), not (
                isinstance(unexpected, list) and unexpected
            )

        monkeypatch.setattr(dryrun, "run", deviating_run)
        monkeypatch.setattr(dryrun, "main", deviating_main)

        code = cli.main(list(argv))
        out = capsys.readouterr().out
        assert code == cli.EXIT_DRYRUN_UNEXPECTED, f"{argv} exited {code}"
        assert code != cli.EXIT_OK
        # And the report has to say so, not just the exit code: an operator
        # reading the text must not have to check `$?` to find out.
        assert wrong.case_id in out

    def test_the_undeviated_run_still_exits_zero(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """The control: the test above must not pass because 5 is returned always."""
        for argv in (("dry-run",), ("dry-run", "--json")):
            assert cli.main(list(argv)) == cli.EXIT_OK
            capsys.readouterr()


class TestTheHumanReportKeepsWhatAReaderJudgesOn:
    """The text report is a strict subset of the JSON, which is correct - a
    rendered report should be shorter than the data. So the property worth
    pinning is not "nothing is omitted" but "what a reader judges on is there",
    which :meth:`TestTheRunIsRepeatable.test_the_human_report_names_every_case_and_its_total`
    covers.

    An earlier version of this class tried to pin the omitted *set* by asking
    which JSON key names fail to appear in the text. It measured the wrong
    thing and is gone: ``case_count`` renders as ``Tong: 12 case``, so the
    information is present while the key name is not. A check that conflates
    those two gives coverage credit for nothing - the failure mode AGENTS.md
    names. The omission set is recorded in the research note as a measured
    fact instead, because I found no clean mechanical way to assert it.
    """

    def test_the_two_denials_survive_as_prose(self) -> None:
        """``is_production_integration`` is absent as a *field*, not as a claim.

        Dropping the field would be fine; dropping the denial would not, and
        the two are easy to confuse when reconciling the sets above.
        """
        from meetai import dryrun

        results, sink = dryrun.run()
        rendered = dryrun.render(
            dryrun.report(results, emitted=dryrun.emitted_count(sink))
        )
        lowered = rendered.lower()
        assert "khong phai thu nghiem discord" in lowered
        assert "khong phai tich hop production" in lowered


class TestTheRunWritesNothing:
    """Re-made against the process, because the module-level check is weaker.

    ``test_dryrun.py::test_the_module_opens_no_file`` parses one module and
    checks four attribute names. Measured: ``Path(p).open("w")`` plus
    ``fh.write(...)`` passes it, and it says nothing about ``cli.py`` or a
    ``logging`` ``FileHandler``.
    """

    @pytest.mark.parametrize(
        "argv", LOCAL_COMMANDS, ids=[" ".join(a) for a in LOCAL_COMMANDS]
    )
    def test_no_write_entry_point_is_called(
        self,
        argv: tuple[str, ...],
        capsys: pytest.CaptureFixture[str],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        recorder = _WriteRecorder()
        recorder.install(monkeypatch)
        code, out, _err = _run(argv, capsys)
        assert code == 0
        assert not recorder.calls, f"{argv} wrote: {recorder.calls}"
        # The run has to have happened, or nothing was being watched.
        assert out.strip(), f"{argv} printed nothing"

    def test_the_recorder_catches_a_write(
        self, tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The control, in both shapes the existing module check misses."""
        recorder = _WriteRecorder()
        recorder.install(monkeypatch)

        target = tmp_path / "canary.txt"
        with pathlib.Path(target).open("w", encoding="utf-8") as handle:
            handle.write("x")
        assert recorder.calls, "Path.open('w') went unrecorded"

        recorder.calls.clear()
        with pytest.raises(AssertionError, match="write_text"):
            target.write_text("x", encoding="utf-8")
        assert recorder.calls == ["Path.write_text"]

    def test_a_read_is_not_recorded_as_a_write(
        self, tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Otherwise the recorder would have to be weakened to stay green."""
        target = tmp_path / "readable.txt"
        target.write_text("x", encoding="utf-8")

        recorder = _WriteRecorder()
        recorder.install(monkeypatch)
        with pathlib.Path(target).open(encoding="utf-8") as handle:
            handle.read()
        assert recorder.calls == []

    def test_the_repository_tree_is_unchanged_by_every_command(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """The outer check: whatever route a write took, the tree would show it."""
        before = _snapshot()
        # A snapshot of nothing would make this pass for free.
        assert len(before) > 100, f"snapshot saw only {len(before)} paths"

        for argv in LOCAL_COMMANDS:
            code, _out, _err = _run(argv, capsys)
            assert code == 0, f"{argv} exited {code}"

        after = _snapshot()
        created = sorted(set(after) - set(before))
        removed = sorted(set(before) - set(after))
        changed = sorted(
            key for key in set(before) & set(after) if before[key] != after[key]
        )
        assert not created, f"created: {created}"
        assert not removed, f"removed: {removed}"
        assert not changed, f"changed: {changed}"
