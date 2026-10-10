"""Tests for Start/Stop, the model switch and the kill switch.

The kill-switch tests are written around what the contract can actually
guarantee. A test asserting "all work stopped" would be unprovable with the
current machinery, and asserting it anyway is how an overclaim gets written
down as verified.
"""

from __future__ import annotations

import pytest

from meetai.consent import ConsentKey, ConsentLedger
from meetai.media_gate import BoundedBuffer, GateRejection
from meetai.policy import ConsentScope, LateJoinPolicy
from meetai.session import Session
from meetai.supervisor import (
    KillSwitch,
    ModelState,
    ModelSwitch,
    RunState,
    Supervisor,
    SupervisorError,
)
from tests.test_consent import ALICE, NOTICE, SESSION, Clock


@pytest.fixture
def clock() -> Clock:
    return Clock()


def ready_model() -> ModelSwitch:
    return ModelSwitch(loader=lambda: ModelState.READY)


@pytest.fixture
def supervisor() -> Supervisor:
    return Supervisor(settings_allows_media=lambda: True, model=ready_model())


class TestRunStateSemantics:
    def test_only_running_is_truthy(self) -> None:
        """`if supervisor.state:` must fail closed."""
        for state in RunState:
            assert bool(state) is (state is RunState.RUNNING)

    def test_killed_is_terminal(self) -> None:
        assert RunState.KILLED.is_terminal is True
        for state in (RunState.STOPPED, RunState.STARTING, RunState.RUNNING):
            assert state.is_terminal is False


class TestStartStop:
    def test_starts_stopped(self, supervisor: Supervisor) -> None:
        assert supervisor.state is RunState.STOPPED
        assert supervisor.is_running is False

    def test_start_runs(self, supervisor: Supervisor) -> None:
        assert supervisor.start() is RunState.RUNNING

    def test_start_is_idempotent(self, supervisor: Supervisor) -> None:
        supervisor.start()
        assert supervisor.start() is RunState.RUNNING

    def test_stop_is_idempotent(self, supervisor: Supervisor) -> None:
        supervisor.start()
        supervisor.stop()
        assert supervisor.stop() is RunState.STOPPED

    def test_stop_is_recoverable_unlike_kill(self, supervisor: Supervisor) -> None:
        """Conflating Stop with Kill would make every Stop need a restart."""
        supervisor.start()
        supervisor.stop()
        assert supervisor.start() is RunState.RUNNING

    def test_start_does_not_turn_the_model_on(self, supervisor: Supervisor) -> None:
        """A Start that loaded a model would be doing more than it says."""
        supervisor.start()
        assert supervisor.model.state is ModelState.OFF

    def test_start_does_not_allow_media_on_its_own(self) -> None:
        """Four conditions, not one. Running is necessary, never sufficient."""
        sup = Supervisor(settings_allows_media=lambda: True, model=ModelSwitch())
        sup.start()
        assert sup.media_allowed() is False  # model is off


class TestModelSwitch:
    def test_starts_off(self) -> None:
        assert ModelSwitch().state is ModelState.OFF

    def test_only_ready_is_truthy(self) -> None:
        """A probe in flight must not read as available."""
        for state in ModelState:
            assert bool(state) is (state is ModelState.READY)

    def test_loading_and_unknown_are_undecided(self) -> None:
        assert ModelState.LOADING.is_decided is False
        assert ModelState.UNKNOWN.is_decided is False
        for state in (ModelState.OFF, ModelState.READY, ModelState.ERROR):
            assert state.is_decided is True

    def test_no_loader_reports_error_not_ready(self) -> None:
        """There is no model runtime, so READY would be a false claim."""
        switch = ModelSwitch()
        assert switch.turn_on() is ModelState.ERROR
        assert "chua co model runtime" in switch.detail

    def test_a_failing_loader_reports_type_only(self) -> None:
        """A loader message could name a model path."""
        canary = "D:/secret/path/to/model.gguf"

        def boom() -> ModelState:
            raise RuntimeError(canary)

        switch = ModelSwitch(loader=boom)
        assert switch.turn_on() is ModelState.ERROR
        assert canary not in switch.detail
        assert "RuntimeError" in switch.detail

    def test_a_working_loader_reports_ready(self) -> None:
        assert ready_model().turn_on() is ModelState.READY

    def test_a_loader_reporting_not_ready_is_believed(self) -> None:
        switch = ModelSwitch(loader=lambda: ModelState.ERROR)
        assert switch.turn_on() is ModelState.ERROR

    def test_turn_off_always_succeeds(self) -> None:
        """Refusing to turn something off would be the wrong failure mode."""
        switch = ready_model()
        switch.turn_on()
        switch.turn_off()
        assert switch.state is ModelState.OFF

    def test_model_on_does_not_allow_media_by_itself(self) -> None:
        """Turning the model on must not turn audio on."""
        sup = Supervisor(settings_allows_media=lambda: True, model=ready_model())
        sup.model.turn_on()
        assert sup.is_running is False
        assert sup.media_allowed() is False


