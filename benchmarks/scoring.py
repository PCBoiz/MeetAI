"""Scoring for the Vietnamese ASR evaluation (S2.2).

Hand-rolled rather than taken from a library, for reasons that are about
correctness rather than dependency count:

- The per-class analysis needs the **alignment**, with a tie-break this project
  declares and can document. No library exposes a tie-break you control.
- The block bootstrap needs per-utterance ``(S, D, I, N)`` persisted, which is
  a data-shape requirement a distance function cannot satisfy.
- The empty-reference rule here differs from every library's. ``jiwer`` returns
  ``wer = num_insertions`` for an empty reference, which is an unbounded count
  reported in the units of a rate.
- ``python-Levenshtein`` is **GPL-2.0-or-later**, and this project is MIT.
  ``evaluate`` resolves its metric by downloading and executing a module from
  the Hugging Face Hub, which is remote code execution on the scoring path and
  flatly incompatible with an offline, no-egress project.

**The metric is SyER, not WER, and the name matters.** Vietnamese writes
syllables separated by spaces, so a whitespace token is a syllable and not a
word. The VLSP ASR challenge uses Syllable Error Rate for exactly this reason,
and a participant paper reports that applying word segmentation to the labels
did not improve the system. Calling a whitespace-token metric "WER" invites the
objection that the tokens are not words; calling it SyER states the contract.

**NFC normalisation is mandatory and it is step one.** Measured on this
machine: the same sentence as NFC reference against NFD hypothesis scores
SyER 0.875 and CER 0.548 - 7 of 8 tokens "wrong" on text that is character for
character identical. After NFC on both sides it is 0.0. NFC is total and
lossless for Vietnamese, so this hides nothing. ``d`` with stroke is a single
code point that NFD does not decompose, which is why diacritic folding needs
its own explicit map and why folding is not used here at all.

Everything this module refuses to do, and why:

- **No diacritic folding on the headline.** Settled project policy. Folding
  collapses ``Thư/Thứ/Thu/Thủ`` and ``Minh/Mình``, which is the error class the
  project cares about most. A folded figure is reported only as a labelled
  secondary diagnostic, and the informative quantity is the *gap*.
- **No case folding on the headline.** Capitalisation is the only text-level
  signal for a proper noun, and the per-class analysis needs it.
- **No digit/word rewriting, no abbreviation expansion.** Those are inverse
  text normalisation, a program with its own bugs in both directions. Variants
  belong in corpus data, not in the scorer.
- **No accuracy, no F1, no ``1 - SyER``.** Same reason
  :mod:`meetai.evaluation` has none: a deletion (a missed commitment) and an
  insertion (an invented one) are not commensurable, and pooling them lets an
  improvement in the cheap direction pay for a regression in the expensive one.
"""

from __future__ import annotations

import random
import unicodedata
from dataclasses import dataclass, field
from enum import Enum

# Unicode categories treated as punctuation or symbols. Replaced with a SPACE,
# never with the empty string: empty-string removal merges tokens across the
# punctuation, which manufactures a substitution and a deletion out of nothing.
_PUNCT_CATEGORIES = frozenset({"Pc", "Pd", "Pe", "Pf", "Pi", "Po", "Ps"})
_SYMBOL_CATEGORIES = frozenset({"Sc", "Sk", "Sm", "So"})

SCORING_CONTRACT = "syer.v1.nfc.punct-to-space.case-sensitive.no-fold"
"""Recorded into every results file. A number is only meaningful next to the
contract that produced it, and this string changes when the contract does."""


def normalise(text: str) -> str:
    """Apply the headline contract. NFC first, always.

    Order is load-bearing: NFC before anything else, because a decomposed
    sequence would otherwise have its combining marks treated as separate
    characters by the punctuation pass and by CER.
    """
    text = unicodedata.normalize("NFC", text)
    out: list[str] = []
    for ch in text:
        category = unicodedata.category(ch)
        if category in _PUNCT_CATEGORIES or category in _SYMBOL_CATEGORIES:
            out.append(" ")
        elif category.startswith("C") or category.startswith("Z"):
            # Control characters and every Unicode separator, including
            # NO-BREAK SPACE. A plain split() would leave U+00A0 in place and
            # glue two syllables into one token.
            out.append(" ")
        else:
            out.append(ch)
    return " ".join("".join(out).split())


def syllables(text: str) -> list[str]:
    """Tokenise into syllables. Whitespace is the syllable boundary."""
    return normalise(text).split()


