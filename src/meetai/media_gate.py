"""The gate every audio frame passes before anything else sees it (slice S1.2).

The handoff document requires unknown, unmapped, stale and revoked audio to be
dropped *before* ASR. That ordering is the whole design: once a frame reaches a
model, the model's output exists, and a later decision to discard it is a
promise rather than a property.

Two deliberate shapes:

- **The gate returns a decision, it does not raise.** At a media boundary the
  correct response to "not allowed" is to drop the frame and count it, not to
  propagate an exception up through a pipeline where some generic handler
  decides what to do. An exception here would make fail-open a possibility.

- **Every rejection has a named reason.** A bare ``False`` gives an operator
  nothing and gives a log line nothing, and "frames are being dropped" with no
  reason is indistinguishable from a bug. :class:`GateRejection` is a closed
  enum, so the reason is loggable metadata rather than free text.

This module imports no framework.
"""

from __future__ import annotations

import enum
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass, field
from weakref import WeakSet

from meetai.consent import ConsentKey, ConsentLedger
from meetai.policy import ConsentScope


def _permits(source: Callable[[], bool]) -> bool:
    """Whether ``source`` says yes, refusing anything that is not exactly yes.

    **``is True``, not truthiness, and the difference was measured.** With a
    plain ``not source()`` guard, a callable returning the string ``"pending"``
    - or ``"false"`` - **allowed the frame**, because ``not "false"`` is
    ``False``. This project already forbids ``(str, Enum)`` for policy enums
    for precisely that reason: a str-mixed member is truthy, so
    ``if settings.consent_mode:`` reads like a guard and fails open on the one
    state that must block. The same trap arrives here across a callable
    boundary, so it gets the same answer - only the boolean ``True`` is a yes.

    **A raising dependency is a refusal, not an exception.** The module's
    contract is that ``evaluate`` returns a decision; a pipeline handed an
    exception by its permission check has no decision to record and no frame
    it deliberately dropped. A permission source that is broken is exactly the
    state in which the answer has to be "no".
    """
    try:
        return source() is True
    except Exception:  # any failure to answer is a refusal, by design
        return False


class GateRejection(enum.Enum):
    """Why a frame was not allowed through.

    Ordered roughly from "configuration is not ready" to "this specific frame
    is not allowed".

    **Declaration order is NOT check order**, and this docstring used to say
    it was. The gate checks ``GATE_CLOSED`` first and it is declared last;
    ``STALE_GENERATION`` is checked before ``NO_CONSENT`` and declared after
    it. Reordering the members to match would be cosmetic and would teach the
    next reader to trust the declaration rather than read
    :meth:`MediaGate.evaluate` - so the order lives in exactly one place, the
    function, and a test pins every adjacent pair of it.
    """

    POLICY_PENDING = "policy_pending"
    """The operator has not chosen a consent policy. Nothing may be processed."""

    SESSION_NOT_ACTIVE = "session_not_active"
    """The session is not in a state where media is expected."""

    SPEAKER_UNMAPPED = "speaker_unmapped"
    """The frame's speaker could not be resolved to a known participant.

    An unmapped speaker is the dangerous case: it may be someone who never saw
    a notice. SSRC-to-user mapping is itself an open evidence gate, so this is
    the refusal that will fire most often in any real deployment.
    """

    NO_CONSENT = "no_consent"
    """The speaker has not granted the scope this frame needs."""

    STALE_GENERATION = "stale_generation"
    """The caller started before a revocation that has since happened."""

    GATE_CLOSED = "gate_closed"
    """The gate was closed explicitly, e.g. by a late join or a kill switch."""


@dataclass(frozen=True, slots=True)
class GateDecision:
    """The gate's answer for one frame.

    ``allowed`` and ``rejection`` are kept consistent by the constructor, so a
    caller cannot read ``allowed`` as False and find no reason, nor read it as
    True and silently ignore a reason that was set.
    """

    allowed: bool
    rejection: GateRejection | None = None

    def __post_init__(self) -> None:
        if self.allowed and self.rejection is not None:
            raise ValueError("GateDecision allowed=True khong duoc co rejection")
        if not self.allowed and self.rejection is None:
            raise ValueError("GateDecision allowed=False phai co rejection")

    @classmethod
    def allow(cls) -> GateDecision:
        return cls(allowed=True)

    @classmethod
    def reject(cls, rejection: GateRejection) -> GateDecision:
        return cls(allowed=False, rejection=rejection)

    def __bool__(self) -> bool:
        return self.allowed


