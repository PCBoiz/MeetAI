"""Normalisation candidates, measured. **Nothing here is wired into ``src``.**

The corpus records three false answers whose shared cause is the subject
tokeniser: it cannot see a one-character difference. This file measures the
candidate repairs **outside the production path**, by rebinding the module
global inside a test, so a number exists before a decision does.

Why it is committed rather than left in a scratch directory: the measurement
is the argument for changing a safety-relevant function, and an argument that
cannot be re-run is not evidence. A test asserting the recorded figures also
means a drift in the candidate, the corpus or the module shows up as a
failure rather than as a stale paragraph in a memo.

**The candidates**

``R1``
    Stop dropping one-character tokens. Closes the designator hole and the
    over-refusal pinned at ``test_a_single_letter_option_label_over_refuses``.
    **Rejected on measurement:** Vietnamese particles fold to single letters,
    so ``theo y minh thi ngan sach tong la 240 trieu dong`` and ``a ngan sach
    tong ...`` stop being answerable. ASR output is full of those, which puts
    the cost exactly where the input lives.

``R1b``
    Admit a one-character token **only when the token before it is a label
    word**. Positional rather than a widened token set, and conjunctive: a
    label word alone changes nothing, so ``an toan`` is untouched while
    ``phuong an B`` keeps its ``B``. Same gains as R1 with none of R1's
    colloquial cost, measured.

``R2``
    A synonym table mapping ``han``/``chot`` to a canonical ``deadline``,
    aimed at the paraphrase cases. **Rejected - but not for the reason an
    earlier version of this docstring gave.**

    That version said R2 "does not reduce false answers, it moves them". An
    independent audit showed that is not what this file measures: **on the
    corpus R2 is strictly better**, 3 -> 2 false answers and 3 -> 2 false
    abstentions, with nothing on-corpus regressing. Stated as written, the
    claim was false and the corpus contradicted it.

    What rejects R2 is off-corpus, and it only became decisive once the
    **class** was measured rather than the one instance this file originally
    rested on: ``han`` and ``chot`` are productive Vietnamese syllables, and
    mapping them to ``deadline`` turns **10 of 10** tested compounds -
    ``han muc``, ``han che``, ``thoi han``, ``gia han``, ``qua han``,
    ``het han``, ``gioi han``, ``han ngach``, ``chot so``, ``chot gia`` -
    from a refusal into an answer. So R2 buys two corpus wins at the cost of
    an entire word class, and the corpus could not see the bill because it
    contains exactly one ``han`` compound.

    The conclusion survived; the reasoning behind it did not. Recorded that
    way because the project's rule is to measure the class, and this is the
    case that shows why a two-case corpus gain is not evidence of a gain.

**What is NOT decided here.** R1b is a proposal with a measurement attached,
not a change. It alters a function shared with retrieval, so it needs an
acceptance criterion from the operator and an eval set the operator controls -
``AGENTS.md`` requires both before a lexicon or tokeniser change lands, and
the recorded reason is that a repair made to turn a suite green is how a
measured hole becomes an unmeasured one.
"""

from __future__ import annotations

import ast
import re
from collections.abc import Callable
from pathlib import Path

import pytest

from meetai import answerability as answerability_module
from meetai import retrieval as retrieval_module
from meetai.answerability import Claim, assess
from meetai.authority import fold_diacritics
from meetai.content import MeetingContent
from tests.corpus.answerability_types import CardSpec
from tests.corpus.answerability_vi import CASES
from tests.test_answerability_eval import build_card, run_case

SRC = Path(__file__).resolve().parent.parent / "src" / "meetai"

LABEL_WORDS = frozenset(
    {"an", "muc", "option", "ban", "luc", "nhom", "loai", "cap", "phien", "kieu"}
)
"""Words a short designator follows. Deliberately small, and only ever
consulted when the **next** token is one character long."""

_SYNONYMS = {"han": "deadline", "chot": "deadline", "nop": "", "deadline": "deadline"}

_PRODUCTION_SUBJECT_TOKENS = answerability_module.subject_tokens
"""Captured at import, before any fixture can rebind the global.

R2 composes on top of the tokeniser, so reading the global at call time made
it compose on top of *itself* once installed - an immediate RecursionError,
and a reminder that a study which patches a module must not also read it."""


