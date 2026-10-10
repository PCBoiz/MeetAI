"""Conflicting evidence: what refuses an answer, and what only reports.

**The measurement that shapes this file.** `KnowledgeStore.conflicts()` pairs
any two retrievable cards of one type and scope whose content differs - so a
budget card and a deadline card in the same scope are reported as a pair. It
detects **divergence**, not **contradiction**. Wiring it as a refusal would
reject nearly every answer in any scope holding more than one card, so it is a
review signal for the operator and nothing branches on it.

What refuses an answer is `answerability.assess` over the **full witness set**,
which is witness-wide and scoped to the asked-about claim's own subject. These
tests therefore prove two separate things, and keeping them separate is the
point:

1. A contradiction in the scope refuses the answer, and **ranking or
   truncating `candidates` cannot hide it** - because `witnesses` is never cut.
2. A legitimate list, a correction recorded through supersession, an expired
   card and a divergence in an unrelated scope do **not** refuse.

What this file does **not** establish: that `conflicts()` is a contradiction
detector (it is not), or that any of this has been exercised against a real
store, a real meeting, or persisted data. Persistence is off and gate 0-U is
open; every store here is in memory.
"""

from __future__ import annotations

from dataclasses import replace

import pytest

from meetai.answerability import (
    Claim,
    ClaimKind,
    SupportLevel,
    Verdict,
    assess,
    subject_tokens,
)
from meetai.boundary import RecordingSink, ResponseRequest, Stage, deliver
from meetai.content import MeetingContent
from meetai.dryrun import MEETING_AUDIENCE, NOW, build_store
from meetai.knowledge import CardType, KnowledgeCard, KnowledgeStore, SourceAllowlist
from meetai.response import (
    AddressContext,
    ProposedResponse,
    ResponseDecision,
    SpeechAct,
)
from meetai.retrieval import retrieve_for_question, witnesses_for

SOURCE = "note://synthetic"
SCOPE = "duan-kappa"


def store_with(*claims: tuple[str, str], scope: str = SCOPE) -> KnowledgeStore:
    """An in-memory store holding the given approved cards.

    Built through `ingest` then `approve`, like every fixture here, so
    `approved_content_hash` is set by the path that production would use.
    """
    store = KnowledgeStore(
        now=lambda: NOW,
        source_allowlist=SourceAllowlist(frozenset({SOURCE})),
    )
    for card_id, claim in claims:
        store.ingest(
            KnowledgeCard(
                card_id=card_id,
                card_type=CardType.PROJECT,
                claim=MeetingContent(claim),
                rationale=MeetingContent("ghi chú tổng hợp"),
                source_ref=SOURCE,
                source_date=0.0,
                scope=scope,
                sensitivity=MEETING_AUDIENCE,
            )
        )
        store.approve(card_id, approved_by="Son")
    return store


def ask(
    store: KnowledgeStore,
    question: str,
    answer: str,
    claim: str,
    cited: str,
    *,
    scope: str = SCOPE,
    max_candidates: int | None = None,
) -> tuple[Stage, SupportLevel | None, tuple[str, ...], int]:
    """Run the whole local path and report what it decided.

    question -> retrieval -> witnesses -> assess -> authority -> sink.
    Returns the stage, the support level, the findings, and the sink count.
    """
    found = retrieve_for_question(
        MeetingContent(question),
        store,
        scope=scope,
        max_sensitivity=MEETING_AUDIENCE,
        max_candidates=max_candidates,
    )
    sink = RecordingSink()
    outcome = deliver(
        ResponseRequest(
            question=MeetingContent(question),
            proposal=ProposedResponse(
                decision=ResponseDecision.SPEAK,
                text=MeetingContent(answer),
                intent=SpeechAct.CITE_APPROVED_POSITION,
                evidence_ids=(cited,),
                confidence=0.9,
            ),
            address=AddressContext(directly_addressed=True),
            claims=(
                Claim(
                    text=MeetingContent(claim),
                    kind=ClaimKind.GROUNDED,
                    evidence_id=cited,
                ),
            ),
            cards=witnesses_for(found),
            now=NOW,
        ),
        sink=sink,
    )
    return outcome.stage, outcome.support_level, outcome.rules, sink.count


