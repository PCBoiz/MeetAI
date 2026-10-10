"""Wrappers for data that must not be rendered.

``SecretStr`` already protects credentials in this codebase, and it works
because the protection lives in the *type* rather than in the discipline of
every call site. Meeting content needs the same treatment and needs it before
the first transcript type exists: once an ASR result is a plain ``str`` inside
an ordinary dataclass, every auto-generated ``__repr__``, every
``logger.info("%s", obj)`` and every exception message becomes a way to write a
transcript to disk.

So content is wrapped, its ``repr`` reports shape only, and reading the text
requires saying :meth:`MeetingContent.unsafe_text` out loud - which is greppable
in review and lintable in CI.
"""

from __future__ import annotations

from typing import Final


class MeetingContent:
    """Text spoken in or derived from a meeting: transcript, notes, replies.

    ``repr`` and ``str`` report the character count and nothing else, so this
    object is safe to interpolate into a log line or an exception message by
    accident. The text is reachable only through :meth:`unsafe_text`.

    Equality and hashing are deliberately **not** implemented. Comparing two
    pieces of meeting content is a domain operation that belongs in the module
    that owns the comparison, with its own rules about normalisation; inheriting
    a default that compares raw text would invite content to be used as a dict
    key, which is how it ends up in a cache nobody remembers to purge.
    """

    __slots__ = ("_kind", "_text")

    def __init__(self, text: str, *, kind: str = "text") -> None:
        self._text: Final = text
        self._kind: Final = kind

    def __repr__(self) -> str:
        return f"<MeetingContent {self._kind} chars={len(self._text)}>"

    __str__ = __repr__

    def __len__(self) -> int:
        return len(self._text)

    def __bool__(self) -> bool:
        return bool(self._text)

    @property
    def kind(self) -> str:
        """What sort of content this is. Safe to log."""
        return self._kind

    @property
    def char_count(self) -> int:
        """Length in characters. Safe to log."""
        return len(self._text)

    def unsafe_text(self) -> str:
        """Return the raw text.

        Named to be conspicuous. Every call is a place where content leaves its
        wrapper, so every call should be reviewable on sight; passing the result
        to a logger or into an exception message is a defect.
        """
        return self._text
