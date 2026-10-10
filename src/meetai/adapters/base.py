"""Platform adapter interfaces, split by capability (slice S1.3).

Three separate protocols instead of one, because the three planes differ in
whether they are *available at all*:

- :class:`ControlPlane` - join, leave, participant events. Documented and
  supported on Discord today.
- :class:`OutboundText` - sending a message. Likewise supported.
- :class:`InboundAudio` - receiving guild voice audio with a bot token and
  mapping a speaker to a participant. **An open evidence gate.**

A single fat interface would make every adapter declare it implements inbound
audio, and the honest answer for Discord right now is that nobody has shown it
can. Keeping the planes apart lets an adapter support what it supports, and
lets the supervisor ask.

Every adapter declares :class:`AdapterCapabilities`, which carries an
``evidence`` field. That field is the point of this module: a capability is
claimed *together with* what substantiates it, and a synthetic adapter cannot
claim otherwise - :class:`PlatformAdapter` rejects an adapter that says it is
real without evidence, and rejects a synthetic one that pretends it is not.

No framework is imported here, and no Discord library. The domain does not
depend on an SDK.
"""

from __future__ import annotations

import enum
from abc import ABC, abstractmethod
from collections.abc import Iterator
from dataclasses import dataclass, field

from meetai.content import MeetingContent
from meetai.errors import MeetAIError


class AdapterMisrepresentationError(MeetAIError):
    """An adapter's declared capabilities do not match what it can prove.

    Raised at construction, not at use. An adapter that misdescribes itself is
    a defect in the adapter, and discovering it when the first audio frame
    arrives would be far too late.
    """


class ParticipantEventKind(enum.Enum):
    """What happened to a participant."""

    JOINED = "joined"
    LEFT = "left"
    SPEAKING_STARTED = "speaking_started"
    SPEAKING_STOPPED = "speaking_stopped"


@dataclass(frozen=True, slots=True)
class ParticipantEvent:
    """Something a participant did.

    ``participant`` is the adapter's opaque handle. ``display_name`` is
    deliberately absent: it is unstable, it is personal data, and this object
    flows into logs. An adapter that needs to show a name resolves it at the
    presentation layer.
    """

    kind: ParticipantEventKind
    participant: str
    at: float


@dataclass(frozen=True, slots=True)
class AudioFrame:
    """One chunk of inbound audio.

    ``participant`` is ``None`` when the platform could not map the speaker -
    which for Discord means SSRC-to-user mapping, itself an open evidence gate.
    The media gate treats ``None`` as a refusal, so the ambiguity is
    represented rather than guessed.

    ``repr`` reports shape only: this object holds audio, and an auto-generated
    repr would put it in the first log line that interpolated it.
    """

    participant: str | None
    pcm: bytes = field(repr=False)
    sample_rate: int
    at: float
    synthetic: bool = False
    """True when the frame came from a fake adapter or a replay fixture.

    Travels with the frame rather than being inferred from its source, so a
    synthetic frame cannot be mistaken for evidence further down the pipeline.
    """

    def __repr__(self) -> str:
        return (
            f"AudioFrame(participant={self.participant!r}, bytes={len(self.pcm)}, "
            f"sample_rate={self.sample_rate}, synthetic={self.synthetic})"
        )

    @property
    def byte_count(self) -> int:
        """Size in bytes. Safe to log."""
        return len(self.pcm)


@dataclass(frozen=True, slots=True)
class AdapterCapabilities:
    """What an adapter claims it can do, and what backs the claim.

    ``evidence`` is a short citation - a documentation URL, a ticket, a test
    manifest id. It is required for any claimed inbound-audio capability on a
    non-synthetic adapter, because that is the claim the handoff document says
    must not be made without proof.
    """

    platform: str
    version: str
    supports_control: bool = False
    supports_outbound_text: bool = False
    supports_inbound_audio: bool = False
    supports_speaker_mapping: bool = False
    synthetic: bool = False
    evidence: str | None = None

    def as_dict(self) -> dict[str, object]:
        """Metadata-only form for the status report and logs."""
        return {
            "platform": self.platform,
            "version": self.version,
            "supports_control": self.supports_control,
            "supports_outbound_text": self.supports_outbound_text,
            "supports_inbound_audio": self.supports_inbound_audio,
            "supports_speaker_mapping": self.supports_speaker_mapping,
            "synthetic": self.synthetic,
            "evidence": self.evidence,
        }


