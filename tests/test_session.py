"""Tests for session lifecycle, late join and the revocation ordering.

The ordering test is the important one: a revocation must close the gate before
it cancels anything, because cancellation is asynchronous and slow while the
gate is synchronous and immediate.
"""

from __future__ import annotations

import pytest

from meetai.consent import ConsentKey, ConsentLedger, ConsentState
from meetai.errors import PendingDecisionError
from meetai.media_gate import GateRejection
from meetai.policy import ConsentScope, LateJoinPolicy
from meetai.session import (
    DISCLOSURE_TEXT,
    Session,
    SessionLifecycleError,
    SessionState,
)
from tests.test_consent import ALICE, BOB, NOTICE, SESSION, Clock


@pytest.fixture
def clock() -> Clock:
    return Clock()


@pytest.fixture
def ledger(clock: Clock) -> ConsentLedger:
    return ConsentLedger(session_id=SESSION, policy_version="p1", now=clock)


def make_session(
    ledger: ConsentLedger,
    *,
    allow_media: bool = True,
    late_join: LateJoinPolicy = LateJoinPolicy.PENDING_DECISION,
) -> Session:
    return Session(
        session_id=SESSION,
        ledger=ledger,
        notice_version=NOTICE,
        policy_allows_media=lambda: allow_media,
        late_join_policy=late_join,
    )


def grant(ledger: ConsentLedger, participant: str) -> None:
    key = ConsentKey(SESSION, participant, ConsentScope.LIVE_MEDIA, NOTICE)
    ledger.grant(key, generation=ledger.generation)


class TestConstruction:
    def test_ledger_must_belong_to_this_session(self, clock: Clock) -> None:
        """Consent is not inherited; a mismatched ledger is a bug, not a config."""
        other = ConsentLedger("sess-other", "p1", clock)
        with pytest.raises(SessionLifecycleError, match="thuoc phien"):
            Session(
                session_id=SESSION,
                ledger=other,
                notice_version=NOTICE,
                policy_allows_media=lambda: True,
            )

    def test_starts_in_created(self, ledger: ConsentLedger) -> None:
        assert make_session(ledger).state is SessionState.CREATED


class TestLifecycle:
    def test_only_active_expects_media(self) -> None:
        for state in SessionState:
            assert state.expects_media is (state is SessionState.ACTIVE)

    def test_announcing_returns_the_fixed_disclosure(self, ledger: ConsentLedger) -> None:
        session = make_session(ledger)
        assert session.begin_announcing([ALICE]) == DISCLOSURE_TEXT
        assert "MeetAI" in DISCLOSURE_TEXT

    def test_announcing_announces_consent_for_each_participant(
        self, ledger: ConsentLedger
    ) -> None:
        session = make_session(ledger)
        session.begin_announcing([ALICE, BOB])
        for participant in (ALICE, BOB):
            key = ConsentKey(SESSION, participant, ConsentScope.LIVE_MEDIA, NOTICE)
            assert ledger.state_of(key) is ConsentState.ANNOUNCED

    def test_cannot_activate_without_announcing(self, ledger: ConsentLedger) -> None:
        """There is no path to media without a disclosure step."""
        with pytest.raises(SessionLifecycleError, match="activate"):
            make_session(ledger).activate()

    def test_cannot_announce_twice(self, ledger: ConsentLedger) -> None:
        session = make_session(ledger)
        session.begin_announcing([ALICE])
        with pytest.raises(SessionLifecycleError):
            session.begin_announcing([BOB])

    def test_activate_refused_while_policy_pending(self, ledger: ConsentLedger) -> None:
        """A running session that silently processes nothing reads as a bug."""
        session = make_session(ledger, allow_media=False)
        session.begin_announcing([ALICE])
        with pytest.raises(PendingDecisionError, match="chua duoc chot"):
            session.activate()

    def test_activate_succeeds_when_policy_is_decided(
        self, ledger: ConsentLedger
    ) -> None:
        session = make_session(ledger)
        session.begin_announcing([ALICE])
        session.activate()
        assert session.state is SessionState.ACTIVE


