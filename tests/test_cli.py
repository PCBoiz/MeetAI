"""Tests for the CLI status report.

Two properties matter here: the report must not overstate what the build can
do, and no failure path may print a configuration value. The second one is
tested by pairing a credential with every kind of invalid configuration -
exactly the combination that was missing when the leak existed.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from meetai.capabilities import CapabilityName
from meetai.cli import EXIT_CONFIG_INVALID, EXIT_OK, main
from tests.conftest import CANARY_SECRET


class TestStatusCommand:
    def test_exits_zero(self, capsys: pytest.CaptureFixture[str]) -> None:
        assert main(["status"]) == EXIT_OK
        assert "MeetAI" in capsys.readouterr().out

    def test_unimplemented_capabilities_report_off(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        assert main(["status", "--json"]) == EXIT_OK
        report = json.loads(capsys.readouterr().out)
        capabilities = report["capabilities"]
        for name in (
            CapabilityName.LIVE_VOICE_RECEIVE,
            CapabilityName.ASR,
            CapabilityName.LLM,
            CapabilityName.TTS,
            CapabilityName.PLATFORM_ADAPTER_DISCORD,
            CapabilityName.CALENDAR_CONNECTOR,
        ):
            assert capabilities[name.value]["available"] is False

    def test_every_off_capability_carries_a_reason(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Universal, not a single-key spot check.

        The earlier version asserted one reason existed, which four reason-less
        capabilities passed.
        """
        main(["status", "--json"])
        report = json.loads(capsys.readouterr().out)
        for name, entry in report["capabilities"].items():
            if not entry["available"]:
                assert entry["blocked_reason"], f"{name} thieu ly do"

    def test_human_output_shows_a_reason_for_every_off_line(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        main(["status"])
        for line in capsys.readouterr().out.splitlines():
            if line.strip().startswith("[OFF]"):
                assert "<-" in line, f"dong khong co ly do: {line}"

    def test_pending_decisions_are_surfaced(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        main(["status", "--json"])
        report = json.loads(capsys.readouterr().out)
        assert set(report["settings"]["pending_decisions"]) == {
            "consent_mode",
            "late_join_policy",
        }

    def test_human_output_states_no_content_persistence(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        main(["status"])
        out = capsys.readouterr().out
        assert "luu noi dung cuoc hop : KHONG" in out
        assert "xu ly media duoc phep : KHONG" in out

    def test_human_output_is_ascii(self, capsys: pytest.CaptureFixture[str]) -> None:
        """A Windows console code page is often not UTF-8.

        Vietnamese with diacritics would render as mojibake, so the terminal
        surface is deliberately unaccented. The web UI uses full Vietnamese.
        """
        main(["status"])
        capsys.readouterr().out.encode("ascii")  # must not raise


class TestSecretsNeverPrinted:
    @pytest.mark.parametrize("json_flag", [True, False])
    def test_success_path_does_not_print_the_token(
        self,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
        json_flag: bool,
    ) -> None:
        monkeypatch.setenv("MEETAI_DISCORD_BOT_TOKEN", CANARY_SECRET)
        argv = ["status", "--json"] if json_flag else ["status"]
        assert main(argv) == EXIT_OK
        captured = capsys.readouterr()
        assert CANARY_SECRET not in captured.out
        assert CANARY_SECRET not in captured.err

    @pytest.mark.parametrize(
        "bad_var",
        [
            "MEETAI_REQUESTED_EXTERNAL_AI",
            "MEETAI_REQUESTED_LIVE_DISCORD_VOICE",
        ],
    )
    def test_tripwire_failure_does_not_print_the_token(
        self,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
        bad_var: str,
    ) -> None:
        """The combination that produced the original leak.

        A credential plus an invalid configuration: pydantic's error payload
        held the raw input mapping and the CLI printed it verbatim.
        """
        monkeypatch.setenv("MEETAI_DISCORD_BOT_TOKEN", CANARY_SECRET)
        monkeypatch.setenv(bad_var, "true")
        assert main(["status"]) == EXIT_CONFIG_INVALID
        captured = capsys.readouterr()
        assert CANARY_SECRET not in captured.out
        assert CANARY_SECRET not in captured.err

    def test_misspelled_credential_in_env_file_does_not_leak(
        self,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
        tmp_path: Path,
    ) -> None:
        """The highest-probability real-world leak.

        `.env` is the documented place for credentials, and a misspelled name
        is exactly what the unknown-name guard exists to catch.
        """
        (tmp_path / ".env").write_text(
            f"MEETAI_DISCORD_TOKEN={CANARY_SECRET}\n", encoding="utf-8"
        )
        monkeypatch.chdir(tmp_path)
        assert main(["status"]) == EXIT_CONFIG_INVALID
        captured = capsys.readouterr()
        assert CANARY_SECRET not in captured.err
        assert "MEETAI_DISCORD_TOKEN" in captured.err

    @pytest.mark.parametrize(
        "wrong_var", ["MEETAI_UI_HOST", "MEETAI_UI_PORT", "MEETAI_CONSENT_MODE"]
    )
    def test_credential_pasted_into_a_known_variable_does_not_leak(
        self,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
        wrong_var: str,
    ) -> None:
        """Copy/pasting a token one line too high in `.env`."""
        monkeypatch.setenv(wrong_var, CANARY_SECRET)
        assert main(["status"]) == EXIT_CONFIG_INVALID
        assert CANARY_SECRET not in capsys.readouterr().err

    def test_credential_in_env_file_success_path_not_printed(
        self,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
        tmp_path: Path,
    ) -> None:
        (tmp_path / ".env").write_text(
            f"MEETAI_DISCORD_BOT_TOKEN={CANARY_SECRET}\n", encoding="utf-8"
        )
        monkeypatch.chdir(tmp_path)
        assert main(["status", "--json"]) == EXIT_OK
        captured = capsys.readouterr()
        assert CANARY_SECRET not in captured.out
        assert CANARY_SECRET not in captured.err
        assert json.loads(captured.out)["settings"]["discord_bot_token_configured"]


class TestInvalidConfiguration:
    def test_refuses_to_start_on_prohibited_setting(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        monkeypatch.setenv("MEETAI_REQUESTED_EXTERNAL_AI", "true")
        assert main(["status"]) == EXIT_CONFIG_INVALID
        assert "khong khoi dong" in capsys.readouterr().err

    def test_refuses_to_start_on_unknown_setting(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("MEETAI_RECORD_EVERYTHING", "true")
        assert main(["status"]) == EXIT_CONFIG_INVALID

    def test_refuses_to_start_on_bad_value(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        monkeypatch.setenv("MEETAI_UI_PORT", "70000")
        assert main(["status"]) == EXIT_CONFIG_INVALID
        assert "ui_port" in capsys.readouterr().err

    def test_refuses_to_start_on_egress_variable(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://x.example:4318")
        assert main(["status"]) == EXIT_CONFIG_INVALID
        assert "OTEL_EXPORTER_OTLP_ENDPOINT" in capsys.readouterr().err

    def test_refuses_to_start_on_persistence_before_consent(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        monkeypatch.setenv("MEETAI_PERSIST_TRANSCRIPT", "true")
        assert main(["status"]) == EXIT_CONFIG_INVALID
        assert "consent" in capsys.readouterr().err

    def test_no_traceback_on_any_failure(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """An escaping exception would print a traceback, and a traceback can
        carry frame locals holding the raw configuration mapping."""
        monkeypatch.setenv("MEETAI_REQUESTED_EXTERNAL_AI", "true")
        assert main(["status"]) == EXIT_CONFIG_INVALID
        captured = capsys.readouterr()
        assert "Traceback" not in captured.err
        assert "Traceback" not in captured.out


class TestLogging:
    def test_log_level_flag_is_accepted(self) -> None:
        assert main(["status", "--log-level", "DEBUG"]) == EXIT_OK

    def test_log_output_carries_no_credential(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        monkeypatch.setenv("MEETAI_DISCORD_BOT_TOKEN", CANARY_SECRET)
        main(["status", "--log-level", "DEBUG"])
        assert CANARY_SECRET not in capsys.readouterr().err
