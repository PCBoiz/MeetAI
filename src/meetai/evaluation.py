"""Metrics for evaluating the authority gate (slice S1.8).

Pure functions over counted outcomes. They live in ``src`` rather than in the
test file so they are typed, reusable and themselves testable, while the corpus
and the scoring run stay in ``tests`` - the corpus must not be importable by
the code it judges.

Two rules shape the whole module:

**False-allow and false-block are never combined into one number.** A
false-allow is MeetAI making a commitment in the operator's name; a false-block
is MeetAI staying quiet when it could have spoken. Those costs are not
comparable, so there is no accuracy and no F1 here. Any single figure would
average a safety failure against an inconvenience and report the mean as
quality.

**Every rate is reported with its denominator.** On a corpus of a few dozen per
group, a percentage on its own is the "tốt/ổn" the project forbids. A rate of
0/14 and a rate of 0/900 are different claims.
"""

from __future__ import annotations

import math
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class Rate:
    """A count over a denominator, with the interval that bounds it.

    The interval is a Wilson score interval, which is used rather than the
    textbook normal approximation because the interesting rates here are near
    zero and the normal approximation is worst exactly there - it happily
    reports a negative lower bound.
    """

    numerator: int
    denominator: int

    def __post_init__(self) -> None:
        if self.numerator < 0 or self.denominator < 0:
            raise ValueError("Rate khong nhan gia tri am")
        if self.numerator > self.denominator:
            raise ValueError("numerator khong duoc lon hon denominator")

    @property
    def value(self) -> float | None:
        """The rate, or ``None`` when nothing was measured.

        ``None`` rather than ``0.0``: an empty group has no rate, and
        reporting zero would read as a clean result.
        """
        if self.denominator == 0:
            return None
        return self.numerator / self.denominator

    def wilson_interval(self, z: float = 1.96) -> tuple[float, float] | None:
        """95% Wilson score interval, or ``None`` for an empty denominator."""
        n = self.denominator
        if n == 0:
            return None
        p = self.numerator / n
        denom = 1 + z**2 / n
        centre = (p + z**2 / (2 * n)) / denom
        margin = (z / denom) * math.sqrt(p * (1 - p) / n + z**2 / (4 * n**2))
        return (max(0.0, centre - margin), min(1.0, centre + margin))

    def render(self) -> str:
        """Count, rate and interval in one string. Never a bare percentage."""
        if self.denominator == 0:
            return "n/a (n=0)"
        interval = self.wilson_interval()
        if interval is None:  # unreachable: denominator > 0 above
            return "n/a (n=0)"
        low, high = interval
        pct = 100 * self.numerator / self.denominator
        return (
            f"{self.numerator}/{self.denominator} = {pct:.1f}% "
            f"[95% CI {100 * low:.1f}-{100 * high:.1f}%]"
        )


@dataclass(frozen=True, slots=True)
class BinaryConfusion:
    """A 2x2 table for one group's verdicts.

    Named from the policy's point of view, not the classifier's, so that
    reading the field names tells you what went wrong rather than requiring a
    convention to be remembered.
    """

    true_allow: int = 0
    false_block: int = 0
    false_allow: int = 0
    true_refuse: int = 0

    @property
    def total(self) -> int:
        return self.true_allow + self.false_block + self.false_allow + self.true_refuse

    @property
    def false_allow_rate(self) -> Rate:
        """Share of cases policy says refuse that the gate allowed.

        The only metric here that corresponds to a safety failure.
        """
        return Rate(self.false_allow, self.false_allow + self.true_refuse)

    @property
    def false_block_rate(self) -> Rate:
        """Share of cases policy says allow that the gate refused."""
        return Rate(self.false_block, self.false_block + self.true_allow)

    @property
    def refusal_rate(self) -> Rate:
        """Share of the group the gate refused, whatever the label.

        This is what "abstain rate" means for a gate that returns a verdict
        rather than choosing to stay silent: the gate has no abstain action of
        its own, so the honest measurement is how often it refuses.
        """
        return Rate(self.false_block + self.true_refuse, self.total)

    def plus(self, other: BinaryConfusion) -> BinaryConfusion:
        return BinaryConfusion(
            true_allow=self.true_allow + other.true_allow,
            false_block=self.false_block + other.false_block,
            false_allow=self.false_allow + other.false_allow,
            true_refuse=self.true_refuse + other.true_refuse,
        )

    @classmethod
    def from_outcome(cls, *, policy_allows: bool, gate_allowed: bool) -> BinaryConfusion:
        if policy_allows and gate_allowed:
            return cls(true_allow=1)
        if policy_allows and not gate_allowed:
            return cls(false_block=1)
        if not policy_allows and gate_allowed:
            return cls(false_allow=1)
        return cls(true_refuse=1)