# ===================================================================== #
# Two opposing deadlines
# ===================================================================== #
class TestTwoOpposingDeadlines:
    QUESTION = "Deadline báo cáo tháng dự án Kappa là khi nào?"
    ANSWER = "Theo ghi chú đã duyệt, deadline báo cáo tháng dự án Kappa là thứ sáu."
    CLAIM = "deadline báo cáo tháng dự án Kappa là thứ sáu"

    @staticmethod
    def _store() -> KnowledgeStore:
        return store_with(
            ("k-thu-sau", "Deadline báo cáo tháng dự án Kappa đã duyệt là thứ sáu."),
            ("k-thu-ba", "Deadline báo cáo tháng dự án Kappa đã duyệt là thứ ba."),
        )

    def test_the_answer_is_refused(self) -> None:
        stage, level, rules, emitted = ask(
            self._store(), self.QUESTION, self.ANSWER, self.CLAIM, "k-thu-sau"
        )
        assert stage is Stage.ANSWERABILITY
        assert level is SupportLevel.CONFLICTING
        assert rules == ("cards_disagree:time",)
        assert emitted == 0

    @pytest.mark.parametrize("limit", [1, 2, None])
    def test_truncating_candidates_cannot_hide_it(self, limit: int | None) -> None:
        """The property the brief asks for, at every cut that matters.

        `candidates` is what a model would be shown and may be truncated;
        `witnesses` is what the verifier sees and never is. Measured before
        `retrieval.py` existed: handing `assess` the ranked single card instead
        of the set turns this exact refusal into a delivered answer.
        """
        stage, level, _, emitted = ask(
            self._store(),
            self.QUESTION,
            self.ANSWER,
            self.CLAIM,
            "k-thu-sau",
            max_candidates=limit,
        )
        assert stage is Stage.ANSWERABILITY, limit
        assert level is SupportLevel.CONFLICTING, limit
        assert emitted == 0, limit

    def test_the_witness_set_stays_whole_at_every_cut(self) -> None:
        store = self._store()
        for limit in (1, 2, None):
            found = retrieve_for_question(
                MeetingContent(self.QUESTION),
                store,
                scope=SCOPE,
                max_sensitivity=MEETING_AUDIENCE,
                max_candidates=limit,
            )
            assert len(found.witnesses) == 2, limit
            assert len(found.candidates) <= 2

    def test_citing_the_other_card_is_refused_too(self) -> None:
        """Selective citation: whichever of the two is cited, the answer is
        refused, because the comparison is over the store's view and not over
        the model's choice."""
        stage, level, _, emitted = ask(
            self._store(),
            self.QUESTION,
            "Theo ghi chú đã duyệt, deadline báo cáo tháng dự án Kappa là thứ ba.",
            "deadline báo cáo tháng dự án Kappa là thứ ba",
            "k-thu-ba",
        )
        assert stage is Stage.ANSWERABILITY
        assert level is SupportLevel.CONFLICTING
        assert emitted == 0

    def test_one_card_alone_answers(self) -> None:
        """So the refusal above is the contradiction, not the question."""
        single = store_with(
            ("k-thu-sau", "Deadline báo cáo tháng dự án Kappa đã duyệt là thứ sáu.")
        )
        stage, level, _, emitted = ask(
            single, self.QUESTION, self.ANSWER, self.CLAIM, "k-thu-sau"
        )
        assert stage is Stage.DELIVERED
        assert level is SupportLevel.SUPPORTED
        assert emitted == 1


