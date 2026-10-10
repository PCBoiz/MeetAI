"""Evaluation of the addressee classifier on the S1.7 corpus.

Reports the rates the acceptance criteria name, **separately and with their
denominators**. A pooled accuracy is deliberately absent, for the same reason
the authority harness has none: the mistakes are not commensurable. A false
activation means MeetAI spoke when it was not addressed - an interjection in
somebody else's meeting, in the operator's name. A false non-address means it
stayed quiet when asked, which costs a repeated question. Averaging the two
into one number would let an improvement in the cheap direction pay for a
regression in the expensive one.

The unclear rate is reported as its own number rather than folded into either.
``UNCLEAR`` is the correct answer for a large part of this corpus, so a low
unclear rate is not a good score and a high one is not a bad score - but a
rate that moves without a label changing means a signal shifted, and that is
worth seeing.

Synthetic corpus. This measures the logic. It is **not** evidence that the
classifier works on real Vietnamese speech, and it cannot calibrate any
threshold.
"""

from __future__ import annotations

import ast
import os
from collections import Counter
from pathlib import Path

import pytest

from meetai.addressing import (
    AddressAssessment,
    AddressClass,
    Alias,
    AliasKind,
    AliasRegistry,
    Utterance,
    classify_address,
)
from meetai.evaluation import Rate
from tests.corpus.addressing_types import (
    AddressCase,
    AddressGroup,
    ExpectedClass,
    ExpectedIntent,
)
from tests.corpus.addressing_vi import (
    AMBIGUOUS_WORD_ALIASES,
    CASES,
    CORPUS_VERSION,
    DEDICATED_ALIASES,
    HUMAN_NAME_ALIASES,
)

KNOWN_GAP_CEILING = 1
"""The number of recorded disagreements between policy and code.

May only ever be **lowered**. A gap in the suite is better than a gap found in
a pilot, and raising this would be the mechanism by which a regression becomes
the new normal.
"""

REPORT_PATH = Path(__file__).resolve().parents[1] / "docs" / "research"


def _registry() -> AliasRegistry:
    """The fixture registry, built from the corpus's invented names.

    Built here rather than in the corpus, because constructing it needs
    ``Alias`` from the module under test and the corpus may not import that.
    """
    return AliasRegistry(
        frozenset(
            [Alias(text, AliasKind.DEDICATED) for text in DEDICATED_ALIASES]
            + [Alias(text, AliasKind.HUMAN_NAME) for text in HUMAN_NAME_ALIASES]
            + [Alias(text, AliasKind.AMBIGUOUS_WORD) for text in AMBIGUOUS_WORD_ALIASES]
        )
    )


REGISTRY = _registry()


def _assess(case: AddressCase) -> AddressAssessment:
    return classify_address(
        Utterance(
            text=case.text,
            speaker_mapping_reliable=case.speaker_mapping_reliable,
            transcript_complete=case.transcript_complete,
            addressed_to_me_by_turn=case.addressed_to_me_by_turn,
        ),
        registry=REGISTRY,
    )


def _agrees(case: AddressCase, assessment: AddressAssessment) -> bool:
    """Whether the code matches every label on the case."""
    return (
        assessment.address_class.value == case.expected_class.value
        and assessment.response_intent.value == case.expected_intent.value
        and assessment.permits_reply == case.expected_reply
    )


# -------------------------------------------------------------------- #
# Label integrity
# -------------------------------------------------------------------- #


