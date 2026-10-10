"""Nine measured false-answer paths, pinned at current behaviour.

Every case here returns ``permits_answering=True`` with an **empty** findings
tuple: the sink sees nothing to log, the authority gate has no act to refuse,
and an operator reviewing the decision has no rule name to look up. That is
what makes these worse than a refusal bug.

**None is fixed here, and that is a decision rather than an omission.** Each
needs either a vocabulary change, a tokeniser change, or a new checking layer,
and ``AGENTS.md`` requires measuring any of those on an eval set the operator
controls *before* it lands - the recorded reason being that a repair made to
turn a suite green converts a measured hole into an unmeasured one. So each
path is asserted **as it behaves today**, with a message telling the next
author to **invert** the assertion rather than delete it.

**Five common roots**, because nine patch sites would be the wrong reading:

1. **Subset containment treats deletion as agreement.** ``claim_subjects <=
   clause.subjects`` means a claim that drops a qualifier, a conjunct or a
   designator stays a subset of its card. Roots #2, #4, #5, #6.
2. **Clause inheritance propagates subjects but not polarity or
   attachment.** Root #1.
3. **The three anchor classes are the only values anything is accountable
   for.** A person, an option label or a place is not an anchor, so nothing
   accounts for it. Roots #3, #8.
4. **Token-identity keys cannot see synonyms.** Root #7.
5. **Question coverage is credited to cards rather than to claims.** Root #9.

Found by an independent review at ``9371fb0`` and **re-measured here
case by case** before being written down; the controls are part of that
re-measurement, since a module that refused everything would satisfy the
positive assertions trivially.
"""

from __future__ import annotations

import pytest

from meetai.answerability import (
    AnchorClass,
    Claim,
    assess,
    contradicting_class,
    subject_tokens,
)
from meetai.content import MeetingContent
from tests.corpus.answerability_types import CardSpec
from tests.test_answerability_eval import build_card

FRAME = "Theo ghi chú đã duyệt, "

INVERT = (
    "Lo nay da dong. Dao assertion thay vi xoa, va cap nhat "
    "docs/spec.md cung PROJECT_STATE."
)


def judge(
    card_text: str,
    claim_text: str,
    question: str,
    *,
    answer: str | None = None,
) -> tuple[bool, str, tuple[str, ...]]:
    """``(permits_answering, level, findings)`` for one claim against one card."""
    spec = CardSpec(card_id="E1", claim=card_text)
    assessment = assess(
        question=MeetingContent(question),
        answer=MeetingContent(answer if answer is not None else f"{FRAME}{claim_text}."),
        claims=(Claim(text=MeetingContent(claim_text), evidence_id="E1"),),
        cards=(build_card(spec),),
        cited_ids=("E1",),
        now=1000.0,
    )
    return (
        assessment.permits_answering,
        assessment.level.value,
        tuple(assessment.findings),
    )


def assert_false_answer(card: str, claim: str, question: str, **kw: str) -> None:
    permits, level, findings = judge(card, claim, question, **kw)
    assert permits is True, INVERT
    assert level == "supported", INVERT
    assert findings == (), f"{INVERT} (findings={findings})"