def _strip_values(text: str) -> str:
    without = fold_diacritics(text)
    for pattern in answerability_module._PATTERNS.values():
        without = pattern.sub(" ", without)
    return without


def _keep(token: str) -> bool:
    return (
        token not in answerability_module._STOPWORDS
        and token not in answerability_module._UNITS
    )


def candidate_r1(text: str) -> frozenset[str]:
    """Admit every one-character token."""
    return frozenset(
        tok for tok in re.findall(r"[a-z]+", _strip_values(text)) if _keep(tok)
    )


def candidate_r1b(text: str) -> frozenset[str]:
    """Admit a one-character token only after a label word."""
    raw = re.findall(r"[a-z]+", _strip_values(text))
    return frozenset(
        tok
        for index, tok in enumerate(raw)
        if _keep(tok) and (len(tok) > 1 or (index > 0 and raw[index - 1] in LABEL_WORDS))
    )


def candidate_r2(text: str) -> frozenset[str]:
    """Collapse a small equivalence table onto a canonical token."""
    mapped = {_SYNONYMS.get(tok, tok) for tok in _PRODUCTION_SUBJECT_TOKENS(text)}
    return frozenset(tok for tok in mapped if tok)


CANDIDATES = {
    "R1": candidate_r1,
    "R1b": candidate_r1b,
    "R2": candidate_r2,
}


@pytest.fixture
def install(monkeypatch: pytest.MonkeyPatch) -> Callable[[str], None]:
    """Rebind the tokeniser for one test, in **both** modules that hold it.

    ``retrieval`` does ``from meetai.answerability import subject_tokens`` and
    so keeps its own reference. Patching only ``answerability`` would measure
    half the pipeline and report it as the whole, which is the kind of quiet
    half-measurement this file exists to avoid.
    """

    def _install(name: str) -> None:
        fn = CANDIDATES[name]
        monkeypatch.setattr(answerability_module, "subject_tokens", fn)
        monkeypatch.setattr(retrieval_module, "subject_tokens", fn)

    return _install


def offenders() -> dict[str, tuple[str, ...]]:
    """``{"false_answer": ids, "false_abstention": ids}`` over the whole corpus.

    Ids rather than counts: a candidate that closes one hole and opens
    another scores the same on a count, and that is precisely the trade this
    study had to be able to see. R2 is the case in point.
    """
    false_answer: list[str] = []
    false_abstention: list[str] = []
    for case in CASES:
        result = run_case(case)
        if not case.expected.permits_answering and result.permits_answering:
            false_answer.append(case.case_id)
        if case.expected.permits_answering and not result.permits_answering:
            false_abstention.append(case.case_id)
    return {
        "false_answer": tuple(sorted(false_answer)),
        "false_abstention": tuple(sorted(false_abstention)),
    }


BASELINE_FALSE_ANSWERS = ("Q.attribute.01", "R.crosscard.01", "Y.letter.01")
BASELINE_FALSE_ABSTENTIONS = ("N.corrected.01", "N.corrected.02", "R.paraphrase.01")


class TestBaseline:
    def test_the_baseline_is_what_the_ledger_says(self) -> None:
        """The study is worthless if its starting point drifts."""
        measured = offenders()
        assert measured["false_answer"] == BASELINE_FALSE_ANSWERS, measured
        assert measured["false_abstention"] == BASELINE_FALSE_ABSTENTIONS, measured


