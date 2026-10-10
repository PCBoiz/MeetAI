"""Approved-knowledge store (slice S1.6).

The handoff document (section 7) is emphatic that RAG here means *approved
knowledge*, not a transcript of everything said. Three properties follow, and
they are the whole module:

1. **Only approved cards are retrievable.** ``retrieve`` filters on approval
   first, so a candidate cannot be returned as fact. The handoff document
   states this as an absolute, and it is the one that would do real damage if
   it drifted: an unapproved claim relayed in a meeting is MeetAI inventing the
   operator's position.

2. **Deletion and edits cascade.** A card lives in chunks, embeddings and
   caches as well as here. Deleting the row and leaving the derivatives is the
   failure that makes a retention promise false, so derived indexes register
   themselves and are purged by this store rather than being remembered about.

3. **Nothing is learned automatically.** There is no path from a transcript to
   a card. Ingest takes a candidate with a source reference that must match an
   allowlist, and a human approves it.

``claim`` and ``rationale`` are wrapped in :class:`~meetai.content.MeetingContent`
so a card cannot be rendered into a log line by an incidental interpolation.
They are the operator's own knowledge rather than meeting audio, but the
protection needed is identical and one mechanism is better than two.

This module imports no framework.
"""

from __future__ import annotations

import enum
import hashlib
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass, field, replace
from typing import Protocol

from meetai.content import MeetingContent
from meetai.errors import MeetAIError
from meetai.response import Evidence, EvidenceStatus


class KnowledgeError(MeetAIError):
    """A knowledge-store operation was refused."""


class IngestRejectedError(KnowledgeError):
    """A candidate's source is not on the allowlist.

    The handoff document rules out ingesting an entire account, repository,
    mailbox or calendar, so the store accepts a source only if the operator
    named it.
    """


class CardType(enum.Enum):
    """The card kinds the handoff document separates.

    The separation matters because the kinds carry different authority. A
    ``POSITION`` can be cited as the operator's stance; a ``STYLE_EXAMPLE``
    only shapes tone and must never be used as evidence of fact; a
    ``MEETING_CONTEXT`` card is session-bound and must not become long-term
    memory.
    """

    PROFILE = "profile"
    POSITION = "position"
    PROJECT = "project"
    GLOSSARY = "glossary"
    STYLE_EXAMPLE = "style_example"
    MEETING_CONTEXT = "meeting_context"

    @property
    def is_citable_as_fact(self) -> bool:
        """Whether a card of this kind may back a factual claim.

        Style examples guide phrasing only, and session context is not
        knowledge. Written as an exclusion of those two rather than a list of
        the rest, so a kind added later is citable only if someone changes this
        deliberately... which is the wrong default, so the check is inverted:
        new kinds are *not* citable until listed.
        """
        return self in _CITABLE_TYPES


_CITABLE_TYPES = frozenset(
    {CardType.PROFILE, CardType.POSITION, CardType.PROJECT, CardType.GLOSSARY}
)


class Sensitivity(enum.Enum):
    """Who a card may be shared with.

    ``PRIVATE`` is the default everywhere a default is needed: a card whose
    audience nobody stated must not be repeated in a group meeting.
    """

    PRIVATE = "private"
    GROUP = "group"
    PUBLIC = "public"


class AllowedAction(enum.Enum):
    """What MeetAI may do with a card.

    Separate from sensitivity: a card may be shareable in a meeting and still
    not be something MeetAI may volunteer unprompted.
    """

    CITE_WHEN_ASKED = "cite_when_asked"
    VOLUNTEER = "volunteer"
    GUIDE_TONE = "guide_tone"


def content_hash(claim: str, rationale: str, source_ref: str) -> str:
    """Stable digest of a card's substance, for dedupe and conflict checks.

    Covers claim, rationale and source so that the same sentence from two
    different sources is two cards - which is what a conflict check needs to
    see. Hashing the claim alone would silently merge them.
    """
    digest = hashlib.sha256()
    for part in (claim, rationale, source_ref):
        digest.update(part.encode("utf-8"))
        digest.update(b"\x1f")  # unit separator, so "ab"+"c" != "a"+"bc"
    return digest.hexdigest()


