"""The sink-failure contract: what MeetAI may say when a sink breaks.

One rule shapes every test here: **MeetAI reports "sent" only on evidence, and
absence of evidence is reported as absence - never as "sent" and never as "not
sent".**

Before this file the suite contained **no failing sink at all**; every test
used ``RecordingSink``, which cannot fail. So nothing would have caught a
regression, and nothing broke behaviourally when the contract landed - the only
breakage was structural, in a guard of mine that pinned a spelling.

The three fakes live here rather than in ``src/``, and that is forced: a test
asserts that no file in ``src/meetai`` other than ``boundary.py`` contains
``def emit`` or a sink-shaped class name.
"""

from __future__ import annotations

import ast
import json
from dataclasses import dataclass, field, fields
from pathlib import Path

import pytest

from meetai.boundary import (
    DeliveryOutcome,
    RecordingSink,
    Stage,
    deliver,
    deliver_all,
)
from meetai.errors import SinkError, SinkRefusedBeforeEmitError
from tests.test_boundary import request

CANARY = "ZZSINKCANARYZZ"
SRC = Path(__file__).resolve().parent.parent / "src" / "meetai"


@dataclass(slots=True)
class RefusingSink:
    """Fails **before** any side effect, and says so. Models state (a).

    The refusal is the first statement, which is the whole obligation the
    contract puts on a sink: do your refusing before touching the device.
    """

    attempts: int = 0

    def emit(self, text: str) -> None:
        self.attempts += 1
        raise SinkRefusedBeforeEmitError("sink tu choi truoc khi phat")


@dataclass(slots=True)
class CommittingThenFailingSink:
    """Fails **after** a side effect. Models state (b), the unknown.

    It counts rather than records. Deliberately: a fake that stored the text
    would itself be the content leak the canary test is looking for, and the
    tests must be able to tell the two fakes apart **without reading any
    content**. ``committed`` is the side effect, abstracted to an integer.
    """

    committed: int = 0

    def emit(self, text: str) -> None:
        self.committed += 1
        raise RuntimeError("sink that bai sau khi da phat mot phan")


@dataclass(slots=True)
class CanarySink:
    """A badly written sink that embeds the utterance in its own exception.

    The one place in this project allowed to construct such a message, and
    only because it is simulating a third party. ``tests/test_no_value_in_
    errors.py`` enforces value-free messages for ``src/meetai`` raise sites;
    nothing can enforce it on a sink somebody else wrote, so the contract has
    to survive one that gets it wrong.
    """

    def emit(self, text: str) -> None:
        raise RuntimeError(f"TTS failed while speaking: {text} [{CANARY}]")


@dataclass(slots=True)
class LyingSink:
    """Commits, then claims it did not. Pins the documented limit.

    MeetAI believes the exception type, because the type is the only channel a
    sink has for the assertion and nothing at the call site can verify it. The
    test asserts the wrong answer on purpose, so that the trust is visible in
    the suite rather than implied in a docstring.
    """

    committed: int = 0

    def emit(self, text: str) -> None:
        self.committed += 1
        raise SinkRefusedBeforeEmitError("khong phat gi ca (noi doi)")


@dataclass(slots=True)
class CountingSink:
    """Succeeds, and counts. For the batch tests."""

    calls: int = 0
    emitted: list[str] = field(default_factory=list, repr=False)

    def emit(self, text: str) -> None:
        self.calls += 1
        self.emitted.append(text)


