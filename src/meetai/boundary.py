"""The one place a proposal can become output (pipeline step 7).

The handoff document's pipeline step 7 is *"Deterministic policy gate kiem lai
truoc send/TTS. LLM/evaluator co the chan hoac xin hoi, khong the cap quyen"*
(line 113). Until this module, that step had no implementation: nothing in
``src/`` called :func:`~meetai.authority.evaluate_response`, so the gate was a
function the tests exercised and nothing else. A control with no caller
constrains nothing.

**This is an internally tested boundary, not a production integration.** There
is no Discord caller, no listener, no persistence, no TTS and no inference
here. :class:`RecordingSink` keeps emitted text in memory for tests and the
CLI. A real sink speaks into a meeting, which makes it a media path and
therefore subject to ``Settings.require_media_processing_allowed()`` and to
consent - neither of which this module invents, because gate 0-U is open and
the operator has not chosen the consent mode. What this module provides is a
boundary a future caller can be *required* to go through.

**The structural claim, and how it is enforced.** Proposal text reaches the
outside world through exactly one expression in this file, inside the branch
that both checks have cleared. Everything else about the outcome is metadata:
:class:`DeliveryOutcome` has **no text field**, deliberately, so a caller
cannot read the content back out of a refusal and emit it anyway. A test reads
this module's AST and asserts the single ``emit`` call site, the same way
``test_ui.py`` pins the single ``FastAPI(...)`` construction.

**Order of checks, and why this order.** Answerability (step 5) runs before
authority (step 7) because they answer different questions and the cheaper
honest refusal should win: a sentence nothing supports should be refused for
being unsupported, not for whatever the lexicon happens to notice in it. Both
must pass. Neither can be skipped by anything the model puts in the proposal.

Framework-free. The boundary decides; it does not serialise, log to a
framework, or open a socket.
"""

from __future__ import annotations

import enum
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable

from meetai.answerability import (
    AnswerabilityAssessment,
    Claim,
    SupportLevel,
    Verdict,
    assess,
)
from meetai.authority import MINIMUM_CONFIDENCE, evaluate_response
from meetai.content import MeetingContent
from meetai.errors import SinkRefusedBeforeEmitError
from meetai.knowledge import KnowledgeCard
from meetai.response import AddressContext, ProposedResponse, ResponseDecision


@runtime_checkable
class OutputSink(Protocol):
    """Where delivered text goes.

    A protocol rather than a base class so a real sink never inherits
    behaviour from a test double. Implementations that reach a meeting are
    media paths: they must call
    ``Settings.require_media_processing_allowed()`` and check consent before
    doing anything. This module cannot enforce that on an arbitrary
    implementation, which is why :func:`deliver` takes the sink as an argument
    and a test asserts no network-capable sink exists in the repository yet.
    """

    def emit(self, text: str) -> None:
        """Deliver ``text``. Called only for an allowed speaking proposal."""
        ...


@dataclass(slots=True)
class RecordingSink:
    """In-memory sink for tests and the CLI. Reaches nothing.

    ``emitted`` holds meeting content, so it is excluded from the repr and the
    class prints shape only - the same discipline every content-bearing
    dataclass in this project follows.
    """

    emitted: list[str] = field(default_factory=list, repr=False)

    def emit(self, text: str) -> None:
        self.emitted.append(text)

    def __repr__(self) -> str:
        return f"RecordingSink({len(self.emitted)} emitted)"

    @property
    def count(self) -> int:
        return len(self.emitted)


