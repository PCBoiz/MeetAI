"""Consent state machine (slice S1.1).

Consent is keyed on ``(session_id, participant, scope, notice_version)`` and
never inherited across sessions. Four properties carry the safety:

1. **Default deny by absence.** A key with no record is ``UNKNOWN``, and
   ``UNKNOWN`` grants nothing. There is no "assume yes because they are in the
   meeting" path, and no code can ask a question this module answers
   permissively by accident - :meth:`ConsentLedger.is_granted` is the only way
   to ask, and it returns ``False`` for every state but ``CONSENTED``.

2. **Terminal refusals.** ``DECLINED``, ``REVOKED`` and ``EXPIRED`` are terminal
   for the rest of the session. A participant who said no is not asked again by
   a retry loop, and a revocation cannot be undone by a late click.

3. **Generations defeat stale clicks and racing tasks.** The session carries a
   generation counter that increments on every revocation. A grant quotes the
   generation its notice was issued under, so a click that was already in
   flight when someone revoked is rejected rather than applied. Asynchronous
   work quotes the generation it started under and
   :meth:`ConsentLedger.is_granted` rejects it if the session has moved on -
   which is what makes "close the gate before cancelling tasks" implementable.

4. **Receipts carry metadata only.** A receipt records that a decision happened,
   under which notice version and when. It never holds audio or transcript.

This module imports no framework. It is the domain, not an adapter to one.
"""

from __future__ import annotations

import enum
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field, replace

from meetai.errors import MeetAIError
from meetai.policy import ConsentScope


class ConsentState(enum.Enum):
    """Where one consent key stands.

    Deliberately not ``str``-mixed, for the same reason as the policy enums: a
    mixed member is truthy and string-equal, which invites a guard that passes
    on a state meant to block.
    """

    UNKNOWN = "unknown"
    ANNOUNCED = "announced"
    CONSENTED = "consented"
    DECLINED = "declined"
    EXPIRED = "expired"
    REVOKED = "revoked"

    @property
    def is_terminal(self) -> bool:
        """Whether this state cannot change again within the session."""
        return self in _TERMINAL_STATES

    @property
    def grants_access(self) -> bool:
        """Whether this state permits the scope it belongs to.

        Exactly one state does. Written as an explicit identity check rather
        than "not in a deny list", so a state added to the enum later is denied
        by default instead of silently permitted.
        """
        return self is ConsentState.CONSENTED


_TERMINAL_STATES = frozenset(
    {ConsentState.DECLINED, ConsentState.EXPIRED, ConsentState.REVOKED}
)


class ConsentTransitionError(MeetAIError):
    """A consent transition was refused.

    The message names states and keys, never a participant's display name and
    never meeting content.
    """


class StaleConsentError(ConsentTransitionError):
    """A decision arrived quoting a generation the session has moved past.

    The realistic case is a participant clicking "I agree" on a notice that was
    already superseded - someone else revoked, or the notice version changed -
    with the click in flight. Applying it would resurrect a revoked grant.
    """


@dataclass(frozen=True, slots=True)
class ConsentKey:
    """What a consent decision is about.

    ``participant`` is an opaque handle produced by the platform adapter's
    mapping, never a display name: a display name is both unstable and
    personal data, and this key ends up in log lines and receipts.
    """

    session_id: str
    participant: str
    scope: ConsentScope
    notice_version: str

    def __str__(self) -> str:
        return (
            f"{self.session_id}/{self.participant}/"
            f"{self.scope.value}@{self.notice_version}"
        )


@dataclass(frozen=True, slots=True)
class ConsentRecord:
    """One consent key's current state.

    ``generation`` is the session generation the record was last written under.
    ``decided_at`` and ``expires_at`` are seconds from the injected clock, not
    wall-clock timestamps, so expiry is testable without sleeping.
    """

    key: ConsentKey
    state: ConsentState
    generation: int
    updated_at: float
    expires_at: float | None = None

    def is_expired_at(self, now: float) -> bool:
        """Whether this record's grant has aged out by ``now``."""
        return self.expires_at is not None and now >= self.expires_at


@dataclass(frozen=True, slots=True)
class ConsentReceipt:
    """Evidence that a decision was recorded. Metadata only.

    There is no field for what was said, and none for who the participant is
    beyond the opaque handle already in the key. The handoff document requires
    receipts to carry metadata, timestamp and policy version and nothing else.
    """

    key: ConsentKey
    state: ConsentState
    generation: int
    recorded_at: float
    policy_version: str


