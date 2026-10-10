"""Session lifecycle (slice S1.2).

A session owns one meeting's consent ledger, its participant mapping and its
media gate. Nothing crosses a session boundary: a new session gets a new
ledger, so "consent is not inherited" is a consequence of the object graph
rather than a rule someone has to remember.

The lifecycle is deliberately small - ``CREATED -> ANNOUNCING -> ACTIVE ->
CLOSED`` - because every state is a state in which some code will ask "may I
process this?", and each one is a chance to answer wrongly. Media is only
expected in ``ACTIVE``.

Late join is the case the handoff document leaves open between two designs (A1
circuit breaker, A3 admission control). This module supports **both** behind
one method and chooses **neither**: with no decision recorded, a participant
arriving mid-session closes the gate. That is the fail-closed reading, and it
is not a vote for A1 - A1 additionally leaves the meeting and stops
reconnecting, which is a product decision this module does not make.
"""

from __future__ import annotations

import enum
from collections.abc import Callable, Iterable
from contextlib import suppress
from dataclasses import dataclass, field

from meetai.consent import ConsentKey, ConsentLedger, ConsentRecord
from meetai.errors import MeetAIError, PendingDecisionError
from meetai.media_gate import BoundedBuffer, MediaGate
from meetai.policy import ConsentScope, LateJoinPolicy

DISCLOSURE_TEXT = "Minh la MeetAI, tro ly AI cua Son."
"""The fixed self-introduction.

Required by the handoff document and kept as a constant so it cannot drift
between the text channel, the spoken form and the UI. Unaccented because it
also goes to a terminal; the web UI renders the accented form from its own
template.
"""


class SessionState(enum.Enum):
    """Where a session is in its life.

    Not ``str``-mixed, for the same reason as every other enum here.
    """

    CREATED = "created"
    ANNOUNCING = "announcing"
    ACTIVE = "active"
    CLOSED = "closed"

    @property
    def expects_media(self) -> bool:
        """Whether audio is expected in this state.

        Exactly one state qualifies, written as an identity check so a state
        added later is excluded by default.
        """
        return self is SessionState.ACTIVE


class SessionLifecycleError(MeetAIError):
    """An operation did not match the session's state."""


@dataclass(frozen=True, slots=True)
class PurgeResult:
    """What a scope purge discarded. Counts only - never what was discarded."""

    participant: str
    scopes: tuple[str, ...]
    buffered_items_dropped: int
    tasks_cancelled: int
    gate_closed: bool


