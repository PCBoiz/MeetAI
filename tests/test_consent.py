"""Tests for the consent state machine.

The transition table is covered exhaustively rather than sampled: for a privacy
gate, the interesting cases are the ones nobody thought to write by hand, and a
sampled table hides exactly those.
"""

from __future__ import annotations

import itertools

import pytest

from meetai.consent import (
    ConsentKey,
    ConsentLedger,
    ConsentState,
    ConsentTransitionError,
    StaleConsentError,
)
from meetai.policy import ConsentScope

SESSION = "sess-1"
ALICE = "participant-handle-a"
BOB = "participant-handle-b"
NOTICE = "notice-v1"


class Clock:
    """Injected clock, so expiry is testable without sleeping."""

    def __init__(self, start: float = 1000.0) -> None:
        self.t = start

    def __call__(self) -> float:
        return self.t

    def advance(self, seconds: float) -> None:
        self.t += seconds


@pytest.fixture
def clock() -> Clock:
    return Clock()


@pytest.fixture
def ledger(clock: Clock) -> ConsentLedger:
    return ConsentLedger(session_id=SESSION, policy_version="p1", now=clock)


def key(
    participant: str = ALICE,
    scope: ConsentScope = ConsentScope.LIVE_MEDIA,
    notice: str = NOTICE,
    session: str = SESSION,
) -> ConsentKey:
    return ConsentKey(session, participant, scope, notice)


class TestDefaultDeny:
    def test_absent_key_is_unknown(self, ledger: ConsentLedger) -> None:
        assert ledger.state_of(key()) is ConsentState.UNKNOWN

    def test_absent_key_grants_nothing(self, ledger: ConsentLedger) -> None:
        assert ledger.is_granted(key()) is False

    def test_announced_grants_nothing(self, ledger: ConsentLedger) -> None:
        """Showing a notice is not consent."""
        ledger.announce(key())
        assert ledger.is_granted(key()) is False

    @pytest.mark.parametrize("state", list(ConsentState))
    def test_only_consented_grants_access(self, state: ConsentState) -> None:
        """A state added to the enum later must be denied by default."""
        assert state.grants_access is (state is ConsentState.CONSENTED)

    def test_no_scope_granted_initially(self, ledger: ConsentLedger) -> None:
        assert ledger.granted_scopes(ALICE, NOTICE) == frozenset()


class TestHappyPath:
    def test_announce_then_grant(self, ledger: ConsentLedger) -> None:
        ledger.announce(key())
        ledger.grant(key(), generation=ledger.generation)
        assert ledger.is_granted(key()) is True

    def test_grant_is_scope_specific(self, ledger: ConsentLedger) -> None:
        """Granting one scope must not grant another."""
        live = key(scope=ConsentScope.LIVE_MEDIA)
        transcript = key(scope=ConsentScope.DURABLE_TRANSCRIPT)
        ledger.announce(live)
        ledger.grant(live, generation=ledger.generation)
        assert ledger.is_granted(live) is True
        assert ledger.is_granted(transcript) is False

    def test_grant_is_participant_specific(self, ledger: ConsentLedger) -> None:
        a = key(participant=ALICE)
        b = key(participant=BOB)
        ledger.announce(a)
        ledger.grant(a, generation=ledger.generation)
        assert ledger.is_granted(b) is False

    def test_grant_is_notice_version_specific(self, ledger: ConsentLedger) -> None:
        """A new notice version is a new question, not an inherited answer."""
        old = key(notice="notice-v1")
        new = key(notice="notice-v2")
        ledger.announce(old)
        ledger.grant(old, generation=ledger.generation)
        assert ledger.is_granted(new) is False

    def test_granted_scopes_reports_exactly_what_was_granted(
        self, ledger: ConsentLedger
    ) -> None:
        for scope in (ConsentScope.LIVE_MEDIA, ConsentScope.REPLY_JOURNAL):
            k = key(scope=scope)
            ledger.announce(k)
            ledger.grant(k, generation=ledger.generation)
        assert ledger.granted_scopes(ALICE, NOTICE) == frozenset(
            {ConsentScope.LIVE_MEDIA, ConsentScope.REPLY_JOURNAL}
        )

    def test_announce_is_idempotent(self, ledger: ConsentLedger) -> None:
        ledger.announce(key())
        ledger.announce(key())
        assert ledger.state_of(key()) is ConsentState.ANNOUNCED

    def test_grant_is_idempotent(self, ledger: ConsentLedger) -> None:
        ledger.announce(key())
        ledger.grant(key(), generation=ledger.generation)
        ledger.grant(key(), generation=ledger.generation)
        assert ledger.is_granted(key()) is True


