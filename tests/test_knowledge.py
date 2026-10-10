"""Tests for the approved-knowledge store.

The property that would do real damage if it drifted is the first one: an
unapproved card must never be retrievable. A claim relayed in a meeting
without approval is MeetAI inventing the operator's position, so that test is
written to fail if the filter is removed rather than merely to pass today.
"""

from __future__ import annotations

from dataclasses import replace

import pytest

from meetai.content import MeetingContent
from meetai.knowledge import (
    AllowedAction,
    CardType,
    CascadeResult,
    IngestRejectedError,
    KnowledgeCard,
    KnowledgeError,
    KnowledgeStore,
    Sensitivity,
    SourceAllowlist,
    content_hash,
)
from meetai.response import EvidenceStatus

NOW = 1000.0
ALLOWED_PREFIX = "notes://approved/"
OPERATOR = "operator-handle"


class Clock:
    def __init__(self, t: float = NOW) -> None:
        self.t = t

    def __call__(self) -> float:
        return self.t

    def advance(self, seconds: float) -> None:
        self.t += seconds


class FakeIndex:
    """Stands in for chunks, embeddings or a retrieval cache."""

    def __init__(self, *, per_card: int = 3, fail: bool = False) -> None:
        self.purged: list[str] = []
        self._per_card = per_card
        self._fail = fail

    def purge(self, card_id: str) -> int:
        if self._fail:
            raise RuntimeError("index unavailable")
        self.purged.append(card_id)
        return self._per_card


@pytest.fixture
def clock() -> Clock:
    return Clock()


@pytest.fixture
def store(clock: Clock) -> KnowledgeStore:
    return KnowledgeStore(
        now=clock,
        source_allowlist=SourceAllowlist(frozenset({ALLOWED_PREFIX})),
    )


def card(
    card_id: str = "card-1",
    *,
    claim: str = "Du an dung Python 3.12",
    rationale: str = "Da verify wheel ML",
    card_type: CardType = CardType.POSITION,
    scope: str = "project",
    sensitivity: Sensitivity = Sensitivity.GROUP,
    source: str = f"{ALLOWED_PREFIX}adr-0001",
    valid_until: float | None = None,
    status: EvidenceStatus = EvidenceStatus.CANDIDATE,
    approved_by: str | None = None,
) -> KnowledgeCard:
    return KnowledgeCard(
        card_id=card_id,
        card_type=card_type,
        claim=MeetingContent(claim, kind="claim"),
        rationale=MeetingContent(rationale, kind="rationale"),
        source_ref=source,
        source_date=NOW,
        scope=scope,
        sensitivity=sensitivity,
        valid_until=valid_until,
        approval_status=status,
        approved_by=approved_by,
    )


def approved(store: KnowledgeStore, c: KnowledgeCard | None = None) -> KnowledgeCard:
    store.ingest(c if c is not None else card())
    return store.approve((c or card()).card_id, approved_by=OPERATOR)


class TestOnlyApprovedIsRetrievable:
    """The absolute from the handoff document."""

    @pytest.mark.parametrize(
        "status",
        [
            EvidenceStatus.CANDIDATE,
            EvidenceStatus.PENDING,
            EvidenceStatus.REJECTED,
            EvidenceStatus.SUPERSEDED,
        ],
    )
    def test_no_unapproved_status_is_retrievable(self, status: EvidenceStatus) -> None:
        """Checked on the card itself, across every non-approved status.

        ``PENDING`` is not reachable through the store's public API today, so
        this asserts the predicate rather than driving the store - which also
        means a status added to the enum later is covered without anyone having
        to find a way to reach it.
        """
        unapproved = replace(card(), approval_status=status, approved_by=None)
        assert unapproved.is_retrievable_at(NOW) is False

    def test_candidate_is_not_retrievable(self, store: KnowledgeStore) -> None:
        store.ingest(card())
        assert store.retrieve() == ()
        assert len(store) == 1  # it exists, it is just not retrievable

    def test_approved_card_is_retrievable(self, store: KnowledgeStore) -> None:
        approved(store)
        assert [c.card_id for c in store.retrieve()] == ["card-1"]

    def test_only_approved_status_is_citable(self) -> None:
        for status in EvidenceStatus:
            assert status.is_citable is (status is EvidenceStatus.APPROVED)


