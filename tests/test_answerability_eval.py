"""Evaluation harness for the answerability layer.

Reports **false answer** and **false abstention** per group, each with its own
denominator, and never pools them. The two are not commensurable: a false
answer is MeetAI stating something the evidence does not support, and a false
abstention is MeetAI refusing a relay it exists to perform. One accuracy number
over that mixture would let the cheap direction pay for the expensive one -
the same reason ``meetai.evaluation`` has no accuracy and the S2.3 scorer has
no F1.

Two agreement rules, as in the authority corpus:

1. A case agrees when the module returns the labelled level. A disagreement is
   a finding, not a tolerance.
2. A case labelled with a known disagreement must **keep** disagreeing, so a
   fix shows up as a failure telling the author to clear the flag.

Nothing in this file is a model. Every judgement is a comparison between a
hand-written label and a deterministic return value.
"""

from __future__ import annotations

import ast
import re
from collections import Counter
from pathlib import Path

import pytest

from meetai.answerability import (
    AnswerabilityAssessment,
    Claim,
    ClaimKind,
    SupportLevel,
    Verdict,
    assess,
)
from meetai.content import MeetingContent
from meetai.knowledge import CardType, KnowledgeCard
from meetai.response import EvidenceStatus
from tests.conftest import personal_identifier_markers
from tests.corpus.answerability_types import (
    AnswerabilityCase,
    CardSpec,
    ExpectedOutcome,
    RiskGroup,
)
from tests.corpus.answerability_vi import CASES, CORPUS

CORPUS_PATH = Path(__file__).resolve().parent / "corpus" / "answerability_vi.py"
TYPES_PATH = Path(__file__).resolve().parent / "corpus" / "answerability_types.py"
HANDOFF = (
    Path(__file__).resolve().parent.parent
    / "docs"
    / "handoff"
    / "MeetAI_Ho_so_ban_giao_Claude_Code_v1.0.md"
)

_STATUSES = {status.value: status for status in EvidenceStatus}
_TYPES = {card_type.value: card_type for card_type in CardType}


def build_card(spec: CardSpec) -> KnowledgeCard:
    """Turn a corpus spec into a real card.

    The corpus names statuses and types as strings so it cannot import the
    code it judges; this is the only place the mapping happens.
    """
    status = _STATUSES[spec.status]
    built = KnowledgeCard(
        card_id=spec.card_id,
        card_type=_TYPES[spec.card_type],
        claim=MeetingContent(spec.claim),
        rationale=MeetingContent("ly do tong hop"),
        source_ref="note://synthetic",
        source_date=0.0,
        approval_status=status,
        approved_by="Son" if status is EvidenceStatus.APPROVED else None,
        valid_from=spec.valid_from,
        valid_until=spec.valid_until,
        superseded_by=spec.superseded_by,
    )
    # An approved card has to witness the content it was approved at, the way
    # the store does. Building one without the digest leaves it uncitable -
    # which is the invariant working, and the reason this helper exists rather
    # than each case reproducing the digest step.
    if status is EvidenceStatus.APPROVED:
        built = built.witnessed_approval(approved_by="Son")
    return built


def run_case(case: AnswerabilityCase) -> AnswerabilityAssessment:
    return assess(
        question=MeetingContent(case.question),
        answer=MeetingContent(case.answer),
        claims=tuple(
            Claim(
                text=MeetingContent(spec.text),
                kind=ClaimKind(spec.kind),
                evidence_id=spec.evidence_id,
            )
            for spec in case.claims
        ),
        cards=tuple(build_card(spec) for spec in case.cards),
        cited_ids=case.cited_ids,
        now=case.now,
    )


# ---------------------------------------------------------------------- #
# Known-gap ledger
#
# A case flagged ``known_gap`` is one where the module **disagrees with
# policy** and the mechanism that would close it is named in the case. The
# flag is not a tolerance: the ceilings below may only be lowered, and the
# agreement tests still hold every unflagged case to its label.
#
# Measured at 2ed4519 on 2026-10-09, 51 cases:
#
#   false answer     R.crosscard.01  Y.letter.01  Q.attribute.01
#   false abstention R.paraphrase.01 N.corrected.01  N.corrected.02
#   wrong level only N.corrected.03
#
# The three false answers are the expensive direction and each is a distinct
# mechanism, not three views of one bug:
#
#   - R.crosscard.01 - two approved cards disagree, worded differently, so
#     the cross-card check does not pair them. No synonym notion exists.
#   - Y.letter.01    - the subject differs by one character, which
#     ``subject_tokens`` drops as noise.
#   - Q.attribute.01 - the claim is true and cited correctly, and answers a
#     different question. Nothing compares claim subject to question subject.
#
# None is closed in this slice, deliberately. Each needs either a vocabulary
# or a tokeniser change, both of which this project requires measuring on an
# eval set the operator controls **before** landing - and a repair made to
# turn the suite green is the failure mode AGENTS.md names outright.
# ---------------------------------------------------------------------- #

