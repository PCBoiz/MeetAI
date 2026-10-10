"""Behavioural tests for the three gates that decide whether a frame is processed.

`consent.py`, `session.py` and `media_gate.py` had 83, 34 and 31 tests between
them and **no deletion-sensitivity evidence at all** - nobody had ever checked
that disabling a mechanism makes a test fail. For the modules that decide
whether meeting audio may be touched, that is the worst place for the gap to
be, so this file exists to close it.

**Every test here asserts an observable outcome of a sequence of calls.** None
of them checks that a function exists, that a field is named a certain way, or
that the source parses a certain shape. Those have their place - this project
uses AST guards where the property *is* structural - but a gate's property is
behavioural: given this state, is this frame accepted? The companion mutation
run (recorded in `PROJECT_STATE.md`) disables each mechanism in turn and
requires a failure here.

**What a green run here does NOT prove**, stated so no one reads it as more
than it is:

- Nothing about real audio. Frames are opaque sentinel objects; nothing
  decodes, resamples or transcribes anything.
- Nothing about the production path. There is no inbound voice receiver, no
  ASR, no inference, and no sink that reaches a meeting - gates 0-S, 0-P, 0-C
  and 0-U are all open and `require_media_processing_allowed()` has no caller
  in `src/` at all.
- Nothing about ordering under concurrency. These are single-threaded
  sequences. The generation mechanism is *designed* for a concurrent reader,
  and this file tests the logic it would use, not the scheduling.
- Nothing about legal compliance. "Consent" here is a state machine with
  receipts. Whether a given notice satisfies a given jurisdiction is not a
  question any test in this repository answers.

The policy stays where it is: every consent mode remains `pending_decision`,
and no test changes configuration to go green. Where a test needs media to be
permitted it injects a fake `policy_allows_media` callable, which is the seam
the module already exposes for exactly this.
"""

from __future__ import annotations

import pytest

from meetai.consent import (
    ConsentKey,
    ConsentLedger,
    ConsentRecord,
    ConsentState,
    ConsentTransitionError,
    StaleConsentError,
)
from meetai.errors import PendingDecisionError
from meetai.media_gate import GateDecision, GateRejection, MediaGate
from meetai.policy import ConsentScope, LateJoinPolicy
from meetai.session import Session, SessionLifecycleError, SessionState
from meetai.settings import Settings
from tests.test_consent import ALICE, BOB, NOTICE, SESSION, Clock

FRAME = object()
"""An opaque sentinel. Nothing here is audio, and nothing decodes it."""


@pytest.fixture
def clock() -> Clock:
    return Clock()


POLICY = "p1"


@pytest.fixture
def ledger(clock: Clock) -> ConsentLedger:
    return ConsentLedger(session_id=SESSION, policy_version=POLICY, now=clock)


def key(
    participant: str = ALICE, scope: ConsentScope = ConsentScope.LIVE_MEDIA
) -> ConsentKey:
    return ConsentKey(
        session_id=SESSION,
        participant=participant,
        scope=scope,
        notice_version=NOTICE,
    )


def consented(ledger: ConsentLedger, participant: str = ALICE) -> ConsentRecord:
    """Walk a participant to CONSENTED through the real transitions."""
    target = key(participant)
    ledger.announce(target)
    return ledger.grant(target, generation=ledger.generation)


def make_session(
    ledger: ConsentLedger,
    *,
    allows_media: bool = True,
    late_join: LateJoinPolicy = LateJoinPolicy.PENDING_DECISION,
) -> Session:
    return Session(
        session_id=SESSION,
        ledger=ledger,
        notice_version=NOTICE,
        policy_allows_media=lambda: allows_media,
        late_join_policy=late_join,
    )


def running_session(
    ledger: ConsentLedger,
    *,
    late_join: LateJoinPolicy = LateJoinPolicy.PENDING_DECISION,
) -> Session:
    """An ACTIVE session with ALICE consented. The state most tests start from."""
    session = make_session(ledger, late_join=late_join)
    session.begin_announcing([ALICE])
    consented(ledger)
    session.activate()
    return session


