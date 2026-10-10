"""Tests for fail-closed settings behaviour.

These exist to make the safety defaults regression-proof: if a default is later
flipped to "convenient", a test fails rather than a meeting leaking.

Where a test asserts a *property* rather than a default, it is written so that
deleting the mechanism makes it fail. An assertion that only restates the
default value would pass against a hardcoded stub, which is how the earlier
version of this file gave false coverage credit.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from pydantic import SecretStr, ValidationError

from meetai.errors import (
    ConfigurationRejectedError,
    PendingDecisionError,
    ProhibitedEgressVariableError,
    UnknownSettingError,
)
from meetai.policy import ConsentMode, LateJoinPolicy
from meetai.settings import (
    Settings,
    _is_prohibited_egress_name,
    load_settings,
    sanitised_validation_errors,
)
from tests.conftest import CANARY_SECRET


class TestFailClosedDefaults:
    def test_no_content_persistence_by_default(self) -> None:
        s = load_settings()
        assert s.persist_transcript is False
        assert s.persist_notes is False
        assert s.persist_reply_journal is False
        assert s.persist_raw_audio_debug is False
        assert s.any_content_persistence_enabled is False

    @pytest.mark.parametrize(
        "field",
        ["persist_transcript", "persist_notes", "persist_reply_journal"],
    )
    def test_any_single_switch_flips_the_aggregate(self, field: str) -> None:
        """The aggregate must react to each switch individually.

        With all four inputs False the aggregate is False for any
        implementation, including one that dropped a field from its `any(...)`.
        Turning each on in turn is what actually tests it.
        """
        overrides: dict[str, Any] = {
            "consent_mode": ConsentMode.PER_PARTICIPANT,
            field: True,
        }
        s = load_settings(**overrides)
        assert s.any_content_persistence_enabled is True

    def test_undecided_policies_are_pending(self) -> None:
        s = load_settings()
        assert s.consent_mode is ConsentMode.PENDING_DECISION
        assert s.late_join_policy is LateJoinPolicy.PENDING_DECISION
        assert set(s.pending_decisions) == {"consent_mode", "late_join_policy"}

    def test_a_decided_policy_leaves_the_pending_list(self) -> None:
        """Deleting the pending logic would leave this failing.

        The previous version only ever checked the both-pending case, which a
        hardcoded two-element return would satisfy.
        """
        s = load_settings(consent_mode=ConsentMode.PER_PARTICIPANT)
        assert s.pending_decisions == ("late_join_policy",)

    def test_media_blocked_until_both_decided(self) -> None:
        assert load_settings().media_processing_allowed is False
        assert (
            load_settings(
                consent_mode=ConsentMode.PER_PARTICIPANT
            ).media_processing_allowed
            is False
        )
        assert (
            load_settings(
                late_join_policy=LateJoinPolicy.A1_CIRCUIT_BREAKER
            ).media_processing_allowed
            is False
        )

    @pytest.mark.parametrize(
        "mode", [ConsentMode.PER_PARTICIPANT, ConsentMode.HOST_COORDINATED]
    )
    @pytest.mark.parametrize(
        "late", [LateJoinPolicy.A1_CIRCUIT_BREAKER, LateJoinPolicy.A3_ADMISSION_CONTROL]
    )
    def test_media_allowed_only_when_fully_decided(
        self, mode: ConsentMode, late: LateJoinPolicy
    ) -> None:
        s = load_settings(consent_mode=mode, late_join_policy=late)
        assert s.media_processing_allowed is True

    def test_require_media_processing_raises_while_pending(self) -> None:
        with pytest.raises(PendingDecisionError, match="consent_mode"):
            load_settings().require_media_processing_allowed()

    def test_pending_decision_enum_member_is_falsy(self) -> None:
        """`if settings.consent_mode:` must not pass while undecided.

        A `(str, Enum)` member is truthy, which would make that natural-looking
        guard fail open on exactly the state that must block.
        """
        assert not ConsentMode.PENDING_DECISION
        assert not LateJoinPolicy.PENDING_DECISION
        assert ConsentMode.PER_PARTICIPANT
        assert LateJoinPolicy.A1_CIRCUIT_BREAKER


class TestProhibitedConfigurations:
    @pytest.mark.parametrize(
        ("field", "expected"),
        [
            ("requested_external_ai", "AI ben ngoai"),
            ("requested_live_discord_voice", "0-S"),
        ],
    )
    def test_tripwires_rejected_via_kwarg(self, field: str, expected: str) -> None:
        with pytest.raises(ValidationError) as exc_info:
            overrides: dict[str, Any] = {field: True}
            load_settings(**overrides)
        assert expected in str(exc_info.value)

    @pytest.mark.parametrize(
        "variable",
        ["MEETAI_REQUESTED_EXTERNAL_AI", "MEETAI_REQUESTED_LIVE_DISCORD_VOICE"],
    )
    def test_tripwires_rejected_via_environment(
        self, monkeypatch: pytest.MonkeyPatch, variable: str
    ) -> None:
        """The environment is the channel an operator actually uses."""
        monkeypatch.setenv(variable, "true")
        with pytest.raises(ValidationError):
            load_settings()

    @pytest.mark.parametrize("variable", ["MEETAI_REQUESTED_EXTERNAL_AI"])
    def test_tripwires_rejected_via_env_file(self, env_file: Path, variable: str) -> None:
        env_file.write_text(f"{variable}=true\n", encoding="utf-8")
        with pytest.raises(ValidationError):
            load_settings(env_file=env_file)

    @pytest.mark.parametrize(
        "value", ["true", "True", "TRUE", "1", "yes", "on", "y", "t"]
    )
    def test_no_truthy_spelling_evades_the_tripwire(
        self, monkeypatch: pytest.MonkeyPatch, value: str
    ) -> None:
        monkeypatch.setenv("MEETAI_REQUESTED_EXTERNAL_AI", value)
        with pytest.raises(ValidationError):
            load_settings()

    @pytest.mark.parametrize(
        "host", ["0.0.0.0", "::", "192.168.1.5", "localhost", "127.0.0.1.nip.io", "127.1"]
    )
    def test_non_loopback_literal_rejected(
        self, monkeypatch: pytest.MonkeyPatch, host: str
    ) -> None:
        """Includes `localhost`: a name resolved at bind time is not a guarantee."""
        monkeypatch.setenv("MEETAI_UI_HOST", host)
        with pytest.raises(ValidationError, match="loopback"):
            load_settings()

    @pytest.mark.parametrize("host", ["127.0.0.1", "::1"])
    def test_loopback_literals_accepted(
        self, monkeypatch: pytest.MonkeyPatch, host: str
    ) -> None:
        monkeypatch.setenv("MEETAI_UI_HOST", host)
        assert load_settings().ui_host == host

    @pytest.mark.parametrize(
        "path",
        [
            pytest.param(r"\\evil-nas\share\state", id="unc-deep"),
            pytest.param(r"\\nas\share", id="unc-share-root"),
            pytest.param("//evil-nas/share/state", id="unc-forward-slash"),
        ],
    )
    def test_unc_state_dir_rejected(
        self, monkeypatch: pytest.MonkeyPatch, path: str
    ) -> None:
        """State would leave the machine via a network path, silently.

        The share-root case is here because the earlier version of this test
        used only three-component UNC paths. Two-component paths normalise
        differently under `pathlib`, so a narrower parametrization would have
        passed over an open rail.
        """
        monkeypatch.setenv("MEETAI_STATE_DIR", path)
        with pytest.raises(ValidationError, match="UNC"):
            load_settings()

    @pytest.mark.parametrize(
        "path",
        [
            pytest.param(r"Z:\state", id="mapped-network-drive"),
            pytest.param(r"C:\Users\u\OneDrive\state", id="onedrive"),
            pytest.param(r"C:\Users\u\Dropbox\meetai", id="dropbox"),
            pytest.param(r"D:\meetai-state", id="other-local-drive"),
            pytest.param("/etc/passwd", id="rooted-posix"),
            pytest.param("/var/state", id="rooted-no-drive"),
        ],
    )
    def test_absolute_state_dir_rejected(
        self, monkeypatch: pytest.MonkeyPatch, path: str
    ) -> None:
        """Only project-relative paths are accepted.

        An allowlist, because enumerating bad locations did not work: an
        earlier version claimed in three documents to reject mapped network
        drives and cloud-synced folders and rejected neither. The rooted-posix
        cases are included because `Path("/etc/passwd").is_absolute()` is
        False on Windows -- no drive letter -- so checking only `is_absolute()`
        leaves them open.
        """
        monkeypatch.setenv("MEETAI_STATE_DIR", path)
        with pytest.raises(ValidationError, match="tuong doi"):
            load_settings()

    @pytest.mark.parametrize("path", ["../../..", "../sibling", "var/../../escape"])
    def test_parent_traversal_in_state_dir_rejected(
        self, monkeypatch: pytest.MonkeyPatch, path: str
    ) -> None:
        """A path that climbs out is no longer bounded by this check."""
        monkeypatch.setenv("MEETAI_STATE_DIR", path)
        with pytest.raises(ValidationError, match=r"\.\."):
            load_settings()

    @pytest.mark.parametrize("path", ["var", "var/state", "state"])
    def test_project_relative_state_dir_accepted(
        self, monkeypatch: pytest.MonkeyPatch, path: str
    ) -> None:
        """The rail must still permit the intended configuration."""
        monkeypatch.setenv("MEETAI_STATE_DIR", path)
        assert load_settings().state_dir == Path(path)

    def test_persistence_rejected_while_consent_undecided(self) -> None:
        with pytest.raises(
            ConfigurationRejectedError, match="persistence_before_consent"
        ):
            load_settings(persist_transcript=True)

    def test_raw_audio_debug_needs_its_own_acknowledgement(self) -> None:
        """Enabling transcripts must not unlock raw audio."""
        with pytest.raises(ConfigurationRejectedError, match="raw_audio_debug"):
            load_settings(
                consent_mode=ConsentMode.PER_PARTICIPANT,
                persist_transcript=True,
                persist_raw_audio_debug=True,
            )

    def test_raw_audio_debug_allowed_with_acknowledgement(self) -> None:
        s = load_settings(
            consent_mode=ConsentMode.PER_PARTICIPANT,
            persist_raw_audio_debug=True,
            raw_audio_debug_acknowledged=True,
        )
        assert s.persist_raw_audio_debug is True

    def test_unknown_kwarg_is_rejected(self) -> None:
        with pytest.raises(ValidationError):
            load_settings(record_everything=True)

    @pytest.mark.parametrize("port", ["70000", "80", "not-a-number"])
    def test_invalid_port_rejected(
        self, monkeypatch: pytest.MonkeyPatch, port: str
    ) -> None:
        monkeypatch.setenv("MEETAI_UI_PORT", port)
        with pytest.raises(ValidationError):
            load_settings()

    def test_invalid_enum_value_rejected(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("MEETAI_CONSENT_MODE", "whatever_seems_reasonable")
        with pytest.raises(ValidationError):
            load_settings()


class TestEgressVariables:
    """OTEL_* is read by library code, so the MEETAI_* guard cannot see it."""

    @pytest.mark.parametrize(
        "variable",
        [
            "OTEL_EXPORTER_OTLP_ENDPOINT",
            "OTEL_TRACES_EXPORTER",
            "OTEL_SDK_DISABLED",
            "OTEL_PYTHON_TRACER_PROVIDER",
        ],
    )
    def test_otel_variable_refuses_startup(
        self, monkeypatch: pytest.MonkeyPatch, variable: str
    ) -> None:
        monkeypatch.setenv(variable, "http://somewhere.example:4318")
        with pytest.raises(ProhibitedEgressVariableError, match=variable):
            load_settings()

    def test_otel_variable_in_env_file_also_refuses(self, env_file: Path) -> None:
        env_file.write_text(
            "OTEL_EXPORTER_OTLP_ENDPOINT=http://somewhere.example:4318\n",
            encoding="utf-8",
        )
        with pytest.raises(ProhibitedEgressVariableError):
            load_settings(env_file=env_file)

    @pytest.mark.parametrize(
        "variable",
        [
            # Model resolution: each of these decides WHERE weights come from,
            # so any of them can turn a local-file design into a downloading
            # one without a line of MeetAI code changing.
            "HF_HUB_OFFLINE",
            "HF_HOME",
            "HF_ENDPOINT",
            "HF_TOKEN",
            "HUGGINGFACE_HUB_CACHE",
            "TRANSFORMERS_OFFLINE",
            "TRANSFORMERS_CACHE",
            # Proxy routing: these can route around the OS-level egress
            # isolation that decision 5 requires, which is the concrete reason
            # they are here and `XDG_CACHE_HOME` is not.
            "HTTP_PROXY",
            "HTTPS_PROXY",
            "ALL_PROXY",
            "NO_PROXY",
        ],
    )
    def test_a_model_resolution_or_proxy_variable_refuses_startup(
        self, monkeypatch: pytest.MonkeyPatch, variable: str
    ) -> None:
        """[CHỐT THEO ỦY QUYỀN CỦA SƠN] 2026-10-10, decision S2.1 #3.

        Measured before the change: all twelve of these started MeetAI fine.
        """
        monkeypatch.setenv(variable, "http://somewhere.example:8080")
        with pytest.raises(ProhibitedEgressVariableError, match=variable):
            load_settings()

    @pytest.mark.parametrize("value", ["1", "0", "", "  ", "false", "offline"])
    def test_presence_is_what_refuses_never_the_value(
        self, monkeypatch: pytest.MonkeyPatch, value: str
    ) -> None:
        """Including ``HF_HUB_OFFLINE=1``, which reads as the safe setting.

        This is the whole point of blocking on presence. A guard that let
        ``HF_HUB_OFFLINE=1`` through would teach the operator that the variable
        is effective here - and the day it becomes ``0``, the guard says
        nothing. An empty string is a set variable too.
        """
        monkeypatch.setenv("HF_HUB_OFFLINE", value)
        with pytest.raises(ProhibitedEgressVariableError, match="HF_HUB_OFFLINE"):
            load_settings()

    def test_the_refusal_names_the_variable_and_never_its_value(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A proxy URL can carry credentials, so the value must not be echoed.

        ``http://user:password@proxy`` is an ordinary way to write a proxy
        setting. The old message only ever joined names, and this pins that
        property rather than trusting it to stay: the refusal is read aloud in
        reports, and a credential inside a proxy URL would travel with it.
        """
        monkeypatch.setenv("HTTPS_PROXY", f"http://user:{CANARY_SECRET}@proxy.example")
        with pytest.raises(ProhibitedEgressVariableError) as caught:
            load_settings()
        rendered = str(caught.value)
        assert "HTTPS_PROXY" in rendered
        assert CANARY_SECRET not in rendered
        assert "user" not in rendered
        assert "proxy.example" not in rendered

    def test_xdg_cache_home_is_deliberately_still_accepted(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Recorded as a decision, not an oversight.

        ``XDG_CACHE_HOME`` relocates a cache. It cannot create a network path
        and it cannot route around a firewall rule, which are the two reasons
        the families above are blocked. Its real residual - a cache landing in
        a synced folder - is the one already recorded for ``state_dir``, and
        refusing a generic variable would buy none of it back.
        """
        monkeypatch.setenv("XDG_CACHE_HOME", "D:/cache")
        assert load_settings().consent_mode is ConsentMode.PENDING_DECISION

    def test_the_families_are_a_closed_tuple_not_a_substring_search(self) -> None:
        """``PROXY_SETTINGS`` must not be caught by the ``_PROXY`` suffix rule.

        A substring test for "PROXY" would also reject a MeetAI-unrelated
        variable that merely mentions it. The suffix is anchored, so a name
        that ends in ``_PROXY`` is rejected and one that merely contains the
        word is not - which is the difference between a rule and a guess.
        """
        assert _is_prohibited_egress_name("HTTPS_PROXY")
        assert _is_prohibited_egress_name("https_proxy")
        assert not _is_prohibited_egress_name("PROXY_SETTINGS")
        assert not _is_prohibited_egress_name("MY_PROXYTOOL")
        assert not _is_prohibited_egress_name("SHF_HOME")
        assert _is_prohibited_egress_name("HF_HOME")

    def test_unrelated_variables_are_left_alone(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("SOME_OTHER_APP_SETTING", "true")
        load_settings()  # must not raise


class TestUnknownNames:
    def test_unknown_prefixed_env_var_rejected(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("MEETAI_PERSIST_TRANSCRPIT", "true")
        with pytest.raises(UnknownSettingError, match="MEETAI_PERSIST_TRANSCRPIT"):
            load_settings()

    def test_unknown_key_in_env_file_rejected(self, env_file: Path) -> None:
        """The guard must cover `.env`, which is where credentials live."""
        env_file.write_text(f"MEETAI_DISCORD_TOKEN={CANARY_SECRET}\n", encoding="utf-8")
        with pytest.raises(UnknownSettingError, match="MEETAI_DISCORD_TOKEN"):
            load_settings(env_file=env_file)

    def test_env_file_rejection_does_not_leak_the_value(self, env_file: Path) -> None:
        env_file.write_text(f"MEETAI_DISCORD_TOKEN={CANARY_SECRET}\n", encoding="utf-8")
        with pytest.raises(UnknownSettingError) as exc_info:
            load_settings(env_file=env_file)
        assert CANARY_SECRET not in str(exc_info.value)

    def test_env_rejection_does_not_leak_the_value(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("MEETAI_DISCORD_TOKEN", CANARY_SECRET)
        with pytest.raises(UnknownSettingError) as exc_info:
            load_settings()
        assert CANARY_SECRET not in str(exc_info.value)

    def test_lowercase_name_still_caught(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("meetai_bogus_name", "1")
        with pytest.raises(UnknownSettingError):
            load_settings()


class TestEnvFileLoading:
    def test_known_key_from_env_file_is_applied(self, env_file: Path) -> None:
        env_file.write_text("MEETAI_UI_PORT=9999\n", encoding="utf-8")
        assert load_settings(env_file=env_file).ui_port == 9999

    def test_environment_beats_env_file(
        self, monkeypatch: pytest.MonkeyPatch, env_file: Path
    ) -> None:
        env_file.write_text("MEETAI_UI_PORT=9999\n", encoding="utf-8")
        monkeypatch.setenv("MEETAI_UI_PORT", "8888")
        assert load_settings(env_file=env_file).ui_port == 8888

    def test_overrides_beat_everything(
        self, monkeypatch: pytest.MonkeyPatch, env_file: Path
    ) -> None:
        env_file.write_text("MEETAI_UI_PORT=9999\n", encoding="utf-8")
        monkeypatch.setenv("MEETAI_UI_PORT", "8888")
        assert load_settings(env_file=env_file, ui_port=7777).ui_port == 7777

    def test_missing_env_file_is_not_an_error(self, tmp_path: Path) -> None:
        load_settings(env_file=tmp_path / "does-not-exist")

    def test_comments_and_blank_lines_ignored(self, env_file: Path) -> None:
        env_file.write_text("# a comment\n\nMEETAI_UI_PORT=9001\n", encoding="utf-8")
        assert load_settings(env_file=env_file).ui_port == 9001

    def test_explicit_env_mapping_isolates_from_the_process(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """An explicit mapping must be the only environment consulted."""
        monkeypatch.setenv("MEETAI_UI_PORT", "8888")
        s = load_settings(env={"MEETAI_UI_PORT": "7001"}, env_file=None)
        assert s.ui_port == 7001


class TestSecretHandling:
    def test_summary_reports_presence_not_value(self) -> None:
        s = load_settings(discord_bot_token=SecretStr(CANARY_SECRET))
        summary = s.redacted_summary()
        assert summary["discord_bot_token_configured"] is True
        assert CANARY_SECRET not in repr(summary)
        assert "discord_bot_token" not in summary

    @pytest.mark.parametrize("field", ["discord_bot_token", "google_oauth_client_secret"])
    def test_both_credentials_are_presence_only(self, field: str) -> None:
        overrides: dict[str, Any] = {field: SecretStr(CANARY_SECRET)}
        s = load_settings(**overrides)
        summary = s.redacted_summary()
        assert summary[f"{field}_configured"] is True
        assert CANARY_SECRET not in json.dumps(summary, default=str)

    def test_secret_absent_from_model_repr(self) -> None:
        s = load_settings(google_oauth_client_secret=SecretStr(CANARY_SECRET))
        assert CANARY_SECRET not in repr(s)
        assert CANARY_SECRET not in str(s)
        assert CANARY_SECRET not in str(s.model_dump())

    def test_summary_is_json_safe(self) -> None:
        s = load_settings(discord_bot_token=SecretStr("x"))
        json.dumps(s.redacted_summary())  # must not raise


class TestValidationErrorSanitising:
    """The leak that mattered: pydantic puts the raw input in its errors."""

    def test_sanitised_errors_drop_the_input(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("MEETAI_DISCORD_BOT_TOKEN", CANARY_SECRET)
        monkeypatch.setenv("MEETAI_UI_HOST", "0.0.0.0")
        with pytest.raises(ValidationError) as exc_info:
            load_settings()

        rendered = " | ".join(sanitised_validation_errors(exc_info.value))
        assert CANARY_SECRET not in rendered
        assert "ui_host" in rendered

    @pytest.mark.parametrize(
        "variable",
        [
            "MEETAI_REQUESTED_EXTERNAL_AI",
            "MEETAI_REQUESTED_LIVE_DISCORD_VOICE",
        ],
    )
    def test_tripwire_error_payload_carries_no_credential(
        self, monkeypatch: pytest.MonkeyPatch, variable: str
    ) -> None:
        """Rails are field validators so the error never holds the whole mapping.

        A model-level validator's error carries the raw input dict - credentials
        and all - in `errors()[i]["input"]`, untruncated. This asserts the
        credential is absent from every rendering of the exception, not only
        from `str()`.
        """
        monkeypatch.setenv("MEETAI_DISCORD_BOT_TOKEN", CANARY_SECRET)
        monkeypatch.setenv(variable, "true")
        with pytest.raises(ValidationError) as exc_info:
            load_settings()

        exc = exc_info.value
        assert CANARY_SECRET not in str(exc)
        assert CANARY_SECRET not in repr(exc.errors())
        assert CANARY_SECRET not in exc.json()
        assert CANARY_SECRET not in " | ".join(sanitised_validation_errors(exc))

    def test_ui_host_error_does_not_echo_the_value(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A credential pasted into the wrong known variable must not be echoed."""
        monkeypatch.setenv("MEETAI_UI_HOST", CANARY_SECRET)
        with pytest.raises(ValidationError) as exc_info:
            load_settings()
        assert CANARY_SECRET not in str(exc_info.value)
        assert CANARY_SECRET not in " | ".join(
            sanitised_validation_errors(exc_info.value)
        )


class TestConstructionGuards:
    """Every way to produce a Settings must preserve the invariants."""

    def test_plain_assignment_is_frozen(self) -> None:
        s = load_settings()
        with pytest.raises(ValidationError):
            s.persist_transcript = True

    def test_model_construct_is_refused(self) -> None:
        """`model_construct` skips every validator by design."""
        with pytest.raises(NotImplementedError):
            Settings.model_construct(requested_external_ai=True)

    def test_model_copy_revalidates(self) -> None:
        s = load_settings()
        with pytest.raises(ValidationError):
            s.model_copy(update={"requested_external_ai": True})

    def test_model_copy_without_update_still_works(self) -> None:
        s = load_settings()
        assert s.model_copy().ui_port == s.ui_port

    def test_model_validate_applies_the_rails(self) -> None:
        with pytest.raises(ValidationError):
            Settings.model_validate({"requested_external_ai": True})

    def test_subclass_inherits_the_rails(self) -> None:
        class Sub(Settings):
            pass

        with pytest.raises(ValidationError):
            Sub(requested_external_ai=True)

    def test_assert_tripwires_detects_a_bypassed_instance(self) -> None:
        """Construction-time validation is not the only control.

        `object.__setattr__` defeats `frozen=True`. The point-of-use check is
        what catches an instance built through pydantic internals.
        """
        s = load_settings()
        object.__setattr__(s, "requested_external_ai", True)
        with pytest.raises(ConfigurationRejectedError):
            s.assert_tripwires_disarmed()

    def test_bypassed_instance_is_visible_in_the_summary(self) -> None:
        """A disarmed rail must not render identically to a safe one."""
        s = load_settings()
        object.__setattr__(s, "requested_external_ai", True)
        assert s.redacted_summary()["requested_external_ai"] is True