class TestCorpusIntegrity:
    """Make classifier-sourced ground truth structurally impossible.

    Same enforcement as the authority corpus, applied to this one. A corpus
    able to call the classifier it judges could copy that classifier's output
    into its own labels, and the evaluation would measure the code against
    itself.
    """

    @staticmethod
    def _source(name: str) -> str:
        return (Path(__file__).resolve().parent / "corpus" / name).read_text(
            encoding="utf-8"
        )

    @pytest.mark.parametrize("name", ["addressing_vi.py", "addressing_types.py"])
    def test_corpus_does_not_import_the_code_it_judges(self, name: str) -> None:
        imported: set[str] = set()
        for node in ast.walk(ast.parse(self._source(name))):
            if isinstance(node, ast.Import):
                imported.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module)
        assert not any(name.startswith("meetai") for name in imported), imported

    def test_corpus_contains_no_computation(self) -> None:
        """A derived label needs code, so the code is forbidden."""
        nodes = list(ast.walk(ast.parse(self._source("addressing_vi.py"))))

        generators = [
            type(node).__name__
            for node in nodes
            if isinstance(
                node,
                ast.ListComp
                | ast.SetComp
                | ast.DictComp
                | ast.GeneratorExp
                | ast.For
                | ast.While,
            )
        ]
        assert not generators, f"corpus chua cau truc sinh du lieu: {generators}"

        called = {
            node.func.id
            if isinstance(node.func, ast.Name)
            else getattr(node.func, "attr", "?")
            for node in nodes
            if isinstance(node, ast.Call)
        }
        assert called <= {"AddressCase"}, called

    def test_every_case_cites_a_decision(self) -> None:
        """A label justified only by "that is what the classifier returned"
        cannot cite a decision."""
        permitted = {"op", "agents", "handoff", "plan"}
        for case in CASES:
            source, _, rest = case.policy_basis.partition(":")
            assert source in permitted, f"{case.case_id}: {case.policy_basis}"
            assert rest.strip(), case.case_id

    def test_case_ids_are_unique(self) -> None:
        ids = [case.case_id for case in CASES]
        assert len(ids) == len(set(ids))

    def test_every_group_is_populated(self) -> None:
        """An empty group would silently remove a risk class from the report."""
        covered = {case.group for case in CASES}
        assert covered == set(AddressGroup), set(AddressGroup) - covered

    def test_every_class_appears_as_an_expected_label(self) -> None:
        """A class nobody labels is a class nobody measures."""
        labelled = {case.expected_class for case in CASES}
        assert labelled == set(ExpectedClass), set(ExpectedClass) - labelled

    def test_every_intent_appears_as_an_expected_label(self) -> None:
        labelled = {case.expected_intent for case in CASES}
        assert labelled == set(ExpectedIntent), set(ExpectedIntent) - labelled

    def test_reply_label_agrees_with_the_two_stage_labels(self) -> None:
        """``expected_reply`` is stored rather than derived, so a labelling
        error shows up as a contradiction a test can catch."""
        for case in CASES:
            implied = (
                case.expected_class is ExpectedClass.DIRECTED_TO_ME
                and case.expected_intent is not ExpectedIntent.NONE
            )
            assert case.expected_reply == implied, case.case_id

    def test_no_real_personal_data(self) -> None:
        source = self._source("addressing_vi.py")
        assert "@" not in "".join(case.text for case in CASES)
        assert "synthetic" in source.lower()

    def test_the_operators_name_is_absent(self) -> None:
        """Real aliases are configured locally and stay out of the repository.
        The authority corpus could not avoid the operator's name because the
        patterns hard-code it; this corpus has no such excuse."""
        texts = " ".join(case.text for case in CASES).lower()
        assert "sơn" not in texts
        assert "son" not in texts.replace("sơn", "")

    def test_the_registry_ships_empty(self) -> None:
        """The corpus's dedicated alias is a fixture value, not a decision
        about what MeetAI is called. The shipped default recognises nobody."""
        assert AliasRegistry().aliases == frozenset()
        assert not AliasRegistry().has_dedicated_alias


# -------------------------------------------------------------------- #
# The safety property, measured over the whole corpus
# -------------------------------------------------------------------- #


