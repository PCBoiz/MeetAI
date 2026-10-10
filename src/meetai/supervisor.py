"""Supervisor: Start/Stop, the model switch, and the kill switch (slice S0.6).

Three objects, and the reason they are separate is that they answer different
questions:

- :class:`KillSwitch` is a **process-wide latch**. One object that every gate
  consults, present and future. Without it a "kill everything" button can only
  kill the sessions the UI happens to hold a reference to - there is no session
  registry - and a kill switch whose reach depends on bookkeeping is not one.
- :class:`ModelSwitch` is a mock for Phase 0/1. It has an explicit ``LOADING``
  and ``ERROR`` state because "I am asking" and "I asked and it failed" are
  different facts from "it was never built", and the honest answer during a
  probe is neither on nor off.
- :class:`Supervisor` composes them and owns the Start/Stop lifecycle.

The composition is the load-bearing part:
``policy_allows_media = settings.media_processing_allowed and not kill.engaged
and supervisor.is_running``. ``Settings`` is frozen and ``model_copy``
re-validates into a *new* object, so a kill switch cannot flip
``media_processing_allowed`` on the live settings. Composing a callable is the
only design in which "kill everything" is true rather than "kill everything I
am holding".

Turning the model on does **not** turn audio on, and starting the supervisor
does **not** join anything. Both are stated here because both are easy to wire
together by accident, and either would be a capability the operator did not ask
for.
"""

from __future__ import annotations

import enum
from collections.abc import Callable
from dataclasses import dataclass, field

from meetai.errors import MeetAIError


class SupervisorError(MeetAIError):
    """An operation did not match the supervisor's state."""


class RunState(enum.Enum):
    """Whether the supervisor is running.

    Not ``str``-mixed, and ``STOPPED`` is falsy, so ``if supervisor.state:``
    fails closed. ``KILLED`` is terminal: the way to continue after a kill is a
    new process, which is what makes the latch worth trusting.
    """

    STOPPED = "stopped"
    STARTING = "starting"
    RUNNING = "running"
    KILLED = "killed"

    def __bool__(self) -> bool:
        return self is RunState.RUNNING

    @property
    def is_terminal(self) -> bool:
        return self is RunState.KILLED


class ModelState(enum.Enum):
    """Where the local model runtime stands.

    ``UNKNOWN`` exists and is falsy. A boolean would force the UI to render
    either ON or OFF while a probe is in flight - that is, to guess - and
    guessing "on" is exactly the dishonesty the capability report exists to
    prevent.
    """

    OFF = "off"
    LOADING = "loading"
    READY = "ready"
    ERROR = "error"
    UNKNOWN = "unknown"

    def __bool__(self) -> bool:
        return self is ModelState.READY

    @property
    def is_decided(self) -> bool:
        """Whether this state is an answer rather than an absence of one."""
        return self not in {ModelState.LOADING, ModelState.UNKNOWN}


@dataclass
class KillSwitch:
    """A process-wide, one-way latch.

    One object, consulted by every gate. Engaging it is irreversible within the
    process: there is no ``disengage``, because a latch that can be flipped
    back is a toggle, and the operator reaching for a kill switch is not asking
    for a toggle.
    """

    _engaged: bool = False
    _reason: str = ""

    @property
    def engaged(self) -> bool:
        return self._engaged

    @property
    def reason(self) -> str:
        """Why it was engaged. Operator-facing, carries no content."""
        return self._reason

    def engage(self, reason: str = "operator engaged kill switch") -> None:
        """Engage the latch. Idempotent; the first reason is kept.

        The first reason is kept rather than the last because the first one is
        the one that describes why media stopped; a later call is a second
        press of a button that is already down.
        """
        if self._engaged:
            return
        self._engaged = True
        self._reason = reason