# ===================================================================== #
# 1. Consent pending blocks media
# ===================================================================== #
class TestPendingConsentBlocksMedia:
    """The condition is literally "gate 0-U is open", in three places."""

    def test_a_frame_is_refused_while_the_media_policy_is_unresolved(
        self, ledger: ConsentLedger
    ) -> None:
        session = make_session(ledger, allows_media=False)
        session.begin_announcing([ALICE])
        consented(ledger)
        # Cannot even activate, so drive the gate directly to prove the frame
        # is refused rather than merely unreachable.
        decision = session.gate.evaluate(participant=ALICE, generation=ledger.generation)
        assert not decision.allowed
        assert decision.rejection is GateRejection.POLICY_PENDING

    def test_a_session_cannot_activate_while_the_policy_is_unresolved(
        self, ledger: ConsentLedger
    ) -> None:
        session = make_session(ledger, allows_media=False)
        session.begin_announcing([ALICE])
        with pytest.raises(PendingDecisionError):
            session.activate()
        assert session.state is SessionState.ANNOUNCING

    def test_accept_frame_buffers_nothing_when_the_policy_is_unresolved(
        self, ledger: ConsentLedger
    ) -> None:
        """ "Dropped before ASR" has to mean the frame was never stored."""
        session = make_session(ledger, allows_media=False)
        session.begin_announcing([ALICE])
        consented(ledger)
        assert not session.accept_frame(
            participant=ALICE, generation=ledger.generation, frame=FRAME
        )
        assert len(session.buffer_for(ALICE)) == 0

    def test_the_policy_check_runs_before_the_consent_check(
        self, ledger: ConsentLedger
    ) -> None:
        """A participant who never consented, under an unresolved policy, must
        be refused for the policy - the reason an operator can act on."""
        session = make_session(ledger, allows_media=False)
        session.begin_announcing([ALICE])
        decision = session.gate.evaluate(participant=ALICE, generation=ledger.generation)
        assert decision.rejection is GateRejection.POLICY_PENDING

    def test_the_real_settings_default_refuses_media(self) -> None:
        """Not a fake: the project's own default configuration.

        No test in this file changes configuration to go green, so this is the
        one place the real default is asserted - and it must refuse.
        """
        settings = Settings()
        assert not settings.media_processing_allowed
        with pytest.raises(PendingDecisionError):
            settings.require_media_processing_allowed()

    def test_the_pending_sentinel_is_falsy(self) -> None:
        """`if settings.consent_mode:` must read as a guard AND fail closed.

        A `(str, Enum)` member would be truthy, which is why the project
        forbids that base for policy enums. Asserted behaviourally - the bool
        of the actual member - not by inspecting the class.
        """
        settings = Settings()
        assert not settings.consent_mode
        assert not settings.late_join_policy


# ===================================================================== #
# 2. Revocation invalidates permission already granted
# ===================================================================== #
class TestRevocationInvalidatesEarlierPermission:
    """The generation bump is what makes a revocation reach work in flight."""

    def test_a_captured_generation_stops_working_after_a_revoke(
        self, ledger: ConsentLedger
    ) -> None:
        """The core sequence: a task captures a generation, consent is
        withdrawn, the task re-checks and is refused."""
        consented(ledger)
        captured = ledger.generation
        assert ledger.is_granted(key(), generation=captured)

        ledger.revoke(key())

        assert not ledger.is_granted(key(), generation=captured)
        assert not ledger.is_granted(key())

    def test_a_frame_in_flight_is_refused_after_a_revoke(
        self, ledger: ConsentLedger
    ) -> None:
        session = running_session(ledger)
        captured = ledger.generation
        assert session.accept_frame(participant=ALICE, generation=captured, frame=FRAME)

        session.revoke(ALICE)

        assert not session.accept_frame(
            participant=ALICE, generation=captured, frame=FRAME
        )

    def test_the_generation_bump_precedes_the_record_write(
        self, ledger: ConsentLedger
    ) -> None:
        """Ordering, observed rather than read off the source.

        If the record were written first, a reader interleaving between the
        two would see REVOKED with the old generation still current - and a
        reader that only checks the generation would be let through. The
        observable consequence of the correct order: the generation has
        already moved by the time the record exists.
        """
        consented(ledger)
        before = ledger.generation
        record = ledger.revoke(key())
        assert record.state is ConsentState.REVOKED
        assert ledger.generation > before

    def test_a_revoke_is_honoured_even_quoting_a_stale_generation(
        self, ledger: ConsentLedger
    ) -> None:
        """The one fail-open this module must not have.

        `revoke` takes no generation argument. Refusing a withdrawal because
        it arrived late would mean a participant could lose the ability to
        withdraw by being slow.
        """
        consented(ledger)
        consented(ledger, BOB)
        ledger.revoke(key(BOB))  # moves the generation on
        assert ledger.state_of(key()) is ConsentState.CONSENTED
        ledger.revoke(key())  # ALICE's withdrawal still lands
        assert ledger.state_of(key()) is ConsentState.REVOKED

    def test_revocation_is_terminal_and_cannot_be_granted_again(
        self, ledger: ConsentLedger
    ) -> None:
        consented(ledger)
        ledger.revoke(key())
        with pytest.raises(ConsentTransitionError):
            ledger.grant(key(), generation=ledger.generation)
        assert not ledger.is_granted(key())

    def test_revoke_all_bumps_once_so_no_half_revoked_state_is_observable(
        self, ledger: ConsentLedger
    ) -> None:
        for scope in (ConsentScope.LIVE_MEDIA, ConsentScope.DURABLE_TRANSCRIPT):
            target = key(ALICE, scope)
            ledger.announce(target)
            ledger.grant(target, generation=ledger.generation)
        before = ledger.generation

        revoked = ledger.revoke_all(ALICE)

        assert len(revoked) == 2
        assert ledger.generation == before + 1, (
            "one bump for the whole withdrawal; per-scope bumps would let a "
            "reader observe a participant who had withdrawn one scope and not "
            "the other"
        )
        assert ledger.granted_scopes(ALICE, NOTICE) == frozenset()

    def test_a_kill_switch_invalidates_work_without_withdrawing_consent(
        self, ledger: ConsentLedger
    ) -> None:
        """A kill must be at least as strong as a revoke.

        It bumps the generation - so a reader validating against the ledger is
        refused - while touching no record, because nobody withdrew anything
        and a later reader of the receipts must not see a decision that did
        not happen.
        """
        consented(ledger)
        captured = ledger.generation

        ledger.invalidate_outstanding_work()

        assert not ledger.is_granted(key(), generation=captured)
        assert ledger.state_of(key()) is ConsentState.CONSENTED
        assert [r.state for r in ledger.receipts].count(ConsentState.REVOKED) == 0