class TestKillSwitchLatch:
    def test_starts_disengaged(self) -> None:
        assert KillSwitch().engaged is False

    def test_engage_latches(self) -> None:
        switch = KillSwitch()
        switch.engage("vi mot ly do")
        assert switch.engaged is True
        assert switch.reason == "vi mot ly do"

    def test_there_is_no_disengage(self) -> None:
        """A latch that flips back is a toggle, which is not what was asked for."""
        switch = KillSwitch()
        assert not hasattr(switch, "disengage")
        assert not hasattr(switch, "reset")

    def test_second_engage_keeps_the_first_reason(self) -> None:
        """The first reason describes why media stopped."""
        switch = KillSwitch()
        switch.engage("ly do dau")
        switch.engage("ly do sau")
        assert switch.reason == "ly do dau"

    def test_kill_stops_and_is_terminal(self, supervisor: Supervisor) -> None:
        supervisor.start()
        supervisor.model.turn_on()
        assert supervisor.kill() is RunState.KILLED
        assert supervisor.model.state is ModelState.OFF

    def test_start_after_kill_is_refused(self, supervisor: Supervisor) -> None:
        supervisor.start()
        supervisor.kill()
        with pytest.raises(SupervisorError, match="kill switch"):
            supervisor.start()

    def test_stop_after_kill_stays_killed(self, supervisor: Supervisor) -> None:
        supervisor.kill()
        assert supervisor.stop() is RunState.KILLED


class TestComposedMediaGate:
    """The composition is what makes the kill switch process-wide."""

    def test_all_four_conditions_are_required(self) -> None:
        sup = Supervisor(settings_allows_media=lambda: True, model=ready_model())
        assert sup.media_allowed() is False  # not running, model off

        sup.start()
        assert sup.media_allowed() is False  # model off

        sup.model.turn_on()
        assert sup.media_allowed() is True

        sup.kill()
        assert sup.media_allowed() is False

    def test_settings_refusal_alone_blocks(self) -> None:
        sup = Supervisor(settings_allows_media=lambda: False, model=ready_model())
        sup.start()
        sup.model.turn_on()
        assert sup.media_allowed() is False

    def test_conditions_are_read_at_call_time(self) -> None:
        """A kill must reach gates that already exist.

        This is the reason `policy_allows_media` is a callable: `Settings` is
        frozen and `model_copy` re-validates into a new object, so nothing can
        flip `media_processing_allowed` on the live settings.
        """
        allowed = True
        sup = Supervisor(settings_allows_media=lambda: allowed, model=ready_model())
        sup.start()
        sup.model.turn_on()
        assert sup.media_allowed() is True

        allowed = False
        assert sup.media_allowed() is False

    def test_kill_reaches_an_existing_gate(self, clock: Clock) -> None:
        """The finding that motivated a process-wide latch.

        Without one, a kill button can only reach the sessions it holds a
        reference to, and there is no session registry.
        """
        sup = Supervisor(settings_allows_media=lambda: True, model=ready_model())
        sup.start()
        sup.model.turn_on()

        ledger = ConsentLedger(SESSION, "p1", clock)
        session = Session(
            session_id=SESSION,
            ledger=ledger,
            notice_version=NOTICE,
            policy_allows_media=sup.media_allowed,
            late_join_policy=LateJoinPolicy.A1_CIRCUIT_BREAKER,
        )
        session.begin_announcing([ALICE])
        session.activate()
        key = ConsentKey(SESSION, ALICE, ConsentScope.LIVE_MEDIA, NOTICE)
        ledger.grant(key, generation=ledger.generation)

        assert session.gate.evaluate(
            participant=ALICE, generation=ledger.generation
        ).allowed

        sup.kill()

        decision = session.gate.evaluate(participant=ALICE, generation=ledger.generation)
        assert decision.rejection is GateRejection.POLICY_PENDING


