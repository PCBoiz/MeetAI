"""MeetAI's deterministic policy rules, with no framework dependency.

This module owns the vocabulary and the prohibitions. It imports nothing but
the standard library and :mod:`meetai.errors`, so the same rules can be applied
to a configuration at startup, to a proposed utterance at runtime, and to a
test fixture, without any of them agreeing on a web framework, a settings
library, or a model engine.

That separation is the point. The handoff document requires a deterministic
policy gate that an LLM cannot talk its way past; a gate that lives inside a
pydantic validator can only ever answer questions about startup configuration.
Slice S1.5 extends this module with the runtime gate and reuses the same
:class:`Violation` vocabulary.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass


class _PendingAwareEnum(enum.Enum):
    """Enum whose ``PENDING_DECISION`` member is falsy.

    Plain ``enum.Enum``, deliberately not ``str``-mixed: a ``(str, Enum)``
    member is equal to its raw string and truthy, which makes
    ``if settings.consent_mode:`` read like a sensible guard while failing open
    on exactly the state that must block. Serialisation goes through
    ``.value`` explicitly instead.
    """

    def __bool__(self) -> bool:
        return self.name != "PENDING_DECISION"


class ConsentMode(_PendingAwareEnum):
    """How consent is collected from meeting participants.

    ``PENDING_DECISION`` is the default because the operator has not chosen
    between per-participant consent and host-coordinated consent (handoff doc
    section 10, question 1). It is a real, usable value meaning "no media may
    be processed" - not an instruction to pick something sensible at runtime.
    """

    PENDING_DECISION = "pending_decision"
    PER_PARTICIPANT = "per_participant"
    HOST_COORDINATED = "host_coordinated"


class LateJoinPolicy(_PendingAwareEnum):
    """What happens when someone joins a session already in progress.

    A1 (circuit breaker) and A3 (host-controlled admission) are the two designs
    the handoff document keeps open. Neither was chosen, so the default refuses
    to run rather than guessing.
    """

    PENDING_DECISION = "pending_decision"
    A1_CIRCUIT_BREAKER = "a1_circuit_breaker"
    A3_ADMISSION_CONTROL = "a3_admission_control"


class ConsentScope(enum.Enum):
    """The separable things a participant can consent to.

    The handoff document (section 5) requires these four to be distinct, so
    that granting one never grants another. ``LIVE_MEDIA`` is first because it
    is the prerequisite for everything else and the one most easily forgotten:
    processing audio at all is its own grant, not a side effect of being in the
    meeting.
    """

    LIVE_MEDIA = "live_media"
    DURABLE_TRANSCRIPT = "durable_transcript"
    REPLY_JOURNAL = "reply_journal"
    DEBUG_RAW_AUDIO = "debug_raw_audio"


@dataclass(frozen=True, slots=True)
class Violation:
    """One broken rule.

    ``rule`` is a stable machine-readable identifier for tests and logs.
    ``reason`` is operator-facing Vietnamese without diacritics, so it survives
    a Windows console whose code page is not UTF-8. Neither field may ever
    contain a configuration value or meeting content.
    """

    rule: str
    reason: str


@dataclass(frozen=True, slots=True)
class ConfigurationFlags:
    """The policy-relevant subset of the operator's configuration.

    A plain dataclass rather than the settings model, so :func:`rejected_configuration`
    stays testable without constructing a pydantic object and cannot accidentally
    reach a credential field.
    """

    consent_mode: ConsentMode
    late_join_policy: LateJoinPolicy
    persist_transcript: bool
    persist_notes: bool
    persist_reply_journal: bool
    persist_raw_audio_debug: bool
    raw_audio_debug_acknowledged: bool
    requested_external_ai: bool
    requested_live_discord_voice: bool


# Scope rules the operator cannot switch on, because they are out of MeetAI's
# scope entirely rather than merely undecided. Keyed by rule id so a test can
# assert the full set is covered.
_OUT_OF_SCOPE_REASONS: dict[str, str] = {
    "external_ai": (
        "Gui audio hoac transcript cuoc hop toi dich vu AI ben ngoai nam ngoai pham vi "
        "MeetAI. Xoa bien cau hinh nay thay vi ghi de."
    ),
    "live_discord_voice": (
        "Live Discord voice receive bi chan boi cong bang chung 0-S / 0-P / 0-C. "
        "Tinh nang nay duoc mo bang bang chung va quyet dinh cua chu du an, "
        "khong phai bang cau hinh."
    ),
}


def rejected_configuration(flags: ConfigurationFlags) -> tuple[Violation, ...]:
    """Return every reason this configuration must not be allowed to start.

    An empty tuple means the configuration is permitted. The function is pure:
    same input, same output, no I/O, no environment access.
    """
    violations: list[Violation] = []

    if flags.requested_external_ai:
        violations.append(Violation("external_ai", _OUT_OF_SCOPE_REASONS["external_ai"]))
    if flags.requested_live_discord_voice:
        violations.append(
            Violation("live_discord_voice", _OUT_OF_SCOPE_REASONS["live_discord_voice"])
        )

    # Persistence of meeting content is an opt-in that only exists *after* a
    # consent policy has been chosen. Writing transcripts while declaring "I
    # have not decided how consent works" is incoherent, and the incoherent
    # direction must be the one that fails.
    if not flags.consent_mode and _any_content_persistence(flags):
        violations.append(
            Violation(
                "persistence_before_consent_decision",
                "Khong the bat luu noi dung cuoc hop khi consent_mode van la "
                "pending_decision. Chon consent policy truoc (cong 0-U).",
            )
        )

    # Debug raw audio is the most sensitive scope. It gets its own
    # acknowledgement rather than riding on another scope's switch: otherwise
    # saying yes to transcripts would silently unlock raw audio capture.
    if flags.persist_raw_audio_debug and not flags.raw_audio_debug_acknowledged:
        violations.append(
            Violation(
                "raw_audio_debug_unacknowledged",
                "Debug raw audio la mot scope consent rieng. Can xac nhan rieng cho "
                "scope nay, khong duoc suy ra tu quyet dinh luu transcript.",
            )
        )

    return tuple(violations)


def _any_content_persistence(flags: ConfigurationFlags) -> bool:
    """True if any switch would write meeting content to disk."""
    return any(
        (
            flags.persist_transcript,
            flags.persist_notes,
            flags.persist_reply_journal,
            flags.persist_raw_audio_debug,
        )
    )


def media_processing_allowed(flags: ConfigurationFlags) -> bool:
    """Whether live media may be processed at all under this configuration.

    Both policy choices must be decided. This is the single named gate that
    media code must consult; the handoff document's "pending_decision means no
    media may be processed" is a property of this function, not a comment.
    """
    return bool(flags.consent_mode) and bool(flags.late_join_policy)


def pending_decisions(flags: ConfigurationFlags) -> tuple[str, ...]:
    """Names of the policy choices still awaiting a decision."""
    pending: list[str] = []
    if not flags.consent_mode:
        pending.append("consent_mode")
    if not flags.late_join_policy:
        pending.append("late_join_policy")
    return tuple(pending)
