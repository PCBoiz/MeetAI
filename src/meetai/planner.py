"""Meeting planner (slice S1.4), driven by calendar fixtures.

Decides, for one calendar event, whether MeetAI should join — and refuses by
default. The scope is set by the handoff document (section 3, item 3): accept
only a clear, allowlisted channel reference; a configurable join window;
idempotent; and never auto-join a stale event after a restart.

Three decisions worth stating because they are not obvious:

**Timezones are the caller's problem, deliberately.** This module refuses a
naive ``datetime`` and never constructs a zone. Window and staleness are
instant arithmetic, which is timezone-free once the timestamps are aware, and
Google Calendar already returns RFC 3339 with an offset. Pushing zone handling
outward also avoids a real trap: Windows ships no IANA database, so
``ZoneInfo("Asia/Ho_Chi_Minh")`` raises on this machine unless ``tzdata`` is
installed. A module that quietly fell back to a fixed +07:00 would be making a
political assumption about Vietnam never adopting DST; a module that refuses
naive input makes the caller state what it means.

**Ambiguity is refused, not resolved.** Two different allowlisted channels in
one event is not a tie to break — it means nobody knows which meeting this is.
An invite link is refused for the same reason: it identifies a server, not the
channel to join.

**The planner cannot be the only thing that says no.** ``join_allowed`` is a
callable so a capability that went offline after the planner was constructed
still blocks the join. The handoff document requires MeetAI never to join
quietly when the model, consent or audio path is not ready.

This module imports no framework and no platform SDK.
"""

from __future__ import annotations

import enum
import re
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from urllib.parse import urlparse

from meetai.errors import MeetAIError

PROJECT_TIMEZONE_NAME = "Asia/Ho_Chi_Minh"
"""The operator's timezone, per the handoff document.

Recorded as a name rather than a constructed ``ZoneInfo``: nothing in this
module needs a wall clock, and resolving the name requires the ``tzdata``
package on Windows. Whatever parses calendar payloads owns that dependency.
"""


class PlannerError(MeetAIError):
    """A planner input was malformed in a way that is a caller defect."""


class JoinDecision(enum.Enum):
    """What the planner concluded."""

    JOIN = "join"
    SKIP = "skip"

    @property
    def is_join(self) -> bool:
        return self is JoinDecision.JOIN


class SkipReason(enum.Enum):
    """Why a join was refused.

    A closed enum so the reason is loggable metadata and so "the planner is
    skipping everything" is never indistinguishable from a bug.
    """

    NO_LINK = "no_link"
    AMBIGUOUS_LINK = "ambiguous_link"
    UNSUPPORTED_LINK_FORM = "unsupported_link_form"
    NOT_ALLOWLISTED = "not_allowlisted"
    CANCELLED = "cancelled"
    TOO_EARLY = "too_early"
    STALE = "stale"
    ALREADY_HANDLED = "already_handled"
    CAPABILITY_BLOCKED = "capability_blocked"


@dataclass(frozen=True, slots=True)
class CalendarEvent:
    """The slice of a calendar event the planner needs.

    Only these fields. The handoff document is explicit that the connector must
    not hand the whole calendar around, and an event's attendee list, organiser
    and free-text body beyond the link are none of the planner's business.

    ``summary`` is absent on purpose: a meeting title is content, and the
    planner would only ever log it.
    """

    event_id: str
    start: datetime
    end: datetime
    location: str = ""
    description: str = ""
    cancelled: bool = False

    def __post_init__(self) -> None:
        for name, value in (("start", self.start), ("end", self.end)):
            if value.tzinfo is None or value.utcoffset() is None:
                raise PlannerError(
                    f"{name} phai la datetime co timezone. Mot timestamp naive "
                    "khong xac dinh duoc thoi diem, va doan mui gio la cach "
                    "join sai gio."
                )
        if self.end < self.start:
            raise PlannerError("end khong duoc truoc start")


@dataclass(frozen=True, slots=True)
class ChannelRef:
    """A fully-qualified voice channel reference.

    Both ids are required. A reference that names a server but not a channel is
    not somewhere MeetAI can join, which is why invite links are refused rather
    than stored here with a blank channel.
    """

    platform: str
    guild_id: str
    channel_id: str

    def __str__(self) -> str:
        return f"{self.platform}:{self.guild_id}/{self.channel_id}"


@dataclass(frozen=True, slots=True)
class ChannelAllowlist:
    """Hosts and channels the operator has explicitly permitted.

    Empty by default, which means nothing is permitted. An allowlist that
    defaulted to "any Discord channel" would be a denylist wearing a different
    name.
    """

    allowed_hosts: frozenset[str] = frozenset()
    allowed_channels: frozenset[ChannelRef] = frozenset()

    def permits(self, ref: ChannelRef) -> bool:
        return ref in self.allowed_channels

    def permits_host(self, host: str) -> bool:
        return host.lower() in {h.lower() for h in self.allowed_hosts}