@dataclass
class ModelSwitch:
    """The model runtime toggle. A mock for Phase 0/1.

    No model is loaded, and this class does not pretend one is: ``turn_on``
    moves to ``LOADING`` and then to whatever the injected loader reports. The
    default loader fails, because there is no model runtime yet and reporting
    ``READY`` would be the exact lie the capability report forbids.
    """

    loader: Callable[[], ModelState] | None = None
    _state: ModelState = ModelState.OFF
    _detail: str = ""

    @property
    def state(self) -> ModelState:
        return self._state

    @property
    def detail(self) -> str:
        """Why the model is in this state. Never a model path or a prompt."""
        return self._detail

    def turn_on(self) -> ModelState:
        """Attempt to load. Returns the resulting state.

        Passes through ``LOADING`` observably rather than jumping straight to a
        verdict, so a UI polling during a slow load has a real state to render
        instead of having to guess.
        """
        self._state = ModelState.LOADING
        self._detail = "dang nap model runtime"
        if self.loader is None:
            self._state = ModelState.ERROR
            self._detail = (
                "chua co model runtime nao duoc trien khai (lat S2.1-S2.3). "
                "Day la mock: bao READY o day se la mot loi tuyen bo sai."
            )
            return self._state
        try:
            self._state = self.loader()
        except Exception as exc:  # the loader is injected, so it is untrusted
            self._state = ModelState.ERROR
            # Type only. A loader failure message could name a model path.
            self._detail = f"loader that bai: {type(exc).__name__}"
            return self._state
        self._detail = "" if self._state is ModelState.READY else "loader bao khong ready"
        return self._state

    def turn_off(self) -> None:
        """Unload. Always succeeds: refusing to turn something off is wrong."""
        self._state = ModelState.OFF
        self._detail = ""


@dataclass
class Supervisor:
    """Start/Stop for the local components, and nothing else.

    ``start`` brings up only what is permitted locally. It explicitly does not
    join a platform, does not open a socket to anything outside the machine,
    and does not enable audio - a Start button that quietly joined a meeting
    would be the worst possible reading of the word.
    """

    settings_allows_media: Callable[[], bool]
    kill_switch: KillSwitch = field(default_factory=KillSwitch)
    model: ModelSwitch = field(default_factory=ModelSwitch)
    _state: RunState = RunState.STOPPED

    @property
    def state(self) -> RunState:
        return self._state

    @property
    def is_running(self) -> bool:
        return self._state is RunState.RUNNING

    def start(self) -> RunState:
        """Bring up the local components.

        Refuses after a kill: the latch is one-way, and a Start that quietly
        un-killed the process would make the latch meaningless.
        """
        if self._state.is_terminal:
            raise SupervisorError(
                "khong the start sau khi kill switch da bat. Kill switch la mot "
                "chieu trong tien trinh nay; muon tiep tuc thi khoi dong lai."
            )
        if self._state is RunState.RUNNING:
            return self._state
        self._state = RunState.STARTING
        # Nothing is actually brought up yet: there is no platform adapter to
        # connect and no model to load. The state transition is the whole
        # behaviour, and saying so beats implying more.
        self._state = RunState.RUNNING
        return self._state

    def stop(self) -> RunState:
        """Bring the local components down. Idempotent.

        Distinct from a kill: stopping is a toggle an operator may undo, while
        the kill latch is not. Conflating them would mean every Stop needed a
        process restart to recover from.
        """
        if self._state.is_terminal:
            return self._state
        self._state = RunState.STOPPED
        return self._state

    def kill(self, reason: str = "operator engaged kill switch") -> RunState:
        """Engage the latch and stop. Irreversible within this process."""
        self.kill_switch.engage(reason)
        self.model.turn_off()
        self._state = RunState.KILLED
        return self._state

    def media_allowed(self) -> bool:
        """The composed gate every :class:`~meetai.media_gate.MediaGate` consults.

        Pass this as ``policy_allows_media``. All four conditions are read at
        call time, which is what makes the kill switch reach gates that already
        exist - the reason that argument is a callable rather than a bool.

        The model being ready is required: the handoff document is explicit
        that MeetAI must not join and pretend to listen when the model is off.
        """
        return (
            self.settings_allows_media()
            and not self.kill_switch.engaged
            and self.is_running
            and bool(self.model.state)
        )

    def status(self) -> dict[str, object]:
        """Metadata-only snapshot for the UI and the log."""
        return {
            "run_state": self._state.value,
            "model_state": self.model.state.value,
            "model_detail": self.model.detail,
            "model_state_decided": self.model.state.is_decided,
            "kill_engaged": self.kill_switch.engaged,
            "kill_reason": self.kill_switch.reason,
            "settings_allows_media": self.settings_allows_media(),
            "media_allowed": self.media_allowed(),
        }