AXIS_CONSTRAINTS: dict[str, dict[str, frozenset[str]]] = {
    "supported": {
        "claim_support": frozenset({"supported"}),
        "citation_validity": frozenset({"valid", "n/a"}),
        "answers_question": frozenset({"yes"}),
    },
    "unsupported": {
        "claim_support": frozenset({"absent", "wrong_subject"}),
        "citation_validity": frozenset({"valid"}),
    },
    "conflicting": {
        "claim_support": frozenset({"conflicting"}),
    },
    "no_citable_evidence": {
        "citation_validity": frozenset({"absent", "not_retrievable"}),
    },
    "partial_undeclared": {
        "claim_support": frozenset({"supported"}),
        "citation_validity": frozenset({"valid"}),
    },
    "gap_asserts": {
        "claim_support": frozenset({"absent"}),
    },
    "malformed": {
        "claim_support": frozenset({"n/a", "supported"}),
        "citation_validity": frozenset({"n/a", "valid"}),
    },
    "unverifiable_claim": {
        "claim_support": frozenset({"unverifiable"}),
        "citation_validity": frozenset({"valid"}),
    },
    "evidence_self_contradictory": {
        "claim_support": frozenset({"unverifiable"}),
    },
}
"""Which axis values each level permits. **Total over the levels.**

Derived from the combinations the 51 cases use, not written from opinion, so
it states what the corpus does and a future case that departs from it has to
say why. Deliberately an **implication** rather than a function: the axes do
not determine the level - ``unverifiable_claim`` and
``evidence_self_contradictory`` share an axis combination, because one is "the
claim could not be checked" and the other is "the card cannot hold its own
story", and no triple of axis values tells those apart.

A level absent from this table used to mean "unconstrained", which is how
``Q.attribute.01`` carried ``claim_support="supported"`` alongside a level
defined as the value being absent from the card. A test now asserts the table
covers every level, so absence is no longer a silent default.

**Why ``malformed`` permits more than the corpus currently shows.** Derived
strictly, it would allow only ``n/a``/``n/a``, because all three existing
``F.*`` cases are ones where nothing *could* be checked. But ``MALFORMED`` is a
**structural** verdict - the answer's shape does not match its claims - and
that is orthogonal to whether the claim happens to be backed. A planned case
makes this concrete: an answer whose claim is true and properly cited, with an
**extra unbacked fragment** appended, is structurally malformed while its claim
support is genuinely ``supported``. Derived-strictly, the table would have
forced that case's author to write ``n/a`` for an axis they knew the answer to,
and a constraint that pressures an author into fudging an axis defeats the
purpose of having axes. Found by review, before the case was written.

**``answers_question`` is constrained for ``supported`` only, and that is not
an oversight.** For every other level both values are legitimate - a claim can
be ``UNSUPPORTED`` whether or not it addresses the attribute asked. More
importantly, the harness **cannot** cross-check this axis against anything: the
predicate it encodes, "does the claim answer the question", is precisely the
check the module does not implement. It is author-asserted and unverifiable
here, which is a limit worth stating rather than hiding behind constraints that
only restate what the corpus happens to contain today.
"""

# **What the ledger does NOT check, found by review and measured.** A flagged
# case's ``expected`` is the author's policy judgement, and the whole premise is
# that the module disagrees with it - so nothing can cross-check it against
# behaviour. Concretely: a ``known_gap`` case whose ``expected`` is wrong, but
# whose axes were written to agree with that wrong level, passes every test
# here. ``settled()`` excludes it from the agreement test, and
# ``test_a_known_gap_still_disagrees`` only asks that the module disagree with
# *something*, which it does.
#
# There is no fix inside the harness: the thing that would adjudicate is the
# operator's own label. It is why the eval document exists, and why these
# labels are marked proposed rather than settled.

FALSE_ANSWER_CEILING: dict[str, int] = {
    "R_paraphrase": 1,
    "Y_designator": 1,
    "Q_question_mismatch": 1,
}
"""Per group, and **only lowerable**. Absent means zero and stays zero."""

FALSE_ABSTENTION_CEILING: dict[str, int] = {
    "R_paraphrase": 1,
    "N_multi_event": 2,
}
"""Same rule. These are capability costs, not safety failures - but they are
the number that says what the fail-closed design costs, so they are measured
rather than waved through."""


def known_gaps() -> tuple[AnswerabilityCase, ...]:
    return tuple(case for case in CASES if case.known_gap)


