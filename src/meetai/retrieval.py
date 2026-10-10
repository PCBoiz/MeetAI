"""Find the cards a question might be answered from (pipeline step 4).

**The one thing this module exists to get right.** Retrieval is where a
narrowing step enters the pipeline, and a narrowing step is how a verified
refusal becomes a delivered answer. Measured, before any of this was written:

    full scope      cards=2  delivered=False  CONFLICTING  cards_disagree:time
    top-1 only      cards=1  delivered=True   SUPPORTED    rules=()

Two approved cards disagreeing about the same deadline. Hand
:func:`~meetai.answerability.assess` both and it refuses; hand it the ranked
best one and it answers. Nothing in ``answerability`` is wrong there - its
conflict check looks at the cards it is **given**, and its own comment calls
citing one of two disagreeing cards "selective citation", the thing it was
built to prevent. A ranked retrieval step does that narrowing on the model's
behalf and makes it look like relevance.

So this module returns **two** sets and keeps them apart by type:

``candidates``
    Ranked, possibly truncated. The cards a model may choose citations from.
    This is retrieval's legitimate job and the only thing ranking affects.

``witnesses``
    **Never truncated.** Every retrievable card in the store, handed to
    ``assess`` as its ``cards`` argument. ``assess`` already scopes conflict
    detection to the claim's own subject, so passing everything costs nothing
    in precision and is the only version that cannot hide a disagreement.

A structural invariant holds the two together: ``candidates`` is always a
subset of ``witnesses``, asserted at construction. Truncating ``witnesses``
makes a conflict test fail, which is how a future author finds out.

**Ranking is not evidence, and this module cannot make it look like evidence.**
A score orders ``candidates`` and reaches nothing else. Every claim still needs
its ``evidence_id`` to resolve to a retrievable card and still passes
answerability and the authority gate. There is no threshold above which a card
counts as support, because there is no quantity here that could mean support.

**Metadata and lexical only.** Spec ``K-8`` records embeddings as deliberately
``absent`` - they are added only if a benchmark on an eval set the operator
controls shows an improvement - and the handoff document says to start with
"metadata + exact/lexical retrieval". So the score is folded-token overlap and
nothing else: no vector store, no index, no model, no network, no persistence.

**Why it reuses ``answerability``'s tokeniser rather than writing one.** If
retrieval decided "about the same thing" differently from the layer that
verifies support, the two would disagree about which cards are on-subject, and
the disagreement would surface as cards ranked first and then refused. Sharing
``subject_tokens`` also inherits its hard-won exclusions: values are stripped,
so a card cannot rank highly for sharing a number; ``_UNITS`` is excluded, so
``dong`` and ``trieu`` cannot make an unrelated card look relevant - the same
collision that once defeated the substitution check outright.

Framework-free, and it reads the store through :meth:`KnowledgeStore.retrieve`
only. That method is where approval, the approved-content digest, supersession,
validity and sensitivity are enforced, and re-implementing any of those here
would be a second place for them to drift.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from meetai.answerability import evidential_text, subject_tokens
from meetai.content import MeetingContent
from meetai.knowledge import CardType, KnowledgeCard, KnowledgeStore, Sensitivity


@dataclass(frozen=True, slots=True)
class ScoredCard:
    """One candidate and why it ranked where it did.

    ``overlap`` is the shared subject tokens, kept so a report can say *which*
    words matched rather than printing a number nobody can check. The tokens
    are diacritic-folded content words from a synthetic or operator-supplied
    card, and they are **shape**, not the card's text - but they are still
    derived from content, so ``card`` is excluded from the repr and the class
    prints counts only.
    """

    card: KnowledgeCard = field(repr=False)
    overlap: frozenset[str] = field(default_factory=frozenset, repr=False)

    @property
    def score(self) -> int:
        """How many subject words this card shares with the question.

        An integer count, not a normalised relevance. A fraction would invite a
        threshold, and a threshold is the shape of a thing that looks like
        evidence. Nothing in this project may read a number here and conclude
        that a claim is supported.
        """
        return len(self.overlap)

    def __repr__(self) -> str:
        return f"ScoredCard(card_id={self.card.card_id!r}, score={self.score})"


@dataclass(frozen=True, slots=True)
class RetrievalResult:
    """What a question found: cards to cite from, and cards that must be seen.

    The two tuples answer different questions and must not be merged. See the
    module docstring for the measurement that forced the split.
    """

    query_tokens: frozenset[str] = field(repr=False)
    candidates: tuple[ScoredCard, ...] = ()
    witnesses: tuple[KnowledgeCard, ...] = field(default=(), repr=False)
    divergent_pairs: tuple[tuple[str, str], ...] = ()
    """Card-id pairs in this scope whose content differs.

    A **review signal for the operator**, and it refuses nothing.
    :meth:`KnowledgeStore.conflicts` pairs any two retrievable cards of
    one type and scope whose content differs - measured: a budget and a
    deadline qualify - so treating it as a refusal would reject nearly
    every answer in a scope holding more than one card.

    What refuses an answer is
    :func:`~meetai.answerability.assess` over the full witness set,
    which is witness-wide and scoped to the claim's own subject. This
    field exists so that an operator reading a dry-run can see the
    store needs attention, not so that anything branches on it.
    """
    scope: str = ""
    """The body of knowledge that was allowed to answer.

    Recorded because it is the one parameter that decides what *could* have
    been found, and a finding has to be reproducible from it. Nothing below
    this module binds scope to an answer, so an outcome that did not say which
    scope it searched would not be re-checkable at all.
    """
    truncated: bool = False
    """Whether ``candidates`` was cut by ``max_candidates``.

    Recorded because a truncated candidate list is a fact about what the model
    was shown, and a report that hid it would make a missing citation look
    like a choice the model made.
    """

    def __post_init__(self) -> None:
        witness_ids = {card.card_id for card in self.witnesses}
        stray = [
            scored.card.card_id
            for scored in self.candidates
            if scored.card.card_id not in witness_ids
        ]
        if stray:
            # Not tidiness. A candidate outside the witness set is a card the
            # model may cite while the conflict check cannot see it, which is
            # exactly the narrowing this module exists to prevent.
            raise ValueError(
                f"candidate khong nam trong witness set: {len(stray)} card. "
                "Moi card co the duoc dan phai nam trong tap witness, neu "
                "khong thi phep kiem mau thuan khong thay no."
            )

    @property
    def candidate_ids(self) -> tuple[str, ...]:
        return tuple(scored.card.card_id for scored in self.candidates)

    def metadata(self) -> dict[str, object]:
        """Metadata-only view. No card text, no question text.

        ``candidates`` is reported as ids and scores so a finding stays
        re-checkable against a specific card, which is the project's rule for
        every finding: a rank or a score alone is not something an operator can
        go and look at.
        """
        return {
            "scope": self.scope,
            "divergent_pairs": [list(pair) for pair in self.divergent_pairs],
            "divergence_is_a_review_signal_not_a_refusal": True,
            "query_token_count": len(self.query_tokens),
            "candidate_count": len(self.candidates),
            "witness_count": len(self.witnesses),
            "truncated": self.truncated,
            "candidates": [
                {"card_id": scored.card.card_id, "score": scored.score}
                for scored in self.candidates
            ],
        }


def retrieve_for_question(
    question: MeetingContent,
    store: KnowledgeStore,
    *,
    scope: str,
    max_sensitivity: Sensitivity,
    max_candidates: int | None = None,
    card_types: tuple[CardType, ...] | None = None,
) -> RetrievalResult:
    """Cards this question might be answered from, plus every possible witness.

    ``scope`` and ``max_sensitivity`` are **required and have no defaults**,
    and both of those are deliberate.

    ``scope`` comes from the **session**, never from the question, because
    there is no safe lexical path from a question to a scope. No layer below
    this one binds scope to an answer - ``assess`` has no ``scope`` parameter
    and ``Evidence.scope`` is consumed by nothing - so whoever calls this is
    the only thing deciding which body of knowledge may answer. Measured:
    "Chi phi ha tang la bao nhieu?", naming no project, is answered from
    another project's card and delivered as ``SUPPORTED``. Making ``scope``
    required does not fix that, and is not claimed to; it means the operator
    chose the body of knowledge rather than a token overlap choosing it.

    ``max_sensitivity`` is required for a blunter reason: it is enforced
    **only** here, in :meth:`KnowledgeStore.retrieve`, and re-checked nowhere.
    ``Sensitivity`` appears zero times in ``answerability.py``,
    ``authority.py`` and ``boundary.py``. A default would be a permissive
    default with nothing downstream to catch it, which is the shape of every
    fail-open bug this project has recorded.

    ``max_candidates`` truncates **only** ``candidates``. There is deliberately
    no parameter that truncates ``witnesses``: the argument for ranking is that
    a model should not be shown fifty cards, and that argument says nothing
    about what the verifier is allowed to check.

    Scoring runs on :func:`~meetai.answerability.evidential_text`, not on the
    raw claim, so the two layers agree on what a card's words are. Measured:
    appending an imperative sentence to a card moved its raw overlap from 7 to
    8 while its evidential overlap stayed at 7. The imperative cannot
    manufacture evidence - answerability strips it - but 7 to 8 is enough to
    win a top-1 cut, so scoring raw text would let anyone who can write one
    line into a note choose which of two approved cards gets spoken.

    **There is deliberately no ``now`` parameter.** There was one, it was
    required, and nothing in the body ever read it - the retrieval moment comes
    from the store's own clock through :meth:`KnowledgeStore.retrieve`. A dead
    parameter named ``now`` is worse than none: a validity or expiry test
    written through it would silently assert nothing, and it had never bitten
    only because the dry-run pins the store's clock to the same value.

    Ordering is by descending score then ``card_id``, so a dry-run is
    reproducible. Ties broken by insertion order would make the report depend
    on which order cards happened to be ingested.
    """
    retrievable = store.retrieve(
        scope=scope, card_types=card_types, max_sensitivity=max_sensitivity
    )
    # Surfaced, never branched on. Scoped, so a divergence somewhere
    # nobody asked about is not reported against this answer.
    divergent = tuple(
        (pair.first_id, pair.second_id)
        for pair in store.conflicts(scope=scope, max_sensitivity=max_sensitivity)
    )
    tokens = subject_tokens(question.unsafe_text())

    scored = [
        ScoredCard(card=card, overlap=overlap)
        for card in retrievable
        if (overlap := tokens & subject_tokens(evidential_text(card.claim.unsafe_text())))
    ]
    scored.sort(key=lambda item: (-item.score, item.card.card_id))

    truncated = max_candidates is not None and len(scored) > max_candidates
    kept = tuple(scored if max_candidates is None else scored[:max_candidates])

    return RetrievalResult(
        query_tokens=tokens,
        candidates=kept,
        witnesses=retrievable,
        divergent_pairs=divergent,
        scope=scope,
        truncated=truncated,
    )


def witnesses_for(result: RetrievalResult) -> tuple[KnowledgeCard, ...]:
    """The tuple to pass as ``assess(cards=...)``.

    A named accessor rather than letting a caller reach for whichever field
    looks right. ``candidates`` is the one that looks right - it is the ranked,
    relevant-looking list - and passing it is the bug this module was written
    to make hard. Going through a function means the mistake has a name and a
    test can look for its absence.
    """
    return result.witnesses


__all__ = [
    "RetrievalResult",
    "ScoredCard",
    "retrieve_for_question",
    "witnesses_for",
]