class TestCandidateR1:
    def test_it_closes_the_designator_false_answer(
        self, install: Callable[[str], None]
    ) -> None:
        install("R1")
        assert "Y.letter.01" not in offenders()["false_answer"]

    def test_it_opens_no_other_corpus_hole(self, install: Callable[[str], None]) -> None:
        """True on the corpus - and the reason the corpus is not enough."""
        install("R1")
        measured = offenders()
        assert set(measured["false_answer"]) <= set(BASELINE_FALSE_ANSWERS)
        assert set(measured["false_abstention"]) <= set(BASELINE_FALSE_ABSTENTIONS)

    @pytest.mark.parametrize(
        "claim",
        [
            "Theo ý mình thì ngân sách tổng là 240 triệu đồng",
            "À ngân sách tổng là 240 triệu đồng",
        ],
    )
    def test_it_refuses_colloquial_fillers_and_that_is_why_it_is_rejected(
        self, install: Callable[[str], None], claim: str
    ) -> None:
        """The cost the 51-case corpus could not show.

        ``ý`` and ``à`` fold to one letter, so under R1 a filler the card does
        not contain breaks subject containment. These answer at baseline. The
        prior note at ``test_a_single_letter_option_label_over_refuses``
        predicted a widened token rule would cost something; this is the part
        of that prediction that measured true.
        """
        assert _answers(claim) is True
        install("R1")
        assert _answers(claim) is False


class TestCandidateR1b:
    def test_it_closes_the_designator_false_answer(
        self, install: Callable[[str], None]
    ) -> None:
        install("R1b")
        assert "Y.letter.01" not in offenders()["false_answer"]

    def test_it_opens_no_other_corpus_hole(self, install: Callable[[str], None]) -> None:
        install("R1b")
        measured = offenders()
        assert set(measured["false_answer"]) <= set(BASELINE_FALSE_ANSWERS)
        assert set(measured["false_abstention"]) <= set(BASELINE_FALSE_ABSTENTIONS)

    @pytest.mark.parametrize(
        "claim",
        [
            "Theo ý mình thì ngân sách tổng là 240 triệu đồng",
            "À ngân sách tổng là 240 triệu đồng",
        ],
    )
    def test_it_keeps_colloquial_fillers_answerable(
        self, install: Callable[[str], None], claim: str
    ) -> None:
        """Where R1b differs from R1, and the only reason to prefer it."""
        install("R1b")
        assert _answers(claim) is True

    def test_the_gain_is_a_whole_class_not_one_case(
        self, install: Callable[[str], None]
    ) -> None:
        """Eight label words times three letter pairs. **24/24.**

        R1b was argued from one corpus case plus three hard negatives, which
        is the same evidential footing R2's *rejection* turned out to need
        strengthening from. So the gain is measured over the class: every
        label word the rule knows, against consecutive letters, with the value
        held identical so only the designator differs.

        Baseline answers all 24 - each one a statement that the wrong option
        was approved. R1b refuses all 24, and leaves none still answering.
        """
        labels = ["Phương án", "Mục", "Nhóm", "Loại", "Cấp", "Phiên", "Kiểu", "Bản"]
        pairs = [("A", "B"), ("B", "C"), ("C", "D")]
        cases = [
            (
                CardSpec(
                    card_id="Z5",
                    claim=f"{label} {held} đã duyệt ngân sách 240 triệu đồng.",
                ),
                f"{label.lower()} {claimed} đã duyệt ngân sách 240 triệu đồng",
                f"{label} {claimed} duyệt ngân sách bao nhiêu?",
            )
            for label in labels
            for held, claimed in pairs
        ]
        assert len(cases) == 24

        answered_at_baseline = [
            question
            for card, claim, question in cases
            if _answers(claim, card=card, question=question)
        ]
        assert len(answered_at_baseline) == 24, answered_at_baseline

        install("R1b")
        still_answered = [
            question
            for card, claim, question in cases
            if _answers(claim, card=card, question=question)
        ]
        assert still_answered == [], still_answered

    def test_no_word_that_folds_to_one_letter_is_affected(
        self, install: Callable[[str], None]
    ) -> None:
        """The cost class, and **why R1b is not R1**.

        R1 admitted every one-character token and so refused ``theo ý mình
        thì`` and ``à ngân sách…``. R1b admits one only **after a label
        word**, and a Vietnamese particle never follows one - so the AND half
        of the rule never reaches them. Measured across the particles that
        fold to a single letter: R1b costs nothing.

        This is the test that would fail first if someone "simplified" R1b
        into R1, which is the likeliest future mistake here.
        """
        claims = [
            "theo ý mình thì ngân sách tổng là 240 triệu đồng",
            "à ngân sách tổng là 240 triệu đồng",
            "ờ thì ngân sách tổng là 240 triệu đồng",
            "ngân sách tổng là 240 triệu đồng ạ",
            "ừ ngân sách tổng là 240 triệu đồng",
        ]
        assert all(_answers(claim) for claim in claims), "tien de sai o baseline"

        install("R1b")
        refused = [claim for claim in claims if not _answers(claim)]
        assert refused == [], refused

    def test_a_label_word_alone_still_changes_nothing(
        self, install: Callable[[str], None]
    ) -> None:
        """The AND half, over the label words rather than one of them.

        If the rule ever degrades into "admit single letters near these
        words", ``an toàn`` and ``mục tiêu`` start tokenising differently and
        this fails.
        """
        for phrase in [
            "an toàn thông tin",
            "mục tiêu chung",
            "bản kế hoạch",
            "cấp trên",
            "loại hình dịch vụ",
        ]:
            assert candidate_r1b(phrase) == _PRODUCTION_SUBJECT_TOKENS(phrase), phrase

    def test_it_also_refuses_a_second_designator_shape(
        self, install: Callable[[str], None]
    ) -> None:
        """``muc A`` / ``muc B``, which no corpus case covers.

        Measured at baseline as a **second** instance of the same false
        answer, which is what makes the designator hole a class rather than
        one unlucky sentence.
        """
        card = CardSpec(card_id="Z2", claim="Mục A chi 60 triệu đồng cho dự án Hải Đăng.")
        claim = "mục B chi 60 triệu đồng"
        assert _answers(claim, card=card, question="Mục B chi bao nhiêu?") is True
        install("R1b")
        assert _answers(claim, card=card, question="Mục B chi bao nhiêu?") is False

    def test_a_label_word_alone_changes_nothing(
        self, install: Callable[[str], None]
    ) -> None:
        """The rule is conjunctive, so it cannot act as a general widening."""
        install("R1b")
        assert "an" in candidate_r1b("an toàn thông tin")
        assert candidate_r1b("an toàn thông tin") == candidate_r1b("an toàn thông tin")
        assert not {tok for tok in candidate_r1b("theo ý mình") if len(tok) == 1}