class MediaSinkPermit:
    """Proof that the gate allowed something to become a frame consumer.

    **Not a security boundary, and the docstring says so first.** Any code in
    this process can reach into this module, add to the issued set, or rebind
    the mint. The threat this answers is *the next careless commit in this
    repository* - the same threat, and the same honest limit, as the residual
    recorded on :attr:`MediaGate._closed`.

    What it is: a thing with **no usable public constructor**, whose validity
    is **object identity** against a set only the gate adds to. Identity is the
    one check that survives the forgeries Python makes easy - measured:

    - direct construction raises;
    - ``MediaSinkPermit.__new__(MediaSinkPermit)`` produces an object that is
      ``isinstance`` of this class and is **not** in the issued set;
    - the same with ``object.__setattr__`` applied afterwards, which defeats
      ``frozen=True`` and ``slots=True`` alike;
    - subclassing is refused outright by ``__init_subclass__``.

    A ``runtime_checkable`` ``Protocol`` check was considered and rejected: it
    tests attribute *presence* only, so an object whose ``emit`` is the integer
    ``3`` satisfies it. A guard written that way is duck typing wearing the
    costume of a check.
    """

    __slots__ = ("__weakref__",)
    """__weakref__ so the gate can hold permits weakly.

    Found by running it: __slots__ without this makes instances
    non-weakref-able, and the mint raised TypeError: cannot create weak
    reference. The slots are otherwise empty on purpose - a permit carries no
    state, because every field would be a thing a forgery could set.
    """

    def __init__(self) -> None:
        raise TypeError(
            "MediaSinkPermit khong duoc khoi tao truc tiep: chi "
            "MediaGate.issue_sink_permit() cap duoc, va hieu luc la danh tinh "
            "doi tuong chu khong phai kieu"
        )

    def __init_subclass__(cls, **kwargs: object) -> None:
        raise TypeError("khong duoc ke thua MediaSinkPermit")

    def __repr__(self) -> str:
        return "MediaSinkPermit(...)"


@dataclass(frozen=True, slots=True)
class SinkPermitDecision:
    """The gate's answer to "may this become a frame consumer?".

    Returns rather than raises, mirroring :class:`GateDecision`, and the
    consistency invariant is the reason it is safe to return: a caller cannot
    fabricate a permit out of a refusal, because a refusal carries ``None``.
    """

    permit: MediaSinkPermit | None
    rejection: GateRejection | None = None

    def __post_init__(self) -> None:
        if (self.permit is None) == (self.rejection is None):
            raise ValueError(
                "SinkPermitDecision phai co dung mot trong hai: permit hoac rejection"
            )

    def __bool__(self) -> bool:
        return self.permit is not None


