"""The unavailable measurement is a type, not a string that looks like a number.

Measured at ``b182d5a``, before this file existed: ``Environment.capture()``
substituted ``["?"] * 10`` when ``nvidia-smi`` produced nothing, and all five
call sites then wrote ``int(env.vram_idle_mib or 0)``. That expression reads
like it handles the unavailable case. It cannot:

    >>> bool("?")
    True

so ``or 0`` never fires and ``int("?")`` raises ``ValueError``. Reproduced
before the fix. It is the same shape as ``if settings.consent_mode:`` looking
like a guard while failing open, which ``AGENTS.md`` already names - a sentinel
that type-checks as the thing it stands in for will be used as that thing.

The consequence was specific: ``measure._resolve``'s own docstring says
returning ``None`` "keeps every caller's measurement-unavailable path, which is
how **a CPU-only machine still produces a usable record**". A CPU-only host is
a stated supported case, and on one the harness crashed instead.

What this file pins, per path: the sentinel is named and reaches the record;
the usable value is ``int | None``; ``None`` is not silently turned into zero,
because a zero baseline makes every attributable figure equal the raw peak;
and each of the five derived figures is withheld rather than fabricated.

Nothing here loads a model, spawns a binary, touches a GPU, opens a socket or
writes a file. ``Environment`` instances are constructed directly.
"""

from __future__ import annotations

import ast
import dataclasses
import pathlib

import pytest
from benchmarks.measure import UNAVAILABLE, Environment

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
BENCHMARKS = REPO_ROOT / "benchmarks"


def unavailable_environment() -> Environment:
    """What ``capture()`` builds when the probe answered nothing."""
    return Environment(
        gpu_name=UNAVAILABLE,
        compute_cap=UNAVAILABLE,
        driver=UNAVAILABLE,
        vram_total_mib=UNAVAILABLE,
        vram_idle_mib=UNAVAILABLE,
        gpu_temp_idle_c=UNAVAILABLE,
        enforced_power_limit_w=UNAVAILABLE,
        max_power_limit_w=UNAVAILABLE,
        mem_clock_max_mhz=UNAVAILABLE,
        sm_clock_max_mhz=UNAVAILABLE,
        captured_at="2026-10-10 00:00:00",
        gpu_probe_ok=False,
    )


def available_environment(idle: str = "853") -> Environment:
    return dataclasses.replace(
        unavailable_environment(),
        vram_idle_mib=idle,
        vram_total_mib="6144",
        gpu_probe_ok=True,
    )


class TestTheSentinelIsNamedAndTyped:
    def test_the_probe_failure_is_recorded_as_a_boolean(self) -> None:
        assert unavailable_environment().gpu_probe_ok is False
        assert available_environment().gpu_probe_ok is True

    def test_the_usable_value_is_none_not_a_string(self) -> None:
        assert unavailable_environment().vram_idle_mib_value is None

    def test_the_usable_value_is_an_int_when_the_probe_answered(self) -> None:
        assert available_environment("853").vram_idle_mib_value == 853

    def test_an_unparseable_answer_is_also_none(self) -> None:
        """A probe that answered with something non-numeric is still unusable."""
        weird = dataclasses.replace(available_environment(), vram_idle_mib="[N/A]")
        assert weird.vram_idle_mib_value is None

    def test_none_is_not_zero(self) -> None:
        """The distinction the old ``or 0`` destroyed.

        Zero is a measurement: it says the GPU was idle at 0 MiB. ``None`` says
        nobody looked. Conflating them makes an attributable figure equal the
        raw peak, which is the error this module's docstring is built around.
        """
        zeroed = dataclasses.replace(available_environment(), vram_idle_mib="0")
        assert zeroed.vram_idle_mib_value == 0
        assert unavailable_environment().vram_idle_mib_value is None
        assert zeroed.vram_idle_mib_value != unavailable_environment().vram_idle_mib_value

    def test_the_old_sentinel_is_gone_from_capture(self) -> None:
        """Not a style point: the bare "?" is what type-checked as a number."""
        source = (BENCHMARKS / "measure.py").read_text(encoding="utf-8")
        tree = ast.parse(source)
        capture = next(
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.FunctionDef) and node.name == "capture"
        )
        constants = {
            node.value
            for node in ast.walk(capture)
            if isinstance(node, ast.Constant) and isinstance(node.value, str)
        }
        assert "?" not in constants, constants

    def test_the_sentinel_still_serialises(self) -> None:
        """The record is compared by hand across runs, so it stays a string."""
        record = dataclasses.asdict(unavailable_environment())
        assert record["vram_idle_mib"] == UNAVAILABLE
        assert record["gpu_probe_ok"] is False
        # A property is not a field, so the typed accessor does not change the
        # artifact schema.
        assert "vram_idle_mib_value" not in record