@dataclass(frozen=True, slots=True)
class LabelConfusion:
    """A 2x2 table for one prohibited act, over a multi-label problem.

    Multi-label rather than a single 7-way table: one phrase can perform two
    acts, and several patterns deliberately overlap. A 7x7 matrix would be
    undefined for those rows and would hide the overlap for the rest.
    """

    true_positive: int = 0
    false_negative: int = 0
    false_positive: int = 0
    true_negative: int = 0

    @property
    def precision(self) -> Rate:
        return Rate(self.true_positive, self.true_positive + self.false_positive)

    @property
    def recall(self) -> Rate:
        return Rate(self.true_positive, self.true_positive + self.false_negative)

    def plus(self, other: LabelConfusion) -> LabelConfusion:
        return LabelConfusion(
            true_positive=self.true_positive + other.true_positive,
            false_negative=self.false_negative + other.false_negative,
            false_positive=self.false_positive + other.false_positive,
            true_negative=self.true_negative + other.true_negative,
        )

    @classmethod
    def from_outcome(cls, *, expected: bool, detected: bool) -> LabelConfusion:
        if expected and detected:
            return cls(true_positive=1)
        if expected and not detected:
            return cls(false_negative=1)
        if not expected and detected:
            return cls(false_positive=1)
        return cls(true_negative=1)


@dataclass
class EvaluationReport:
    """Verdict and detection outcomes, grouped, plus the per-rule ledger."""

    by_group: dict[str, BinaryConfusion] = field(default_factory=dict)
    by_act: dict[str, LabelConfusion] = field(default_factory=dict)
    rule_firings: dict[str, int] = field(default_factory=dict)
    rule_firings_on_allow: dict[str, int] = field(default_factory=dict)
    false_allow_cases: list[str] = field(default_factory=list)
    false_block_cases: list[str] = field(default_factory=list)

    def record_verdict(
        self,
        *,
        group: str,
        case_id: str,
        policy_allows: bool,
        gate_allowed: bool,
        rules: Iterable[str] = (),
    ) -> None:
        outcome = BinaryConfusion.from_outcome(
            policy_allows=policy_allows, gate_allowed=gate_allowed
        )
        self.by_group[group] = self.by_group.get(group, BinaryConfusion()).plus(outcome)
        if outcome.false_allow:
            self.false_allow_cases.append(case_id)
        if outcome.false_block:
            self.false_block_cases.append(case_id)

        for rule in rules:
            self.rule_firings[rule] = self.rule_firings.get(rule, 0) + 1
            if policy_allows:
                # A rule that fires mostly on cases policy permits is the
                # over-broad pattern, named. This is the diagnostic that makes
                # a stable rule id worth having.
                self.rule_firings_on_allow[rule] = (
                    self.rule_firings_on_allow.get(rule, 0) + 1
                )

    def record_detection(self, *, act: str, expected: bool, detected: bool) -> None:
        outcome = LabelConfusion.from_outcome(expected=expected, detected=detected)
        self.by_act[act] = self.by_act.get(act, LabelConfusion()).plus(outcome)

    @property
    def pooled(self) -> BinaryConfusion:
        total = BinaryConfusion()
        for confusion in self.by_group.values():
            total = total.plus(confusion)
        return total

    @property
    def total_false_allows(self) -> int:
        """Any value above zero is a finding, whatever the sample size."""
        return len(self.false_allow_cases)

    def over_broad_rules(self, *, minimum_firings: int = 1) -> tuple[str, ...]:
        """Rules whose firings are mostly on cases policy permits.

        The ordering of the comparison matters: ``>`` half, so a rule that
        splits evenly is not accused.
        """
        suspects = [
            rule
            for rule, count in sorted(self.rule_firings.items())
            if count >= minimum_firings
            and self.rule_firings_on_allow.get(rule, 0) * 2 > count
        ]
        return tuple(suspects)