@dataclass(frozen=True, slots=True)
class KnowledgeCard:
    """One unit of approved knowledge.

    The field set is the one the handoff document mandates. ``content_hash`` is
    computed rather than supplied, so it cannot disagree with the content it
    describes.
    """

    card_id: str
    card_type: CardType
    claim: MeetingContent
    rationale: MeetingContent
    source_ref: str
    source_date: float
    approval_status: EvidenceStatus = EvidenceStatus.CANDIDATE
    approved_by: str | None = None
    approved_content_hash: str | None = None
    """The content digest as it stood **when the operator approved**.

    Not a duplicate of :attr:`content_hash`, and the difference is the whole
    point. ``content_hash`` is derived from the card's *current* content, so it
    always matches itself and can never witness a change - re-deriving it
    proves only that the digest function is deterministic. This field is a
    *record*, so comparing the two asks a question with a real answer: is this
    still the text that was read?

    ``update`` already revoked approval on edit, for the right reason - an
    edited card keeping its approval means the operator approved text they
    never saw. But that invariant held only for edits going *through* the
    store, and :class:`KnowledgeCard` is a frozen dataclass:
    ``dataclasses.replace`` produces an approved card with arbitrary content
    and no method was called to revoke anything. This closes that path.

    A **superseded** card keeps its witness, and that is deliberate: it *was*
    approved at that content, the store keeps old cards so a change can be
    explained, and :meth:`is_retrievable_at` already excludes them by
    ``superseded_by``. ``CANDIDATE``, ``PENDING`` and ``REJECTED`` must carry
    ``None`` - those states mean never approved, or approval withdrawn.

    ``None`` on an approved card is **not citable**. Fail closed on absence:
    a card marked approved with no record of what was approved is exactly the
    state this exists to detect, so it must not be the permissive default.

    **In-memory only.** Persistence is off and gate 0-U is open, so this is
    object state in a process and a fake store. It is not evidence of
    durability across a restart, and nothing here adds a database.
    """
    valid_from: float | None = None
    valid_until: float | None = None
    supersedes: str | None = None
    superseded_by: str | None = None
    scope: str = "general"
    sensitivity: Sensitivity = Sensitivity.PRIVATE
    confidence: float = 0.0
    allowed_actions: frozenset[AllowedAction] = field(
        default_factory=lambda: frozenset({AllowedAction.CITE_WHEN_ASKED})
    )
    version: int = 1

    def __post_init__(self) -> None:
        if not 0.0 <= self.confidence <= 1.0:
            raise KnowledgeError("confidence phai trong khoang [0, 1]")
        if (
            self.approval_status
            not in {EvidenceStatus.APPROVED, EvidenceStatus.SUPERSEDED}
            and self.approved_content_hash is not None
        ):
            raise KnowledgeError(
                "approved_content_hash chi co nghia tren card APPROVED hoac "
                "SUPERSEDED: card chua duyet hoac bi tu choi khong co noi dung "
                "nao da duoc duyet"
            )
        if self.approval_status is EvidenceStatus.APPROVED and not self.approved_by:
            raise KnowledgeError(
                "card APPROVED phai co approved_by: mot the duyet ma khong biet "
                "ai duyet thi khong phai bang chung duyet"
            )
        if (
            self.valid_from is not None
            and self.valid_until is not None
            and self.valid_until <= self.valid_from
        ):
            raise KnowledgeError("valid_until phai sau valid_from")

    @property
    def content_hash(self) -> str:
        """Digest of this card's substance."""
        return content_hash(
            self.claim.unsafe_text(), self.rationale.unsafe_text(), self.source_ref
        )

    def witnessed_approval(self, *, approved_by: str) -> KnowledgeCard:
        """This card, approved, with the digest of what was approved recorded.

        The one operation that may set :attr:`approved_content_hash`, and it
        always sets it from the content in front of it - so the field can never
        be pointed at content nobody read. :meth:`KnowledgeStore.approve` does
        the same thing; this exists so a caller holding a bare card (a test, a
        fake store, a future review UI) does not have to reproduce the digest
        step by hand and get it subtly wrong.
        """
        return replace(
            self,
            approval_status=EvidenceStatus.APPROVED,
            approved_by=approved_by,
            approved_content_hash=self.content_hash,
        )

    def is_valid_at(self, now: float) -> bool:
        if self.valid_from is not None and now < self.valid_from:
            return False
        return not (self.valid_until is not None and now >= self.valid_until)

    @property
    def approval_matches_content(self) -> bool:
        """Whether the approval still witnesses this card's content.

        ``None`` is false, not true. An approved card that never recorded what
        was approved is the state the field exists to detect.
        """
        return (
            self.approved_content_hash is not None
            and self.approved_content_hash == self.content_hash
        )

    def is_retrievable_at(self, now: float) -> bool:
        """Whether this card may be returned as approved knowledge.

        ``approval_matches_content`` is in the conjunction rather than checked
        by callers, so a card edited behind the store's back stops being
        citable everywhere at once - including in the authority gate, which
        receives only :meth:`as_evidence` and cannot see claim text at all.
        """
        return (
            self.approval_status is EvidenceStatus.APPROVED
            and self.approval_matches_content
            and self.superseded_by is None
            and self.card_type.is_citable_as_fact
            and self.is_valid_at(now)
        )

    def as_evidence(self) -> Evidence:
        """The view the authority gate needs: metadata, no claim text."""
        return Evidence(
            evidence_id=self.card_id,
            status=self.approval_status,
            scope=self.scope,
            valid_from=self.valid_from,
            valid_until=self.valid_until,
            superseded_by=self.superseded_by,
        )

    def metadata(self) -> dict[str, object]:
        """Metadata-only view for a log line or the review UI."""
        return {
            "card_id": self.card_id,
            "card_type": self.card_type.value,
            "approval_status": self.approval_status.value,
            "approved_by": self.approved_by,
            "approval_matches_content": self.approval_matches_content,
            "scope": self.scope,
            "sensitivity": self.sensitivity.value,
            "confidence": self.confidence,
            "version": self.version,
            "content_hash": self.content_hash,
            "claim_chars": self.claim.char_count,
            "supersedes": self.supersedes,
            "superseded_by": self.superseded_by,
        }