def fold_diacritics(text: str) -> str:
    """Diacritic folding, for the SECONDARY diagnostic only.

    Never used for a headline number. Present so the folded/unfolded gap can
    be reported, because that gap is the diacritic error mass.
    """
    lowered = unicodedata.normalize("NFC", text).lower().replace("đ", "d")
    decomposed = unicodedata.normalize("NFD", lowered)
    return "".join(c for c in decomposed if not unicodedata.combining(c))


class Op(Enum):
    """Alignment operation, from the reference's point of view."""

    EQUAL = "equal"
    SUBSTITUTE = "substitute"
    DELETE = "delete"
    INSERT = "insert"


@dataclass(frozen=True, slots=True)
class Step:
    """One alignment step. Indices are into the token lists, not characters."""

    op: Op
    ref_index: int | None
    hyp_index: int | None


@dataclass(frozen=True, slots=True)
class Counts:
    """Edit counts for one utterance, kept per-utterance on purpose.

    The block bootstrap resamples utterances and re-sums these, so storing the
    components rather than a ratio means a confidence interval costs no
    re-alignment.
    """

    substitutions: int
    deletions: int
    insertions: int
    ref_tokens: int

    @property
    def errors(self) -> int:
        return self.substitutions + self.deletions + self.insertions

    def plus(self, other: Counts) -> Counts:
        return Counts(
            self.substitutions + other.substitutions,
            self.deletions + other.deletions,
            self.insertions + other.insertions,
            self.ref_tokens + other.ref_tokens,
        )

    @property
    def syer(self) -> float | None:
        """``(S+D+I)/N``, or None when the reference is empty.

        ``None`` rather than 0.0 or infinity: SyER on an empty reference is
        undefined, and reporting zero would read as a clean result on exactly
        the clips built to expose hallucination. Those clips are scored by
        :func:`non_speech_output_rate` instead.
        """
        if self.ref_tokens == 0:
            return None
        return self.errors / self.ref_tokens

    @property
    def insertion_rate(self) -> float | None:
        """``I/N``, broken out because insertions are the safety-relevant class.

        An insertion is MeetAI saying something nobody said. A deletion is
        MeetAI missing something. Pooling them into one figure is the move
        :mod:`meetai.evaluation` exists to forbid.
        """
        if self.ref_tokens == 0:
            return None
        return self.insertions / self.ref_tokens


EMPTY = Counts(0, 0, 0, 0)


def align(ref: list[str], hyp: list[str]) -> tuple[Counts, tuple[Step, ...]]:
    """Levenshtein alignment with a declared, deterministic tie-break.

    Ties in the recurrence are broken in the fixed order
    **substitute/equal > delete > insert**. The order is arbitrary but it is
    *declared and stable*, which is what makes per-token attribution
    reproducible. Alignment is not unique, so an undeclared tie-break makes
    per-class numbers depend on an implementation detail.
    """
    n, m = len(ref), len(hyp)
    cost = [[0] * (m + 1) for _ in range(n + 1)]
    for i in range(1, n + 1):
        cost[i][0] = i
    for j in range(1, m + 1):
        cost[0][j] = j
    for i in range(1, n + 1):
        for j in range(1, m + 1):
            same = ref[i - 1] == hyp[j - 1]
            cost[i][j] = min(
                cost[i - 1][j - 1] + (0 if same else 1),
                cost[i - 1][j] + 1,
                cost[i][j - 1] + 1,
            )

    steps: list[Step] = []
    i, j = n, m
    subs = dels = ins = 0
    while i > 0 or j > 0:
        if i > 0 and j > 0:
            same = ref[i - 1] == hyp[j - 1]
            if cost[i][j] == cost[i - 1][j - 1] + (0 if same else 1):
                steps.append(Step(Op.EQUAL if same else Op.SUBSTITUTE, i - 1, j - 1))
                if not same:
                    subs += 1
                i, j = i - 1, j - 1
                continue
        if i > 0 and cost[i][j] == cost[i - 1][j] + 1:
            steps.append(Step(Op.DELETE, i - 1, None))
            dels += 1
            i -= 1
            continue
        steps.append(Step(Op.INSERT, None, j - 1))
        ins += 1
        j -= 1
    steps.reverse()
    return Counts(subs, dels, ins, n), tuple(steps)


def score_utterance(reference: str, hypothesis: str) -> tuple[Counts, tuple[Step, ...]]:
    """Score one utterance under the headline contract."""
    return align(syllables(reference), syllables(hypothesis))