def settled() -> tuple[AnswerabilityCase, ...]:
    """Cases the module is expected to agree with. The suite's real floor."""
    return tuple(case for case in CASES if not case.known_gap)


class TestCorpusIntegrity:
    """Make label-copying structurally impossible."""

    @staticmethod
    def _source(path: Path) -> str:
        return path.read_text(encoding="utf-8")

    @pytest.mark.parametrize("path", [CORPUS_PATH, TYPES_PATH])
    def test_corpus_cannot_consult_what_it_judges(self, path: Path) -> None:
        imported: set[str] = set()
        for node in ast.walk(ast.parse(self._source(path))):
            if isinstance(node, ast.Import):
                imported.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module)
        assert not any(name.startswith(("meetai", "benchmarks")) for name in imported), (
            imported
        )

    def test_every_case_is_a_literal(self) -> None:
        """No loop, no comprehension. Twenty-odd literals can be read."""
        for node in ast.walk(ast.parse(self._source(CORPUS_PATH))):
            assert not isinstance(
                node,
                ast.ListComp
                | ast.SetComp
                | ast.DictComp
                | ast.GeneratorExp
                | ast.For
                | ast.While
                | ast.Lambda,
            ), ast.dump(node)[:120]

    def test_only_permitted_constructors_are_called(self) -> None:
        permitted = {"AnswerabilityCase", "CardSpec", "ClaimSpec", "Corpus"}
        called: set[str] = set()
        for node in ast.walk(ast.parse(self._source(CORPUS_PATH))):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                called.add(node.func.id)
        assert called <= permitted, sorted(called - permitted)

    def test_case_ids_are_unique(self) -> None:
        ids = [case.case_id for case in CASES]
        duplicates = [name for name, count in Counter(ids).items() if count > 1]
        assert not duplicates, duplicates

    def test_every_minimal_pair_resolves(self) -> None:
        ids = {case.case_id for case in CASES}
        dangling = [
            (case.case_id, case.minimal_pair)
            for case in CASES
            if case.minimal_pair and case.minimal_pair not in ids
        ]
        assert not dangling, dangling

    @pytest.mark.parametrize("case", CASES, ids=lambda c: c.case_id)
    def test_a_handoff_citation_resolves_to_a_policy_item(
        self, case: AnswerabilityCase
    ) -> None:
        """Content-checked, like the authority corpus's citations.

        That corpus cited a blank line and the whole block one line early for
        several slices. The check costs nothing and the mechanism it protects -
        a label that must cite policy - is the only thing stopping labels from
        being derived from the code.
        """
        match = re.match(r"handoff:(\d+)$", case.policy_basis)
        if match is None:
            assert case.policy_basis.startswith("operator:"), case.policy_basis
            return
        lines = HANDOFF.read_text(encoding="utf-8").splitlines()
        index = int(match.group(1))
        assert 1 <= index <= len(lines), f"{case.case_id}: dong {index}"
        content = lines[index - 1].strip()
        assert content and not content.startswith("#"), (
            f"{case.case_id}: dong {index} trong hoac la tieu de"
        )
        assert re.match(r"^(-|\d+\.)\s", content), (
            f"{case.case_id}: dong {index} khong phai muc chinh sach: {content[:60]!r}"
        )

    def test_no_real_identifiers(self) -> None:
        """The markers come from ``personal_identifier_markers``, not a literal.

        The literal tuple here held the operator's account name and an email
        fragment - so this test, whose job is keeping personal data out of the
        corpus, was itself the place the repository stored some.
        """
        source = self._source(CORPUS_PATH).lower()
        for marker in personal_identifier_markers():
            assert marker not in source, marker

    @pytest.mark.parametrize("case", CASES, ids=lambda c: c.case_id)
    def test_the_axes_imply_the_expected_level(self, case: AnswerabilityCase) -> None:
        """The implication the types module promised and nothing checked.

        ``answerability_types`` says *"a case whose axes cannot produce its
        expected level is a labelling mistake, and a test checks the
        implication rather than trusting it"*. It did not. ``claim_support``
        and ``citation_validity`` were read by exactly one test about variety,
        and ``answers_question`` by none - so the axes were write-only and the
        docstring overstated.

        The error it was written for: ``Q.attribute.01`` carried
        ``claim_support="supported"``, ``citation_validity="valid"`` and
        ``expected=UNSUPPORTED``, a level defined as the claim's subject or
        value being **absent from the card it cites**. False of a verbatim
        span, and it would have given an operator a reason that misdescribes
        the card.

        **Stated precisely, because the first version of this docstring was
        not:** that case was relabelled two commits before this test existed,
        so the test did not catch it and cannot fail on the present 51 cases.
        It is a **forward guard**, and the table being the corpus's own image
        is exactly why - every constrained slot permits precisely what the
        corpus uses. Verified that it fires on the mislabelling that actually
        happened, by re-applying it in memory.
        """
        constraints = AXIS_CONSTRAINTS[case.expected.value]
        for axis, permitted in constraints.items():
            actual = getattr(case, axis)
            assert actual in permitted, (
                f"{case.case_id}: muc do {case.expected.value} khong cho "
                f"{axis}={actual!r} (chi nhan {sorted(permitted)}). Neu claim "
                f"dung nhung tra loi sai cau hoi, muc do la "
                f"PARTIAL_UNDECLARED chu khong phai UNSUPPORTED."
            )

    def test_the_constraint_table_covers_every_level(self) -> None:
        """So a new level cannot arrive unconstrained.

        Before this, a level missing from the table meant "anything goes", and
        that silent default is what let a supported claim sit under a level
        defined as the value being absent from its card.
        """
        assert set(AXIS_CONSTRAINTS) == {o.value for o in ExpectedOutcome}, set(
            AXIS_CONSTRAINTS
        ) ^ {o.value for o in ExpectedOutcome}
        for level, constraints in AXIS_CONSTRAINTS.items():
            assert constraints, f"{level}: rang buoc rong thi vo nghia"
            assert set(constraints) <= {
                "claim_support",
                "citation_validity",
                "answers_question",
            }, (level, sorted(constraints))

    def test_the_corpus_outcomes_mirror_the_module_levels(self) -> None:
        """An exact correspondence that nothing checked until now.

        ``ExpectedOutcome`` and ``SupportLevel`` hold the same nine values, and
        they must: the corpus states levels as strings precisely so it cannot
        import the enum it grades, which means **nothing** would notice a new
        ``SupportLevel`` member. The corpus would simply never express it, and
        a whole class of module behaviour would go unmeasured while the suite
        stayed green - the exact failure this corpus was extended to fix.

        Compared by value rather than by identity, so the corpus keeps its
        independence while the correspondence is still enforced.
        """
        assert {o.value for o in ExpectedOutcome} == {
            level.value for level in SupportLevel
        }, {o.value for o in ExpectedOutcome} ^ {level.value for level in SupportLevel}

    def test_every_outcome_maps_to_a_verdict_the_module_has(self) -> None:
        """Every member's verdict is one the module actually has.

        **This test does NOT catch a newly added member**, and an earlier
        docstring claimed it did. ``ExpectedOutcome.verdict`` is an if/elif
        chain whose codomain is the three strings already produced by existing
        members, so the result **set** is invariant under adding a member: a
        new one falls through to ``return "unsupported"`` and the set is
        unchanged. Measured with a ten-member mimic of the enum.

        What does catch that member is
        :meth:`test_the_corpus_outcomes_mirror_the_module_levels` and
        :meth:`test_the_constraint_table_covers_every_level` - both fire.
        Checked, rather than assumed, after the review pointed out the claim.

        So this test keeps a narrower job worth keeping: it asserts per member
        that the string returned is one ``Verdict`` really defines, which is
        what stops a typo in the chain from inventing a fourth verdict.
        """
        legal = {verdict.value for verdict in Verdict}
        for outcome in ExpectedOutcome:
            assert outcome.verdict in legal, (outcome.value, outcome.verdict)
        assert {outcome.verdict for outcome in ExpectedOutcome} == legal

    def test_the_third_axis_is_actually_separated(self) -> None:
        """One non-default value in 51 cases is not a separated axis.

        It had exactly that when the axis was added, which is how the
        inconsistency above survived: three other cases whose own notes say
        the claim does not answer the question were left at the default.
        """
        answering = Counter(case.answers_question for case in CASES)
        assert answering["no"] >= 3, answering

    def test_the_two_axes_are_both_used(self) -> None:
        """A corpus where one axis never varies is not separating them.

        ``claim_support`` and ``citation_validity`` exist to be independent, so
        the corpus has to contain cases where they disagree - which is the
        pending-card case: perfect wording, unusable card.
        """
        supports = {case.claim_support for case in CASES}
        validities = {case.citation_validity for case in CASES}
        assert len(supports) >= 3, supports
        assert len(validities) >= 3, validities
        crossed = [
            case.case_id
            for case in CASES
            if case.claim_support == "supported"
            and case.citation_validity == "not_retrievable"
        ]
        assert crossed, "thieu case wording dung nhung card khong dung duoc"


