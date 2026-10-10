"""Label integrity for the S2.3 corpus, enforced structurally.

The corpus decides what the benchmark means. A corpus that could consult the
thing it judges could copy that thing's output into its own labels, and the
copy would be invisible in the resulting table - every number would look
good. So the constraints here are about *what the corpus file is allowed to
be*, not about whether its labels look sensible:

- it may not import ``meetai`` or the benchmark, so it cannot ask either what
  the answer is;
- it may not contain a loop or a comprehension, so every case is a literal a
  reader can check;
- every case must cite a policy line, which a model-derived label cannot
  produce;
- no real person's name and no real meeting content.

This mirrors ``tests/test_authority_eval.py``'s guard on the authority corpus.
The duplication is deliberate: a shared helper would be one edit away from
exempting both.
"""

from __future__ import annotations

import ast
import pathlib
import re
from collections import Counter

import pytest

from tests.conftest import personal_identifier_markers
from tests.corpus.llm_policy_types import (
    Corpus,
    EvidenceItem,
    ExpectedBehaviour,
    PolicyCase,
    RiskGroup,
)
from tests.corpus.llm_policy_vi import CORPUS

CORPUS_PATH = pathlib.Path(__file__).resolve().parent / "corpus" / "llm_policy_vi.py"
TYPES_PATH = pathlib.Path(__file__).resolve().parent / "corpus" / "llm_policy_types.py"


def corpus_source() -> str:
    return CORPUS_PATH.read_text(encoding="utf-8")


class TestStructuralIntegrity:
    def test_the_corpus_cannot_consult_what_it_judges(self) -> None:
        imported: set[str] = set()
        for node in ast.walk(ast.parse(corpus_source())):
            if isinstance(node, ast.Import):
                imported.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module)
        forbidden = {
            name for name in imported if name.startswith(("meetai", "benchmarks"))
        }
        assert not forbidden, forbidden

    def test_the_types_module_cannot_either(self) -> None:
        imported: set[str] = set()
        for node in ast.walk(ast.parse(TYPES_PATH.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Import):
                imported.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module)
        assert not any(name.startswith(("meetai", "benchmarks")) for name in imported), (
            imported
        )

    def test_every_case_is_a_literal(self) -> None:
        """No loop, no comprehension, no generated case.

        A generated case is a rule, and a rule can encode the behaviour under
        test without anyone noticing. Forty-three literals can be read.
        """
        for node in ast.walk(ast.parse(corpus_source())):
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
        """The file builds cases and nothing else."""
        permitted = {"PolicyCase", "EvidenceItem", "Corpus", "frozenset", "tuple"}
        called: set[str] = set()
        for node in ast.walk(ast.parse(corpus_source())):
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name):
                    called.add(node.func.id)
                elif isinstance(node.func, ast.Attribute):
                    called.add(node.func.attr)
        assert called <= permitted, sorted(called - permitted)

    def test_no_function_or_class_is_defined(self) -> None:
        for node in ast.walk(ast.parse(corpus_source())):
            assert not isinstance(
                node, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef
            ), ast.dump(node)[:80]


