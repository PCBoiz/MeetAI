"""A media sink cannot be added without a permit the gate minted.

**What this file replaces.** "No media sink exists" was enforced by a regex
scanning `src/meetai/*.py` for `def emit` and `class *sink`, plus the accident
that `discord`, `av`, `pyaudio` and `torch` are not installed. Both are weak,
and the second is not a control at all. Measured gaps in the regex:
`async def on_audio(...)` does not match; `def emit_audio(...)` does not match
because `_` is a word character and the pattern anchors on `emit\\b`;
`class AudioSinkFactory` does not match because `sink` is not at a word
boundary; and `boundary.py` was excluded outright.

**What replaces it, in order of strength.**

1. A **third-party import allowlist** for the whole package. The forbidden-list
   it replaces named twelve network modules and no media ones at all - so
   `import discord` in a new `src/meetai/voice.py` passed the entire suite.
   Measured: the package imports exactly six external roots today, so the
   allowlist is tight rather than aspirational.
2. **One frame-delivery expression.** `BoundedBuffer.push` is called from
   exactly one place in `src/`, and that place runs the gate first. "There is
   one expression in this project that hands a frame to anything" is checkable
   and decision-free.
3. **No import-time construction.** A module-level `SINK = DiscordSink()` runs
   before any caller can intervene, and nothing prevented it.
4. **A permit whose validity is object identity**, mintable only by a gate that
   re-reads the policy at grant time.

**What this does not claim.** None of it is a security boundary. Any code in
this process can reach into `media_gate` and add to the issued set, and no test
can stop that - the same honest limit already recorded on `MediaGate._closed`.
The threat these answer is the next careless commit in this repository. And no
media sink exists, no listener exists, and consent is `pending_decision`, so
media is refused in code regardless of any of this.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

import pytest

from meetai.consent import ConsentLedger
from meetai.media_gate import (
    GateRejection,
    MediaGate,
    MediaSinkPermit,
    SinkPermitDecision,
)
from meetai.settings import Settings
from tests.test_consent import NOTICE, SESSION, Clock

SRC = Path(__file__).resolve().parent.parent / "src" / "meetai"

PERMITTED_THIRD_PARTY = frozenset(
    {"dotenv", "fastapi", "pydantic", "pydantic_settings", "starlette", "uvicorn"}
)
"""Every external root `src/meetai` may import. Measured, not aspirational.

An allowlist rather than a denylist, for the reason this project already
applies to log fields: a denylist loses to the first new name. The forbidden
list this replaces contained twelve network modules and **no** media ones, so
`import discord`, `import av`, `import pyaudio`, `import torch` or
`import faster_whisper` in a new module passed every test in the suite.
"""

PERMITTED_MODULE_LEVEL_CALLS = frozenset(
    {
        # Pure builders, evaluated once at import. Nothing here can open a
        # device, a socket or a file.
        "compile",
        "frozenset",
        "chr",
        "join",
        "escape",
        "get",
        "ContextVar",
        "LogRecord",
        "Path",
        # The dry-run's own synthetic fixtures, which are plain dataclasses.
        "CardFixture",
        "DryRunCase",
        "ClaimFixture",
        # cli.py's `if __name__ == "__main__"` guard.
        "SystemExit",
        "main",
    }
)
"""Callees allowed to run at import time anywhere in `src/meetai`.

