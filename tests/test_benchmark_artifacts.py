"""Where artifacts may be written, and the digest that must be pinned first.

Two S2.1 decisions, both **[CHỐT THEO ỦY QUYỀN CỦA SƠN]** on 2026-10-10:

**#1 - the digest is mandatory and there is no override.** ``--no-hash``
existed and had been used in 2 of the 7 recorded measurements, which wrote
``"sha256": "skipped"`` into the artifact. A flag that turns a check off is
the shape of the problem, not a convenience: the artifact still looked
complete. So the flag is gone, the digest is always computed, and - the part
that makes it a *check* rather than a *record* - a run refuses unless the
digest is pinned in committed source.

**#2 - the artifact root is fixed, relative and git-ignored.** Not
configurable, inheriting the argument already settled for ``state_dir``: a
relative path inside the project cannot name a network drive or a
cloud-synced directory, and it does not need to recognise either one to
exclude both.

The ledger is **empty on purpose**. It refuses by the absence of an approved
digest, exactly as ``CPU_RAM_MARGIN_MIB`` refuses by the absence of an
approved threshold - the policy is decided, the value stays the owner's.
Nothing here loads a model, hashes a real artifact, spawns anything or
touches the network.
"""

from __future__ import annotations

import ast
import pathlib

import pytest
from benchmarks.artifacts import (
    ARTIFACT_ROOT,
    PINNED_MODEL_DIGESTS,
    ArtifactPathRefused,
    DigestNotPinned,
    DigestRefused,
    artifact_path,
    require_pinned_digest,
)

from tests.conftest import code_tokens

A_DIGEST = "a" * 64
B_DIGEST = "b" * 64


class TestTheArtifactRootIsFixed:
    def test_it_is_relative_and_inside_the_project(self) -> None:
        assert not ARTIFACT_ROOT.is_absolute()
        assert ".." not in ARTIFACT_ROOT.parts
        assert ARTIFACT_ROOT.parts[0] == "var"

    def test_it_is_git_ignored(self) -> None:
        """Otherwise a measurement could be committed by accident.

        Artifacts can embed prompts and model output, and git history does not
        forget. ``.gitignore`` already lists ``var/``; this asserts the root
        and the ignore rule have not drifted apart.
        """
        ignore = (
            pathlib.Path(__file__).resolve().parent.parent / ".gitignore"
        ).read_text(encoding="utf-8")
        assert f"{ARTIFACT_ROOT.as_posix()}/" in ignore.splitlines()

    def test_a_normal_name_lands_under_the_root(self) -> None:
        assert artifact_path("bench", "x.json") == ARTIFACT_ROOT / "bench" / "x.json"

    @pytest.mark.parametrize(
        "parts",
        [
            ("..", "escape.json"),
            ("bench", "..", "..", "escape.json"),
            ("C:/elsewhere/x.json",),
            ("/absolute/x.json",),
            ("\\\\server\\share\\x.json",),
            ("D:x.json",),
            ("",),
        ],
    )
    def test_everything_that_leaves_the_root_is_refused(
        self, parts: tuple[str, ...]
    ) -> None:
        with pytest.raises(ArtifactPathRefused):
            artifact_path(*parts)

    def test_the_refusal_names_a_code_and_not_the_path(self) -> None:
        """The same rule as ``refusals.py``: a shape, never the operator's input."""
        with pytest.raises(ArtifactPathRefused) as caught:
            artifact_path("C:/Users/someone/staging/x.json")
        rendered = str(caught.value)
        assert "artifact-path-" in rendered
        assert "someone" not in rendered
        assert "staging" not in rendered
        assert "C:" not in rendered

    def test_it_takes_no_environment_override(self) -> None:
        """Decision #2 was "fixed", so there is no variable to read.

        Checked as the absence of a lookup rather than by setting a variable
        and hoping: a module that reads no environment cannot be redirected by
        one.

        Over :func:`code_tokens` rather than the raw text. The substring
        version of this assertion failed on the module's own docstring, which
        says it *reads no environment variable* - the fifth time that pattern
        has fired on a document describing what it forbids, and the reason the
        helper now lives in ``conftest``.
        """
        source = (
            pathlib.Path(__file__).resolve().parent.parent / "benchmarks" / "artifacts.py"
        ).read_text(encoding="utf-8")
        tokens = code_tokens(ast.parse(source))
        for forbidden in ("os", "environ", "getenv"):
            assert forbidden not in tokens, forbidden