class Stage(enum.Enum):
    """Which stage decided the outcome.

    Named stages rather than a bare boolean because a refusal's *reason* is
    what an operator needs, and because "refused by the gate" and "refused for
    lack of support" are different problems with different fixes.
    """

    NOT_SPEAKING = "not_speaking"
    """The proposal was silence or a follow-up. Nothing to deliver, and
    nothing refused: both are always permitted."""

    ANSWERABILITY = "answerability"
    AUTHORITY = "authority"
    DELIVERED = "delivered"

    SINK_REFUSED = "sink_refused"
    """Both gates passed; the sink **asserts** it emitted nothing.

    The proposal is still approved. What failed is transport, not judgement -
    a different problem from a refusal, and a caller that counted it as a
    refusal would go and revise a sentence that was fine.
    """

    SINK_UNKNOWN = "sink_unknown"
    """Both gates passed; **whether anything was emitted is not known.**

    The honest state, and the default for any sink failure that is not an
    explicit :class:`SinkRefusedBeforeEmitError`. A caller may conclude
    nothing at all about the meeting from it: not that the sentence was said,
    and not that it was not.
    """

    NOT_ATTEMPTED = "not_attempted"
    """A turn :func:`deliver_all` stopped before reaching.

    Exists so a batch result stays the same length as its input. An index that
    silently shifts is how a caller attributes one turn's outcome to another.
    """

    @property
    def is_refusal(self) -> bool:
        """Whether a **gate** refused. Sink failures are not refusals."""
        return _KIND[self] is _Kind.REFUSED

    @property
    def is_sink_failure(self) -> bool:
        """Whether the sink failed after both gates permitted."""
        return _KIND[self] is _Kind.SINK_FAILED

    @property
    def permits_claiming_sent(self) -> bool:
        """Whether MeetAI may say the sentence went out.

        True for exactly one member. A property rather than a comparison at
        each call site, so that adding a member forces a decision here instead
        of inheriting ``False`` by accident - or, worse, inheriting ``True``
        from a set someone extended.
        """
        return self is Stage.DELIVERED


class _Kind(enum.Enum):
    """What a stage *is*, for the classifications above."""

    QUIET = "quiet"
    REFUSED = "refused"
    DELIVERED = "delivered"
    SINK_FAILED = "sink_failed"
    SKIPPED = "skipped"


_KIND: dict[Stage, _Kind] = {
    Stage.NOT_SPEAKING: _Kind.QUIET,
    Stage.ANSWERABILITY: _Kind.REFUSED,
    Stage.AUTHORITY: _Kind.REFUSED,
    Stage.DELIVERED: _Kind.DELIVERED,
    Stage.SINK_REFUSED: _Kind.SINK_FAILED,
    Stage.SINK_UNKNOWN: _Kind.SINK_FAILED,
    Stage.NOT_ATTEMPTED: _Kind.SKIPPED,
}
"""Total map over :class:`Stage`, with a coverage test.

A dict rather than a set membership test, for the reason the answerability
verdict map already gives: ``is_refusal`` used to be ``self in {...}``, so a
new member answered ``False`` to every question without anyone choosing that.
A ``KeyError`` is a better outcome than a silent default, and the coverage test
turns it into a failure at the right time.
"""


@dataclass(frozen=True, slots=True)
class ResponseRequest:
    """One turn's input to the boundary.

    ``cards`` is the store's view; ``proposal.evidence_ids`` is the model's
    claim about which of them it used. Keeping the two in separate fields is
    the claim/evidence mapping: the model selects, the store decides what a
    selection resolves to, and nothing the model writes can promote an
    unretrievable card.

    ``address`` likewise comes from the addressing classifier, not from the
    model. A proposal cannot assert that it was spoken to.
    """

    question: MeetingContent
    proposal: ProposedResponse
    address: AddressContext
    claims: tuple[Claim, ...] = ()
    cards: tuple[KnowledgeCard, ...] = ()
    now: float = 0.0
    """claims is the answer's structure: one assertion per cited card,
    plus an explicit gap claim for anything the question asked that the
    evidence does not cover. The operator decided a partial answer is
    permitted only when it says what it is missing, and a flat list of
    evidence ids cannot express that."""

    def metadata(self) -> dict[str, object]:
        """Metadata-only view. No question text, no answer text."""
        return {
            "question_chars": self.question.char_count,
            "claim_count": len(self.claims),
            "card_count": len(self.cards),
            "directly_addressed": self.address.directly_addressed,
            **self.proposal.metadata(),
        }


