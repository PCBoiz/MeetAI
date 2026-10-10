"""The level-2 dry-run: what it demonstrates, and what it must not claim.

Two jobs. The first is that the cases keep producing the outcomes written
down beside them, so a change in either layer surfaces here naming the case
rather than moving a number in a summary. The second is that the tool itself
stays inside the boundary's discipline: it must reach the sink only through
``deliver``, print no meeting content, print ASCII, and never describe itself
as an integration.
"""

from __future__ import annotations

import ast
import json
from pathlib import Path

import pytest

from meetai.answerability import SupportLevel, Verdict
from meetai.boundary import RecordingSink, Stage
from meetai.cli import EXIT_DRYRUN_UNEXPECTED, EXIT_OK, main
from meetai.dryrun import (
    CARDS,
    CASES,
    GLOSS,
    NOW,
    SYNTHETIC_SOURCE,
    VERDICT_GLOSS,
    DryRunCase,
    build_store,
    emitted_count,
    render,
    report,
    run,
    to_request,
)

MODULE = Path(__file__).resolve().parent.parent / "src" / "meetai" / "dryrun.py"


class TestEveryCaseMatchesItsWrittenExpectation:
    """The expectations are policy, written before the run, not a snapshot.

    Two of them were wrong when first written and the measurement corrected
    them, which is the point of writing them at all: ``D4`` is ``UNSUPPORTED``
    rather than ``UNCLEAR`` because two *approved* cards disagreeing is a
    definite finding, and ``D7``'s first wording never reached the authority
    stage because its commitment clause carried a time value no claim declared.
    """

    @pytest.mark.parametrize("case", CASES, ids=lambda case: case.case_id)
    def test_the_case_lands_where_it_says(self, case: DryRunCase) -> None:
        sink = RecordingSink()
        results, _ = run(sink=sink, cases=(case,))
        outcome = results[0].outcome
        assert outcome.stage is case.expected_stage, (
            case.case_id,
            outcome.stage,
            outcome.rules,
        )
        assert outcome.answerability_verdict is case.expected_verdict, (
            case.case_id,
            outcome.answerability_verdict,
        )
        assert results[0].matches_expectation

    def test_the_whole_run_agrees(self) -> None:
        results, sink = run()
        assert len(results) == len(CASES)
        assert all(result.matches_expectation for result in results)
        assert isinstance(sink, RecordingSink)
        assert emitted_count(sink) == 1

    def test_exactly_one_case_reaches_the_sink(self) -> None:
        """A dry-run where everything is refused proves nothing.

        A fail-closed layer reaches 0 false answers trivially by refusing
        everything, so the useful assertion is that the one case built to be
        answerable *is* answered, and that it is the only one.
        """
        results, sink = run()
        delivered = [r.case_id for r in results if r.outcome.delivered]
        assert delivered == ["D1.du-evidence"], delivered
        assert emitted_count(sink) == 1

    def test_both_layers_are_exercised(self) -> None:
        """Each stage must be the decider for at least one case.

        Without this, the set could drift until every refusal came from one
        layer and the dry-run would stop showing that there are two.
        """
        results, _ = run()
        stages = {result.outcome.stage for result in results}
        assert stages == {
            Stage.DELIVERED,
            Stage.ANSWERABILITY,
            Stage.AUTHORITY,
            Stage.NOT_SPEAKING,
        }, stages

    def test_all_three_verdicts_appear(self) -> None:
        results, _ = run()
        verdicts = {
            result.outcome.answerability_verdict
            for result in results
            if result.outcome.answerability_verdict is not None
        }
        assert verdicts == {Verdict.SUPPORTED, Verdict.UNSUPPORTED, Verdict.UNCLEAR}

    def test_the_authority_stage_runs_on_a_supported_answer(self) -> None:
        """The demonstration that justifies two layers.

        ``verdict=SUPPORTED`` and ``delivered=False`` on the same case: the
        evidence held up and the gate refused anyway. If every authority
        refusal sat behind an unsupported answer, the gate would never be
        observed doing anything the evidence check had not already done.
        """
        results, _ = run()
        gated = [r for r in results if r.outcome.stage is Stage.AUTHORITY]
        assert gated, "no case reaches the authority stage any more"
        for result in gated:
            assert result.outcome.answerability_verdict is Verdict.SUPPORTED
            assert not result.outcome.delivered
            assert result.outcome.rules