class TestFrameAcceptance:
    def _active(self, ledger: ConsentLedger) -> Session:
        session = make_session(ledger)
        session.begin_announcing([ALICE, BOB])
        session.activate()
        return session

    def test_consented_frame_is_buffered(self, ledger: ConsentLedger) -> None:
        session = self._active(ledger)
        grant(ledger, ALICE)
        assert session.accept_frame(
            participant=ALICE, generation=ledger.generation, frame=b"pcm"
        )
        assert len(session.buffer_for(ALICE)) == 1

    def test_unconsented_frame_is_not_buffered(self, ledger: ConsentLedger) -> None:
        """Dropped before ASR has to mean never stored anywhere."""
        session = self._active(ledger)
        assert not session.accept_frame(
            participant=ALICE, generation=ledger.generation, frame=b"pcm"
        )
        assert len(session.buffer_for(ALICE)) == 0

    def test_unmapped_speaker_gets_no_buffer(self, ledger: ConsentLedger) -> None:
        session = self._active(ledger)
        assert not session.accept_frame(
            participant=None, generation=ledger.generation, frame=b"pcm"
        )
        assert session.gate.rejection_counts == {"speaker_unmapped": 1}

    def test_frame_before_activation_is_rejected(self, ledger: ConsentLedger) -> None:
        session = make_session(ledger)
        session.begin_announcing([ALICE])
        grant(ledger, ALICE)
        assert not session.accept_frame(
            participant=ALICE, generation=ledger.generation, frame=b"pcm"
        )
        assert session.gate.rejection_counts == {"session_not_active": 1}


class TestRevocationOrdering:
    def _active_with_consent(self, ledger: ConsentLedger) -> Session:
        session = make_session(ledger)
        session.begin_announcing([ALICE, BOB])
        session.activate()
        grant(ledger, ALICE)
        grant(ledger, BOB)
        return session

    def test_gate_closes_before_tasks_are_cancelled(self, ledger: ConsentLedger) -> None:
        """The ordering that matters.

        The cancellation callback checks the gate as it runs. If the gate were
        still permissive at that moment, a task that had already passed its
        check could still emit.
        """
        session = self._active_with_consent(ledger)
        captured = ledger.generation
        observed: list[bool] = []

        def cancel() -> None:
            decision = session.gate.evaluate(participant=ALICE, generation=captured)
            observed.append(decision.allowed)

        session.register_cancellation(cancel)
        session.revoke(ALICE)

        assert observed == [False], "gate still allowed work during cancellation"

    def test_revocation_invalidates_in_flight_generation(
        self, ledger: ConsentLedger
    ) -> None:
        session = self._active_with_consent(ledger)
        captured = ledger.generation
        session.revoke(BOB)
        decision = session.gate.evaluate(participant=ALICE, generation=captured)
        assert decision.rejection is GateRejection.STALE_GENERATION

    def test_revocation_purges_the_participants_buffer(
        self, ledger: ConsentLedger
    ) -> None:
        session = self._active_with_consent(ledger)
        session.accept_frame(
            participant=ALICE, generation=ledger.generation, frame=b"pcm"
        )
        result = session.revoke(ALICE)
        assert result.buffered_items_dropped == 1

    def test_revocation_reports_scopes_without_content(
        self, ledger: ConsentLedger
    ) -> None:
        session = self._active_with_consent(ledger)
        result = session.revoke(ALICE)
        assert result.participant == ALICE
        assert result.scopes == (ConsentScope.LIVE_MEDIA.value,)

    def test_cancellations_run_once(self, ledger: ConsentLedger) -> None:
        session = self._active_with_consent(ledger)
        calls: list[int] = []
        session.register_cancellation(lambda: calls.append(1))
        session.revoke(ALICE)
        session.revoke(BOB)
        assert calls == [1]

    def test_a_raising_cancellation_does_not_stop_the_others(
        self, ledger: ConsentLedger
    ) -> None:
        """A half-cancelled revocation is worse than a noisy one."""
        session = self._active_with_consent(ledger)
        ran: list[str] = []

        def boom() -> None:
            ran.append("boom")
            raise RuntimeError("cancellation failed")

        session.register_cancellation(boom)
        session.register_cancellation(lambda: ran.append("second"))

        result = session.revoke(ALICE)
        assert ran == ["boom", "second"]
        assert result.tasks_cancelled == 2

    def test_revoked_participant_cannot_send_frames(self, ledger: ConsentLedger) -> None:
        session = self._active_with_consent(ledger)
        session.revoke(ALICE)
        assert not session.accept_frame(
            participant=ALICE, generation=ledger.generation, frame=b"pcm"
        )

    def test_other_participants_continue_after_a_revocation(
        self, ledger: ConsentLedger
    ) -> None:
        """A withdrawal must stop the withdrawer, not end everyone's session."""
        session = self._active_with_consent(ledger)
        session.revoke(ALICE)
        assert session.accept_frame(
            participant=BOB, generation=ledger.generation, frame=b"pcm"
        )