@dataclass(frozen=True, slots=True)
class DeliveryOutcome:
    """What the boundary decided. **Carries no content, by design.**

    There is no ``text`` field and there will not be one. A caller holding a
    refusal must not be able to read the proposed sentence out of it and emit
    that instead - the whole point of routing everything through one sink is
    that the sink is the only way out.
    """

    delivered: bool
    stage: Stage
    rules: tuple[str, ...] = ()
    support_level: SupportLevel | None = None
    error_type: str | None = None
    """The failing exception's **class name**, and nothing else.

    A ``str`` produced by ``type(exc).__name__`` at the boundary - never the
    exception object, never ``str(exc)``, never ``__cause__``. The reason is
    specific: an exception object reaches its own ``__traceback__``, which
    reaches the frame that was executing, whose locals hold the utterance. A
    field called ``error`` holding the exception would pass the field-name
    tests in this repository and be a complete content leak by reference.

    The same shape ``logging_setup`` already settled on for the same reason.
    """
    answerability_verdict: Verdict | None = None
    """The three-state answerability result, when that stage ran.

    Surfaced separately from ``support_level`` because a caller branching on
    the detailed level would have nine cases to get right, while the verdict
    has three and only one of them speaks. ``UNCLEAR`` is the one worth
    logging loudly: it means the module could not check, so a run with many of
    them is a run whose evidence or phrasing needs attention rather than a run
    that went well.
    """

    emitted_chars: int | None = 0
    """Characters **handed to the sink**, or ``None`` for "no claim".

    Named for what it measures. On a successful delivery it is ``len(text)``,
    which is what MeetAI passed in - not what the sink delivered and not what
    anyone heard. For :class:`RecordingSink` those coincide; for a speaking
    sink they will not, and the distinction is the difference between intent
    and effect.

    ``None`` is reserved for :attr:`Stage.SINK_UNKNOWN`, where ``0`` would be a
    claim MeetAI cannot make - "nothing went out" - rather than the absence of
    one. ``None`` is falsy, so every existing ``if not emitted_chars`` guard
    keeps working; what changes is that ``0`` and "unknown" stop being the same
    value.
    """

    def __post_init__(self) -> None:
        if self.delivered and self.stage is not Stage.DELIVERED:
            raise ValueError("delivered=True phai di voi stage=delivered")
        if not self.delivered and self.stage is Stage.DELIVERED:
            raise ValueError("stage=delivered phai di voi delivered=True")
        if self.emitted_chars is not None and self.emitted_chars < 0:
            # The old check was `not self.emitted_chars`, whose message
            # promised `> 0` while accepting -1. Harmless while the only
            # producer was len(text); not harmless the moment a count could
            # come from a sink.
            raise ValueError("emitted_chars khong duoc am")
        if self.delivered and not self.emitted_chars:
            raise ValueError("delivered=True phai co emitted_chars > 0")
        if not self.delivered and self.emitted_chars:
            raise ValueError("khong delivered thi emitted_chars phai la 0")
        if self.stage is Stage.SINK_UNKNOWN and self.emitted_chars is not None:
            raise ValueError(
                "sink_unknown phai co emitted_chars=None: 0 la mot khang dinh "
                "('khong co gi di ra') ma MeetAI khong co bang chung cho"
            )
        if self.stage is not Stage.SINK_UNKNOWN and self.emitted_chars is None:
            raise ValueError("chi sink_unknown duoc co emitted_chars=None")
        if self.error_type is not None and not self.stage.is_sink_failure:
            raise ValueError("error_type chi co nghia khi sink that bai")

    def __bool__(self) -> bool:
        return self.delivered

    @property
    def may_claim_sent(self) -> bool:
        """Whether MeetAI may report that the sentence was said.

        The question the contract exists to answer, with a name, so that no
        caller has to assemble it from ``delivered`` and a stage comparison and
        get it subtly wrong.
        """
        return self.delivered and self.stage.permits_claiming_sent

    @property
    def must_not_retry(self) -> bool:
        """Whether re-sending this proposal risks saying it twice.

        True for :attr:`Stage.SINK_UNKNOWN`, because MeetAI does not know
        whether the first attempt was heard. The boundary does not retry in any
        state - it reports, and the caller decides - but the unknown state is
        the one where a caller's retry could put a duplicate utterance into a
        meeting, and nothing here can promise exactly-once without
        idempotency the sink does not have.
        """
        return self.stage is Stage.SINK_UNKNOWN

    def metadata(self) -> dict[str, object]:
        return {
            "delivered": self.delivered,
            "stage": self.stage.value,
            "rules": list(self.rules),
            "support_level": None
            if self.support_level is None
            else self.support_level.value,
            "emitted_chars": self.emitted_chars,
            "error_type": self.error_type,
            "may_claim_sent": self.may_claim_sent,
            "must_not_retry": self.must_not_retry,
        }


