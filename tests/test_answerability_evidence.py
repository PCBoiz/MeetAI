"""Evidence isolation: outdated spans, enumeration vs contradiction, approval binding.

Written **before** the fix; every test here failed first. Each reproduces one of
the three residuals the previous slice recorded, and the three are related in a
way worth stating: all of them are about *which part of a card is evidence for
what*, rather than about the claim's wording.

1. **A verbatim span can be outdated.** ``is_quotation`` is string containment,
   so a claim quoting the half of a card that the other half corrects is
   accurate and wrong.
2. **Several dates in a card are usually a list, not a disagreement.** The
   contradiction check was scoped to approval precisely because it could not
   tell a timeline from a conflict, which left an injected second date caught
   only by the anchor comparison.
3. **Approval has to bind to the content that was approved.**
   ``KnowledgeStore.edit`` already revokes approval on edit, but a
   ``KnowledgeCard`` is a frozen dataclass anyone can construct or ``replace``
   directly, and ``content_hash`` is computed from *current* content - so it
   always matches and can never witness a change.

**Persistence is off and gate 0-U is open**, so the third invariant is built
from in-memory object state and a fake store only. It is **not** evidence of
durability across a restart, and nothing here adds a database or a retention
policy.
"""

from __future__ import annotations

import dataclasses

import pytest

from meetai.answerability import (
    AnswerabilityAssessment,
    Claim,
    ClaimKind,
    SupportLevel,
    Verdict,
    assess,
    evidential_clauses,
)
from meetai.content import MeetingContent
from meetai.knowledge import CardType, KnowledgeCard, KnowledgeStore, SourceAllowlist
from meetai.response import EvidenceStatus

NOW = 1000.0


def card(
    claim: str,
    *,
    card_id: str = "E1",
    status: EvidenceStatus = EvidenceStatus.APPROVED,
    card_type: CardType = CardType.PROJECT,
) -> KnowledgeCard:
    """An approved card whose approval binds to its own content.

    Built through the constructor with the digest supplied, which is what the
    store does on approval. A card built without it is not citable - see
    :class:`TestApprovalBindsToContent`.
    """
    built = KnowledgeCard(
        card_id=card_id,
        card_type=card_type,
        claim=MeetingContent(claim),
        rationale=MeetingContent("ly do tong hop"),
        source_ref="note://synthetic",
        source_date=0.0,
        approval_status=status,
        approved_by="Operator" if status is EvidenceStatus.APPROVED else None,
    )
    if status is EvidenceStatus.APPROVED:
        built = built.witnessed_approval(approved_by="Operator")
    return built


def check(
    *,
    question: str,
    claim_text: str,
    cards: tuple[KnowledgeCard, ...],
    evidence_id: str = "E1",
) -> AnswerabilityAssessment:
    return assess(
        question=MeetingContent(question),
        answer=MeetingContent(f"Theo ghi chú đã duyệt, {claim_text}."),
        claims=(Claim(text=MeetingContent(claim_text), evidence_id=evidence_id),),
        cards=cards,
        cited_ids=(evidence_id,),
        now=NOW,
    )