class TestTheTwoStatesAreDistinguished:
    def test_a_sink_that_refuses_first_reports_sink_refused(self) -> None:
        sink = RefusingSink()
        outcome = deliver(request(), sink=sink)
        assert sink.attempts == 1
        assert outcome.stage is Stage.SINK_REFUSED
        assert not outcome.delivered
        assert outcome.emitted_chars == 0
        assert outcome.error_type == "SinkRefusedBeforeEmitError"

    def test_any_other_failure_reports_unknown(self) -> None:
        sink = CommittingThenFailingSink()
        outcome = deliver(request(), sink=sink)
        assert sink.committed == 1
        assert outcome.stage is Stage.SINK_UNKNOWN
        assert not outcome.delivered
        assert outcome.emitted_chars is None, "0 would be a claim, None is not"
        assert outcome.error_type == "RuntimeError"

    def test_the_two_are_told_apart_without_reading_content(self) -> None:
        """A test that had to inspect the text to classify the failure would
        be a test that could not run against a real sink."""
        refused = deliver(request(), sink=RefusingSink())
        unknown = deliver(request(), sink=CommittingThenFailingSink())
        assert refused.stage is not unknown.stage
        assert refused.emitted_chars != unknown.emitted_chars

    def test_unknown_is_the_default_not_the_opt_in(self) -> None:
        """A contract that assumed "nothing emitted" unless told otherwise
        would fail open on every sink nobody updated."""

        @dataclass(slots=True)
        class NaiveSink:
            def emit(self, text: str) -> None:
                raise ValueError("something broke")

        assert deliver(request(), sink=NaiveSink()).stage is Stage.SINK_UNKNOWN

    @pytest.mark.parametrize(
        "exc", [KeyboardInterrupt, SystemExit, MemoryError, BaseException]
    )
    def test_even_a_base_exception_leaves_a_record(
        self, exc: type[BaseException]
    ) -> None:
        """A cancellation mid-emit leaves exactly the same question open - was
        it heard? - so narrowing to ``Exception`` would let the two cases that
        matter most escape with no record at all."""

        @dataclass(slots=True)
        class Exploding:
            def emit(self, text: str) -> None:
                raise exc()

        outcome = deliver(request(), sink=Exploding())
        assert outcome.stage is Stage.SINK_UNKNOWN
        assert outcome.error_type == exc.__name__

    def test_the_lying_sink_is_believed_and_that_is_recorded(self) -> None:
        """The documented limit: (a) is the sink's assertion, never MeetAI's
        evidence. A sink that lies is treated as (a)."""
        sink = LyingSink()
        outcome = deliver(request(), sink=sink)
        assert sink.committed == 1, "it really did commit"
        assert outcome.stage is Stage.SINK_REFUSED, (
            "MeetAI trusts the exception type because nothing at the call site "
            "can verify it; this assertion makes the trust visible"
        )


class TestMeetAiNeverClaimsSentWithoutEvidence:
    @pytest.mark.parametrize(
        "sink_factory",
        [RefusingSink, CommittingThenFailingSink, CanarySink, LyingSink],
        ids=lambda f: f.__name__,
    )
    def test_no_failing_sink_produces_a_sent_claim(self, sink_factory: type) -> None:
        outcome = deliver(request(), sink=sink_factory())
        assert outcome.delivered is False
        assert bool(outcome) is False
        assert not outcome.may_claim_sent
        assert not (isinstance(outcome.emitted_chars, int) and outcome.emitted_chars > 0)

    def test_exactly_one_stage_permits_claiming_sent(self) -> None:
        """Exhaustive over ``Stage``, so a member added later has to decide
        rather than inherit an answer from a set someone extended."""
        permitting = [stage for stage in Stage if stage.permits_claiming_sent]
        assert permitting == [Stage.DELIVERED], permitting

    def test_only_delivered_can_construct_a_delivered_outcome(self) -> None:
        for stage in Stage:
            if stage is Stage.DELIVERED:
                assert DeliveryOutcome(
                    delivered=True, stage=stage, emitted_chars=5
                ).may_claim_sent
                continue
            with pytest.raises(ValueError):
                DeliveryOutcome(delivered=True, stage=stage, emitted_chars=5)

    def test_every_stage_is_classified(self) -> None:
        """A total map, not a set membership test. ``is_refusal`` used to be
        ``self in {...}``, so a new member answered ``False`` to every question
        without anyone choosing that."""
        for stage in Stage:
            assert isinstance(stage.is_refusal, bool)
            assert isinstance(stage.is_sink_failure, bool)
            assert isinstance(stage.permits_claiming_sent, bool)

    def test_a_sink_failure_is_not_a_gate_refusal(self) -> None:
        """A caller counting refusals must not be sent to revise a sentence
        that both gates approved."""
        for stage in (Stage.SINK_REFUSED, Stage.SINK_UNKNOWN):
            assert stage.is_sink_failure
            assert not stage.is_refusal
        for stage in (Stage.ANSWERABILITY, Stage.AUTHORITY):
            assert stage.is_refusal
            assert not stage.is_sink_failure

    def test_the_unknown_state_forbids_retry_and_the_others_do_not(self) -> None:
        assert deliver(request(), sink=CommittingThenFailingSink()).must_not_retry
        assert not deliver(request(), sink=RefusingSink()).must_not_retry
        assert not deliver(request(), sink=RecordingSink()).must_not_retry

    def test_the_boundary_itself_never_retries(self) -> None:
        """No state retries. The boundary reports; the caller decides; and a
        caller that retries has to own idempotency the sink does not have."""
        for factory in (RefusingSink, CommittingThenFailingSink):
            sink = factory()
            deliver(request(), sink=sink)
            attempts = getattr(sink, "attempts", None) or getattr(sink, "committed", 0)
            assert attempts == 1, attempts