class TestLateJoin:
    def _active(self, ledger: ConsentLedger, policy: LateJoinPolicy) -> Session:
        session = make_session(ledger, late_join=policy)
        session.begin_announcing([ALICE])
        session.activate()
        grant(ledger, ALICE)
        return session

    def test_pending_decision_closes_the_gate(self, ledger: ConsentLedger) -> None:
        """Fail-closed, and it says which decision is missing."""
        session = self._active(ledger, LateJoinPolicy.PENDING_DECISION)
        outcome = session.participant_joined(BOB)
        assert outcome.gate_closed is True
        assert outcome.reason == "late_join_policy_pending"
        assert not session.accept_frame(
            participant=ALICE, generation=ledger.generation, frame=b"pcm"
        )

    def test_a1_trips_the_circuit_breaker(self, ledger: ConsentLedger) -> None:
        session = self._active(ledger, LateJoinPolicy.A1_CIRCUIT_BREAKER)
        cancelled: list[int] = []
        session.register_cancellation(lambda: cancelled.append(1))

        outcome = session.participant_joined(BOB)
        assert outcome.reason == "circuit_breaker_tripped"
        assert outcome.gate_closed is True
        assert cancelled == [1]

    def test_a3_awaits_admission_without_cancelling(self, ledger: ConsentLedger) -> None:
        """Admission control pauses; it does not tear the pipeline down."""
        session = self._active(ledger, LateJoinPolicy.A3_ADMISSION_CONTROL)
        cancelled: list[int] = []
        session.register_cancellation(lambda: cancelled.append(1))

        outcome = session.participant_joined(BOB)
        assert outcome.reason == "awaiting_admission"
        assert outcome.gate_closed is True
        assert cancelled == []

    def test_both_designs_are_supported(self) -> None:
        """Neither design is chosen here; the module supports both."""
        assert LateJoinPolicy.A1_CIRCUIT_BREAKER
        assert LateJoinPolicy.A3_ADMISSION_CONTROL
        assert not LateJoinPolicy.PENDING_DECISION

    def test_joining_before_activation_is_just_registration(
        self, ledger: ConsentLedger
    ) -> None:
        session = make_session(ledger)
        session.begin_announcing([ALICE])
        outcome = session.participant_joined(BOB)
        assert outcome.gate_closed is False
        assert outcome.reason == "registered_before_active"
        key = ConsentKey(SESSION, BOB, ConsentScope.LIVE_MEDIA, NOTICE)
        assert ledger.state_of(key) is ConsentState.ANNOUNCED

    def test_joining_a_closed_session_is_refused(self, ledger: ConsentLedger) -> None:
        session = self._active(ledger, LateJoinPolicy.PENDING_DECISION)
        session.close()
        with pytest.raises(SessionLifecycleError, match="da dong"):
            session.participant_joined(BOB)

    def test_require_decision_raises_while_pending(self, ledger: ConsentLedger) -> None:
        session = make_session(ledger, late_join=LateJoinPolicy.PENDING_DECISION)
        with pytest.raises(PendingDecisionError, match="A1 circuit breaker"):
            session.require_late_join_decision()

    @pytest.mark.parametrize(
        "policy",
        [LateJoinPolicy.A1_CIRCUIT_BREAKER, LateJoinPolicy.A3_ADMISSION_CONTROL],
    )
    def test_require_decision_passes_when_decided(
        self, ledger: ConsentLedger, policy: LateJoinPolicy
    ) -> None:
        make_session(ledger, late_join=policy).require_late_join_decision()


class TestClose:
    def test_close_closes_cancels_and_purges(self, ledger: ConsentLedger) -> None:
        session = make_session(ledger)
        session.begin_announcing([ALICE])
        session.activate()
        grant(ledger, ALICE)
        session.accept_frame(
            participant=ALICE, generation=ledger.generation, frame=b"pcm"
        )
        cancelled: list[int] = []
        session.register_cancellation(lambda: cancelled.append(1))

        result = session.close()

        assert session.state is SessionState.CLOSED
        assert session.gate.is_closed is True
        assert result.buffered_items_dropped == 1
        assert result.tasks_cancelled == 1
        assert cancelled == [1]

    def test_closed_session_accepts_nothing(self, ledger: ConsentLedger) -> None:
        session = make_session(ledger)
        session.begin_announcing([ALICE])
        session.activate()
        grant(ledger, ALICE)
        session.close()
        assert not session.accept_frame(
            participant=ALICE, generation=ledger.generation, frame=b"pcm"
        )


class TestStatus:
    def test_status_is_metadata_only(self, ledger: ConsentLedger) -> None:
        """The status goes to a log line and the UI, so it must carry no content."""
        session = make_session(ledger)
        session.begin_announcing([ALICE, BOB])
        status = session.status()

        assert status["session_id"] == SESSION
        assert status["state"] == "announcing"
        assert status["participant_count"] == 2
        assert status["late_join_policy"] == "pending_decision"
        assert "participants" not in status
        assert "frames" not in status
        assert "transcript" not in status

    def test_status_reports_gate_counters(self, ledger: ConsentLedger) -> None:
        session = make_session(ledger)
        session.begin_announcing([ALICE])
        session.activate()
        session.accept_frame(participant=ALICE, generation=ledger.generation, frame=b"x")
        assert session.status()["rejection_counts"] == {"no_consent": 1}