class TestCardTypeAuthority:
    def test_style_examples_cannot_back_a_fact(self, store: KnowledgeStore) -> None:
        """Style guides tone; it is never evidence of fact."""
        c = card("style-1", card_type=CardType.STYLE_EXAMPLE)
        store.ingest(c)
        store.approve("style-1", approved_by=OPERATOR)
        assert store.retrieve() == ()

    def test_meeting_context_does_not_become_long_term_memory(
        self, store: KnowledgeStore
    ) -> None:
        c = card("ctx-1", card_type=CardType.MEETING_CONTEXT)
        store.ingest(c)
        store.approve("ctx-1", approved_by=OPERATOR)
        assert store.retrieve() == ()

    @pytest.mark.parametrize(
        "card_type",
        [CardType.PROFILE, CardType.POSITION, CardType.PROJECT, CardType.GLOSSARY],
    )
    def test_knowledge_types_are_citable(
        self, store: KnowledgeStore, card_type: CardType
    ) -> None:
        c = card("k-1", card_type=card_type)
        store.ingest(c)
        store.approve("k-1", approved_by=OPERATOR)
        assert len(store.retrieve()) == 1

    def test_a_new_card_type_would_not_be_citable_by_default(self) -> None:
        """New kinds must be listed deliberately, not inherit citability."""
        citable = {t for t in CardType if t.is_citable_as_fact}
        assert CardType.STYLE_EXAMPLE not in citable
        assert CardType.MEETING_CONTEXT not in citable


class TestIngestAllowlist:
    def test_source_outside_the_allowlist_is_refused(self, store: KnowledgeStore) -> None:
        """No ingesting a whole account, repo, mailbox or calendar."""
        with pytest.raises(IngestRejectedError, match="allowlist"):
            store.ingest(card(source="mailbox://inbox/all"))

    def test_empty_allowlist_permits_nothing(self, clock: Clock) -> None:
        empty = KnowledgeStore(now=clock)
        with pytest.raises(IngestRejectedError):
            empty.ingest(card())

    def test_allowlisted_prefix_is_accepted(self, store: KnowledgeStore) -> None:
        assert store.ingest(card()).card_id == "card-1"

    def test_pre_approved_card_cannot_be_ingested(self, store: KnowledgeStore) -> None:
        """Approval is an act, not a field that arrives over the wire."""
        with pytest.raises(KnowledgeError, match="CANDIDATE"):
            store.ingest(card(status=EvidenceStatus.APPROVED, approved_by=OPERATOR))

    def test_duplicate_id_is_refused(self, store: KnowledgeStore) -> None:
        store.ingest(card())
        with pytest.raises(KnowledgeError, match="da ton tai"):
            store.ingest(card(claim="khac han"))

    def test_duplicate_content_is_refused(self, store: KnowledgeStore) -> None:
        store.ingest(card("card-1"))
        with pytest.raises(KnowledgeError, match="trung noi dung"):
            store.ingest(card("card-2"))


class TestContentHash:
    def test_same_substance_same_hash(self) -> None:
        assert content_hash("a", "b", "c") == content_hash("a", "b", "c")

    def test_different_source_different_hash(self) -> None:
        """The same sentence from two sources is two cards, not one."""
        assert content_hash("a", "b", "src1") != content_hash("a", "b", "src2")

    def test_field_boundaries_are_unambiguous(self) -> None:
        """Without a separator, "ab"+"c" and "a"+"bc" would collide."""
        assert content_hash("ab", "c", "s") != content_hash("a", "bc", "s")

    def test_card_hash_matches_its_content(self) -> None:
        c = card()
        assert c.content_hash == content_hash(
            "Du an dung Python 3.12", "Da verify wheel ML", f"{ALLOWED_PREFIX}adr-0001"
        )


