"""Tests for the meeting planner.

Scope under test is the one recorded in PROJECT_STATE section 6 for S1.4:
allowlisted channel references only, a configurable join window, idempotency,
and no auto-join of a stale event after a restart. Nothing beyond that.

The lookalike-host cases are the ones worth reading: a planner that matched
hosts by substring would join a channel on an attacker's domain, and that is a
mistake that looks fine in a happy-path test.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta, timezone

import pytest

from meetai.planner import (
    CalendarEvent,
    ChannelAllowlist,
    ChannelRef,
    JoinDecision,
    JoinWindow,
    MeetingPlanner,
    PlannerError,
    PlanResult,
    SkipReason,
    extract_channel_candidates,
)

ICT = timezone(timedelta(hours=7))
"""A fixed +07:00 for fixtures.

Not `ZoneInfo("Asia/Ho_Chi_Minh")`: Windows ships no IANA database, so that
would raise here unless tzdata were installed. Fixtures only need a definite
instant, which a fixed offset provides, and the planner refuses naive input
rather than resolving zone names itself.
"""

ALLOWED_HOST = "discord.com"
GUILD = "123456789012345678"
CHANNEL = "987654321098765432"
ALLOWED_REF = ChannelRef("discord", GUILD, CHANNEL)
START = datetime(2026, 10, 7, 14, 0, tzinfo=ICT)


def channel_url(
    guild: str = GUILD, channel: str = CHANNEL, host: str = ALLOWED_HOST
) -> str:
    return f"https://{host}/channels/{guild}/{channel}"


def event(
    *,
    event_id: str = "evt-1",
    start: datetime = START,
    location: str = "",
    description: str = "",
    cancelled: bool = False,
) -> CalendarEvent:
    return CalendarEvent(
        event_id=event_id,
        start=start,
        end=start + timedelta(hours=1),
        location=location,
        description=description,
        cancelled=cancelled,
    )


class Clock:
    def __init__(self, moment: datetime) -> None:
        self.moment = moment

    def __call__(self) -> datetime:
        return self.moment

    def advance(self, **kwargs: float) -> None:
        self.moment += timedelta(**kwargs)


def make_planner(
    *,
    at: datetime | None = None,
    allowlist: ChannelAllowlist | None = None,
    window: JoinWindow | None = None,
    join_allowed: bool = True,
) -> tuple[MeetingPlanner, Clock]:
    clock = Clock(at if at is not None else START)
    planner = MeetingPlanner(
        allowlist=allowlist
        or ChannelAllowlist(
            allowed_hosts=frozenset({ALLOWED_HOST}),
            allowed_channels=frozenset({ALLOWED_REF}),
        ),
        window=window or JoinWindow(),
        now=clock,
        join_allowed=lambda: join_allowed,
    )
    return planner, clock


class TestTimestampDiscipline:
    def test_naive_start_is_refused(self) -> None:
        """A naive timestamp does not identify an instant."""
        with pytest.raises(PlannerError, match="timezone"):
            CalendarEvent(
                event_id="e",
                start=datetime(2026, 10, 7, 14, 0),
                end=datetime(2026, 10, 7, 15, 0, tzinfo=ICT),
            )

    def test_naive_end_is_refused(self) -> None:
        with pytest.raises(PlannerError, match="timezone"):
            CalendarEvent(
                event_id="e",
                start=datetime(2026, 10, 7, 14, 0, tzinfo=ICT),
                end=datetime(2026, 10, 7, 15, 0),
            )

    def test_end_before_start_is_refused(self) -> None:
        with pytest.raises(PlannerError, match="end khong duoc truoc start"):
            CalendarEvent(
                event_id="e",
                start=START,
                end=START - timedelta(hours=1),
            )

    def test_naive_clock_is_refused(self) -> None:
        planner = MeetingPlanner(
            allowlist=ChannelAllowlist(
                frozenset({ALLOWED_HOST}), frozenset({ALLOWED_REF})
            ),
            window=JoinWindow(),
            now=lambda: datetime(2026, 10, 7, 14, 0),
        )
        with pytest.raises(PlannerError, match="clock phai tra ve"):
            planner.plan(event(location=channel_url()))

    def test_offsets_are_compared_as_instants(self) -> None:
        """The same instant expressed in two offsets must behave identically."""
        planner, _ = make_planner(at=START.astimezone(UTC))
        result = planner.plan(event(location=channel_url()))
        assert result.decision is JoinDecision.JOIN


class TestLinkExtraction:
    def test_link_in_location(self) -> None:
        planner, _ = make_planner()
        assert planner.plan(event(location=channel_url())).decision is JoinDecision.JOIN

    def test_link_in_description(self) -> None:
        """The handoff document says the link may be in either field."""
        planner, _ = make_planner()
        result = planner.plan(event(description=f"Hop nhom: {channel_url()}"))
        assert result.decision is JoinDecision.JOIN

    def test_link_surrounded_by_prose(self) -> None:
        planner, _ = make_planner()
        result = planner.plan(
            event(description=f"Tham gia tai ({channel_url()}) truoc 14h nhe.")
        )
        assert result.decision is JoinDecision.JOIN
        assert result.channel == ALLOWED_REF

    def test_no_link_at_all(self) -> None:
        planner, _ = make_planner()
        result = planner.plan(event(description="Hop nhom luc 2h chieu"))
        assert result.reason is SkipReason.NO_LINK

    def test_no_link_is_distinct_from_rejected_link(self) -> None:
        """An operator must be able to tell "no link" from "a link I refuse"."""
        planner, _ = make_planner()
        assert planner.plan(event(description="khong co gi")).reason is SkipReason.NO_LINK
        assert (
            planner.plan(event(description="https://zoom.us/j/123")).reason
            is SkipReason.NOT_ALLOWLISTED
        )

    def test_channel_ids_must_be_snowflakes(self) -> None:
        planner, _ = make_planner()
        result = planner.plan(event(location=f"https://{ALLOWED_HOST}/channels/abc/def"))
        assert result.reason is SkipReason.UNSUPPORTED_LINK_FORM

    def test_direct_message_pseudo_guild_is_refused(self) -> None:
        """`@me` is a DM, not a meeting."""
        planner, _ = make_planner()
        result = planner.plan(
            event(location=f"https://{ALLOWED_HOST}/channels/@me/{CHANNEL}")
        )
        assert result.reason is SkipReason.UNSUPPORTED_LINK_FORM

    def test_invite_link_is_refused_with_an_accurate_reason(self) -> None:
        """An invite names a server, not the channel to join."""
        planner, _ = make_planner(
            allowlist=ChannelAllowlist(
                allowed_hosts=frozenset({"discord.gg"}),
                allowed_channels=frozenset({ALLOWED_REF}),
            )
        )
        result = planner.plan(event(location="https://discord.gg/abcdef"))
        assert result.reason is SkipReason.UNSUPPORTED_LINK_FORM


class TestLookalikeHosts:
    """Substring host matching would join a channel on an attacker's domain."""

    @pytest.mark.parametrize(
        "host",
        [
            "discord.com.evil.example",
            "notdiscord.com",
            "discord.com.co",
            "xn--discord-vn0a.com",
            "evil.example",
        ],
    )
    def test_lookalike_host_is_not_allowlisted(self, host: str) -> None:
        planner, _ = make_planner()
        result = planner.plan(event(location=channel_url(host=host)))
        assert result.reason is SkipReason.NOT_ALLOWLISTED, host

    def test_userinfo_trick_resolves_to_the_real_host(self) -> None:
        """`https://discord.com@evil.example/...` has hostname evil.example.

        This is exactly why hosts are compared on the parsed hostname rather
        than by searching the raw string.
        """
        planner, _ = make_planner()
        result = planner.plan(
            event(location=f"https://discord.com@evil.example/channels/{GUILD}/{CHANNEL}")
        )
        assert result.reason is SkipReason.NOT_ALLOWLISTED

    def test_host_matching_is_case_insensitive(self) -> None:
        planner, _ = make_planner()
        result = planner.plan(event(location=channel_url(host="DISCORD.COM")))
        assert result.decision is JoinDecision.JOIN

    def test_port_bearing_host_still_resolves(self) -> None:
        refs, _ = extract_channel_candidates(
            f"https://{ALLOWED_HOST}:443/channels/{GUILD}/{CHANNEL}",
            allowed_hosts=frozenset({ALLOWED_HOST}),
        )
        assert refs == frozenset({ALLOWED_REF})