class TestStatusIsMetadataOnly:
    def test_status_fields(self, supervisor: Supervisor) -> None:
        status = supervisor.status()
        assert status["run_state"] == "stopped"
        assert status["model_state"] == "off"
        assert status["kill_engaged"] is False
        assert status["media_allowed"] is False

    def test_status_distinguishes_undecided_model_state(self) -> None:
        """The UI needs "do not know yet" as a renderable state."""
        sup = Supervisor(
            settings_allows_media=lambda: True,
            model=ModelSwitch(loader=lambda: ModelState.LOADING),
        )
        sup.model.turn_on()
        assert sup.status()["model_state"] == "loading"
        assert sup.status()["model_state_decided"] is False

    def test_status_carries_no_paths_or_content(self) -> None:
        canary = "D:/secret/model/path.gguf"

        def boom() -> ModelState:
            raise RuntimeError(canary)

        sup = Supervisor(
            settings_allows_media=lambda: True, model=ModelSwitch(loader=boom)
        )
        sup.model.turn_on()
        assert canary not in str(sup.status())


class TestKillSwitchContractOnSessions:
    """Only the guarantees the machinery actually provides."""

    def _live_session(self, clock: Clock) -> tuple[Session, ConsentLedger, ConsentKey]:
        ledger = ConsentLedger(SESSION, "p1", clock)
        session = Session(
            session_id=SESSION,
            ledger=ledger,
            notice_version=NOTICE,
            policy_allows_media=lambda: True,
            late_join_policy=LateJoinPolicy.A1_CIRCUIT_BREAKER,
        )
        session.begin_announcing([ALICE])
        session.activate()
        key = ConsentKey(SESSION, ALICE, ConsentScope.LIVE_MEDIA, NOTICE)
        ledger.grant(key, generation=ledger.generation)
        return session, ledger, key

    def test_close_refuses_a_valid_current_grant(self, clock: Clock) -> None:
        """Checked against a grant that would otherwise pass.

        Asserting a refusal on a participant with no consent would pass
        against a gate that is merely refusing for the ordinary reason.
        """
        session, ledger, _ = self._live_session(clock)
        assert session.gate.evaluate(
            participant=ALICE, generation=ledger.generation
        ).allowed

        session.close()
        decision = session.gate.evaluate(participant=ALICE, generation=ledger.generation)
        assert decision.rejection is GateRejection.GATE_CLOSED

    def test_close_invalidates_a_ledger_level_recheck(self, clock: Clock) -> None:
        """The gap that made close() weaker than revoke().

        A downstream stage can re-check against the ledger rather than against
        this gate object. Before close() bumped the generation, such a stage
        was refused by a revocation and not by a kill.
        """
        session, ledger, key = self._live_session(clock)
        captured = ledger.generation
        assert ledger.is_granted(key, generation=captured) is True

        session.close()
        assert ledger.is_granted(key, generation=captured) is False

    def test_close_does_not_fabricate_a_consent_decision(self, clock: Clock) -> None:
        """Bumping the generation must not look like a withdrawal.

        Nobody withdrew consent, so the records and the receipts must show no
        decision that did not happen.
        """
        session, ledger, key = self._live_session(clock)
        receipts_before = len(ledger.receipts)
        state_before = ledger.state_of(key)

        session.close()
        assert ledger.state_of(key) is state_before
        assert len(ledger.receipts) == receipts_before

    def test_buffered_frames_are_unreachable_even_to_a_holder(self, clock: Clock) -> None:
        """Purge alone was not enough.

        Clearing the session's dict drops the session's reference, but a
        consumer that called buffer_for earlier still holds the object - and a
        purged-but-open buffer accepts another push.
        """
        session, ledger, _ = self._live_session(clock)
        session.accept_frame(
            participant=ALICE, generation=ledger.generation, frame=b"pcm"
        )
        held = session.buffer_for(ALICE)

        session.close()

        assert held.is_closed is True
        held.push(b"more")
        assert len(held) == 0
        assert held.drain() == ()

    def test_a_recreated_gate_is_still_refused(self, clock: Clock) -> None:
        """Pins an accidental second line of defence.

        `_gate` is a plain field, so clearing it rebuilds an open gate. It
        still refuses, but via the session-state check rather than the closed
        flag - worth a test precisely because it is accidental.
        """
        session, ledger, _ = self._live_session(clock)
        session.close()
        session._gate = None

        decision = session.gate.evaluate(participant=ALICE, generation=ledger.generation)
        assert decision.rejection is GateRejection.SESSION_NOT_ACTIVE

    def test_tasks_cancelled_counts_attempts_not_successes(self, clock: Clock) -> None:
        """Stated explicitly so the UI does not render it as a guarantee.

        Cancellation callbacks are wrapped in `suppress`, deliberately, so a
        callback that raises on its first line is still counted.
        """
        session, _, _ = self._live_session(clock)

        def boom() -> None:
            raise RuntimeError("cancel failed")

        session.register_cancellation(boom)
        result = session.close()
        assert result.tasks_cancelled == 1  # invoked, not necessarily stopped

    def test_unregistered_work_is_not_counted(self, clock: Clock) -> None:
        """The most important thing not to overclaim.

        There is no registry of outstanding work, so work that never
        registered a cancellation callback is invisible. The count is of
        callbacks invoked, and nothing can make it complete.
        """
        session, _, _ = self._live_session(clock)
        result = session.close()
        assert result.tasks_cancelled == 0  # not "no work was running"

    def test_gate_closed_is_observed(self, clock: Clock) -> None:
        session, _, _ = self._live_session(clock)
        result = session.close()
        assert result.gate_closed is session.gate.is_closed