class TestCandidateR2:
    def test_it_closes_the_paraphrase_cases(self, install: Callable[[str], None]) -> None:
        install("R2")
        measured = offenders()
        assert "R.paraphrase.01" not in measured["false_abstention"]
        assert "R.crosscard.01" not in measured["false_answer"]

    def test_it_manufactures_a_different_false_answer(
        self, install: Callable[[str], None]
    ) -> None:
        """One instance of why R2 is rejected. **Not the whole argument.**

        ``hạn mức`` is a *limit*; ``hạn chót`` is a *deadline*. Mapping the
        syllable ``hạn`` to a canonical ``deadline`` makes a card about one
        answer a question about the other, with a date attached. Baseline
        refuses this. R2 answers it.

        On its own this establishes only "R2 introduces at least one new false
        answer off-corpus" - which is **not** the same as the claim an earlier
        version of this file made. See
        :meth:`test_the_collision_is_a_whole_word_class` for the measurement
        that actually carries the rejection.
        """
        card = CardSpec(card_id="Z3", claim="Hạn mức báo cáo đã duyệt là thứ sáu.")
        claim = "hạn chót nộp báo cáo là thứ sáu"
        question = "Hạn chót nộp báo cáo là ngày nào?"
        assert _answers(claim, card=card, question=question) is False
        install("R2")
        assert _answers(claim, card=card, question=question) is True

    def test_the_collision_is_a_whole_word_class(
        self, install: Callable[[str], None]
    ) -> None:
        """The measurement that carries the R2 rejection.

        ``hạn`` and ``chốt`` are productive syllables, so the question is not
        whether one compound collides but how many. Every card below says
        ``thứ sáu``, so only the subject differs, and the question always asks
        about ``hạn chót`` - a deadline.

        Baseline refuses all ten. R2 answers all ten. That is the bill the
        51-case corpus could not show, because it holds exactly one ``hạn``
        compound - and it is why "measure the class, not the instance" is a
        standing rule here rather than advice.
        """
        compounds = [
            "Hạn mức báo cáo đã duyệt là thứ sáu.",
            "Hạn chế báo cáo đã duyệt là thứ sáu.",
            "Thời hạn báo cáo đã duyệt là thứ sáu.",
            "Gia hạn báo cáo đã duyệt là thứ sáu.",
            "Quá hạn báo cáo đã duyệt là thứ sáu.",
            "Hết hạn báo cáo đã duyệt là thứ sáu.",
            "Giới hạn báo cáo đã duyệt là thứ sáu.",
            "Hạn ngạch báo cáo đã duyệt là thứ sáu.",
            "Chốt sổ báo cáo đã duyệt là thứ sáu.",
            "Chốt giá báo cáo đã duyệt là thứ sáu.",
        ]
        claim = "hạn chót nộp báo cáo là thứ sáu"
        question = "Hạn chót nộp báo cáo là ngày nào?"

        refused_at_baseline = [
            card
            for card in compounds
            if not _answers(
                claim,
                card=CardSpec(card_id="Z4", claim=card),
                question=question,
            )
        ]
        assert len(refused_at_baseline) == 10, refused_at_baseline

        install("R2")
        answered_under_r2 = [
            card
            for card in compounds
            if _answers(
                claim,
                card=CardSpec(card_id="Z4", claim=card),
                question=question,
            )
        ]
        assert len(answered_under_r2) == 10, answered_under_r2

    def test_on_the_corpus_r2_looks_strictly_better(
        self, install: Callable[[str], None]
    ) -> None:
        """Pinned, because this is the number that would mislead a reader.

        R1 and R1b each had a "opens no other corpus hole" test and R2 had
        none, so R2's corpus profile was measured ad hoc and its rejection
        lived only in prose. Asserting it means the prose can no longer drift
        away from it: on the corpus R2 **removes** one false answer and one
        false abstention and adds nothing. The rejection has to come from
        off-corpus evidence, and it does.
        """
        install("R2")
        measured = offenders()
        assert set(measured["false_answer"]) < set(BASELINE_FALSE_ANSWERS), measured
        assert set(measured["false_abstention"]) < set(BASELINE_FALSE_ABSTENTIONS), (
            measured
        )