class TestGrantRequiresAnnouncement:
    def test_grant_without_announce_is_refused(self, ledger: ConsentLedger) -> None:
        """A grant for a notice nobody saw is an assumption, not consent."""
        with pytest.raises(ConsentTransitionError, match="chua announce"):
            ledger.grant(key(), generation=ledger.generation)


class TestTerminalStates:
    @pytest.mark.parametrize(
        "state", [ConsentState.DECLINED, ConsentState.REVOKED, ConsentState.EXPIRED]
    )
    def test_terminal_flag(self, state: ConsentState) -> None:
        assert state.is_terminal is True

    @pytest.mark.parametrize(
        "state", [ConsentState.UNKNOWN, ConsentState.ANNOUNCED, ConsentState.CONSENTED]
    )
    def test_non_terminal_flag(self, state: ConsentState) -> None:
        assert state.is_terminal is False

    def test_declined_cannot_be_granted(self, ledger: ConsentLedger) -> None:
        """A retry loop must not re-ask someone who refused."""
        ledger.decline(key(), generation=ledger.generation)
        with pytest.raises(ConsentTransitionError, match="trang thai cuoi"):
            ledger.grant(key(), generation=ledger.generation)

    def test_declined_cannot_be_announced_again(self, ledger: ConsentLedger) -> None:
        ledger.decline(key(), generation=ledger.generation)
        with pytest.raises(ConsentTransitionError, match="trang thai cuoi"):
            ledger.announce(key())

    def test_revoked_cannot_be_granted(self, ledger: ConsentLedger) -> None:
        ledger.announce(key())
        ledger.grant(key(), generation=ledger.generation)
        ledger.revoke(key())
        with pytest.raises(ConsentTransitionError, match="trang thai cuoi"):
            ledger.grant(key(), generation=ledger.generation)

    def test_expired_cannot_be_granted(self, ledger: ConsentLedger, clock: Clock) -> None:
        ledger.grant_ttl_seconds = 60.0
        ledger.announce(key())
        ledger.grant(key(), generation=ledger.generation)
        clock.advance(61.0)
        with pytest.raises(ConsentTransitionError, match="trang thai cuoi"):
            ledger.grant(key(), generation=ledger.generation)

    def test_decline_is_idempotent(self, ledger: ConsentLedger) -> None:
        ledger.decline(key(), generation=ledger.generation)
        ledger.decline(key(), generation=ledger.generation)
        assert ledger.state_of(key()) is ConsentState.DECLINED

    def test_revoke_is_idempotent(self, ledger: ConsentLedger) -> None:
        ledger.announce(key())
        ledger.grant(key(), generation=ledger.generation)
        before = ledger.generation
        ledger.revoke(key())
        after_first = ledger.generation
        ledger.revoke(key())
        assert ledger.generation == after_first > before


class TestDeclineFromUnknown:
    def test_decline_without_announce_is_allowed(self, ledger: ConsentLedger) -> None:
        """A refusal before the notice rendered is still a refusal."""
        ledger.decline(key(), generation=ledger.generation)
        assert ledger.state_of(key()) is ConsentState.DECLINED