def score_failed_utterance(reference: str) -> Counts:
    """Counts for a clip that timed out, OOMed, errored, or produced nothing.

    Every reference token counts as a deletion, so the denominator is
    unchanged and the utterance scores 100%. This is the only accounting that
    cannot be gamed by dropping the clip, which is what the acceptance
    criteria require.

    Note the asymmetry this does **not** cover: an empty hypothesis against an
    **empty** reference is the correct answer, not a failure. The caller must
    not route non-speech clips here. :func:`non_speech_output_rate` scores
    those.
    """
    tokens = len(syllables(reference))
    return Counts(0, tokens, 0, tokens)


def character_counts(reference: str, hypothesis: str) -> Counts:
    """CER counts over NFC characters, spaces included.

    Spaces are counted, and that is a declared choice rather than an oversight:
    excluding them would hide syllable-boundary errors, which in Vietnamese are
    word-boundary errors.
    """
    ref = list(normalise(reference))
    hyp = list(normalise(hypothesis))
    counts, _ = align(ref, hyp)
    return counts


# ------------------------------------------------------------------ #
# Non-speech: a different question, so a different metric.
# ------------------------------------------------------------------ #


@dataclass(frozen=True, slots=True)
class NonSpeechResult:
    """Hallucination on clips whose correct output is nothing at all.

    SyER cannot express this: the reference has no tokens, so the denominator
    is zero. The reported rate is per **clip**, which is a genuine binomial
    proportion, plus severity figures because the rate saturates - a model that
    emits three tokens on silence and one that emits three hundred both score
    100%.
    """

    clips: int
    clips_with_output: int
    total_hallucinated_tokens: int
    total_audio_seconds: float
    examples_shape_only: tuple[str, ...] = ()

    @property
    def output_rate(self) -> float | None:
        """Fraction of non-speech clips that produced any token."""
        if self.clips == 0:
            return None
        return self.clips_with_output / self.clips

    @property
    def tokens_per_minute(self) -> float | None:
        """Severity, normalised by audio duration so it survives saturation."""
        if self.total_audio_seconds <= 0:
            return None
        return self.total_hallucinated_tokens / (self.total_audio_seconds / 60.0)

    def render(self) -> str:
        if self.clips == 0:
            return "n/a (0 clips)"
        rate = self.output_rate or 0.0
        per_min = self.tokens_per_minute
        severity = f"{per_min:.1f} tokens/min" if per_min is not None else "n/a"
        return (
            f"{self.clips_with_output}/{self.clips} = {rate * 100:.1f}% clips "
            f"emitted output; {severity}"
        )


def non_speech_output_rate(
    hypotheses: list[str], durations_s: list[float]
) -> NonSpeechResult:
    """Score a non-speech partition. Any output at all counts as hallucination."""
    if len(hypotheses) != len(durations_s):
        raise ValueError(
            f"so clip khong khop: {len(hypotheses)} hyp, {len(durations_s)} duration"
        )
    with_output = 0
    tokens = 0
    for hypothesis in hypotheses:
        found = syllables(hypothesis)
        if found:
            with_output += 1
            tokens += len(found)
    return NonSpeechResult(
        clips=len(hypotheses),
        clips_with_output=with_output,
        total_hallucinated_tokens=tokens,
        total_audio_seconds=sum(durations_s),
    )


# ------------------------------------------------------------------ #
# Uncertainty: bootstrap over utterances, not a binomial over tokens.
# ------------------------------------------------------------------ #


def bootstrap_syer(
    per_utterance: list[Counts],
    *,
    blocks: list[str] | None = None,
    replicates: int = 2000,
    seed: int = 7,
) -> tuple[float, float] | None:
    """Percentile confidence interval for pooled SyER.

    A Wilson interval is wrong here for two independent reasons, so it is not
    offered: SyER is not a proportion (insertions are in the numerator but not
    the denominator, so it can exceed 1), and word errors cluster inside an
    utterance, so treating N tokens as N independent trials understates the
    variance in the flattering direction.

    Resampling is over whole utterances. ``blocks`` resamples groups of
    utterances instead - one block per recording or meeting - because
    utterances from one recording are not independent and ignoring that makes
    the interval too narrow.
    """
    if not per_utterance:
        return None
    # Statistical resampling, not a security primitive; seeded so a reported
    # interval is reproducible from the record.
    rng = random.Random(seed)  # noqa: S311

    if blocks is not None:
        if len(blocks) != len(per_utterance):
            raise ValueError(
                f"so block khong khop: {len(blocks)} block, "
                f"{len(per_utterance)} utterance"
            )
        grouped: dict[str, list[Counts]] = {}
        for name, counts in zip(blocks, per_utterance, strict=True):
            grouped.setdefault(name, []).append(counts)
        units = list(grouped.values())
    else:
        units = [[counts] for counts in per_utterance]

    estimates: list[float] = []
    for _ in range(replicates):
        total = EMPTY
        for _ in range(len(units)):
            # Statistical resampling, not a security primitive; seeded so a
            # reported interval is reproducible.
            for counts in rng.choice(units):
                total = total.plus(counts)
        value = total.syer
        if value is not None:
            estimates.append(value)
    if not estimates:
        return None
    estimates.sort()
    low = estimates[int(0.025 * (len(estimates) - 1))]
    high = estimates[int(0.975 * (len(estimates) - 1))]
    return low, high