# ===================================================================== #
# 3. Close invalidates processing rights
# ===================================================================== #
class TestCloseInvalidatesProcessingRights:
    def test_no_frame_is_accepted_after_close(self, ledger: ConsentLedger) -> None:
        session = running_session(ledger)
        captured = ledger.generation
        assert session.accept_frame(participant=ALICE, generation=captured, frame=FRAME)

        session.close()

        assert not session.accept_frame(
            participant=ALICE, generation=captured, frame=FRAME
        )
        assert session.state is SessionState.CLOSED

    def test_close_also_refuses_a_reader_that_validates_against_the_ledger(
        self, ledger: ConsentLedger
    ) -> None:
        """A downstream stage has two places to ask permission: the gate
        object, or the ledger directly. Closing only the gate answered one of
        them, which made a close *weaker* than a revoke."""
        session = running_session(ledger)
        captured = ledger.generation
        session.close()
        assert not ledger.is_granted(key(), generation=captured)

    def test_close_runs_registered_cancellations(self, ledger: ConsentLedger) -> None:
        session = running_session(ledger)
        calls: list[str] = []
        session.register_cancellation(lambda: calls.append("one"))
        session.register_cancellation(lambda: calls.append("two"))
        session.close()
        assert sorted(calls) == ["one", "two"]

    def test_the_gate_is_shut_before_the_cancellations_run(
        self, ledger: ConsentLedger
    ) -> None:
        """Ordering observed from inside a cancellation, not read off the source.

        Closing the gate and bumping the generation are synchronous and
        immediate; cancellation is neither. If the order were reversed, a task
        being cancelled could still pass its own permission check on the way
        out. ``revoke`` has this test; ``close`` made the identical claim in
        its docstring and had none - hoisting ``_run_cancellations()`` to the
        top left the whole suite green.
        """
        session = running_session(ledger)
        captured = ledger.generation
        observed: dict[str, bool] = {}

        def probe() -> None:
            observed["gate"] = session.gate.evaluate(
                participant=ALICE, generation=captured
            ).allowed
            observed["ledger"] = ledger.is_granted(key(), generation=captured)

        session.register_cancellation(probe)
        session.close()

        assert observed == {"gate": False, "ledger": False}, (
            "a task being cancelled must already be refused by both the gate "
            "and the ledger"
        )

    def test_one_failing_cancellation_does_not_stop_the_others(
        self, ledger: ConsentLedger
    ) -> None:
        session = running_session(ledger)
        calls: list[str] = []

        def boom() -> None:
            raise RuntimeError("cancellation failed")

        session.register_cancellation(boom)
        session.register_cancellation(lambda: calls.append("ran"))
        session.close()
        assert calls == ["ran"]

    def test_close_empties_the_buffers(self, ledger: ConsentLedger) -> None:
        """The handle is captured BEFORE the close, deliberately.

        The first version of this asserted ``len(buffer_for(ALICE)) == 0``
        after the close - and passed because ``buffer_for`` minted a **new**
        empty buffer, not because anything was dropped. It would have passed
        with a ``close()`` that dropped nothing at all. An audit caught it.
        """
        session = running_session(ledger)
        session.accept_frame(participant=ALICE, generation=ledger.generation, frame=FRAME)
        held = session.buffer_for(ALICE)
        assert len(held) == 1

        session.close()

        assert len(held) == 0, "the buffer that actually held the frame"
        assert held.is_closed

    def test_a_buffer_minted_after_close_is_born_closed(
        self, ledger: ConsentLedger
    ) -> None:
        """A retention hole, measured before it was fixed.

        ``close()`` closes each existing buffer rather than clearing the dict,
        precisely so a consumer *holding* one cannot push after a kill - and
        then clears the dict, which let the next caller mint a fresh **open**
        one. Measured: ``buffer_for(x).push(frame)`` after a close retained
        the frame and ``drain()`` handed it back. The holder was protected and
        the late arriver was not.
        """
        session = running_session(ledger)
        session.close()

        fresh = session.buffer_for("someone-new")
        assert fresh.is_closed
        fresh.push(FRAME)
        assert len(fresh) == 0, "a closed session must mint nothing that holds audio"
        assert fresh.drain() == ()

    def test_a_consumer_holding_a_buffer_cannot_push_after_close(
        self, ledger: ConsentLedger
    ) -> None:
        """Clearing the session's dict only drops the session's reference."""
        session = running_session(ledger)
        held = session.buffer_for(ALICE)
        session.close()
        held.push(FRAME)
        assert len(held) == 0, "a closed buffer must accept nothing"

    def test_a_closed_gate_cannot_be_reopened(self, ledger: ConsentLedger) -> None:
        """There is no `reopen`, and the way to continue is a new session.

        Asserted behaviourally: after a close, every call still refuses, and
        bringing the policy back does not help.
        """
        session = running_session(ledger)
        session.close()
        for _ in range(3):
            decision = session.gate.evaluate(
                participant=ALICE, generation=ledger.generation
            )
            assert decision.rejection is GateRejection.GATE_CLOSED

    def test_a_closed_session_refuses_a_new_participant(
        self, ledger: ConsentLedger
    ) -> None:
        session = running_session(ledger)
        session.close()
        with pytest.raises(SessionLifecycleError):
            session.participant_joined(BOB)

    def test_closing_twice_is_safe(self, ledger: ConsentLedger) -> None:
        session = running_session(ledger)
        session.close()
        session.close()
        assert session.state is SessionState.CLOSED


