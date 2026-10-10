"""A benchmark refusal must not echo the path it was handed.

Measured at ``bb848b8``, before this file existed: running
``bench_llm_policy --model C:/Users/canary-operator/secret-staging/model.gguf`` printed

    khong tim thay model: C:/Users/canary-operator/secret-staging/model.gguf

and five other scripts did the same in their own wording. Benchmark stderr is
quoted into reports, so the staging layout and the Windows account name went
with it. ``tests/test_no_value_in_errors.py`` never caught it because that file
is scoped to ``src/meetai``; ``benchmarks/`` was outside every leak test.

**Why this file was rewritten.** Its first version ran **7 cases** against **16
artifact checks**, and the cases were not the checks: each loop-style CLI stops
at the *first* missing input, so which branch a case reached depended on what
happened to be installed. Both ``var/`` binaries exist on the development
machine, so ``bench_asr`` reached ``manifest`` and its ``whisper-binary`` branch
never ran; on a fresh checkout the same test would have passed while exercising
a different branch. The assertion did not notice, because it only required the
role to be *some* member of the allowlist. Nine of sixteen branches were
unexercised and the file read as though all of them were covered.

So the matrix below is derived from source and **asserted against source**
(:meth:`TestTheMatrixIsTheSource.test_the_matrix_matches_the_source`), every
branch gets its own case with its prerequisites staged in ``tmp_path``, and each
case demands the **exact** role rather than allowlist membership.

Four kinds of assertion, because the obvious one passes for free:

1. **Behavioural, per branch** - exit code, the exact expected role, and the
   canary absent from stdout, stderr and the exception text. On its own,
   "no canary in the output" also holds for a ``main()`` that prints nothing.
2. **The matrix is the source** - the 16 entries equal what the AST says, in
   order, so a new check cannot be added without a case.
3. **Controls** - the leak checker can fail; roles are distinct within a module,
   so demanding the exact one actually discriminates; and a deliberately
   missing prerequisite fires the *earlier* branch, which is the failure mode
   the first version of this file had.
4. **Structural** - every call site resolves to literals from the allowlist,
   since ``missing_artifact(str(path))`` would pass 1 and 3 on branches nobody
   runs.

Nothing here launches a binary, loads a model, touches a GPU or opens a socket.
Every case leaves one input missing so the CLI refuses inside the check
sequence, and a fence monkeypatches ``subprocess``, ``preload_cuda`` and
``gpu_benchmark_lock`` to raise, so a test that ever got past the checks would
fail loudly instead of starting a benchmark.
"""

from __future__ import annotations

import ast
import importlib
import pathlib
import subprocess
import sys
from collections.abc import Iterator
from dataclasses import dataclass

import pytest
from benchmarks.refusals import ARTIFACT_ROLES, MISSING_ARTIFACT_CODE

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
BENCHMARKS = REPO_ROOT / "benchmarks"

# A path shaped like real staging: an absolute Windows path, a username and a
# directory name that says what the leak would reveal. Every fragment is
# checked separately, because a message that prints only the basename is still
# a leak and would pass a whole-path check.
#
# "canary-operator" earns its place twice: it is the username inside the canary, and it
# is also inside ``tmp_path`` on this machine, so the same assertion catches a
# refusal that echoed a staged *prerequisite* path instead of the canary.
CANARY_DIR = "C:/Users/canary-operator/secret-staging"
CANARY_FRAGMENTS = (
    CANARY_DIR,
    CANARY_DIR.replace("/", "\\"),
    "secret-staging",
    "canary-operator",
    "canary-artifact",
)


@dataclass(frozen=True)
class Slot:
    """One artifact check, in the order its CLI evaluates them.

    ``kind`` says how the path reaches the check, which is what decides how a
    test stages it:

    - ``arg`` - a CLI flag, so the test just points it somewhere;
    - ``const`` - a module-level constant under ``var/``, monkeypatched so the
      case does not depend on what is installed;
    - ``const_dir`` - a module-level directory constant with ``child`` joined
      onto it inside ``main()``.
    """

    role: str
    kind: str
    key: str
    child: str = ""
    filename: str = ""
    """Basename both the placeholder and the canary must use for this slot.

    Needed once ``bench_llm_policy`` grew a closed allowlist of executable
    basenames, checked *before* the existence check. A slot whose name is not
    allowlisted is refused by name and never reaches ``artifact-missing``, so a
    case aimed at that branch has to use a permitted basename. The canary is
    still a canary: the staging directory and the username carry it, which is
    the part that must not be echoed.
    """


