"""Record types for the answerability corpus.

Different question again from the other three corpora. ``authority_vi`` judges
a deterministic function on one utterance; ``llm_policy_vi`` judges free-form
model output; this judges a deterministic function on a **claim/evidence
mapping**, so a case has to carry the store's cards and the answer's structure
separately - which is exactly the distinction the module exists to enforce.

**The two axes are kept apart on purpose.** ``citation_validity`` is about
whether the cited ids resolve to retrievable cards: approved, in date,
unsuperseded, a citable card type. ``claim_support`` is about whether the
card's words back the claim's words. A case can be valid and unsupported -
that is the recorded residual - and a corpus that collapsed them into one
label could not express it.

Imports nothing from ``meetai``, enforced by a test that reads this source. A
corpus able to call the function it judges could copy that function's output
into its own labels, and the copy would be invisible in the resulting table.
Levels and kinds are plain strings for the same reason.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass, field


class RiskGroup(enum.Enum):
    """The slices reported separately.

    Grouped by *what kind of mistake a failure would be*. A false answer in
    ``V_SUBSTITUTION`` is MeetAI stating a figure that answers a different
    question; a false abstention in ``S_SUPPORTED`` is MeetAI refusing a relay
    it was built to make. Those are not commensurable, so they never share a
    denominator.
    """

    S_SUPPORTED = "S_supported"
    """Evidence genuinely backs every claim. Answering is correct."""

    V_SUBSTITUTION = "V_substitution"
    """A real approved card holds the value, but it answers a different
    question. The case an id-level check cannot see."""

    M_MISSING_VALUE = "M_missing_value"
    """The card is on subject and holds no value for what was asked."""

    C_CONFLICT = "C_conflict"
    """Two cited cards disagree."""

    T_CITATION_VALIDITY = "T_citation_validity"
    """Pending, superseded, expired, absent, or a non-citable card type.
    Nothing to do with claim wording."""

    P_PARTIAL = "P_partial"
    """Multi-part questions. The operator's decision: answer the supported
    parts, declare the rest."""

    I_INJECTION = "I_injection"
    """An imperative instruction sits inside a card's claim text."""

    D_DECLARATIVE_INJECTION = "D_declarative_injection"
    """A flat assertion inside a card, with no imperative to strip. There is
    nothing in the wording to find, so the card has to be judged on whether it
    contradicts itself."""

    U_UNVERIFIABLE = "U_unverifiable"
    """The module has no way to check the claim: a paraphrase outside the
    anchor classes, or a value that depends on identity. These used to pass."""

    F_MALFORMED = "F_malformed"
    """The claim structure does not describe the answer, or disagrees with the
    proposal's citations."""

    R_PARAPHRASE = "R_paraphrase"
    """The claim and the card use **different words for the same thing**, and
    the card really does answer the question. ``deadline`` / ``han chot``.

    The only group here whose correct outcome is to answer, which is why it is
    separate from the groups below: it measures the **cost** of a token-based
    subject check rather than its safety. A refusal here is a false
    abstention, and the operator asking in Vietnamese about a card written
    with the English word is not an adversarial case - it is the ordinary
    one."""

    Y_DESIGNATOR = "Y_designator"
    """The subject differs only by a short **label**: option B against option
    C, phase 1 against phase 2.

    Its own group because the distinguishing token is not a value and not a
    content word, so neither the anchor comparison nor the subject comparison
    is built to see it - and the two cards are otherwise word-for-word alike.
    A substitution here changes **which** thing was approved while every
    other check passes."""

    Q_QUESTION_MISMATCH = "Q_question_mismatch"
    """The claim is **true and properly cited**, and answers a different
    question than the one asked.

    Distinct from ``V_SUBSTITUTION``, where the claim itself misstates a
    card. Here nothing about the claim is false, so every claim-against-card
    check passes by construction; what is wrong is the claim-against-
    *question* relation. The harm is the attribution frame: a listener who
    asked about phase 2 and hears "according to the approved note, Khue owns
    phase 1 testing" takes that as the answer."""

    N_MULTI_EVENT = "N_multi_event"
    """One card, several events, and possibly a correction to one of them.

    Ordinary meeting notes look like this, so the group measures both
    directions at once: retiring the corrected event is required, and
    retiring the **untouched** events along with it is an over-refusal that
    makes a normal card unanswerable."""


