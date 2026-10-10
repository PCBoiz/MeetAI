"""Validated application settings with fail-closed defaults.

Every switch that could expose meeting content, persist it, or let MeetAI act
on the operator's behalf defaults to the safest value. Decisions the operator
has not made are represented as a ``pending_decision`` state that blocks, never
as a guessed policy.

Secrets are never rendered by this module, and neither is any other
configuration value. :meth:`Settings.redacted_summary` is the only supported
way to show settings in a UI, a log line, or a report, and
:func:`sanitised_validation_errors` is the only supported way to show a
validation failure. Printing ``str(ValidationError)`` leaks the offending
value - pydantic puts the raw input in the error - so the rendering path
matters as much as the model.

The policy rules themselves live in :mod:`meetai.policy`, which has no
framework dependency. This module adapts them to pydantic; it does not own
them.
"""

from __future__ import annotations

import os
from collections.abc import Iterable, Mapping
from pathlib import Path, PureWindowsPath
from typing import Annotated, Any, Self

from dotenv import dotenv_values
from pydantic import Field, SecretStr, ValidationError, field_validator, model_validator
from pydantic_settings import BaseSettings, PydanticBaseSettingsSource, SettingsConfigDict

from meetai.errors import (
    ConfigurationRejectedError,
    PendingDecisionError,
    ProhibitedEgressVariableError,
    UnknownSettingError,
)
from meetai.policy import (
    ConfigurationFlags,
    ConsentMode,
    LateJoinPolicy,
    media_processing_allowed,
    pending_decisions,
    rejected_configuration,
)

ENV_PREFIX = "MEETAI_"
DEFAULT_ENV_FILE = Path(".env")

#: Loopback literals accepted for the supervisor UI bind address.
#:
#: Deliberately a closed allowlist of literal addresses rather than a
#: resolve-and-classify check, so no hostname can pass. ``localhost`` is
#: excluded on purpose: it is a *name*, resolved at bind time, so a tampered
#: hosts file would change where the UI actually listens while this check still
#: passed.
LOOPBACK_ADDRESSES = frozenset({"127.0.0.1", "::1"})

#: Environment variable prefixes that can cause data to leave this machine
#: without any MeetAI code being involved.
#:
#: ``OTEL_*`` is read directly by library code (FastAPI >= 0.142 has a
#: first-party telemetry subsystem whose exporter endpoint comes from
#: ``OTEL_EXPORTER_OTLP_ENDPOINT``), so the ``MEETAI_*`` guard cannot see it.
#:
#: The ``HF_``/``HUGGINGFACE``/``TRANSFORMERS`` families were added on
#: 2026-10-10 as S2.1 decision #3, **[CHỐT THEO ỦY QUYỀN CỦA SƠN]**. Each of
#: them decides *where model weights are resolved from* - ``HF_ENDPOINT``
#: names a host, ``HF_HOME`` and the cache variables name a directory,
#: ``HF_HUB_OFFLINE`` and ``TRANSFORMERS_OFFLINE`` switch the behaviour - so
#: any one of them can turn a local-file design into a downloading one with no
#: MeetAI code changing. Measured beforehand: all of them started MeetAI fine.
#:
#: MeetAI has no legitimate use for any of these on the operator's own machine.
PROHIBITED_EGRESS_PREFIXES = (
    "OTEL_",
    "HF_",
    "HUGGINGFACE",
    "TRANSFORMERS",
)

#: Variable name suffixes rejected for the same reason, where the family is not
#: prefix-shaped.
#:
#: Proxy settings are spelled ``HTTP_PROXY``, ``HTTPS_PROXY``, ``ALL_PROXY``,
#: ``NO_PROXY`` - a suffix family, not a prefix one. They are rejected for a
#: narrower and more concrete reason than the resolution families: a proxy
#: **can route around the OS-level egress isolation that S2.1 decision #5
#: requires**. A firewall rule that blocks direct outbound traffic from
#: ``llama-cli.exe`` does not help if an allowed proxy will forward it. That
#: interaction is the justification; "proxies feel network-ish" is not, which
#: is why ``XDG_CACHE_HOME`` is deliberately *not* here - it relocates a cache,
#: and can neither create a network path nor defeat a firewall rule.
#:
#: Anchored as a suffix rather than searched as a substring, so a variable that
#: merely mentions the word (``PROXY_SETTINGS``) is left alone.
PROHIBITED_EGRESS_SUFFIXES = ("_PROXY",)


