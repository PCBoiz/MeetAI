"""Residuals an adversarial audit of the boundary found, each reproduced first.

Four holes, all independently reproduced before anything was changed, plus the
structural invariants the user asked to be enforced rather than reviewed: no
second path to a sink, and no path that reaches a sink while skipping a gate.

The order matters here. Every test in the first four classes **failed** before
its fix, and the reproduction is written as the test rather than described in a
comment, so a regression says what it is instead of saying that a number moved.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

from meetai.answerability import SupportLevel, Verdict, supporting_clause
from meetai.authority import MINIMUM_CONFIDENCE
from meetai.boundary import (
    DeliveryOutcome,
    RecordingSink,
    Stage,
    deliver,
    deliver_all,
)
from tests.test_boundary import request

SRC = Path(__file__).resolve().parent.parent / "src" / "meetai"
GATE_OWNER = "boundary.py"


def _sources() -> list[tuple[str, str]]:
    return [
        (path.name, path.read_text(encoding="utf-8"))
        for path in sorted(SRC.rglob("*.py"))
    ]


class TestAnApproximateQuantityIsAQuantity:
    """A figure no claim covers must not ride to the sink.

    Reproduced: ``"... deadline la thu sau, chi phi ha tang nua ty dong"`` was
    **delivered** as ``SUPPORTED`` with empty findings. The orphan-value check
    in ``_structure_findings`` is the only thing that makes the answer's
    content be accounted for by its claims, and it works on anchors - so a
    quantity that produced no anchor was invisible to it.

    The cause was the two-syllable floor in ``_NUMBER``, which is correct about
    ``Trâm``/``trăm`` and was silently also excluding every single-syllable
    quantifier. Every substitution case in the suite used digits, which always
    anchor, so the whole class was untested.
    """

    @pytest.mark.parametrize(
        "quantity",
        ["nua ty dong", "chuc trieu dong", "vai ty dong", "may trieu dong"],
    )
    def test_a_single_syllable_quantifier_does_not_reach_the_sink(
        self, quantity: str
    ) -> None:
        sink = RecordingSink()
        answer = (
            "Theo ghi chú đã duyệt, deadline báo cáo tháng là thứ sáu, "
            f"chi phí hạ tầng {quantity}."
        )
        outcome = deliver(
            request(answer=answer, claim_text="deadline báo cáo tháng là thứ sáu"),
            sink=sink,
        )
        assert not outcome.delivered, outcome
        assert sink.count == 0
        assert "answer_value_outside_claims:number" in outcome.rules

    @pytest.mark.parametrize("quantity", ["mot ty dong", "240 trieu dong"])
    def test_the_shapes_that_already_worked_still_work(self, quantity: str) -> None:
        """The fix must not rest on the cases that were already caught."""
        sink = RecordingSink()
        answer = (
            "Theo ghi chú đã duyệt, deadline báo cáo tháng là thứ sáu, "
            f"chi phí hạ tầng {quantity}."
        )
        outcome = deliver(
            request(answer=answer, claim_text="deadline báo cáo tháng là thứ sáu"),
            sink=sink,
        )
        assert not outcome.delivered
        assert sink.count == 0

    def test_the_two_syllable_floor_is_still_there_for_names(self) -> None:
        """The measured reason for the floor must survive the fix.

        ``Trâm`` folds to ``tram`` (hundred). The floor exists because of this
        exact collision, so the new branch has to require a scale word after
        the quantifier rather than lowering the floor.
        """
        from meetai.answerability import _NUMBER
        from meetai.authority import fold_diacritics

        assert not _NUMBER.search(fold_diacritics("Trâm phụ trách phần kiểm thử"))
        assert not _NUMBER.search(fold_diacritics("ghi chú không nêu"))
        assert _NUMBER.search(fold_diacritics("nửa tỷ đồng"))


class TestMinimumConfidenceIsAFloorNotASetting:
    """The gate's numeric check must not be switchable off by its caller.

    Reproduced: ``deliver(..., minimum_confidence=0.0)`` delivered a proposal
    with confidence 0.0 that the default refuses, and ``-5.0`` did too.
    ``deliver_all`` forwarded the value to every turn.
    """

    @pytest.mark.parametrize("floor", [0.0, -5.0, -1e9])
    def test_a_caller_cannot_lower_the_floor(self, floor: float) -> None:
        sink = RecordingSink()
        outcome = deliver(request(confidence=0.0), sink=sink, minimum_confidence=floor)
        assert not outcome.delivered, outcome
        assert sink.count == 0
        assert "low_confidence" in outcome.rules

    def test_a_caller_may_still_demand_more(self) -> None:
        """Raising the bar is a legitimate caller decision; lowering it is not."""
        sink = RecordingSink()
        assert deliver(request(confidence=0.8), sink=sink).delivered
        strict = RecordingSink()
        outcome = deliver(request(confidence=0.8), sink=strict, minimum_confidence=0.99)
        assert not outcome.delivered
        assert strict.count == 0

    def test_deliver_all_cannot_lower_it_either(self) -> None:
        sink = RecordingSink()
        outcomes = deliver_all(
            [request(confidence=0.0), request(confidence=0.0)],
            sink=sink,
            minimum_confidence=0.0,
        )
        assert not any(outcome.delivered for outcome in outcomes)
        assert sink.count == 0

    def test_the_clamp_is_in_the_source_and_not_only_in_behaviour(self) -> None:
        """Deleting the clamp must be visible, not just detectable."""
        source = (SRC / "boundary.py").read_text(encoding="utf-8")
        assert "max(minimum_confidence, MINIMUM_CONFIDENCE)" in source
        assert MINIMUM_CONFIDENCE > 0.0


class TestNoClausePrintsCardWords:
    """Meeting content must not appear on a non-emit surface either.

    Reproduced with a canary: ``repr(supporting_clause(...))`` printed
    ``inherited=frozenset({'canary', 'ngan', 'sach', ...})`` - diacritic-folded
    subject words taken straight from the card.

    The cause is a Python trap worth naming: ``@dataclass`` on a subclass
    **generates** a ``__repr__`` that overrides an inherited hand-written one,
    so the parent's shape-only repr was silently replaced.
    """

    CANARY = "ZZCANARYZZ"

    def test_the_inheriting_clause_repr_carries_no_content(self) -> None:
        clause = supporting_clause(
            "trang thai cho duyet",
            f"De xuat ngan sach {self.CANARY} 300 trieu dong, trang thai cho duyet.",
        )
        assert clause is not None
        rendered = repr(clause)
        assert self.CANARY.lower() not in rendered.lower(), rendered
        assert "ngan" not in rendered, rendered

    def test_every_clause_type_prints_shape_only(self) -> None:
        """Both halves of the fix, because either alone is undone by the next
        person who adds a field: the field is ``repr=False`` *and* the method
        is redeclared.

        The method half has to be asserted carefully, and a mutation check is
        what showed why. ``"__repr__" in _InheritingClause.__dict__`` passes
        even with the hand-written method deleted, because ``@dataclass`` then
        **generates** one into ``__dict__`` - which is the exact trap this
        whole finding was about, reappearing in the test written to catch it.
        So the assertion is that the repr is *hand-written*: a generated one
        has no docstring and carries ``__create_fn__`` in its qualname.
        """
        from dataclasses import fields

        from meetai.answerability import _InheritingClause

        own_repr = _InheritingClause.__dict__.get("__repr__")
        assert own_repr is not None
        assert "__create_fn__" not in own_repr.__qualname__, (
            "the hand-written __repr__ is gone and @dataclass generated one in "
            "its place; the generated repr prints every repr-visible field"
        )
        assert own_repr.__doc__, "a generated __repr__ has no docstring"

        by_name = {f.name: f for f in fields(_InheritingClause)}
        assert not by_name["inherited"].repr
        assert not by_name["text"].repr


class TestTheStructuralTestsMatchThePropertyNotTheSpelling:
    """The AST guard must catch an emit written in a form nobody wrote yet.

    Reproduced: the previous predicate (``ast.Call`` whose ``func`` is an
    ``ast.Attribute`` named ``emit``) matched **0 of 3** evasive shapes -
        ``getattr(sink, "emit")(text)``
        ``fn = sink.emit; fn(text)``
        ``list(map(sink.emit, [text]))``
    each of which is a second boundary that satisfies "``sink.emit(...)``
    appears exactly once in ``src/``".
    """

    EVASIONS = (
        'getattr(sink, "emit")(text)',
        "fn = sink.emit\nfn(text)",
        "list(map(sink.emit, [text]))",
        "[m(text) for m in (sink.emit,)]",
    )

    @staticmethod
    def emit_references(source: str) -> list[int]:
        """Every mention of ``emit``, not only a call in ``func`` position.

        An attribute *reference* is enough, because a reference can be stored,
        mapped or passed. ``getattr`` with a literal is checked separately
        since it names the attribute as a string.
        """
        found: list[int] = []
        for node in ast.walk(ast.parse(source)):
            names_it = isinstance(node, ast.Attribute) and node.attr == "emit"
            getattrs_it = (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id == "getattr"
                and len(node.args) >= 2
                and isinstance(node.args[1], ast.Constant)
                and node.args[1].value == "emit"
            )
            if names_it or getattrs_it:
                found.append(getattr(node, "lineno", 0))
        return found

    @pytest.mark.parametrize("evasion", EVASIONS)
    def test_the_strengthened_predicate_catches_each_evasion(self, evasion: str) -> None:
        assert self.emit_references(f"def speak(sink, text):\n    {evasion}\n")

    def test_only_the_boundary_mentions_emit_at_all(self) -> None:
        """The invariant, enforced with the strengthened predicate.

        ``RecordingSink.emit`` and the one call site both live in
        ``boundary.py``; every other module in ``src/`` must not name ``emit``
        in any position.
        """
        offenders = [
            f"{name}:{line}"
            for name, source in _sources()
            if name != GATE_OWNER
            for line in self.emit_references(source)
        ]
        assert not offenders, offenders

    def test_the_boundary_has_exactly_one_emit_call(self) -> None:
        source = (SRC / GATE_OWNER).read_text(encoding="utf-8")
        calls = [
            node
            for node in ast.walk(ast.parse(source))
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "emit"
        ]
        assert len(calls) == 1, [node.lineno for node in calls]


class TestNoPathSkipsAGate:
    """A caller must not be able to reach a sink around the two checks.

    The emit guard answers "is there a second way out". These answer "is there
    a way out that skipped a check", which is a different question: a module
    could run the gates itself, in its own order, and then emit.
    """

    @pytest.mark.parametrize("gate", ["assess", "evaluate_response"])
    def test_only_the_boundary_calls_a_gate(self, gate: str) -> None:
        offenders = [
            f"{name}:{node.lineno}"
            for name, source in _sources()
            if name != GATE_OWNER
            for node in ast.walk(ast.parse(source))
            if isinstance(node, ast.Call)
            and (
                (isinstance(node.func, ast.Name) and node.func.id == gate)
                or (isinstance(node.func, ast.Attribute) and node.func.attr == gate)
            )
        ]
        assert not offenders, (
            f"{gate} is called outside {GATE_OWNER}: {offenders}. Route the "
            "proposal through boundary.deliver instead of re-running the "
            "checks, so the order of the stages has one definition."
        )

    def test_only_the_boundary_can_report_a_delivery(self) -> None:
        """``DeliveryOutcome(delivered=True)`` is a claim that text went out.

        Constructing one elsewhere would let a module report a delivery it did
        not make, which is the same lie as emitting without the gates - just
        told to the caller instead of to the meeting.
        """
        # Parameterised over every outcome-shaped name, not just the one that
        # exists: a sibling type (`DeliveryAttempt`, `SinkFailure`) would
        # escape a single-name check, and reporting a delivery nobody made
        # would be back under a new spelling.
        outcome_types = {
            "DeliveryOutcome",
            "DeliveryAttempt",
            "DeliveryResult",
            "SinkOutcome",
            "SinkFailure",
            "EmitResult",
        }
        offenders: list[str] = []
        for name, source in _sources():
            if name == GATE_OWNER:
                continue
            for node in ast.walk(ast.parse(source)):
                if (
                    isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Name)
                    and node.func.id in outcome_types
                ):
                    offenders.append(f"{name}:{node.lineno} ({node.func.id})")
        assert not offenders, offenders

    def test_the_gates_run_in_one_order_only(self) -> None:
        """Answerability before authority, as a property of the source.

        Both must run, and the cheaper honest refusal should win: a sentence
        nothing supports is refused for being unsupported rather than for
        whatever the lexicon happens to notice in it.
        """
        source = (SRC / GATE_OWNER).read_text(encoding="utf-8")
        tree = ast.parse(source)
        order = [
            node.func.id
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id in {"assess", "evaluate_response"}
        ]
        assert order == ["assess", "evaluate_response"], order

    @staticmethod
    def _deliver_fn() -> ast.FunctionDef:
        tree = ast.parse((SRC / GATE_OWNER).read_text(encoding="utf-8"))
        return next(
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.FunctionDef) and node.name == "deliver"
        )

    def test_emit_never_appears_in_a_handler_or_a_finally(self) -> None:
        """The property the previous version of this test only commented on.

        It used to assert "no ``ast.Try`` anywhere in ``deliver``", with a
        comment explaining why: a ``finally`` that emitted would run on a
        refusal path too. The comment names a property; the assertion banned a
        keyword - so the first correct sink-failure contract, a ``try/except``
        that only classifies and never emits, failed a test whose own comment
        it satisfies. A reviewer predicted that and then it happened.

        ``emit`` in a ``try`` **body** is required by the contract: that is the
        only position from which its failure can be caught. ``emit`` in a
        handler, an ``orelse`` or a ``finalbody`` is the dangerous shape,
        because each of those runs on paths the gates did not clear.
        """
        for node in ast.walk(self._deliver_fn()):
            if not isinstance(node, ast.Try):
                continue
            for region, label in (
                (node.handlers, "except"),
                (node.orelse, "else"),
                (node.finalbody, "finally"),
            ):
                for statement in region:
                    emits = [
                        inner
                        for inner in ast.walk(statement)
                        if isinstance(inner, ast.Attribute) and inner.attr == "emit"
                    ]
                    assert not emits, (
                        f"emit appears in a `{label}` block at line "
                        f"{getattr(emits[0], 'lineno', 0)}. A refusal path "
                        "must not be able to reach the sink."
                    )

    def test_no_finally_exists_at_all(self) -> None:
        """A ``finally`` is still forbidden outright, for a second reason.

        ``return`` inside ``finally`` discards an in-flight exception, which
        would turn "something went wrong" into a tidy outcome - the fail-open
        shape this project refuses elsewhere. Banning the construct is cheaper
        than reasoning about each one.
        """
        for node in ast.walk(self._deliver_fn()):
            if isinstance(node, ast.Try):
                assert not node.finalbody, getattr(node, "lineno", 0)

    def test_the_emit_is_the_last_statement_of_its_branch(self) -> None:
        """Nothing may run between the gates clearing and the text going out."""
        deliver_fn = self._deliver_fn()
        emit_line = next(
            node.lineno
            for node in ast.walk(deliver_fn)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "emit"
        )
        returns = [
            node.lineno for node in ast.walk(deliver_fn) if isinstance(node, ast.Return)
        ]
        assert max(returns) > emit_line, (emit_line, returns)


class TestRationaleIsNotEvidence:
    """A card's free-text ``rationale`` cannot ground a claim.

    The operator's instruction, made into an invariant: an emitted claim needs
    a direct evidence mapping, and free prose cannot grant extra truth or extra
    permission to speak. ``claim`` is the field that was approved; ``rationale``
    is why someone wrote it down.

    Enforced two ways, because either alone is weak. The behavioural test says
    today's code does not read it; the structural test says a future author
    cannot start reading it without deleting an assertion that explains why.
    """

    EVIDENTIAL = ("answerability.py", "authority.py", "boundary.py")

    @pytest.mark.parametrize("module", EVIDENTIAL)
    def test_no_evidential_module_mentions_rationale(self, module: str) -> None:
        source = (SRC / module).read_text(encoding="utf-8")
        hits = [
            line
            for number, line in enumerate(source.splitlines(), 1)
            if re.search(r"\brationale\b", line)
        ]
        assert not hits, (
            f"{module} now refers to `rationale`: {hits}. The claim is the "
            "field the operator approved; the rationale is free text that no "
            "review witnessed as the assertion. If this should change, it is "
            "a decision for the operator, not a refactor."
        )

    def test_a_claim_grounded_only_in_the_rationale_is_refused(self) -> None:
        """The behavioural half: put the answer in the rationale and nowhere
        else, and the claim must still be refused."""
        from dataclasses import replace

        from meetai.answerability import Claim, ClaimKind
        from meetai.boundary import ResponseRequest
        from meetai.content import MeetingContent
        from meetai.dryrun import build_store
        from meetai.response import (
            AddressContext,
            ProposedResponse,
            ResponseDecision,
            SpeechAct,
        )

        store = build_store()
        card = store.get("card-ngansach")
        assert card is not None
        # The rationale holds the asked-about figure; the claim does not.
        moved = replace(
            card,
            claim=MeetingContent("Dự án Alpha có một ghi chú ngân sách."),
            rationale=MeetingContent("Ngân sách tổng dự án Alpha là 240 triệu đồng."),
        )
        moved = moved.witnessed_approval(approved_by="Son")
        assert moved.is_retrievable_at(1000.0)

        sink = RecordingSink()
        outcome = deliver(
            ResponseRequest(
                question=MeetingContent("Ngân sách tổng dự án Alpha là bao nhiêu?"),
                proposal=ProposedResponse(
                    decision=ResponseDecision.SPEAK,
                    text=MeetingContent(
                        "Theo ghi chú đã duyệt, ngân sách tổng dự án Alpha "
                        "là 240 triệu đồng."
                    ),
                    intent=SpeechAct.CITE_APPROVED_POSITION,
                    evidence_ids=("card-ngansach",),
                    confidence=0.9,
                ),
                address=AddressContext(directly_addressed=True),
                claims=(
                    Claim(
                        text=MeetingContent(
                            "ngân sách tổng dự án Alpha là 240 triệu đồng"
                        ),
                        kind=ClaimKind.GROUNDED,
                        evidence_id="card-ngansach",
                    ),
                ),
                cards=(moved,),
                now=1000.0,
            ),
            sink=sink,
        )
        assert not outcome.delivered, outcome
        assert sink.count == 0
        assert outcome.stage is Stage.ANSWERABILITY
        assert outcome.answerability_verdict is not Verdict.SUPPORTED


class TestTheGatesEvidenceTierIsShadowed:
    """A measured fact about the boundary, recorded rather than fixed.

    The authority gate has its own evidence rules (``not_approved``,
    ``expired``, ``superseded``, ``evidence_not_found``). Measured: they cannot
    fire through ``deliver``, because a grounded claim citing such a card is
    refused by answerability first. Both layers refuse; only the earlier one is
    ever the reporter.

    Pinned as current behaviour so that a change is visible. It is **not** a
    hole - the proposal is refused either way - but a reader must not conclude
    from a green suite that the gate's evidence tier has been exercised
    end to end.
    """

    def test_an_expired_card_is_refused_by_answerability_not_by_the_gate(
        self,
    ) -> None:
        from dataclasses import replace

        from meetai.answerability import Claim, ClaimKind
        from meetai.boundary import ResponseRequest
        from meetai.content import MeetingContent
        from meetai.dryrun import build_store
        from meetai.response import (
            AddressContext,
            ProposedResponse,
            ResponseDecision,
            SpeechAct,
        )

        store = build_store()
        card = store.get("card-ngansach")
        assert card is not None
        expired = replace(card, valid_until=500.0)
        expired = replace(expired, approved_content_hash=expired.content_hash)
        assert not expired.is_retrievable_at(1000.0)

        sink = RecordingSink()
        outcome = deliver(
            ResponseRequest(
                question=MeetingContent("Ngân sách tổng dự án Alpha là bao nhiêu?"),
                proposal=ProposedResponse(
                    decision=ResponseDecision.SPEAK,
                    text=MeetingContent(
                        "Theo ghi chú đã duyệt, ngân sách tổng dự án Alpha "
                        "là 240 triệu đồng."
                    ),
                    intent=SpeechAct.CITE_APPROVED_POSITION,
                    evidence_ids=("card-ngansach",),
                    confidence=0.9,
                ),
                address=AddressContext(directly_addressed=True),
                claims=(
                    Claim(
                        text=MeetingContent(
                            "ngân sách tổng dự án Alpha là 240 triệu đồng"
                        ),
                        kind=ClaimKind.GROUNDED,
                        evidence_id="card-ngansach",
                    ),
                ),
                cards=(expired,),
                now=1000.0,
            ),
            sink=sink,
        )
        assert not outcome.delivered
        assert sink.count == 0
        # If this ever becomes Stage.AUTHORITY, the stage order changed and the
        # claim above needs rewriting - invert it, do not relax it.
        assert outcome.stage is Stage.ANSWERABILITY, (
            "the gate's evidence tier is now reachable through deliver; update "
            "this ledger entry rather than deleting it"
        )
        assert outcome.support_level is SupportLevel.NO_CITABLE_EVIDENCE


class TestTheOutcomeStillCarriesNoContent:
    """Re-asserted here because this slice added fields near it."""

    def test_the_outcome_has_no_text_field(self) -> None:
        from dataclasses import fields

        names = {f.name for f in fields(DeliveryOutcome)}
        for suspicious in ("text", "answer", "content", "message", "body"):
            assert suspicious not in names, names