A module-level `SINK = DiscordSink()` runs before any caller can intervene,
and nothing in the suite prevented it. This is the narrow list of what the
package actually does at import today; a new entry is exactly the moment a
human should look.
"""


def third_party_roots() -> dict[str, set[str]]:
    """External import roots, per file."""
    stdlib = set(sys.stdlib_module_names)
    found: dict[str, set[str]] = {}
    for path in sorted(SRC.rglob("*.py")):
        roots: set[str] = set()
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Import):
                roots.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                roots.add(node.module.split(".")[0])
        external = {r for r in roots if r not in stdlib and r != "meetai"}
        if external:
            found[str(path.relative_to(SRC))] = external
    return found


def module_level_calls() -> list[tuple[str, int, str]]:
    """Calls evaluated at import time, with their callee name."""
    out: list[tuple[str, int, str]] = []
    for path in sorted(SRC.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for statement in tree.body:
            if isinstance(
                statement, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef
            ):
                continue
            for node in ast.walk(statement):
                if not isinstance(node, ast.Call):
                    continue
                func = node.func
                name = (
                    func.id if isinstance(func, ast.Name) else getattr(func, "attr", "?")
                )
                out.append((str(path.relative_to(SRC)), node.lineno, name))
    return out


def make_gate(**overrides: object) -> MediaGate:
    defaults: dict[str, object] = {
        "ledger": ConsentLedger(session_id=SESSION, policy_version="p1", now=Clock()),
        "notice_version": NOTICE,
        "policy_allows_media": lambda: True,
        "session_is_active": lambda: True,
    }
    defaults.update(overrides)
    return MediaGate(**defaults)  # type: ignore[arg-type]


class TestNoModuleMayImportAMediaLibrary:
    def test_the_package_imports_only_the_allowlisted_roots(self) -> None:
        offenders = {
            name: sorted(roots - PERMITTED_THIRD_PARTY)
            for name, roots in third_party_roots().items()
            if roots - PERMITTED_THIRD_PARTY
        }
        assert not offenders, (
            f"new external imports in src/meetai: {offenders}. An allowlist, "
            "not a denylist: adding a dependency here is a decision with a "
            "license and provenance note, and a media or Discord library is a "
            "gate-0 question before it is a dependency question."
        )

    @pytest.mark.parametrize(
        "library",
        [
            "discord",
            "nextcord",
            "disnake",
            "av",
            "pyaudio",
            "sounddevice",
            "soundfile",
            "webrtcvad",
            "torch",
            "llama_cpp",
            "faster_whisper",
            "whisper",
            "numpy",
            "transformers",
        ],
    )
    def test_each_named_media_library_is_absent(self, library: str) -> None:
        """Named explicitly as well, because a reader looking for "is discord
        forbidden" should find the word, not infer it from a set difference."""
        assert library not in PERMITTED_THIRD_PARTY
        for name, roots in third_party_roots().items():
            assert library not in roots, f"{name} imports {library}"

    def test_the_allowlist_is_tight(self) -> None:
        """Every permitted root is actually used, so the list cannot quietly
        accumulate permissions nobody needs."""
        used: set[str] = set()
        for roots in third_party_roots().values():
            used |= roots
        unused = PERMITTED_THIRD_PARTY - used
        assert not unused, f"allowlisted but unused: {sorted(unused)}"


class TestNothingIsConstructedAtImportTime:
    def test_every_import_time_call_is_allowlisted(self) -> None:
        offenders = [
            f"{name}:{line} {callee}()"
            for name, line, callee in module_level_calls()
            if callee not in PERMITTED_MODULE_LEVEL_CALLS
        ]
        assert not offenders, (
            f"new import-time calls: {offenders}. A module-level "
            "`SINK = DiscordSink()` runs before any caller can intervene, so "
            "the set of things this package does at import is kept small and "
            "explicit."
        )

    def test_importing_the_package_constructs_no_gate_and_no_session(self) -> None:
        """Behavioural companion: importing must not build the machinery."""
        calls = {callee for _, _, callee in module_level_calls()}
        for forbidden in ("MediaGate", "Session", "ConsentLedger", "KnowledgeStore"):
            assert forbidden not in calls, forbidden