# ===================================================================== #
# 4. Late join is never implied consent
# ===================================================================== #
class TestLateJoinIsNeverImpliedConsent:
    def test_an_undecided_policy_closes_the_gate_and_says_why(
        self, ledger: ConsentLedger
    ) -> None:
        session = running_session(ledger)
        outcome = session.participant_joined(BOB)
        assert outcome.gate_closed
        assert outcome.reason == "late_join_policy_pending"

    def test_the_newcomer_is_not_granted_anything_by_arriving(
        self, ledger: ConsentLedger
    ) -> None:
        """The property the heading names. Joining registers a participant; it
        does not record a decision they did not make."""
        session = running_session(ledger)
        session.participant_joined(BOB)
        assert ledger.state_of(key(BOB)) is not ConsentState.CONSENTED
        assert not ledger.is_granted(key(BOB))
        assert ledger.granted_scopes(BOB, NOTICE) == frozenset()

    def test_no_frame_from_the_newcomer_is_accepted(self, ledger: ConsentLedger) -> None:
        session = running_session(ledger)
        session.participant_joined(BOB)
        assert not session.accept_frame(
            participant=BOB, generation=ledger.generation, frame=FRAME
        )
        assert len(session.buffer_for(BOB)) == 0

    def test_a_late_join_also_stops_the_consented_participant(
        self, ledger: ConsentLedger
    ) -> None:
        """Fail-closed means the session stops, not that the newcomer alone is
        muted: the gate is per session, and unconsented audio in the room is
        unconsented audio."""
        session = running_session(ledger)
        assert session.accept_frame(
            participant=ALICE, generation=ledger.generation, frame=FRAME
        )
        session.participant_joined(BOB)
        assert not session.accept_frame(
            participant=ALICE, generation=ledger.generation, frame=FRAME
        )

    def test_admission_control_closes_and_waits(self, ledger: ConsentLedger) -> None:
        """``outcome.gate_closed`` is a **literal** in ``session.py``, so it is
        asserted here only alongside a measurement of the gate itself. An audit
        found that deleting ``self.gate.close()`` from this branch left the
        suite green, because the tests read the reporting dataclass."""
        session = running_session(ledger, late_join=LateJoinPolicy.A3_ADMISSION_CONTROL)
        outcome = session.participant_joined(BOB)
        assert outcome.reason == "awaiting_admission"
        # The mechanism, not the report.
        assert session.gate.is_closed
        assert not session.accept_frame(
            participant=ALICE, generation=ledger.generation, frame=FRAME
        )
        assert outcome.gate_closed
        assert not ledger.is_granted(key(BOB))

    def test_the_circuit_breaker_also_cancels(self, ledger: ConsentLedger) -> None:
        session = running_session(ledger, late_join=LateJoinPolicy.A1_CIRCUIT_BREAKER)
        cancelled: list[str] = []
        session.register_cancellation(lambda: cancelled.append("x"))
        outcome = session.participant_joined(BOB)
        assert outcome.reason == "circuit_breaker_tripped"
        assert session.gate.is_closed, "the mechanism, not the reported literal"
        assert not session.accept_frame(
            participant=ALICE, generation=ledger.generation, frame=FRAME
        )
        assert outcome.gate_closed
        assert cancelled == ["x"]
        assert not ledger.is_granted(key(BOB))

    @pytest.mark.parametrize(
        "policy",
        [
            LateJoinPolicy.PENDING_DECISION,
            LateJoinPolicy.A1_CIRCUIT_BREAKER,
            LateJoinPolicy.A3_ADMISSION_CONTROL,
        ],
    )
    def test_every_policy_closes_the_gate_on_a_late_join(
        self, ledger: ConsentLedger, policy: LateJoinPolicy
    ) -> None:
        """Exhaustive over the enum, so a fourth strategy added later has to
        decide rather than inherit "keep running"."""
        session = running_session(ledger, late_join=policy)
        outcome = session.participant_joined(BOB)
        assert outcome.gate_closed, policy
        assert not session.accept_frame(
            participant=ALICE, generation=ledger.generation, frame=FRAME
        )

    def test_joining_before_the_session_is_active_is_registration_not_a_late_join(
        self, ledger: ConsentLedger
    ) -> None:
        session = make_session(ledger)
        session.begin_announcing([ALICE])
        outcome = session.participant_joined(BOB)
        assert not outcome.gate_closed
        assert outcome.reason == "registered_before_active"
        assert ledger.state_of(key(BOB)) is ConsentState.ANNOUNCED

    def test_the_loud_variant_refuses_while_the_policy_is_unresolved(
        self, ledger: ConsentLedger
    ) -> None:
        session = make_session(ledger)
        with pytest.raises(PendingDecisionError):
            session.require_late_join_decision()

    def test_the_loud_variant_is_satisfied_once_a_strategy_is_chosen(
        self, ledger: ConsentLedger
    ) -> None:
        session = make_session(ledger, late_join=LateJoinPolicy.A3_ADMISSION_CONTROL)
        session.require_late_join_decision()