def _is_prohibited_egress_name(name: str) -> bool:
    """True if this variable name is refused regardless of its value.

    Presence, never value. A guard that allowed ``HF_HUB_OFFLINE=1`` because
    the value reads as the safe one would teach the operator that the variable
    takes effect here, and would say nothing on the day it becomes ``0``. The
    same reasoning the project already applies to ``OTEL_SDK_DISABLED=true``.
    """
    upper = name.upper()
    return upper.startswith(PROHIBITED_EGRESS_PREFIXES) or upper.endswith(
        PROHIBITED_EGRESS_SUFFIXES
    )


class Settings(BaseSettings):
    """Runtime configuration. Construct via :func:`load_settings`."""

    model_config = SettingsConfigDict(
        extra="forbid",
        frozen=True,
        # Blanks `input_value` out of `str(exc)`. Defence in depth only: it
        # does NOT clear `errors()[i]["input"]`, so the sanitiser is still the
        # thing that actually closes the leak.
        hide_input_in_errors=True,
    )

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        """Read configuration only from explicit arguments.

        The library's own environment and dotenv sources are switched off, and
        :func:`load_settings` reads both itself. That is not stylistic: the
        dotenv source turns an unknown key into an ``extra_forbidden`` error
        whose payload is the raw value, so a misspelled credential name in
        ``.env`` - the exact typo the unknown-name guard exists to catch - gets
        the credential echoed into the error. Reading the file ourselves lets
        the guard run on names before any value reaches pydantic.

        It also makes the inputs explicit: nothing about the resulting
        ``Settings`` depends on the process environment or the current working
        directory except through arguments a caller passed.
        """
        return (init_settings,)

    # --- Credentials -----------------------------------------------------
    # Declared first on purpose. When pydantic renders a model-level error it
    # truncates the middle of the input mapping and keeps the tail, so fields
    # declared last are the ones that survive truncation. Credentials belong in
    # the part that gets truncated away. The sanitiser is the real fix; this is
    # free insurance behind it.
    discord_bot_token: SecretStr | None = None
    google_oauth_client_secret: SecretStr | None = None

    # --- Supervisor / local UI -------------------------------------------
    ui_host: str = Field(
        default="127.0.0.1",
        description="Bind address for the local supervisor UI. Loopback literal only.",
    )
    ui_port: Annotated[int, Field(ge=1024, le=65535)] = 8765
    state_dir: Path = Field(
        default=Path("var"),
        description="Operational state (never meeting content). Must be local and fixed.",
    )

    # --- Consent and media gating (fail-closed) --------------------------
    consent_mode: ConsentMode = ConsentMode.PENDING_DECISION
    late_join_policy: LateJoinPolicy = LateJoinPolicy.PENDING_DECISION

    # --- Persistence switches, all off until the operator decides --------
    persist_transcript: bool = Field(
        default=False,
        description="Store meeting transcripts. Handoff doc section 10 q3: undecided.",
    )
    persist_notes: bool = Field(
        default=False,
        description="Store meeting notes. Handoff doc section 10 q3: undecided.",
    )
    persist_reply_journal: bool = Field(
        default=False,
        description="Store what MeetAI said. Handoff doc section 10 q4: undecided.",
    )
    persist_raw_audio_debug: bool = Field(
        default=False,
        description="Debug-only raw audio capture. Its own consent scope.",
    )
    raw_audio_debug_acknowledged: bool = Field(
        default=False,
        description=(
            "Explicit acknowledgement for the debug raw audio scope. Required "
            "separately so that enabling transcripts never unlocks raw audio."
        ),
    )

    # --- Tripwires -------------------------------------------------------
    # These are not feature switches. Setting either to True is refused, so
    # after a successful load both are always False. They exist so that a
    # misconfiguration is caught loudly instead of being ignored silently.
    requested_external_ai: bool = Field(
        default=False,
        description="Tripwire. Sending content to an external AI service is out of scope.",
    )
    requested_live_discord_voice: bool = Field(
        default=False,
        description="Tripwire. Live Discord voice is blocked by evidence gates.",
    )

    # ------------------------------------------------------------------ #
    # Validation
    # ------------------------------------------------------------------ #

    @field_validator("ui_host")
    @classmethod
    def _must_be_loopback(cls, value: str) -> str:
        """Refuse to expose the supervisor UI beyond this machine.

        The UI shows consent state and session status. The deployment target is
        the operator's own machine, not a service, so a non-loopback bind is a
        configuration mistake rather than a feature.

        The message names no value: a credential pasted one line too high in
        ``.env`` would otherwise be echoed here, and the field name is already
        in the error's location.
        """
        if value not in LOOPBACK_ADDRESSES:
            raise ValueError(
                "ui_host phai la dia chi loopback dang so (127.0.0.1 hoac ::1). "
                "Khong dung ten mien, ke ca localhost."
            )
        return value

    @field_validator("state_dir")
    @classmethod
    def _must_be_project_relative(cls, value: Path) -> Path:
        """Keep operational state inside the project directory.

        ``state_dir`` will hold consent receipts and operational metadata, so a
        path that leaves the machine - a UNC share, a mapped network drive, a
        cloud-synced folder - would ship that state off-box by configuration
        alone. It is the same class of mistake the ``ui_host`` rail prevents,
        on the write side instead of the listen side.

        The rule is an **allowlist**, which is why it is phrased as "must be
        relative, with no parent traversal" rather than as a list of bad
        locations. An earlier version tried to enumerate them and claimed in
        three documents to reject network drives and cloud folders; it rejected
        neither. ``Z:\\state`` and ``C:\\Users\\u\\OneDrive\\state`` were both
        accepted, because "is this a mapped drive" needs a Windows API call and
        "is this a cloud folder" needs a list of vendor directory names that
        changes and is localised. Requiring a relative path rejects all of
        them, plus ``/etc/passwd``, without having to recognise any of them.

        Residual, and stated rather than papered over: a relative path resolves
        under the process working directory, so if the *project itself* were
        placed inside a synced folder, the state would be synced too. That is
        outside what this validator can see. Putting state on another local
        disk is also refused, which is a real restriction; widening it should
        be a deliberate decision with its own check, not a loosening of this
        one.
        """
        raw = str(value)
        if raw.startswith(("\\\\", "//")) or PureWindowsPath(raw).drive.startswith("\\"):
            # Caught separately so the operator gets the specific diagnosis.
            raise ValueError(
                "state_dir khong duoc la duong dan UNC. State phai nam trong "
                "thu muc du an."
            )
        # `is_absolute()` is not enough on Windows: a rooted-but-driveless path
        # such as "/etc/passwd" reports False there, so the anchor is checked
        # directly. Tested, because that asymmetry is exactly the kind of thing
        # a reader assumes away.
        windows_view = PureWindowsPath(raw)
        if value.is_absolute() or windows_view.drive or windows_view.root:
            raise ValueError(
                "state_dir phai la duong dan tuong doi trong thu muc du an. "
                "Duong dan tuyet doi co the tro ra o mang, o dia khac, hoac "
                "thu muc dong bo cloud - khi do state roi khoi may."
            )
        if ".." in value.parts:
            raise ValueError(
                "state_dir khong duoc chua '..'. Duong dan di ra ngoai thu muc "
                "du an khong con duoc rang buoc boi kiem tra nay."
            )
        return value

    @field_validator("requested_external_ai")
    @classmethod
    def _external_ai_is_out_of_scope(cls, value: bool) -> bool:
        """Reject the external-AI tripwire at field level.

        Field level, not model level, and that choice is load-bearing: a
        model-level validator's error carries the whole raw input mapping,
        credentials included, into ``exc.errors()[i]["input"]``. A field-level
        error carries only this field's value, which is a bool.
        """
        if value:
            raise ValueError(
                "Gui audio hoac transcript cuoc hop toi dich vu AI ben ngoai nam "
                "ngoai pham vi MeetAI. Xoa bien cau hinh nay thay vi ghi de."
            )
        return value

    @field_validator("requested_live_discord_voice")
    @classmethod
    def _live_voice_is_gated(cls, value: bool) -> bool:
        """Reject the live-voice tripwire at field level. See the sibling above."""
        if value:
            raise ValueError(
                "Live Discord voice receive bi chan boi cong bang chung 0-S / 0-P / "
                "0-C. Tinh nang nay duoc mo bang bang chung va quyet dinh cua chu "
                "du an, khong phai bang cau hinh."
            )
        return value

    @model_validator(mode="after")
    def _apply_policy_rules(self) -> Self:
        """Apply the cross-field prohibitions from :mod:`meetai.policy`.

        Raises :class:`ConfigurationRejectedError` rather than ``ValueError``
        so it does not become a pydantic model-level error - which would put
        the raw input mapping, credentials and all, into the error payload.
        Pydantic lets a non-``ValueError`` exception propagate unwrapped.
        """
        violations = rejected_configuration(self.policy_flags)
        if violations:
            raise ConfigurationRejectedError(
                "Cau hinh bi tu choi: "
                + "; ".join(f"[{v.rule}] {v.reason}" for v in violations)
            )
        return self

    # ------------------------------------------------------------------ #
    # Construction guards
    # ------------------------------------------------------------------ #

    @classmethod
    def model_construct(cls, *args: Any, **kwargs: Any) -> Settings:
        """Refused.

        ``model_construct`` skips every validator by design, which would hand
        back a ``Settings`` with the tripwires armed and the policy rules never
        applied. There is no legitimate use for it here, and a well-meaning
        call in a fixture or a reload path would silently disarm every rail.
        """
        raise NotImplementedError(
            "Settings.model_construct bi vo hieu hoa vi no bo qua toan bo validator. "
            "Dung load_settings() hoac Settings.model_validate()."
        )

    def model_copy(
        self, *, update: Mapping[str, Any] | None = None, deep: bool = False
    ) -> Settings:
        """Copy with re-validation.

        pydantic's ``model_copy(update=...)`` does not re-validate and is not
        stopped by ``frozen=True``, so the stock implementation is another way
        to produce a ``Settings`` with the tripwires armed. Routing through
        ``model_validate`` keeps the invariants true for every instance that
        exists, not only for the ones built by the front door.
        """
        if not update:
            return super().model_copy(deep=deep)
        merged = {**self.model_dump(), **dict(update)}
        return type(self).model_validate(merged)

    # ------------------------------------------------------------------ #
    # Derived state
    # ------------------------------------------------------------------ #

    @property
    def policy_flags(self) -> ConfigurationFlags:
        """This configuration expressed in the framework-free policy vocabulary."""
        return ConfigurationFlags(
            consent_mode=self.consent_mode,
            late_join_policy=self.late_join_policy,
            persist_transcript=self.persist_transcript,
            persist_notes=self.persist_notes,
            persist_reply_journal=self.persist_reply_journal,
            persist_raw_audio_debug=self.persist_raw_audio_debug,
            raw_audio_debug_acknowledged=self.raw_audio_debug_acknowledged,
            requested_external_ai=self.requested_external_ai,
            requested_live_discord_voice=self.requested_live_discord_voice,
        )

    @property
    def any_content_persistence_enabled(self) -> bool:
        """True if any switch would write meeting content to disk."""
        return any(
            (
                self.persist_transcript,
                self.persist_notes,
                self.persist_reply_journal,
                self.persist_raw_audio_debug,
            )
        )

    @property
    def media_processing_allowed(self) -> bool:
        """Whether live media may be processed at all under this configuration."""
        return media_processing_allowed(self.policy_flags)

    @property
    def pending_decisions(self) -> tuple[str, ...]:
        """Policy choices still waiting on the operator.

        The supervisor UI shows these so "not configured" never looks like
        "configured and ready".
        """
        return pending_decisions(self.policy_flags)

    def require_media_processing_allowed(self) -> None:
        """Raise unless both policy choices have been decided.

        This is the gate every future media code path must call. It exists so
        that "pending_decision blocks media" is a property the code enforces
        rather than a sentence in a docstring.
        """
        if not self.media_processing_allowed:
            raise PendingDecisionError(
                "Chua the xu ly media: con quyet dinh chua chot - "
                + ", ".join(self.pending_decisions)
            )

    def assert_tripwires_disarmed(self) -> None:
        """Re-check the tripwires at point of use.

        Construction-time validation is a convenience, not the sole control:
        an instance can still be produced through pydantic internals. Any code
        about to act on this configuration calls this first, so a disarmed rail
        is caught where it matters rather than only where it was built.
        """
        if self.requested_external_ai or self.requested_live_discord_voice:
            raise ConfigurationRejectedError(
                "Tripwire dang bat tren doi tuong Settings nay. Day la loi noi bo: "
                "doi tuong duoc tao bang duong khong qua validation."
            )

    def redacted_summary(self) -> dict[str, Any]:
        """Settings rendered for display. No value that could be a secret appears.

        Credentials are reported as presence only, so a UI or a log line can
        say "token configured" without the token ever leaving this process.

        The tripwires are included even though a validly-constructed instance
        always has them ``False``: if an instance is ever produced through a
        path that skips validation, the status report must look different from
        a safe one rather than identical to it.
        """
        return {
            "ui_host": self.ui_host,
            "ui_port": self.ui_port,
            "state_dir": str(self.state_dir),
            "consent_mode": self.consent_mode.value,
            "late_join_policy": self.late_join_policy.value,
            "persist_transcript": self.persist_transcript,
            "persist_notes": self.persist_notes,
            "persist_reply_journal": self.persist_reply_journal,
            "persist_raw_audio_debug": self.persist_raw_audio_debug,
            "raw_audio_debug_acknowledged": self.raw_audio_debug_acknowledged,
            "any_content_persistence_enabled": self.any_content_persistence_enabled,
            "media_processing_allowed": self.media_processing_allowed,
            "pending_decisions": list(self.pending_decisions),
            "requested_external_ai": self.requested_external_ai,
            "requested_live_discord_voice": self.requested_live_discord_voice,
            "discord_bot_token_configured": self.discord_bot_token is not None,
            "google_oauth_client_secret_configured": (
                self.google_oauth_client_secret is not None
            ),
        }