class TestTheDigestMustBePinnedBeforeAnyRun:
    def test_the_ledger_is_empty_so_every_role_refuses(self) -> None:
        """Pending by construction, not by configuration.

        An empty ledger is the whole mechanism: the policy "the digest is
        mandatory" is decided here, while *which* digest is correct is a fact
        only the owner can pin, because pinning it means asserting that a
        specific staged file is the right one.
        """
        assert PINNED_MODEL_DIGESTS == {}
        with pytest.raises(DigestNotPinned) as caught:
            require_pinned_digest("llm-model", A_DIGEST)
        assert "chua duoc ghim" in str(caught.value)

    def test_a_pinned_digest_that_matches_is_accepted(self) -> None:
        require_pinned_digest("llm-model", A_DIGEST, pinned={"llm-model": A_DIGEST})

    def test_a_pinned_digest_that_differs_refuses(self) -> None:
        with pytest.raises(DigestRefused) as caught:
            require_pinned_digest("llm-model", B_DIGEST, pinned={"llm-model": A_DIGEST})
        assert caught.value.code == "digest-mismatch"

    def test_not_pinned_and_mismatched_are_different_refusals(self) -> None:
        """Different problems, different fixes.

        "Nobody has said what this file should be" is answered by the owner
        pinning a value. "This file is not the one that was pinned" means the
        artifact changed, and the fix is to find out why. Collapsing them
        would send an operator to the wrong question.
        """
        assert issubclass(DigestNotPinned, DigestRefused)
        with pytest.raises(DigestNotPinned) as caught:
            require_pinned_digest("llm-model", A_DIGEST, pinned={})
        assert caught.value.code == "digest-not-pinned"

    def test_an_unknown_role_is_rejected_rather_than_pinned_by_accident(self) -> None:
        """Roles come from the closed set the refusal messages already use.

        A typo'd role would otherwise create a brand-new ledger key that
        nothing pins, and the run would refuse with a message naming a role
        that does not exist.
        """
        with pytest.raises(ValueError, match="unknown artifact role"):
            require_pinned_digest("llm-modle", A_DIGEST, pinned={"llm-modle": A_DIGEST})

    @pytest.mark.parametrize("bad", ["", "abc", "g" * 64, "A" * 63, "a" * 65])
    def test_a_value_that_is_not_a_sha256_is_refused(self, bad: str) -> None:
        """A digest that is not 64 lowercase hex characters is not a digest.

        This is what stops the old behaviour coming back in a new spelling: a
        placeholder such as ``"skipped"`` cannot be smuggled through as if it
        were a measurement.
        """
        with pytest.raises(DigestRefused) as caught:
            require_pinned_digest("llm-model", bad, pinned={"llm-model": A_DIGEST})
        assert caught.value.code == "digest-malformed"

    def test_the_word_skipped_cannot_pass_as_a_digest(self) -> None:
        """Named explicitly because it is the exact value the artifacts hold."""
        with pytest.raises(DigestRefused):
            require_pinned_digest("llm-model", "skipped", pinned={"llm-model": A_DIGEST})