class TestNoFalseActivation:
    """False activation is the expensive direction, so it gets its own class.

    The acceptance criteria require it reported separately from false
    non-address, and the two assertions below are different claims: one says
    the rate is zero today, the other says the class is unreachable without a
    dedicated alias at all.
    """

    def test_no_case_outside_group_p_permits_a_reply(self) -> None:
        wrong = [
            case.case_id
            for case in CASES
            if not case.expected_reply and _assess(case).permits_reply
        ]
        assert not wrong, f"false activation: {wrong}"

    def test_without_a_dedicated_alias_only_turn_context_reaches_direct(self) -> None:
        """Measured across every utterance in the corpus, not a sample.

        The first version of this test asserted that nothing at all reaches
        ``DIRECTED_TO_ME`` without a dedicated alias, and it failed - correctly.
        Turn context is a second, independent evidence path that needs no
        alias, by design. So the property is stated as an exact exception set
        rather than loosened: the only cases that get there are the ones
        carrying trustworthy turn context, and reaching that state requires
        ``speaker_mapping_reliable``, which Gate 0-C governs.
        """
        registry = AliasRegistry(
            frozenset(
                [Alias(text, AliasKind.HUMAN_NAME) for text in HUMAN_NAME_ALIASES]
                + [
                    Alias(text, AliasKind.AMBIGUOUS_WORD)
                    for text in AMBIGUOUS_WORD_ALIASES
                ]
            )
        )
        direct: set[str] = set()
        for case in CASES:
            assessment = classify_address(
                Utterance(
                    text=case.text,
                    speaker_mapping_reliable=case.speaker_mapping_reliable,
                    transcript_complete=case.transcript_complete,
                    addressed_to_me_by_turn=case.addressed_to_me_by_turn,
                ),
                registry=registry,
            )
            if assessment.address_class is AddressClass.DIRECTED_TO_ME:
                direct.add(case.case_id)
                assert "turn_context" in assessment.reasons, case.case_id

        by_turn = {case.case_id for case in CASES if case.addressed_to_me_by_turn}
        assert direct <= by_turn, direct - by_turn

    def test_a_reply_always_needs_a_dedicated_alias_or_turn_context(self) -> None:
        """The composed claim, over every case and both registries.

        This is the one that matters operationally: with no alias configured
        and Gate 0-C open, there is no input in this corpus that makes MeetAI
        speak.
        """
        for case in CASES:
            assessment = classify_address(
                Utterance(
                    text=case.text,
                    speaker_mapping_reliable=case.speaker_mapping_reliable,
                    transcript_complete=case.transcript_complete,
                    addressed_to_me_by_turn=case.addressed_to_me_by_turn,
                ),
                registry=AliasRegistry(),
            )
            if assessment.permits_reply:
                assert case.addressed_to_me_by_turn, case.case_id

    def test_an_empty_registry_makes_a_reply_unreachable(self) -> None:
        empty = AliasRegistry()
        for case in CASES:
            assessment = classify_address(
                Utterance(
                    text=case.text,
                    speaker_mapping_reliable=case.speaker_mapping_reliable,
                    transcript_complete=case.transcript_complete,
                    addressed_to_me_by_turn=case.addressed_to_me_by_turn,
                ),
                registry=empty,
            )
            assert not assessment.permits_reply, case.case_id


# -------------------------------------------------------------------- #
# The known-gap ledger
# -------------------------------------------------------------------- #


class TestKnownGaps:
    """Recorded disagreements must persist until deliberately cleared.

    Inverted on purpose: closing a gap fails the suite with a message telling
    the author to clear the flag. Without that, a fix silently improves a
    number and the ledger drifts out of date.
    """

    def test_gap_count_is_within_the_ceiling(self) -> None:
        gaps = [case.case_id for case in CASES if case.known_gap]
        assert len(gaps) <= KNOWN_GAP_CEILING, gaps

    @pytest.mark.parametrize(
        "case", [c for c in CASES if c.known_gap], ids=lambda c: c.case_id
    )
    def test_a_known_gap_still_disagrees(self, case: AddressCase) -> None:
        assert not _agrees(case, _assess(case)), (
            f"{case.case_id} da khop policy: bo known_gap va ha "
            f"KNOWN_GAP_CEILING xuong {KNOWN_GAP_CEILING - 1}"
        )

    @pytest.mark.parametrize(
        "case", [c for c in CASES if c.known_gap], ids=lambda c: c.case_id
    )
    def test_a_known_gap_names_its_error_class(self, case: AddressCase) -> None:
        """A gap recorded without a cause is a gap nobody can close."""
        assert "lop loi" in case.notes.lower(), case.case_id

    def test_a_known_gap_never_permits_a_reply(self) -> None:
        """A gap is tolerable only while it cannot make MeetAI speak."""
        for case in CASES:
            if case.known_gap:
                assert not _assess(case).permits_reply, case.case_id

    @pytest.mark.parametrize(
        "case", [c for c in CASES if not c.known_gap], ids=lambda c: c.case_id
    )
    def test_case_matches_policy(self, case: AddressCase) -> None:
        assessment = _assess(case)
        assert _agrees(case, assessment), (
            f"{case.case_id}: want "
            f"({case.expected_class.value}, {case.expected_intent.value}, "
            f"reply={case.expected_reply}) got "
            f"({assessment.address_class.value}, "
            f"{assessment.response_intent.value}, "
            f"reply={assessment.permits_reply}) reasons={assessment.reasons}"
        )