# Derived from source and asserted against it below. Order matters: it is the
# order each CLI checks its inputs, which is what makes a branch reachable.
MATRIX: dict[str, tuple[Slot, ...]] = {
    "benchmarks.bench_asr": (
        Slot("whisper-binary", "const", "WHISPER"),
        Slot("manifest", "arg", "--manifest"),
        Slot("asr-model", "arg", "--model"),
    ),
    "benchmarks.bench_coresidency": (
        Slot("llama-binary", "const", "LLAMA"),
        Slot("whisper-binary", "const", "WHISPER"),
        Slot("llm-model", "arg", "--llm"),
        Slot("asr-model", "arg", "--asr"),
        Slot("audio-clip", "arg", "--clip"),
    ),
    "benchmarks.bench_llamacpp": (
        Slot("llm-model", "arg", "--model"),
        Slot("llama-bench-binary", "const_dir", "BUILD_DIR", "llama-bench.exe"),
    ),
    "benchmarks.bench_llm": (Slot("llm-model", "arg", "--model"),),
    "benchmarks.bench_llm_policy": (
        Slot("llm-binary", "arg", "--binary", filename="llama-cli.exe"),
        Slot("llm-model", "arg", "--model"),
    ),
    "benchmarks.postprocess_asr": (
        Slot("results-json", "arg", "--results"),
        Slot("reference-tsv", "arg", "--tsv"),
        Slot("manifest", "arg", "--manifest"),
    ),
}

# Flags a CLI needs but does not check. ``--out`` is here so no case can write
# into the repository.
EXTRA_ARGV: dict[str, tuple[str, ...]] = {
    "benchmarks.bench_llm_policy": ("--out",),
}

BRANCHES: tuple[tuple[str, int], ...] = tuple(
    (module, index) for module, slots in MATRIX.items() for index in range(len(slots))
)


def leaked_fragments(text: str) -> list[str]:
    """Return the canary fragments present in ``text``."""
    return [fragment for fragment in CANARY_FRAGMENTS if fragment in text]


def _source_trees() -> Iterator[tuple[pathlib.Path, ast.Module]]:
    for path in sorted(BENCHMARKS.glob("*.py")):
        yield path, ast.parse(path.read_text(encoding="utf-8"))


def source_roles(module_name: str) -> tuple[str, ...]:
    """Return the roles a module can refuse with, in evaluation order.

    Read from the AST rather than from :data:`MATRIX`, so the two can be
    compared. A direct call contributes one role at its own line; a loop
    contributes one per tuple row, in row order.
    """
    path = BENCHMARKS / f"{module_name.rsplit('.', 1)[-1]}.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))
    found: list[tuple[int, int, str]] = []
    for call in ast.walk(tree):
        if not isinstance(call, ast.Call):
            continue
        func = call.func
        name = func.attr if isinstance(func, ast.Attribute) else getattr(func, "id", None)
        if name != "missing_artifact" or not call.args:
            continue
        arg = call.args[0]
        if isinstance(arg, ast.Constant):
            found.append((call.lineno, 0, str(arg.value)))
            continue
        if not isinstance(arg, ast.Name):
            continue
        for loop in ast.walk(tree):
            if not isinstance(loop, ast.For) or not isinstance(loop.target, ast.Tuple):
                continue
            names = [el.id for el in loop.target.elts if isinstance(el, ast.Name)]
            if arg.id not in names or not isinstance(loop.iter, ast.Tuple):
                continue
            if not any(call is node for node in ast.walk(loop)):
                continue
            slot = names.index(arg.id)
            for index, row in enumerate(loop.iter.elts):
                assert isinstance(row, ast.Tuple)
                value = row.elts[slot]
                assert isinstance(value, ast.Constant)
                found.append((loop.lineno, index, str(value.value)))
            break
    return tuple(role for _, _, role in sorted(found))


def _fence(monkeypatch: pytest.MonkeyPatch, module: object) -> None:
    """Make anything past the artifact checks fail loudly, not run.

    Every case leaves an input missing, so the CLI should return before this
    matters. The fence is here because the cost of being wrong about that is
    launching a model, and a test suite must not be one bug away from that.
    """

    def refuse(*args: object, **kwargs: object) -> object:
        raise AssertionError("reached past the artifact checks")

    for attr in ("run", "Popen", "check_output", "call", "check_call"):
        monkeypatch.setattr(subprocess, attr, refuse, raising=False)
    for attr in ("preload_cuda", "gpu_benchmark_lock", "nvidia_smi"):
        monkeypatch.setattr(module, attr, refuse, raising=False)