class TestCoverage:
    def test_every_group_has_cases(self) -> None:
        present = {case.group for case in CASES}
        assert present == set(RiskGroup), set(RiskGroup) - present

    def test_every_outcome_is_exercised(self) -> None:
        present = {case.expected for case in CASES}
        assert present == set(ExpectedOutcome), set(ExpectedOutcome) - present

    def test_both_directions_are_represented(self) -> None:
        """A corpus of only refusals would reward refusing everything."""
        answerable = [c for c in CASES if c.expected.permits_answering]
        refusals = [c for c in CASES if not c.expected.permits_answering]
        assert len(answerable) >= 5, len(answerable)
        assert len(refusals) >= 5, len(refusals)

    def test_the_substitution_group_has_a_supported_counterpart(self) -> None:
        """Otherwise it measures refusing, not discriminating."""
        group = [c for c in CASES if c.group is RiskGroup.V_SUBSTITUTION]
        assert group
        paired = [c for c in group if c.minimal_pair]
        assert len(paired) >= 3, [c.case_id for c in group if not c.minimal_pair]


class TestAgreement:
    @pytest.mark.parametrize("case", settled(), ids=lambda c: c.case_id)
    def test_case_matches_its_label(self, case: AnswerabilityCase) -> None:
        assessment = run_case(case)
        assert assessment.level.value == case.expected.value, (
            f"{case.case_id}: nhan noi {case.expected.value}, module tra "
            f"{assessment.level.value}; findings={list(assessment.findings)}"
        )

    @pytest.mark.parametrize("case", known_gaps(), ids=lambda c: c.case_id)
    def test_a_known_gap_still_disagrees(self, case: AnswerabilityCase) -> None:
        """Invert-on-fix. A closed gap **fails here**, which is the point.

        Without this the flag would be a permanent excuse: the gap could be
        fixed, or could drift to a different wrong answer, and nothing would
        say so. Failing on the fix is how the next author learns the ledger
        entry is stale rather than inheriting it.
        """
        assessment = run_case(case)
        assert assessment.level.value != case.expected.value, (
            f"{case.case_id}: module GIO DA DONG Y voi nhan "
            f"({case.expected.value}). Day la tin tot: xoa known_gap va "
            f"gap_reason khoi case, ha tran tuong ung trong "
            f"FALSE_ANSWER_CEILING / FALSE_ABSTENTION_CEILING, roi chay lai. "
            f"Dung xoa test nay."
        )

    @pytest.mark.parametrize("case", CASES, ids=lambda c: c.case_id)
    def test_every_gap_names_a_mechanism(self, case: AnswerabilityCase) -> None:
        """A reason that does not name what is missing is not a reason."""
        if not case.known_gap:
            assert not case.gap_reason, case.case_id
            return
        assert len(case.gap_reason) > 60, f"{case.case_id}: {case.gap_reason!r}"
        assert not any(
            vague in case.gap_reason.lower()
            for vague in ("chua lam", "sau nay", "todo", "can them thoi gian")
        ), f"{case.case_id}: {case.gap_reason!r}"

    @pytest.mark.parametrize("case", settled(), ids=lambda c: c.case_id)
    def test_permission_follows_the_level(self, case: AnswerabilityCase) -> None:
        """``permits_answering`` must never disagree with the level.

        Two ways to ask the same question is two ways for them to drift, so
        the agreement is asserted rather than assumed.
        """
        assessment = run_case(case)
        assert assessment.permits_answering is case.expected.permits_answering
        assert bool(assessment) is assessment.permits_answering


