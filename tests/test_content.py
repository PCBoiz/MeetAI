"""Tests that meeting content cannot be rendered by accident.

``MeetingContent`` exists because the protection has to live in the type.
These tests cover every way Python might stringify an object on a developer's
behalf.
"""

from __future__ import annotations

import json
import logging

import pytest

from meetai.content import MeetingContent

CANARY = "NOI-DUNG-CUOC-HOP-KHONG-DUOC-HIEN-RA"


class TestRendering:
    def test_repr_reports_shape_only(self) -> None:
        text = MeetingContent(CANARY)
        assert CANARY not in repr(text)
        assert f"chars={len(CANARY)}" in repr(text)

    def test_str_reports_shape_only(self) -> None:
        assert CANARY not in str(MeetingContent(CANARY))

    def test_fstring_is_safe(self) -> None:
        text = MeetingContent(CANARY)
        assert CANARY not in f"{text}"
        assert CANARY not in f"{text!r}"
        assert CANARY not in f"{text!s}"

    def test_percent_formatting_is_safe(self) -> None:
        # Percent formatting is the idiom under test, not a style slip:
        # logging defers formatting and then applies exactly this.
        text = MeetingContent(CANARY)
        assert CANARY not in "%s" % (text,)  # noqa: UP031
        assert CANARY not in "%r" % (text,)  # noqa: UP031

    def test_format_builtin_is_safe(self) -> None:
        assert CANARY not in format(MeetingContent(CANARY))

    def test_json_default_str_is_safe(self) -> None:
        """A structured log formatter typically falls back to `default=str`."""
        payload = json.dumps({"x": MeetingContent(CANARY)}, default=str)
        assert CANARY not in payload

    def test_inside_a_container_repr(self) -> None:
        text = MeetingContent(CANARY)
        assert CANARY not in repr([text])
        assert CANARY not in repr({"k": text})

    def test_logging_interpolation_is_safe(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        with caplog.at_level(logging.INFO):
            logging.getLogger("t").info("said %s", MeetingContent(CANARY))
        assert CANARY not in caplog.text

    def test_exception_message_interpolation_is_safe(self) -> None:
        text = MeetingContent(CANARY)
        exc = ValueError(f"unparseable: {text}")
        assert CANARY not in str(exc)


class TestAccess:
    def test_text_reachable_only_via_unsafe_text(self) -> None:
        assert MeetingContent(CANARY).unsafe_text() == CANARY

    def test_no_public_text_attribute(self) -> None:
        """No convenient alias that would bypass the conspicuous accessor."""
        text = MeetingContent(CANARY)
        assert not hasattr(text, "text")
        assert not hasattr(text, "value")

    def test_slots_prevent_attribute_injection(self) -> None:
        text = MeetingContent(CANARY)
        with pytest.raises(AttributeError):
            text.extra = "x"  # type: ignore[attr-defined]


class TestSafeMetadata:
    def test_char_count_and_kind_are_exposed(self) -> None:
        text = MeetingContent(CANARY, kind="transcript")
        assert text.char_count == len(CANARY)
        assert text.kind == "transcript"
        assert len(text) == len(CANARY)

    def test_truthiness_follows_emptiness(self) -> None:
        assert MeetingContent("x")
        assert not MeetingContent("")

    def test_kind_appears_in_repr(self) -> None:
        assert "transcript" in repr(MeetingContent(CANARY, kind="transcript"))


class TestDeliberateOmissions:
    def test_equality_is_not_implemented(self) -> None:
        """Content must not become a dict key or a cache entry by default.

        Comparison is a domain operation with its own normalisation rules; an
        inherited default would invite content into caches nobody purges.
        """
        a = MeetingContent(CANARY)
        b = MeetingContent(CANARY)
        assert a != b
        assert a == a