class TestNothingIsLanded:
    """The boundary this whole file sits behind.

    Checked structurally rather than by reading the diff, because the thing
    being prevented is a later author moving a candidate into ``src`` and
    citing this study's favourable numbers as the approval it never was.
    """

    def test_the_production_rule_still_behaves_as_it_does_today(self) -> None:
        """**The guard that matters**, and the only behavioural one here.

        The name and content checks below are tripwires against a copy-paste;
        they would miss the same rule written differently, which is exactly
        the weakness this project has recorded about grepping for shapes. This
        one asks what the pipeline **decides**.

        It used to ask only what ``subject_tokens`` returns, which was the
        same weakness one level up: an audit landed R1b in a new helper, left
        the public name intact, and passed every check in this class while
        closing the ledger case in production. The first assertion below is
        now ``Y.letter.01``'s own outcome.

        **Still not covered:** ``_event_key`` is a second, independent
        tokeniser with its own ``len(token) > 1`` rule that does not route
        through ``subject_tokens``. No candidate here touches it, so the
        measured gains are the gains of a partial landing.

        If R1b or R1 lands, ``phuong an B`` and ``phuong an C`` stop having
        identical subject tokens and this fails - which is correct, and the
        failure message says what to do. Keeping it means the study cannot
        quietly become the implementation.
        """
        # **Bound to the DECISION, not to the name.** An audit landed R1b in a
        # new helper, redirected the internal call sites and left the public
        # ``subject_tokens`` untouched: ``Y.letter.01`` closed in production
        # and all five checks in this class passed. So the first assertion is
        # now the corpus case's own outcome, which no renaming can dodge.
        case = next(c for c in CASES if c.case_id == "Y.letter.01")
        assert run_case(case).permits_answering is True, (
            "Y.letter.01 khong con la false answer - mot ung vien da duoc ap "
            "dung o dau do trong duong quyet dinh. Neu Son da duyet: cap nhat "
            "memo, dao ledger test, roi sua test nay."
        )
        production = vars(answerability_module)["subject_tokens"]
        assert production("Phương án B") == production("Phương án C"), (
            "subject_tokens da phan biet designator mot ky tu - mot ung vien "
            "da duoc ap dung. Neu Son da duyet: cap nhat memo, dao hai ledger "
            "test (Y.letter.01 va "
            "test_a_single_letter_option_label_over_refuses), roi sua test nay."
        )
        assert production("mục A") == production("mục B")
        # And the paraphrase half. Stated as **containment**, not as an empty
        # intersection: the two share "bao cao" and always will, and it is
        # containment that the subject check actually asks for.
        assert not production("hạn chót nộp báo cáo") <= production("deadline báo cáo")

    def test_no_candidate_function_exists_in_src(self) -> None:
        defined: set[str] = set()
        for path in SRC.rglob("*.py"):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
                    defined.add(node.name)
        # Named exactly, not by prefix: ``candidate_ids`` is a real function
        # in the package, and a prefix match reported it as a leaked
        # candidate. A check that fires on an innocent name teaches the next
        # author to loosen it, which is how the real check gets lost.
        assert not ({"candidate_r1", "candidate_r1b", "candidate_r2"} & defined), defined

    def test_the_label_word_set_is_not_in_src(self) -> None:
        """The table itself, wherever it were named.

        Asserted on the *contents* rather than on the name ``LABEL_WORDS``, so
        copying the set under another name is caught too. Checked against
        ``src`` only, which is why this file may hold it.
        """
        distinctive = {"phien", "kieu", "nhom"}
        for path in SRC.rglob("*.py"):
            source = path.read_text(encoding="utf-8")
            quoted = set(re.findall(r'"([a-z]+)"', source))
            assert not distinctive <= quoted, path

    def test_the_synonym_table_is_not_in_src(self) -> None:
        for path in SRC.rglob("*.py"):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if not isinstance(node, ast.Dict):
                    continue
                values = {
                    item.value
                    for item in node.values
                    if isinstance(item, ast.Constant) and isinstance(item.value, str)
                }
                assert "deadline" not in values, f"{path}: {values}"

    def test_the_production_tokeniser_is_unchanged_by_this_module(self) -> None:
        """Import-time safety: loading the study may not install anything.

        ``monkeypatch`` undoes a rebinding at teardown, but a module-level
        assignment would not be undone at all, and would be invisible in every
        other test file's results.
        """
        # Read out of the module dict, because ``retrieval`` re-imports the
        # name rather than defining it and attribute access on a re-export is
        # not something mypy will grant.
        in_answerability = vars(answerability_module)["subject_tokens"]
        in_retrieval = vars(retrieval_module)["subject_tokens"]
        assert in_answerability.__module__ == "meetai.answerability"
        assert in_retrieval.__module__ == "meetai.answerability"
        assert in_answerability is in_retrieval