class TestPerGroupRates:
    """False answer, false abstention and unclear - per group, never pooled.

    Three axes now, because the module has three states. ``unclear`` is
    reported on its own and is **not** folded into either error column: it is
    neither a false answer nor a false abstention, it is the module saying it
    could not check. Counting it as an error would push towards guessing;
    counting it as a success would hide how much of the corpus goes
    unverified. It is the number that says how much capability the fail-closed
    design costs.

    No pooled accuracy, and a test asserts the absence.
    """

    @staticmethod
    def _rates() -> dict[str, dict[str, tuple[int, int]]]:
        """``group -> axis -> (hits, denominator)``."""
        table: dict[str, dict[str, tuple[int, int]]] = {}
        for group in RiskGroup:
            cases = [c for c in CASES if c.group is group]
            must_refuse = [c for c in cases if not c.expected.permits_answering]
            must_answer = [c for c in cases if c.expected.permits_answering]
            results = {case.case_id: run_case(case) for case in cases}
            flagged = {case.case_id for case in cases if case.known_gap}
            table[group.value] = {
                "false_answer_known_gap": (
                    sum(
                        1
                        for c in must_refuse
                        if c.case_id in flagged and results[c.case_id].permits_answering
                    ),
                    len(must_refuse),
                ),
                "false_abstention_known_gap": (
                    sum(
                        1
                        for c in must_answer
                        if c.case_id in flagged
                        and not results[c.case_id].permits_answering
                    ),
                    len(must_answer),
                ),
                "false_answer": (
                    sum(
                        1
                        for c in must_refuse
                        if c.case_id not in flagged
                        and results[c.case_id].permits_answering
                    ),
                    len(must_refuse),
                ),
                "false_abstention": (
                    sum(
                        1
                        for c in must_answer
                        if c.case_id not in flagged
                        and not results[c.case_id].permits_answering
                    ),
                    len(must_answer),
                ),
                "unclear": (
                    sum(
                        1 for c in cases if results[c.case_id].verdict is Verdict.UNCLEAR
                    ),
                    len(cases),
                ),
            }
        return table

    def test_no_false_answer_in_any_group(self) -> None:
        """The expensive direction. Zero per group **among unflagged cases**.

        The flagged ones are counted by
        :meth:`test_known_gaps_stay_within_their_ceiling`, which is a
        different assertion: this one says no *new* false answer appears, that
        one says the recorded ones do not multiply.
        """
        offenders = {
            group: axes["false_answer"]
            for group, axes in self._rates().items()
            if axes["false_answer"][0]
        }
        assert not offenders, offenders

    def test_no_false_abstention_in_any_group(self) -> None:
        """The cost direction, measured rather than assumed acceptable.

        Unflagged cases only, for the reason above.
        """
        offenders = {
            group: axes["false_abstention"]
            for group, axes in self._rates().items()
            if axes["false_abstention"][0]
        }
        assert not offenders, offenders

    def test_known_gaps_stay_within_their_ceiling(self) -> None:
        """The recorded holes may not grow, and may not spread to new groups.

        Two separate assertions, because they fail for different reasons: a
        count above the ceiling means a change made an existing hole wider,
        and a group absent from the ceiling dict means a change opened a hole
        somewhere the ledger never claimed one.
        """
        for axis, ceiling in (
            ("false_answer_known_gap", FALSE_ANSWER_CEILING),
            ("false_abstention_known_gap", FALSE_ABSTENTION_CEILING),
        ):
            for group, axes in self._rates().items():
                count = axes[axis][0]
                allowed = ceiling.get(group, 0)
                assert count <= allowed, (
                    f"{group}/{axis}: {count} > tran {allowed}. Mot thay doi "
                    f"vua lam rong mot lo da ghi, hoac mo mot lo o nhom "
                    f"ledger khong he khai."
                )

    def test_a_ceiling_entry_is_backed_by_a_flagged_case(self) -> None:
        """No ceiling may outlive the gap it was raised for.

        A ceiling left behind after a fix is a budget for a future
        regression - it would let a brand-new false answer land silently in
        the group where an old one used to be.
        """
        flagged_groups = {case.group.value for case in known_gaps()}
        for ceiling in (FALSE_ANSWER_CEILING, FALSE_ABSTENTION_CEILING):
            stale = set(ceiling) - flagged_groups
            assert not stale, f"tran con lai nhung khong con gap: {sorted(stale)}"

    def test_the_ledger_is_not_empty_and_not_the_whole_corpus(self) -> None:
        """Both degenerate ledgers are mistakes, and they look different.

        Empty means the corpus found nothing, which for a corpus written to
        probe untested shapes means it was written to agree. Everything
        flagged means the labels stopped constraining anything at all.
        """
        assert known_gaps(), "corpus khong tim ra gi - nhan co the da duoc viet theo code"
        assert len(known_gaps()) < len(CASES) // 3, (
            f"{len(known_gaps())}/{len(CASES)} case duoc co known_gap - "
            f"nhan khong con rang buoc gi"
        )

    def test_unclear_is_reported_and_bounded_to_its_groups(self) -> None:
        """``UNCLEAR`` must land where the corpus says it should, and nowhere else.

        A fail-closed design can always reach zero false answers by returning
        ``UNCLEAR`` everywhere, so the useful assertion is not "unclear is
        low" but "unclear appears exactly where a case is labelled unclear".
        That is what stops the closure from being bought with silence.
        """
        for case in settled():
            result = run_case(case)
            assert (result.verdict is Verdict.UNCLEAR) is (
                case.expected.verdict == "unclear"
            ), (
                f"{case.case_id}: verdict={result.verdict.value}, nhan={case.expected.verdict}"
            )

    def test_the_verdict_matches_the_corpus_three_state_label(self) -> None:
        """The corpus states the verdict itself, without importing the enum.

        So a mislabelled verdict is a corpus bug the harness catches rather
        than an assumption it inherits from the code it is judging.
        """
        for case in settled():
            assert run_case(case).verdict.value == case.expected.verdict, case.case_id

    def test_every_group_has_a_denominator_on_at_least_one_axis(self) -> None:
        for group, axes in self._rates().items():
            assert any(denominator for _, denominator in axes.values()), group

    def test_there_is_no_pooled_accuracy(self) -> None:
        """Asserted, because the temptation is to add one later."""
        axes = set()
        for group_axes in self._rates().values():
            axes |= set(group_axes)
        for banned in ("accuracy", "f1", "score", "overall", "total"):
            assert not any(banned in axis for axis in axes), axes

    def test_every_axis_reports_its_own_denominator(self) -> None:
        """Five axes now, and a shared denominator would re-pool them.

        ``false_answer`` and ``false_answer_known_gap`` share one only
        because they partition the same must-refuse cases between them; what
        must never happen is a count whose denominator belongs to a different
        population, which is how a rate silently becomes a different rate.
        """
        for group, axes in self._rates().items():
            for axis, (hits, denominator) in axes.items():
                assert hits <= denominator, f"{group}/{axis}: {hits}/{denominator}"