# ---------------------------------------------------------------------- #
# Error rendering
# ---------------------------------------------------------------------- #


def sanitised_validation_errors(exc: ValidationError) -> list[str]:
    """Render a validation failure without any offending value.

    This is the only safe way to show a ``ValidationError`` from this module.
    ``str(exc)`` and ``exc.json()`` both embed the raw input: for a model-level
    error that input is the *whole* mapping, so a single bad flag would print
    the tail of a credential alongside it. ``include_input=False`` drops it,
    and the field location is enough to tell the operator what to fix.
    """
    return [
        f"{'.'.join(str(part) for part in err['loc']) or '<model>'}: {err['msg']}"
        for err in exc.errors(include_input=False, include_url=False)
    ]


# ---------------------------------------------------------------------- #
# Loading
# ---------------------------------------------------------------------- #


def _known_env_names() -> frozenset[str]:
    return frozenset(f"{ENV_PREFIX}{name}".upper() for name in Settings.model_fields)


def _unknown_meetai_names(names: Iterable[str]) -> list[str]:
    """Names that look like MeetAI settings but match no field."""
    known = _known_env_names()
    return sorted(
        {
            name
            for name in names
            if name.upper().startswith(ENV_PREFIX) and name.upper() not in known
        }
    )


def _read_env_file(env_file: Path | None) -> dict[str, str]:
    """Load a ``.env`` file into a mapping, or return empty if there is none.

    Uses python-dotenv rather than a hand-rolled split so quoting and escaping
    behave the way an operator editing ``.env`` expects.
    """
    if env_file is None or not env_file.is_file():
        return {}
    return {
        key: value
        for key, value in dotenv_values(env_file, encoding="utf-8").items()
        if value is not None
    }