class TestInheritanceCarriesSubjectsButNotPolarity:
    """Root 1, and it re-opens the module's own flagship example.

    ``answerability``'s module docstring opens with "chi phí hạ tầng" against
    "ngân sách tổng", 240 triệu, and ``supporting_clause`` says that case was
    measured and closed. It is closed when the clauses are joined by a full
    stop, and **open when they are joined by a comma in the other order**.

    Inherited subjects travel forward into the next clause;
    ``supporting_clause`` tests ``_NEGATED`` against ``clause.text`` only,
    never against what the clause inherited. So the second clause offers its
    value under the first clause's subject, and the first clause's "not yet
    settled" does not come with it.
    """

    QUESTION = "Chi phí hạ tầng là bao nhiêu?"
    CLAIM = "chi phí hạ tầng là 240 triệu đồng"

    def test_a_comma_lets_the_next_clause_value_be_claimed_for_this_subject(
        self,
    ) -> None:
        assert_false_answer(
            "Chi phí hạ tầng chưa chốt, ngân sách tổng đã duyệt là 240 triệu đồng.",
            self.CLAIM,
            self.QUESTION,
        )

    def test_a_full_stop_instead_of_a_comma_is_refused(self) -> None:
        """Control. The same two sentences, one punctuation mark apart."""
        permits, _, findings = judge(
            "Chi phí hạ tầng chưa chốt. Ngân sách tổng đã duyệt là 240 triệu đồng.",
            self.CLAIM,
            self.QUESTION,
        )
        assert permits is False
        assert "unsupported_anchor:cross_clause" in findings

    def test_the_other_clause_order_is_refused(self) -> None:
        """Control. Same comma, same words, value clause first."""
        permits, _, _ = judge(
            "Ngân sách tổng đã duyệt là 240 triệu đồng, chi phí hạ tầng chưa chốt.",
            self.CLAIM,
            self.QUESTION,
        )
        assert permits is False

    def test_no_negator_is_needed_anywhere(self) -> None:
        """So this is not a hole in the negation lexicon.

        Any leading clause that merely *names* subject A lets the following
        comma clause's value be claimed for A.
        """
        assert_false_answer(
            "Chi phí hạ tầng vẫn đang xem xét, ngân sách tổng là 240 triệu đồng.",
            self.CLAIM,
            self.QUESTION,
        )

    def test_it_moves_a_date_onto_the_wrong_subject_too(self) -> None:
        """Not specific to NUMBER."""
        assert_false_answer(
            "Giai đoạn hai vẫn đang làm, giai đoạn khởi động xong ngày 20.",
            "giai đoạn hai xong ngày 20",
            "Giai đoạn hai xong ngày nào?",
        )

    def test_it_states_an_approval_the_card_denies(self) -> None:
        """The most serious instance: an approval for a subject under review.

        With **two** competing approval values the card is caught - but by
        ``contradicting_class``, not by anything in the inheritance logic. With
        one, nothing catches it.
        """
        assert_false_answer(
            "Chi phí hạ tầng vẫn đang xem xét, đề xuất thiết bị đã được duyệt.",
            "chi phí hạ tầng đã được duyệt",
            "Chi phí hạ tầng đã duyệt chưa?",
        )

    def test_two_competing_approvals_are_caught(self) -> None:
        """Control, and it shows what is doing the catching."""
        permits, level, findings = judge(
            "Chi phí hạ tầng chưa duyệt, đề xuất thiết bị đã được duyệt.",
            "chi phí hạ tầng đã được duyệt",
            "Chi phí hạ tầng đã duyệt chưa?",
        )
        assert permits is False
        assert level == "evidence_self_contradictory"
        assert "card_contradicts_itself:approval" in findings


class TestAnEmptySubjectSetIsASubsetOfEveryCard:
    """Root 1, in its purest form: ``frozenset() <= anything``.

    ``subject_tokens("Tài liệu đã được duyệt")`` is **empty** - ``tài`` and
    ``lieu`` are both stopwords, as are ``đã``, ``được`` and ``duyệt``. Subset
    containment is then vacuously true against any card carrying the anchor,
    so the claim is "on subject" for a card about anything at all.

    This is ordinary Vietnamese, not an adversarial string. Both guards fail
    on the same input: the question side collapses to stopwords too, so
    ``PARTIAL_UNDECLARED`` cannot fire either.
    """

    QUESTION = "Tài liệu đã duyệt chưa?"
    CLAIM = "Tài liệu đã được duyệt"

    def test_the_claim_has_no_subject_tokens_at_all(self) -> None:
        assert subject_tokens(self.CLAIM) == frozenset(), INVERT

    def test_it_is_answered_from_a_budget_card(self) -> None:
        assert_false_answer(
            "Ngân sách hạ tầng đã được duyệt là 240 triệu đồng.",
            self.CLAIM,
            self.QUESTION,
        )

    def test_it_is_answered_from_a_card_about_something_unrelated(self) -> None:
        assert_false_answer(
            "Quy trình tuyển dụng đã được duyệt.", self.CLAIM, self.QUESTION
        )

    def test_one_non_stopword_in_the_subject_refuses_it(self) -> None:
        """Control. ``hợp đồng`` survives tokenising; ``tài liệu`` does not."""
        permits, _, findings = judge(
            "Quy trình tuyển dụng đã được duyệt.",
            "hợp đồng đã được duyệt",
            "Hợp đồng đã duyệt chưa?",
        )
        assert permits is False
        assert "claim_subject_absent_from_card" in findings