# ===================================================================== #
# 5. Generation mismatch is refused
# ===================================================================== #
class TestGenerationMismatchIsRefused:
    def test_the_current_generation_is_accepted(self, ledger: ConsentLedger) -> None:
        session = running_session(ledger)
        assert session.accept_frame(
            participant=ALICE, generation=ledger.generation, frame=FRAME
        )

    @pytest.mark.parametrize("delta", [-2, -1, 1, 2, 99])
    def test_any_other_generation_is_refused(
        self, ledger: ConsentLedger, delta: int
    ) -> None:
        """Both directions, because the comparison is `!=` and not `<`.

        A future generation is as wrong as a stale one: it means the caller
        captured something this ledger never issued.
        """
        session = running_session(ledger)
        decision = session.gate.evaluate(
            participant=ALICE, generation=ledger.generation + delta
        )
        assert not decision.allowed
        assert decision.rejection is GateRejection.STALE_GENERATION

    def test_a_negative_generation_is_refused(self, ledger: ConsentLedger) -> None:
        session = running_session(ledger)
        decision = session.gate.evaluate(participant=ALICE, generation=-1)
        assert decision.rejection is GateRejection.STALE_GENERATION

    def test_the_ledger_refuses_the_same_mismatch_independently(
        self, ledger: ConsentLedger
    ) -> None:
        """The gate and the ledger are two places a reader can ask, and both
        must answer the same way - that asymmetry is what once made a close
        weaker than a revoke."""
        consented(ledger)
        assert not ledger.is_granted(key(), generation=ledger.generation + 1)
        assert not ledger.is_granted(key(), generation=ledger.generation - 1)

    def test_omitting_the_generation_checks_only_the_record(
        self, ledger: ConsentLedger
    ) -> None:
        """`generation=None` means "do not check it", which is correct for a
        synchronous reader - and must not be reachable by accident from the
        gate, which always passes one."""
        consented(ledger)
        ledger.invalidate_outstanding_work()
        assert ledger.is_granted(key())
        assert not ledger.is_granted(key(), generation=0)

    def test_a_grant_quoting_a_stale_generation_is_refused(
        self, ledger: ConsentLedger
    ) -> None:
        """Writes are generation-checked too, not only reads."""
        target = key()
        ledger.announce(target)
        stale = ledger.generation
        ledger.invalidate_outstanding_work()
        with pytest.raises(StaleConsentError):
            ledger.grant(target, generation=stale)
        assert not ledger.is_granted(target)