@dataclass
class GroupResult:
    """Pooled counts for one reported group, with its own denominators.

    Counts before rates, and a rate never without its denominator - the
    convention :mod:`meetai.evaluation` sets and the reason it has no accuracy.
    """

    name: str
    utterances: int = 0
    counts: Counts = EMPTY
    char_counts: Counts = EMPTY
    folded_counts: Counts = EMPTY
    failures: dict[str, int] = field(default_factory=dict)
    per_utterance: list[Counts] = field(default_factory=list)

    def add(
        self,
        counts: Counts,
        *,
        char: Counts = EMPTY,
        folded: Counts = EMPTY,
    ) -> None:
        self.utterances += 1
        self.counts = self.counts.plus(counts)
        self.char_counts = self.char_counts.plus(char)
        self.folded_counts = self.folded_counts.plus(folded)
        self.per_utterance.append(counts)

    def note_failure(self, kind: str) -> None:
        self.failures[kind] = self.failures.get(kind, 0) + 1

    def render(self) -> str:
        """ASCII only. Vietnamese text never reaches a terminal from here."""
        c = self.counts
        if c.ref_tokens == 0:
            return f"{self.name}: n={self.utterances} ref_tokens=0 SyER=n/a"
        syer = c.syer or 0.0
        cer = self.char_counts.syer
        folded = self.folded_counts.syer
        gap = (
            f" folded={folded * 100:.1f}% gap={(syer - folded) * 100:+.1f}pp"
            if folded is not None
            else ""
        )
        return (
            f"{self.name}: n={self.utterances} N={c.ref_tokens} "
            f"S={c.substitutions} D={c.deletions} I={c.insertions} "
            f"SyER={syer * 100:.1f}% IER={(c.insertion_rate or 0) * 100:.1f}%"
            + (f" CER={cer * 100:.1f}%" if cer is not None else "")
            + gap
        )


# ------------------------------------------------------------------ #
# Per-class error analysis: proper nouns, numbers, dates.
# ------------------------------------------------------------------ #


class TokenClass(Enum):
    """Reference-token classes reported separately.

    Precedence is ``DATE > NUMBER > PROPER_NOUN`` and classes are mutually
    exclusive at token level, because a date span contains numbers and without
    a declared precedence one error would be counted in two classes and the
    class rates would relate to nothing.
    """

    DATE = "date"
    NUMBER = "number"
    PROPER_NOUN = "proper_noun"


_DIGITS = frozenset("0123456789")

_NUMBER_WORDS = frozenset(
    [
        "khong",
        "mot",
        "hai",
        "ba",
        "bon",
        "nam",
        "sau",
        "bay",
        "tam",
        "chin",
        "muoi",
        "tram",
        "nghin",
        "ngan",
        "trieu",
        "ty",
        "linh",
        "le",
        "mot",
        "mot",
        "muoi",
        "lam",
    ]
)

_DATE_CUES = frozenset(["ngay", "thang", "nam", "thu", "quy", "tuan"])


