"""What MeetAI can actually do right now, and why not, when it cannot.

The handoff document requires the supervisor to state plainly that it cannot
participate and why - a build that is not ready must never read as ready. That
only holds if an unavailable capability cannot exist without a reason, so the
invariant is enforced in :class:`Capability`'s constructor rather than left to
whoever edits the list.

The registry is also the seam the platform adapters will report through
(slice S1.3): an adapter declares its own capability, and a fake adapter is
required to say it is synthetic. Keeping that in one typed place now means the
CLI and the future web UI render the same truth instead of each maintaining a
hand-written dict.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class CapabilityName(Enum):
    """The capabilities the supervisor reports on.

    A closed enum rather than free strings so a typo cannot invent a
    capability, and so the renderer cannot silently omit one.

    Not ``str``-mixed, for the same reason as the policy enums: a mixed member
    is equal to its raw value and renders as ``ClassName.MEMBER`` under
    ``str()``, so serialisation goes through ``.value`` explicitly instead.
    """

    CONFIG_VALIDATION = "config_validation"
    STRUCTURED_LOGGING = "structured_logging"
    CONSENT_GATE = "consent_gate"
    SESSION_LIFECYCLE = "session_lifecycle"
    AUTHORITY_GATE = "authority_gate"
    MEETING_PLANNER = "meeting_planner"
    KNOWLEDGE_STORE = "knowledge_store"
    PLATFORM_ADAPTER_FAKE = "platform_adapter_fake"
    LOCAL_WEB_UI = "local_web_ui"
    CALENDAR_CONNECTOR = "calendar_connector"
    PLATFORM_ADAPTER_DISCORD = "platform_adapter_discord"
    LIVE_VOICE_RECEIVE = "live_voice_receive"
    ASR = "asr"
    LLM = "llm"
    TTS = "tts"


class BlockedBy(Enum):
    """Why a capability is unavailable, as a stable identifier.

    Separate from the human prose because a UI must be able to branch on this,
    and branching on free Vietnamese text means string-matching a sentence
    somebody will reword. The project already draws this distinction elsewhere
    - ``GateOutcome.reason`` and ``Violation.rule`` are both stable ids with
    prose alongside - and ``Capability`` was the outlier.

    The discriminator also carries *what the operator can do about it*, which
    is what the UI needs in order to decide whether to render a control.
    Rendering a button next to something the operator cannot fix is its own
    kind of dishonesty.
    """

    NOT_BUILT = "not_built"
    """No code yet. Nothing the operator can do."""

    EVIDENCE_GATE = "evidence_gate"
    """Blocked by an open evidence gate. Needs evidence, not a toggle."""

    PENDING_DECISION = "pending_decision"
    """Blocked by a policy choice the operator has not made. They can decide."""

    NOT_RUNNING = "not_running"
    """Built, but not active in this process. The operator can start it.

    Added because the three members above could not describe the local web UI
    honestly. It was reported as ``NOT_BUILT`` - whose docstring says "No code
    yet. Nothing the operator can do" - while ``ui.py`` had seven routes,
    ``meetai serve`` ran it and 62 tests covered it. Both halves of that
    sentence were false, and it is printed to the operator.

    The distinction this enum exists to carry is *what the operator can do*,
    and the docstring above says rendering a control next to something they
    cannot fix is its own kind of dishonesty. Not rendering one next to
    something they **can** do is the same mistake facing the other way.
    """

    @property
    def operator_can_act(self) -> bool:
        return self in {BlockedBy.PENDING_DECISION, BlockedBy.NOT_RUNNING}


@dataclass(frozen=True, slots=True)
class Capability:
    """One capability and its honest status.

    ``synthetic`` marks a capability backed by a mock or a replay fixture. A
    fake platform adapter sets it, so a synthetic success can never be read as
    evidence that a real integration works - the handoff document calls that
    out specifically, and it is the kind of claim that is easy to make by
    accident in a status display.
    """

    name: CapabilityName
    available: bool
    blocked_reason: str | None = None
    blocked_by: BlockedBy | None = None
    synthetic: bool = False

    def __post_init__(self) -> None:
        if not self.available and self.blocked_by is None:
            raise ValueError(
                f"Capability {self.name.value} khong kha dung nhung thieu "
                "blocked_by. UI can mot ma on dinh de biet nen hien control gi."
            )
        if self.available and self.blocked_by is not None:
            raise ValueError(
                f"Capability {self.name.value} kha dung nhung lai co blocked_by."
            )
        if not self.available and not self.blocked_reason:
            raise ValueError(
                f"Capability {self.name.value} khong kha dung nhung thieu ly do. "
                "Moi capability OFF phai noi ro vi sao."
            )
        if self.available and self.blocked_reason:
            raise ValueError(
                f"Capability {self.name.value} kha dung nhung lai co ly do bi chan."
            )

    @property
    def display_status(self) -> str:
        """Short status token for a text or HTML report."""
        if not self.available:
            return "OFF"
        return "MOCK" if self.synthetic else "ON"


@dataclass(frozen=True, slots=True)
class CapabilityReport:
    """The full set of capabilities, guaranteed complete.

    Completeness is checked rather than assumed: a capability added to the enum
    and forgotten here would otherwise disappear from the report, which is the
    optimistic direction of failure and the one that matters.
    """

    capabilities: tuple[Capability, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        reported = [c.name for c in self.capabilities]
        duplicates = {n for n in reported if reported.count(n) > 1}
        if duplicates:
            raise ValueError(
                "Capability bi khai bao trung: "
                + ", ".join(sorted(n.value for n in duplicates))
            )
        missing = set(CapabilityName) - set(reported)
        if missing:
            raise ValueError(
                "Capability chua duoc bao cao: "
                + ", ".join(sorted(n.value for n in missing))
            )

    def as_dict(self) -> dict[str, dict[str, object]]:
        """Machine-readable form for the JSON report and the future UI."""
        return {
            c.name.value: {
                "available": c.available,
                "blocked_reason": c.blocked_reason,
                "blocked_by": None if c.blocked_by is None else c.blocked_by.value,
                "operator_can_act": (
                    c.blocked_by.operator_can_act if c.blocked_by is not None else False
                ),
                "synthetic": c.synthetic,
            }
            for c in self.capabilities
        }


# Reasons shared by several unbuilt capabilities, named so the text stays
# consistent between the CLI, the future UI and the tests.
_GATE_0_BLOCKED = (
    "cong bang chung 0-S / 0-P / 0-C chua dong: chua co bang chung ve standard bot "
    "nhan inbound guild voice, mapping nguoi noi, va policy Discord"
)
_NOT_BUILT = "chua trien khai (xem docs/plan.md)"


def current_capabilities() -> CapabilityReport:
    """Build the capability report for this build.

    Everything not implemented is reported ``False`` with a reason. When a
    slice lands, its entry changes here and the renderers follow automatically.
    """
    return CapabilityReport(
        (
            Capability(CapabilityName.CONFIG_VALIDATION, available=True),
            Capability(CapabilityName.STRUCTURED_LOGGING, available=True),
            Capability(CapabilityName.CONSENT_GATE, available=True),
            Capability(CapabilityName.SESSION_LIFECYCLE, available=True),
            Capability(CapabilityName.AUTHORITY_GATE, available=True),
            # Decides joins from calendar fixtures. The real calendar
            # connector is a separate capability and is still off.
            Capability(CapabilityName.MEETING_PLANNER, available=True),
            # Holds approved cards and cascades deletions. Retrieval is
            # metadata + exact match; no embeddings yet, by design.
            Capability(CapabilityName.KNOWLEDGE_STORE, available=True),
            # Available, and marked synthetic: it exercises the machinery
            # and proves nothing about any platform.
            Capability(
                CapabilityName.PLATFORM_ADAPTER_FAKE, available=True, synthetic=True
            ),
            Capability(
                CapabilityName.LOCAL_WEB_UI,
                available=False,
                blocked_reason=(
                    "da xay o lat S0.6 va co test, nhung can extra 'ui' "
                    "(uv sync --extra ui) va chay 'meetai serve'; khong tu "
                    "khoi dong cung 'meetai status'"
                ),
                blocked_by=BlockedBy.NOT_RUNNING,
            ),
            Capability(
                CapabilityName.CALENDAR_CONNECTOR,
                available=False,
                blocked_reason=f"{_NOT_BUILT}: lat S1.4 tren fixture, chua ket noi that",
                blocked_by=BlockedBy.NOT_BUILT,
            ),
            Capability(
                CapabilityName.PLATFORM_ADAPTER_DISCORD,
                available=False,
                blocked_reason=_GATE_0_BLOCKED,
                blocked_by=BlockedBy.EVIDENCE_GATE,
            ),
            Capability(
                CapabilityName.LIVE_VOICE_RECEIVE,
                available=False,
                blocked_reason=_GATE_0_BLOCKED,
                blocked_by=BlockedBy.EVIDENCE_GATE,
            ),
            Capability(
                CapabilityName.ASR,
                available=False,
                blocked_reason=f"{_NOT_BUILT}: da benchmark o S2.2 (SyER 23.47% tren doc cau), nhung chua co duong ASR nao trong pipeline va S2.2 van partial/open",
                blocked_by=BlockedBy.NOT_BUILT,
            ),
            Capability(
                CapabilityName.LLM,
                available=False,
                blocked_reason=f"{_NOT_BUILT}: da benchmark o S2.3 (43 case, 5 truc), nhung chua co inference nao trong pipeline va S2.3 van partial/open",
                blocked_by=BlockedBy.NOT_BUILT,
            ),
            Capability(
                CapabilityName.TTS,
                available=False,
                blocked_reason=f"{_NOT_BUILT}: chua phai phu thuoc cua MVP",
                blocked_by=BlockedBy.NOT_BUILT,
            ),
        )
    )