class TestBoundedBufferTerminalClose:
    def test_close_discards_and_latches(self, clock: Clock) -> None:
        buffer = BoundedBuffer(max_items=10, max_age_seconds=100.0, now=clock)
        buffer.push("a")
        buffer.push("b")
        assert buffer.close() == 2
        assert buffer.is_closed is True

    def test_push_after_close_is_a_silent_no_op(self, clock: Clock) -> None:
        """Silent rather than raising: a pipeline pushing into a killed
        session should stop, not crash into a handler that might do something
        else with the frame."""
        buffer = BoundedBuffer(max_items=10, max_age_seconds=100.0, now=clock)
        buffer.close()
        buffer.push("a")
        assert len(buffer) == 0

    def test_drain_after_close_is_empty(self, clock: Clock) -> None:
        buffer = BoundedBuffer(max_items=10, max_age_seconds=100.0, now=clock)
        buffer.push("a")
        buffer.close()
        assert buffer.drain() == ()

    def test_purge_does_not_latch(self, clock: Clock) -> None:
        """Purge and close are different operations; a revocation purges."""
        buffer = BoundedBuffer(max_items=10, max_age_seconds=100.0, now=clock)
        buffer.push("a")
        buffer.purge()
        assert buffer.is_closed is False
        buffer.push("b")
        assert len(buffer) == 1

    def test_there_is_no_reopen(self, clock: Clock) -> None:
        buffer = BoundedBuffer(max_items=10, max_age_seconds=100.0, now=clock)
        assert not hasattr(buffer, "reopen")
