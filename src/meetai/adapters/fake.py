"""A synthetic adapter for tests and replay (slice S1.3).

Its purpose is to exercise the session, consent and gate machinery without any
network, any platform account, or any real participant. It is **not** evidence
about any platform, and it is built so it cannot be mistaken for evidence:

- ``platform`` is ``"fake"``, and the base class refuses a synthetic adapter
  that takes a real platform's name.
- ``synthetic=True``, so every status display shows ``MOCK`` rather than ``ON``.
- Every frame it emits carries ``synthetic=True``, so the marking survives into
  the pipeline rather than stopping at the adapter boundary.

It supports inbound audio, which a real Discord adapter currently may not. That
asymmetry is the honest one: a fake can obviously produce bytes, and pretending
otherwise would make the harness useless without making anything safer.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass, field

from meetai.adapters.base import (
    AdapterCapabilities,
    AdapterHealth,
    AudioFrame,
    ControlPlane,
    InboundAudio,
    OutboundText,
    ParticipantEvent,
    ParticipantEventKind,
    PlatformAdapter,
)
from meetai.content import MeetingContent

FAKE_PLATFORM = "fake"


@dataclass
class _ScriptedFrame:
    """One queued frame. ``pcm`` is synthetic bytes, never recorded audio."""

    participant: str | None
    pcm: bytes
    sample_rate: int = 16_000


class FakeAdapter(PlatformAdapter, ControlPlane, OutboundText, InboundAudio):
    """A scripted adapter driven entirely by the test that built it."""

    def __init__(self, *, clock: object = None, now: float = 0.0) -> None:
        super().__init__(
            AdapterCapabilities(
                platform=FAKE_PLATFORM,
                version="0.1.0",
                supports_control=True,
                supports_outbound_text=True,
                supports_inbound_audio=True,
                supports_speaker_mapping=True,
                synthetic=True,
                evidence="synthetic adapter; khong phai bang chung ve platform nao",
            )
        )
        self._now = now
        self._joined_channel: str | None = None
        self._events: list[ParticipantEvent] = []
        self._frames: list[_ScriptedFrame] = []
        self._sent: list[MeetingContent] = []
        self._leave_count = 0

    # ------------------------------------------------------------------ #
    # Scripting, for the test to drive
    # ------------------------------------------------------------------ #

    def script_participant_event(
        self, kind: ParticipantEventKind, participant: str
    ) -> None:
        self._events.append(ParticipantEvent(kind, participant, self._now))

    def script_frame(
        self,
        participant: str | None,
        pcm: bytes = b"\x00\x00",
        sample_rate: int = 16_000,
    ) -> None:
        """Queue a frame. ``participant=None`` models an unmapped speaker."""
        self._frames.append(_ScriptedFrame(participant, pcm, sample_rate))

    # ------------------------------------------------------------------ #
    # Observation, for the test to assert on
    # ------------------------------------------------------------------ #

    @property
    def joined_channel(self) -> str | None:
        return self._joined_channel

    @property
    def leave_count(self) -> int:
        """How many times ``leave`` was called. Must be safe to call when idle."""
        return self._leave_count

    @property
    def sent_messages(self) -> tuple[MeetingContent, ...]:
        """What was sent, still wrapped so a test cannot log it by accident."""
        return tuple(self._sent)

    # ------------------------------------------------------------------ #
    # ControlPlane
    # ------------------------------------------------------------------ #

    def join(self, channel_ref: str) -> None:
        self._joined_channel = channel_ref

    def leave(self) -> None:
        self._leave_count += 1
        self._joined_channel = None

    def participant_events(self) -> Iterator[ParticipantEvent]:
        events, self._events = self._events, []
        yield from events

    def health(self) -> AdapterHealth:
        if self._joined_channel is None:
            return AdapterHealth(connected=False, detail="chua join channel nao")
        return AdapterHealth(connected=True, detail="synthetic adapter dang join")

    # ------------------------------------------------------------------ #
    # OutboundText
    # ------------------------------------------------------------------ #

    def send_text(self, content: MeetingContent) -> None:
        self._sent.append(content)

    # ------------------------------------------------------------------ #
    # InboundAudio
    # ------------------------------------------------------------------ #

    def audio_frames(self) -> Iterator[AudioFrame]:
        frames, self._frames = self._frames, []
        for frame in frames:
            yield AudioFrame(
                participant=frame.participant,
                pcm=frame.pcm,
                sample_rate=frame.sample_rate,
                at=self._now,
                synthetic=True,
            )


@dataclass
class BlockedDiscordAdapter(PlatformAdapter, ControlPlane, OutboundText):
    """Placeholder for the real Discord adapter, deliberately without audio.

    It declares the *shape* of a Discord adapter - the control and outbound
    text planes, which Discord documents and supports - and does **not**
    implement :class:`InboundAudio`, because nothing has yet shown that a
    standard bot token can receive guild voice audio and map a speaker to a
    user. Evidence gates 0-S, 0-P and 0-C are open.

    It declares **no** capabilities as supported. That is not a contradiction
    with the paragraph above: the planes are what a Discord adapter *would*
    cover, and nothing here is implemented, so claiming any of them would be
    the misrepresentation the base class exists to prevent.

    It exists as a type rather than as a comment so the shape of the gap is
    visible in the code: when the evidence arrives, inbound audio is added here
    with its citation, and the base class will require that citation.

    Every operation that would have to reach Discord raises. Two deliberate
    exceptions, for different reasons.

    ``health()`` must not raise: a health check that raised would be
    indistinguishable from a crash, and the supervisor needs to ask "can you
    work?" and get "no, and here is why". It returns ``connected=False``
    citing the open gate.

    ``leave()`` is a no-op, because ``ControlPlane.leave`` is documented as
    "must be safe to call when not joined" and raising broke that contract for
    any caller unwinding after a failure. It is safe here precisely because
    ``join`` still raises, so there is never anything to leave.
    """

    _capabilities_init: AdapterCapabilities = field(
        init=False,
        default_factory=lambda: AdapterCapabilities(
            platform="discord",
            version="unimplemented",
            supports_control=False,
            supports_outbound_text=False,
            supports_inbound_audio=False,
            supports_speaker_mapping=False,
            synthetic=False,
            evidence=None,
        ),
        repr=False,
    )
    """What this adapter says about itself. **Not an ``__init__`` parameter.**

    It was one, accepted positionally, so a caller could construct this class
    declaring ``supports_inbound_audio=True``, ``synthetic=False``,
    ``platform="discord"`` and ``evidence="trust me"`` - and
    ``capabilities.as_dict()`` would report a real Discord integration with
    inbound audio. Measured.

    A **reporting** hole rather than an audio one: every operation still
    raises, this is still not an :class:`~meetai.adapters.base.InboundAudio`,
    and there is no code path on it that produces an ``AudioFrame``. What was
    at stake was what it *said*, which matters because the registry docstring
    describes a future seam where an adapter reports its own capability into
    ``meetai status`` - the moment that seam is wired, a forged declaration
    becomes a forged status line.

    ``init=False`` rather than ``__post_init__`` overwriting it: silently
    discarding what a caller asked for is worse than refusing, and refusing is
    a ``TypeError`` they will read.
    """

    def __post_init__(self) -> None:
        PlatformAdapter.__init__(self, self._capabilities_init)

    def _blocked(self) -> NotImplementedError:
        return NotImplementedError(
            "Discord adapter chua duoc trien khai. Cong bang chung 0-S / 0-P / 0-C "
            "chua dong: chua co nguon chinh thuc ve standard bot nhan inbound guild "
            "voice audio, mapping SSRC sang user, va policy hien hanh."
        )

    def join(self, channel_ref: str) -> None:
        raise self._blocked()

    def leave(self) -> None:
        """A no-op, and idempotent, because the contract says it must be.

        ``ControlPlane.leave`` is documented as "must be safe to call when not
        joined", and raising broke that for every caller unwinding after a
        failed join - they would have had to know whether the join succeeded
        before they could clean up.

        Safe to make a no-op precisely because this adapter can never join:
        ``join`` still raises, so there is never a session for ``leave`` to
        end. "You are not in a channel" is already true, which is what a
        cleanup verb is being asked to ensure. It opens no capability, touches
        no state, and leaves every other operation refusing.
        """

    def participant_events(self) -> Iterator[ParticipantEvent]:
        raise self._blocked()

    def health(self) -> AdapterHealth:
        return AdapterHealth(
            connected=False,
            detail="chua trien khai; cong bang chung 0-S / 0-P / 0-C chua dong",
        )

    def send_text(self, content: MeetingContent) -> None:
        raise self._blocked()