def classify_reference_tokens(tokens: list[str]) -> dict[int, TokenClass]:
    """Tag reference tokens by class. **Reference only, never the hypothesis.**

    That direction is not a style preference. If classes were tagged by
    matching the hypothesis, a model that *deletes* a hard name would reduce
    the number of names it is scored on - the denominator would become
    model-dependent and the metric would reward deletion.

    The proper-noun rule is a **capitalisation heuristic, not annotation**, and
    the limit has to be stated wherever its numbers appear: Vietnamese given
    names are ordinary common nouns (``Thu`` autumn, ``Hoa`` flower, ``Minh``
    bright, ``Lan`` orchid), so capitalisation is the only text-level signal
    and a sentence-initial name is indistinguishable from a sentence-initial
    word. Tokens at index 0 are therefore not tagged, which loses real names
    and keeps the denominator honest rather than inflated.
    """
    tagged: dict[int, TokenClass] = {}
    folded = [fold_diacritics(token) for token in tokens]

    for index, token in enumerate(tokens):
        bare = folded[index]
        previous = folded[index - 1] if index > 0 else ""

        is_numeric = any(ch in _DIGITS for ch in token) or bare in _NUMBER_WORDS

        # A date is a cue word plus something countable next to it, so a bare
        # "nam" (year, or five, or the adjective) does not become a date.
        if previous in _DATE_CUES and is_numeric:
            tagged[index - 1] = TokenClass.DATE
            tagged[index] = TokenClass.DATE
            continue
        if bare in _DATE_CUES and index + 1 < len(tokens):
            nxt = folded[index + 1]
            if any(ch in _DIGITS for ch in tokens[index + 1]) or nxt in _NUMBER_WORDS:
                tagged[index] = TokenClass.DATE
                tagged[index + 1] = TokenClass.DATE
                continue
        if is_numeric:
            tagged.setdefault(index, TokenClass.NUMBER)
            continue
        if index > 0 and token[:1].isupper():
            tagged.setdefault(index, TokenClass.PROPER_NOUN)

    return tagged


@dataclass
class ClassResult:
    """Per-class counts, each with its own denominator.

    Both numbers are kept because they answer different questions. Token error
    rate is comparable to the headline SyER. Span-level correctness is the
    operational one: for a meeting assistant a name is either right or wrong,
    and a one-tone miss on a name is a wrong name.
    """

    token_class: TokenClass
    ref_tokens: int = 0
    substitutions: int = 0
    deletions: int = 0
    insertions_interior: int = 0
    boundary_ambiguous_insertions: int = 0

    @property
    def errors(self) -> int:
        return self.substitutions + self.deletions + self.insertions_interior

    @property
    def token_error_rate(self) -> float | None:
        if self.ref_tokens == 0:
            return None
        return self.errors / self.ref_tokens

    def render(self) -> str:
        if self.ref_tokens == 0:
            return f"{self.token_class.value}: n=0 rate=n/a"
        rate = self.token_error_rate or 0.0
        return (
            f"{self.token_class.value}: N={self.ref_tokens} "
            f"S={self.substitutions} D={self.deletions} "
            f"I={self.insertions_interior} rate={rate * 100:.1f}% "
            f"(boundary_ambiguous_I={self.boundary_ambiguous_insertions})"
        )


def score_classes(reference: str, hypothesis: str) -> dict[TokenClass, ClassResult]:
    """Attribute alignment operations to reference-token classes.

    Insertions are attributed **interior-only**: an insertion sits *between*
    reference positions, so at a span edge it is undecidable which side it
    belongs to. Counting edge insertions into the class would inflate the rate;
    dropping them silently would make hallucinated extra name syllables vanish.
    They are counted separately instead, so the convention's effect is visible.
    """
    ref_tokens = syllables(reference)
    hyp_tokens = syllables(hypothesis)
    tags = classify_reference_tokens(ref_tokens)
    _, steps = align(ref_tokens, hyp_tokens)

    results = {cls: ClassResult(token_class=cls) for cls in TokenClass}
    for cls in tags.values():
        results[cls].ref_tokens += 1

    for position, step in enumerate(steps):
        if step.ref_index is not None:
            cls = tags.get(step.ref_index)
            if cls is None:
                continue
            if step.op is Op.SUBSTITUTE:
                results[cls].substitutions += 1
            elif step.op is Op.DELETE:
                results[cls].deletions += 1
            continue

        # An insertion. Interior only if the nearest tagged reference tokens on
        # both sides share the same class.
        before = next(
            (
                steps[i].ref_index
                for i in range(position - 1, -1, -1)
                if steps[i].ref_index is not None
            ),
            None,
        )
        after = next(
            (
                steps[i].ref_index
                for i in range(position + 1, len(steps))
                if steps[i].ref_index is not None
            ),
            None,
        )
        left = tags.get(before) if before is not None else None
        right = tags.get(after) if after is not None else None
        if left is not None and left is right:
            results[left].insertions_interior += 1
        elif left is not None or right is not None:
            edge = left or right
            if edge is not None:
                results[edge].boundary_ambiguous_insertions += 1

    return results