@dataclass(frozen=True, slots=True)
class AdapterHealth:
    """Whether the adapter is usable right now, and why not if it is not."""

    connected: bool
    detail: str

    def __post_init__(self) -> None:
        if not self.connected and not self.detail:
            raise ValueError("AdapterHealth khong connected phai co detail")


class ControlPlane(ABC):
    """Joining, leaving, and participant events."""

    @abstractmethod
    def join(self, channel_ref: str) -> None:
        """Join a channel identified by an allowlisted reference."""

    @abstractmethod
    def leave(self) -> None:
        """Leave. Must be safe to call when not joined."""

    @abstractmethod
    def participant_events(self) -> Iterator[ParticipantEvent]:
        """Yield participant events as they arrive."""

    @abstractmethod
    def health(self) -> AdapterHealth:
        """Report current usability."""


class OutboundText(ABC):
    """Sending text.

    Takes :class:`MeetingContent` rather than ``str`` so that what MeetAI is
    about to say is typed as content all the way to the boundary, and cannot be
    logged on the way out by an incidental interpolation.
    """

    @abstractmethod
    def send_text(self, content: MeetingContent) -> None:
        """Send a message. The caller has already passed the policy gate."""


class InboundAudio(ABC):
    """Receiving audio.

    Implementing this is a claim that the platform supports it, and
    :class:`PlatformAdapter` will not let a non-synthetic adapter make that
    claim without evidence.
    """

    @abstractmethod
    def audio_frames(self) -> Iterator[AudioFrame]:
        """Yield inbound audio frames.

        A frame whose speaker could not be mapped must carry
        ``participant=None`` rather than a guess. The media gate refuses those,
        which is the behaviour an unmapped speaker should get.
        """


class PlatformAdapter:
    """Base class that holds every adapter to its own description.

    A concrete base rather than an ABC: it declares no operations of its own,
    it only enforces that an adapter's claims match what it can prove. The
    operations live in the three capability protocols, which an adapter mixes
    in according to what it actually supports.

    The checks run at construction:

    - A non-synthetic adapter claiming inbound audio must cite evidence.
    - A non-synthetic adapter claiming speaker mapping must cite evidence.
    - Speaker mapping without inbound audio is incoherent.
    - A synthetic adapter must say ``synthetic=True`` **and** must not present a
      platform name that reads as a real integration.

    The last check is the one the handoff document asks for by name: a fake
    adapter must not report itself as a Discord integration. Without it, a
    passing test against a fake would look like evidence that the real thing
    works, which is the specific confusion the evidence gates exist to prevent.
    """

    def __init__(self, capabilities: AdapterCapabilities) -> None:
        self._validate(capabilities)
        self._capabilities = capabilities

    @property
    def capabilities(self) -> AdapterCapabilities:
        return self._capabilities

    @property
    def is_synthetic(self) -> bool:
        return self._capabilities.synthetic

    @staticmethod
    def _validate(capabilities: AdapterCapabilities) -> None:
        # This check also **subsumes** the speaker-mapping-needs-evidence
        # rule, which is why that rule is not written out separately below.
        # Reaching it would require speaker mapping without inbound audio,
        # which this refuses; with inbound audio, the evidence check below
        # already fires. A fourth branch spelling it out was unreachable -
        # confirmed by coverage, never executed - and the test that appeared
        # to cover it was passing on the inbound message's text instead.
        #
        # So if anyone ever relaxes *this* check, the mapping-without-evidence
        # case becomes constructible and the rule must be written back.
        if (
            capabilities.supports_speaker_mapping
            and not capabilities.supports_inbound_audio
        ):
            raise AdapterMisrepresentationError(
                "speaker mapping khong co y nghia khi khong nhan inbound audio"
            )

        if capabilities.synthetic:
            reserved = {"discord", "google meet", "zoom", "teams", "slack"}
            if capabilities.platform.strip().lower() in reserved:
                raise AdapterMisrepresentationError(
                    f"adapter synthetic khong duoc lay ten platform that "
                    f"({capabilities.platform!r}). Mot test dat qua fake adapter "
                    "khong phai bang chung rang integration that hoat dong."
                )
            return

        if capabilities.supports_inbound_audio and not capabilities.evidence:
            raise AdapterMisrepresentationError(
                "khai bao inbound audio ma khong co evidence. Day la cong bang "
                "chung 0-S: can nguon chinh thuc hoac trace tai lap duoc."
            )