class TestAllowlist:
    def test_empty_allowlist_permits_nothing(self) -> None:
        """An allowlist that defaulted to permissive would be a denylist."""
        planner, _ = make_planner(allowlist=ChannelAllowlist())
        result = planner.plan(event(location=channel_url()))
        assert result.reason is SkipReason.NOT_ALLOWLISTED

    def test_allowlisted_host_but_unlisted_channel_is_refused(self) -> None:
        planner, _ = make_planner(
            allowlist=ChannelAllowlist(
                allowed_hosts=frozenset({ALLOWED_HOST}), allowed_channels=frozenset()
            )
        )
        result = planner.plan(event(location=channel_url()))
        assert result.reason is SkipReason.NOT_ALLOWLISTED
        assert result.channel == ALLOWED_REF  # reported, so the operator can add it

    def test_different_channel_in_allowlisted_guild_is_refused(self) -> None:
        planner, _ = make_planner()
        result = planner.plan(event(location=channel_url(channel="111111111111111111")))
        assert result.reason is SkipReason.NOT_ALLOWLISTED


class TestAmbiguity:
    def test_two_different_allowlisted_channels_is_refused(self) -> None:
        """Not a tie to break: nobody knows which meeting this is."""
        other = ChannelRef("discord", GUILD, "222222222222222222")
        planner, _ = make_planner(
            allowlist=ChannelAllowlist(
                allowed_hosts=frozenset({ALLOWED_HOST}),
                allowed_channels=frozenset({ALLOWED_REF, other}),
            )
        )
        result = planner.plan(
            event(
                location=channel_url(),
                description=channel_url(channel=other.channel_id),
            )
        )
        assert result.reason is SkipReason.AMBIGUOUS_LINK

    def test_the_same_link_twice_is_not_ambiguous(self) -> None:
        planner, _ = make_planner()
        result = planner.plan(
            event(location=channel_url(), description=f"nhac lai: {channel_url()}")
        )
        assert result.decision is JoinDecision.JOIN