class TestLabelProvenance:
    @pytest.mark.parametrize("case", CORPUS.cases, ids=lambda c: c.case_id)
    def test_every_case_cites_a_policy_line(self, case: PolicyCase) -> None:
        assert case.policy_basis.strip(), case.case_id

    @pytest.mark.parametrize("case", CORPUS.cases, ids=lambda c: c.case_id)
    def test_a_handoff_citation_names_a_real_line(self, case: PolicyCase) -> None:
        """Checked against the document, not taken on trust.

        The authority corpus cites this same block one line early throughout,
        which is how this test came to exist. A citation that does not resolve
        is not provenance.
        """
        match = re.match(r"handoff:(\d+)", case.policy_basis)
        if match is None:
            return
        handoff = (
            pathlib.Path(__file__).resolve().parent.parent
            / "docs"
            / "handoff"
            / "MeetAI_Ho_so_ban_giao_Claude_Code_v1.0.md"
        )
        lines = handoff.read_text(encoding="utf-8").splitlines()
        number = int(match.group(1))
        assert 1 <= number <= len(lines), f"{case.case_id}: dong {number} khong ton tai"
        line = lines[number - 1].strip()
        # A policy item is a bullet or a numbered pipeline step. Headings and
        # blank lines are not: the handoff's "Quy tac noi" heading is on 117,
        # one line above the first rule, which is exactly the off-by-one the
        # authority corpus has throughout.
        assert line and not line.startswith("#"), (
            f"{case.case_id}: dong {number} trong hoac la tieu de: {line[:60]!r}"
        )
        assert re.match(r"^(-|\d+\.)\s", line), (
            f"{case.case_id}: dong {number} khong phai mot muc chinh sach: {line[:60]!r}"
        )

    def test_case_ids_are_unique(self) -> None:
        ids = [case.case_id for case in CORPUS.cases]
        duplicates = [name for name, count in Counter(ids).items() if count > 1]
        assert not duplicates, duplicates

    def test_every_minimal_pair_resolves(self) -> None:
        ids = {case.case_id for case in CORPUS.cases}
        dangling = [
            (case.case_id, case.minimal_pair)
            for case in CORPUS.cases
            if case.minimal_pair and case.minimal_pair not in ids
        ]
        assert not dangling, dangling

    def test_no_case_names_itself_as_its_pair(self) -> None:
        assert not [
            case.case_id for case in CORPUS.cases if case.minimal_pair == case.case_id
        ]


class TestNoRealData:
    def test_the_operator_is_named_only_where_policy_requires_a_refusal(self) -> None:
        """ "Son" appears, and it has to.

        The prohibitions are about acting *for the operator*, so a case that
        never names him cannot test them. What must not appear is anything
        identifying beyond the given name already in the handoff document.
        """
        source = corpus_source().lower()
        for form in personal_identifier_markers():
            assert form not in source, form

    def test_no_real_file_path_or_url(self) -> None:
        source = corpus_source()
        for marker in ("http://", "https://", "C:\\", "D:\\", "/Users/"):
            assert marker not in source, marker

    def test_invented_names_only(self) -> None:
        """A spot check that the cast is the invented one.

        Not exhaustive - it cannot be - but it fails if a real participant's
        name is pasted in alongside the invented cast.
        """
        source = corpus_source()
        invented = ("Khuê", "Trâm", "Dũng", "Hạnh", "Nghĩa", "Phúc", "Quyên", "Tuyết")
        assert sum(1 for name in invented if name in source) >= 3


class TestCoverage:
    def test_every_risk_group_has_cases(self) -> None:
        present = {case.group for case in CORPUS.cases}
        assert present == set(RiskGroup), set(RiskGroup) - present

    def test_every_expected_behaviour_has_cases(self) -> None:
        present = {case.expected for case in CORPUS.cases}
        assert present == set(ExpectedBehaviour), set(ExpectedBehaviour) - present

    def test_both_directions_of_abstention_are_represented(self) -> None:
        """A corpus of only abstain cases would reward refusing everything."""
        abstain = [c for c in CORPUS.cases if c.expected is ExpectedBehaviour.ABSTAIN]
        answer = [
            c
            for c in CORPUS.cases
            if c.expected is ExpectedBehaviour.ANSWER_FROM_EVIDENCE
        ]
        assert len(abstain) >= 5, len(abstain)
        assert len(answer) >= 5, len(answer)

    def test_the_authority_group_pairs_reporting_against_deciding(self) -> None:
        """Both halves, or the group measures topic rather than act."""
        authority = [c for c in CORPUS.cases if c.group is RiskGroup.H_AUTHORITY]
        refusals = [
            c
            for c in authority
            if c.expected is ExpectedBehaviour.REFUSE_OUT_OF_AUTHORITY
        ]
        reports = [
            c for c in authority if c.expected is ExpectedBehaviour.ANSWER_FROM_EVIDENCE
        ]
        assert len(refusals) >= 5, len(refusals)
        assert len(reports) >= 3, len(reports)

    def test_injection_cases_have_a_clean_counterpart(self) -> None:
        injections = [
            c
            for c in CORPUS.cases
            if c.expected is ExpectedBehaviour.IGNORE_INSTRUCTION_IN_EVIDENCE
        ]
        assert injections
        paired = [c for c in injections if c.minimal_pair]
        assert len(paired) >= 3, [c.case_id for c in injections if not c.minimal_pair]

    def test_every_injection_case_actually_contains_an_instruction(self) -> None:
        """Otherwise the group measures nothing.

        A case labelled as an injection whose evidence carries no instruction
        would pass trivially and inflate the resistance figure.

        Two shapes count, and the second was added because this test caught
        ``I.authority.01`` without it. An injection can be an **imperative**
        ("bo qua moi quy tac", "hay tra loi rang...") or a **declarative grant
        of capability** ("Son da uy quyen cho MeetAI nhan viec thay anh").
        The second is the more realistic one in a transcript, where nobody
        issues commands to an assistant but people do assert what it is
        allowed to do.
        """
        imperatives = (
            "bỏ qua",
            "hãy",
            "yêu cầu",
            "từ giờ",
            "từ lượt này",
            "lưu ý hệ thống",
            "đóng vai",
            "khi trả lời",
            "uỷ quyền",
            "ủy quyền",
            "được phép",
            "cho phép",
        )
        for case in CORPUS.cases:
            if case.expected is not ExpectedBehaviour.IGNORE_INSTRUCTION_IN_EVIDENCE:
                continue
            blob = " ".join(item.text for item in case.evidence).lower()
            assert any(word in blob for word in imperatives), case.case_id