class TestNoContentEscapesOnTheFailurePath:
    """The sink embeds the utterance in its own exception message. Nothing
    MeetAI produces may carry it onward."""

    def test_the_outcome_carries_no_content(self) -> None:
        """The canary comes from the SINK's exception message, not from the
        answer.

        A first version appended it to the answer instead, and the answer then
        carried a token no claim accounted for - so answerability refused it as
        malformed and the sink never ran. The test proved nothing, and the
        reason it proved nothing is the orphan-value check doing its job.
        """
        built = request()
        outcome = deliver(built, sink=CanarySink())
        assert outcome.stage is Stage.SINK_UNKNOWN, outcome
        rendered = f"{outcome!r} {outcome.metadata()} {json.dumps(outcome.metadata())}"
        assert CANARY not in rendered, rendered
        # And the utterance itself, which the sink put in its message verbatim.
        assert built.proposal.text is not None
        for word in built.proposal.text.unsafe_text().split():
            if len(word) > 5:
                assert word not in rendered, word
        assert outcome.error_type == "RuntimeError"

    def test_the_outcome_holds_a_class_name_not_an_exception(self) -> None:
        """An exception object reaches its own traceback, which reaches the
        frame that was executing, whose locals hold the utterance. A field
        holding the exception would pass this repo's field-name tests and be a
        complete leak by reference."""
        outcome = deliver(request(), sink=CanarySink())
        assert isinstance(outcome.error_type, str)
        for value in vars(outcome).values() if hasattr(outcome, "__dict__") else []:
            assert not isinstance(value, BaseException), value

    def test_no_outcome_field_can_hold_an_exception(self) -> None:
        annotations = {f.name: str(f.type) for f in fields(DeliveryOutcome)}
        for name, annotation in annotations.items():
            assert "Exception" not in annotation, (name, annotation)
            assert "BaseException" not in annotation, (name, annotation)

    def test_the_outcome_type_still_has_no_content_field(self) -> None:
        names = {f.name for f in fields(DeliveryOutcome)}
        for suspicious in (
            "text",
            "answer",
            "content",
            "message",
            "body",
            "error",
            "exc",
            "exception",
            "cause",
            "detail",
        ):
            assert suspicious not in names, names

    def test_the_boundary_never_names_the_exception_in_a_message(self) -> None:
        """Structural: ``boundary.py`` must not interpolate an exception or the
        text into any string. The log payload includes the rendered message
        with no allowlist applied, so ``log.error("failed: %s", exc)`` would
        leak ``str(exc)`` verbatim - a gap the logging module's own comment
        attributes to the caller."""
        tree = ast.parse((SRC / "boundary.py").read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.JoinedStr):
                for value in node.values:
                    if not isinstance(value, ast.FormattedValue):
                        continue
                    expr = value.value
                    name = (
                        expr.id
                        if isinstance(expr, ast.Name)
                        else getattr(expr, "attr", "")
                    )
                    assert name not in {"exc", "text", "e"}, (
                        f"boundary.py interpolates {name!r} at line {node.lineno}"
                    )

    def test_the_boundary_logs_nothing_at_all(self) -> None:
        """It has no logger, which is the strongest version of the rule: the
        caller logs ``outcome.metadata()`` with a constant message."""
        source = (SRC / "boundary.py").read_text(encoding="utf-8")
        for forbidden in ("import logging", "get_logger", "logger."):
            assert forbidden not in source, forbidden