class TestJoinWindow:
    def test_too_early_is_refused(self) -> None:
        planner, _ = make_planner(at=START - timedelta(minutes=10))
        assert planner.plan(event(location=channel_url())).reason is SkipReason.TOO_EARLY

    def test_window_opens_before_start(self) -> None:
        planner, _ = make_planner(
            at=START - timedelta(seconds=119), window=JoinWindow(opens_before_seconds=120)
        )
        assert planner.plan(event(location=channel_url())).decision is JoinDecision.JOIN

    def test_window_closes_after_start(self) -> None:
        planner, _ = make_planner(
            at=START + timedelta(seconds=299),
            window=JoinWindow(closes_after_start_seconds=300),
        )
        assert planner.plan(event(location=channel_url())).decision is JoinDecision.JOIN

    def test_past_the_window_is_stale(self) -> None:
        planner, _ = make_planner(
            at=START + timedelta(seconds=301),
            window=JoinWindow(closes_after_start_seconds=300),
        )
        assert planner.plan(event(location=channel_url())).reason is SkipReason.STALE

    def test_window_is_configurable(self) -> None:
        planner, _ = make_planner(
            at=START - timedelta(minutes=30),
            window=JoinWindow(opens_before_seconds=3600),
        )
        assert planner.plan(event(location=channel_url())).decision is JoinDecision.JOIN

    def test_negative_window_is_refused(self) -> None:
        with pytest.raises(PlannerError, match="khong duoc am"):
            JoinWindow(opens_before_seconds=-1)

    def test_zero_trailing_window_is_refused(self) -> None:
        """It would make every join fail, which reads as a bug not a policy."""
        with pytest.raises(PlannerError, match="closes_after_start_seconds"):
            JoinWindow(closes_after_start_seconds=0)


class TestStaleAfterRestart:
    """The requirement stated in the handoff document: no auto-join of an old
    event after a restart."""

    def test_a_fresh_planner_does_not_join_a_long_finished_meeting(self) -> None:
        """A restart empties the claimed set, so the window is the only guard."""
        yesterday = START - timedelta(days=1)
        planner, _ = make_planner(at=START)
        result = planner.plan(event(start=yesterday, location=channel_url()))
        assert result.reason is SkipReason.STALE
        assert planner.handled_keys == frozenset()

    def test_a_fresh_planner_still_joins_an_event_inside_its_window(self) -> None:
        """Staleness is about age, not about having restarted."""
        planner, _ = make_planner(at=START + timedelta(seconds=10))
        assert planner.plan(event(location=channel_url())).decision is JoinDecision.JOIN

    def test_restored_keys_suppress_a_rejoin(self) -> None:
        planner, _ = make_planner()
        key = MeetingPlanner.idempotency_key(event())
        planner.restore_handled([key])
        assert (
            planner.plan(event(location=channel_url())).reason
            is SkipReason.ALREADY_HANDLED
        )