class TestThePolicyIsEnforcedAcrossEveryHarness:
    """One applied instance is not a policy; this asks every harness.

    Written because the pattern this project keeps hitting is a control that
    is correct in the file it was added to and absent in the four siblings -
    the CPU gate guarded 1 of 5 model paths when it first landed.
    """

    ARTIFACT_WRITERS = (
        "bench_asr.py",
        "bench_coresidency.py",
        "bench_llamacpp.py",
        "bench_llm.py",
        "bench_llm_policy.py",
        "rescore_llm_policy.py",
    )

    @staticmethod
    def _benchmarks() -> dict[str, str]:
        root = pathlib.Path(__file__).resolve().parent.parent / "benchmarks"
        return {
            path.name: path.read_text(encoding="utf-8")
            for path in sorted(root.glob("*.py"))
        }

    @staticmethod
    def _hand_built_output_paths(source: str) -> list[str]:
        """Assignments to an output name built from a literal path.

        Targeted at *writes*, not at every mention of the root. ``var/`` also
        holds **inputs** - the staged ``whisper-cli.exe`` and the model files
        live there - and a constant naming one of those is correct code. The
        first version of this test asserted on every string starting with
        ``var/`` and failed on fifteen legitimate input constants, which is
        the difference between "where artifacts are written" and "any mention
        of a directory".
        """
        offenders = []
        for node in ast.walk(ast.parse(source)):
            if not isinstance(node, ast.Assign):
                continue
            names = [t.id for t in node.targets if isinstance(t, ast.Name)]
            if not any(
                part in name for name in names for part in ("out", "target", "dest")
            ):
                continue
            for inner in ast.walk(node.value):
                if (
                    isinstance(inner, ast.Call)
                    and isinstance(inner.func, ast.Attribute)
                    and inner.func.attr == "Path"
                    and inner.args
                    and isinstance(inner.args[0], ast.Constant)
                ):
                    offenders.append(f"{names} = Path({inner.args[0].value!r})")
        return offenders

    def test_no_harness_builds_an_output_path_from_a_literal(self) -> None:
        """``out_dir = pathlib.Path("var/bench")`` is how the old shape returns."""
        offenders = {
            name: found
            for name, source in self._benchmarks().items()
            if name != "artifacts.py" and (found := self._hand_built_output_paths(source))
        }
        assert offenders == {}

    def test_every_artifact_writer_goes_through_the_helper(self) -> None:
        """Each model harness's final JSON sink must descend from the helper.

        A token-presence check was too weak: importing ``artifact_path`` and
        then writing to an unrelated ``Path`` passed. Track simple local path
        assignments inside each top-level function and inspect the actual
        ``write_text`` sink.
        Temporary prompts and generated inputs are different write classes;
        they are deliberately not described by this result-artifact invariant.
        """
        sources = self._benchmarks()
        for name in self.ARTIFACT_WRITERS:
            sinks = self._json_artifact_sinks(sources[name])
            assert sinks == [True], (
                f"{name}: expected one helper-rooted JSON sink, got {sinks}"
            )

    @staticmethod
    def _json_artifact_sinks(source: str) -> list[bool]:
        """Return whether each JSON ``write_text`` receiver is helper-rooted."""
        tree = ast.parse(source)
        helper_names: set[str] = set()
        for node in tree.body:
            if isinstance(node, ast.ImportFrom) and node.module == "benchmarks.artifacts":
                helper_names.update(
                    alias.asname or alias.name
                    for alias in node.names
                    if alias.name == "artifact_path"
                )

        def assigned_names(targets: list[ast.expr]) -> set[str]:
            return {
                node.id
                for target in targets
                for node in ast.walk(target)
                if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store)
            }

        def is_helper_call(expr: ast.expr) -> bool:
            return (
                isinstance(expr, ast.Call)
                and isinstance(expr.func, ast.Name)
                and expr.func.id in helper_names
            )

        def is_safe_path(expr: ast.expr, safe_names: set[str]) -> bool:
            if is_helper_call(expr):
                return True
            if isinstance(expr, ast.Name):
                return expr.id in safe_names
            if isinstance(expr, ast.BinOp) and isinstance(expr.op, ast.Div):
                return is_safe_path(expr.left, safe_names)
            if isinstance(expr, ast.Attribute) and expr.attr == "parent":
                return is_safe_path(expr.value, safe_names)
            if (
                isinstance(expr, ast.Call)
                and isinstance(expr.func, ast.Attribute)
                and expr.func.attr == "joinpath"
            ):
                return is_safe_path(expr.func.value, safe_names)
            return False

        def names_for_function(
            function: ast.FunctionDef | ast.AsyncFunctionDef,
        ) -> set[str]:
            safe_names: set[str] = set()
            # Follow only straight-line assignments in source order. Treating
            # all assignments as an unordered fixed point would let a later
            # safe reassignment bless an earlier unsafe path.
            for statement in function.body:
                if isinstance(statement, ast.Assign) and is_safe_path(
                    statement.value, safe_names
                ):
                    safe_names.update(assigned_names(statement.targets))
            return safe_names

        functions = [
            node
            for node in tree.body
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        ]
        sinks: list[bool] = []
        for function in functions:
            safe_names = names_for_function(function)

            for candidate in ast.walk(function):
                if not isinstance(candidate, ast.Call) or not isinstance(
                    candidate.func, ast.Attribute
                ):
                    continue
                if candidate.func.attr != "write_text" or not candidate.args:
                    continue
                payload = candidate.args[0]
                if not (
                    isinstance(payload, ast.Call)
                    and isinstance(payload.func, ast.Attribute)
                    and payload.func.attr == "dumps"
                    and isinstance(payload.func.value, ast.Name)
                    and payload.func.value.id == "json"
                ):
                    continue
                sinks.append(is_safe_path(candidate.func.value, safe_names))
        return sinks

    def test_sink_control_rejects_dead_helper_import_and_accepts_alias_flow(self) -> None:
        safe = (
            "from benchmarks.artifacts import artifact_path as output_root\n"
            "def main():\n"
            "    root = output_root('bench')\n"
            "    target = root / 'result.json'\n"
            "    target.write_text(json.dumps({}))\n"
        )
        unsafe = (
            "from benchmarks.artifacts import artifact_path\n"
            "from pathlib import Path\n"
            "def main():\n"
            "    target = Path('var/bench/result.json')\n"
            "    target.write_text(json.dumps({}))\n"
        )
        unbound_helper = (
            "def main():\n"
            "    target = artifact_path('bench') / 'result.json'\n"
            "    target.write_text(json.dumps({}))\n"
        )
        reassigned_after_use = (
            "from benchmarks.artifacts import artifact_path\n"
            "from pathlib import Path\n"
            "def main():\n"
            "    root = Path('C:/outside')\n"
            "    target = root / 'result.json'\n"
            "    root = artifact_path('bench')\n"
            "    target.write_text(json.dumps({}))\n"
        )
        temporary_text = (
            "from pathlib import Path\n"
            "def main():\n"
            "    prompt = Path('var/bench/prompt.txt')\n"
            "    prompt.write_text('synthetic prompt')\n"
        )
        assert self._json_artifact_sinks(safe) == [True]
        assert self._json_artifact_sinks(unsafe) == [False]
        assert self._json_artifact_sinks(unbound_helper) == [False]
        assert self._json_artifact_sinks(reassigned_after_use) == [False]
        assert self._json_artifact_sinks(temporary_text) == []

    def test_replacing_each_harness_helper_with_a_direct_path_is_detected(self) -> None:
        sources = self._benchmarks()
        for name in self.ARTIFACT_WRITERS:
            source = sources[name]
            assert "artifact_path(" in source, name
            mutated = source.replace("artifact_path(", "pathlib.Path(", 1)
            assert self._json_artifact_sinks(mutated) == [False], name

    def test_the_scan_would_catch_a_hand_built_path(self) -> None:
        """Control: the scan above passes for free if it matches nothing."""
        found = self._hand_built_output_paths('out_dir = pathlib.Path("var/bench")\n')
        assert found == ["['out_dir'] = Path('var/bench')"]

    def test_no_harness_still_offers_a_digest_override(self) -> None:
        """S2.1 decision #1 removed ``--no-hash``; this keeps it removed."""
        for name, source in self._benchmarks().items():
            tokens = code_tokens(ast.parse(source))
            assert "--no-hash" not in tokens, name
            assert "no_hash" not in tokens, name

    def test_no_harness_can_write_skipped_where_a_digest_belongs(self) -> None:
        """The literal two recorded artifacts contain, kept out by structure."""
        for name, source in self._benchmarks().items():
            tree = ast.parse(source)
            for node in ast.walk(tree):
                if not isinstance(node, ast.Dict):
                    continue
                for key, value in zip(node.keys, node.values, strict=True):
                    # `key` is None for `{**spread}`, which has no lineno.
                    if not isinstance(key, ast.Constant) or key.value != "sha256":
                        continue
                    if isinstance(value, ast.Constant):
                        pytest.fail(
                            f"{name}: a literal digest value at line {key.lineno}"
                        )

    #: Literal-rooted names that are read, never written. A staged binary is
    #: an input, and routing an input through the output helper would be
    #: wrong, not stricter.
    WRITING_METHODS = ("mkdir", "write_text", "write_bytes", "touch")

    @classmethod
    def _literal_paths(cls, source: str) -> dict[str, str]:
        """Names assigned from ``pathlib.Path(<string literal>)``."""
        literals: dict[str, str] = {}
        for node in ast.walk(ast.parse(source)):
            if not isinstance(node, ast.Assign):
                continue
            value = node.value
            if (
                isinstance(value, ast.Call)
                and isinstance(value.func, ast.Attribute)
                and value.func.attr == "Path"
                and value.args
                and isinstance(value.args[0], ast.Constant)
                and isinstance(value.args[0].value, str)
            ):
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        literals[target.id] = value.args[0].value
        return literals

    @classmethod
    def _written_names(cls, source: str) -> set[str]:
        """Names a writing method is called on."""
        return {
            node.func.value.id
            for node in ast.walk(ast.parse(source))
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr in cls.WRITING_METHODS
            and isinstance(node.func.value, ast.Name)
        }

    def test_no_output_path_is_built_from_a_literal(self) -> None:
        """Outputs go through the helper; inputs are left alone.

        The earlier version of this check asked whether the *variable name*
        contained "out", "target" or "dest". That heuristic missed
        ``CLIP_ROOT`` and ``MANIFEST`` purely because of what they are called,
        which is how two literal output paths sat beside a sibling generator
        that already used the helper.

        Asking what the code *does* with the name separates them properly: a
        path a writing method is called on is an output, and the staged binary
        constants - ``WHISPER``, ``LLAMA``, ``BUILD_DIR`` - are inputs that
        must **not** be routed through an output helper, because that would be
        wrong rather than stricter.
        """
        offenders: dict[str, list[str]] = {}
        for name, source in self._benchmarks().items():
            if name == "artifacts.py":
                continue  # defines the root; it is the helper, not a caller
            literals = self._literal_paths(source)
            written = self._written_names(source)
            found = [
                f"{variable} = Path({literals[variable]!r})"
                for variable in sorted(literals)
                if variable in written
            ]
            if found:
                offenders[name] = found
        assert offenders == {}, (
            f"an output path is built from a literal instead of artifact_path(): "
            f"{offenders}. S2.1 decision #2 fixes the artifact root; a sibling "
            "generator already routes its manifest through the helper."
        )

    def test_input_constants_are_deliberately_left_alone(self) -> None:
        """The other direction, so the check cannot be 'flag every literal'.

        Without this, widening the rule until nothing is missed would also
        drag the staged binary paths in, and the suite would not object.
        """
        inputs = {"WHISPER", "LLAMA", "BUILD_DIR"}
        seen: set[str] = set()
        for name, source in self._benchmarks().items():
            literals = self._literal_paths(source)
            written = self._written_names(source)
            for variable in literals:
                if variable in inputs:
                    seen.add(variable)
                    assert variable not in written, (
                        f"{name}: {variable} is a staged input and must not be written to"
                    )
        assert seen == inputs, f"expected the input constants to exist, saw {seen}"