def _stage(
    module_name: str,
    missing_index: int,
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
    module: object,
) -> list[str]:
    """Stage every slot so that exactly ``missing_index`` is the first absent one.

    Earlier slots get a real placeholder file. The target slot and everything
    after it get canary paths: if the expected branch somehow does not fire, a
    *later* branch fires with a different role and the case fails, rather than
    the CLI running.
    """
    argv: list[str] = [module_name]
    for index, slot in enumerate(MATRIX[module_name]):
        if index < missing_index:
            name = slot.filename or f"present-{index}-{slot.child or 'input'}"
            target = tmp_path / name
            target.write_bytes(b"placeholder")
            value = str(target)
            directory = str(tmp_path)
        else:
            name = slot.filename or f"canary-artifact-{index}.bin"
            value = f"{CANARY_DIR}/{name}"
            directory = CANARY_DIR

        if slot.kind == "arg":
            argv += [slot.key, value]
        elif slot.kind == "const":
            monkeypatch.setattr(module, slot.key, pathlib.Path(value))
        elif slot.kind == "const_dir":
            # ``main()`` joins ``child`` onto the directory, so the placeholder
            # has to sit there under its real name.
            root = pathlib.Path(directory)
            if index < missing_index:
                root = tmp_path / f"build-{index}"
                root.mkdir(exist_ok=True)
                (root / slot.child).write_bytes(b"placeholder")
            monkeypatch.setattr(module, slot.key, root)
        else:  # pragma: no cover - a typo in the matrix, not a branch
            raise AssertionError(f"unknown slot kind {slot.kind!r}")

    for flag in EXTRA_ARGV.get(module_name, ()):
        argv += [flag, str(tmp_path / "out.json")]
    return argv


def _run(
    module_name: str, argv: list[str], capsys: pytest.CaptureFixture[str]
) -> tuple[object, str, str, str]:
    module = sys.modules[module_name]
    exception_text = ""
    code: object
    try:
        code = module.main()
    except SystemExit as exc:  # argparse and explicit exits both land here
        code = exc.code
        exception_text = f"{exc!r} {exc}"
    except Exception as exc:  # a crash must not leak either
        code = None
        exception_text = f"{exc!r} {exc}"
    captured = capsys.readouterr()
    return code, captured.out, captured.err, exception_text


def _refused_role(stderr: str) -> str | None:
    if f"{MISSING_ARTIFACT_CODE}:" not in stderr:
        return None
    return stderr.split(f"{MISSING_ARTIFACT_CODE}:", 1)[1].split()[0]