class TestRevocation:
    def test_revoke_requires_a_grant(self, ledger: ConsentLedger) -> None:
        ledger.announce(key())
        with pytest.raises(ConsentTransitionError, match="chi co the revoke"):
            ledger.revoke(key())

    def test_revoke_bumps_the_generation(self, ledger: ConsentLedger) -> None:
        ledger.announce(key())
        ledger.grant(key(), generation=ledger.generation)
        before = ledger.generation
        ledger.revoke(key())
        assert ledger.generation == before + 1

    def test_revoke_closes_the_gate_for_in_flight_work(
        self, ledger: ConsentLedger
    ) -> None:
        """The revoke race: work that started before a revocation must not finish.

        A task captures the generation when it starts. After a revocation its
        captured generation is stale, so its pre-emit check fails - the gate
        closes before anything is cancelled.
        """
        ledger.announce(key())
        ledger.grant(key(), generation=ledger.generation)

        captured = ledger.generation
        assert ledger.is_granted(key(), generation=captured) is True

        ledger.revoke(key())

        assert ledger.is_granted(key(), generation=captured) is False

    def test_another_participants_revoke_also_invalidates_in_flight_work(
        self, ledger: ConsentLedger
    ) -> None:
        """One withdrawal invalidates the whole session's outstanding work.

        Bob revoking must stop a pipeline that is mid-way through Alice's
        audio, because that pipeline's output could contain Bob.
        """
        a, b = key(participant=ALICE), key(participant=BOB)
        for k in (a, b):
            ledger.announce(k)
            ledger.grant(k, generation=ledger.generation)

        captured = ledger.generation
        ledger.revoke(b)

        assert ledger.state_of(a) is ConsentState.CONSENTED
        assert ledger.is_granted(a, generation=captured) is False
        assert ledger.is_granted(a) is True  # the key itself is still granted

    def test_revoke_all_uses_one_generation_bump(self, ledger: ConsentLedger) -> None:
        """A reader must not be able to observe a half-revoked participant."""
        for scope in ConsentScope:
            k = key(scope=scope)
            ledger.announce(k)
            ledger.grant(k, generation=ledger.generation)

        before = ledger.generation
        revoked = ledger.revoke_all(ALICE)

        assert len(revoked) == len(ConsentScope)
        assert ledger.generation == before + 1
        assert ledger.granted_scopes(ALICE, NOTICE) == frozenset()

    def test_revoke_all_on_nothing_does_not_bump(self, ledger: ConsentLedger) -> None:
        before = ledger.generation
        assert ledger.revoke_all(ALICE) == ()
        assert ledger.generation == before

    def test_revoke_all_leaves_other_participants_granted(
        self, ledger: ConsentLedger
    ) -> None:
        for participant in (ALICE, BOB):
            k = key(participant=participant)
            ledger.announce(k)
            ledger.grant(k, generation=ledger.generation)

        ledger.revoke_all(ALICE)
        assert ledger.is_granted(key(participant=BOB)) is True
        assert ledger.is_granted(key(participant=ALICE)) is False

    def test_revoke_does_not_require_a_current_generation(
        self, ledger: ConsentLedger
    ) -> None:
        """A withdrawal is always honoured.

        Refusing a revocation because it quoted a stale generation would be the
        one fail-open this module must not have.
        """
        a, b = key(participant=ALICE), key(participant=BOB)
        for k in (a, b):
            ledger.announce(k)
            ledger.grant(k, generation=ledger.generation)

        ledger.revoke(b)  # generation moves on
        ledger.revoke(a)  # must still succeed
        assert ledger.state_of(a) is ConsentState.REVOKED


class TestStaleClicks:
    def test_stale_grant_is_refused(self, ledger: ConsentLedger) -> None:
        """A click already in flight when someone revoked must not apply."""
        a, b = key(participant=ALICE), key(participant=BOB)
        ledger.announce(a)
        ledger.announce(b)
        ledger.grant(b, generation=ledger.generation)

        notice_generation = ledger.generation
        ledger.revoke(b)  # generation moves on

        with pytest.raises(StaleConsentError, match="generation da cu"):
            ledger.grant(a, generation=notice_generation)
        assert ledger.is_granted(a) is False

    def test_stale_decline_is_refused(self, ledger: ConsentLedger) -> None:
        """Symmetry matters: a stale decision of either kind is stale.

        A stale decline is harmless in outcome but accepting it would mean the
        generation check is advisory, and the next author would reasonably
        conclude the same about grant.
        """
        a, b = key(participant=ALICE), key(participant=BOB)
        ledger.announce(b)
        ledger.grant(b, generation=ledger.generation)
        stale = ledger.generation
        ledger.revoke(b)

        with pytest.raises(StaleConsentError):
            ledger.decline(a, generation=stale)

    def test_future_generation_is_also_refused(self, ledger: ConsentLedger) -> None:
        ledger.announce(key())
        with pytest.raises(StaleConsentError):
            ledger.grant(key(), generation=ledger.generation + 5)

    def test_revoked_grant_cannot_be_resurrected_by_a_fresh_click(
        self, ledger: ConsentLedger
    ) -> None:
        """Even a correctly-generationed click cannot undo a revocation."""
        ledger.announce(key())
        ledger.grant(key(), generation=ledger.generation)
        ledger.revoke(key())
        with pytest.raises(ConsentTransitionError, match="trang thai cuoi"):
            ledger.grant(key(), generation=ledger.generation)


