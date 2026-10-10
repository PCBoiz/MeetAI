"""Contract tests for the ASR scorer (S2.2).

Runs with no dataset and no GPU, so it belongs in the default suite. The
measurement itself cannot live here - it needs gigabytes of audio and minutes
of GPU - and a test that silently skips on every clean checkout would be a
closed evidence gate wearing a test's clothes. The threshold logic therefore
stays in the benchmark script's exit code; what is asserted here is the
arithmetic and the normalisation contract.

Every Vietnamese string below was written for this file. None is copied from
FLEURS or VIVOS - partly because corpus text must not enter git at all, and
specifically because VIVOS is CC BY-NC-SA and ShareAlike propagates to
derivatives.
"""

from __future__ import annotations

import sys
import unicodedata
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "benchmarks"))

from scoring import (
    EMPTY,
    Counts,
    NonSpeechResult,
    Op,
    bootstrap_syer,
    character_counts,
    fold_diacritics,
    non_speech_output_rate,
    normalise,
    score_failed_utterance,
    score_utterance,
    syllables,
)


class TestNfcIsMandatory:
    """The trap that silently destroys a WER number.

    Measured before writing this: the same sentence as NFC reference against
    NFD hypothesis scores SyER 0.875 - seven of eight tokens "wrong" on text
    that is character for character identical. Remove the NFC step and these
    tests fail, which is the property the project asks of a mechanism.
    """

    SENTENCE = "anh Tuấn sẽ gửi báo cáo thứ năm"

    def test_nfd_and_nfc_score_identical(self) -> None:
        nfd = unicodedata.normalize("NFD", self.SENTENCE)
        assert nfd != self.SENTENCE, "fixture khong con la NFD"
        counts, _ = score_utterance(self.SENTENCE, nfd)
        assert counts.errors == 0
        assert counts.syer == 0.0

    def test_nfd_and_nfc_tokenise_identically(self) -> None:
        nfd = unicodedata.normalize("NFD", self.SENTENCE)
        assert syllables(self.SENTENCE) == syllables(nfd)

    def test_character_counts_are_unaffected_by_form(self) -> None:
        """CER is where the denominator swing shows up: 31 vs 41 characters."""
        nfd = unicodedata.normalize("NFD", self.SENTENCE)
        assert character_counts(self.SENTENCE, nfd).errors == 0

    def test_normalise_output_is_nfc(self) -> None:
        nfd = unicodedata.normalize("NFD", self.SENTENCE)
        assert unicodedata.is_normalized("NFC", normalise(nfd))


class TestPunctuationBecomesSpace:
    """Removing punctuation to the empty string merges tokens.

    That manufactures a substitution and a deletion out of nothing, and it is
    what the obvious library helper does.
    """

    def test_punctuation_does_not_merge_tokens(self) -> None:
        assert syllables("Hà Nội,Thành phố") == ["Hà", "Nội", "Thành", "phố"]

    def test_trailing_punctuation_is_not_an_error(self) -> None:
        counts, _ = score_utterance("mình gửi báo cáo", "mình gửi báo cáo.")
        assert counts.errors == 0

    def test_symbols_are_handled_too(self) -> None:
        """Percent and currency are category S, not P. A P-only filter leaves
        them and they become spurious tokens."""
        assert syllables("tăng 5% nữa") == ["tăng", "5", "nữa"]

    def test_non_breaking_space_separates(self) -> None:
        """A plain split on " " leaves U+00A0 and glues two syllables."""
        nbsp = chr(0x00A0)
        assert syllables(f"báo{nbsp}cáo") == ["báo", "cáo"]


class TestHeadlineKeepsTheSignal:
    """What the headline contract must NOT forgive."""

    def test_diacritics_are_not_folded(self) -> None:
        """thư (letter) vs thứ (weekday). Folding both to "thu" is exactly the
        error class the project cares about."""
        counts, _ = score_utterance("gửi thư cho Lan", "gửi thứ cho Lan")
        assert counts.substitutions == 1
        assert counts.syer == pytest.approx(1 / 4)

    def test_case_is_not_folded(self) -> None:
        """Capitalisation is the only text signal for a proper noun."""
        counts, _ = score_utterance("bạn Hoa đã gửi", "bạn hoa đã gửi")
        assert counts.substitutions == 1

    def test_folding_is_available_only_as_a_diagnostic(self) -> None:
        """The folded figure exists so the gap can be reported, and the gap is
        the diacritic error mass."""
        assert fold_diacritics("thứ") == fold_diacritics("thư") == "thu"
        assert fold_diacritics("Mình") == fold_diacritics("Minh") == "minh"
        assert fold_diacritics("đúng") == "dung"


