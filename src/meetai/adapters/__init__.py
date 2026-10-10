"""Platform adapters.

The interfaces live in :mod:`meetai.adapters.base` and are split by capability
rather than gathered into one object, because the capabilities genuinely differ
in availability: sending text to a Discord channel is a documented, supported
operation today, while receiving guild voice audio with a bot token is an open
evidence gate. One interface covering both would force every adapter to claim
both.

:mod:`meetai.adapters.fake` is a synthetic adapter for tests and replay. It is
required to identify itself as synthetic, and the base class enforces that.
"""

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

__all__ = [
    "AdapterCapabilities",
    "AdapterHealth",
    "AudioFrame",
    "ControlPlane",
    "InboundAudio",
    "OutboundText",
    "ParticipantEvent",
    "ParticipantEventKind",
    "PlatformAdapter",
]