@dataclass(frozen=True, slots=True)
class JoinWindow:
    """How long before and after the start time a join is permitted.

    ``closes_after_start_seconds`` is what stops a restart from joining a
    meeting that began hours ago: the handled-set lives in memory, so after a
    restart the only thing standing between the planner and a stale event is
    this bound.
    """

    opens_before_seconds: float = 120.0
    closes_after_start_seconds: float = 300.0

    def __post_init__(self) -> None:
        if self.opens_before_seconds < 0 or self.closes_after_start_seconds < 0:
            raise PlannerError("join window khong duoc am")
        if self.closes_after_start_seconds == 0:
            raise PlannerError(
                "closes_after_start_seconds = 0 khien moi join that bai vi "
                "khong co do tre nao duoc phep"
            )


@dataclass(frozen=True, slots=True)
class PlanResult:
    """The planner's answer for one event. Metadata only, safe to log."""

    event_id: str
    decision: JoinDecision
    reason: SkipReason | None
    channel: ChannelRef | None
    idempotency_key: str

    def __post_init__(self) -> None:
        if self.decision.is_join and self.reason is not None:
            raise PlannerError("decision=join khong duoc co reason")
        if not self.decision.is_join and self.reason is None:
            raise PlannerError("decision=skip phai co reason")
        if self.decision.is_join and self.channel is None:
            raise PlannerError("decision=join phai co channel")

    def as_dict(self) -> dict[str, object]:
        return {
            "event_id": self.event_id,
            "decision": self.decision.value,
            "reason": None if self.reason is None else self.reason.value,
            "channel": None if self.channel is None else str(self.channel),
            "idempotency_key": self.idempotency_key,
        }


# A URL candidate scanner, not a validator. It finds things that look like
# http(s) URLs so each can be parsed properly; the decision about whether a
# candidate is acceptable is made by urlparse and the allowlist, never by this
# regex. Trailing punctuation is excluded because calendar bodies wrap links in
# prose.
_URL_CANDIDATE = re.compile(r"https?://[^\s<>\"'\]\)]+", re.IGNORECASE)

# Discord channel URLs: /channels/<guild>/<channel>. Numeric snowflakes only -
# "@me" is a direct-message pseudo-guild and is not a meeting.
_DISCORD_CHANNEL_PATH = re.compile(r"^/channels/(\d{5,})/(\d{5,})/?$")

# Invite forms, recognised so they can be refused with an accurate reason
# rather than falling through to "no link".
_DISCORD_INVITE_PATH = re.compile(r"^/(invite/)?[A-Za-z0-9-]{2,}/?$")
_DISCORD_INVITE_HOSTS = frozenset({"discord.gg", "discord.com", "discordapp.com"})


def extract_channel_candidates(
    text: str, *, allowed_hosts: frozenset[str]
) -> tuple[frozenset[ChannelRef], frozenset[str]]:
    """Find channel references in free text.

    Returns the distinct allowlisted-host channel references, and the set of
    rejection notes describing candidates that looked like links but were not
    usable. Both are needed: a caller must be able to tell "no link at all"
    from "a link I will not accept".

    Host comparison is on the parsed hostname, so a lookalike such as
    ``https://discord.com.evil.example/channels/1/2`` or a userinfo trick such
    as ``https://discord.com@evil.example/...`` is rejected - in the second
    case ``urlparse`` reports the host as ``evil.example``, which is the whole
    reason parsing beats substring matching here.
    """
    refs: set[ChannelRef] = set()
    notes: set[str] = set()

    for raw in _URL_CANDIDATE.findall(text):
        parsed = urlparse(raw)
        host = (parsed.hostname or "").lower()
        if not host:
            notes.add(SkipReason.UNSUPPORTED_LINK_FORM.value)
            continue
        if host not in {h.lower() for h in allowed_hosts}:
            notes.add(SkipReason.NOT_ALLOWLISTED.value)
            continue

        channel_match = _DISCORD_CHANNEL_PATH.match(parsed.path)
        if channel_match is not None:
            refs.add(
                ChannelRef(
                    platform="discord",
                    guild_id=channel_match.group(1),
                    channel_id=channel_match.group(2),
                )
            )
            continue

        if host in _DISCORD_INVITE_HOSTS and _DISCORD_INVITE_PATH.match(parsed.path):
            # An invite names a server, not the channel to join.
            notes.add(SkipReason.UNSUPPORTED_LINK_FORM.value)
            continue

        notes.add(SkipReason.UNSUPPORTED_LINK_FORM.value)

    return frozenset(refs), frozenset(notes)