def render_report(
    report: EvaluationReport,
    *,
    corpus_version: str,
    group_names: Mapping[str, str] | None = None,
    threshold_sweep: Sequence[tuple[float, BinaryConfusion]] = (),
) -> str:
    """Render the report as Markdown.

    Written for a human reviewing a change, so counts come before rates and
    every failing case is listed by id. There is no overall score line, by
    design.
    """
    names = dict(group_names or {})
    lines = [
        f"# Authority gate evaluation - corpus {corpus_version}",
        "",
        "Counts first, then rates with their denominators. There is no single",
        "accuracy figure: a false-allow is an unauthorised commitment and a",
        "false-block is unnecessary silence, and averaging them would report a",
        "safety failure as a quality score.",
        "",
        "## Verdicts by risk group",
        "",
        "| group | n | true allow | false block | false allow | true refuse |"
        " false-allow rate | false-block rate | refusal rate |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for group in sorted(report.by_group):
        c = report.by_group[group]
        label = names.get(group, group)
        lines.append(
            f"| {label} | {c.total} | {c.true_allow} | {c.false_block} | "
            f"{c.false_allow} | {c.true_refuse} | {c.false_allow_rate.render()} | "
            f"{c.false_block_rate.render()} | {c.refusal_rate.render()} |"
        )
    pooled = report.pooled
    lines += [
        f"| **pooled** | {pooled.total} | {pooled.true_allow} | "
        f"{pooled.false_block} | {pooled.false_allow} | {pooled.true_refuse} | "
        f"{pooled.false_allow_rate.render()} | {pooled.false_block_rate.render()} | "
        f"{pooled.refusal_rate.render()} |",
        "",
        "## Detection by prohibited act (multi-label)",
        "",
        "| act | TP | FN | FP | TN | precision | recall |",
        "|---|---|---|---|---|---|---|",
    ]
    for act in sorted(report.by_act):
        a = report.by_act[act]
        lines.append(
            f"| {act} | {a.true_positive} | {a.false_negative} | "
            f"{a.false_positive} | {a.true_negative} | {a.precision.render()} | "
            f"{a.recall.render()} |"
        )

    lines += [
        "",
        "## Rule firings",
        "",
        "| rule | fired | of which on allow-cases |",
        "|---|---|---|",
    ]
    for rule in sorted(report.rule_firings):
        lines.append(
            f"| {rule} | {report.rule_firings[rule]} | "
            f"{report.rule_firings_on_allow.get(rule, 0)} |"
        )

    suspects = report.over_broad_rules(minimum_firings=2)
    lines += [
        "",
        "Rules firing mostly on cases policy permits (over-broad suspects): "
        + (", ".join(suspects) if suspects else "none"),
        "",
        "## Failing cases",
        "",
        f"False allows ({len(report.false_allow_cases)}): "
        + (", ".join(report.false_allow_cases) or "none"),
        "",
        f"False blocks ({len(report.false_block_cases)}): "
        + (", ".join(report.false_block_cases) or "none"),
    ]

    if threshold_sweep:
        lines += [
            "",
            "## Confidence threshold sensitivity",
            "",
            "Sensitivity only. Every confidence value in the corpus was chosen",
            "by its author, so this measures how much of the gate's behaviour",
            "the threshold controls - not whether any threshold is correct.",
            "",
            "| minimum_confidence | false allow | false block |",
            "|---|---|---|",
        ]
        for threshold, confusion in threshold_sweep:
            lines.append(
                f"| {threshold:.2f} | {confusion.false_allow_rate.render()} | "
                f"{confusion.false_block_rate.render()} |"
            )

    return "\n".join(lines) + "\n"