class TestExpiry:
    def test_grant_without_ttl_does_not_expire(
        self, ledger: ConsentLedger, clock: Clock
    ) -> None:
        ledger.announce(key())
        ledger.grant(key(), generation=ledger.generation)
        clock.advance(10_000.0)
        assert ledger.is_granted(key()) is True

    def test_grant_expires_after_ttl(self, clock: Clock) -> None:
        ledger = ConsentLedger(SESSION, "p1", clock, grant_ttl_seconds=60.0)
        ledger.announce(key())
        ledger.grant(key(), generation=ledger.generation)

        clock.advance(59.0)
        assert ledger.is_granted(key()) is True

        clock.advance(2.0)
        assert ledger.is_granted(key()) is False
        assert ledger.state_of(key()) is ConsentState.EXPIRED

    def test_reading_expiry_does_not_mutate(self, clock: Clock) -> None:
        """A read must not change what a later read returns."""
        ledger = ConsentLedger(SESSION, "p1", clock, grant_ttl_seconds=10.0)
        ledger.announce(key())
        ledger.grant(key(), generation=ledger.generation)
        receipts_before = len(ledger.receipts)

        clock.advance(11.0)
        ledger.state_of(key())
        ledger.state_of(key())

        assert len(ledger.receipts) == receipts_before

    def test_sweep_makes_expiry_durable(self, clock: Clock) -> None:
        ledger = ConsentLedger(SESSION, "p1", clock, grant_ttl_seconds=10.0)
        ledger.announce(key())
        ledger.grant(key(), generation=ledger.generation)
        clock.advance(11.0)

        swept = ledger.sweep_expired()
        assert len(swept) == 1
        assert swept[0].state is ConsentState.EXPIRED

    def test_sweep_does_not_bump_the_generation(self, clock: Clock) -> None:
        """Expiry is not an instruction to stop in-flight work.

        Unlike a revocation, nobody withdrew anything; is_granted already
        refuses the expired key on its own.
        """
        ledger = ConsentLedger(SESSION, "p1", clock, grant_ttl_seconds=10.0)
        ledger.announce(key())
        ledger.grant(key(), generation=ledger.generation)
        before = ledger.generation
        clock.advance(11.0)
        ledger.sweep_expired()
        assert ledger.generation == before

    def test_sweep_leaves_live_grants_alone(self, clock: Clock) -> None:
        ledger = ConsentLedger(SESSION, "p1", clock, grant_ttl_seconds=100.0)
        ledger.announce(key())
        ledger.grant(key(), generation=ledger.generation)
        clock.advance(10.0)
        assert ledger.sweep_expired() == ()
        assert ledger.is_granted(key()) is True


class TestSessionIsolation:
    def test_key_from_another_session_is_refused(self, ledger: ConsentLedger) -> None:
        """Consent is never inherited across sessions."""
        other = key(session="sess-2")
        with pytest.raises(ConsentTransitionError, match="khong duoc ke thua"):
            ledger.state_of(other)

    def test_grant_from_another_session_is_refused(self, ledger: ConsentLedger) -> None:
        other = key(session="sess-2")
        with pytest.raises(ConsentTransitionError, match="khong duoc ke thua"):
            ledger.grant(other, generation=ledger.generation)

    def test_a_new_ledger_starts_empty(self, clock: Clock) -> None:
        first = ConsentLedger(SESSION, "p1", clock)
        first.announce(key())
        first.grant(key(), generation=first.generation)

        second = ConsentLedger("sess-2", "p1", clock)
        assert second.state_of(key(session="sess-2")) is ConsentState.UNKNOWN