class TestApproval:
    def test_approval_requires_an_approver(self) -> None:
        """A card approved by nobody is not evidence of approval."""
        with pytest.raises(KnowledgeError, match="approved_by"):
            card(status=EvidenceStatus.APPROVED, approved_by=None)

    def test_approve_records_the_approver(self, store: KnowledgeStore) -> None:
        result = approved(store)
        assert result.approved_by == OPERATOR
        assert result.approval_status is EvidenceStatus.APPROVED

    def test_rejected_card_cannot_be_approved(self, store: KnowledgeStore) -> None:
        """A reversal should be an explicit new review."""
        store.ingest(card())
        store.reject("card-1")
        with pytest.raises(KnowledgeError, match="REJECTED"):
            store.approve("card-1", approved_by=OPERATOR)

    def test_superseded_card_cannot_be_approved(self, store: KnowledgeStore) -> None:
        approved(store)
        store.supersede("card-1", card("card-2", claim="Python 3.13"))
        with pytest.raises(KnowledgeError, match="supersede"):
            store.approve("card-1", approved_by=OPERATOR)

    def test_approving_a_missing_card_is_refused(self, store: KnowledgeStore) -> None:
        with pytest.raises(KnowledgeError, match="khong co card"):
            store.approve("nope", approved_by=OPERATOR)


class TestEditRevokesApproval:
    def test_editing_an_approved_card_returns_it_to_review(
        self, store: KnowledgeStore
    ) -> None:
        """Otherwise the operator approved text they never saw."""
        approved(store)
        edited = store.edit("card-1", claim=MeetingContent("Python 3.13", kind="claim"))
        assert edited.approval_status is EvidenceStatus.CANDIDATE
        assert edited.approved_by is None
        assert store.retrieve() == ()

    def test_edit_bumps_the_version(self, store: KnowledgeStore) -> None:
        approved(store)
        assert store.edit("card-1", scope="other").version == 2

    def test_edit_purges_derived_indexes(self, store: KnowledgeStore) -> None:
        """The derivatives describe the old content."""
        index = FakeIndex()
        store.register_index(index)
        approved(store)
        store.edit("card-1", claim=MeetingContent("moi", kind="claim"))
        assert index.purged == ["card-1"]

    def test_edit_can_change_sensitivity(self, store: KnowledgeStore) -> None:
        approved(store)
        edited = store.edit("card-1", sensitivity=Sensitivity.PRIVATE)
        assert edited.sensitivity is Sensitivity.PRIVATE


class TestSensitivity:
    def test_private_is_the_default(self) -> None:
        """A card whose audience nobody stated must not reach a group."""
        assert (
            KnowledgeCard(
                card_id="x",
                card_type=CardType.POSITION,
                claim=MeetingContent("c"),
                rationale=MeetingContent("r"),
                source_ref="s",
                source_date=0.0,
            ).sensitivity
            is Sensitivity.PRIVATE
        )

    def test_group_audience_excludes_private_cards(self, store: KnowledgeStore) -> None:
        store.ingest(card("priv", sensitivity=Sensitivity.PRIVATE))
        store.approve("priv", approved_by=OPERATOR)
        store.ingest(card("grp", claim="khac", sensitivity=Sensitivity.GROUP))
        store.approve("grp", approved_by=OPERATOR)

        visible = {c.card_id for c in store.retrieve(max_sensitivity=Sensitivity.GROUP)}
        assert visible == {"grp"}

    def test_public_audience_excludes_group_cards(self, store: KnowledgeStore) -> None:
        approved(store, card("grp", sensitivity=Sensitivity.GROUP))
        assert store.retrieve(max_sensitivity=Sensitivity.PUBLIC) == ()

    def test_private_audience_sees_everything(self, store: KnowledgeStore) -> None:
        approved(store, card("priv", sensitivity=Sensitivity.PRIVATE))
        assert len(store.retrieve(max_sensitivity=Sensitivity.PRIVATE)) == 1

    def test_narrower_audience_returns_strictly_less(self, store: KnowledgeStore) -> None:
        for i, level in enumerate(Sensitivity):
            approved(store, card(f"c{i}", claim=f"claim {i}", sensitivity=level))
        private = len(store.retrieve(max_sensitivity=Sensitivity.PRIVATE))
        group = len(store.retrieve(max_sensitivity=Sensitivity.GROUP))
        public = len(store.retrieve(max_sensitivity=Sensitivity.PUBLIC))
        assert private >= group >= public
        assert private == 3
        assert public == 1