class ExpectedOutcome(enum.Enum):
    """What the module must return.

    Named for the *level* rather than for "pass/fail", because the reason is
    what a caller logs and what an operator reads.
    """

    SUPPORTED = "supported"
    UNSUPPORTED = "unsupported"
    CONFLICTING = "conflicting"
    NO_CITABLE_EVIDENCE = "no_citable_evidence"
    PARTIAL_UNDECLARED = "partial_undeclared"
    GAP_ASSERTS = "gap_asserts"
    MALFORMED = "malformed"
    UNVERIFIABLE_CLAIM = "unverifiable_claim"
    EVIDENCE_SELF_CONTRADICTORY = "evidence_self_contradictory"

    @property
    def permits_answering(self) -> bool:
        return self is ExpectedOutcome.SUPPORTED

    @property
    def verdict(self) -> str:
        """Three-state view, as a plain string.

        The corpus states this itself rather than importing the enum it
        judges, so a mislabelled verdict is a corpus bug the harness can
        catch instead of an assumption it inherits.
        """
        if self is ExpectedOutcome.SUPPORTED:
            return "supported"
        if self in {
            ExpectedOutcome.MALFORMED,
            ExpectedOutcome.UNVERIFIABLE_CLAIM,
            ExpectedOutcome.EVIDENCE_SELF_CONTRADICTORY,
        }:
            return "unclear"
        return "unsupported"


@dataclass(frozen=True, slots=True)
class CardSpec:
    """One card in the store, as the corpus states it.

    ``status`` and ``card_type`` are plain strings so this module stays free
    of ``meetai`` imports; the harness maps them. ``retrievable`` is the
    corpus author's own statement of citation validity, written independently
    of the status fields so a disagreement between them is a corpus bug the
    harness can catch rather than a silent assumption.
    """

    card_id: str
    claim: str
    status: str = "approved"
    card_type: str = "project"
    retrievable: bool = True
    valid_from: float | None = None
    valid_until: float | None = None
    superseded_by: str | None = None

    def __post_init__(self) -> None:
        if not self.card_id or not self.claim:
            raise ValueError(f"{self.card_id!r}: card_id va claim phai khac rong")
        if not isinstance(self.claim, str):
            raise TypeError(f"{self.card_id}: claim phai la str")


@dataclass(frozen=True, slots=True)
class ClaimSpec:
    """One claim in the answer, with the single card it rests on."""

    text: str
    evidence_id: str | None = None
    kind: str = "grounded"

    def __post_init__(self) -> None:
        if self.kind not in {"grounded", "gap"}:
            raise ValueError(f"kind phai la grounded hoac gap: {self.kind!r}")
        if self.kind == "grounded" and not self.evidence_id:
            raise ValueError(f"{self.text[:24]!r}: claim grounded phai dan evidence")
        if self.kind == "gap" and self.evidence_id:
            raise ValueError(f"{self.text[:24]!r}: claim gap khong duoc dan evidence")