class TestReceipts:
    def test_every_transition_records_a_receipt(self, ledger: ConsentLedger) -> None:
        ledger.announce(key())
        ledger.grant(key(), generation=ledger.generation)
        ledger.revoke(key())
        assert [r.state for r in ledger.receipts] == [
            ConsentState.ANNOUNCED,
            ConsentState.CONSENTED,
            ConsentState.REVOKED,
        ]

    def test_receipt_carries_policy_version_and_time(
        self, ledger: ConsentLedger, clock: Clock
    ) -> None:
        ledger.announce(key())
        receipt = ledger.receipts[-1]
        assert receipt.policy_version == "p1"
        assert receipt.recorded_at == clock.t
        assert receipt.generation == ledger.generation

    def test_receipt_has_no_content_field(self) -> None:
        """A receipt records that a decision happened, never what was said."""
        from dataclasses import fields

        from meetai.consent import ConsentReceipt

        names = {f.name for f in fields(ConsentReceipt)}
        assert names == {
            "key",
            "state",
            "generation",
            "recorded_at",
            "policy_version",
        }

    def test_receipt_identifies_the_participant_only_by_handle(
        self, ledger: ConsentLedger
    ) -> None:
        ledger.announce(key())
        receipt = ledger.receipts[-1]
        assert receipt.key.participant == ALICE
        assert "handle" in receipt.key.participant


class TestExhaustiveTransitionTable:
    """Every (state, action) pair, so no combination goes unconsidered."""

    def _put_into(self, ledger: ConsentLedger, state: ConsentState, clock: Clock) -> None:
        k = key()
        if state is ConsentState.UNKNOWN:
            return
        if state is ConsentState.ANNOUNCED:
            ledger.announce(k)
            return
        if state is ConsentState.CONSENTED:
            ledger.announce(k)
            ledger.grant(k, generation=ledger.generation)
            return
        if state is ConsentState.DECLINED:
            ledger.decline(k, generation=ledger.generation)
            return
        if state is ConsentState.REVOKED:
            ledger.announce(k)
            ledger.grant(k, generation=ledger.generation)
            ledger.revoke(k)
            return
        if state is ConsentState.EXPIRED:
            ledger.grant_ttl_seconds = 10.0
            ledger.announce(k)
            ledger.grant(k, generation=ledger.generation)
            clock.advance(11.0)
            return
        raise AssertionError(f"unhandled state {state}")

    @pytest.mark.parametrize(
        ("state", "action"),
        list(itertools.product(ConsentState, ["announce", "grant", "decline", "revoke"])),
    )
    def test_transition_either_succeeds_or_raises_meetai_error(
        self, clock: Clock, state: ConsentState, action: str
    ) -> None:
        """No pair may raise an unexpected exception type.

        A KeyError or AttributeError escaping a consent gate would be handled
        by whatever generic handler happens to be above it, and a generic
        handler is exactly where fail-open creeps in.
        """
        ledger = ConsentLedger(SESSION, "p1", clock)
        self._put_into(ledger, state, clock)
        k = key()

        try:
            if action == "announce":
                ledger.announce(k)
            elif action == "grant":
                ledger.grant(k, generation=ledger.generation)
            elif action == "decline":
                ledger.decline(k, generation=ledger.generation)
            else:
                ledger.revoke(k)
        except ConsentTransitionError:
            pass  # a refusal is a correct outcome

        # Whatever happened, the ledger must still answer coherently.
        final = ledger.state_of(k)
        assert isinstance(final, ConsentState)
        assert ledger.is_granted(k) is final.grants_access

    @pytest.mark.parametrize("state", list(ConsentState))
    def test_terminal_states_never_become_granted(
        self, clock: Clock, state: ConsentState
    ) -> None:
        ledger = ConsentLedger(SESSION, "p1", clock)
        self._put_into(ledger, state, clock)
        k = key()
        if not ledger.state_of(k).is_terminal:
            pytest.skip("not a terminal state")

        for attempt in (ledger.generation, ledger.generation + 1, 0):
            with pytest.raises(ConsentTransitionError):
                ledger.grant(k, generation=attempt)
        assert ledger.is_granted(k) is False