@dataclass(frozen=True, slots=True)
class Conflict:
    """Two approved cards in one scope whose content differs.

    **Divergence, not contradiction**, and the distinction is load-bearing.
    Measured: a budget card and a deadline card in the same scope - two
    obviously compatible facts - are reported as a pair here, because the test
    is "same type, same scope, different content". This docstring previously
    said "cannot both be current" and "two contradictory positions", which
    claimed far more than the code checks.

    So this is a **review signal for the operator**, not a reason to refuse an
    answer. Refusing on it would reject almost every answer in any scope
    holding more than one card. What refuses an answer is
    :func:`~meetai.answerability.assess`, which compares the full witness set
    and is scoped to the asked-about claim's own subject.

    Reported rather than resolved, which part was always right: deciding which
    of two cards is current is the operator's call.
    """

    first_id: str
    second_id: str
    card_type: str
    scope: str


class DerivedIndex(Protocol):
    """Anything that holds data derived from a card.

    Chunks, embeddings, a retrieval cache. Registered with the store so that
    deletion and edits cascade, rather than every call site having to remember
    which derivatives exist.
    """

    def purge(self, card_id: str) -> int:
        """Drop everything derived from ``card_id``. Returns how many items."""
        ...


@dataclass(frozen=True, slots=True)
class CascadeResult:
    """What a delete or an edit removed. Counts only."""

    card_id: str
    card_removed: bool
    derived_items_purged: int
    indexes_notified: int


@dataclass
class SourceAllowlist:
    """Source references the operator has permitted ingest from.

    Prefix matching on an explicit list. Empty permits nothing, which is the
    point: the handoff document rules out ingesting a whole account or
    repository, so breadth has to be opted into one prefix at a time.
    """

    allowed_prefixes: frozenset[str] = frozenset()

    def permits(self, source_ref: str) -> bool:
        return any(source_ref.startswith(prefix) for prefix in self.allowed_prefixes)


