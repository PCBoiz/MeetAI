"""Exception messages describe shape, never value.

``errors.py`` claims this rule is enforced by test and cited this file by name
before it existed. It exists now, and it enforces the rule repo-wide rather
than one exception at a time.

The rule matters because of where an exception message ends up. Once a value is
interpolated into a string, every later protection is bypassed: ``SecretStr``
masking, ``MeetingContent``'s shape-only repr, and the logging filter all
operate on objects, and ``str(exc)`` is just a string by then.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parent.parent / "src" / "meetai"

CANARY = "CANARY-GIA-TRI-KHONG-DUOC-XUAT-HIEN-TRONG-EXCEPTION"


class TestNoValueInterpolation:
    """No ``raise`` may interpolate a value the caller supplied.

    Checked by reading the AST rather than by exercising every path: there are
    far more raise sites than tests, and a static rule covers the ones nobody
    thought to exercise.

    A formatted message is permitted when every interpolation is a *name of a
    thing* rather than a value - a field name, an enum's ``.value``, a type
    name, a count. The allowlist below is explicit so widening it is a visible
    decision.
    """

    ALLOWED_TERMINALS = frozenset(
        {
            # Opaque identifiers.
            "key",
            "card_id",
            "case_id",
            "session_id",
            "event_id",
            "evidence_id",
            "participant",
            # Labels for a thing, not the thing.
            "name",
            "value",  # an enum member's .value
            "rule",
            "reason",
            "action",
            "scope",
            "state",
            "platform",
            # Counters.
            "generation",
            "_generation",
        }
    )
    """Terminal expressions a raise message may interpolate.

    Explicit, so widening it is a visible decision rather than a habit. A
    ``len(...)`` call is also permitted: a count describes shape by definition.

    ``platform`` is here deliberately. An adapter's platform name is a label
    its author chose, not a value a caller supplied, and naming it is what
    makes the misrepresentation error actionable.
    """

    @staticmethod
    def _raise_sites(tree: ast.AST) -> list[ast.Raise]:
        return [node for node in ast.walk(tree) if isinstance(node, ast.Raise)]

    @classmethod
    def _terminal(cls, expr: ast.expr) -> str:
        """What a substitution resolves to, ignoring how it got there.

        ``{self._state.value}`` resolves to ``value``; walking every node
        instead would also collect ``self`` and ``_state``, which is what made
        the first version of this test flag every correct call site.
        """
        if isinstance(expr, ast.Attribute):
            return expr.attr
        if isinstance(expr, ast.Name):
            return expr.id
        if isinstance(expr, ast.Call):
            func = expr.func
            if isinstance(func, ast.Name) and func.id == "len":
                return "len"
            return cls._terminal(func)
        return type(expr).__name__

    @pytest.mark.parametrize("path", sorted(SRC.rglob("*.py")), ids=lambda p: p.name)
    def test_raise_messages_interpolate_only_identifiers(self, path: Path) -> None:
        source = path.read_text(encoding="utf-8")
        offenders: list[str] = []
        for node in self._raise_sites(ast.parse(source)):
            for sub in ast.walk(node):
                if not isinstance(sub, ast.FormattedValue):
                    continue
                terminal = self._terminal(sub.value)
                if terminal == "len" or terminal in self.ALLOWED_TERMINALS:
                    continue
                segment = ast.get_source_segment(source, sub.value) or terminal
                offenders.append(f"{path.name}:{sub.lineno} {{{segment}}}")
        assert not offenders, (
            "exception message noi gia tri thay vi hinh dang: " + ", ".join(offenders)
        )

    @pytest.mark.parametrize("path", sorted(SRC.rglob("*.py")), ids=lambda p: p.name)
    def test_repr_conversion_only_on_allowlisted_terminals(self, path: Path) -> None:
        """``{value!r}`` is the exact shape of the bug this rule prevents.

        The settings module had one - ``got {value!r}`` in the loopback check -
        and a credential pasted into the wrong variable was echoed by it. The
        conversion itself is not the problem; applying it to an arbitrary value
        is, so the same allowlist governs it.
        """
        source = path.read_text(encoding="utf-8")
        offenders: list[str] = []
        for node in self._raise_sites(ast.parse(source)):
            for sub in ast.walk(node):
                if not isinstance(sub, ast.FormattedValue):
                    continue
                if sub.conversion != ord("r"):
                    continue
                if self._terminal(sub.value) in self.ALLOWED_TERMINALS:
                    continue
                segment = ast.get_source_segment(source, sub.value) or "?"
                offenders.append(f"{path.name}:{sub.lineno} {{{segment}!r}}")
        assert not offenders, (
            "dung !r tren gia tri khong nam trong allowlist: " + ", ".join(offenders)
        )


class TestLiveExceptionMessages:
    """Static analysis cannot see a message built elsewhere, so spot-check."""

    def test_settings_validation_error_carries_no_value(self) -> None:
        from pydantic import ValidationError

        from meetai.settings import load_settings, sanitised_validation_errors

        with pytest.raises(ValidationError) as exc_info:
            load_settings(env={"MEETAI_UI_HOST": CANARY}, env_file=None)
        rendered = " | ".join(sanitised_validation_errors(exc_info.value))
        assert CANARY not in rendered
        assert CANARY not in str(exc_info.value)

    def test_unknown_name_error_carries_no_value(self) -> None:
        from meetai.errors import UnknownSettingError
        from meetai.settings import load_settings

        with pytest.raises(UnknownSettingError) as exc_info:
            load_settings(env={"MEETAI_NOT_A_FIELD": CANARY}, env_file=None)
        assert CANARY not in str(exc_info.value)
        assert "MEETAI_NOT_A_FIELD" in str(exc_info.value)

    def test_knowledge_purge_failure_carries_no_claim(self) -> None:
        from meetai.content import MeetingContent
        from meetai.knowledge import (
            CardType,
            KnowledgeCard,
            KnowledgeError,
            KnowledgeStore,
            SourceAllowlist,
        )

        class BrokenIndex:
            def purge(self, card_id: str) -> int:
                raise RuntimeError("index down")

        store = KnowledgeStore(
            now=lambda: 0.0,
            source_allowlist=SourceAllowlist(frozenset({"notes://"})),
        )
        store.register_index(BrokenIndex())
        store.ingest(
            KnowledgeCard(
                card_id="c1",
                card_type=CardType.POSITION,
                claim=MeetingContent(CANARY),
                rationale=MeetingContent(CANARY),
                source_ref="notes://x",
                source_date=0.0,
            )
        )
        with pytest.raises(KnowledgeError) as exc_info:
            store.delete("c1")
        assert CANARY not in str(exc_info.value)

    def test_planner_error_carries_no_calendar_content(self) -> None:
        from datetime import datetime, timedelta, timezone

        from meetai.planner import CalendarEvent, PlannerError

        tz = timezone(timedelta(hours=7))
        with pytest.raises(PlannerError) as exc_info:
            CalendarEvent(
                event_id="e",
                start=datetime(2026, 1, 1, tzinfo=tz),
                end=datetime(2025, 1, 1, tzinfo=tz),
                description=CANARY,
            )
        assert CANARY not in str(exc_info.value)

    def test_adapter_misrepresentation_names_the_platform_only(self) -> None:
        """The one place a raise message does echo an input.

        A platform name is a label the adapter author chose, not a value a
        caller supplied, and naming it is what makes the error actionable.
        Pinned by a test so the exemption stays deliberate.
        """
        from meetai.adapters.base import (
            AdapterCapabilities,
            AdapterMisrepresentationError,
            PlatformAdapter,
        )

        class Probe(PlatformAdapter):
            pass

        with pytest.raises(AdapterMisrepresentationError) as exc_info:
            Probe(AdapterCapabilities(platform="discord", version="1", synthetic=True))
        assert "discord" in str(exc_info.value)


class TestErrorsModuleIsHonest:
    def test_the_cited_test_file_exists(self) -> None:
        """errors.py names this file. It must be this file."""
        source = (SRC / "errors.py").read_text(encoding="utf-8")
        cited = re.findall(r"tests/\S+\.py", source)
        assert cited, "errors.py khong con trich dan test nao"
        for name in cited:
            assert (Path(__file__).resolve().parent.parent / name).is_file(), (
                f"errors.py trich dan file khong ton tai: {name}"
            )

    def test_every_meetai_error_subclass_documents_itself(self) -> None:
        import inspect

        from meetai import errors

        for name, obj in inspect.getmembers(errors, inspect.isclass):
            if issubclass(obj, errors.MeetAIError):
                assert obj.__doc__, name