class TestTheFixtureUsesTheRealApprovalPath:
    """A fixture whose cards are citable for a reason no production path
    produces would make the whole dry-run meaningless."""

    def test_cards_are_approved_through_the_store(self) -> None:
        store = build_store()
        card = store.get("card-ngansach")
        assert card is not None
        assert card.approved_content_hash == card.content_hash
        assert card.approval_matches_content
        assert card.is_retrievable_at(NOW)

    def test_an_unapproved_card_is_never_retrieved(self) -> None:
        store = build_store()
        pending = store.get("card-chuaduyet")
        assert pending is not None
        assert not pending.is_retrievable_at(NOW)
        assert pending not in store.retrieve(scope="duan-zeta")
        assert store.retrieve(scope="duan-zeta") == ()

    def test_retrieval_is_what_puts_cards_in_the_request(self) -> None:
        """The link that did not exist: store view -> ResponseRequest."""
        store = build_store()
        case = next(c for c in CASES if c.case_id == "D4.evidence-mau-thuan")
        built = to_request(case, store)
        assert len(built.cards) == 2, built.cards
        # Only one is cited; retrieval returns what the store holds, and the
        # contradiction check is over that, not over the model's selection.
        assert len(built.proposal.evidence_ids) == 1

    def test_every_fixture_card_comes_from_the_synthetic_source(self) -> None:
        store = build_store()
        for fixture in CARDS:
            card = store.get(fixture.card_id)
            assert card is not None
            assert card.source_ref == SYNTHETIC_SOURCE

    def test_the_fixture_store_permits_nothing_else(self) -> None:
        """An empty allowlist permits nothing; this one permits exactly one
        prefix, so the fixture cannot be pointed at a real source."""
        store = build_store()
        assert store.source_allowlist.permits(SYNTHETIC_SOURCE)
        for other in ("file://C:/notes", "https://example.invalid", "note://real"):
            assert not store.source_allowlist.permits(other), other


class TestTheReportCarriesNoContent:
    """The tool prints shape, never values - the same rule as the outcome.

    The content here is synthetic, so printing it would leak nothing. The rule
    holds anyway: a printer that prints content "because this content is safe"
    is a printer whose next caller prints content that is not.
    """

    def test_no_card_or_question_text_appears_in_the_report(self) -> None:
        results, sink = run()
        rendered = render(report(results, emitted=emitted_count(sink)))
        for case in CASES:
            assert case.question not in rendered
            if case.answer is not None:
                assert case.answer not in rendered
            for claim in case.claims:
                assert claim.text not in rendered
        for fixture in CARDS:
            assert fixture.claim not in rendered

    def test_only_one_function_reads_the_sink_at_all(self) -> None:
        """One accessor owns the read, and it takes a length.

        Asked of the AST rather than of the text: the first version of this
        test searched for a substring and broke the moment the read was moved
        into a typed accessor, which is a test pinning a spelling rather than
        a property. The property has two halves - exactly one function may
        name ``emitted``, and nothing anywhere may reach past its length.
        """
        tree = ast.parse(MODULE.read_text(encoding="utf-8"))
        readers = [
            node.name
            for node in ast.walk(tree)
            if isinstance(node, ast.FunctionDef)
            and any(
                isinstance(inner, ast.Constant) and inner.value == "emitted"
                for inner in ast.walk(node)
            )
        ]
        assert readers == ["emitted_count"], readers

    def test_nothing_reaches_past_the_sinks_length(self) -> None:
        """A count is evidence of delivery; an element is the content."""
        tree = ast.parse(MODULE.read_text(encoding="utf-8"))
        accessor = next(
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.FunctionDef) and node.name == "emitted_count"
        )
        # The value obtained from the sink is consumed by len() and by an
        # isinstance guard - never subscripted, never iterated, never joined.
        assert any(
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "len"
            for node in ast.walk(accessor)
        )
        for node in ast.walk(accessor):
            assert not isinstance(node, ast.Subscript), ast.dump(node)
            assert not isinstance(node, ast.For | ast.comprehension), ast.dump(node)

        # And no attribute access on `.emitted` anywhere in the module: the
        # getattr form is the single permitted shape, so a future author
        # cannot quietly add `sink.emitted[0]`.
        for node in ast.walk(tree):
            assert not (isinstance(node, ast.Attribute) and node.attr == "emitted"), (
                getattr(node, "lineno", 0)
            )

    def test_the_rendered_report_is_ascii(self) -> None:
        """Terminal output. A Windows console's code page is usually not UTF-8,
        and a report rendered as mojibake is worse than a plain one."""
        results, sink = run()
        rendered = render(report(results, emitted=emitted_count(sink)))
        assert rendered.isascii(), [c for c in rendered if not c.isascii()]

    def test_the_result_type_has_no_text_field(self) -> None:
        from dataclasses import fields

        from meetai.dryrun import DryRunResult

        names = {f.name for f in fields(DryRunResult)}
        for suspicious in ("text", "answer", "content", "question", "emitted"):
            assert suspicious not in names, names

    def test_the_json_report_carries_no_content(self) -> None:
        results, sink = run()
        blob = json.dumps(report(results, emitted=emitted_count(sink)))
        for fixture in CARDS:
            assert fixture.claim not in blob