class TestAcceptanceCriterionIsPending:
    def test_the_decision_is_recorded_as_unresolved(self) -> None:
        """No candidate may land before the operator sets the criterion.

        The memo is the artefact that would carry an answer, so its absence
        or a silent edit removing the pending marker is a failure here.
        """
        memo = (
            Path(__file__).resolve().parent.parent
            / "docs"
            / "research"
            / "2026-10-09-do-bao-phu-claim-evidence.md"
        )
        assert memo.exists(), memo
        text = memo.read_text(encoding="utf-8")
        assert "[CHỜ BẰNG CHỨNG]" in text or "[ĐỀ XUẤT]" in text, "memo thieu nhan"
        assert "R1b" in text
        assert "R2" in text


def _answers(
    claim: str,
    *,
    card: CardSpec | None = None,
    question: str = "Ngân sách tổng là bao nhiêu?",
) -> bool:
    spec = card or CardSpec(
        card_id="Z1", claim="Ngân sách tổng đã duyệt là 240 triệu đồng."
    )
    assessment = assess(
        question=MeetingContent(question),
        answer=MeetingContent(f"Theo ghi chú đã duyệt, {claim}."),
        claims=(Claim(text=MeetingContent(claim), evidence_id=spec.card_id),),
        cards=(build_card(spec),),
        cited_ids=(spec.card_id,),
        now=1000.0,
    )
    return assessment.permits_answering
