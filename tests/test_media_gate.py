"""Tests for the media gate and the bounded buffer.

The gate's job is to refuse, so most of these assert a refusal and the reason
for it. A gate that allowed everything would pass a test that only checked the
happy path.
"""

from __future__ import annotations

import pytest

from meetai.consent import ConsentKey, ConsentLedger
from meetai.media_gate import BoundedBuffer, GateDecision, GateRejection, MediaGate
from meetai.policy import ConsentScope
from tests.test_consent import ALICE, BOB, NOTICE, SESSION, Clock


@pytest.fixture
def clock() -> Clock:
    return Clock()


@pytest.fixture
def ledger(clock: Clock) -> ConsentLedger:
    return ConsentLedger(session_id=SESSION, policy_version="p1", now=clock)


@pytest.fixture
def gate(ledger: ConsentLedger) -> MediaGate:
    return MediaGate(
        ledger=ledger,
        notice_version=NOTICE,
        policy_allows_media=lambda: True,
        session_is_active=lambda: True,
    )


def consent(
    ledger: ConsentLedger, participant: str, scope: ConsentScope = ConsentScope.LIVE_MEDIA
) -> None:
    key = ConsentKey(SESSION, participant, scope, NOTICE)
    ledger.announce(key)
    ledger.grant(key, generation=ledger.generation)


class TestDecisionInvariants:
    def test_allowed_decision_cannot_carry_a_reason(self) -> None:
        with pytest.raises(ValueError, match="khong duoc co rejection"):
            GateDecision(allowed=True, rejection=GateRejection.NO_CONSENT)

    def test_rejected_decision_must_carry_a_reason(self) -> None:
        """A bare refusal gives an operator and a log line nothing."""
        with pytest.raises(ValueError, match="phai co rejection"):
            GateDecision(allowed=False)

    def test_decision_is_truthy_when_allowed(self) -> None:
        assert GateDecision.allow()
        assert not GateDecision.reject(GateRejection.NO_CONSENT)


class TestFailClosed:
    def test_no_consent_is_rejected(self, gate: MediaGate, ledger: ConsentLedger) -> None:
        decision = gate.evaluate(participant=ALICE, generation=ledger.generation)
        assert decision.allowed is False
        assert decision.rejection is GateRejection.NO_CONSENT

    def test_unmapped_speaker_is_rejected(
        self, gate: MediaGate, ledger: ConsentLedger
    ) -> None:
        """The dangerous case: a speaker who may never have seen a notice."""
        consent(ledger, ALICE)
        decision = gate.evaluate(participant=None, generation=ledger.generation)
        assert decision.rejection is GateRejection.SPEAKER_UNMAPPED

    def test_unmapped_is_checked_before_consent(
        self, gate: MediaGate, ledger: ConsentLedger
    ) -> None:
        """An unmapped frame must not be able to borrow anyone's consent."""
        consent(ledger, ALICE)
        assert (
            gate.evaluate(participant=None, generation=ledger.generation).rejection
            is GateRejection.SPEAKER_UNMAPPED
        )

    def test_policy_pending_is_rejected(self, ledger: ConsentLedger) -> None:
        consent(ledger, ALICE)
        gate = MediaGate(
            ledger=ledger,
            notice_version=NOTICE,
            policy_allows_media=lambda: False,
            session_is_active=lambda: True,
        )
        assert (
            gate.evaluate(participant=ALICE, generation=ledger.generation).rejection
            is GateRejection.POLICY_PENDING
        )

    def test_inactive_session_is_rejected(self, ledger: ConsentLedger) -> None:
        consent(ledger, ALICE)
        gate = MediaGate(
            ledger=ledger,
            notice_version=NOTICE,
            policy_allows_media=lambda: True,
            session_is_active=lambda: False,
        )
        assert (
            gate.evaluate(participant=ALICE, generation=ledger.generation).rejection
            is GateRejection.SESSION_NOT_ACTIVE
        )

    def test_wrong_scope_is_rejected(
        self, gate: MediaGate, ledger: ConsentLedger
    ) -> None:
        """Consent to live media is not consent to a durable transcript."""
        consent(ledger, ALICE, ConsentScope.LIVE_MEDIA)
        decision = gate.evaluate(
            participant=ALICE,
            generation=ledger.generation,
            scope=ConsentScope.DURABLE_TRANSCRIPT,
        )
        assert decision.rejection is GateRejection.NO_CONSENT

    def test_another_participants_consent_does_not_help(
        self, gate: MediaGate, ledger: ConsentLedger
    ) -> None:
        consent(ledger, ALICE)
        assert (
            gate.evaluate(participant=BOB, generation=ledger.generation).rejection
            is GateRejection.NO_CONSENT
        )

    def test_consented_frame_is_allowed(
        self, gate: MediaGate, ledger: ConsentLedger
    ) -> None:
        consent(ledger, ALICE)
        assert gate.evaluate(participant=ALICE, generation=ledger.generation).allowed