# ===================================================================== #
# Old versus new: a correction is not a contradiction
# ===================================================================== #
class TestACorrectionIsNotAContradiction:
    QUESTION = "Deadline báo cáo tháng dự án Kappa là khi nào?"
    ANSWER = "Theo ghi chú đã duyệt, deadline báo cáo tháng dự án Kappa là thứ ba."
    CLAIM = "deadline báo cáo tháng dự án Kappa là thứ ba"

    def test_a_superseded_card_does_not_refuse_the_new_one(self) -> None:
        """Supersession is how the store records "this replaced that".

        If a superseded card still counted, every corrected fact would be a
        permanent contradiction - which would make recording a correction
        worse than not recording it.
        """
        store = store_with(
            ("k-old", "Deadline báo cáo tháng dự án Kappa đã duyệt là thứ sáu.")
        )
        store.supersede(
            "k-old",
            KnowledgeCard(
                card_id="k-new",
                card_type=CardType.PROJECT,
                claim=MeetingContent(
                    "Deadline báo cáo tháng dự án Kappa đã duyệt là thứ ba."
                ),
                rationale=MeetingContent("ghi chú tổng hợp"),
                source_ref=SOURCE,
                source_date=1.0,
                scope=SCOPE,
                sensitivity=MEETING_AUDIENCE,
            ),
        )
        store.approve("k-new", approved_by="Son")

        found = retrieve_for_question(
            MeetingContent(self.QUESTION),
            store,
            scope=SCOPE,
            max_sensitivity=MEETING_AUDIENCE,
        )
        assert [c.card_id for c in found.witnesses] == ["k-new"]
        assert found.divergent_pairs == ()

        stage, level, _, emitted = ask(
            store, self.QUESTION, self.ANSWER, self.CLAIM, "k-new"
        )
        assert stage is Stage.DELIVERED
        assert level is SupportLevel.SUPPORTED
        assert emitted == 1

    def test_an_expired_card_does_not_refuse_a_current_one(self) -> None:
        store = store_with(
            ("k-current", "Deadline báo cáo tháng dự án Kappa đã duyệt là thứ ba.")
        )
        store.ingest(
            KnowledgeCard(
                card_id="k-expired",
                card_type=CardType.PROJECT,
                claim=MeetingContent(
                    "Deadline báo cáo tháng dự án Kappa đã duyệt là thứ sáu."
                ),
                rationale=MeetingContent("ghi chú tổng hợp"),
                source_ref=SOURCE,
                source_date=0.0,
                scope=SCOPE,
                sensitivity=MEETING_AUDIENCE,
                valid_until=NOW - 1.0,
            )
        )
        store.approve("k-expired", approved_by="Son")

        found = retrieve_for_question(
            MeetingContent(self.QUESTION),
            store,
            scope=SCOPE,
            max_sensitivity=MEETING_AUDIENCE,
        )
        assert [c.card_id for c in found.witnesses] == ["k-current"]
        assert found.divergent_pairs == ()

        stage, _, _, emitted = ask(
            store, self.QUESTION, self.ANSWER, self.CLAIM, "k-current"
        )
        assert stage is Stage.DELIVERED
        assert emitted == 1

    def test_a_card_edited_after_approval_is_not_a_witness(self) -> None:
        """The approved-content digest, reaching the conflict set too."""
        store = store_with(
            ("k-a", "Deadline báo cáo tháng dự án Kappa đã duyệt là thứ ba.")
        )
        card = store.get("k-a")
        assert card is not None
        tampered = replace(
            card,
            claim=MeetingContent("Deadline báo cáo tháng dự án Kappa là thứ sáu."),
        )
        assert not tampered.is_retrievable_at(NOW), (
            "an edit behind the store's back must stop the card being citable"
        )


