"""The schema for one proposed reply (slice S1.5).

A reply is a *proposal* until a deterministic gate clears it. That word is the
design: the model produces a structured object declaring what it wants to say,
what it is relying on, and how confident it is, and
:mod:`meetai.authority` decides. Nothing in this module can approve anything.

Two shapes are load-bearing:

- **Text is :class:`~meetai.content.MeetingContent`.** A proposed reply is
  content. Typing it as content means an incidental log line or exception
  message reports its length rather than its words, all the way to the
  platform boundary.

- **Risk flags can only restrict.** The model declares what it thinks is risky
  and the gate adds its own findings; there is no field through which a
  proposal can assert that something is *permitted*. A model that could grant
  itself authority would make every other check advisory.

This module imports no framework.
"""

from __future__ import annotations

import enum
from collections.abc import Sequence
from dataclasses import dataclass, field

from meetai.content import MeetingContent


class ResponseDecision(enum.Enum):
    """What the model proposes to do.

    ``SILENT`` is first and is the safe default: the handoff document is
    explicit that not interjecting is preferable to interjecting wrongly, and
    an ambiguous classification must land here.
    """

    SILENT = "silent"
    SPEAK = "speak"
    FOLLOWUP = "followup"
    """Say nothing now and record a question to put to the operator later."""


class SpeechAct(enum.Enum):
    """The speech acts MeetAI is *permitted* to perform.

    An allowlist, and that direction is the design. Pattern matching on text
    can only deny what it recognises, so a gate built on detection alone is
    only as good as its lexicon - and a Vietnamese commissive lexicon will
    never be complete ("xong thu hai", "chot luon", "cu giao minh" are all
    commitments with no keyword in common).

    Requiring the model to declare one of these inverts the burden: a proposal
    with no declared intent, or an intent outside this set, is refused without
    anyone having to have anticipated its phrasing. A bypass now needs *both*
    a mislabelled declaration *and* phrasing the lexicon misses, instead of
    either one.
    """

    INFORM = "inform"
    """State general knowledge, as an assistant rather than as the operator."""

    CITE_APPROVED_POSITION = "cite_approved_position"
    """Relay a position from an approved knowledge card, with attribution."""

    DISCLOSE_IDENTITY = "disclose_identity"
    """Say what MeetAI is."""

    DEFER_TO_OPERATOR = "defer_to_operator"
    """Say that this needs the operator, and offer nothing further."""

    ASK_CLARIFICATION = "ask_clarification"
    """Ask the meeting a question, committing to nothing."""


class RiskFlag(enum.Enum):
    """A concern attached to a proposal, by the model or by the gate.

    These never unlock anything. The gate reads them, adds to them, and may
    refuse because of them.
    """

    NO_EVIDENCE = "no_evidence"
    STALE_EVIDENCE = "stale_evidence"
    CONFLICTING_EVIDENCE = "conflicting_evidence"
    OUT_OF_SCOPE_EVIDENCE = "out_of_scope_evidence"
    LOW_CONFIDENCE = "low_confidence"
    AMBIGUOUS_ADDRESS = "ambiguous_address"
    POSSIBLE_INJECTION = "possible_injection"
    PERSONAL_POSITION = "personal_position"
    """The reply states a position attributable to the operator, not general knowledge."""


class EvidenceStatus(enum.Enum):
    """Whether a knowledge card may be cited.

    ``APPROVED`` is the only citable status, written as an identity check so a
    status added later cannot be cited by default. ``CANDIDATE`` and ``PENDING``
    exist precisely so that unapproved material has somewhere to live without
    being retrievable as fact.
    """

    CANDIDATE = "candidate"
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    SUPERSEDED = "superseded"

    @property
    def is_citable(self) -> bool:
        return self is EvidenceStatus.APPROVED


@dataclass(frozen=True, slots=True)
class Evidence:
    """One approved knowledge card, as far as the gate needs to see it.

    Carries no claim text. The gate decides whether a citation is *usable* -
    approved, in scope, unexpired, unconflicted - and that decision needs
    metadata only. Keeping the claim out means the gate cannot be tempted to
    reason about content, and a gate verdict is safe to log.
    """

    evidence_id: str
    status: EvidenceStatus
    scope: str
    valid_from: float | None = None
    valid_until: float | None = None
    superseded_by: str | None = None

    def is_valid_at(self, now: float) -> bool:
        """Whether this card is within its validity window at ``now``."""
        if self.valid_from is not None and now < self.valid_from:
            return False
        return not (self.valid_until is not None and now >= self.valid_until)

    def is_usable_at(self, now: float) -> bool:
        """Whether this card may be cited at all at ``now``."""
        return (
            self.status.is_citable
            and self.superseded_by is None
            and self.is_valid_at(now)
        )