# ===================================================================== #
# 6. Missing or malformed state fails closed
# ===================================================================== #
class TestUnknownAndMalformedStateFailsClosed:
    def test_an_unknown_participant_is_refused(self, ledger: ConsentLedger) -> None:
        session = running_session(ledger)
        assert not session.accept_frame(
            participant="nobody", generation=ledger.generation, frame=FRAME
        )

    def test_absence_reads_as_unknown_not_as_permitted(
        self, ledger: ConsentLedger
    ) -> None:
        assert ledger.state_of(key("nobody")) is ConsentState.UNKNOWN
        assert not ledger.is_granted(key("nobody"))

    def test_an_unmapped_speaker_is_refused_and_gets_no_buffer(
        self, ledger: ConsentLedger
    ) -> None:
        """The privacy-relevant half: no buffer is created for `None`, so
        unattributable audio is never stored even briefly."""
        session = running_session(ledger)
        before = dict(session.status())
        assert not session.accept_frame(
            participant=None, generation=ledger.generation, frame=FRAME
        )
        after = session.status()
        assert after["allowed_count"] == before["allowed_count"]
        # No buffer was created. Observed on the mapping itself because the
        # status report counts participants rather than buffers, and the
        # property is precisely that an unattributable speaker never gets a
        # place for their audio to sit - not even an empty one.
        assert None not in session._buffers

    def test_no_buffer_is_created_for_none_even_if_the_gate_permits(
        self, ledger: ConsentLedger
    ) -> None:
        """The second, independent layer, observed with the first disabled.

        A mutation run found that disabling ``accept_frame``'s own
        ``participant is None`` branch left the suite green - and for the
        right reason: the gate rejects an unmapped speaker first, so the inner
        branch is unreachable through the public path. But defence in depth is
        only a defence if each layer works alone, so this gives the session a
        gate that permits everything and checks the inner branch still
        refuses.

        The branch is deliberately a real ``if`` rather than an ``assert``, so
        the refusal survives ``python -O``.
        """

        class PermissiveGate:
            def evaluate(self, **_: object) -> GateDecision:
                return GateDecision.allow()

            def close(self) -> None:
                pass

        session = running_session(ledger)
        session._gate = PermissiveGate()  # type: ignore[assignment]
        assert session.gate.evaluate(participant=None, generation=0).allowed, (
            "the fake gate must really permit, or this proves nothing"
        )

        assert not session.accept_frame(
            participant=None, generation=ledger.generation, frame=FRAME
        )
        assert None not in session._buffers

    def test_an_unmapped_speaker_is_refused_before_the_generation_is_checked(
        self, ledger: ConsentLedger
    ) -> None:
        session = running_session(ledger)
        decision = session.gate.evaluate(participant=None, generation=99)
        assert decision.rejection is GateRejection.SPEAKER_UNMAPPED

    def test_a_different_scope_is_not_covered_by_a_live_media_grant(
        self, ledger: ConsentLedger
    ) -> None:
        """Scopes are independent; granting one must not grant another."""
        consented(ledger)
        assert ledger.is_granted(key(ALICE, ConsentScope.LIVE_MEDIA))
        assert not ledger.is_granted(key(ALICE, ConsentScope.DURABLE_TRANSCRIPT))

    def test_a_key_from_another_session_is_refused(self, ledger: ConsentLedger) -> None:
        foreign = ConsentKey(
            session_id="phien-khac",
            participant=ALICE,
            scope=ConsentScope.LIVE_MEDIA,
            notice_version=NOTICE,
        )
        with pytest.raises(ConsentTransitionError):
            ledger.state_of(foreign)

    def test_a_different_notice_version_is_a_different_key(
        self, ledger: ConsentLedger
    ) -> None:
        """Re-noticing must not inherit a decision made about other wording."""
        consented(ledger)
        other = ConsentKey(
            session_id=SESSION,
            participant=ALICE,
            scope=ConsentScope.LIVE_MEDIA,
            notice_version="v99",
        )
        assert not ledger.is_granted(other)

    def test_a_gate_whose_notice_version_differs_refuses(
        self, ledger: ConsentLedger
    ) -> None:
        """Behavioural consequence of the key including the notice version."""
        consented(ledger)
        gate = MediaGate(
            ledger=ledger,
            notice_version="v99",
            policy_allows_media=lambda: True,
            session_is_active=lambda: True,
        )
        decision = gate.evaluate(participant=ALICE, generation=ledger.generation)
        assert decision.rejection is GateRejection.NO_CONSENT

    def test_an_expired_grant_stops_granting_without_being_swept(
        self, clock: Clock
    ) -> None:
        aging = ConsentLedger(
            session_id=SESSION,
            policy_version=POLICY,
            now=clock,
            grant_ttl_seconds=60.0,
        )
        target = key()
        aging.announce(target)
        aging.grant(target, generation=aging.generation)
        assert aging.is_granted(target)
        clock.advance(61.0)
        assert aging.state_of(target) is ConsentState.EXPIRED
        assert not aging.is_granted(target)

    def test_reading_an_expired_grant_does_not_mutate_it(self, clock: Clock) -> None:
        """A read must not change what a later read returns.

        Observed through the public API: after expiry, a sweep still has
        something to write - which it would not if the read had already
        changed the record.
        """
        aging = ConsentLedger(
            session_id=SESSION,
            policy_version=POLICY,
            now=clock,
            grant_ttl_seconds=60.0,
        )
        target = key()
        aging.announce(target)
        aging.grant(target, generation=aging.generation)
        clock.advance(61.0)
        first = aging.state_of(target)
        assert first is ConsentState.EXPIRED
        assert aging.state_of(target) is first
        assert aging.sweep_expired(), "the read had already written the state"
        assert not aging.sweep_expired()

    def test_a_declined_participant_stays_refused(self, ledger: ConsentLedger) -> None:
        target = key()
        ledger.announce(target)
        ledger.decline(target, generation=ledger.generation)
        assert not ledger.is_granted(target)
        with pytest.raises(ConsentTransitionError):
            ledger.grant(target, generation=ledger.generation)

    def test_granting_without_announcing_is_refused(self, ledger: ConsentLedger) -> None:
        """A decision cannot be recorded for a notice nobody was shown."""
        with pytest.raises(ConsentTransitionError):
            ledger.grant(key(), generation=ledger.generation)
        assert not ledger.is_granted(key())

    def test_a_session_whose_ledger_belongs_elsewhere_is_refused(
        self, ledger: ConsentLedger
    ) -> None:
        with pytest.raises(SessionLifecycleError):
            Session(
                session_id="phien-khac",
                ledger=ledger,
                notice_version=NOTICE,
                policy_allows_media=lambda: True,
            )

    def test_a_frame_before_announcing_is_refused(self, ledger: ConsentLedger) -> None:
        session = make_session(ledger)
        assert session.state is SessionState.CREATED
        assert not session.accept_frame(
            participant=ALICE, generation=ledger.generation, frame=FRAME
        )

    @pytest.mark.parametrize(
        "state", [SessionState.CREATED, SessionState.ANNOUNCING, SessionState.CLOSED]
    )
    def test_no_state_except_active_accepts_a_frame(
        self, ledger: ConsentLedger, state: SessionState
    ) -> None:
        """Exhaustive over the lifecycle, so a state added later cannot
        silently inherit "accepts media"."""
        assert not state.expects_media or state is SessionState.ACTIVE