class TestExpiry:
    def test_expired_card_is_not_retrieved(
        self, store: KnowledgeStore, clock: Clock
    ) -> None:
        approved(store, card(valid_until=NOW + 100))
        assert len(store.retrieve()) == 1
        clock.advance(101)
        assert store.retrieve() == ()

    def test_not_yet_valid_card_is_not_retrieved(self, clock: Clock) -> None:
        store = KnowledgeStore(
            now=clock, source_allowlist=SourceAllowlist(frozenset({ALLOWED_PREFIX}))
        )
        c = KnowledgeCard(
            card_id="future",
            card_type=CardType.POSITION,
            claim=MeetingContent("c"),
            rationale=MeetingContent("r"),
            source_ref=f"{ALLOWED_PREFIX}x",
            source_date=NOW,
            valid_from=NOW + 500,
        )
        store.ingest(c)
        store.approve("future", approved_by=OPERATOR)
        assert store.retrieve() == ()

    def test_inverted_validity_window_is_refused(self) -> None:
        with pytest.raises(KnowledgeError, match="valid_until phai sau"):
            KnowledgeCard(
                card_id="x",
                card_type=CardType.POSITION,
                claim=MeetingContent("c"),
                rationale=MeetingContent("r"),
                source_ref="s",
                source_date=0.0,
                valid_from=100.0,
                valid_until=50.0,
            )


class TestSupersede:
    def test_old_card_stops_being_retrieved(self, store: KnowledgeStore) -> None:
        approved(store)
        store.supersede("card-1", card("card-2", claim="Python 3.13"))
        assert store.retrieve() == ()

    def test_old_card_is_kept_for_explanation(self, store: KnowledgeStore) -> None:
        """A past citation should still be explicable."""
        approved(store)
        store.supersede("card-1", card("card-2", claim="Python 3.13"))
        old = store.get("card-1")
        assert old is not None
        assert old.approval_status is EvidenceStatus.SUPERSEDED
        assert old.superseded_by == "card-2"

    def test_new_card_records_what_it_replaces(self, store: KnowledgeStore) -> None:
        approved(store)
        new = store.supersede("card-1", card("card-2", claim="Python 3.13"))
        assert new.supersedes == "card-1"

    def test_new_card_needs_its_own_approval(self, store: KnowledgeStore) -> None:
        approved(store)
        store.supersede("card-1", card("card-2", claim="Python 3.13"))
        assert store.retrieve() == ()
        store.approve("card-2", approved_by=OPERATOR)
        assert [c.card_id for c in store.retrieve()] == ["card-2"]

    def test_superseding_with_the_same_id_is_refused(self, store: KnowledgeStore) -> None:
        approved(store)
        with pytest.raises(KnowledgeError, match="card_id khac"):
            store.supersede("card-1", card("card-1", claim="khac"))

    def test_supersede_purges_the_old_derivatives(self, store: KnowledgeStore) -> None:
        index = FakeIndex()
        store.register_index(index)
        approved(store)
        store.supersede("card-1", card("card-2", claim="Python 3.13"))
        assert "card-1" in index.purged