# -------------------------------------------------------------------- #
# The report
# -------------------------------------------------------------------- #


def _rate(numerator: int, denominator: int) -> Rate:
    return Rate(numerator=numerator, denominator=denominator)


def _render() -> tuple[str, dict[str, Rate]]:
    """Build the report and the headline rates.

    Returns both so the tests can assert on the numbers rather than on the
    prose, which is what makes the assertions survive a rewording.
    """
    rows: list[str] = []
    rates: dict[str, Rate] = {}

    false_activation = 0
    activation_denominator = 0
    false_non_address = 0
    non_address_denominator = 0
    unclear = 0
    class_wrong = 0
    intent_wrong = 0
    examples: list[str] = []

    per_group: dict[AddressGroup, Counter[str]] = {
        group: Counter() for group in AddressGroup
    }

    for case in CASES:
        assessment = _assess(case)
        counter = per_group[case.group]
        counter["n"] += 1

        if case.expected_reply:
            non_address_denominator += 1
            if not assessment.permits_reply:
                false_non_address += 1
                counter["false_non_address"] += 1
        else:
            activation_denominator += 1
            if assessment.permits_reply:
                false_activation += 1
                counter["false_activation"] += 1

        if assessment.address_class is AddressClass.UNCLEAR:
            unclear += 1
            counter["unclear"] += 1
        if assessment.address_class.value != case.expected_class.value:
            class_wrong += 1
            counter["class_wrong"] += 1
            examples.append(
                f"- `{case.case_id}` "
                f"({case.group.value}): nhan `{case.expected_class.value}`, "
                f"code tra `{assessment.address_class.value}`, "
                f"reasons `{','.join(assessment.reasons)}`"
                f"{' **[known gap]**' if case.known_gap else ''}"
            )
        if assessment.response_intent.value != case.expected_intent.value:
            intent_wrong += 1
            counter["intent_wrong"] += 1
            examples.append(
                f"- `{case.case_id}` ({case.group.value}): intent nhan "
                f"`{case.expected_intent.value}`, code tra "
                f"`{assessment.response_intent.value}`"
                f"{' **[known gap]**' if case.known_gap else ''}"
            )

    rates["false_activation"] = _rate(false_activation, activation_denominator)
    rates["false_non_address"] = _rate(false_non_address, non_address_denominator)
    rates["unclear"] = _rate(unclear, len(CASES))
    rates["class_wrong"] = _rate(class_wrong, len(CASES))
    rates["intent_wrong"] = _rate(intent_wrong, len(CASES))

    rows.append(f"# Danh gia direct-address classifier (S1.7), corpus v{CORPUS_VERSION}")
    rows.append("")
    rows.append(
        "Corpus **synthetic**, alias **gia**. Do logic, **khong** phai bang chung "
        "classifier chay tot tren tieng Viet thuc te, va **khong** calibrate duoc "
        "nguong nao. Moi ty le kem denominator."
    )
    rows.append("")
    rows.append("## Chi so dau bao")
    rows.append("")
    rows.append("| Chi so | Gia tri | Y nghia khi sai |")
    rows.append("|---|---|---|")
    rows.append(
        f"| False activation | {rates['false_activation'].render()} | "
        "MeetAI noi khi khong duoc goi |"
    )
    rows.append(
        f"| False non-address | {rates['false_non_address'].render()} | "
        "MeetAI im khi duoc hoi |"
    )
    rows.append(
        f"| UNCLEAR rate | {rates['unclear'].render()} | khong phai diem; "
        "UNCLEAR la dap an dung cho phan lon corpus |"
    )
    rows.append(f"| Sai lop address | {rates['class_wrong'].render()} | |")
    rows.append(f"| Sai intent | {rates['intent_wrong'].render()} | |")
    rows.append("")
    rows.append("## Theo nhom rui ro")
    rows.append("")
    rows.append("| Nhom | n | false activation | false non-address | UNCLEAR | sai lop |")
    rows.append("|---|---|---|---|---|---|")
    for group in AddressGroup:
        counter = per_group[group]
        total = counter["n"]
        rows.append(
            f"| {group.value} | {total} | "
            f"{counter['false_activation']}/{total} | "
            f"{counter['false_non_address']}/{total} | "
            f"{counter['unclear']}/{total} | "
            f"{counter['class_wrong']}/{total} |"
        )
    rows.append("")
    rows.append("## Vi du sai")
    rows.append("")
    rows.extend(examples or ["- khong co"])
    rows.append("")
    rows.append("## Gioi han")
    rows.append("")
    rows.append(
        "- Corpus do chinh tac gia viet ra. No kiem tra logic va bat lop loi, "
        "**khong** do duoc phan phoi cau noi thuc te."
    )
    rows.append(
        "- Alias `MeetAI` la gia tri fixture, **khong** phai quyet dinh ve ten "
        "goi cua MeetAI. Registry mac dinh rong."
    )
    rows.append(
        "- Turn context (`addressed_to_me_by_turn`) chi dat duoc khi participant "
        "mapping dang tin cay. **Gate 0-C con mo**, nen duong code do hom nay "
        "chi duoc test, chua duoc dung."
    )
    rows.append(
        "- Khong co confidence tren assessment. `MINIMUM_CONFIDENCE` van la "
        "placeholder chua calibrate va corpus synthetic khong calibrate duoc."
    )
    return "\n".join(rows) + "\n", rates