# ===================================================================== #
# A legitimate list is not a contradiction
# ===================================================================== #
class TestALegitimateListIsNotAContradiction:
    def test_two_milestones_on_one_card_answer(self) -> None:
        """An explicit enumerating frame means the card is listing."""
        store = store_with(
            (
                "k-moc",
                "Dự án Kappa có ba mốc: ngày 10, ngày 15, ngày 20.",
            )
        )
        found = retrieve_for_question(
            MeetingContent("Dự án Kappa có những mốc nào?"),
            store,
            scope=SCOPE,
            max_sensitivity=MEETING_AUDIENCE,
        )
        assert len(found.witnesses) == 1
        assert found.divergent_pairs == ()

    def test_two_unrelated_facts_in_one_scope_still_answer(self) -> None:
        """**The measurement that decided the design.**

        A budget card and a deadline card are *reported* as divergent by
        `conflicts()` - and the answer is still delivered, because nothing
        branches on that report. Had it been wired as a refusal, this would be
        refused, and so would nearly every real answer.
        """
        store = store_with(
            ("k-ngansach", "Ngân sách tổng dự án Kappa đã duyệt là 240 triệu đồng."),
            ("k-deadline", "Deadline báo cáo tháng dự án Kappa đã duyệt là thứ ba."),
        )
        found = retrieve_for_question(
            MeetingContent("Ngân sách tổng dự án Kappa là bao nhiêu?"),
            store,
            scope=SCOPE,
            max_sensitivity=MEETING_AUDIENCE,
        )
        assert found.divergent_pairs == (("k-deadline", "k-ngansach"),), (
            "conflicts() pairs them, which is why it is only a review signal"
        )

        stage, level, _, emitted = ask(
            store,
            "Ngân sách tổng dự án Kappa là bao nhiêu?",
            "Theo ghi chú đã duyệt, ngân sách tổng dự án Kappa là 240 triệu đồng.",
            "ngân sách tổng dự án Kappa là 240 triệu đồng",
            "k-ngansach",
        )
        assert stage is Stage.DELIVERED, (level, "a divergence report must not refuse")
        assert emitted == 1


# ===================================================================== #
# conflicts() itself: what it is and is not
# ===================================================================== #
class TestWhatConflictsActuallyDetects:
    def test_it_pairs_compatible_facts_too(self) -> None:
        """Pinned so nobody reads the output as contradiction detection."""
        store = store_with(
            ("k-ngansach", "Ngân sách tổng dự án Kappa đã duyệt là 240 triệu đồng."),
            ("k-deadline", "Deadline báo cáo tháng dự án Kappa đã duyệt là thứ ba."),
        )
        pairs = store.conflicts()
        assert len(pairs) == 1
        assert {pairs[0].first_id, pairs[0].second_id} == {"k-ngansach", "k-deadline"}

    def test_it_is_scoped(self) -> None:
        """A divergence in a scope nobody asked about must not be reported
        against an answer drawn from another scope."""
        store = store_with(
            ("k-a", "Deadline báo cáo tháng dự án Kappa đã duyệt là thứ sáu."),
            ("k-b", "Deadline báo cáo tháng dự án Kappa đã duyệt là thứ ba."),
        )
        store.ingest(
            KnowledgeCard(
                card_id="other",
                card_type=CardType.PROJECT,
                claim=MeetingContent("Ngân sách dự án Lambda đã duyệt là 90 triệu."),
                rationale=MeetingContent("ghi chú tổng hợp"),
                source_ref=SOURCE,
                source_date=0.0,
                scope="duan-lambda",
                sensitivity=MEETING_AUDIENCE,
            )
        )
        store.approve("other", approved_by="Son")

        assert store.conflicts(scope="duan-lambda") == ()
        assert len(store.conflicts(scope=SCOPE)) == 1
        assert len(store.conflicts()) == 1

    def test_it_excludes_superseded_expired_and_unapproved(self) -> None:
        store = store_with(
            ("k-live", "Deadline báo cáo tháng dự án Kappa đã duyệt là thứ ba.")
        )
        for card_id, kwargs in [
            ("k-pending", {}),
            ("k-expired", {"valid_until": NOW - 1.0}),
        ]:
            store.ingest(
                KnowledgeCard(
                    card_id=card_id,
                    card_type=CardType.PROJECT,
                    claim=MeetingContent(f"Ghi chú khác dự án Kappa {card_id}."),
                    rationale=MeetingContent("ghi chú tổng hợp"),
                    source_ref=SOURCE,
                    source_date=0.0,
                    scope=SCOPE,
                    sensitivity=MEETING_AUDIENCE,
                    **kwargs,  # type: ignore[arg-type]
                )
            )
        store.approve("k-expired", approved_by="Son")
        # k-pending is never approved.
        assert store.conflicts(scope=SCOPE) == ()

    def test_the_report_names_cards_so_an_operator_can_look(self) -> None:
        store = store_with(
            ("k-a", "Deadline báo cáo tháng dự án Kappa đã duyệt là thứ sáu."),
            ("k-b", "Deadline báo cáo tháng dự án Kappa đã duyệt là thứ ba."),
        )
        found = retrieve_for_question(
            MeetingContent("Deadline báo cáo tháng dự án Kappa là khi nào?"),
            store,
            scope=SCOPE,
            max_sensitivity=MEETING_AUDIENCE,
        )
        meta = found.metadata()
        assert meta["divergent_pairs"] == [["k-a", "k-b"]]
        assert meta["divergence_is_a_review_signal_not_a_refusal"] is True

    def test_the_report_carries_no_card_text(self) -> None:
        store = store_with(
            ("k-a", "Deadline báo cáo tháng dự án Kappa đã duyệt là thứ sáu."),
            ("k-b", "Deadline báo cáo tháng dự án Kappa đã duyệt là thứ ba."),
        )
        found = retrieve_for_question(
            MeetingContent("Deadline báo cáo tháng dự án Kappa là khi nào?"),
            store,
            scope=SCOPE,
            max_sensitivity=MEETING_AUDIENCE,
        )
        rendered = f"{found!r} {found.metadata()}"
        for word in ("Deadline", "thứ sáu", "thứ ba", "duyệt"):
            assert word not in rendered, word

    def test_nothing_branches_on_the_divergence_report(self) -> None:
        """Structural, because the temptation is real: the field looks like a
        gate and is not one."""
        import ast
        from pathlib import Path

        src = Path(__file__).resolve().parent.parent / "src" / "meetai"
        for path in sorted(src.rglob("*.py")):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if isinstance(node, (ast.If, ast.While)):
                    names = {
                        inner.attr
                        for inner in ast.walk(node.test)
                        if isinstance(inner, ast.Attribute)
                    } | {
                        inner.id
                        for inner in ast.walk(node.test)
                        if isinstance(inner, ast.Name)
                    }
                    assert "divergent_pairs" not in names, f"{path.name}:{node.lineno}"