class TestEmptyReferenceIsNotZero:
    """SyER on an empty reference is undefined, not clean."""

    def test_empty_reference_has_no_syer(self) -> None:
        counts, _ = score_utterance("", "Hãy đăng ký kênh")
        assert counts.ref_tokens == 0
        assert counts.syer is None
        assert counts.insertion_rate is None
        assert counts.insertions == 4

    def test_empty_both_sides_is_no_error(self) -> None:
        """Silence in, silence out is the correct answer."""
        counts, _ = score_utterance("", "")
        assert counts.errors == 0
        assert counts.syer is None

    def test_pooled_rate_is_none_when_nothing_has_a_reference(self) -> None:
        assert EMPTY.syer is None


class TestFailuresKeepTheDenominator:
    """Timeout, OOM, empty output and crash all count, denominator unchanged."""

    def test_failed_utterance_scores_one_hundred_percent(self) -> None:
        counts = score_failed_utterance("mình sẽ gửi lại báo cáo")
        assert counts.ref_tokens == 6
        assert counts.deletions == 6
        assert counts.syer == 1.0

    def test_failure_cannot_be_hidden_by_dropping_the_clip(self) -> None:
        """Pooling a failure must move the rate, otherwise dropping clips is a
        silent improvement."""
        good, _ = score_utterance("mình gửi báo cáo", "mình gửi báo cáo")
        bad = score_failed_utterance("mình gửi báo cáo")
        pooled = good.plus(bad)
        assert pooled.ref_tokens == 8
        assert pooled.syer == pytest.approx(0.5)


class TestInsertionsAreUnbounded:
    """Why Rate cannot be reused for SyER."""

    def test_syer_can_exceed_one(self) -> None:
        """A repetition loop produces more insertions than reference tokens.
        Clamping this to 100% would destroy the signal the group exists for."""
        counts, _ = score_utterance("xong rồi", "xong rồi xong rồi xong rồi xong rồi")
        assert counts.syer is not None
        assert counts.syer > 1.0

    def test_rate_would_reject_it(self) -> None:
        """Asserted against the real class so the claim cannot go stale."""
        from meetai.evaluation import Rate

        with pytest.raises(ValueError):
            Rate(numerator=6, denominator=2)

    def test_insertion_rate_is_reported_separately(self) -> None:
        """An insertion is MeetAI saying something nobody said; a deletion is
        MeetAI missing something. They are not interchangeable."""
        counts, _ = score_utterance("mình gửi báo cáo", "mình gửi thêm báo cáo")
        assert counts.insertions == 1
        assert counts.deletions == 0
        assert counts.insertion_rate == pytest.approx(0.25)


class TestAlignment:
    """The alignment must be usable for per-class attribution."""

    def test_operations_cover_every_reference_token(self) -> None:
        _, steps = score_utterance("một hai ba bốn", "một hai ba bốn")
        assert [s.op for s in steps] == [Op.EQUAL] * 4

    def test_substitution_keeps_both_indices(self) -> None:
        _, steps = score_utterance("một hai ba", "một bảy ba")
        subs = [s for s in steps if s.op is Op.SUBSTITUTE]
        assert len(subs) == 1
        assert subs[0].ref_index == 1
        assert subs[0].hyp_index == 1

    def test_deletion_has_no_hypothesis_index(self) -> None:
        _, steps = score_utterance("một hai ba", "một ba")
        dels = [s for s in steps if s.op is Op.DELETE]
        assert len(dels) == 1
        assert dels[0].hyp_index is None

    def test_insertion_has_no_reference_index(self) -> None:
        _, steps = score_utterance("một ba", "một hai ba")
        ins = [s for s in steps if s.op is Op.INSERT]
        assert len(ins) == 1
        assert ins[0].ref_index is None

    def test_tie_break_is_deterministic(self) -> None:
        """Alignment is not unique, so an undeclared tie-break makes per-class
        numbers depend on an implementation detail."""
        first = score_utterance("a b c d", "a x y d")[1]
        for _ in range(20):
            assert score_utterance("a b c d", "a x y d")[1] == first

    def test_counts_match_the_steps(self) -> None:
        counts, steps = score_utterance("một hai ba bốn", "một bảy ba")
        assert counts.substitutions == sum(1 for s in steps if s.op is Op.SUBSTITUTE)
        assert counts.deletions == sum(1 for s in steps if s.op is Op.DELETE)
        assert counts.insertions == sum(1 for s in steps if s.op is Op.INSERT)