class TestTheToolStaysInsideTheBoundary:
    """Structural, not reviewed: the dry-run must not become a second way out."""

    def test_the_module_never_calls_emit(self) -> None:
        source = MODULE.read_text(encoding="utf-8")
        for node in ast.walk(ast.parse(source)):
            assert not (isinstance(node, ast.Attribute) and node.attr == "emit"), (
                node.lineno
            )

    def test_the_module_reaches_the_sink_only_through_deliver(self) -> None:
        source = MODULE.read_text(encoding="utf-8")
        called = {
            node.func.id
            for node in ast.walk(ast.parse(source))
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
        }
        assert "deliver" in called
        for gate in ("assess", "evaluate_response"):
            assert gate not in called, gate

    def test_the_module_imports_nothing_that_can_reach_a_network(self) -> None:
        source = MODULE.read_text(encoding="utf-8")
        roots: set[str] = set()
        for node in ast.walk(ast.parse(source)):
            if isinstance(node, ast.Import):
                roots.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                roots.add(node.module.split(".")[0])
        for forbidden in (
            "socket",
            "http",
            "urllib",
            "requests",
            "httpx",
            "discord",
            "asyncio",
            "sqlite3",
            "subprocess",
        ):
            assert forbidden not in roots, roots

    def test_the_module_opens_no_file(self) -> None:
        """This module's syntax names no write - which is less than it sounds.

        The docstring here used to read "No persistence, and nothing to leave
        behind on disk". That overstated a syntactic check on one module.
        Measured at ``b814271``, ``pathlib.Path(p).open("w")`` followed by
        ``fh.write(...)`` passed it: ``open`` was checked only as a bare name,
        so the attribute form went by, and ``write`` was not on the list.
        Both are closed below.

        It is still only ``dryrun.py``'s syntax. The claim about the *process* -
        no write entry point called, repository tree unchanged afterwards -
        lives in ``tests/test_local_trial.py``, which covers ``cli.py`` and a
        ``logging`` ``FileHandler`` too.
        """
        source = MODULE.read_text(encoding="utf-8")
        names = {
            node.func.id
            for node in ast.walk(ast.parse(source))
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
        }
        attrs = {
            node.attr
            for node in ast.walk(ast.parse(source))
            if isinstance(node, ast.Attribute)
        }
        assert "open" not in names
        # ``open`` as an attribute closes ``Path(p).open("w")``; ``write``
        # closes the handle it would hand back. ``Path.replace`` is left off
        # deliberately: it collides with ``str.replace``, and a check that
        # fires on an innocent name is how the next author learns to loosen
        # the list. The process-level test covers that route instead.
        for forbidden in (
            "open",
            "write",
            "writelines",
            "write_text",
            "write_bytes",
            "mkdir",
            "makedirs",
            "touch",
            "unlink",
            "rename",
        ):
            assert forbidden not in attrs, forbidden


class TestTheReportRefusesToOverstateItself:
    """A command named "run" is the easiest thing here to mistake for
    readiness, so the output says what it is not."""

    def test_the_findings_deny_being_an_integration(self) -> None:
        results, sink = run()
        findings = report(results, emitted=emitted_count(sink))
        assert findings["level"] == "2-local-recording-sink"
        assert findings["is_production_integration"] is False
        assert findings["is_discord_test"] is False

    def test_the_rendered_header_says_what_it_is_not(self) -> None:
        results, sink = run()
        rendered = render(report(results, emitted=emitted_count(sink)))
        lowered = rendered.lower()
        assert "khong phai thu nghiem discord" in lowered
        assert "khong phai tich hop production" in lowered

    def test_no_case_shape_claims_a_meeting(self) -> None:
        for case in CASES:
            lowered = case.shape.lower()
            for overclaim in ("production", "discord", "cuoc hop that", "san sang"):
                assert overclaim not in lowered, case.case_id