@dataclass(frozen=True, slots=True)
class AddressContext:
    """Whether and how MeetAI was addressed.

    ``alias_mentioned`` being true on its own is never enough to speak. The
    handoff document calls this out directly, and it matters more in Vietnamese
    than it might seem: the operator's name collides with an ordinary word, so
    "son nha" is a sentence about painting a house, not a summons.
    """

    directly_addressed: bool = False
    alias_mentioned: bool = False
    third_person_reference: bool = False

    @property
    def permits_speaking(self) -> bool:
        """Only a direct address permits an interjection."""
        return self.directly_addressed


@dataclass(frozen=True, slots=True)
class ProposedResponse:
    """What the model wants to do, pending the gate.

    ``declared_acts`` is how the model tells the gate what kind of speech act
    it believes it is performing. It is an input to a refusal, never to a
    permission: declaring nothing does not make a promise acceptable, because
    the gate inspects the text independently.
    """

    decision: ResponseDecision
    text: MeetingContent | None = None
    intent: SpeechAct | None = None
    """Which permitted speech act this is. Required to speak.

    ``None`` is refused rather than defaulted. A default would mean a proposal
    that declared nothing got the benefit of the doubt, which is the opposite
    of what an allowlist is for.
    """
    evidence_ids: tuple[str, ...] = ()
    confidence: float = 0.0
    risk_flags: frozenset[RiskFlag] = field(default_factory=frozenset)
    declared_acts: frozenset[str] = field(default_factory=frozenset)
    states_personal_position: bool = False

    def __post_init__(self) -> None:
        if self.decision is ResponseDecision.SPEAK and self.text is None:
            raise ValueError("decision=speak phai co text")
        if self.decision is ResponseDecision.SPEAK and self.intent is None:
            raise ValueError("decision=speak phai khai intent trong SpeechAct")
        if self.decision is not ResponseDecision.SPEAK and self.text is not None:
            # Closes a trap rather than tidying a type. The gate returns early
            # for a non-speak decision - correctly, because "silence is always
            # permitted" - so a SILENT proposal carrying prohibited text used
            # to come back ``allowed=True`` with no violations. Nothing was
            # wrong with that verdict; the danger was a caller reading
            # ``allowed`` and then delivering ``text`` without honouring
            # ``decision``. Measured and recorded in ADR 0006's addendum as a
            # caller obligation, which is a sentence someone has to remember.
            #
            # This makes it unforgettable: a proposal that says nothing cannot
            # carry anything to say. The obligation becomes a type error at
            # construction, which is where a boundary cannot route around it.
            #
            # FOLLOWUP is included deliberately. A follow-up question is for
            # the operator, not the meeting, so it belongs on a separate field
            # with its own routing if a later slice needs one - not on the
            # field the speech sink reads.
            raise ValueError(
                "chi decision=speak duoc mang text: mot proposal khong noi gi "
                "khong duoc mang noi dung co the toi sink"
            )
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("confidence phai trong khoang [0, 1]")

    @property
    def char_count(self) -> int:
        """Length of the proposed text. Safe to log."""
        return 0 if self.text is None else self.text.char_count

    def metadata(self) -> dict[str, object]:
        """Metadata-only view for a log line or the status UI."""
        return {
            "decision": self.decision.value,
            "intent": None if self.intent is None else self.intent.value,
            "char_count": self.char_count,
            "evidence_count": len(self.evidence_ids),
            "confidence": self.confidence,
            "risk_flags": sorted(flag.value for flag in self.risk_flags),
        }


def silence(*flags: RiskFlag) -> ProposedResponse:
    """A proposal to say nothing. Always available, never refused.

    Provided so that every abstention path in the pipeline produces the same
    object rather than each constructing its own, and so that "say nothing" is
    as easy to write as speaking.
    """
    return ProposedResponse(decision=ResponseDecision.SILENT, risk_flags=frozenset(flags))


def followup(reason_flags: Sequence[RiskFlag] = ()) -> ProposedResponse:
    """A proposal to record a question for the operator instead of answering."""
    return ProposedResponse(
        decision=ResponseDecision.FOLLOWUP, risk_flags=frozenset(reason_flags)
    )
