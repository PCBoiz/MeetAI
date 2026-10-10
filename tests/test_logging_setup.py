"""Tests that the log can carry metadata and nothing else.

The assertions are written as canary searches: a sentinel string is pushed
through a logging idiom and must not appear in the output. That shape matters
because the failure mode is not "the log is wrong" but "the log contains a
transcript", and only a search for the content proves it absent.
"""

from __future__ import annotations

import io
import json
import logging
from collections.abc import Iterator

import pytest
from pydantic import SecretStr, ValidationError

from meetai.content import MeetingContent
from meetai.logging_setup import (
    ALLOWED_FIELDS,
    JsonMetadataFormatter,
    MetadataOnlyFilter,
    configure_logging,
    get_logger,
    session_context,
)
from meetai.settings import load_settings
from tests.conftest import CANARY_SECRET

CANARY_CONTENT = "TRANSCRIPT-SENTINEL-chuyen-nay-khong-duoc-ghi-ra-log"


@pytest.fixture
def log_stream() -> Iterator[io.StringIO]:
    """A configured logger writing to an in-memory stream."""
    stream = io.StringIO()
    configure_logging(level=logging.DEBUG, stream=stream)
    try:
        yield stream
    finally:
        root = logging.getLogger()
        for handler in list(root.handlers):
            root.removeHandler(handler)
            handler.close()


def _records(stream: io.StringIO) -> list[dict[str, object]]:
    return [json.loads(line) for line in stream.getvalue().splitlines() if line.strip()]


class TestStructure:
    def test_each_line_is_one_json_object(self, log_stream: io.StringIO) -> None:
        log = get_logger("t")
        log.info("first", extra={"event": "a"})
        log.info("second", extra={"event": "b"})
        records = _records(log_stream)
        assert [r["event"] for r in records] == ["a", "b"]

    def test_standard_keys_present(self, log_stream: io.StringIO) -> None:
        get_logger("t").warning("something", extra={"event": "x"})
        record = _records(log_stream)[0]
        assert set(record) >= {"ts", "level", "logger", "msg", "event"}
        assert record["level"] == "WARNING"

    def test_configure_is_idempotent(self) -> None:
        """A second call must replace the handler, not add another."""
        stream = io.StringIO()
        configure_logging(level=logging.INFO, stream=stream)
        configure_logging(level=logging.INFO, stream=stream)
        get_logger("t").info("once", extra={"event": "e"})
        assert len(_records(stream)) == 1


class TestAllowlist:
    def test_allowlisted_field_survives(self, log_stream: io.StringIO) -> None:
        get_logger("t").info("ok", extra={"session_id": "s-1", "duration_ms": 12})
        record = _records(log_stream)[0]
        assert record["session_id"] == "s-1"
        assert record["duration_ms"] == 12

    def test_unknown_field_is_dropped_and_counted(self, log_stream: io.StringIO) -> None:
        get_logger("t").info(
            "ok", extra={"transcript": CANARY_CONTENT, "event": "asr_done"}
        )
        record = _records(log_stream)[0]
        assert CANARY_CONTENT not in json.dumps(record)
        assert "transcript" not in record
        assert record["dropped_fields"] == 1
        assert record["event"] == "asr_done"

    def test_content_fields_are_not_allowlisted(self) -> None:
        """A field name that obviously carries content must never be permitted."""
        forbidden = {
            "text",
            "transcript",
            "utterance",
            "content",
            "message_body",
            "audio",
            "token",
            "secret",
            "prompt",
            "reply",
        }
        assert not (forbidden & ALLOWED_FIELDS)