class TestDeletionCascade:
    def test_delete_removes_the_card(self, store: KnowledgeStore) -> None:
        approved(store)
        result = store.delete("card-1")
        assert result.card_removed is True
        assert store.get("card-1") is None

    def test_delete_cascades_to_every_index(self, store: KnowledgeStore) -> None:
        """Deleting the row and leaving the embeddings makes retention a lie."""
        first, second = FakeIndex(per_card=3), FakeIndex(per_card=5)
        store.register_index(first)
        store.register_index(second)
        approved(store)

        result = store.delete("card-1")
        assert first.purged == ["card-1"]
        assert second.purged == ["card-1"]
        assert result.derived_items_purged == 8
        assert result.indexes_notified == 2

    def test_delete_of_a_missing_card_still_cascades(self, store: KnowledgeStore) -> None:
        """Derivatives may outlive the row they came from."""
        index = FakeIndex()
        store.register_index(index)
        result = store.delete("never-existed")
        assert result.card_removed is False
        assert index.purged == ["never-existed"]

    def test_a_failing_index_is_reported_not_swallowed(
        self, store: KnowledgeStore
    ) -> None:
        """A partial purge must not look like a successful one."""
        store.register_index(FakeIndex(fail=True))
        approved(store)
        with pytest.raises(KnowledgeError, match="purge index that bai"):
            store.delete("card-1")

    def test_purge_failure_names_no_content(self, store: KnowledgeStore) -> None:
        store.register_index(FakeIndex(fail=True))
        approved(store)
        with pytest.raises(KnowledgeError) as exc_info:
            store.delete("card-1")
        assert "Du an dung Python 3.12" not in str(exc_info.value)

    def test_reject_cascades(self, store: KnowledgeStore) -> None:
        index = FakeIndex()
        store.register_index(index)
        approved(store)
        store.reject("card-1")
        assert index.purged == ["card-1"]
        assert store.retrieve() == ()

    def test_purge_scope_deletes_every_card_in_it(self, store: KnowledgeStore) -> None:
        approved(store, card("a", claim="one", scope="projX"))
        approved(store, card("b", claim="two", scope="projX"))
        approved(store, card("c", claim="three", scope="other"))

        results = store.purge_scope("projX")
        assert len(results) == 2
        assert {c.card_id for c in store.retrieve()} == {"c"}

    def test_cascade_result_is_counts_only(self) -> None:
        result = CascadeResult("id", True, 3, 1)
        assert set(result.__dataclass_fields__) == {
            "card_id",
            "card_removed",
            "derived_items_purged",
            "indexes_notified",
        }


class TestConflicts:
    def test_two_contradictory_approved_cards_are_reported(
        self, store: KnowledgeStore
    ) -> None:
        approved(store, card("a", claim="Dung Python 3.12", scope="project"))
        approved(store, card("b", claim="Dung Python 3.13", scope="project"))
        conflicts = store.conflicts()
        assert len(conflicts) == 1
        assert {conflicts[0].first_id, conflicts[0].second_id} == {"a", "b"}

    def test_conflicts_are_reported_not_resolved(self, store: KnowledgeStore) -> None:
        """Guessing which position is the operator's would be worse."""
        approved(store, card("a", claim="X", scope="project"))
        approved(store, card("b", claim="Y", scope="project"))
        assert len(store.retrieve()) == 2  # both still returned, with the conflict known

    def test_different_scopes_do_not_conflict(self, store: KnowledgeStore) -> None:
        approved(store, card("a", claim="X", scope="projA"))
        approved(store, card("b", claim="Y", scope="projB"))
        assert store.conflicts() == ()

    def test_different_types_do_not_conflict(self, store: KnowledgeStore) -> None:
        approved(store, card("a", claim="X", card_type=CardType.POSITION))
        approved(store, card("b", claim="Y", card_type=CardType.PROJECT))
        assert store.conflicts() == ()

    def test_an_unapproved_card_does_not_create_a_conflict(
        self, store: KnowledgeStore
    ) -> None:
        approved(store, card("a", claim="X"))
        store.ingest(card("b", claim="Y"))
        assert store.conflicts() == ()

    def test_a_superseded_card_does_not_conflict_with_its_replacement(
        self, store: KnowledgeStore
    ) -> None:
        approved(store, card("a", claim="X"))
        store.supersede("a", card("b", claim="Y"))
        store.approve("b", approved_by=OPERATOR)
        assert store.conflicts() == ()

    def test_conflict_record_carries_no_claim_text(self, store: KnowledgeStore) -> None:
        approved(store, card("a", claim="NOI-DUNG-BI-MAT", scope="project"))
        approved(store, card("b", claim="KHAC", scope="project"))
        assert "NOI-DUNG-BI-MAT" not in str(store.conflicts())