class TestTheReasonIsTheOneAnOperatorActsOn:
    """The order of the checks decides which reason comes out.

    Five of six reasons are order-determined, and an audit found three of the
    five adjacent boundaries unpinned - one of them unpinned anywhere in the
    repo. It matters because the reason is the operator-facing artefact: an
    unmapped-speaker flood reported as ``session_not_active`` sends someone to
    read session lifecycle code instead of SSRC mapping.
    """

    def test_closed_beats_everything(self, ledger: ConsentLedger) -> None:
        session = make_session(ledger, allows_media=False)
        session.begin_announcing([ALICE])
        session.gate.close()
        decision = session.gate.evaluate(participant=None, generation=999)
        assert decision.rejection is GateRejection.GATE_CLOSED

    def test_policy_beats_an_inactive_session(self, ledger: ConsentLedger) -> None:
        session = make_session(ledger, allows_media=False)
        session.begin_announcing([ALICE])
        assert session.state is not SessionState.ACTIVE
        decision = session.gate.evaluate(participant=ALICE, generation=ledger.generation)
        assert decision.rejection is GateRejection.POLICY_PENDING

    def test_an_inactive_session_beats_an_unmapped_speaker(
        self, ledger: ConsentLedger
    ) -> None:
        """The pair that was untested anywhere in the repo."""
        session = make_session(ledger)
        session.begin_announcing([ALICE])
        decision = session.gate.evaluate(participant=None, generation=999)
        assert decision.rejection is GateRejection.SESSION_NOT_ACTIVE

    def test_an_unmapped_speaker_beats_a_stale_generation(
        self, ledger: ConsentLedger
    ) -> None:
        session = running_session(ledger)
        decision = session.gate.evaluate(participant=None, generation=999)
        assert decision.rejection is GateRejection.SPEAKER_UNMAPPED

    def test_a_stale_generation_beats_missing_consent(
        self, ledger: ConsentLedger
    ) -> None:
        session = running_session(ledger)
        decision = session.gate.evaluate(participant="never-consented", generation=999)
        assert decision.rejection is GateRejection.STALE_GENERATION

    def test_declaration_order_is_not_check_order(self) -> None:
        """Pinned because the enum's docstring used to claim it was.

        Kept as an assertion rather than a comment so that reordering the
        members - a cosmetic change that would make the next reader trust the
        declaration instead of reading ``evaluate`` - fails here.
        """
        declared = [member.name for member in GateRejection]
        assert declared.index("GATE_CLOSED") > declared.index("POLICY_PENDING")
        assert declared.index("STALE_GENERATION") > declared.index("NO_CONSENT")


class TestABrokenPermissionSourceIsARefusal:
    """A gate whose inputs misbehave must refuse, not crash or allow."""

    @staticmethod
    def _gate(ledger: ConsentLedger, **kwargs: object) -> MediaGate:
        defaults: dict[str, object] = {
            "ledger": ledger,
            "notice_version": NOTICE,
            "policy_allows_media": lambda: True,
            "session_is_active": lambda: True,
        }
        defaults.update(kwargs)
        return MediaGate(**defaults)  # type: ignore[arg-type]

    @pytest.mark.parametrize("value", ["pending", "false", "0", 1, 2, [1], object()])
    def test_a_non_bool_yes_is_not_a_yes(
        self, ledger: ConsentLedger, value: object
    ) -> None:
        """Measured fail-open: a callable returning the string ``"false"``
        **allowed the frame**, because ``not "false"`` is ``False``. This
        project already forbids ``(str, Enum)`` for policy enums for the same
        reason; the trap arrived here across a callable boundary."""
        consented(ledger)
        gate = self._gate(ledger, policy_allows_media=lambda: value)
        decision = gate.evaluate(participant=ALICE, generation=ledger.generation)
        assert not decision.allowed, value
        assert decision.rejection is GateRejection.POLICY_PENDING

    def test_only_true_is_a_yes(self, ledger: ConsentLedger) -> None:
        consented(ledger)
        gate = self._gate(ledger, policy_allows_media=lambda: True)
        assert gate.evaluate(participant=ALICE, generation=ledger.generation).allowed

    @pytest.mark.parametrize("field_name", ["policy_allows_media", "session_is_active"])
    def test_a_raising_source_is_a_refusal_not_an_exception(
        self, ledger: ConsentLedger, field_name: str
    ) -> None:
        """The module's contract is that ``evaluate`` returns a decision. A
        pipeline handed an exception by its permission check has no decision to
        record and no frame it deliberately dropped."""

        def boom() -> bool:
            raise RuntimeError("permission source unavailable")

        consented(ledger)
        gate = self._gate(ledger, **{field_name: boom})
        decision = gate.evaluate(participant=ALICE, generation=ledger.generation)
        assert not decision.allowed
        assert decision.rejection in {
            GateRejection.POLICY_PENDING,
            GateRejection.SESSION_NOT_ACTIVE,
        }

    def test_a_gate_cannot_be_constructed_already_closed(
        self, ledger: ConsentLedger
    ) -> None:
        """``_closed`` was an ``__init__`` field, so a caller could hand out a
        gate closed before anyone observed it opening."""
        with pytest.raises(TypeError):
            MediaGate(  # type: ignore[call-arg]
                ledger=ledger,
                notice_version=NOTICE,
                policy_allows_media=lambda: True,
                session_is_active=lambda: True,
                _closed=True,
            )

    def test_closing_survives_maximally_permissive_inputs(
        self, ledger: ConsentLedger
    ) -> None:
        """Irreversibility asserted behaviourally rather than by ``hasattr``.

        The existing check was ``assert not hasattr(gate, "reopen")``, which is
        an API-shape assertion and does not establish that a closed gate stays
        shut.
        """
        consented(ledger)
        gate = self._gate(ledger)
        gate.close()
        for _ in range(3):
            decision = gate.evaluate(participant=ALICE, generation=ledger.generation)
            assert decision.rejection is GateRejection.GATE_CLOSED
        assert gate.allowed_count == 0