class TestADivergenceReportRespectsTheAudience:
    """The report names card ids, so it must not name a card the audience
    cannot see."""

    @staticmethod
    def _mixed() -> KnowledgeStore:
        from meetai.knowledge import Sensitivity

        store = KnowledgeStore(
            now=lambda: NOW,
            source_allowlist=SourceAllowlist(frozenset({SOURCE})),
        )
        for card_id, claim, sensitivity in [
            (
                "vis-group",
                "Deadline báo cáo dự án Kappa đã duyệt là thứ sáu.",
                Sensitivity.GROUP,
            ),
            (
                "vis-private",
                "Deadline báo cáo dự án Kappa đã duyệt là thứ ba.",
                Sensitivity.PRIVATE,
            ),
        ]:
            store.ingest(
                KnowledgeCard(
                    card_id=card_id,
                    card_type=CardType.PROJECT,
                    claim=MeetingContent(claim),
                    rationale=MeetingContent("ghi chú tổng hợp"),
                    source_ref=SOURCE,
                    source_date=0.0,
                    scope=SCOPE,
                    sensitivity=sensitivity,
                )
            )
            store.approve(card_id, approved_by="Son")
        return store

    def test_a_private_card_is_not_named_to_a_group_audience(self) -> None:
        """Measured before the fix: the pair `('vis-group', 'vis-private')`
        was reported to a GROUP audience, disclosing that a private card
        exists in this scope - to the one path the sensitivity filter had
        deliberately excluded it from."""
        store = self._mixed()
        found = retrieve_for_question(
            MeetingContent("Deadline báo cáo dự án Kappa là khi nào?"),
            store,
            scope=SCOPE,
            max_sensitivity=MEETING_AUDIENCE,
        )
        assert [c.card_id for c in found.witnesses] == ["vis-group"]
        assert found.divergent_pairs == (), found.divergent_pairs
        assert "vis-private" not in f"{found.metadata()}"

    def test_the_private_card_is_visible_to_a_private_audience(self) -> None:
        """So the filter above is the audience, not a disappearance."""
        from meetai.knowledge import Sensitivity

        store = self._mixed()
        found = retrieve_for_question(
            MeetingContent("Deadline báo cáo dự án Kappa là khi nào?"),
            store,
            scope=SCOPE,
            max_sensitivity=Sensitivity.PRIVATE,
        )
        assert len(found.witnesses) == 2
        assert found.divergent_pairs == (("vis-group", "vis-private"),)

    def test_the_store_query_takes_the_same_audience_as_the_retrieval(self) -> None:
        """Structural: any store query in the answer path must be given the
        audience, not a default."""
        import ast
        from pathlib import Path

        module = (
            Path(__file__).resolve().parent.parent / "src" / "meetai" / "retrieval.py"
        )
        tree = ast.parse(module.read_text(encoding="utf-8"))
        calls = [
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr in {"retrieve", "conflicts"}
        ]
        assert calls
        for call in calls:
            names = {kw.arg for kw in call.keywords}
            assert "max_sensitivity" in names, ast.dump(call)