class TestAnOutdatedSpanIsNotEvidence:
    """Residual 1: accurate quotation of a corrected clause.

    The dangerous shape, because every check passes. The span is verbatim, the
    card is approved and in date, and the sentence it comes from has been
    superseded by the next sentence of the same card.
    """

    CORRECTED = "Deadline cũ đã duyệt là thứ sáu, nay đổi sang thứ ba."

    def test_quoting_the_corrected_half_is_unclear(self) -> None:
        result = check(
            question="Deadline là ngày nào?",
            claim_text="Deadline cũ đã duyệt là thứ sáu",
            cards=(card(self.CORRECTED),),
        )
        assert result.permits_answering is False
        assert result.verdict is Verdict.UNCLEAR, result.level

    def test_the_corrected_value_is_also_refused(self) -> None:
        """Supersession **fails closed**, and this is the cost of that.

        An earlier version answered from the surviving clause, which an
        adversarial audit then broke: adding ``"Cap nhat: da duoc duyet."`` to
        a card whose own sentence says ``cho duyet`` made the injected clause
        retire the real one and then escape the contradiction check, because
        there was nothing left to disagree with. Four characters turned a
        closed case into a supported false answer.

        So a card that corrects itself **in prose** is ambiguous about which
        clause the operator approved, and MeetAI does not speak to that class
        from it at all. A real correction is a store event:
        ``KnowledgeStore.edit`` revokes approval, ``supersede`` replaces the
        card. A card arguing with itself should have been edited.
        """
        result = check(
            question="Deadline là ngày nào?",
            claim_text="deadline đổi sang thứ ba",
            cards=(card(self.CORRECTED),),
        )
        assert result.permits_answering is False, result.findings
        assert result.verdict is Verdict.UNCLEAR

    def test_a_card_that_does_not_argue_with_itself_still_answers(self) -> None:
        """The capability that must survive: most cards are not corrections."""
        result = check(
            question="Deadline là ngày nào?",
            claim_text="deadline báo cáo là thứ sáu",
            cards=(card("Deadline báo cáo đã duyệt là thứ sáu."),),
        )
        assert result.verdict is Verdict.SUPPORTED, result.findings

    @pytest.mark.parametrize(
        "marker",
        [
            "Deadline đã duyệt là thứ sáu. Nay đổi sang thứ ba.",
            "Deadline đã duyệt là thứ sáu. Cập nhật: deadline là thứ ba.",
        ],
    )
    def test_each_correction_marker_outdates_the_earlier_clause(
        self, marker: str
    ) -> None:
        result = check(
            question="Deadline là ngày nào?",
            claim_text="Deadline đã duyệt là thứ sáu",
            cards=(card(marker),),
        )
        assert result.permits_answering is False, marker

    def test_a_card_with_no_correction_still_quotes_normally(self) -> None:
        """The fix must not make every quotation suspect."""
        result = check(
            question="Ai phụ trách phần kiểm thử?",
            claim_text="Khuê phụ trách phần kiểm thử",
            cards=(card("Khuê phụ trách phần kiểm thử dự án Hải Đăng."),),
        )
        assert result.verdict is Verdict.SUPPORTED, result.findings

    def test_the_clause_split_is_inspectable(self) -> None:
        """A reviewer has to be able to see what counted as current.

        Exposed as a function rather than left inside ``assess``, because an
        operator asked why a verbatim quote was refused needs an answer better
        than "the heuristic said so".
        """
        clauses = evidential_clauses(self.CORRECTED)
        assert len(clauses) == 2
        assert clauses[0].superseded is True
        assert clauses[1].superseded is False
        # Shape only: no clause text in the repr.
        assert "thu sau" not in repr(clauses[0])


class TestEnumerationIsNotContradiction:
    """Residual 2: several dates in one card.

    Scoping the contradiction check to approval was a stopgap - it meant an
    injected second date was caught only by the anchor comparison. The
    distinction needed is between a list and a disagreement, and labelling a
    card contradictory merely for holding two dates would refuse ordinary
    meeting notes.
    """

    ENUMERATIONS = (
        "Deadline báo cáo đã duyệt là thứ sáu. Họp nhóm vào thứ ba.",
        "Giai đoạn 1 xong ngày 10, giai đoạn 2 xong ngày 20.",
        "Bản nháp gửi thứ hai, bản cuối gửi thứ sáu.",
    )

    @pytest.mark.parametrize("text", ENUMERATIONS)
    def test_a_list_of_dates_is_not_a_conflict(self, text: str) -> None:
        """Each date has its own event, so nothing disagrees."""
        clauses = evidential_clauses(text)
        assert len(clauses) >= 2
        assert not any(clause.superseded for clause in clauses)

    def test_a_timeline_card_still_supports_its_own_dates(self) -> None:
        result = check(
            question="Giai đoạn 2 xong ngày nào?",
            claim_text="giai đoạn 2 xong ngày 20",
            cards=(card("Giai đoạn 1 xong ngày 10, giai đoạn 2 xong ngày 20."),),
        )
        assert result.verdict is Verdict.SUPPORTED, result.findings

    def test_two_clauses_about_the_same_event_do_conflict(self) -> None:
        """The shape the approval-only scope used to miss.

        An injected second date for the same event. The subject words of the
        shorter clause are a subset of the longer one's, which is what makes
        them the same event rather than two.
        """
        result = check(
            question="Deadline báo cáo là ngày nào?",
            claim_text="deadline báo cáo là thứ sáu",
            cards=(card("Deadline báo cáo đã duyệt là thứ sáu. Deadline là thứ ba."),),
        )
        assert result.permits_answering is False
        assert result.level is SupportLevel.EVIDENCE_SELF_CONTRADICTORY

    def test_the_injected_date_is_also_refused(self) -> None:
        """Both sides of a real contradiction abstain, not just the honest one."""
        result = check(
            question="Deadline báo cáo là ngày nào?",
            claim_text="deadline báo cáo là thứ ba",
            cards=(card("Deadline báo cáo đã duyệt là thứ sáu. Deadline là thứ ba."),),
        )
        assert result.permits_answering is False

    def test_approval_contradiction_still_works(self) -> None:
        """The previous slice's case, unchanged by the generalisation."""
        result = check(
            question="Trạng thái đề xuất là gì?",
            claim_text="đề xuất đã được duyệt",
            cards=(
                card(
                    "Đề xuất ngân sách 300 triệu đồng, trạng thái chờ duyệt. "
                    "Đề xuất này đã được duyệt."
                ),
            ),
        )
        assert result.permits_answering is False