class TestTheGlossCoversEveryOutcome:
    """A level with no sentence is a level an operator cannot act on."""

    def test_every_support_level_has_a_gloss(self) -> None:
        missing = [level.value for level in SupportLevel if level.value not in GLOSS]
        assert not missing, (
            f"SupportLevel members with no plain-language gloss: {missing}. "
            "Add the sentence; nine enum names printed at an operator is not "
            "the same as an operator understanding the difference."
        )

    def test_every_verdict_has_a_gloss(self) -> None:
        missing = [v.value for v in Verdict if v.value not in VERDICT_GLOSS]
        assert not missing, missing

    def test_the_gloss_names_its_layer_for_each_verdict(self) -> None:
        """``supported`` once read "noi duoc" (may speak) and printed next to
        two cases the authority gate refused. The verdict answers one question;
        reading it as the final answer is the conflation two layers exist to
        prevent."""
        for text in VERDICT_GLOSS.values():
            assert "answerability" in text.lower(), text

    def test_the_gloss_keeps_unsupported_and_unclear_apart(self) -> None:
        assert VERDICT_GLOSS["unsupported"] != VERDICT_GLOSS["unclear"]
        assert "khong kiem duoc" in VERDICT_GLOSS["unclear"].lower()
        assert "da kiem" in VERDICT_GLOSS["unsupported"].lower()

    def test_every_gloss_is_ascii(self) -> None:
        for text in (*GLOSS.values(), *VERDICT_GLOSS.values()):
            assert text.isascii(), text


class TestTheCliCommand:
    def test_the_dry_run_command_exits_zero(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        assert main(["dry-run"]) == EXIT_OK
        out = capsys.readouterr().out
        assert "dry-run cap 2" in out
        assert out.isascii()

    def test_the_json_form_is_parseable_and_denies_integration(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        assert main(["dry-run", "--json"]) == EXIT_OK
        payload = json.loads(capsys.readouterr().out)
        assert payload["is_production_integration"] is False
        assert payload["case_count"] == len(CASES)
        assert payload["emitted_to_sink"] == 1

    def test_a_deviation_exits_non_zero(self) -> None:
        """A check whose failure exits 0 is a check nobody notices."""
        assert EXIT_DRYRUN_UNEXPECTED != EXIT_OK

    def test_the_dry_run_does_not_touch_the_media_gate(self) -> None:
        """Gating this on consent would imply it is a media path.

        What stands between the operator and a meeting is that no sink exists,
        not that a flag is unset - and teaching them otherwise would make the
        consent gate look like the last line of defence.
        """
        from meetai import cli

        tree = ast.parse(Path(cli.__file__).read_text(encoding="utf-8"))
        handler = next(
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.FunctionDef) and node.name == "_dry_run"
        )
        # The AST, not the text: the handler's own docstring explains why it
        # does not consult the gate, and a substring search cannot tell an
        # explanation from a call.
        referenced = {
            node.attr for node in ast.walk(handler) if isinstance(node, ast.Attribute)
        } | {node.id for node in ast.walk(handler) if isinstance(node, ast.Name)}
        for gate in ("media_processing_allowed", "require_media_processing_allowed"):
            assert gate not in referenced, gate
        assert "settings" not in referenced


class TestNoRealPersonData:
    """Synthetic only. The fixture is committed source, so this is a property
    of the file, not of a run."""

    def test_the_cards_name_only_the_operator_and_roles(self) -> None:
        """``Son`` is the project owner and already appears throughout the
        repository; every other reference is a role word. No name list, and
        nothing inferred from a transcript - there is no transcript."""
        assert SYNTHETIC_SOURCE == "note://synthetic"
        # The claim is about the fixture CONTENT, not about the module text -
        # the first version of this test searched the whole file for "@" and
        # matched every decorator.
        content = [fixture.claim for fixture in CARDS]
        content += [case.question for case in CASES]
        content += [case.answer for case in CASES if case.answer is not None]
        content += [claim.text for case in CASES for claim in case.claims]
        for text in content:
            for marker in ("@", "+84", "http://", "https://", "09"):
                assert marker not in text, (marker, text[:40])

    def test_the_fixture_scopes_are_placeholders(self) -> None:
        for fixture in CARDS:
            assert fixture.scope.startswith("duan-"), fixture.scope