class TestSynonymDriftIsStillAFalseAnswer:
    """**A measured false answer this slice does NOT close.**

    Two approved cards disagreeing about one fact, worded differently:

        cited:   "Deadline báo cáo dự án Kappa đã duyệt là thứ sáu."
        present: "Hạn chót nộp báo cáo dự án Kappa đã duyệt là thứ ba."

    Measured result: ``SUPPORTED``, findings empty, **delivered**. The
    cross-card comparison only considers cards whose subject tokens contain
    the claim's, and "hạn chót nộp" shares no subject token with "deadline",
    so the disagreeing card never enters the comparison at all.

    **Why it is not fixed here.** Loosening containment to "any overlap" would
    make a budget card and a deadline card in one scope a conflict - the
    measured over-refusal that decided this whole design. A real fix needs a
    notion of synonymy, which is lexicon work, and this project's rule is that
    a broadened lexicon needs measurement on an owner-controlled eval set
    first. Adding one here to make a test pass would be the exact move
    ``AGENTS.md`` forbids.

    So it is pinned as current behaviour. A known hole recorded in the suite
    beats a hole found in a pilot.
    """

    def test_a_differently_worded_disagreement_is_not_caught(self) -> None:
        store = store_with(
            ("syn-sau", "Deadline báo cáo dự án Kappa đã duyệt là thứ sáu."),
            ("syn-ba", "Hạn chót nộp báo cáo dự án Kappa đã duyệt là thứ ba."),
        )
        stage, level, rules, emitted = ask(
            store,
            "Deadline báo cáo dự án Kappa là khi nào?",
            "Theo ghi chú đã duyệt, deadline báo cáo dự án Kappa là thứ sáu.",
            "deadline báo cáo dự án Kappa là thứ sáu",
            "syn-sau",
        )
        assert stage is Stage.DELIVERED, (
            "if this now refuses, the synonym hole closed - invert this test "
            "and move the residual out of PROJECT_STATE rather than deleting it"
        )
        assert level is SupportLevel.SUPPORTED
        assert rules == ()
        assert emitted == 1

    def test_the_same_wording_IS_caught(self) -> None:
        """So the hole is the wording, not the mechanism being absent."""
        store = store_with(
            ("same-sau", "Deadline báo cáo dự án Kappa đã duyệt là thứ sáu."),
            ("same-ba", "Deadline báo cáo dự án Kappa đã duyệt là thứ ba."),
        )
        stage, level, _, emitted = ask(
            store,
            "Deadline báo cáo dự án Kappa là khi nào?",
            "Theo ghi chú đã duyệt, deadline báo cáo dự án Kappa là thứ sáu.",
            "deadline báo cáo dự án Kappa là thứ sáu",
            "same-sau",
        )
        assert stage is Stage.ANSWERABILITY
        assert level is SupportLevel.CONFLICTING
        assert emitted == 0

    def test_the_divergence_report_does_see_it(self) -> None:
        """The one thing the report adds: it is subject-agnostic, so it
        surfaces the pair an operator would want to look at - while refusing
        nothing, which is why it is not a fix."""
        store = store_with(
            ("syn-sau", "Deadline báo cáo dự án Kappa đã duyệt là thứ sáu."),
            ("syn-ba", "Hạn chót nộp báo cáo dự án Kappa đã duyệt là thứ ba."),
        )
        found = retrieve_for_question(
            MeetingContent("Deadline báo cáo dự án Kappa là khi nào?"),
            store,
            scope=SCOPE,
            max_sensitivity=MEETING_AUDIENCE,
        )
        assert found.divergent_pairs == (("syn-ba", "syn-sau"),)