class TestThereIsOneFrameDeliveryExpression:
    @staticmethod
    def _push_sites() -> list[str]:
        sites: list[str] = []
        for path in sorted(SRC.rglob("*.py")):
            for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
                if (
                    isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Attribute)
                    and node.func.attr == "push"
                ):
                    sites.append(f"{path.relative_to(SRC)}:{node.lineno}")
        return sites

    def test_a_frame_reaches_storage_from_exactly_one_place(self) -> None:
        """The real invariant, replacing a name regex.

        "One expression hands a frame to anything" is checkable without being
        brittle, and it is the property the regex was gesturing at.
        """
        sites = self._push_sites()
        assert sites == ["session.py:368"], sites

    def test_that_one_place_runs_the_gate_first(self) -> None:
        source = (SRC / "session.py").read_text(encoding="utf-8")
        tree = ast.parse(source)
        accept = next(
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.FunctionDef) and node.name == "accept_frame"
        )
        evaluate_line = next(
            node.lineno
            for node in ast.walk(accept)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "evaluate"
        )
        push_line = next(
            node.lineno
            for node in ast.walk(accept)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "push"
        )
        assert evaluate_line < push_line, (evaluate_line, push_line)

    def test_no_sink_shaped_method_exists_outside_the_boundary(self) -> None:
        """The widened smoke test, kept as a smoke test.

        Labelled so nobody mistakes it for the guarantee again: the guarantee
        is the import allowlist plus the single delivery expression. This
        catches the obvious spelling and now also `emit_audio`, `on_audio`,
        `on_voice` and a sink-shaped class name anywhere in the name.
        """
        suspicious = ("emit", "on_audio", "on_voice", "receive_audio", "feed_audio")
        # Each entry is a decision someone made, which is the point of an
        # allowlist: adding one is visible in review. `emitted_count` reads a
        # length; the four types are an exception class, its subclass, and the
        # permit pair - none of them touches a frame.
        known_good = {
            "emitted_count",
            "SinkError",
            "SinkRefusedBeforeEmitError",
            "MediaSinkPermit",
            "SinkPermitDecision",
        }
        offenders: list[str] = []
        for path in sorted(SRC.rglob("*.py")):
            if path.name == "boundary.py":
                continue
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
                    if node.name in known_good:
                        continue
                    if any(node.name.startswith(p) for p in suspicious):
                        offenders.append(f"{path.name}:{node.lineno} def {node.name}")
                if isinstance(node, ast.ClassDef) and "sink" in node.name.lower():
                    if node.name in known_good:
                        continue
                    offenders.append(f"{path.name}:{node.lineno} class {node.name}")
        assert not offenders, offenders


class TestAPermitIsUnobtainableWhileConsentIsPending:
    def test_the_projects_real_default_configuration_refuses(self) -> None:
        """No fake, and no test changes configuration to go green."""
        settings = Settings()
        gate = make_gate(policy_allows_media=lambda: settings.media_processing_allowed)
        decision = gate.issue_sink_permit()
        assert decision.permit is None
        assert decision.rejection is GateRejection.POLICY_PENDING
        assert not decision

    def test_a_closed_gate_mints_nothing(self) -> None:
        gate = make_gate()
        gate.close()
        decision = gate.issue_sink_permit()
        assert decision.permit is None
        assert decision.rejection is GateRejection.GATE_CLOSED

    def test_an_inactive_session_mints_nothing(self) -> None:
        gate = make_gate(session_is_active=lambda: False)
        assert gate.issue_sink_permit().rejection is GateRejection.SESSION_NOT_ACTIVE

    @pytest.mark.parametrize("value", ["pending", "false", 1, object()])
    def test_a_non_bool_yes_mints_nothing(self, value: object) -> None:
        """The same fail-open shape the per-frame path already refuses."""
        gate = make_gate(policy_allows_media=lambda: value)
        assert gate.issue_sink_permit().rejection is GateRejection.POLICY_PENDING

    def test_a_raising_policy_source_mints_nothing(self) -> None:
        def boom() -> bool:
            raise RuntimeError("policy source down")

        gate = make_gate(policy_allows_media=boom)
        assert gate.issue_sink_permit().rejection is GateRejection.POLICY_PENDING

    def test_a_permit_cannot_be_minted_at_import_time(self) -> None:
        """Minting needs a live gate, which needs a ledger and a callable, so
        there is nothing a module body could do."""
        calls = {callee for _, _, callee in module_level_calls()}
        assert "issue_sink_permit" not in calls
        assert "MediaGate" not in calls