class TestIdempotency:
    def test_planning_twice_joins_once(self) -> None:
        planner, _ = make_planner()
        first = planner.plan_and_claim(event(location=channel_url()))
        second = planner.plan_and_claim(event(location=channel_url()))
        assert first.decision is JoinDecision.JOIN
        assert second.reason is SkipReason.ALREADY_HANDLED

    def test_plan_alone_does_not_consume(self) -> None:
        """A dry run must not spend the occurrence's one join."""
        planner, _ = make_planner()
        planner.plan(event(location=channel_url()))
        planner.plan(event(location=channel_url()))
        assert (
            planner.plan_and_claim(event(location=channel_url())).decision
            is JoinDecision.JOIN
        )

    def test_an_unclaimed_join_can_be_retried(self) -> None:
        """A join that failed to connect should be retryable inside the window."""
        planner, clock = make_planner()
        first = planner.plan(event(location=channel_url()))
        assert first.decision is JoinDecision.JOIN
        # Not claimed: the connection attempt failed.
        clock.advance(seconds=30)
        assert planner.plan(event(location=channel_url())).decision is JoinDecision.JOIN

    def test_claim_returns_false_the_second_time(self) -> None:
        planner, _ = make_planner()
        result = planner.plan(event(location=channel_url()))
        assert planner.claim(result) is True
        assert planner.claim(result) is False

    def test_claiming_a_skip_does_nothing(self) -> None:
        planner, _ = make_planner()
        skipped = planner.plan(event(description="no link"))
        assert planner.claim(skipped) is False
        assert planner.handled_keys == frozenset()

    def test_rescheduling_produces_a_new_occurrence(self) -> None:
        """A moved meeting must still be joinable.

        Keying on event_id alone would make a rescheduled meeting unjoinable;
        keying on nothing would double-join.
        """
        planner, clock = make_planner()
        planner.plan_and_claim(event(location=channel_url()))

        moved = START + timedelta(hours=2)
        clock.moment = moved
        result = planner.plan_and_claim(event(start=moved, location=channel_url()))
        assert result.decision is JoinDecision.JOIN

    def test_distinct_events_do_not_share_a_claim(self) -> None:
        planner, _ = make_planner()
        planner.plan_and_claim(event(event_id="a", location=channel_url()))
        result = planner.plan_and_claim(event(event_id="b", location=channel_url()))
        assert result.decision is JoinDecision.JOIN


class TestCancellationAndCapability:
    def test_cancelled_event_is_refused(self) -> None:
        planner, _ = make_planner()
        assert (
            planner.plan(event(location=channel_url(), cancelled=True)).reason
            is SkipReason.CANCELLED
        )

    def test_cancellation_is_checked_before_anything_else(self) -> None:
        """A cancelled event with no link should report the cancellation."""
        planner, _ = make_planner(at=START - timedelta(days=5))
        result = planner.plan(event(cancelled=True))
        assert result.reason is SkipReason.CANCELLED

    def test_capability_block_refuses_the_join(self) -> None:
        """MeetAI must never join quietly when the local stack is not ready."""
        planner, _ = make_planner(join_allowed=False)
        assert (
            planner.plan(event(location=channel_url())).reason
            is SkipReason.CAPABILITY_BLOCKED
        )

    def test_capability_is_read_at_decision_time(self) -> None:
        """A capability that goes offline later must block subsequent joins."""
        allowed = True
        clock = Clock(START)
        planner = MeetingPlanner(
            allowlist=ChannelAllowlist(
                frozenset({ALLOWED_HOST}), frozenset({ALLOWED_REF})
            ),
            window=JoinWindow(),
            now=clock,
            join_allowed=lambda: allowed,
        )
        assert planner.plan(event(location=channel_url())).decision is JoinDecision.JOIN
        allowed = False
        assert (
            planner.plan(event(location=channel_url())).reason
            is SkipReason.CAPABILITY_BLOCKED
        )

    def test_capability_block_does_not_consume_the_occurrence(self) -> None:
        """Otherwise a transient outage would silently skip the meeting."""
        allowed = False
        clock = Clock(START)
        planner = MeetingPlanner(
            allowlist=ChannelAllowlist(
                frozenset({ALLOWED_HOST}), frozenset({ALLOWED_REF})
            ),
            window=JoinWindow(),
            now=clock,
            join_allowed=lambda: allowed,
        )
        planner.plan_and_claim(event(location=channel_url()))
        allowed = True
        assert (
            planner.plan_and_claim(event(location=channel_url())).decision
            is JoinDecision.JOIN
        )