@pytest.fixture(scope="module")
def report() -> tuple[str, dict[str, Rate]]:
    return _render()


class TestReport:
    """The numbers the acceptance criteria name."""

    def test_false_activation_is_reported_with_its_denominator(
        self, report: tuple[str, dict[str, Rate]]
    ) -> None:
        rendered = report[1]["false_activation"].render()
        assert "/" in rendered

    def test_false_activation_and_non_address_are_separate_numbers(
        self, report: tuple[str, dict[str, Rate]]
    ) -> None:
        """Not one score. A false activation and a false non-address are not
        commensurable, and the criteria require them apart."""
        rates = report[1]
        assert rates["false_activation"].denominator != 0
        assert rates["false_non_address"].denominator != 0
        assert rates["false_activation"].denominator + rates[
            "false_non_address"
        ].denominator == len(CASES)

    def test_report_contains_no_accuracy(
        self, report: tuple[str, dict[str, Rate]]
    ) -> None:
        lowered = report[0].lower()
        assert "accuracy" not in lowered
        assert "f1" not in lowered

    def test_report_states_it_cannot_calibrate(
        self, report: tuple[str, dict[str, Rate]]
    ) -> None:
        assert "calibrate" in report[0].lower()
        assert "synthetic" in report[0].lower()

    def test_report_states_gate_0c_is_open(
        self, report: tuple[str, dict[str, Rate]]
    ) -> None:
        assert "0-C" in report[0]

    def test_report_is_written(self, report: tuple[str, dict[str, Rate]]) -> None:
        """Written to a file so the numbers can be committed and diffed.

        Skipped when the suite runs read-only.
        """
        if os.environ.get("MEETAI_EVAL_NO_WRITE"):
            pytest.skip("eval report writing disabled")
        REPORT_PATH.mkdir(parents=True, exist_ok=True)
        target = REPORT_PATH / "2026-10-07-addressing-eval-v1.md"
        target.write_text(report[0], encoding="utf-8")
        assert target.exists()
