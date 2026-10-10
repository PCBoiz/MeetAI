"""Structured, metadata-only logging (slice S0.5).

The requirement is that a log line may describe *that* something happened and
its shape, never *what was said*. Two design choices carry that:

1. **The field allowlist.** The formatter emits only keys named in
   :data:`ALLOWED_FIELDS`. A denylist would lose to the first new field name
   somebody invents; an allowlist fails in the direction of dropping a useful
   diagnostic rather than publishing a transcript. Dropped keys are counted and
   the count is reported, so the loss is visible instead of silent.

2. **Exception sanitising.** ``logger.exception`` and ``exc_info=True`` are the
   single most dangerous idiom here. A ``pydantic.ValidationError`` carries the
   raw input mapping - credentials included, untruncated - in
   ``exc.errors()[i]["input"]``, and the default formatter renders the whole
   traceback. :class:`MetadataOnlyFilter` replaces every exception with its
   type name plus a sanitised message and drops the traceback text.

Third-party loggers are also handled: once a root handler exists, every library
logger inherits it, so a library that interpolates an object into a warning can
publish content this module never saw. Everything goes through the same filter
and formatter regardless of origin.

Nothing here writes to a file. Log destination and retention are an operator
decision that has not been made (handoff doc section 10, item 5), so the
default sink is stderr, which has no retention at all.
"""

from __future__ import annotations

import enum
import json
import logging
import sys
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from contextvars import ContextVar
from typing import IO, Any

from pydantic import ValidationError

from meetai.settings import sanitised_validation_errors

#: Metadata keys a log record may carry.
#:
#: Each is a shape, an identifier, a count or an outcome - never text a person
#: said and never a credential. Adding a key here is a privacy decision and
#: should be reviewed as one.
ALLOWED_FIELDS: frozenset[str] = frozenset(
    {
        # Correlation. Opaque handles only: a session id is generated, and a
        # speaker handle is an internal mapping, never a display name.
        "session_id",
        "speaker_handle",
        "generation",
        # What happened.
        "event",
        "outcome",
        "decision",
        "state",
        "previous_state",
        "reason_code",
        "rule",
        "capability",
        "scope",
        "adapter",
        "synthetic",
        # Shape and cost.
        "char_count",
        "frame_count",
        "byte_count",
        "duration_ms",
        "queue_depth",
        "attempt",
        "dropped_fields",
        # Errors, type only.
        "error_type",
        "error_detail",
    }
)

#: Loggers that must never be louder than this, whatever the root level is.
#:
#: These libraries interpolate request paths, span objects and config values
#: into their own messages. The allowlist formatter would strip the structured
#: part, but the human message itself is theirs, so the volume is capped too.
_THIRD_PARTY_CEILINGS: Mapping[str, int] = {
    "uvicorn.access": logging.WARNING,
    "uvicorn.error": logging.WARNING,
    "fastapi": logging.WARNING,
    "opentelemetry": logging.WARNING,
    "httpx": logging.WARNING,
    "httpcore": logging.WARNING,
}

#: Session correlation id for the current task, stamped onto every record.
#:
#: Only an opaque id lives here. Putting a richer "session context" object in a
#: ContextVar is the obvious next step and the wrong one: the first author who
#: parks a live transcript buffer in it stamps content onto every record in the
#: process, including third-party ones.
_session_id: ContextVar[str | None] = ContextVar("meetai_session_id", default=None)

_LOGGER_NAME = "meetai"

# LogRecord's own attributes, so the filter can tell an injected `extra=` key
# from a built-in one.
_RESERVED_RECORD_ATTRS: frozenset[str] = frozenset(
    logging.LogRecord("", 0, "", 0, "", None, None).__dict__
) | {"message", "asctime", "taskName"}


def _sanitise_exception(exc: BaseException) -> str:
    """Describe an exception without any value it may be carrying.

    A ``ValidationError`` goes through the settings sanitiser, which keeps the
    field location and the message and drops the input. Anything else is
    reported by type only: its ``str()`` may embed the offending value, and in
    this codebase that value can be a credential or a transcript.
    """
    if isinstance(exc, ValidationError):
        return "; ".join(sanitised_validation_errors(exc))
    return f"{type(exc).__name__} (chi tiet bi loc bo de tranh ro ri noi dung)"