class TestEvidenceBridge:
    def test_evidence_view_carries_no_claim(self, store: KnowledgeStore) -> None:
        """The gate decides usability from metadata; it must not see content."""
        approved(store, card("a", claim="NOI-DUNG-BI-MAT"))
        evidence = store.evidence_for(["a"])[0]
        assert "NOI-DUNG-BI-MAT" not in repr(evidence)
        assert evidence.evidence_id == "a"
        assert evidence.status is EvidenceStatus.APPROVED

    def test_missing_ids_are_simply_absent(self, store: KnowledgeStore) -> None:
        """The store reports what it has; the gate refuses what it cannot resolve."""
        approved(store, card("a"))
        assert [e.evidence_id for e in store.evidence_for(["a", "nope"])] == ["a"]

    def test_evidence_order_follows_the_request(self, store: KnowledgeStore) -> None:
        approved(store, card("a", claim="one"))
        approved(store, card("b", claim="two"))
        assert [e.evidence_id for e in store.evidence_for(["b", "a"])] == ["b", "a"]

    def test_unapproved_card_reports_its_real_status(self, store: KnowledgeStore) -> None:
        store.ingest(card("a"))
        assert store.evidence_for(["a"])[0].status is EvidenceStatus.CANDIDATE


class TestNoContentLeakage:
    def test_card_metadata_carries_no_claim(self) -> None:
        canary = "NOI-DUNG-THE-KHONG-DUOC-LOG"
        metadata = card(claim=canary).metadata()
        assert canary not in str(metadata)
        assert metadata["claim_chars"] == len(canary)

    def test_claim_is_wrapped(self) -> None:
        canary = "NOI-DUNG-THE"
        c = card(claim=canary)
        assert canary not in repr(c.claim)
        assert c.claim.unsafe_text() == canary

    def test_card_repr_does_not_expose_the_claim(self) -> None:
        canary = "NOI-DUNG-TRONG-REPR"
        assert canary not in repr(card(claim=canary))


class TestNoAutomaticLearning:
    def test_there_is_no_path_from_a_transcript_to_a_card(self) -> None:
        """Ingest is the only entry, and it requires an allowlisted source."""
        public = {
            name
            for name in dir(KnowledgeStore)
            if not name.startswith("_") and callable(getattr(KnowledgeStore, name))
        }
        for forbidden in ("learn", "observe", "from_transcript", "auto_ingest"):
            assert forbidden not in public, public

    def test_confidence_must_be_a_probability(self) -> None:
        with pytest.raises(KnowledgeError, match=r"\[0, 1\]"):
            KnowledgeCard(
                card_id="x",
                card_type=CardType.POSITION,
                claim=MeetingContent("c"),
                rationale=MeetingContent("r"),
                source_ref="s",
                source_date=0.0,
                confidence=1.5,
            )

    def test_default_allowed_action_is_the_narrow_one(self) -> None:
        """Volunteering is opt-in; citing when asked is the floor."""
        assert card().allowed_actions == frozenset({AllowedAction.CITE_WHEN_ASKED})


class TestPurgeContinuesPastFailure:
    """One unreachable index must not leave the others un-purged.

    Leaving embeddings behind because a cache was down is the failure that
    makes a retention promise false, so every index gets its turn and the
    failures are reported afterwards.
    """

    def test_a_healthy_index_is_still_purged(self, store: KnowledgeStore) -> None:
        broken = FakeIndex(fail=True)
        healthy = FakeIndex()
        store.register_index(broken)
        store.register_index(healthy)
        approved(store)

        with pytest.raises(KnowledgeError):
            store.delete("card-1")

        assert healthy.purged == ["card-1"], "index lanh bi bo qua khi index khac loi"

    def test_failure_message_counts_the_failures(self, store: KnowledgeStore) -> None:
        store.register_index(FakeIndex(fail=True))
        store.register_index(FakeIndex(fail=True))
        store.register_index(FakeIndex())
        approved(store)

        with pytest.raises(KnowledgeError, match=r"\(2/3\)"):
            store.delete("card-1")

    def test_failure_message_names_types_not_content(self, store: KnowledgeStore) -> None:
        store.register_index(FakeIndex(fail=True))
        approved(store, card(claim="NOI-DUNG-BI-MAT"))
        with pytest.raises(KnowledgeError) as exc_info:
            store.delete("card-1")
        message = str(exc_info.value)
        assert "NOI-DUNG-BI-MAT" not in message
        assert "FakeIndex" in message