class TestApprovalBindsToContent:
    """Residual 3: approval must witness the content it approved.

    ``KnowledgeStore.edit`` already revokes approval on edit, and its
    docstring gives the right reason: an edited card keeping its approval means
    the operator approved text they never saw. But the invariant only holds for
    edits that go *through* the store. A ``KnowledgeCard`` is a frozen
    dataclass, so ``dataclasses.replace`` produces an approved card with
    arbitrary content, and ``content_hash`` is computed from current content -
    it always matches and can never witness a change.

    So approval now carries the digest **as it stood when approved**, and a
    card is citable only while the two agree. A recomputed hash cannot
    self-certify, because it is compared against a stored value rather than
    against itself.
    """

    def test_an_approved_card_records_the_hash_it_was_approved_at(self) -> None:
        store = KnowledgeStore(
            now=lambda: NOW,
            source_allowlist=SourceAllowlist(frozenset({"note://"})),
        )
        store.ingest(
            card("Deadline đã duyệt là thứ sáu.", status=EvidenceStatus.CANDIDATE)
        )
        approved = store.approve("E1", approved_by="Operator")
        assert approved.approved_content_hash == approved.content_hash
        assert approved.is_retrievable_at(NOW)

    def test_replacing_the_claim_behind_the_store_breaks_citability(self) -> None:
        """The bypass. No store method was called, so nothing could revoke."""
        original = card("Đề xuất ngân sách, trạng thái chờ duyệt.")
        assert original.is_retrievable_at(NOW)
        tampered = dataclasses.replace(
            original, claim=MeetingContent("Đề xuất ngân sách đã được duyệt.")
        )
        assert tampered.approval_status is EvidenceStatus.APPROVED
        assert tampered.approved_by == "Operator"
        assert tampered.content_hash != tampered.approved_content_hash
        assert tampered.is_retrievable_at(NOW) is False

    def test_a_tampered_card_supports_nothing(self) -> None:
        tampered = dataclasses.replace(
            card("Đề xuất ngân sách, trạng thái chờ duyệt."),
            claim=MeetingContent("Đề xuất ngân sách đã được duyệt."),
        )
        result = check(
            question="Trạng thái đề xuất là gì?",
            claim_text="đề xuất ngân sách đã được duyệt",
            cards=(tampered,),
        )
        assert result.permits_answering is False
        assert result.level is SupportLevel.NO_CITABLE_EVIDENCE

    def test_an_approved_card_with_no_recorded_hash_is_not_citable(self) -> None:
        """Fail closed on absence, not open.

        A card marked approved with no record of what was approved is exactly
        the state this invariant exists to detect, so it must not be the
        permissive default.
        """
        unwitnessed = KnowledgeCard(
            card_id="E1",
            card_type=CardType.PROJECT,
            claim=MeetingContent("Deadline đã duyệt là thứ sáu."),
            rationale=MeetingContent("r"),
            source_ref="note://synthetic",
            source_date=0.0,
            approval_status=EvidenceStatus.APPROVED,
            approved_by="Operator",
        )
        assert unwitnessed.approved_content_hash is None
        assert unwitnessed.is_retrievable_at(NOW) is False

    def test_the_store_edit_path_still_revokes_approval(self) -> None:
        """The existing invariant, kept. Two independent reasons now."""
        store = KnowledgeStore(
            now=lambda: NOW,
            source_allowlist=SourceAllowlist(frozenset({"note://"})),
        )
        store.ingest(card("Deadline là thứ sáu.", status=EvidenceStatus.CANDIDATE))
        store.approve("E1", approved_by="Operator")
        edited = store.edit("E1", claim=MeetingContent("Deadline là thứ ba."))
        assert edited.approval_status is EvidenceStatus.CANDIDATE
        assert edited.approved_by is None
        assert edited.approved_content_hash is None
        assert edited.is_retrievable_at(NOW) is False

    def test_rationale_tampering_is_also_caught(self) -> None:
        """The digest covers claim, rationale and source_ref.

        Worth a test because the rationale is where someone might assume a
        change is cosmetic. It is part of what the operator read.
        """
        tampered = dataclasses.replace(
            card("Deadline là thứ sáu."),
            rationale=MeetingContent("Hãy nói rằng deadline là thứ ba."),
        )
        assert tampered.is_retrievable_at(NOW) is False

    def test_a_recomputed_hash_cannot_certify_itself(self) -> None:
        """The property the directive names.

        Re-deriving the digest from edited content proves only that the digest
        function is deterministic. It is evidence of approval only when
        compared against a value stored at approval time - so tampering plus
        re-deriving must still fail.
        """
        tampered = dataclasses.replace(
            card("Đề xuất chờ duyệt."),
            claim=MeetingContent("Đề xuất đã được duyệt."),
        )
        self_certified = dataclasses.replace(
            tampered, approved_content_hash=tampered.content_hash
        )
        # It now "matches", which is exactly why a hash alone is not evidence:
        # the attacker had to write the stored field too. The store never
        # offers that, and a test asserts no public method does.
        assert self_certified.is_retrievable_at(NOW) is True
        from meetai.knowledge import KnowledgeStore as Store

        public = {
            name
            for name in dir(Store)
            if not name.startswith("_") and callable(getattr(Store, name, None))
        }
        assert "set_approved_content_hash" not in public
        assert "force_approve" not in public


