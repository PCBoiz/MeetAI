"""Exception types for MeetAI.

Every message in this module describes the *shape* of a problem, never a value.
A configuration value can be a credential and a runtime value can be meeting
content, so an exception message that interpolates either becomes a leak the
moment anything logs it. The rule is enforced by test, not by convention
(``tests/test_no_value_in_errors.py``).
"""

from __future__ import annotations


class MeetAIError(Exception):
    """Base class for every error MeetAI raises deliberately."""


class UnknownSettingError(MeetAIError):
    """A ``MEETAI_*`` name does not match any known setting.

    pydantic-settings' ``extra="forbid"`` only rejects unknown keyword
    arguments; an unrecognised prefixed environment variable or ``.env`` key is
    otherwise silently ignored, and the ``.env`` case additionally echoes the
    value in pydantic's error output. Silence is the wrong behaviour: a typo in
    a consent or persistence variable would look like it took effect while the
    setting kept its default.

    The message names the offending keys and never their values.
    """


class ProhibitedEgressVariableError(MeetAIError):
    """An environment variable that could send data off this machine is set.

    MeetAI's whole privacy position is that meeting content stays local. Some
    egress switches are not ``MEETAI_*`` — OpenTelemetry's exporter endpoint is
    read straight from ``OTEL_*`` by library code — so the ``MEETAI_*`` guard
    cannot see them. This error closes that blind spot.
    """


class PendingDecisionError(MeetAIError):
    """An operation needs a policy decision that the operator has not made.

    This is the runtime half of ``pending_decision``: the enum value records
    that nothing was chosen, and this error is what happens when code tries to
    act anyway. It is deliberately not catchable-and-ignorable at a call site:
    the only correct response is to refuse the operation.
    """


class ConfigurationRejectedError(MeetAIError):
    """A configuration was understood and refused on policy grounds.

    Distinct from a validation error, which means "not understood". This one
    means "understood, and not allowed" - for example a switch that MeetAI's
    scope rules out.
    """


class SinkError(MeetAIError):
    """An output sink failed. Carries no content, like every error here."""


class SinkRefusedBeforeEmitError(SinkError):
    """A sink asserts it produced **no output at all** before failing.

    **An assertion by the sink, never evidence held by MeetAI.** An exception
    arriving at the boundary carries no information about how far the sink got:
    a driver that could not open the device and the same driver failing after
    two seconds of audio are indistinguishable at the call site. So the only
    way the "nothing was emitted" case can be known is for the sink to say so,
    and the only channel an exception has for saying it is its type.

    Which fixes the direction of the default: **unknown is the default and this
    is the opt-in.** A contract that assumed "nothing was emitted" unless told
    otherwise would fail open on every sink nobody had updated.

    A sink raises this **only** before its first side effect. Raising it after
    producing output is a lie the boundary cannot detect and will act on - a
    test pins that limit rather than leaving it implied.
    """