@dataclass
class MediaGate:
    """Decides whether media may be processed, for one session.

    ``policy_allows_media`` is a callable rather than a bool so the gate
    reflects configuration at the moment of the decision instead of at the
    moment it was constructed - a kill switch that only took effect for gates
    created afterwards would not be a kill switch.
    """

    ledger: ConsentLedger
    notice_version: str
    policy_allows_media: Callable[[], bool]
    session_is_active: Callable[[], bool]
    _closed: bool = field(default=False, init=False, repr=False)
    """Latched by :meth:`close`. **Not an ``__init__`` parameter.**

    It was one, which meant a caller could hand out a gate that was closed
    before anyone could observe it opening - and, more usefully to whoever
    comes next, the field name invited ``gate._closed = False``. Python cannot
    stop that assignment on a mutable dataclass; what it can do is keep the
    state out of the constructor and keep :meth:`close` the only thing that
    sets it. The residual is recorded rather than claimed shut: a caller that
    assigns to a private attribute can still reopen a gate, and no test can
    prevent that.
    """
    _issued_permits: WeakSet[MediaSinkPermit] = field(
        default_factory=WeakSet, init=False, repr=False
    )
    """Permits this gate minted, held weakly and by identity.

    Weak so a permit does not keep a sink alive, and owned by the gate so
    there is no module-level set a test could poison. ``init=False`` for
    the same reason ``_closed`` is: the state must not be reachable through
    the constructor."""
    _rejections: dict[GateRejection, int] = field(default_factory=dict, repr=False)
    _allowed_count: int = 0

    @property
    def is_closed(self) -> bool:
        return self._closed

    @property
    def allowed_count(self) -> int:
        """Frames allowed through. Metadata, safe to log."""
        return self._allowed_count

    @property
    def rejection_counts(self) -> dict[str, int]:
        """Rejections by reason. Metadata, safe to log.

        Visible counts matter: a gate that silently drops everything looks the
        same as a quiet meeting.
        """
        return {
            reason.value: count
            for reason, count in sorted(
                self._rejections.items(), key=lambda item: item[0].value
            )
        }

    def close(self) -> None:
        """Close the gate immediately and irreversibly for this session.

        Called before cancelling outstanding work, never after: cancellation
        is asynchronous and slow, while this is synchronous and immediate. A
        gate that closed after cancellation would leave a window in which a
        task that had already passed its check could still emit.

        There is no ``reopen``. A session whose gate closed is finished; the
        way to continue is a new session with a new notice and a new ledger.
        """
        self._closed = True
        # Permits die with the gate. Without this a sink registered before
        # a close would still hold something that validated, which would
        # make a close weaker than it looks - the same asymmetry that once
        # made `close` weaker than `revoke`.
        self._issued_permits.clear()

    def issue_sink_permit(self) -> SinkPermitDecision:
        """Mint a permit, or refuse and say why.

        Coarser than :meth:`evaluate` on purpose: a registration has no
        participant and no generation of its own, so the per-frame key cannot
        be built. What this answers is "may a frame consumer exist at all",
        and the per-frame question is still asked of every frame afterwards.

        The policy is read **here, now**, through the same callable
        :meth:`evaluate` uses - so a permit cannot be minted at import time
        (minting needs a live gate, which needs a ledger and a callable), and
        a pending consent decision refuses. ``_permits`` already refuses a
        non-``True`` yes and treats a raising source as a refusal.

        **What this does NOT decide**, because it is not ours to decide: which
        consent scope a registration consumes, whether a permit should die on a
        revocation as well as on a close, and whether a session with no
        registered sink is an error. Those are recorded as pending questions;
        until they are answered the permit is the narrowest thing that is
        clearly right - it dies with the gate and nothing more is claimed.
        """
        if self._closed:
            return SinkPermitDecision(permit=None, rejection=GateRejection.GATE_CLOSED)
        if not _permits(self.policy_allows_media):
            return SinkPermitDecision(permit=None, rejection=GateRejection.POLICY_PENDING)
        if not _permits(self.session_is_active):
            return SinkPermitDecision(
                permit=None, rejection=GateRejection.SESSION_NOT_ACTIVE
            )
        permit = MediaSinkPermit.__new__(MediaSinkPermit)
        self._issued_permits.add(permit)
        return SinkPermitDecision(permit=permit)

    def permit_is_valid(self, permit: object) -> bool:
        """Whether this gate issued ``permit`` and has not closed since.

        **Identity, not ``isinstance``.** A forged object of the right type is
        not in the set; that is the entire mechanism. Written as a method on
        the gate so the issued set has one owner and no module-level mutable
        state for a test to poison.
        """
        if self._closed:
            return False
        return any(issued is permit for issued in self._issued_permits)

    def evaluate(
        self,
        *,
        participant: str | None,
        generation: int,
        scope: ConsentScope = ConsentScope.LIVE_MEDIA,
    ) -> GateDecision:
        """Decide whether one frame or job may proceed.

        ``participant`` is ``None`` when the platform could not map the speaker.
        ``generation`` is the consent generation the caller captured when it
        started, which is what makes a revocation during processing effective.
        """
        if self._closed:
            return self._record(GateDecision.reject(GateRejection.GATE_CLOSED))
        if not _permits(self.policy_allows_media):
            return self._record(GateDecision.reject(GateRejection.POLICY_PENDING))
        if not _permits(self.session_is_active):
            return self._record(GateDecision.reject(GateRejection.SESSION_NOT_ACTIVE))
        if participant is None:
            return self._record(GateDecision.reject(GateRejection.SPEAKER_UNMAPPED))
        if generation != self.ledger.generation:
            return self._record(GateDecision.reject(GateRejection.STALE_GENERATION))

        key = ConsentKey(
            session_id=self.ledger.session_id,
            participant=participant,
            scope=scope,
            notice_version=self.notice_version,
        )
        if not self.ledger.is_granted(key, generation=generation):
            return self._record(GateDecision.reject(GateRejection.NO_CONSENT))
        return self._record(GateDecision.allow())

    def _record(self, decision: GateDecision) -> GateDecision:
        if decision.allowed:
            self._allowed_count += 1
        elif decision.rejection is not None:
            self._rejections[decision.rejection] = (
                self._rejections.get(decision.rejection, 0) + 1
            )
        return decision