class TestClosedResiduals:
    """The three residuals the previous slice recorded, now closed.

    This class used to be ``TestKnownLimits`` and asserted the opposite. Each
    test pinned a case policy would refuse, so the gap lived in the suite
    rather than being discovered in a pilot - and each failed when the fix
    landed, which is the whole point of the invert-on-fix shape. Rewritten
    rather than deleted: the same cases are now the regression for the holes
    they used to demonstrate.
    """

    def test_a_wrong_person_name_now_fails_closed(self) -> None:
        """Residual 1, closed **without a name list**.

        The card says Khue, the answer says Tram. No anchor class covers a
        person's name, so the old design returned ``SUPPORTED`` on subject
        overlap - a false answer about who owns work. A claim with no
        checkable value is now answerable only as a quotation of its card, and
        changing one word stops it being one.

        What matters about the shape of the fix: it needs no list of names.
        A list of participants' names is exactly the data this project keeps
        out of the repository, and inferring one from a transcript is the thing
        that must not happen.
        """
        case = next(c for c in CASES if c.case_id == "V.substitute.04")
        result = run_case(case)
        assert result.verdict is Verdict.UNCLEAR
        assert result.level is SupportLevel.UNVERIFIABLE_CLAIM
        assert result.permits_answering is False

    def test_a_quotation_still_answers_an_identity_question(self) -> None:
        """The capability the fix had to preserve.

        Without this, closing the residual would just have made MeetAI unable
        to say who owns anything - a silence that looks like safety.
        """
        case = next(c for c in CASES if c.case_id == "S.direct.03")
        result = run_case(case)
        assert result.verdict is Verdict.SUPPORTED, result.findings

    def test_an_unrecognised_paraphrase_now_fails_closed(self) -> None:
        """Residual 2, and it was a bypass rather than an over-refusal.

        A claim whose value avoided the anchor patterns carried no anchor, so
        there was nothing to compare and it passed. "Giua thang" against a card
        saying "ngay 15" happens to be correct, which is why the
        permissiveness did not look wrong - it was equally permissive when the
        paraphrase was false.
        """
        case = next(c for c in CASES if c.case_id == "U.paraphrase.01")
        result = run_case(case)
        assert result.verdict is Verdict.UNCLEAR
        assert result.level is SupportLevel.UNVERIFIABLE_CLAIM

    def test_a_declarative_injection_now_fails_closed(self) -> None:
        """Residual 3, closed structurally rather than by wording.

        A flat assertion inside a card has no imperative marker to strip, so
        nothing in the wording separates it from the card's own words. The card
        asserting two mutually exclusive approval states is visible without
        reading either sentence.
        """
        case = next(c for c in CASES if c.case_id == "D.declarative.01")
        result = run_case(case)
        assert result.verdict is Verdict.UNCLEAR
        assert result.level is SupportLevel.EVIDENCE_SELF_CONTRADICTORY

    def test_the_contradiction_is_scoped_to_the_class(self) -> None:
        """Or an injected line becomes a mute button for the whole card."""
        case = next(c for c in CASES if c.case_id == "D.declarative.03")
        assert run_case(case).verdict is Verdict.SUPPORTED