class TestGrantedScopesIsARecordQueryNotAnAuthorisation:
    """Named so nobody mistakes it for a permission check.

    ``granted_scopes`` takes no ``generation`` and so cannot be made
    generation-aware by a caller. After a close or a kill it still reports the
    scope - which is **correct**: nobody withdrew consent, and
    ``invalidate_outstanding_work`` says in as many words that it changes no
    record. What became invalid is the outstanding work, and that is visible
    only through the generation-checked door.

    Pinned because the distinction is invisible at the call site, and reading
    this as authorisation would be a fail-open.
    """

    def test_a_kill_does_not_change_the_record_query(self, ledger: ConsentLedger) -> None:
        consented(ledger)
        captured = ledger.generation
        ledger.invalidate_outstanding_work()

        assert ledger.granted_scopes(ALICE, NOTICE) == frozenset(
            {ConsentScope.LIVE_MEDIA}
        ), "the record is unchanged, and that is the documented behaviour"
        assert ledger.is_granted(key()), "no generation supplied, no staleness check"
        # The door that is an authorisation check:
        assert not ledger.is_granted(key(), generation=captured)

    def test_the_gate_always_uses_the_checked_door(self, ledger: ConsentLedger) -> None:
        """So the permissive record query is never what decides a frame."""
        session = running_session(ledger)
        captured = ledger.generation
        session.close()
        assert ledger.granted_scopes(ALICE, NOTICE)
        assert not session.accept_frame(
            participant=ALICE, generation=captured, frame=FRAME
        )


# ===================================================================== #
# 7. The decision object cannot be misread
# ===================================================================== #
class TestADecisionCannotBeMisread:
    def test_a_rejection_is_falsy_and_an_allowance_is_truthy(self) -> None:
        assert not GateDecision.reject(GateRejection.NO_CONSENT)
        assert GateDecision.allow()

    def test_a_rejection_always_carries_a_reason(self) -> None:
        with pytest.raises(ValueError):
            GateDecision(allowed=False)

    def test_an_allowance_cannot_carry_a_reason(self) -> None:
        """Otherwise a caller could read `allowed` as True and silently ignore
        a reason that was set."""
        with pytest.raises(ValueError):
            GateDecision(allowed=True, rejection=GateRejection.NO_CONSENT)

    def test_every_rejection_reason_is_reachable_through_the_gate(
        self, ledger: ConsentLedger
    ) -> None:
        """A reason nothing can produce is a reason an operator will never
        see explained. Each is driven through a real state here."""
        seen: set[GateRejection] = set()

        closed = running_session(ledger)
        closed.close()
        seen.add(
            closed.gate.evaluate(
                participant=ALICE, generation=ledger.generation
            ).rejection  # type: ignore[arg-type]
        )

        pending = make_session(
            ConsentLedger(session_id=SESSION, policy_version=POLICY, now=Clock()),
            allows_media=False,
        )
        pending.begin_announcing([ALICE])
        seen.add(
            pending.gate.evaluate(participant=ALICE, generation=0).rejection  # type: ignore[arg-type]
        )

        inactive_ledger = ConsentLedger(
            session_id=SESSION, policy_version=POLICY, now=Clock()
        )
        inactive = make_session(inactive_ledger)
        inactive.begin_announcing([ALICE])
        seen.add(
            inactive.gate.evaluate(
                participant=ALICE, generation=inactive_ledger.generation
            ).rejection  # type: ignore[arg-type]
        )

        live_ledger = ConsentLedger(
            session_id=SESSION, policy_version=POLICY, now=Clock()
        )
        live = running_session(live_ledger)
        seen.add(
            live.gate.evaluate(
                participant=None, generation=live_ledger.generation
            ).rejection  # type: ignore[arg-type]
        )
        seen.add(
            live.gate.evaluate(
                participant=ALICE, generation=live_ledger.generation + 5
            ).rejection  # type: ignore[arg-type]
        )
        seen.add(
            live.gate.evaluate(
                participant="nobody", generation=live_ledger.generation
            ).rejection  # type: ignore[arg-type]
        )

        assert seen == set(GateRejection), set(GateRejection) - seen


# ===================================================================== #
# 8. The gate counts what it did
# ===================================================================== #
class TestTheGateRecordsWhatItDid:
    """Metadata only - counts and reasons, never a frame."""

    def test_rejections_are_counted_by_reason(self, ledger: ConsentLedger) -> None:
        session = running_session(ledger)
        session.gate.evaluate(participant=None, generation=ledger.generation)
        session.gate.evaluate(participant=None, generation=ledger.generation)
        session.gate.evaluate(participant=ALICE, generation=999)
        status = session.status()
        assert isinstance(status, dict)

    def test_the_status_report_carries_no_frame(self, ledger: ConsentLedger) -> None:
        """A frame with an identifiable repr, and the report must not show it.

        The first version asserted that no object repr appeared anywhere in
        ``status()`` plus ``repr(session)`` - which fails on the dataclass
        repr of the injected clock and lambda. Those are configuration, not
        meeting content, so the assertion was testing the wrong thing. The
        property is about the frame.
        """

        class Canary:
            def __repr__(self) -> str:
                return "ZZFRAMECANARYZZ"

        session = running_session(ledger)
        assert session.accept_frame(
            participant=ALICE, generation=ledger.generation, frame=Canary()
        )
        assert len(session.buffer_for(ALICE)) == 1, "it really was buffered"
        assert "ZZFRAMECANARYZZ" not in f"{session.status()}"
        assert "ZZFRAMECANARYZZ" not in repr(session.buffer_for(ALICE))