class TestNonSpeech:
    """Hallucination needs its own metric because the denominator is clips."""

    def test_any_output_counts_as_hallucination(self) -> None:
        result = non_speech_output_rate(
            ["", "Hãy đăng ký kênh", "", "cảm ơn các bạn"], [5.0, 5.0, 5.0, 3.0]
        )
        assert result.clips == 4
        assert result.clips_with_output == 2
        assert result.output_rate == 0.5

    def test_silence_in_silence_out_is_not_hallucination(self) -> None:
        result = non_speech_output_rate(["", "", ""], [5.0, 5.0, 5.0])
        assert result.clips_with_output == 0
        assert result.output_rate == 0.0

    def test_severity_is_duration_normalised(self) -> None:
        """The rate saturates: three tokens and three hundred both score 100%."""
        few = non_speech_output_rate(["một hai"], [60.0])
        many = non_speech_output_rate([" ".join(["một"] * 60)], [60.0])
        assert few.output_rate == many.output_rate == 1.0
        assert many.tokens_per_minute is not None
        assert few.tokens_per_minute is not None
        assert many.tokens_per_minute > few.tokens_per_minute

    def test_render_always_carries_the_denominator(self) -> None:
        rendered = non_speech_output_rate(["x"], [1.0]).render()
        assert "/1" in rendered

    def test_empty_partition_has_no_rate(self) -> None:
        result = NonSpeechResult(0, 0, 0, 0.0)
        assert result.output_rate is None
        assert "n/a" in result.render()

    def test_mismatched_lengths_are_refused(self) -> None:
        with pytest.raises(ValueError):
            non_speech_output_rate(["a", "b"], [1.0])


class TestBootstrap:
    """Uncertainty over utterances, not a binomial over tokens."""

    def test_interval_brackets_the_point_estimate(self) -> None:
        per = [Counts(1, 0, 0, 10) for _ in range(40)]
        interval = bootstrap_syer(per, replicates=400, seed=1)
        assert interval is not None
        low, high = interval
        assert low <= 0.1 <= high

    def test_deterministic_for_a_seed(self) -> None:
        per = [Counts(2, 1, 0, 12) for _ in range(30)]
        assert bootstrap_syer(per, replicates=200, seed=5) == bootstrap_syer(
            per, replicates=200, seed=5
        )

    def test_blocks_widen_the_interval(self) -> None:
        """Utterances from one recording are not independent; ignoring that
        makes the interval too narrow in the flattering direction."""
        per = [Counts(1, 0, 0, 10) for _ in range(10)] + [
            Counts(5, 0, 0, 10) for _ in range(10)
        ]
        blocks = ["rec_a"] * 10 + ["rec_b"] * 10
        plain = bootstrap_syer(per, replicates=600, seed=3)
        blocked = bootstrap_syer(per, blocks=blocks, replicates=600, seed=3)
        assert plain is not None and blocked is not None
        assert (blocked[1] - blocked[0]) > (plain[1] - plain[0])

    def test_empty_input_has_no_interval(self) -> None:
        assert bootstrap_syer([]) is None

    def test_mismatched_blocks_are_refused(self) -> None:
        with pytest.raises(ValueError):
            bootstrap_syer([Counts(0, 0, 0, 1)], blocks=["a", "b"])