def _to_field_overrides(env: Mapping[str, str]) -> dict[str, str]:
    """Map recognised ``MEETAI_*`` variables onto field names.

    Only names that match a declared field are returned; unrecognised ones are
    rejected earlier by :func:`_unknown_meetai_names`, by name, before any
    value is handled.
    """
    known = {f"{ENV_PREFIX}{name}".upper(): name for name in Settings.model_fields}
    return {
        known[name.upper()]: value for name, value in env.items() if name.upper() in known
    }


def _reject_prohibited_egress_vars(env: Mapping[str, str]) -> None:
    """Fail if an egress switch outside MeetAI's own namespace is set."""
    # Names only. A proxy setting is commonly written
    # `http://user:password@host`, so echoing the value here would put a
    # credential into a message that gets pasted into reports.
    found = sorted(name for name in env if _is_prohibited_egress_name(name))
    if found:
        raise ProhibitedEgressVariableError(
            "Bien moi truong co the gui du lieu ra ngoai may dang duoc dat: "
            + ", ".join(found)
            + ". MeetAI khong chay khi cac bien nay ton tai. Xoa chung roi thu lai."
        )


def load_settings(
    *,
    env: Mapping[str, str] | None = None,
    env_file: Path | None = DEFAULT_ENV_FILE,
    **overrides: Any,
) -> Settings:
    """Build settings from an environment mapping, a ``.env`` file and overrides.

    ``env`` defaults to ``os.environ`` and ``env_file`` to ``./.env``. Both are
    parameters rather than implicit globals so a caller - a test, or a future
    supervisor showing "configuration as loaded" - can be explicit about what
    it is reading.

    Raises :class:`ProhibitedEgressVariableError` when an egress switch is set,
    :class:`UnknownSettingError` on an unrecognised ``MEETAI_*`` name from
    either source, :class:`ConfigurationRejectedError` on a refused policy
    combination, and ``pydantic.ValidationError`` on a malformed value. The
    caller must let all four propagate: a supervisor that cannot validate its
    own configuration must not start. When reporting a ``ValidationError`` to a
    human, render it with :func:`sanitised_validation_errors`.
    """
    environment: Mapping[str, str] = os.environ if env is None else env
    from_file = _read_env_file(env_file)

    _reject_prohibited_egress_vars(environment)
    _reject_prohibited_egress_vars(from_file)

    # Names first, before any value is touched, so the error can name the
    # offending key without rendering what was assigned to it.
    unknown = _unknown_meetai_names([*from_file, *environment])
    if unknown:
        raise UnknownSettingError(
            "Bien cau hinh khong duoc nhan dang (co the do go sai ten): "
            + ", ".join(unknown)
        )

    # Precedence, lowest to highest: .env file, process environment, explicit
    # overrides. The environment beating .env matches how operators expect a
    # one-off `VAR=x meetai status` to behave.
    data: dict[str, Any] = {}
    data.update(_to_field_overrides(from_file))
    data.update(_to_field_overrides(environment))
    data.update(overrides)

    return Settings(**data)