class MetadataOnlyFilter(logging.Filter):
    """Strip everything from a record that is not metadata.

    Runs on records from MeetAI and from third-party libraries alike. It
    mutates the record in place, which is how a ``logging.Filter`` is expected
    to normalise records, and returns ``True`` so the record is still emitted -
    the goal is a safe line, not a missing one.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        # Exceptions first: this is the leak route that matters most.
        if record.exc_info is not None:
            exc = record.exc_info[1]
            if exc is not None:
                record.error_type = type(exc).__name__
                record.error_detail = _sanitise_exception(exc)
            record.exc_info = None
        # exc_text is a formatter cache of the rendered traceback.
        record.exc_text = None
        record.stack_info = None

        # The human message is rendered now, while its arguments are still
        # available, and then the arguments are discarded. Anything whose repr
        # would expose content is the caller's defect; MeetingContent and
        # SecretStr both render as shape only, which is why they exist.
        record.msg = record.getMessage()
        record.args = None

        dropped = 0
        for key in list(record.__dict__):
            if key in _RESERVED_RECORD_ATTRS or key in ALLOWED_FIELDS:
                continue
            del record.__dict__[key]
            dropped += 1
        if dropped:
            record.dropped_fields = dropped

        session = _session_id.get()
        if session is not None and not hasattr(record, "session_id"):
            record.session_id = session
        return True


class JsonMetadataFormatter(logging.Formatter):
    """Render a record as one JSON object containing only allowlisted keys."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        for key in sorted(ALLOWED_FIELDS):
            if hasattr(record, key):
                payload[key] = _jsonable(getattr(record, key))
        return json.dumps(payload, ensure_ascii=False, default=str)


def _jsonable(value: object) -> object:
    """Coerce an allowlisted field to something ``json.dumps`` accepts.

    Enums become their ``.value`` rather than ``str(member)``, which for a
    non-``str`` enum would be ``"ClassName.MEMBER"`` - a different string from
    the one the configuration used.
    """
    if isinstance(value, enum.Enum):
        # Checked before the scalar case: a str-mixed member is also a str, and
        # `str(member)` renders "ClassName.MEMBER" - a different string from the
        # one the configuration file used, which a downstream comparison against
        # the logged value would then fail to match.
        return _jsonable(value.value)
    if isinstance(value, bool | int | float | str) or value is None:
        return value
    return str(value)


def configure_logging(
    *,
    level: int = logging.INFO,
    stream: IO[str] | None = None,
) -> logging.Logger:
    """Install the metadata-only handler as the process's only log sink.

    Idempotent: calling it again replaces the handler rather than adding a
    second one, so a repeated call cannot double every line or leave an
    unfiltered handler behind.

    Returns MeetAI's own logger for convenience. The handler is installed on
    the **root** logger so that third-party records are filtered too.
    """
    handler = logging.StreamHandler(stream if stream is not None else sys.stderr)
    handler.setFormatter(JsonMetadataFormatter())
    handler.addFilter(MetadataOnlyFilter())

    root = logging.getLogger()
    for existing in list(root.handlers):
        root.removeHandler(existing)
        existing.close()
    root.addHandler(handler)
    root.setLevel(level)

    for name, ceiling in _THIRD_PARTY_CEILINGS.items():
        third_party = logging.getLogger(name)
        third_party.setLevel(max(level, ceiling))

    return logging.getLogger(_LOGGER_NAME)


def get_logger(name: str | None = None) -> logging.Logger:
    """Return a MeetAI logger. ``name`` is appended under the ``meetai`` root."""
    return logging.getLogger(_LOGGER_NAME if name is None else f"{_LOGGER_NAME}.{name}")


@contextmanager
def session_context(session_id: str) -> Iterator[None]:
    """Stamp ``session_id`` onto every record emitted inside this block."""
    token = _session_id.set(session_id)
    try:
        yield
    finally:
        _session_id.reset(token)