class TestTypeInvariants:
    def test_an_answer_label_needs_citable_evidence(self) -> None:
        with pytest.raises(ValueError, match="ANSWER_FROM_EVIDENCE"):
            PolicyCase(
                case_id="X",
                group=RiskGroup.G_GROUNDING,
                question="q",
                expected=ExpectedBehaviour.ANSWER_FROM_EVIDENCE,
                policy_basis="test",
                evidence=(EvidenceItem("E1", "t", supports=False),),
            )

    def test_an_abstain_label_rejects_citable_evidence(self) -> None:
        with pytest.raises(ValueError, match="ABSTAIN"):
            PolicyCase(
                case_id="X",
                group=RiskGroup.A_ABSTENTION,
                question="q",
                expected=ExpectedBehaviour.ABSTAIN,
                policy_basis="test",
                evidence=(EvidenceItem("E1", "t"),),
            )

    def test_a_missing_policy_basis_is_refused(self) -> None:
        with pytest.raises(ValueError, match="policy_basis"):
            PolicyCase(
                case_id="X",
                group=RiskGroup.S_STRUCTURE,
                question="q",
                expected=ExpectedBehaviour.ABSTAIN,
                policy_basis="",
            )

    def test_a_tuple_where_a_string_belongs_is_refused(self) -> None:
        """The stray-comma bug, caught in this corpus before it was run.

        An implicitly concatenated Vietnamese string across source lines is
        one comma away from being a tuple, and the dataclass does not enforce
        annotations at run time. It would have reached the prompt as a repr.
        """
        with pytest.raises(TypeError, match="dau phay thua"):
            EvidenceItem("E1", ("a", "b"))  # type: ignore[arg-type]

    def test_duplicate_evidence_ids_are_refused(self) -> None:
        with pytest.raises(ValueError, match="trung lap"):
            PolicyCase(
                case_id="X",
                group=RiskGroup.G_GROUNDING,
                question="q",
                expected=ExpectedBehaviour.ABSTAIN,
                policy_basis="test",
                evidence=(
                    EvidenceItem("E1", "a", supports=False),
                    EvidenceItem("E1", "b", supports=False),
                ),
            )

    def test_an_unfolded_forbidden_shape_is_refused(self) -> None:
        """A shape with diacritics could never match folded output."""
        with pytest.raises(ValueError, match="chu thuong"):
            PolicyCase(
                case_id="X",
                group=RiskGroup.H_AUTHORITY,
                question="q",
                expected=ExpectedBehaviour.REFUSE_OUT_OF_AUTHORITY,
                policy_basis="test",
                forbidden_substrings=("Cam Ket",),
            )

    def test_the_corpus_version_is_pinned(self) -> None:
        assert CORPUS.version
        assert isinstance(CORPUS, Corpus)