class TestReversalVerbsEscapeTheNegationGuard:
    """Root 3. ``_NEGATED`` is ``khong|chua|chang``; rejection has more words.

    ``từ chối``, ``bác bỏ`` and ``huỷ`` reverse a card's assertion without
    tripping the polarity test. In the first case the rejection *is* visible to
    the module as an ``APPROVAL`` anchor - it simply never constrains a claim
    that declares no approval anchor of its own.
    """

    def test_a_rejected_proposal_is_relayed_as_the_figure(self) -> None:
        assert_false_answer(
            "Đề xuất ngân sách 240 triệu đồng đã bị từ chối.",
            "ngân sách là 240 triệu đồng",
            "Ngân sách là bao nhiêu?",
        )

    def test_bac_bo_behaves_the_same(self) -> None:
        assert_false_answer(
            "Đề xuất ngân sách 240 triệu đồng đã bị bác bỏ.",
            "ngân sách là 240 triệu đồng",
            "Ngân sách là bao nhiêu?",
        )

    def test_a_cancelled_deadline_is_relayed_as_the_deadline(self) -> None:
        assert_false_answer(
            "Deadline báo cáo là thứ sáu đã bị huỷ.",
            "deadline báo cáo là thứ sáu",
            "Deadline báo cáo là ngày nào?",
        )

    def test_an_intra_card_retraction_of_consent_is_relayed_as_consent(self) -> None:
        """The one that matters most: it is about the operator's own consent.

        ``Sơn đồng ý phương án B, sau đó bác bỏ.`` relayed as ``Sơn đồng ý
        phương án B``. Same shape the code comments record as closed for
        ``chưa``, on the act the authority gate exists to protect.
        """
        assert_false_answer(
            "Sơn đồng ý phương án B, sau đó bác bỏ.",
            "Sơn đồng ý phương án B",
            "Sơn đồng ý phương án B chưa?",
        )

    def test_khong_duoc_duyet_is_refused(self) -> None:
        """Control. The lexicon works where it reaches."""
        permits, _, _ = judge(
            "Đề xuất ngân sách 240 triệu đồng không được duyệt.",
            "ngân sách là 240 triệu đồng",
            "Ngân sách là bao nhiêu?",
        )
        assert permits is False


class TestMotIsAStopwordWhileHaiAndBaAreNot:
    """Root 1, and a **one-way** hole, which is what makes it easy to miss.

    ``một`` is in ``_STOPWORDS``; ``hai``, ``ba``, ``bốn`` are not. So a claim
    about "giai đoạn một" has no token for the ordinal, and its subject set is
    a subset of a card about "giai đoạn hai". The reverse direction is
    refused.

    A distinct root cause from the recorded single-character designator case:
    there the designator is dropped for being one character, here for being a
    stopword, and here only one direction opens.
    """

    def test_a_claim_about_phase_one_is_answered_from_a_phase_two_card(self) -> None:
        assert_false_answer(
            "Giai đoạn hai hoàn thành ngày 20.",
            "giai đoạn một hoàn thành ngày 20",
            "Giai đoạn một hoàn thành ngày nào?",
        )

    def test_it_works_against_phuong_an_bon_too(self) -> None:
        assert_false_answer(
            "Phương án bốn đã được duyệt.",
            "phương án một đã được duyệt",
            "Phương án một đã duyệt chưa?",
        )

    def test_the_reverse_direction_is_refused(self) -> None:
        """Control, and the asymmetry: the hole opens only when the **claim**
        is the vaguer of the two."""
        permits, _, findings = judge(
            "Giai đoạn một hoàn thành ngày 20.",
            "giai đoạn hai hoàn thành ngày 20",
            "Giai đoạn hai hoàn thành ngày nào?",
        )
        assert permits is False
        assert "claim_subject_absent_from_card" in findings