class TestResultShape:
    def test_join_result_carries_a_channel_and_no_reason(self) -> None:
        planner, _ = make_planner()
        result = planner.plan(event(location=channel_url()))
        assert result.channel == ALLOWED_REF
        assert result.reason is None

    def test_join_with_a_reason_is_refused(self) -> None:
        with pytest.raises(PlannerError, match="khong duoc co reason"):
            PlanResult("e", JoinDecision.JOIN, SkipReason.STALE, ALLOWED_REF, "k")

    def test_skip_without_a_reason_is_refused(self) -> None:
        with pytest.raises(PlannerError, match="phai co reason"):
            PlanResult("e", JoinDecision.SKIP, None, None, "k")

    def test_join_without_a_channel_is_refused(self) -> None:
        with pytest.raises(PlannerError, match="phai co channel"):
            PlanResult("e", JoinDecision.JOIN, None, None, "k")

    def test_as_dict_is_metadata_only(self) -> None:
        """The result is logged, so it must carry no meeting content."""
        planner, _ = make_planner()
        secret_title = "NOI-DUNG-LICH-KHONG-DUOC-LOG"
        result = planner.plan(
            event(location=channel_url(), description=f"{secret_title} {channel_url()}")
        )
        assert secret_title not in str(result.as_dict())

    def test_calendar_event_has_no_summary_field(self) -> None:
        """A meeting title is content; the planner would only ever log it."""
        from dataclasses import fields

        names = {f.name for f in fields(CalendarEvent)}
        assert names == {
            "event_id",
            "start",
            "end",
            "location",
            "description",
            "cancelled",
        }


class TestPlanAll:
    def test_events_are_processed_in_start_order(self) -> None:
        """Deterministic ordering, not whatever order the calendar returned."""
        planner, _ = make_planner(at=START)
        later = event(
            event_id="later", start=START + timedelta(seconds=60), location=channel_url()
        )
        earlier = event(event_id="earlier", start=START, location=channel_url())
        results = planner.plan_all([later, earlier])
        assert [r.event_id for r in results] == ["earlier", "later"]

    def test_each_join_is_claimed(self) -> None:
        planner, _ = make_planner()
        planner.plan_all([event(location=channel_url())])
        again = planner.plan_all([event(location=channel_url())])
        assert again[0].reason is SkipReason.ALREADY_HANDLED

    def test_empty_input_is_fine(self) -> None:
        planner, _ = make_planner()
        assert planner.plan_all([]) == ()


class TestTimezoneConstant:
    def test_timezone_is_recorded_as_a_name(self) -> None:
        """Recorded, not constructed: resolving it needs tzdata on Windows."""
        from meetai.planner import PROJECT_TIMEZONE_NAME

        assert PROJECT_TIMEZONE_NAME == "Asia/Ho_Chi_Minh"

    def test_planner_imports_no_timezone_database(self) -> None:
        """Zone handling belongs to whatever parses calendar payloads.

        Checks the import graph rather than the file text: the module's own
        docstring discusses `ZoneInfo` to explain why it is absent, and a
        substring search would match the explanation.
        """
        import ast
        from pathlib import Path

        source = (
            Path(__file__).resolve().parent.parent / "src" / "meetai" / "planner.py"
        ).read_text(encoding="utf-8")
        imported: set[str] = set()
        for node in ast.walk(ast.parse(source)):
            if isinstance(node, ast.Import):
                imported.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module.split(".")[0])

        assert "zoneinfo" not in imported
        assert "tzdata" not in imported