@dataclass
class MeetingPlanner:
    """Decides which calendar events MeetAI may join.

    ``join_allowed`` is consulted at decision time rather than at construction,
    so a capability that goes offline - the model unloaded, consent withdrawn,
    the kill switch pulled - blocks subsequent joins without the planner having
    to be rebuilt.
    """

    allowlist: ChannelAllowlist
    window: JoinWindow
    now: Callable[[], datetime]
    join_allowed: Callable[[], bool] = lambda: True
    _handled: set[str] = field(default_factory=set, repr=False)

    @staticmethod
    def idempotency_key(event: CalendarEvent) -> str:
        """Identity of one *scheduled occurrence*.

        The start time is part of the key on purpose: a rescheduled meeting is
        a new occurrence that should be joined, while replanning the same
        occurrence must not join twice. Keying on ``event_id`` alone would make
        a moved meeting unjoinable; keying on nothing would double-join.
        """
        return f"{event.event_id}@{event.start.isoformat()}"

    @property
    def handled_keys(self) -> frozenset[str]:
        """Occurrences already claimed. Metadata, safe to log."""
        return frozenset(self._handled)

    def restore_handled(self, keys: Iterable[str]) -> None:
        """Rehydrate the claimed set, for a future operational store.

        Nothing writes this to disk today: where operational state is kept and
        for how long is an open operator decision, and the window bound already
        prevents a restart from joining a stale occurrence. The hook exists so
        that adding durability later does not require reshaping the planner.
        """
        self._handled.update(keys)

    def plan(self, event: CalendarEvent) -> PlanResult:
        """Decide without recording anything.

        Pure apart from reading the clock and the capability callable, so a
        caller can inspect a decision - in a dry-run, or in the status UI -
        without consuming the occurrence's one join.
        """
        key = self.idempotency_key(event)

        def skip(reason: SkipReason, channel: ChannelRef | None = None) -> PlanResult:
            return PlanResult(event.event_id, JoinDecision.SKIP, reason, channel, key)

        if event.cancelled:
            return skip(SkipReason.CANCELLED)
        if key in self._handled:
            return skip(SkipReason.ALREADY_HANDLED)
        if not self.join_allowed():
            return skip(SkipReason.CAPABILITY_BLOCKED)

        refs, notes = extract_channel_candidates(
            f"{event.location}\n{event.description}",
            allowed_hosts=self.allowlist.allowed_hosts,
        )
        if not refs:
            if not notes:
                return skip(SkipReason.NO_LINK)
            # Report the most specific objection available.
            if SkipReason.NOT_ALLOWLISTED.value in notes:
                return skip(SkipReason.NOT_ALLOWLISTED)
            return skip(SkipReason.UNSUPPORTED_LINK_FORM)
        if len(refs) > 1:
            # Not a tie to break: nobody knows which meeting this is.
            return skip(SkipReason.AMBIGUOUS_LINK)

        ref = next(iter(refs))
        if not self.allowlist.permits(ref):
            return skip(SkipReason.NOT_ALLOWLISTED, ref)

        moment = self._require_aware_now()
        opens = event.start.timestamp() - self.window.opens_before_seconds
        closes = event.start.timestamp() + self.window.closes_after_start_seconds
        current = moment.timestamp()
        if current < opens:
            return skip(SkipReason.TOO_EARLY, ref)
        if current > closes:
            # Covers the restart case: the claimed set is empty after a
            # restart, so this bound is what stops a long-finished meeting
            # from being joined.
            return skip(SkipReason.STALE, ref)

        return PlanResult(event.event_id, JoinDecision.JOIN, None, ref, key)

    def claim(self, result: PlanResult) -> bool:
        """Record that a join decision was acted on.

        Returns whether this call was the first to claim it. Separate from
        :meth:`plan` so that deciding and consuming are distinct events - a
        join that fails to connect can be left unclaimed and retried inside the
        window.
        """
        if not result.decision.is_join:
            return False
        if result.idempotency_key in self._handled:
            return False
        self._handled.add(result.idempotency_key)
        return True

    def plan_and_claim(self, event: CalendarEvent) -> PlanResult:
        """Decide and consume in one step. The normal operating path."""
        result = self.plan(event)
        if result.decision.is_join:
            self.claim(result)
        return result

    def plan_all(self, events: Sequence[CalendarEvent]) -> tuple[PlanResult, ...]:
        """Plan several events, claiming each join as it is decided.

        Events are processed in start order so that when two events point at
        the same occurrence key, the earlier one wins deterministically rather
        than depending on the order the calendar returned them.
        """
        ordered = sorted(events, key=lambda e: (e.start, e.event_id))
        return tuple(self.plan_and_claim(event) for event in ordered)

    def _require_aware_now(self) -> datetime:
        moment = self.now()
        if moment.tzinfo is None or moment.utcoffset() is None:
            raise PlannerError(
                "clock phai tra ve datetime co timezone; so sanh voi mot "
                "timestamp naive la so sanh khong xac dinh"
            )
        return moment