class TestExceptionSanitising:
    def test_validation_error_payload_is_not_logged(
        self, log_stream: io.StringIO, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """`logger.exception` on a ValidationError is the worst-case idiom.

        pydantic carries the raw input - credentials included, untruncated - in
        `errors()[i]["input"]`, and the default formatter renders the traceback.
        """
        monkeypatch.setenv("MEETAI_DISCORD_BOT_TOKEN", CANARY_SECRET)
        monkeypatch.setenv("MEETAI_UI_HOST", "0.0.0.0")
        try:
            load_settings()
        except ValidationError:
            get_logger("t").exception("config failed", extra={"event": "config"})

        output = log_stream.getvalue()
        assert CANARY_SECRET not in output
        record = _records(log_stream)[0]
        assert record["error_type"] == "ValidationError"
        assert "ui_host" in str(record["error_detail"])

    def test_arbitrary_exception_reports_type_only(self, log_stream: io.StringIO) -> None:
        try:
            raise RuntimeError(f"nguoi noi: {CANARY_CONTENT}")
        except RuntimeError:
            get_logger("t").exception("failed", extra={"event": "e"})

        output = log_stream.getvalue()
        assert CANARY_CONTENT not in output
        assert _records(log_stream)[0]["error_type"] == "RuntimeError"

    def test_no_traceback_text_in_output(self, log_stream: io.StringIO) -> None:
        try:
            raise ValueError("boom")
        except ValueError:
            get_logger("t").exception("failed", extra={"event": "e"})
        output = log_stream.getvalue()
        assert "Traceback" not in output
        assert "test_logging_setup.py" not in output


class TestContentWrappers:
    def test_meeting_content_interpolation_is_safe(self, log_stream: io.StringIO) -> None:
        """The idiom `logger.info("%s", obj)` must be safe for content."""
        get_logger("t").info(
            "utterance %s", MeetingContent(CANARY_CONTENT), extra={"event": "asr"}
        )
        output = log_stream.getvalue()
        assert CANARY_CONTENT not in output
        assert "chars=" in output

    def test_secret_interpolation_is_safe(self, log_stream: io.StringIO) -> None:
        get_logger("t").info(
            "token %s", SecretStr(CANARY_SECRET), extra={"event": "auth"}
        )
        assert CANARY_SECRET not in log_stream.getvalue()

    def test_settings_object_interpolation_is_safe(self, log_stream: io.StringIO) -> None:
        s = load_settings(discord_bot_token=SecretStr(CANARY_SECRET))
        get_logger("t").info("settings %s", s, extra={"event": "boot"})
        assert CANARY_SECRET not in log_stream.getvalue()


class TestThirdPartyLoggers:
    @pytest.mark.parametrize(
        "logger_name", ["fastapi", "opentelemetry.trace", "uvicorn.access", "httpx"]
    )
    def test_third_party_records_go_through_the_allowlist(
        self, log_stream: io.StringIO, logger_name: str
    ) -> None:
        """Once a root handler exists, every library logger inherits it."""
        logging.getLogger(logger_name).error(
            "library said something", extra={"transcript": CANARY_CONTENT}
        )
        assert CANARY_CONTENT not in log_stream.getvalue()

    def test_unknown_third_party_logger_also_filtered(
        self, log_stream: io.StringIO
    ) -> None:
        """A library not on the ceiling list must still be filtered."""
        logging.getLogger("some.new.library").warning(
            "hello", extra={"body": CANARY_CONTENT}
        )
        assert CANARY_CONTENT not in log_stream.getvalue()


class TestSessionContext:
    def test_session_id_is_stamped(self, log_stream: io.StringIO) -> None:
        with session_context("sess-42"):
            get_logger("t").info("inside", extra={"event": "e"})
        assert _records(log_stream)[0]["session_id"] == "sess-42"

    def test_session_id_absent_outside_the_block(self, log_stream: io.StringIO) -> None:
        with session_context("sess-42"):
            pass
        get_logger("t").info("outside", extra={"event": "e"})
        assert "session_id" not in _records(log_stream)[0]

    def test_explicit_session_id_wins(self, log_stream: io.StringIO) -> None:
        with session_context("sess-outer"):
            get_logger("t").info("x", extra={"session_id": "sess-explicit"})
        assert _records(log_stream)[0]["session_id"] == "sess-explicit"


class TestFilterAndFormatterDirectly:
    def test_filter_returns_true_so_the_record_is_kept(self) -> None:
        """Filtering must sanitise, not silence."""
        record = logging.LogRecord("x", logging.INFO, "f", 1, "m", None, None)
        assert MetadataOnlyFilter().filter(record) is True

    def test_formatter_emits_only_allowlisted_keys(self) -> None:
        record = logging.LogRecord("x", logging.INFO, "f", 1, "m", None, None)
        record.event = "e"
        record.transcript = CANARY_CONTENT
        payload = json.loads(JsonMetadataFormatter().format(record))
        assert "transcript" not in payload
        assert payload["event"] == "e"


class TestEnumFieldSerialisation:
    """An enum field must log its `.value`, not `ClassName.MEMBER`.

    The earlier helper inspected `type(value).__mro__[1].__name__ == "Enum"`,
    which misses any enum with an intermediate base class - including both of
    MeetAI's policy enums, whose shared base supplies `__bool__`. The symptom
    was a log line carrying a different string from the one the config used,
    which a downstream comparison would then fail to match.
    """

    def test_policy_enum_logs_its_value(self, log_stream: io.StringIO) -> None:
        from meetai.policy import ConsentMode

        get_logger("t").info("x", extra={"state": ConsentMode.PER_PARTICIPANT})
        assert _records(log_stream)[0]["state"] == "per_participant"

    def test_capability_enum_logs_its_value(self, log_stream: io.StringIO) -> None:
        from meetai.capabilities import CapabilityName

        get_logger("t").info("x", extra={"capability": CapabilityName.ASR})
        assert _records(log_stream)[0]["capability"] == "asr"

    def test_enum_with_intermediate_base_is_handled(self) -> None:
        """Directly covers the shape the old mro[1] check got wrong."""
        import enum

        from meetai.logging_setup import _jsonable

        class Base(enum.Enum):
            def __bool__(self) -> bool:
                return True

        class Derived(Base):
            MEMBER = "member_value"

        assert _jsonable(Derived.MEMBER) == "member_value"