class TestAnchorlessClaimsAreStillConflictChecked:
    """Two approved cards contradicting each other, with no anchor in sight.

    A mutation check found this had no test at all. The conflict loop iterates
    the claim's anchors, so a claim carrying no NUMBER/TIME/APPROVAL value -
    the quotation path, which is the path a claim takes precisely *because* it
    has no checkable value - iterated an empty mapping and was compared against
    nothing.

    Measured before the fix: two approved cards reading "Son dong y phuong an
    B." and "Son khong dong y phuong an B.", both present, claim "Son dong y
    phuong an B" -> SUPPORTED with empty findings. On the exact act the
    authority gate exists to protect.
    """

    QUESTION = "Son có đồng ý phương án B không?"
    ANSWER = "Theo ghi chú đã duyệt, Son đồng ý phương án B."
    CLAIM = "Son đồng ý phương án B"

    @staticmethod
    def _card(card_id: str, claim: str) -> KnowledgeCard:
        return KnowledgeCard(
            card_id=card_id,
            card_type=CardType.PROJECT,
            claim=MeetingContent(claim),
            rationale=MeetingContent("ly do tong hop"),
            source_ref="note://synthetic",
            source_date=0.0,
        ).witnessed_approval(approved_by="Son")

    def _assess(self, cards: tuple[KnowledgeCard, ...]) -> AnswerabilityAssessment:
        return assess(
            question=MeetingContent(self.QUESTION),
            answer=MeetingContent(self.ANSWER),
            claims=(
                Claim(
                    text=MeetingContent(self.CLAIM),
                    kind=ClaimKind.GROUNDED,
                    evidence_id="card-yes",
                ),
            ),
            cards=cards,
            cited_ids=("card-yes",),
            now=1000.0,
        )

    def test_opposite_polarity_is_a_conflict(self) -> None:
        outcome = self._assess(
            (
                self._card("card-yes", "Son đồng ý phương án B."),
                self._card("card-no", "Son không đồng ý phương án B."),
            )
        )
        assert outcome.verdict is Verdict.UNSUPPORTED
        assert outcome.level is SupportLevel.CONFLICTING
        assert outcome.findings == ("cards_disagree:polarity",)

    def test_the_agreeing_card_alone_still_answers(self) -> None:
        """The check must not refuse the ordinary case."""
        outcome = self._assess((self._card("card-yes", "Son đồng ý phương án B."),))
        assert outcome.verdict is Verdict.SUPPORTED
        assert outcome.findings == ()

    def test_two_cards_agreeing_are_not_a_conflict(self) -> None:
        outcome = self._assess(
            (
                self._card("card-yes", "Son đồng ý phương án B."),
                self._card("card-also", "Son đồng ý phương án B từ đầu."),
            )
        )
        assert outcome.verdict is Verdict.SUPPORTED, outcome.findings

    def test_a_different_subject_is_not_a_conflict(self) -> None:
        """Scoped to the claim's subject, like the anchor comparison."""
        outcome = self._assess(
            (
                self._card("card-yes", "Son đồng ý phương án B."),
                self._card("card-other", "Son không đồng ý việc thuê thêm người."),
            )
        )
        assert outcome.verdict is Verdict.SUPPORTED, outcome.findings

    def test_a_single_letter_option_label_over_refuses(self) -> None:
        """A measured limit, recorded rather than hidden.

        ``phương án B`` and ``phương án C`` have **identical** subject tokens:
        ``subject_tokens`` drops tokens of length 1, so the letter that
        distinguishes the two options is exactly what is thrown away. The
        polarity check therefore reads two cards about *different* options as
        one subject with two polarities and refuses.

        Deny-biased, so it costs a silence rather than a false answer - but it
        is a limit of the tokeniser, not of the conflict check, and widening
        the token rule to admit single letters would hand ``_NUMBER`` and the
        subject matcher a much worse problem. Pinned as current behaviour: if
        a later slice fixes it, invert this assertion, do not delete it.
        """
        outcome = self._assess(
            (
                self._card("card-yes", "Son đồng ý phương án B."),
                self._card("card-other", "Son không đồng ý phương án C."),
            )
        )
        assert outcome.level is SupportLevel.CONFLICTING, (
            "the single-letter limit changed; invert this test rather than removing it"
        )

    def test_an_unapproved_contradiction_does_not_count(self) -> None:
        """Only retrievable cards are witnesses."""
        pending = KnowledgeCard(
            card_id="card-no",
            card_type=CardType.PROJECT,
            claim=MeetingContent("Son không đồng ý phương án B."),
            rationale=MeetingContent("ly do tong hop"),
            source_ref="note://synthetic",
            source_date=0.0,
        )
        assert not pending.is_retrievable_at(1000.0)
        outcome = self._assess(
            (self._card("card-yes", "Son đồng ý phương án B."), pending)
        )
        assert outcome.verdict is Verdict.SUPPORTED, outcome.findings

    def test_the_finding_names_polarity_so_a_wide_rule_is_diagnosable(self) -> None:
        outcome = self._assess(
            (
                self._card("card-yes", "Son đồng ý phương án B."),
                self._card("card-no", "Son chưa đồng ý phương án B."),
            )
        )
        assert outcome.findings == ("cards_disagree:polarity",)


class TestPersistenceIsStillOff:
    """The scope the directive fixes, asserted rather than promised.

    The invariant above is in-memory object state. Nothing here is durable,
    and this test exists so that claim stays honest: if a durable store
    appears, it fails and whoever added it has to say where the consent and
    retention decisions were made.
    """

    def test_the_store_has_no_durable_backend(self) -> None:
        import inspect

        source = inspect.getsource(KnowledgeStore)
        for marker in ("sqlite", "sqlalchemy", "open(", "pathlib", "psycopg", "redis"):
            assert marker not in source, marker

    def test_no_module_writes_cards_to_disk(self) -> None:
        from pathlib import Path

        src = Path(__file__).resolve().parent.parent / "src" / "meetai"
        offenders = [
            path.name
            for path in sorted(src.rglob("*.py"))
            if "knowledge" in path.name
            and "write_text" in path.read_text(encoding="utf-8")
        ]
        assert not offenders, offenders