@dataclass
class KnowledgeStore:
    """Cards, their approval state, and the indexes derived from them."""

    now: Callable[[], float]
    source_allowlist: SourceAllowlist = field(default_factory=SourceAllowlist)
    _cards: dict[str, KnowledgeCard] = field(default_factory=dict, repr=False)
    _indexes: list[DerivedIndex] = field(default_factory=list, repr=False)

    # ------------------------------------------------------------------ #
    # Registration
    # ------------------------------------------------------------------ #

    def register_index(self, index: DerivedIndex) -> None:
        """Register a derived index to be cascaded on delete and edit."""
        self._indexes.append(index)

    # ------------------------------------------------------------------ #
    # Queries
    # ------------------------------------------------------------------ #

    def get(self, card_id: str) -> KnowledgeCard | None:
        return self._cards.get(card_id)

    def __len__(self) -> int:
        return len(self._cards)

    def __iter__(self) -> Iterable[KnowledgeCard]:
        return iter(tuple(self._cards.values()))

    def retrieve(
        self,
        *,
        scope: str | None = None,
        card_types: Iterable[CardType] | None = None,
        max_sensitivity: Sensitivity = Sensitivity.PRIVATE,
    ) -> tuple[KnowledgeCard, ...]:
        """Return approved, in-date, unsuperseded cards.

        Approval is filtered first and unconditionally. ``max_sensitivity``
        describes the audience: asking for ``GROUP`` returns group and public
        cards but never private ones, so a private note cannot be relayed into
        a meeting by a caller that forgot to filter.
        """
        moment = self.now()
        permitted = _SENSITIVITY_VISIBILITY[max_sensitivity]
        wanted = None if card_types is None else frozenset(card_types)
        return tuple(
            card
            for card in self._cards.values()
            if card.is_retrievable_at(moment)
            and card.sensitivity in permitted
            and (scope is None or card.scope == scope)
            and (wanted is None or card.card_type in wanted)
        )

    def evidence_for(self, card_ids: Sequence[str]) -> tuple[Evidence, ...]:
        """Metadata views for the authority gate.

        Returns entries for the ids that exist, in request order. Missing ids
        are simply absent, and the gate refuses a citation it cannot resolve -
        which is the right division: the store reports what it has, the gate
        decides what that means.
        """
        return tuple(
            self._cards[card_id].as_evidence()
            for card_id in card_ids
            if card_id in self._cards
        )

    def conflicts(
        self,
        *,
        scope: str | None = None,
        max_sensitivity: Sensitivity = Sensitivity.PRIVATE,
    ) -> tuple[Conflict, ...]:
        """Pairs of retrievable cards in one scope whose content differs.

        **Not "cards that contradict each other"**, which is what this said
        before. Two cards are paired when they share a type and a scope, are
        both retrievable now, and differ in content. A budget and a deadline
        satisfy that - measured - so the output is a **review signal**, never a
        reason to refuse an answer. See :class:`Conflict`.

        ``scope`` narrows the scan, which matters for the only caller: a
        divergence in a scope nobody asked about must not be reported against
        an answer drawn from a different scope.

        ``max_sensitivity`` is there for a sharper reason, and it was measured.
        This method had no sensitivity filter while :meth:`retrieve` does, so a
        ``PRIVATE`` card was paired with a ``GROUP`` one and the pair - which
        names both card ids - was reported to a ``GROUP`` audience. That
        discloses the **existence** of a private card to a path the sensitivity
        filter had deliberately excluded. Any store query used in an answer
        path takes the same audience the retrieval took.

        Superseded, expired, unapproved and digest-mismatched cards are
        excluded, because the filter is :meth:`KnowledgeCard.is_retrievable_at`
        - so a *correction* recorded through ``supersede`` does not read as a
        divergence, which is exactly the point of recording it that way.
        """
        moment = self.now()
        live = sorted(
            (
                c
                for c in self._cards.values()
                if c.is_retrievable_at(moment)
                and c.sensitivity in _SENSITIVITY_VISIBILITY[max_sensitivity]
                and (scope is None or c.scope == scope)
            ),
            key=lambda c: c.card_id,
        )
        found: list[Conflict] = []
        for i, first in enumerate(live):
            for second in live[i + 1 :]:
                if (
                    first.card_type is second.card_type
                    and first.scope == second.scope
                    and first.content_hash != second.content_hash
                ):
                    found.append(
                        Conflict(
                            first_id=first.card_id,
                            second_id=second.card_id,
                            card_type=first.card_type.value,
                            scope=first.scope,
                        )
                    )
        return tuple(found)

    # ------------------------------------------------------------------ #
    # Lifecycle
    # ------------------------------------------------------------------ #

    def ingest(self, card: KnowledgeCard) -> KnowledgeCard:
        """Accept a candidate for review.

        Refuses a card that arrives already approved: approval is an act the
        operator performs through :meth:`approve`, and letting it come in over
        the wire would make the review step optional.
        """
        if not self.source_allowlist.permits(card.source_ref):
            raise IngestRejectedError(
                "source_ref khong nam trong allowlist. Khong ingest toan bo "
                "account/repo/mailbox/calendar; tung nguon phai duoc cho phep rieng."
            )
        if card.approval_status is not EvidenceStatus.CANDIDATE:
            raise KnowledgeError(
                "ingest chi nhan card o trang thai CANDIDATE; duyet la mot hanh "
                "dong rieng cua chu du an"
            )
        if card.card_id in self._cards:
            raise KnowledgeError(f"card_id da ton tai: {card.card_id}")

        duplicate = self._find_duplicate(card)
        if duplicate is not None:
            raise KnowledgeError(
                f"trung noi dung voi card da co ({duplicate.card_id}); "
                "sua card cu hoac dung supersede thay vi tao ban moi"
            )

        self._cards[card.card_id] = card
        return card

    def approve(self, card_id: str, *, approved_by: str) -> KnowledgeCard:
        """Approve a candidate. Only then is it retrievable.

        ``approved_by`` is required, and a rejected card cannot be approved: a
        reversal should be an explicit new review, not a second call that
        happens to win.
        """
        card = self._require(card_id)
        if card.approval_status is EvidenceStatus.REJECTED:
            raise KnowledgeError(
                "card da REJECTED; tao ban moi va review lai thay vi duyet lai"
            )
        if card.approval_status is EvidenceStatus.SUPERSEDED:
            raise KnowledgeError("card da bi supersede, khong duyet lai duoc")
        updated = replace(
            card,
            approval_status=EvidenceStatus.APPROVED,
            approved_by=approved_by,
            approved_content_hash=card.content_hash,
        )
        self._cards[card_id] = updated
        return updated

    def reject(self, card_id: str) -> KnowledgeCard:
        """Reject a card and purge anything derived from it."""
        card = self._require(card_id)
        updated = replace(
            card,
            approval_status=EvidenceStatus.REJECTED,
            approved_content_hash=None,
        )
        self._cards[card_id] = updated
        self._cascade(card_id)
        return updated

    def edit(
        self,
        card_id: str,
        *,
        claim: MeetingContent | None = None,
        rationale: MeetingContent | None = None,
        scope: str | None = None,
        sensitivity: Sensitivity | None = None,
        valid_until: float | None = None,
    ) -> KnowledgeCard:
        """Change a card's content, returning it to review.

        Editing an approved card **revokes its approval** and bumps the
        version. The alternative - an edited card keeping its approval - would
        mean the operator approved text they never saw, which is the quiet way
        a review step stops meaning anything.

        Derived indexes are purged, because they describe the old content.
        """
        card = self._require(card_id)
        updated = replace(
            card,
            claim=card.claim if claim is None else claim,
            rationale=card.rationale if rationale is None else rationale,
            scope=card.scope if scope is None else scope,
            sensitivity=card.sensitivity if sensitivity is None else sensitivity,
            valid_until=card.valid_until if valid_until is None else valid_until,
            approval_status=EvidenceStatus.CANDIDATE,
            approved_by=None,
            approved_content_hash=None,
            version=card.version + 1,
        )
        self._cards[card_id] = updated
        self._cascade(card_id)
        return updated

    def supersede(self, old_id: str, new_card: KnowledgeCard) -> KnowledgeCard:
        """Replace a card with a newer one.

        The old card is marked superseded rather than deleted, so a past
        citation can still be explained, and its derivatives are purged so it
        stops being retrieved. The new card arrives as a candidate and needs
        its own approval.
        """
        old = self._require(old_id)
        if new_card.card_id == old_id:
            raise KnowledgeError("card moi phai co card_id khac card bi thay the")
        incoming = replace(new_card, supersedes=old_id)
        self.ingest(incoming)
        self._cards[old_id] = replace(
            old,
            approval_status=EvidenceStatus.SUPERSEDED,
            superseded_by=new_card.card_id,
        )
        self._cascade(old_id)
        return incoming

    def delete(self, card_id: str) -> CascadeResult:
        """Remove a card and everything derived from it.

        Deleting the row and leaving the embeddings is what makes a retention
        promise false, so the cascade is part of the operation rather than a
        follow-up somebody has to remember.
        """
        existed = self._cards.pop(card_id, None) is not None
        purged, notified = self._purge_derived(card_id)
        return CascadeResult(
            card_id=card_id,
            card_removed=existed,
            derived_items_purged=purged,
            indexes_notified=notified,
        )

    def purge_scope(self, scope: str) -> tuple[CascadeResult, ...]:
        """Delete every card in a scope. What a retention policy calls."""
        targets = [c.card_id for c in tuple(self._cards.values()) if c.scope == scope]
        return tuple(self.delete(card_id) for card_id in targets)

    # ------------------------------------------------------------------ #
    # Internals
    # ------------------------------------------------------------------ #

    def _require(self, card_id: str) -> KnowledgeCard:
        card = self._cards.get(card_id)
        if card is None:
            raise KnowledgeError(f"khong co card: {card_id}")
        return card

    def _find_duplicate(self, card: KnowledgeCard) -> KnowledgeCard | None:
        target = card.content_hash
        for existing in self._cards.values():
            if existing.content_hash == target:
                return existing
        return None

    def _cascade(self, card_id: str) -> CascadeResult:
        purged, notified = self._purge_derived(card_id)
        return CascadeResult(
            card_id=card_id,
            card_removed=False,
            derived_items_purged=purged,
            indexes_notified=notified,
        )

    def _purge_derived(self, card_id: str) -> tuple[int, int]:
        """Purge every registered index.

        One index failing must not stop the others: leaving embeddings behind
        because a cache was unreachable is the failure that makes a retention
        promise false. So every index gets its turn, and *then* the failures
        are reported - a caller must not be able to mistake a partial purge
        for a complete one, which is why this raises rather than returning a
        count and a warning.

        Failure messages name the index type, never the card's content.
        """
        purged = 0
        failures: list[str] = []
        for index in self._indexes:
            try:
                purged += index.purge(card_id)
            except Exception as exc:  # every index must get its turn
                failures.append(f"{type(index).__name__}:{type(exc).__name__}")
        if failures:
            raise KnowledgeError(
                f"purge index that bai cho card {card_id} "
                f"({len(failures)}/{len(self._indexes)}): " + ", ".join(failures)
            )
        return purged, len(self._indexes)


_SENSITIVITY_VISIBILITY: dict[Sensitivity, frozenset[Sensitivity]] = {
    Sensitivity.PUBLIC: frozenset({Sensitivity.PUBLIC}),
    Sensitivity.GROUP: frozenset({Sensitivity.PUBLIC, Sensitivity.GROUP}),
    Sensitivity.PRIVATE: frozenset(Sensitivity),
}
"""What each audience may see.

Asking for a narrower audience returns strictly less. Written as explicit sets
rather than an ordering comparison, because an ordering invites
``>=`` and a sign error in that comparison leaks a private card.
"""