class TestDeletingAQualifierOnTheValueIsPermitted:
    """Root 1. The card hedges the figure; the claim drops the hedge.

    Containment cannot see a deletion, so every one of these stays "on
    subject". No quotation is involved, so ``is_quotation``'s clause-initial
    guard never gets a say.
    """

    QUESTION = "Ngân sách hạ tầng là bao nhiêu?"
    CLAIM = "ngân sách hạ tầng là 240 triệu đồng"

    @pytest.mark.parametrize(
        "card",
        [
            "Ngân sách hạ tầng sơ bộ là 240 triệu đồng.",
            "Ngân sách hạ tầng tạm tính là 240 triệu đồng.",
            "Ngân sách hạ tầng khoảng 240 triệu đồng.",
        ],
    )
    def test_a_hedged_figure_is_relayed_as_settled(self, card: str) -> None:
        assert_false_answer(card, self.CLAIM, self.QUESTION)

    def test_a_proposed_budget_is_relayed_as_the_budget(self) -> None:
        """The worst of the set, because of the frame it is spoken under.

        ``đề xuất`` makes it a **proposal**. Relayed as the budget, prefixed
        with "theo ghi chú đã duyệt" - so the sentence asserts both that this
        is the figure and that it is approved, and the card says neither.
        """
        assert_false_answer(
            "Ngân sách hạ tầng đề xuất là 240 triệu đồng.", self.CLAIM, self.QUESTION
        )

    def test_a_forecast_date_is_relayed_as_the_date(self) -> None:
        assert_false_answer(
            "Deadline báo cáo dự kiến là thứ sáu.",
            "deadline báo cáo là thứ sáu",
            "Deadline báo cáo là ngày nào?",
        )


class TestADroppedConjunctNarrowsTheValuesScope:
    """Root 1, where the deleted material is the value's **scope**."""

    def test_a_budget_for_two_things_is_relayed_as_being_for_one(self) -> None:
        """240 for equipment **and** training, relayed as 240 for equipment.

        ``và`` is a stopword and the other conjunct's words are simply absent
        from the claim, which keeps it a subset.
        """
        assert_false_answer(
            "Ngân sách cho thiết bị và đào tạo là 240 triệu đồng.",
            "ngân sách thiết bị là 240 triệu đồng",
            "Ngân sách thiết bị là bao nhiêu?",
        )


class TestEventKeysCannotSeeSynonymsWithinOneCard:
    """Root 4, and distinct from the recorded **cross-card** synonym gap.

    One card holding two different dates for one event is not a
    contradiction, because ``_event_key`` builds token sets and neither
    ``{bao, cao, deadline}`` nor ``{bao, cao, chot, han}`` contains the other.
    """

    CARD = "Deadline báo cáo là thứ sáu. Hạn chót báo cáo là thứ ba."

    def test_the_card_is_not_seen_as_contradicting_itself(self) -> None:
        assert contradicting_class(self.CARD, AnchorClass.TIME) is False, INVERT

    def test_so_one_of_the_two_dates_is_relayed(self) -> None:
        assert_false_answer(
            self.CARD, "deadline báo cáo là thứ sáu", "Deadline báo cáo là ngày nào?"
        )

    def test_the_same_wording_twice_is_caught(self) -> None:
        """Control. Identical vocabulary, and the keys then match."""
        assert (
            contradicting_class(
                "Deadline báo cáo là thứ sáu. Deadline báo cáo là thứ ba.",
                AnchorClass.TIME,
            )
            is True
        )


class TestTheOrphanValueCheckIsAnchorOnly:
    """Root 3. ``_structure_findings`` strips claim texts, then looks only for
    ``_anchors`` in what is left.

    A person, an option label or a place is not an anchor, so an unbacked one
    in the **answer** - the text the sink emits - is unaccounted for. The
    ``nửa tỷ`` leak the ``_NUMBER`` docstring records as closed is the same
    shape; the figure case is closed and the identity case is not.
    """

    CARD = "Ngân sách hạ tầng đã duyệt là 240 triệu đồng."
    CLAIM = "ngân sách hạ tầng là 240 triệu đồng"
    QUESTION = "Ngân sách hạ tầng là bao nhiêu?"

    def test_an_unbacked_person_name_in_the_answer_is_permitted(self) -> None:
        """The project's named must-not-happen: a participant name spoken with
        no claim and no card behind it."""
        assert_false_answer(
            self.CARD,
            self.CLAIM,
            self.QUESTION,
            answer=f"{FRAME}{self.CLAIM}, do Trâm phụ trách.",
        )

    def test_an_unbacked_option_label_in_the_answer_is_permitted(self) -> None:
        assert_false_answer(
            self.CARD,
            self.CLAIM,
            self.QUESTION,
            answer=f"{FRAME}{self.CLAIM}, và phương án B được chọn.",
        )

    def test_an_unbacked_number_in_the_answer_is_caught(self) -> None:
        """Control, and it shows the check exists - just not for this class."""
        permits, level, findings = judge(
            self.CARD,
            self.CLAIM,
            self.QUESTION,
            answer=f"{FRAME}{self.CLAIM}, chi phí 60 triệu đồng.",
        )
        assert permits is False
        assert level == "malformed"
        assert "answer_value_outside_claims:number" in findings