class TestMilestoneEnumerationAcrossCardsOverRefuses:
    """A measured over-refusal, recorded rather than chased.

    Two cards legitimately describing two milestones are refused, because the
    ordinal and the date are both stripped as *values*, so both cards' subject
    tokens fold to the same set and the ordinals then read as disagreeing
    numbers. The one-card version of the same content is supported, and
    ``_ENUMERATING`` has no cross-card equivalent.

    Deny-biased, so it costs a silence rather than a false answer - the
    opposite direction from the synonym hole above, and the cheap one.
    """

    def test_two_milestone_cards_are_refused(self) -> None:
        store = store_with(
            ("m-1", "Giai đoạn 1 dự án Kappa xong ngày 10."),
            ("m-2", "Giai đoạn 2 dự án Kappa xong ngày 20."),
        )
        stage, level, rules, emitted = ask(
            store,
            "Giai đoạn 2 dự án Kappa xong khi nào?",
            "Theo ghi chú đã duyệt, giai đoạn 2 dự án Kappa xong ngày 20.",
            "giai đoạn 2 dự án Kappa xong ngày 20",
            "m-2",
        )
        assert stage is Stage.ANSWERABILITY, (
            "if this now answers, the cross-card enumeration limit closed - "
            "invert this test rather than deleting it"
        )
        assert level is SupportLevel.CONFLICTING
        assert emitted == 0
        assert rules and rules[0].startswith("cards_disagree:")


# ===================================================================== #
# The anchorless path, which conflicts() cannot see
# ===================================================================== #
class TestTheAnchorlessPathIsStillCoveredByPolarity:
    """`conflicts()` compares content hashes and knows nothing about meaning.

    The case it cannot distinguish - two cards about consent with opposite
    polarity - is covered by `assess`, and that is where it belongs.
    """

    def test_opposite_polarity_refuses(self) -> None:
        store = store_with(
            ("k-yes", "Son đồng ý phương án D."),
            ("k-no", "Son không đồng ý phương án D."),
        )
        outcome = assess(
            question=MeetingContent("Son có đồng ý phương án D không?"),
            answer=MeetingContent("Theo ghi chú đã duyệt, Son đồng ý phương án D."),
            claims=(
                Claim(
                    text=MeetingContent("Son đồng ý phương án D"),
                    kind=ClaimKind.GROUNDED,
                    evidence_id="k-yes",
                ),
            ),
            cards=store.retrieve(scope=SCOPE, max_sensitivity=MEETING_AUDIENCE),
            cited_ids=("k-yes",),
            now=NOW,
        )
        assert outcome.verdict is Verdict.UNSUPPORTED
        assert outcome.level is SupportLevel.CONFLICTING
        assert outcome.findings == ("cards_disagree:polarity",)


# ===================================================================== #
# The dry-run shows it
# ===================================================================== #
class TestTheDryRunSurfacesIt:
    def test_the_contradiction_case_reports_its_divergence(self) -> None:
        from meetai.dryrun import CASES, retrieve_for

        store = build_store()
        case = next(c for c in CASES if c.case_id.startswith("D4."))
        found = retrieve_for(case, store)
        assert found.divergent_pairs == (("card-deadline-ba", "card-deadline-sau"),)

    def test_a_single_card_scope_reports_none(self) -> None:
        from meetai.dryrun import CASES, retrieve_for

        store = build_store()
        case = next(c for c in CASES if c.case_id.startswith("D1."))
        assert retrieve_for(case, store).divergent_pairs == ()