class TestLivePolicyReading:
    def test_policy_is_read_at_decision_time(self, ledger: ConsentLedger) -> None:
        """A kill switch that only affected later gates would not be one."""
        consent(ledger, ALICE)
        allowed = True
        gate = MediaGate(
            ledger=ledger,
            notice_version=NOTICE,
            policy_allows_media=lambda: allowed,
            session_is_active=lambda: True,
        )
        assert gate.evaluate(participant=ALICE, generation=ledger.generation).allowed

        allowed = False
        assert (
            gate.evaluate(participant=ALICE, generation=ledger.generation).rejection
            is GateRejection.POLICY_PENDING
        )


class TestRevokeRace:
    def test_stale_generation_is_rejected(
        self, gate: MediaGate, ledger: ConsentLedger
    ) -> None:
        consent(ledger, ALICE)
        captured = ledger.generation
        assert gate.evaluate(participant=ALICE, generation=captured).allowed

        consent(ledger, BOB)
        ledger.revoke(ConsentKey(SESSION, BOB, ConsentScope.LIVE_MEDIA, NOTICE))

        decision = gate.evaluate(participant=ALICE, generation=captured)
        assert decision.rejection is GateRejection.STALE_GENERATION

    def test_revoked_participant_is_rejected(
        self, gate: MediaGate, ledger: ConsentLedger
    ) -> None:
        consent(ledger, ALICE)
        ledger.revoke(ConsentKey(SESSION, ALICE, ConsentScope.LIVE_MEDIA, NOTICE))
        decision = gate.evaluate(participant=ALICE, generation=ledger.generation)
        assert decision.rejection is GateRejection.NO_CONSENT

    def test_expired_consent_is_rejected(self, clock: Clock) -> None:
        ledger = ConsentLedger(SESSION, "p1", clock, grant_ttl_seconds=10.0)
        gate = MediaGate(
            ledger=ledger,
            notice_version=NOTICE,
            policy_allows_media=lambda: True,
            session_is_active=lambda: True,
        )
        consent(ledger, ALICE)
        assert gate.evaluate(participant=ALICE, generation=ledger.generation).allowed

        clock.advance(11.0)
        assert (
            gate.evaluate(participant=ALICE, generation=ledger.generation).rejection
            is GateRejection.NO_CONSENT
        )


class TestGateClosing:
    def test_closed_gate_rejects_everything(
        self, gate: MediaGate, ledger: ConsentLedger
    ) -> None:
        consent(ledger, ALICE)
        gate.close()
        assert (
            gate.evaluate(participant=ALICE, generation=ledger.generation).rejection
            is GateRejection.GATE_CLOSED
        )

    def test_closing_is_checked_first(self, ledger: ConsentLedger) -> None:
        """A closed gate refuses even when nothing else would."""
        gate = MediaGate(
            ledger=ledger,
            notice_version=NOTICE,
            policy_allows_media=lambda: False,
            session_is_active=lambda: False,
        )
        gate.close()
        assert (
            gate.evaluate(participant=None, generation=99).rejection
            is GateRejection.GATE_CLOSED
        )

    def test_no_reopen_api(self, gate: MediaGate) -> None:
        """A session whose gate closed is finished; continuing needs a new one."""
        assert not hasattr(gate, "reopen")
        assert not hasattr(gate, "open")