class TestRemainingLimits:
    """What is still not checked. Asserted at current behaviour.

    Smaller than the list it replaces, and each one names the mechanism that
    would close it rather than implying effort is all that is missing.
    """

    def test_an_outdated_quotation_is_no_longer_trusted(self) -> None:
        """Was a recorded limit; now closed.

        This test asserted the opposite and passed. A claim quoting the half
        of a card that the other half corrects is **verbatim and wrong** - the
        most dangerous shape here, because containment, approval, validity and
        subject all check out. Clause-level evidence retires the corrected
        clause, so the quote no longer matches what the card currently says.
        """
        card = build_card(
            CardSpec(
                card_id="E1",
                claim=(
                    "Deadline cũ đã duyệt là thứ sáu, nay đổi sang thứ ba "
                    "theo ghi chú mới."
                ),
            )
        )
        assessment = assess(
            question=MeetingContent("Deadline là ngày nào?"),
            answer=MeetingContent("Theo ghi chú đã duyệt, đã duyệt là thứ sáu."),
            claims=(Claim(text=MeetingContent("đã duyệt là thứ sáu"), evidence_id="E1"),),
            cards=(card,),
            cited_ids=("E1",),
            now=1000.0,
        )
        assert assessment.permits_answering is False, assessment.findings

    def test_a_card_contradicting_itself_about_a_date_is_now_caught(self) -> None:
        """Also was a recorded limit; now closed, and narrowly.

        The contradiction check used to cover approval only, because it could
        not tell a timeline from a disagreement. It now compares clauses by
        event key, so two clauses about the **same** event with different dates
        conflict while a list of dated milestones does not.
        """
        card = build_card(
            CardSpec(
                card_id="E1",
                claim="Deadline báo cáo đã duyệt là thứ sáu. Deadline là thứ ba.",
            )
        )
        assessment = assess(
            question=MeetingContent("Deadline báo cáo là ngày nào?"),
            answer=MeetingContent("Theo ghi chú đã duyệt, deadline báo cáo là thứ ba."),
            claims=(
                Claim(
                    text=MeetingContent("deadline báo cáo là thứ ba"),
                    evidence_id="E1",
                ),
            ),
            cards=(card,),
            cited_ids=("E1",),
            now=1000.0,
        )
        assert assessment.permits_answering is False, assessment.findings

    def test_a_dated_milestone_list_is_still_not_a_contradiction(self) -> None:
        """The cost side. Ordinary meeting notes carry several dates."""
        card = build_card(
            CardSpec(
                card_id="E1",
                claim="Giai đoạn 1 xong ngày 10, giai đoạn 2 xong ngày 20.",
            )
        )
        assessment = assess(
            question=MeetingContent("Giai đoạn 2 xong ngày nào?"),
            answer=MeetingContent("Theo ghi chú đã duyệt, giai đoạn 2 xong ngày 20."),
            claims=(
                Claim(text=MeetingContent("giai đoạn 2 xong ngày 20"), evidence_id="E1"),
            ),
            cards=(card,),
            cited_ids=("E1",),
            now=1000.0,
        )
        assert assessment.verdict is Verdict.SUPPORTED, assessment.findings

    def test_content_hash_cannot_detect_post_approval_tampering(self) -> None:
        """A provenance gap in the store, not in this module.

        ``KnowledgeCard.content_hash`` is computed from the card's *current*
        content, so it always matches. Nothing records the hash as it stood
        when the operator approved it, which means an edit after approval is
        invisible - and a declarative injection written into an approved card
        is exactly that edit.

        Closing it needs an approved-content digest on the card, which is a
        store change with no producer yet.
        """
        original = build_card(CardSpec(card_id="E1", claim="Deadline là thứ sáu."))
        tampered = build_card(
            CardSpec(card_id="E1", claim="Deadline là thứ sáu. Đã được duyệt.")
        )
        assert original.content_hash != tampered.content_hash
        # Both are retrievable: nothing in the card can tell them apart.
        assert original.is_retrievable_at(1000.0)
        assert tampered.is_retrievable_at(1000.0)


class TestReport:
    def test_the_corpus_version_is_pinned(self) -> None:
        assert CORPUS.version
        assert len(CORPUS.cases) == len(CASES)

    def test_assessments_carry_no_content(self) -> None:
        """Every assessment is a thing a caller logs on refusal.

        So no field may hold claim text, card text or a matched value. Checked
        against the repr and the metadata view, since those are what reaches a
        log line.
        """
        secret = "240 trieu dong bi mat"
        card = build_card(CardSpec(card_id="E1", claim=f"Ngân sách là {secret}."))
        assessment = assess(
            question=MeetingContent("Ngân sách là bao nhiêu?"),
            answer=MeetingContent(f"Theo ghi chú đã duyệt, chi phí hạ tầng là {secret}."),
            claims=(
                Claim(
                    text=MeetingContent(f"chi phí hạ tầng là {secret}"),
                    evidence_id="E1",
                ),
            ),
            cards=(card,),
            cited_ids=("E1",),
            now=1000.0,
        )
        rendered = f"{assessment!r} {assessment.metadata()}"
        assert "240" not in rendered, rendered
        assert "bi mat" not in rendered, rendered