def deliver(
    request: ResponseRequest,
    *,
    sink: OutputSink,
    minimum_confidence: float = MINIMUM_CONFIDENCE,
) -> DeliveryOutcome:
    """Run the full boundary and deliver only if every stage permits.

    Fail-closed at each step, and fail-closed on the way out: the sink call is
    the last statement of the last branch, so an exception anywhere before it
    means nothing was emitted. There is no ``finally`` that delivers and no
    path that delivers twice.

    A non-speaking proposal returns without touching the sink. Since
    :class:`~meetai.response.ProposedResponse` now refuses text on a non-speak
    decision, such a proposal has nothing to leak - but the branch is still
    written as an early return rather than relying on that, because two
    independent reasons a thing cannot happen is the pattern this project uses
    where the cost of being wrong is high.
    """
    proposal = request.proposal
    # A floor, not a setting. Measured: `deliver(..., minimum_confidence=0.0)`
    # delivered a proposal with confidence 0.0 that the default refuses, and
    # -5.0 did too - so the gate's one numeric check was switchable off
    # through the boundary's own public signature, and `deliver_all` passed the
    # value to every turn. A caller may demand *more* confidence than the
    # project's floor; it may not demand less. MINIMUM_CONFIDENCE is itself
    # uncalibrated, which makes a caller "tuning" it a foreseeable move rather
    # than an attack, and is exactly why the clamp belongs here.
    effective_confidence = max(minimum_confidence, MINIMUM_CONFIDENCE)

    if proposal.decision is not ResponseDecision.SPEAK:
        return DeliveryOutcome(
            delivered=False,
            stage=Stage.NOT_SPEAKING,
            rules=(f"decision_{proposal.decision.value}",),
        )

    # Narrowing for the type checker and a real guard: SPEAK without text is
    # refused at construction, so this is unreachable through the public type.
    # Kept as a branch rather than an assert, because an assert disappears
    # under `python -O` and a refusal must not depend on an optimisation flag.
    if proposal.text is None:
        return DeliveryOutcome(
            delivered=False,
            stage=Stage.AUTHORITY,
            rules=("speak_without_text",),
        )

    assessment: AnswerabilityAssessment = assess(
        question=request.question,
        answer=proposal.text,
        claims=request.claims,
        cards=request.cards,
        cited_ids=proposal.evidence_ids,
        now=request.now,
    )
    if not assessment.permits_answering:
        return DeliveryOutcome(
            delivered=False,
            stage=Stage.ANSWERABILITY,
            rules=assessment.findings,
            support_level=assessment.level,
            answerability_verdict=assessment.verdict,
        )

    verdict = evaluate_response(
        proposal,
        address=request.address,
        evidence=tuple(card.as_evidence() for card in request.cards),
        now=request.now,
        minimum_confidence=effective_confidence,
    )
    if not verdict.allowed:
        return DeliveryOutcome(
            delivered=False,
            stage=Stage.AUTHORITY,
            rules=verdict.rules,
            support_level=assessment.level,
            answerability_verdict=assessment.verdict,
        )

    text = proposal.text.unsafe_text()
    try:
        # The only expression in the project that hands proposal text to a
        # sink. An AST test asserts it is the only one, and asserts it is not
        # inside any handler or finally - a `finally` that emitted would run on
        # a refusal path too, which is the shape the guard exists to forbid.
        sink.emit(text)
    except SinkRefusedBeforeEmitError as exc:
        # The sink *asserts* nothing left it. Trusted, and recorded as trust:
        # the boundary cannot verify the claim, and a sink that raises this
        # after speaking is a lie this code will act on.
        return DeliveryOutcome(
            delivered=False,
            stage=Stage.SINK_REFUSED,
            rules=("sink_refused_before_emit",),
            support_level=assessment.level,
            answerability_verdict=assessment.verdict,
            error_type=type(exc).__name__,
        )
    except BaseException as exc:
        # `BaseException`, deliberately. A KeyboardInterrupt or a cancellation
        # arriving mid-emit leaves exactly the same question unanswered - was
        # it heard? - and narrowing to `Exception` would let those two cases
        # escape as an exception with no record, which is the behaviour this
        # whole contract replaces.
        #
        # The outcome is returned rather than raised because an exception is
        # the one channel that cannot carry the per-turn record, and the record
        # is the point: both gates passed, the one legitimate emit was
        # attempted, and nothing is known about the result.
        return DeliveryOutcome(
            delivered=False,
            stage=Stage.SINK_UNKNOWN,
            rules=("sink_failed_outcome_unknown",),
            support_level=assessment.level,
            answerability_verdict=assessment.verdict,
            emitted_chars=None,
            error_type=type(exc).__name__,
        )
    return DeliveryOutcome(
        delivered=True,
        stage=Stage.DELIVERED,
        support_level=assessment.level,
        answerability_verdict=assessment.verdict,
        emitted_chars=len(text),
    )