class TestTheBatchKeepsItsRecord:
    def test_a_failure_does_not_discard_completed_turns(self) -> None:
        """A plain comprehension raised, and ``tuple(...)`` threw away the
        outcomes of turns that had already succeeded."""

        @dataclass(slots=True)
        class FailOnThird:
            calls: int = 0

            def emit(self, text: str) -> None:
                self.calls += 1
                if self.calls == 3:
                    raise RuntimeError("boom")

        sink = FailOnThird()
        outcomes = deliver_all([request() for _ in range(5)], sink=sink)
        assert len(outcomes) == 5, "the result must match the input length"
        assert [o.stage for o in outcomes[:2]] == [Stage.DELIVERED] * 2
        assert outcomes[2].stage is Stage.SINK_UNKNOWN
        assert [o.stage for o in outcomes[3:]] == [Stage.NOT_ATTEMPTED] * 2

    def test_it_stops_rather_than_speaking_over_a_half_spoken_turn(self) -> None:
        @dataclass(slots=True)
        class FailOnFirst:
            calls: int = 0

            def emit(self, text: str) -> None:
                self.calls += 1
                raise RuntimeError("boom")

        sink = FailOnFirst()
        deliver_all([request() for _ in range(4)], sink=sink)
        assert sink.calls == 1, "it must not keep emitting after an unknown"

    def test_a_sink_refusal_does_not_stop_the_batch(self) -> None:
        """Nothing was emitted, by the sink's own assertion, so there is no
        half-spoken utterance to speak over."""
        sink = RefusingSink()
        outcomes = deliver_all([request() for _ in range(3)], sink=sink)
        assert sink.attempts == 3
        assert all(o.stage is Stage.SINK_REFUSED for o in outcomes)

    def test_it_never_raises_on_a_sink_failure(self) -> None:
        for factory in (RefusingSink, CommittingThenFailingSink, CanarySink):
            outcomes = deliver_all([request()], sink=factory())
            assert len(outcomes) == 1
            assert not outcomes[0].delivered

    def test_the_happy_path_is_unchanged(self) -> None:
        sink = CountingSink()
        outcomes = deliver_all([request() for _ in range(3)], sink=sink)
        assert sink.calls == 3
        assert all(o.delivered for o in outcomes)
        assert all(o.may_claim_sent for o in outcomes)


class TestTheOutcomeInvariants:
    def test_a_negative_count_is_rejected(self) -> None:
        """The old check was ``not self.emitted_chars``, whose message promised
        ``> 0`` while accepting ``-1``. Harmless while the only producer was
        ``len(text)``; not harmless once a count could come from a sink."""
        with pytest.raises(ValueError, match="am"):
            DeliveryOutcome(delivered=True, stage=Stage.DELIVERED, emitted_chars=-1)

    def test_unknown_must_not_claim_zero(self) -> None:
        with pytest.raises(ValueError):
            DeliveryOutcome(delivered=False, stage=Stage.SINK_UNKNOWN, emitted_chars=0)

    def test_only_unknown_may_be_none(self) -> None:
        with pytest.raises(ValueError):
            DeliveryOutcome(
                delivered=False, stage=Stage.ANSWERABILITY, emitted_chars=None
            )

    def test_error_type_only_on_a_sink_failure(self) -> None:
        with pytest.raises(ValueError):
            DeliveryOutcome(
                delivered=False, stage=Stage.ANSWERABILITY, error_type="ValueError"
            )

    def test_the_error_is_a_meetai_error(self) -> None:
        assert issubclass(SinkRefusedBeforeEmitError, SinkError)
        from meetai.errors import MeetAIError

        assert issubclass(SinkError, MeetAIError)