class TestCounters:
    def test_rejections_are_counted_by_reason(
        self, gate: MediaGate, ledger: ConsentLedger
    ) -> None:
        """A gate that silently drops everything looks like a quiet meeting."""
        gate.evaluate(participant=ALICE, generation=ledger.generation)
        gate.evaluate(participant=ALICE, generation=ledger.generation)
        gate.evaluate(participant=None, generation=ledger.generation)

        assert gate.rejection_counts == {"no_consent": 2, "speaker_unmapped": 1}

    def test_allowed_frames_are_counted(
        self, gate: MediaGate, ledger: ConsentLedger
    ) -> None:
        consent(ledger, ALICE)
        gate.evaluate(participant=ALICE, generation=ledger.generation)
        gate.evaluate(participant=ALICE, generation=ledger.generation)
        assert gate.allowed_count == 2

    def test_counters_contain_no_content(
        self, gate: MediaGate, ledger: ConsentLedger
    ) -> None:
        """The counters are logged, so they must be metadata only."""
        gate.evaluate(participant=ALICE, generation=ledger.generation)
        for name, count in gate.rejection_counts.items():
            assert isinstance(name, str)
            assert isinstance(count, int)


class TestBoundedBuffer:
    def test_size_bound_evicts_oldest(self, clock: Clock) -> None:
        buffer = BoundedBuffer(max_items=3, max_age_seconds=100.0, now=clock)
        for i in range(5):
            buffer.push(i)
        assert buffer.drain() == (2, 3, 4)
        assert buffer.dropped_by_size == 2

    def test_age_bound_evicts_stale(self, clock: Clock) -> None:
        """Audio sitting in a buffer is audio a revocation should have discarded."""
        buffer = BoundedBuffer(max_items=100, max_age_seconds=5.0, now=clock)
        buffer.push("old")
        clock.advance(6.0)
        buffer.push("new")
        assert buffer.drain() == ("new",)
        assert buffer.dropped_by_age == 1

    def test_len_reflects_age_eviction(self, clock: Clock) -> None:
        buffer = BoundedBuffer(max_items=100, max_age_seconds=5.0, now=clock)
        buffer.push("x")
        assert len(buffer) == 1
        clock.advance(6.0)
        assert len(buffer) == 0

    def test_purge_discards_everything(self, clock: Clock) -> None:
        buffer = BoundedBuffer(max_items=10, max_age_seconds=100.0, now=clock)
        for i in range(4):
            buffer.push(i)
        assert buffer.purge() == 4
        assert len(buffer) == 0

    def test_purge_is_not_counted_as_eviction(self, clock: Clock) -> None:
        """Conflating a deliberate purge with eviction would hide a real problem."""
        buffer = BoundedBuffer(max_items=10, max_age_seconds=100.0, now=clock)
        buffer.push("x")
        buffer.purge()
        assert buffer.dropped_by_size == 0
        assert buffer.dropped_by_age == 0

    def test_drain_empties(self, clock: Clock) -> None:
        buffer = BoundedBuffer(max_items=10, max_age_seconds=100.0, now=clock)
        buffer.push("x")
        assert buffer.drain() == ("x",)
        assert buffer.drain() == ()

    @pytest.mark.parametrize(
        ("items", "age"), [(0, 5.0), (-1, 5.0), (10, 0.0), (10, -1.0)]
    )
    def test_invalid_bounds_refused(self, clock: Clock, items: int, age: float) -> None:
        """An unbounded buffer is not a buffer, it is a leak."""
        with pytest.raises(ValueError, match="phai"):
            BoundedBuffer(max_items=items, max_age_seconds=age, now=clock)