def deliver_all(
    requests: Sequence[ResponseRequest],
    *,
    sink: OutputSink,
    minimum_confidence: float = MINIMUM_CONFIDENCE,
) -> tuple[DeliveryOutcome, ...]:
    """Run several turns through the same sink.

    Exists for the CLI demonstration and for tests that need a sequence. It
    adds no decision of its own about *whether to speak* - deliberately, so
    there is no second place where the order of checks could differ.

    It does make one decision about *whether to continue*: an unknown sink
    outcome stops the batch. The result is always the same length as
    ``requests``, with unreached turns marked :attr:`Stage.NOT_ATTEMPTED`.

    **It never raises on a sink failure**, and that is a change from a plain
    comprehension, which discarded the outcomes of turns that had already
    succeeded. The cost is stated honestly: a caller that ignores the returned
    tuple now proceeds quietly where it used to get an exception. That is paid
    for with a test, not with a comment.
    """
    outcomes: list[DeliveryOutcome] = []
    stop = False
    for request in requests:
        if stop:
            # Same length as `requests`, always, so a caller zipping the two
            # cannot mis-attribute one turn's outcome to another turn.
            outcomes.append(
                DeliveryOutcome(
                    delivered=False,
                    stage=Stage.NOT_ATTEMPTED,
                    rules=("stopped_after_unknown_sink_outcome",),
                )
            )
            continue
        outcome = deliver(request, sink=sink, minimum_confidence=minimum_confidence)
        outcomes.append(outcome)
        if outcome.must_not_retry:
            # After an unknown outcome MeetAI may be mid-utterance. Speaking
            # the next turn on top of a possibly half-spoken one is the
            # duplicate-utterance harm this contract exists to prevent, so the
            # batch stops and says so in the result rather than carrying on.
            stop = True
    return tuple(outcomes)


__all__ = [
    "DeliveryOutcome",
    "OutputSink",
    "RecordingSink",
    "ResponseRequest",
    "Stage",
    "deliver",
    "deliver_all",
]