class TestAPermitCannotBeForged:
    def test_a_minted_permit_validates(self) -> None:
        gate = make_gate()
        permit = gate.issue_sink_permit().permit
        assert permit is not None
        assert gate.permit_is_valid(permit)

    def test_direct_construction_is_refused(self) -> None:
        with pytest.raises(TypeError):
            MediaSinkPermit()

    def test_subclassing_is_refused(self) -> None:
        with pytest.raises(TypeError):
            type("Forged", (MediaSinkPermit,), {})

    def test_a_new_forgery_is_the_right_type_and_still_invalid(self) -> None:
        """The measurement that chose identity over ``isinstance``.

        ``object.__setattr__`` defeats ``frozen=True`` and ``slots=True``
        alike, so no per-instance invariant survives. Identity against the
        gate's own set does.
        """
        gate = make_gate()
        forged = MediaSinkPermit.__new__(MediaSinkPermit)
        assert isinstance(forged, MediaSinkPermit)
        assert not gate.permit_is_valid(forged)

    @pytest.mark.parametrize("impostor", [None, 3, "permit", object(), [], {}])
    def test_nothing_else_validates(self, impostor: object) -> None:
        assert not make_gate().permit_is_valid(impostor)

    def test_another_gates_permit_does_not_validate(self) -> None:
        """A permit is a gate's own, so one session cannot lend to another."""
        first, second = make_gate(), make_gate()
        permit = first.issue_sink_permit().permit
        assert permit is not None
        assert first.permit_is_valid(permit)
        assert not second.permit_is_valid(permit)

    def test_a_permit_dies_with_the_gate(self) -> None:
        gate = make_gate()
        permit = gate.issue_sink_permit().permit
        assert permit is not None
        assert gate.permit_is_valid(permit)
        gate.close()
        assert not gate.permit_is_valid(permit)

    def test_the_check_is_identity_not_isinstance(self) -> None:
        """Structural, because `isinstance` is the attractive simplification
        and it would accept every forgery above."""
        source = (SRC / "media_gate.py").read_text(encoding="utf-8")
        tree = ast.parse(source)
        checker = next(
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.FunctionDef) and node.name == "permit_is_valid"
        )
        # Asked of the NODES, not of `ast.dump`: the first version searched
        # the dump text, which includes the docstring - and the docstring
        # explains why `isinstance` is wrong, so the test failed on its own
        # explanation. Third time this project has hit that trap.
        comparisons = [
            node for node in ast.walk(checker) if isinstance(node, ast.Compare)
        ]
        assert comparisons, "there is no comparison at all"
        assert any(isinstance(op, ast.Is) for node in comparisons for op in node.ops), (
            "the comparison must be `is`"
        )
        called = {
            node.func.id
            for node in ast.walk(checker)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
        }
        assert "isinstance" not in called, called


class TestTheDecisionTypeCannotBeMisread:
    def test_a_refusal_carries_no_permit(self) -> None:
        with pytest.raises(ValueError):
            SinkPermitDecision(permit=None)

    def test_a_grant_cannot_also_carry_a_rejection(self) -> None:
        gate = make_gate()
        permit = gate.issue_sink_permit().permit
        with pytest.raises(ValueError):
            SinkPermitDecision(permit=permit, rejection=GateRejection.POLICY_PENDING)

    def test_a_refusal_is_falsy_and_a_grant_is_truthy(self) -> None:
        assert not SinkPermitDecision(permit=None, rejection=GateRejection.GATE_CLOSED)
        gate = make_gate()
        assert gate.issue_sink_permit()

    def test_no_new_gate_rejection_member_was_added(self) -> None:
        """Registration reuses the existing reasons, so the pinned adjacent
        order of the per-frame checks is untouched."""
        assert {member.name for member in GateRejection} == {
            "POLICY_PENDING",
            "SESSION_NOT_ACTIVE",
            "SPEAKER_UNMAPPED",
            "NO_CONSENT",
            "STALE_GENERATION",
            "GATE_CLOSED",
        }


class TestTheTextSinkIsDeliberatelyNotUnderThisBoundary:
    """`boundary.OutputSink` stays permit-free, and the reason is measured.

    A text sink that speaks into a meeting *is* a media path in the egress
    direction - `boundary.py` says so itself. But `RecordingSink` is used by
    the dry-run and by many tests, and requiring a permit at `deliver` time
    would make every one of those construct a ledger, a gate and a policy
    callable **returning True** - i.e. the suite would have to switch the media
    policy on in order to run. That inverts the claim
    `test_safety_gates.py` is built to make, and it would put
    `policy_allows_media=lambda: True` into dozens of places where it can be
    copied into something real.

    So the permit attaches to *reaching a meeting*, not to *being a sink*, and
    no sink that reaches a meeting exists. Recorded here rather than left to be
    rediscovered.
    """

    def test_deliver_requires_no_permit(self) -> None:
        import inspect

        from meetai.boundary import deliver

        params = inspect.signature(deliver).parameters
        assert "permit" not in params

    def test_and_no_sink_that_reaches_a_meeting_exists(self) -> None:
        """Which is what makes the paragraph above safe."""
        roots: set[str] = set()
        for found in third_party_roots().values():
            roots |= found
        assert not roots & {"discord", "av", "pyaudio", "sounddevice"}