class TestNoForbiddenMetric:
    """The project reports no accuracy and no F1, by design."""

    def test_module_defines_no_accuracy_or_f1(self) -> None:
        source = (
            Path(__file__).resolve().parent.parent / "benchmarks" / "scoring.py"
        ).read_text(encoding="utf-8")
        lowered = source.lower()
        for forbidden in ("def accuracy", "def f1", "def precision", "def recall"):
            assert forbidden not in lowered, forbidden

    def test_render_is_ascii(self) -> None:
        """Terminal output must be ASCII; Vietnamese belongs in UTF-8 files."""
        from scoring import GroupResult

        group = GroupResult(name="fleurs_dev")
        counts, _ = score_utterance("gửi thư cho Lan", "gửi thứ cho Lan")
        group.add(counts, char=character_counts("gửi thư", "gửi thứ"))
        group.render().encode("ascii")

    def test_scoring_contract_is_recorded(self) -> None:
        """A number is only meaningful next to the contract that produced it."""
        from scoring import SCORING_CONTRACT

        assert "nfc" in SCORING_CONTRACT
        assert "no-fold" in SCORING_CONTRACT


class TestPerClassAnalysis:
    """Classes come from the reference only, and the tagger states its limits."""

    def test_classes_come_from_the_reference_not_the_hypothesis(self) -> None:
        """The direction that matters. If classes were tagged from the
        hypothesis, deleting a hard name would shrink the denominator the model
        is judged on, and the metric would reward deletion."""
        from scoring import TokenClass, score_classes

        reference = "anh Tuấn gửi cho Hà Nội"
        full = score_classes(reference, "anh Tuấn gửi cho Hà Nội")
        deleted = score_classes(reference, "anh gửi cho")
        assert (
            full[TokenClass.PROPER_NOUN].ref_tokens
            == deleted[TokenClass.PROPER_NOUN].ref_tokens
        )
        assert deleted[TokenClass.PROPER_NOUN].deletions > 0

    def test_dates_take_precedence_over_numbers(self) -> None:
        """A date span contains numbers; without declared precedence one error
        would be counted twice and the class rates would mean nothing."""
        from scoring import TokenClass, classify_reference_tokens

        tags = classify_reference_tokens(syllables("gửi ngày 15 tháng 3"))
        assert TokenClass.NUMBER not in tags.values()
        assert tags[2] is TokenClass.DATE

    def test_classes_are_mutually_exclusive(self) -> None:
        from scoring import classify_reference_tokens

        tokens = syllables("anh Tuấn gửi báo cáo ngày 15 tháng 3 cho Hà Nội")
        tags = classify_reference_tokens(tokens)
        assert len(tags) == len(set(tags.keys()))

    def test_sentence_initial_token_is_not_tagged_a_proper_noun(self) -> None:
        """Capitalisation is the only text signal, and a sentence-initial name
        is indistinguishable from a sentence-initial ordinary word. Losing
        those keeps the denominator honest instead of inflated."""
        from scoring import TokenClass, classify_reference_tokens

        tags = classify_reference_tokens(syllables("Hoa đã nở"))
        assert tags.get(0) is not TokenClass.PROPER_NOUN

    def test_proper_noun_substitution_is_attributed(self) -> None:
        from scoring import TokenClass, score_classes

        results = score_classes("anh Tuấn gửi", "anh Tuân gửi")
        assert results[TokenClass.PROPER_NOUN].substitutions == 1
        assert results[TokenClass.PROPER_NOUN].ref_tokens == 1

    def test_boundary_insertions_are_counted_separately(self) -> None:
        """An insertion sits between reference positions, so at a span edge it
        is undecidable which side owns it. Counted apart so the convention's
        effect is visible rather than silently inflating or vanishing."""
        from scoring import TokenClass, score_classes

        results = score_classes("gửi Hà Nội", "gửi Hà Nội thêm")
        pn = results[TokenClass.PROPER_NOUN]
        assert pn.insertions_interior + pn.boundary_ambiguous_insertions >= 1

    def test_every_class_rate_carries_its_denominator(self) -> None:
        from scoring import score_classes

        for result in score_classes("anh Tuấn gửi", "anh Tuân gửi").values():
            rendered = result.render()
            assert "N=" in rendered or "n=0" in rendered

    def test_empty_class_has_no_rate(self) -> None:
        """An unmeasured class reports n/a, never 0."""
        from scoring import TokenClass, score_classes

        results = score_classes("mình gửi lại", "mình gửi lại")
        assert results[TokenClass.DATE].ref_tokens == 0
        assert results[TokenClass.DATE].token_error_rate is None