class TestTheReproductionOfTheOldDefect:
    """Kept as a test, because the mechanism is subtle and will recur."""

    def test_the_old_guard_could_not_have_worked(self) -> None:
        # Held in a variable, not written as a literal: `"?" or 0` folds to
        # `"?"` and a linter rightly says so - the redundancy IS the defect.
        sentinel = "?"
        assert bool(sentinel) is True, "a truthy sentinel means `or 0` never fires"
        with pytest.raises(ValueError, match="invalid literal"):
            int(sentinel or 0)

    def test_the_new_sentinel_is_truthy_too_which_is_why_the_type_changed(self) -> None:
        """Renaming the sentinel would not have fixed anything.

        ``"unavailable"`` is just as truthy as ``"?"``. The fix is the
        ``int | None`` accessor, not the spelling - so this test exists to stop
        a future reader concluding the rename was the repair.
        """
        assert bool(UNAVAILABLE) is True
        with pytest.raises(ValueError, match="invalid literal"):
            int(UNAVAILABLE or 0)


class TestEveryDerivedFigureIsWithheldNotFabricated:
    """One assertion per call site that consumed the old expression.

    Five sites existed. Each computed a VRAM rise or an attributable figure
    from the baseline, so each had to learn to produce ``None``.
    """

    CALL_SITES = (
        ("bench_llamacpp.py", "_locked_main"),
        ("bench_llm.py", "main"),
        ("bench_coresidency.py", "run_single"),
        ("bench_coresidency.py", "_locked_main"),
    )

    def test_no_benchmark_still_coerces_the_baseline_with_or_zero(self) -> None:
        """``measure.py`` is excluded because its docstring quotes the old
        expression on purpose, as the record of what was measured. The
        exclusion cannot hide a live one: the companion assertion is that no
        ``BoolOp`` over that attribute survives anywhere, which is the call
        rather than the prose.
        """
        offenders = [
            path.name
            for path in sorted(BENCHMARKS.glob("*.py"))
            if path.name != "measure.py"
            and "vram_idle_mib or 0" in path.read_text(encoding="utf-8")
        ]
        assert not offenders, offenders

        live: list[str] = []
        for path in sorted(BENCHMARKS.glob("*.py")):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            live += [
                f"{path.name}:{node.lineno}"
                for node in ast.walk(tree)
                if isinstance(node, ast.BoolOp) and "vram_idle_mib" in ast.unparse(node)
            ]
        assert not live, live

    def test_every_rise_computation_guards_the_baseline(self) -> None:
        """A rise is ``peak - idle``; both operands have to be present.

        Found by AST rather than by reading: every subtraction whose right
        operand is the baseline name must sit under a ``None`` check for it.
        """
        unguarded: list[str] = []
        for path in sorted(BENCHMARKS.glob("*.py")):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if not isinstance(node, ast.BinOp) or not isinstance(node.op, ast.Sub):
                    continue
                right = node.right
                if not isinstance(right, ast.Name) or right.id not in {
                    "idle",
                    "idle_mib",
                }:
                    continue
                # The enclosing IfExp or If must mention the same name.
                guarded = any(
                    isinstance(parent, ast.IfExp | ast.If)
                    and right.id in ast.unparse(parent.test)
                    for parent in ast.walk(tree)
                    if isinstance(parent, ast.IfExp | ast.If)
                    and any(node is child for child in ast.walk(parent))
                )
                if not guarded:
                    unguarded.append(f"{path.name}:{node.lineno}")
        assert not unguarded, unguarded

    def test_the_scan_actually_found_the_subtractions(self) -> None:
        """A scan that matched nothing would pass the test above for free."""
        total = 0
        for path in sorted(BENCHMARKS.glob("*.py")):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            total += sum(
                1
                for node in ast.walk(tree)
                if isinstance(node, ast.BinOp)
                and isinstance(node.op, ast.Sub)
                and isinstance(node.right, ast.Name)
                and node.right.id in {"idle", "idle_mib"}
            )
        assert total >= 4, f"only found {total} baseline subtractions"

    @pytest.mark.parametrize(("module", "function"), CALL_SITES)
    def test_the_call_site_still_exists(self, module: str, function: str) -> None:
        """So the test above cannot pass because a site was deleted."""
        tree = ast.parse((BENCHMARKS / module).read_text(encoding="utf-8"))
        names = {
            node.name for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)
        }
        assert function in names, sorted(names)