class TestEveryBranchRefusesWithItsOwnRole:
    """One case per artifact check - 16, not 7, and not machine-dependent."""

    @pytest.mark.parametrize(
        ("module_name", "index"),
        BRANCHES,
        ids=[f"{m.rsplit('.', 1)[-1]}-{i}-{MATRIX[m][i].role}" for m, i in BRANCHES],
    )
    def test_the_branch_names_its_role_and_leaks_nothing(
        self,
        module_name: str,
        index: int,
        tmp_path: pathlib.Path,
        capsys: pytest.CaptureFixture[str],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        module = importlib.import_module(module_name)
        _fence(monkeypatch, module)
        argv = _stage(module_name, index, tmp_path, monkeypatch, module)
        monkeypatch.setattr(sys, "argv", argv)

        code, out, err, exception_text = _run(module_name, argv, capsys)

        expected = MATRIX[module_name][index].role
        # The refusal has to actually happen, or "no canary in the output" is
        # satisfied by an empty run.
        assert code == 2, f"{module_name}[{index}] did not refuse ({code!r}): {err!r}"
        # The *exact* role, not allowlist membership: this is what proves the
        # intended branch fired rather than a neighbour.
        assert _refused_role(err) == expected, (
            f"{module_name}[{index}] expected {expected!r}, got {err!r}"
        )

        for stream_name, stream in (
            ("stdout", out),
            ("stderr", err),
            ("exception", exception_text),
        ):
            leaks = leaked_fragments(stream)
            assert not leaks, f"{module_name}[{index}] leaked {leaks} via {stream_name}"


class TestTheMatrixIsTheSource:
    """The count has to come from the code, not from this file's own table."""

    def test_the_matrix_matches_the_source(self) -> None:
        for module_name, slots in MATRIX.items():
            assert source_roles(module_name) == tuple(slot.role for slot in slots), (
                f"{module_name}: the matrix and the source disagree"
            )

    def test_the_matrix_covers_every_refusing_module(self) -> None:
        on_disk = {
            f"benchmarks.{path.stem}"
            for path, tree in _source_trees()
            if "missing_artifact(" in path.read_text(encoding="utf-8")
            and path.name != "refusals.py"
        }
        assert on_disk == set(MATRIX), f"on disk {sorted(on_disk)}"

    def test_every_allowlisted_role_is_exercised(self) -> None:
        """An unused member of a safety allowlist is dead code in that allowlist.

        This is the assertion the 7-case version could not make: it reached 4
        of the 10 roles. A role added for a future check fails here until a
        branch and a case exist for it, which is the intended pressure.
        """
        exercised = {MATRIX[module][index].role for module, index in BRANCHES}
        assert exercised == set(ARTIFACT_ROLES), (
            f"never refused with: {sorted(set(ARTIFACT_ROLES) - exercised)}"
        )

    def test_the_branch_count_is_sixteen(self) -> None:
        """Pinned because the number is quoted in PROJECT_STATE and the plan.

        Not a magic constant: :meth:`test_the_matrix_matches_the_source` ties
        the matrix to the AST, so this only pins the total those 16 add up to.
        """
        assert len(BRANCHES) == 16
        assert sum(len(source_roles(module)) for module in MATRIX) == 16


class TestTheControls:
    """A green suite above must mean these assertions can fail."""

    def test_the_checker_catches_a_planted_leak(self) -> None:
        planted = f"khong tim thay model: {CANARY_DIR}/canary-artifact-0.bin"
        assert leaked_fragments(planted), "the leak checker cannot see a leak"
        # And a basename-only leak, which a whole-path check would miss.
        assert leaked_fragments("model: canary-artifact-0.bin")

    def test_roles_are_distinct_within_each_module(self) -> None:
        """Otherwise "the exact role" could not tell two branches apart.

        Demanding an exact role is only a real assertion while no module can
        refuse twice under the same name. ``whisper-binary`` and ``asr-model``
        both appear in two *different* modules, which is fine; a repeat inside
        one module would silently weaken every case for it.
        """
        for module_name, slots in MATRIX.items():
            roles = [slot.role for slot in slots]
            assert len(set(roles)) == len(roles), f"{module_name} repeats a role: {roles}"

    def test_a_missing_prerequisite_fires_the_earlier_branch(
        self,
        tmp_path: pathlib.Path,
        capsys: pytest.CaptureFixture[str],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """The failure mode the 7-case version of this file actually had.

        ``bench_asr``'s ``manifest`` branch is only reachable while ``WHISPER``
        exists. Leave that prerequisite absent and the refusal names
        ``whisper-binary`` instead - so a case that asserted only "some role in
        the allowlist" would pass having tested a branch it did not intend, and
        which branch that was would depend on the machine.
        """
        module = importlib.import_module("benchmarks.bench_asr")
        _fence(monkeypatch, module)
        monkeypatch.setattr(module, "WHISPER", pathlib.Path(f"{CANARY_DIR}/absent.exe"))
        monkeypatch.setattr(
            sys,
            "argv",
            [
                "bench_asr",
                "--manifest",
                f"{CANARY_DIR}/canary-artifact-1.bin",
                "--model",
                f"{CANARY_DIR}/canary-artifact-2.bin",
            ],
        )

        code, _out, err, _exc = _run("benchmarks.bench_asr", [], capsys)

        assert code == 2
        assert _refused_role(err) == "whisper-binary", err
        # Which is NOT the branch the staged arguments were aiming at.
        assert _refused_role(err) != "manifest"

    def test_the_fence_would_catch_a_run_past_the_checks(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The fence is only reassuring if it is actually installed."""
        module = importlib.import_module("benchmarks.bench_llm")
        _fence(monkeypatch, module)
        with pytest.raises(AssertionError, match="past the artifact checks"):
            subprocess.run([sys.executable, "-c", ""], check=False)
        with pytest.raises(AssertionError, match="past the artifact checks"):
            module.preload_cuda()


def _role_literals_of(call: ast.Call, module: ast.Module) -> list[str]:
    """Return every role string that can reach ``call``, or ``[]`` if unknown.

    Two call shapes exist and both are literal at source level:
    ``missing_artifact("llm-model")`` for a single check, and
    ``missing_artifact(role)`` inside ``for role, path in (("manifest", p), ...)``
    for the loop checks. The second is still a closed set of literals, which is
    the property under test - so this resolves the loop variable rather than
    banning it. Anything else returns ``[]`` and fails the caller, because an
    unresolvable role is how ``str(path)`` would get in.
    """
    if len(call.args) != 1 or call.keywords:
        return []
    arg = call.args[0]
    if isinstance(arg, ast.Constant):
        return [arg.value] if isinstance(arg.value, str) else []
    if not isinstance(arg, ast.Name):
        return []
    # Find the enclosing ``for`` that binds this name to a literal tuple slot.
    for loop in ast.walk(module):
        if not isinstance(loop, ast.For) or not isinstance(loop.target, ast.Tuple):
            continue
        names = [el.id for el in loop.target.elts if isinstance(el, ast.Name)]
        if arg.id not in names or not isinstance(loop.iter, ast.Tuple):
            continue
        if not any(call is node for node in ast.walk(loop)):
            continue
        slot = names.index(arg.id)
        found: list[str] = []
        for row in loop.iter.elts:
            if not isinstance(row, ast.Tuple) or slot >= len(row.elts):
                return []
            value = row.elts[slot]
            if not isinstance(value, ast.Constant) or not isinstance(value.value, str):
                return []
            found.append(value.value)
        return found
    return []


class TestEveryCallSitePassesALiteralRole:
    """``missing_artifact(str(path))`` would pass every behavioural test above.

    It would not, in fact, survive runtime - :func:`missing_artifact` rejects an
    unlisted role - but that only protects branches a test exercises. This class
    protects the ones nobody runs.
    """

    def test_every_call_site_resolves_to_listed_literals(self) -> None:
        sites = 0
        for path, tree in _source_trees():
            for node in ast.walk(tree):
                if not isinstance(node, ast.Call):
                    continue
                func = node.func
                if isinstance(func, ast.Attribute):
                    name: str | None = func.attr
                elif isinstance(func, ast.Name):
                    name = func.id
                else:
                    name = None
                if name != "missing_artifact":
                    continue
                sites += 1
                roles = _role_literals_of(node, tree)
                assert roles, (
                    f"{path.name}:{node.lineno} passes a role this test cannot "
                    "resolve to literals - a computed role is how a path gets out"
                )
                unlisted = [role for role in roles if role not in ARTIFACT_ROLES]
                assert not unlisted, f"{path.name}:{node.lineno} passes {unlisted}"
        # One site per refusal branch, and the loop-style checks share a site
        # across several roles, so the floor is the number of refusing modules.
        assert sites >= len(MATRIX), f"only {sites} call sites found"

    def test_the_resolver_rejects_a_computed_role(self) -> None:
        """The control for the resolver: it must not resolve ``str(path)``."""
        leaky = ast.parse("missing_artifact(str(args.model))\n")
        call = next(
            node
            for node in ast.walk(leaky)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "missing_artifact"
        )
        assert _role_literals_of(call, leaky) == []

    def test_no_benchmark_still_formats_a_path_into_a_missing_file_message(self) -> None:
        """The old wording, as a regression pin on the exact measured bug.

        ``refusals.py`` is excluded because its docstring quotes the old line
        on purpose, as the record of what was measured. The exclusion cannot
        hide a real leak there: the companion assert is that the module prints
        nothing at all.
        """
        old_wordings = (
            "khong ton tai: {",
            "khong tim thay binary: {",
            "khong tim thay model: {",
        )
        offenders = [
            f"{path.name}: {old!r}"
            for path in sorted(BENCHMARKS.glob("*.py"))
            if path.name != "refusals.py"
            for old in old_wordings
            if old in path.read_text(encoding="utf-8")
        ]
        assert not offenders, offenders

        refusals_tree = ast.parse(
            (BENCHMARKS / "refusals.py").read_text(encoding="utf-8")
        )
        writes = [
            node.lineno
            for node in ast.walk(refusals_tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "print"
        ]
        assert not writes, f"refusals.py writes to a stream at {writes}"

    def test_the_discovery_actually_reads_the_benchmarks(self) -> None:
        """A glob that matches nothing makes both tests above pass for free."""
        seen = [path.name for path, _ in _source_trees()]
        assert len(seen) >= 17, seen
        for module_name in MATRIX:
            assert f"{module_name.rsplit('.', 1)[-1]}.py" in seen