@dataclass
class ConsentLedger:
    """Consent for one session.

    One ledger per session, which is how "consent is not inherited across
    sessions" is enforced structurally: a new session gets a new ledger, and
    there is no API for copying records between them.
    """

    session_id: str
    policy_version: str
    now: Callable[[], float]
    grant_ttl_seconds: float | None = None
    _records: dict[ConsentKey, ConsentRecord] = field(default_factory=dict, repr=False)
    _receipts: list[ConsentReceipt] = field(default_factory=list, repr=False)
    _generation: int = 0

    @property
    def generation(self) -> int:
        """The session's current consent generation.

        Increments on every revocation. Asynchronous work captures this value
        when it starts and quotes it back, so work begun before a revocation
        cannot complete after one.
        """
        return self._generation

    @property
    def receipts(self) -> tuple[ConsentReceipt, ...]:
        """Recorded decisions, oldest first."""
        return tuple(self._receipts)

    def __iter__(self) -> Iterator[ConsentRecord]:
        return iter(tuple(self._records.values()))

    # ------------------------------------------------------------------ #
    # Queries
    # ------------------------------------------------------------------ #

    def state_of(self, key: ConsentKey) -> ConsentState:
        """The state of ``key``, treating absence as ``UNKNOWN``.

        Also reports ``EXPIRED`` for a grant that has aged out, without
        mutating anything: a read must not have the side effect of changing
        what a later read returns. :meth:`sweep_expired` does the write.
        """
        self._require_same_session(key)
        record = self._records.get(key)
        if record is None:
            return ConsentState.UNKNOWN
        if record.state is ConsentState.CONSENTED and record.is_expired_at(self.now()):
            return ConsentState.EXPIRED
        return record.state

    def is_granted(self, key: ConsentKey, *, generation: int | None = None) -> bool:
        """Whether ``key`` currently permits its scope.

        ``generation`` is the session generation the caller started under. If
        the session has moved past it - which happens on any revocation - this
        returns ``False`` even when the key itself still reads ``CONSENTED``.
        That is the check an asynchronous task makes immediately before it
        processes or emits anything.

        Returns a bool rather than raising, because the correct response at a
        gate is to drop the work quietly, not to propagate an exception through
        a media pipeline.
        """
        if generation is not None and generation != self._generation:
            return False
        return self.state_of(key).grants_access

    def granted_scopes(
        self, participant: str, notice_version: str
    ) -> frozenset[ConsentScope]:
        """Scopes this participant currently grants under ``notice_version``."""
        return frozenset(
            scope
            for scope in ConsentScope
            if self.is_granted(
                ConsentKey(self.session_id, participant, scope, notice_version)
            )
        )

    # ------------------------------------------------------------------ #
    # Transitions
    # ------------------------------------------------------------------ #

    def announce(self, key: ConsentKey) -> ConsentRecord:
        """Record that the notice was shown. ``UNKNOWN -> ANNOUNCED``.

        Re-announcing an already-announced key is allowed and idempotent: a
        notice can legitimately be re-displayed. Announcing over a terminal
        state is refused, so a retry loop cannot re-ask someone who declined.
        """
        current = self.state_of(key)
        if current is ConsentState.ANNOUNCED:
            return self._records[key]
        self._require_not_terminal(key, current, "announce")
        if current is not ConsentState.UNKNOWN:
            raise ConsentTransitionError(
                f"khong the announce tu trang thai {current.value} cho {key}"
            )
        return self._write(key, ConsentState.ANNOUNCED)

    def grant(self, key: ConsentKey, *, generation: int) -> ConsentRecord:
        """Record consent. ``ANNOUNCED -> CONSENTED``.

        ``generation`` is the session generation the notice was issued under.
        A mismatch raises :class:`StaleConsentError` rather than being applied,
        because the alternative is resurrecting a grant that a revocation had
        already removed.

        Consent requires a prior announcement: a grant for a notice nobody was
        shown is not consent, it is an assumption.
        """
        self._require_current_generation(key, generation, "grant")
        current = self.state_of(key)
        self._require_not_terminal(key, current, "grant")
        if current is ConsentState.CONSENTED:
            return self._records[key]
        if current is not ConsentState.ANNOUNCED:
            raise ConsentTransitionError(
                f"khong the grant khi chua announce: {key} dang o {current.value}"
            )
        expires_at = (
            None
            if self.grant_ttl_seconds is None
            else self.now() + self.grant_ttl_seconds
        )
        return self._write(key, ConsentState.CONSENTED, expires_at=expires_at)

    def decline(self, key: ConsentKey, *, generation: int) -> ConsentRecord:
        """Record refusal. Terminal for the session.

        Allowed from ``UNKNOWN`` as well as ``ANNOUNCED``: a participant who
        refuses before the notice is rendered has still refused, and the
        fail-closed reading of an ambiguous input is the refusal.
        """
        self._require_current_generation(key, generation, "decline")
        current = self.state_of(key)
        if current is ConsentState.DECLINED:
            return self._records[key]
        self._require_not_terminal(key, current, "decline")
        return self._write(key, ConsentState.DECLINED)

    def revoke(self, key: ConsentKey) -> ConsentRecord:
        """Withdraw consent. Terminal for the session, and bumps the generation.

        Takes no ``generation`` argument on purpose. A revocation is always
        honoured: refusing a withdrawal because it quoted a stale generation
        would be the one fail-open this module must not have.

        The generation increments *before* the record is written, so any
        concurrent reader that re-checks :meth:`is_granted` with its captured
        generation is refused from this moment on - the gate closes first, and
        cancelling the outstanding tasks is a separate, slower step.
        """
        current = self.state_of(key)
        if current is ConsentState.REVOKED:
            return self._records[key]
        if current is not ConsentState.CONSENTED:
            raise ConsentTransitionError(
                f"chi co the revoke tu CONSENTED: {key} dang o {current.value}"
            )
        self._generation += 1
        return self._write(key, ConsentState.REVOKED)

    def revoke_all(self, participant: str) -> tuple[ConsentRecord, ...]:
        """Withdraw every scope this participant granted.

        One generation bump for the whole withdrawal rather than one per scope,
        so a reader cannot observe a half-revoked participant.
        """
        targets = [
            record.key
            for record in tuple(self._records.values())
            if record.key.participant == participant
            and self.state_of(record.key) is ConsentState.CONSENTED
        ]
        if not targets:
            return ()
        self._generation += 1
        return tuple(self._write(key, ConsentState.REVOKED) for key in targets)

    def invalidate_outstanding_work(self) -> int:
        """Bump the generation without changing any consent record.

        What a kill switch needs, and the reason it exists is a gap worth
        stating. A reader re-checking permission has two places to ask: the
        media gate object, or the ledger directly via
        ``is_granted(key, generation=captured)``. ``MediaGate.close()`` only
        answers the first. ``revoke()`` bumps the generation and so answers
        both, which made a revocation *stronger* than a kill - the opposite of
        what either name suggests.

        Returns the new generation. Does not touch any record: nobody withdrew
        consent, so the states are unchanged and a later session reading the
        receipts sees no decision that did not happen.
        """
        self._generation += 1
        return self._generation

    def sweep_expired(self) -> tuple[ConsentRecord, ...]:
        """Write ``EXPIRED`` for grants that have aged out.

        Expiry is observable through :meth:`state_of` without this call; this
        makes it durable and produces receipts. Expiry does **not** bump the
        generation: unlike a revocation it is not an instruction to stop
        in-flight work, and :meth:`is_granted` already refuses an expired key.
        """
        now = self.now()
        swept = [
            record.key
            for record in tuple(self._records.values())
            if record.state is ConsentState.CONSENTED and record.is_expired_at(now)
        ]
        return tuple(self._write(key, ConsentState.EXPIRED) for key in swept)

    # ------------------------------------------------------------------ #
    # Internals
    # ------------------------------------------------------------------ #

    def _write(
        self,
        key: ConsentKey,
        state: ConsentState,
        *,
        expires_at: float | None = None,
    ) -> ConsentRecord:
        now = self.now()
        existing = self._records.get(key)
        record = (
            replace(
                existing,
                state=state,
                generation=self._generation,
                updated_at=now,
                expires_at=expires_at,
            )
            if existing is not None
            else ConsentRecord(
                key=key,
                state=state,
                generation=self._generation,
                updated_at=now,
                expires_at=expires_at,
            )
        )
        self._records[key] = record
        self._receipts.append(
            ConsentReceipt(
                key=key,
                state=state,
                generation=self._generation,
                recorded_at=now,
                policy_version=self.policy_version,
            )
        )
        return record

    def _require_same_session(self, key: ConsentKey) -> None:
        if key.session_id != self.session_id:
            raise ConsentTransitionError(
                f"consent khong duoc ke thua giua cac phien: ledger cua "
                f"{self.session_id}, key cua {key.session_id}"
            )

    def _require_not_terminal(
        self, key: ConsentKey, current: ConsentState, action: str
    ) -> None:
        if current.is_terminal:
            raise ConsentTransitionError(
                f"{current.value} la trang thai cuoi trong phien, khong the {action}: {key}"
            )

    def _require_current_generation(
        self, key: ConsentKey, generation: int, action: str
    ) -> None:
        self._require_same_session(key)
        if generation != self._generation:
            raise StaleConsentError(
                f"{action} bi tu choi vi generation da cu "
                f"(gui {generation}, hien tai {self._generation}): {key}"
            )