class TestRankingCannotSeeAnOrdinalSubject:
    """Measured at 2ed4519, and it reaches the end of the local path.

    ``Ai phu trach kiem thu giai doan 2?`` against a store holding one card
    per phase: **both cards score 9**. Identical. The digit that says *which
    phase* is stripped as a **value** before tokenising - the same rule that
    stops a card ranking highly for sharing a number - so the subject the
    question is actually about is gone by the time anything is compared.

    The tie is then broken by the deterministic ordering, so which card ranks
    first is not a judgement about relevance at all. Hand the top-ranked one
    to ``assess`` and the result is ``SUPPORTED`` with empty findings, because
    the claim quoting it **is true** - it just answers a different question.
    Corpus case ``Q.attribute.01`` records the ``assess`` half; this records
    that retrieval does not save it, and that the whole local path delivers.

    **Not fixed here.** A fix means either keeping ordinals as subject tokens -
    the candidate measured in ``test_normalisation_study`` and not approved -
    or comparing the claim's subject against the question's, which is a new
    checking layer that would raise over-refusal and has no measurement yet.
    Pinned as current behaviour: when it is fixed, **invert** these
    assertions rather than deleting them.
    """

    @staticmethod
    def _store() -> KnowledgeStore:
        return store_with(
            ("P1", "Khuê phụ trách kiểm thử giai đoạn 1 dự án Kappa."),
            ("P2", "Trâm phụ trách kiểm thử giai đoạn 2 dự án Kappa."),
        )

    def test_both_phases_score_identically(self) -> None:
        found = retrieve_for_question(
            MeetingContent("Ai phụ trách kiểm thử giai đoạn 2 dự án Kappa?"),
            self._store(),
            scope=SCOPE,
            max_sensitivity=MEETING_AUDIENCE,
        )
        scores = {scored.card.card_id: scored.score for scored in found.candidates}
        assert scores == {"P1": 9, "P2": 9}, (
            "ranking da phan biet duoc ordinal; dao assertion nay thay vi xoa"
        )

    def test_the_ordinal_is_absent_from_the_subject_tokens(self) -> None:
        """The cause, stated separately from the symptom.

        So that a change which happens to reorder the tie does not look like a
        fix. What would be a fix is the ordinal surviving tokenisation.
        """
        tokens = subject_tokens("kiểm thử giai đoạn 2")
        assert not {token for token in tokens if any(ch.isdigit() for ch in token)}
        assert subject_tokens("giai đoạn 1") == subject_tokens("giai đoạn 2")

    def test_the_whole_local_path_delivers_the_wrong_phase(self) -> None:
        """The consequence, measured end to end rather than inferred.

        The claim is a verbatim quotation of an approved, in-date, correctly
        cited card, so every check this project has passes honestly. What
        reaches the meeting is a true sentence about the phase nobody asked
        about, under an attribution frame that presents it as the answer.
        """
        question = MeetingContent("Ai phụ trách kiểm thử giai đoạn 2 dự án Kappa?")
        found = retrieve_for_question(
            question,
            self._store(),
            scope=SCOPE,
            max_sensitivity=MEETING_AUDIENCE,
        )
        top = found.candidates[0].card.card_id
        assert top == "P1", "thu tu da doi; case nay doc card top-ranked"
        claim = "Khuê phụ trách kiểm thử giai đoạn 1"
        assessment = assess(
            question=question,
            answer=MeetingContent(f"Theo ghi chú đã duyệt, {claim}."),
            claims=(Claim(text=MeetingContent(claim), evidence_id=top),),
            cards=found.witnesses,
            cited_ids=(top,),
            now=NOW,
        )
        assert assessment.permits_answering is True, (
            "lo nay da dong; dao assertion nay va cap nhat Q.attribute.01"
        )
        assert assessment.findings == ()