@dataclass
class Session:
    """One meeting.

    ``late_join_policy`` comes from configuration and may be
    ``PENDING_DECISION``, which is the default. In that case
    :meth:`participant_joined` closes the gate rather than guessing, and
    :meth:`require_late_join_decision` is available for a caller that would
    rather fail loudly than degrade.
    """

    session_id: str
    ledger: ConsentLedger
    notice_version: str
    policy_allows_media: Callable[[], bool]
    late_join_policy: LateJoinPolicy = LateJoinPolicy.PENDING_DECISION
    buffer_max_items: int = 256
    buffer_max_age_seconds: float = 5.0
    _state: SessionState = SessionState.CREATED
    _participants: set[str] = field(default_factory=set, repr=False)
    _buffers: dict[str, BoundedBuffer] = field(default_factory=dict, repr=False)
    _cancellations: list[Callable[[], None]] = field(default_factory=list, repr=False)
    _gate: MediaGate | None = field(default=None, repr=False)

    def __post_init__(self) -> None:
        if self.ledger.session_id != self.session_id:
            raise SessionLifecycleError(
                f"ledger thuoc phien {self.ledger.session_id}, khong phai {self.session_id}"
            )

    # ------------------------------------------------------------------ #
    # State
    # ------------------------------------------------------------------ #

    @property
    def state(self) -> SessionState:
        return self._state

    @property
    def gate(self) -> MediaGate:
        """The media gate, created on first access.

        Lazily built so it can capture ``session_is_active`` as a callable that
        reads the live state rather than a snapshot.
        """
        if self._gate is None:
            self._gate = MediaGate(
                ledger=self.ledger,
                notice_version=self.notice_version,
                policy_allows_media=self.policy_allows_media,
                session_is_active=lambda: self._state.expects_media,
            )
        return self._gate

    @property
    def participants(self) -> frozenset[str]:
        """Known participant handles. Opaque handles, never display names."""
        return frozenset(self._participants)

    def status(self) -> dict[str, object]:
        """Metadata-only snapshot for a log line or the status UI."""
        return {
            "session_id": self.session_id,
            "state": self._state.value,
            "generation": self.ledger.generation,
            "participant_count": len(self._participants),
            "gate_closed": self.gate.is_closed,
            "allowed_count": self.gate.allowed_count,
            "rejection_counts": self.gate.rejection_counts,
            "late_join_policy": self.late_join_policy.value,
        }

    # ------------------------------------------------------------------ #
    # Lifecycle
    # ------------------------------------------------------------------ #

    def begin_announcing(self, participants: Iterable[str]) -> str:
        """Enter ``ANNOUNCING`` and register the participants present.

        Returns the disclosure text the caller must deliver. The session cannot
        become active without passing through here, so there is no path to
        processing media without a disclosure step having happened.
        """
        self._require_state(SessionState.CREATED, "begin_announcing")
        self._participants.update(participants)
        for participant in self._participants:
            self.ledger.announce(self._key(participant, ConsentScope.LIVE_MEDIA))
        self._state = SessionState.ANNOUNCING
        return DISCLOSURE_TEXT

    def activate(self) -> None:
        """Enter ``ACTIVE``.

        Refuses while the operator's media policy is unresolved. Letting a
        session go active and relying on the gate to refuse every frame would
        work, but it would also display as a running session that silently
        processes nothing - which reads as a bug rather than as a pending
        decision.
        """
        self._require_state(SessionState.ANNOUNCING, "activate")
        if not self.policy_allows_media():
            raise PendingDecisionError(
                "khong the activate phien khi policy xu ly media chua duoc chot"
            )
        self._state = SessionState.ACTIVE

    def close(self) -> PurgeResult:
        """Close the gate, invalidate outstanding work, cancel, purge, end.

        The order is the point: closing the gate and bumping the generation are
        synchronous and immediate, while cancellation is neither.

        The generation bump was missing, and its absence made this method
        *weaker* than :meth:`revoke` - which is backwards for something called
        a kill. A downstream stage re-checking permission has two places to
        ask: this gate object, or the ledger directly. Closing the gate answers
        only the first, so a stage that captured a generation and validates
        against the ledger was refused by a revocation and **not** by a close.

        ``buffer.close()`` rather than ``purge()`` for the same reason: clearing
        the session's dict drops the session's reference, but a consumer holding
        the buffer object could still push into it.
        """
        self.gate.close()
        self.ledger.invalidate_outstanding_work()
        cancelled = self._run_cancellations()
        dropped = sum(buffer.close() for buffer in self._buffers.values())
        self._buffers.clear()
        self._state = SessionState.CLOSED
        return PurgeResult(
            participant="*",
            scopes=tuple(scope.value for scope in ConsentScope),
            buffered_items_dropped=dropped,
            tasks_cancelled=cancelled,
            # Observed, not asserted. A status field the UI renders should be a
            # measurement; the literal `True` here was correct only because
            # `gate.close()` happened to be four lines above it.
            gate_closed=self.gate.is_closed,
        )

    # ------------------------------------------------------------------ #
    # Participants
    # ------------------------------------------------------------------ #

    def participant_joined(self, participant: str) -> GateOutcome:
        """Handle someone arriving.

        Before the session is active this is just registration. Once active it
        is a late join, and what should happen is an open product decision
        (A1 versus A3). With no decision recorded the gate closes - the
        fail-closed reading - and the caller is told why rather than being left
        to infer it from frames stopping.
        """
        if self._state is SessionState.CLOSED:
            raise SessionLifecycleError("khong the tham gia phien da dong")

        self._participants.add(participant)

        if not self._state.expects_media:
            self.ledger.announce(self._key(participant, ConsentScope.LIVE_MEDIA))
            return GateOutcome(gate_closed=False, reason="registered_before_active")

        if self.late_join_policy is LateJoinPolicy.A3_ADMISSION_CONTROL:
            # Admission control: the newcomer waits outside until the host
            # readmits them, so the running session is not interrupted and no
            # unconsented audio is processed in the meantime.
            self.gate.close()
            return GateOutcome(gate_closed=True, reason="awaiting_admission")

        if self.late_join_policy is LateJoinPolicy.A1_CIRCUIT_BREAKER:
            # Circuit breaker: tear the pipeline down. Leaving the meeting and
            # suppressing reconnect is the platform adapter's job, not this
            # module's, so the caller is told the gate tripped.
            self.gate.close()
            self._run_cancellations()
            return GateOutcome(gate_closed=True, reason="circuit_breaker_tripped")

        # PENDING_DECISION. Close, and say so.
        self.gate.close()
        return GateOutcome(gate_closed=True, reason="late_join_policy_pending")

    def require_late_join_decision(self) -> None:
        """Raise if the late-join design has not been chosen.

        For a caller that prefers a loud failure to a degraded session. The
        default path does not call it: refusing to start at all would be a
        stronger claim than the fail-closed default needs to make.
        """
        if not self.late_join_policy:
            raise PendingDecisionError(
                "late_join_policy van la pending_decision: chua chon giua "
                "A1 circuit breaker va A3 admission control"
            )

    # ------------------------------------------------------------------ #
    # Revocation
    # ------------------------------------------------------------------ #

    def revoke(self, participant: str) -> PurgeResult:
        """Withdraw a participant's consent and purge what it covered.

        Ordering, which is the substance of this method:

        1. ``ledger.revoke_all`` bumps the generation, so every in-flight task
           that re-checks before emitting is refused **from this instant**.
        2. Outstanding work is cancelled.
        3. Buffers are purged.

        Doing (2) or (3) first would leave a window in which a task that had
        already passed its check could still emit.
        """
        records = self.ledger.revoke_all(participant)
        cancelled = self._run_cancellations()
        buffer = self._buffers.pop(participant, None)
        dropped = buffer.purge() if buffer is not None else 0
        return PurgeResult(
            participant=participant,
            scopes=tuple(sorted({r.key.scope.value for r in records})),
            buffered_items_dropped=dropped,
            tasks_cancelled=cancelled,
            gate_closed=self.gate.is_closed,
        )

    def register_cancellation(self, cancel: Callable[[], None]) -> None:
        """Register a callback that aborts one piece of outstanding work.

        A callback rather than a task handle so this module stays independent
        of any concurrency library - asyncio, threads or a future queue all
        reduce to "call this to stop".
        """
        self._cancellations.append(cancel)

    # ------------------------------------------------------------------ #
    # Media
    # ------------------------------------------------------------------ #

    def buffer_for(self, participant: str) -> BoundedBuffer:
        """The bounded buffer for one participant, created on demand.

        **A buffer minted after :meth:`close` is born closed.** Measured: it
        used to be born open, and it accepted audio - ``buffer_for(x).push(..)``
        after a close retained a frame and handed it back from ``drain()``.

        That defeated the care :meth:`close` takes. It calls ``buffer.close()``
        rather than clearing the dict precisely so a consumer *holding* a
        buffer cannot push into it after a kill - but clearing the dict is what
        then let the next caller mint a fresh, open one. The holder was
        protected and the late arriver was not.

        The check is on the session state rather than on a flag of its own, so
        there is no second thing to keep in sync, and ``CLOSED`` is terminal
        and unreachable in reverse.
        """
        if participant not in self._buffers:
            buffer = BoundedBuffer(
                max_items=self.buffer_max_items,
                max_age_seconds=self.buffer_max_age_seconds,
                now=self.ledger.now,
            )
            if self._state is SessionState.CLOSED:
                buffer.close()
            self._buffers[participant] = buffer
        return self._buffers[participant]

    def accept_frame(
        self,
        *,
        participant: str | None,
        generation: int,
        frame: object,
        scope: ConsentScope = ConsentScope.LIVE_MEDIA,
    ) -> bool:
        """Offer one frame to the pipeline. Returns whether it was accepted.

        The gate runs **before** the frame is buffered, so a rejected frame is
        never stored anywhere - which is what "dropped before ASR" has to mean
        if it is to be worth anything. An unmapped speaker in particular never
        gets a buffer created for them.
        """
        decision = self.gate.evaluate(
            participant=participant, generation=generation, scope=scope
        )
        if not decision.allowed:
            return False
        if participant is None:
            # Unreachable: the gate rejects an unmapped speaker above. Kept as
            # a real branch rather than an assert so the refusal survives
            # `python -O`, and so no buffer is ever created for None.
            return False
        self.buffer_for(participant).push(frame)
        return True

    # ------------------------------------------------------------------ #
    # Internals
    # ------------------------------------------------------------------ #

    def _run_cancellations(self) -> int:
        """Invoke and clear every cancellation callback.

        One callback raising must not prevent the others from running: a
        half-cancelled revocation is worse than a noisy one. Exceptions are
        swallowed here because there is no safe way to re-raise during a
        teardown whose whole purpose is to stop things.
        """
        callbacks, self._cancellations = self._cancellations, []
        for cancel in callbacks:
            # Swallowed deliberately: there is no safe way to re-raise during a
            # teardown whose whole purpose is to stop things.
            with suppress(Exception):
                cancel()
        return len(callbacks)

    def _key(self, participant: str, scope: ConsentScope) -> ConsentKey:
        return ConsentKey(
            session_id=self.session_id,
            participant=participant,
            scope=scope,
            notice_version=self.notice_version,
        )

    def _require_state(self, expected: SessionState, action: str) -> None:
        if self._state is not expected:
            raise SessionLifecycleError(
                f"{action} can trang thai {expected.value}, dang o {self._state.value}"
            )


@dataclass(frozen=True, slots=True)
class GateOutcome:
    """What a participant event did to the gate, and why.

    ``reason`` is a stable identifier for logs and tests, not prose, so a test
    can assert on the decision rather than on wording.
    """

    gate_closed: bool
    reason: str


__all__ = [
    "DISCLOSURE_TEXT",
    "ConsentRecord",
    "GateOutcome",
    "PurgeResult",
    "Session",
    "SessionLifecycleError",
    "SessionState",
]