class TestQuestionCoverageIsCreditedToCardsNotClaims:
    """Root 5, and it gets **worse** the more the card admits its own gap.

    ``covered_subjects`` absorbs the cited card's subjects as well as the
    claims', so a card that merely *mentions* the second half of a two-part
    question disables ``PARTIAL_UNDECLARED`` for that half - even when what
    the card says about it is that it is **not settled**.
    """

    QUESTION = "Ngân sách bao nhiêu và deadline bao giờ?"
    CLAIM = "ngân sách là 240 triệu đồng"

    def test_a_card_mentioning_the_other_half_suppresses_the_gap_check(self) -> None:
        assert_false_answer(
            "Ngân sách đã duyệt là 240 triệu đồng, deadline chưa chốt.",
            self.CLAIM,
            self.QUESTION,
        )

    def test_without_that_mention_the_gap_check_fires(self) -> None:
        """Control. The silence about the deadline is identical in both."""
        permits, level, findings = judge(
            "Ngân sách đã duyệt là 240 triệu đồng.", self.CLAIM, self.QUESTION
        )
        assert permits is False
        assert level == "partial_undeclared"
        assert "question_needs:time" in findings


SILENT_PATHS = [
    (
        "Chi phí hạ tầng chưa chốt, ngân sách tổng đã duyệt là 240 triệu đồng.",
        "chi phí hạ tầng là 240 triệu đồng",
        "Chi phí hạ tầng là bao nhiêu?",
    ),
    (
        "Quy trình tuyển dụng đã được duyệt.",
        "Tài liệu đã được duyệt",
        "Tài liệu đã duyệt chưa?",
    ),
    (
        "Đề xuất ngân sách 240 triệu đồng đã bị từ chối.",
        "ngân sách là 240 triệu đồng",
        "Ngân sách là bao nhiêu?",
    ),
    (
        "Giai đoạn hai hoàn thành ngày 20.",
        "giai đoạn một hoàn thành ngày 20",
        "Giai đoạn một hoàn thành ngày nào?",
    ),
    (
        "Ngân sách hạ tầng đề xuất là 240 triệu đồng.",
        "ngân sách hạ tầng là 240 triệu đồng",
        "Ngân sách hạ tầng là bao nhiêu?",
    ),
    (
        "Ngân sách cho thiết bị và đào tạo là 240 triệu đồng.",
        "ngân sách thiết bị là 240 triệu đồng",
        "Ngân sách thiết bị là bao nhiêu?",
    ),
]
"""Every path above, as one table. Module level so it is not a mutable
class attribute, and so the count is visible in one place."""


class TestNoneOfThemLeaveAnythingToLog:
    """What unites all nine, and why they are worse than a refusal bug.

    Each returns ``supported`` with empty findings, so there is no rule name
    for an operator to look up, nothing for the boundary to log, and no act
    for the authority gate to refuse. A refusal bug announces itself; these
    are silent by construction.
    """

    @pytest.mark.parametrize("card,claim,question", SILENT_PATHS)
    def test_the_findings_are_empty(self, card: str, claim: str, question: str) -> None:
        permits, _, findings = judge(card, claim, question)
        assert permits is True, INVERT
        assert findings == (), f"{INVERT} (findings={findings})"

    def test_the_assessment_still_carries_no_content(self) -> None:
        """The one property that does hold. Worth asserting while it does."""
        secret = "240 trieu dong bi mat"
        spec = CardSpec(card_id="E1", claim=f"Ngân sách hạ tầng đề xuất là {secret}.")
        assessment = assess(
            question=MeetingContent("Ngân sách hạ tầng là bao nhiêu?"),
            answer=MeetingContent(f"{FRAME}ngân sách hạ tầng là {secret}."),
            claims=(
                Claim(
                    text=MeetingContent(f"ngân sách hạ tầng là {secret}"),
                    evidence_id="E1",
                ),
            ),
            cards=(build_card(spec),),
            cited_ids=("E1",),
            now=1000.0,
        )
        rendered = f"{assessment!r} {assessment.metadata()}"
        assert "240" not in rendered, rendered
        assert "bi mat" not in rendered, rendered