@dataclass(frozen=True, slots=True)
class AnswerabilityCase:
    """One labelled turn.

    ``claim_support`` and ``citation_validity`` are recorded separately from
    ``expected``, and that redundancy is the point: ``expected`` says what the
    function must return, while the two axes say *why* the author believes it.
    A case whose axes cannot produce its expected level is a labelling mistake,
    and a test checks the implication rather than trusting it.

    ``policy_basis`` cites the rule the label follows. A label justified only
    by "that is what the function returned" cannot produce one.
    """

    case_id: str
    group: RiskGroup
    question: str
    answer: str
    expected: ExpectedOutcome
    policy_basis: str
    claims: tuple[ClaimSpec, ...] = ()
    cards: tuple[CardSpec, ...] = ()
    cited_ids: tuple[str, ...] = ()
    now: float = 1000.0

    claim_support: str = "supported"
    """``supported`` | ``absent`` | ``wrong_subject`` | ``conflicting``
    | ``unverifiable`` | ``n/a``

    ``unverifiable`` is the axis value added when the skip-path closed: the
    claim is neither backed nor contradicted, because nothing could check it.
    """

    citation_validity: str = "valid"
    """``valid`` | ``not_retrievable`` | ``absent`` | ``n/a``"""

    answers_question: str = "yes"
    """``yes`` | ``no`` | ``n/a`` - whether the claim addresses what was asked.

    **The rule, stated because it was applied inconsistently before it was
    written down.** ``no`` means the claim addresses a *different attribute*
    than the question did: total budget for infrastructure cost, phase 1 for
    phase 2, a figure for a percentage. For a **multi-part** question, a claim
    answering one of the parts asked is ``yes`` - its failure is the silence
    about the other part, which is what ``PARTIAL_UNDECLARED`` already says,
    and recording it as ``no`` would conflate going quiet with answering the
    wrong thing. ``P.undeclared.01`` is the case that forced the distinction.

    The **third** axis, and it is independent of the other two for a reason
    the corpus needed a group to express: a claim can be word-for-word out of
    its card, cited to a valid card, and still answer a different question
    than the one asked. Both older axes say "fine" there, because both compare
    the claim to the **card**. Nothing compared it to the **question**.

    So a case with ``claim_support="supported"``, ``citation_validity="valid"``
    and ``answers_question="no"`` is not a contradictory label - it is the
    whole point of ``Q_QUESTION_MISMATCH``, and a reader who sees the first
    two fields and expects ``SUPPORTED`` is making the mistake the group is
    there to catch."""

    minimal_pair: str = ""
    notes: str = ""

    known_gap: bool = False
    """The module is known to **disagree** with this label.

    Same ledger shape as ``authority_vi``: a measured hole lives in the suite
    rather than waiting to be found in a pilot. ``expected`` keeps saying what
    policy requires, so the label never drifts towards the implementation, and
    the harness asserts the disagreement **persists** - a fix fails the test
    and tells the author to clear the flag.

    It is not a tolerance. Each flag carries a ``gap_reason`` naming the
    mechanism that would close it, and the per-group ceilings may only be
    lowered."""

    gap_reason: str = ""
    """Which mechanism is missing. Required when ``known_gap`` is set.

    "Needs more work" is not a reason; the field exists to make the author
    name the thing that is absent, because that is what distinguishes a
    recorded hole from an excuse."""

    def __post_init__(self) -> None:
        if not self.policy_basis:
            raise ValueError(f"{self.case_id}: thieu policy_basis")
        if self.claim_support not in {
            "supported",
            "absent",
            "wrong_subject",
            "conflicting",
            "unverifiable",
            "n/a",
        }:
            raise ValueError(f"{self.case_id}: claim_support khong hop le")
        if self.citation_validity not in {"valid", "not_retrievable", "absent", "n/a"}:
            raise ValueError(f"{self.case_id}: citation_validity khong hop le")
        if self.answers_question not in {"yes", "no", "n/a"}:
            raise ValueError(f"{self.case_id}: answers_question khong hop le")
        if self.expected is ExpectedOutcome.SUPPORTED and self.answers_question == "no":
            raise ValueError(
                f"{self.case_id}: expected SUPPORTED nhung claim khong tra loi "
                f"dung cau hoi"
            )
        if self.expected is ExpectedOutcome.SUPPORTED and self.claim_support != (
            "supported"
        ):
            raise ValueError(
                f"{self.case_id}: expected SUPPORTED nhung claim_support = "
                f"{self.claim_support!r}"
            )
        if self.known_gap and not self.gap_reason:
            raise ValueError(
                f"{self.case_id}: known_gap phai kem gap_reason neu ten co che con thieu"
            )
        if self.gap_reason and not self.known_gap:
            raise ValueError(f"{self.case_id}: co gap_reason nhung khong known_gap")
        ids = [card.card_id for card in self.cards]
        if len(set(ids)) != len(ids):
            raise ValueError(f"{self.case_id}: card_id trung lap: {ids}")


@dataclass(frozen=True, slots=True)
class Corpus:
    version: str
    cases: tuple[AnswerabilityCase, ...] = field(default_factory=tuple)