@dataclass
class BoundedBuffer:
    """A size- and age-bounded buffer for in-flight media.

    Both bounds are required by the handoff document, and they protect
    different failures. The size bound stops a stalled consumer from growing
    memory without limit. The **age** bound is the privacy-relevant one: audio
    that has been sitting in a buffer is audio that a revocation should already
    have discarded, so holding it longer than the pipeline needs turns a buffer
    into de facto retention.

    Eviction is from the front, so what survives is the most recent audio - the
    only part a real-time pipeline can still use.
    """

    max_items: int
    max_age_seconds: float
    now: Callable[[], float]
    _items: deque[tuple[float, object]] = field(default_factory=deque, repr=False)
    _dropped_by_size: int = 0
    _dropped_by_age: int = 0
    _closed: bool = False

    def __post_init__(self) -> None:
        if self.max_items < 1:
            raise ValueError("max_items phai >= 1")
        if self.max_age_seconds <= 0:
            raise ValueError("max_age_seconds phai > 0")

    def __len__(self) -> int:
        self._evict_aged()
        return len(self._items)

    @property
    def dropped_by_size(self) -> int:
        return self._dropped_by_size

    @property
    def dropped_by_age(self) -> int:
        return self._dropped_by_age

    def push(self, item: object) -> None:
        """Add an item, evicting whatever the bounds require.

        A no-op on a closed buffer. Silent rather than raising: a media
        pipeline pushing into a killed session should stop, not crash into a
        handler that might do something else with the frame.
        """
        if self._closed:
            return
        self._evict_aged()
        self._items.append((self.now(), item))
        while len(self._items) > self.max_items:
            self._items.popleft()
            self._dropped_by_size += 1

    def drain(self) -> tuple[object, ...]:
        """Remove and return everything still within the age bound.

        Returns empty on a closed buffer, so a consumer mid-drain gets nothing
        rather than the last frames of a killed session.
        """
        if self._closed:
            return ()
        self._evict_aged()
        items = tuple(item for _, item in self._items)
        self._items.clear()
        return items

    def purge(self) -> int:
        """Discard everything. Returns how many items were dropped.

        What a revocation calls. Not counted as an age or size drop: it is a
        deliberate purge, and conflating the two would hide a real eviction
        problem behind normal revocation traffic.
        """
        count = len(self._items)
        self._items.clear()
        return count

    def close(self) -> int:
        """Discard everything and refuse all further use. Irreversible.

        Separate from :meth:`purge` because purge alone was not enough to make
        a kill switch honest. ``self._buffers.clear()`` on the session drops the
        session's reference, but any consumer that called ``buffer_for``
        earlier still holds the object - and a purged-but-open buffer happily
        accepts another ``push``. So "buffered audio is unreachable" was not
        true for a holder.

        After this, ``push`` is a no-op and ``drain`` returns empty. There is
        no reopen: a buffer belonging to a killed session is finished.
        """
        count = self.purge()
        self._closed = True
        return count

    @property
    def is_closed(self) -> bool:
        return self._closed

    def _evict_aged(self) -> None:
        cutoff = self.now() - self.max_age_seconds
        while self._items and self._items[0][0] <= cutoff:
            self._items.popleft()
            self._dropped_by_age += 1
