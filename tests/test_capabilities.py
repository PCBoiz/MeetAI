"""Tests that the capability report cannot lie optimistically.

The dangerous direction is a build claiming readiness it lacks, so the
invariants under test are structural: an unavailable capability cannot exist
without a reason, and a capability cannot go missing from the report.
"""

from __future__ import annotations

import pytest

from meetai.capabilities import (
    BlockedBy,
    Capability,
    CapabilityName,
    CapabilityReport,
    current_capabilities,
)


class TestCapabilityInvariants:
    def test_unavailable_without_a_discriminator_is_refused(self) -> None:
        """The UI needs a stable code to decide whether to render a control."""
        with pytest.raises(ValueError, match="thieu blocked_by"):
            Capability(CapabilityName.ASR, available=False, blocked_reason="not built")

    def test_unavailable_without_reason_is_refused(self) -> None:
        with pytest.raises(ValueError, match="thieu ly do"):
            Capability(
                CapabilityName.ASR,
                available=False,
                blocked_by=BlockedBy.NOT_BUILT,
            )

    def test_unavailable_with_empty_reason_is_refused(self) -> None:
        with pytest.raises(ValueError, match="thieu ly do"):
            Capability(
                CapabilityName.ASR,
                available=False,
                blocked_reason="",
                blocked_by=BlockedBy.NOT_BUILT,
            )

    def test_available_with_a_discriminator_is_refused(self) -> None:
        with pytest.raises(ValueError, match="co blocked_by"):
            Capability(
                CapabilityName.ASR,
                available=True,
                blocked_by=BlockedBy.NOT_BUILT,
            )

    def test_available_with_reason_is_refused(self) -> None:
        """A contradictory record would render ambiguously."""
        with pytest.raises(ValueError, match="co ly do bi chan"):
            Capability(
                CapabilityName.ASR, available=True, blocked_reason="should not be here"
            )

    def test_available_capability_is_accepted(self) -> None:
        assert Capability(CapabilityName.ASR, available=True).display_status == "ON"

    def test_synthetic_capability_reports_mock(self) -> None:
        """A mock must never display the same as a real integration."""
        cap = Capability(
            CapabilityName.PLATFORM_ADAPTER_DISCORD, available=True, synthetic=True
        )
        assert cap.display_status == "MOCK"

    def test_unavailable_reports_off(self) -> None:
        cap = Capability(
            CapabilityName.ASR,
            available=False,
            blocked_reason="not built",
            blocked_by=BlockedBy.NOT_BUILT,
        )
        assert cap.display_status == "OFF"


class TestReportCompleteness:
    def test_missing_capability_is_refused(self) -> None:
        """A capability added to the enum and forgotten must not vanish."""
        with pytest.raises(ValueError, match="chua duoc bao cao"):
            CapabilityReport(
                (Capability(CapabilityName.CONFIG_VALIDATION, available=True),)
            )

    def test_duplicate_capability_is_refused(self) -> None:
        with pytest.raises(ValueError, match="trung"):
            CapabilityReport(
                (
                    Capability(CapabilityName.CONFIG_VALIDATION, available=True),
                    Capability(CapabilityName.CONFIG_VALIDATION, available=True),
                )
            )

    def test_empty_report_is_refused(self) -> None:
        with pytest.raises(ValueError, match="chua duoc bao cao"):
            CapabilityReport(())


class TestCurrentBuild:
    def test_report_covers_every_capability(self) -> None:
        report = current_capabilities()
        assert set(report.as_dict()) == {name.value for name in CapabilityName}

    @pytest.mark.parametrize(
        "name",
        [
            CapabilityName.LIVE_VOICE_RECEIVE,
            CapabilityName.PLATFORM_ADAPTER_DISCORD,
            CapabilityName.ASR,
            CapabilityName.LLM,
            CapabilityName.TTS,
            CapabilityName.CALENDAR_CONNECTOR,
        ],
    )
    def test_unbuilt_capabilities_are_off(self, name: CapabilityName) -> None:
        entry = current_capabilities().as_dict()[name.value]
        assert entry["available"] is False

    def test_the_local_web_ui_is_off_but_not_unbuilt(self) -> None:
        """It was listed as unbuilt, and it is built.

        ``docs/plan.md`` marks S0.6 ``[x]``, ``ui.py`` has seven routes,
        ``meetai serve`` runs it, and ``test_ui.py`` passes 62 tests. The
        capability is still correctly OFF - it needs the ``ui`` extra and an
        explicit ``serve``, and it is not running during ``status`` - but
        ``NOT_BUILT`` says "No code yet. Nothing the operator can do", and
        both halves were false in output the operator reads.

        Third time this class of defect has surfaced here, after the
        ``asr``/``llm`` reasons and the RAM-preflight claim. The lesson being
        recorded is that a test naming a capability "unbuilt" pins the claim as
        much as the string does.
        """
        entry = current_capabilities().as_dict()[CapabilityName.LOCAL_WEB_UI.value]
        assert entry["available"] is False
        assert entry["blocked_by"] == BlockedBy.NOT_RUNNING.value
        reason = entry["blocked_reason"]
        assert isinstance(reason, str)
        assert "chua trien khai" not in reason, reason
        assert "serve" in reason

    def test_a_not_running_capability_is_actionable(self) -> None:
        """The enum carries what the operator can do, and here they can act:
        run ``meetai serve``. Reporting it as unactionable hid a control the
        operator already had."""
        assert BlockedBy.NOT_RUNNING.operator_can_act
        assert not BlockedBy.NOT_BUILT.operator_can_act

    def test_every_blocked_by_member_answers_operator_can_act(self) -> None:
        """Exhaustive, so a fifth member has to decide rather than inherit."""
        for member in BlockedBy:
            assert isinstance(member.operator_can_act, bool), member

    def test_every_off_capability_has_a_reason(self) -> None:
        """The property the previous spot-check only sampled."""
        for value, entry in current_capabilities().as_dict().items():
            if not entry["available"]:
                assert entry["blocked_reason"], f"{value} khong co ly do"

    def test_gate_zero_is_cited_for_discord_capabilities(self) -> None:
        report = current_capabilities().as_dict()
        for name in (
            CapabilityName.LIVE_VOICE_RECEIVE,
            CapabilityName.PLATFORM_ADAPTER_DISCORD,
        ):
            assert "0-S" in str(report[name.value]["blocked_reason"])

    def test_only_the_fake_adapter_is_synthetic(self) -> None:
        """A mock backing must be declared, and only where it is true.

        The fake adapter is genuinely synthetic and says so. Anything else
        claiming a mock backing would mean a capability was wired to a stub
        while reporting itself as working.
        """
        synthetic = {
            name
            for name, entry in current_capabilities().as_dict().items()
            if entry["synthetic"]
        }
        assert synthetic == {CapabilityName.PLATFORM_ADAPTER_FAKE.value}

    def test_the_fake_adapter_displays_as_mock_not_on(self) -> None:
        """MOCK and ON must never render the same."""
        fake = next(
            c
            for c in current_capabilities().capabilities
            if c.name is CapabilityName.PLATFORM_ADAPTER_FAKE
        )
        assert fake.display_status == "MOCK"

    def test_the_real_discord_adapter_is_still_off(self) -> None:
        """A working fake must not make the real integration look available."""
        entry = current_capabilities().as_dict()[
            CapabilityName.PLATFORM_ADAPTER_DISCORD.value
        ]
        assert entry["available"] is False
        assert "0-S" in str(entry["blocked_reason"])


class TestBlockedByDiscriminator:
    """A UI must not have to string-match Vietnamese prose to branch."""

    def test_only_a_pending_decision_is_operator_actionable(self) -> None:
        """Rendering a control next to something unfixable is dishonest too."""
        assert BlockedBy.PENDING_DECISION.operator_can_act is True
        assert BlockedBy.NOT_BUILT.operator_can_act is False
        assert BlockedBy.EVIDENCE_GATE.operator_can_act is False

    def test_every_off_capability_carries_a_discriminator(self) -> None:
        for name, entry in current_capabilities().as_dict().items():
            if not entry["available"]:
                assert entry["blocked_by"], name

    def test_discord_capabilities_are_gate_blocked_not_unbuilt(self) -> None:
        """Two different facts with two different remedies."""
        report = current_capabilities().as_dict()
        for name in (
            CapabilityName.LIVE_VOICE_RECEIVE,
            CapabilityName.PLATFORM_ADAPTER_DISCORD,
        ):
            assert report[name.value]["blocked_by"] == BlockedBy.EVIDENCE_GATE.value
            assert report[name.value]["operator_can_act"] is False

    def test_unbuilt_capabilities_say_so(self) -> None:
        report = current_capabilities().as_dict()
        for name in (CapabilityName.ASR, CapabilityName.LLM, CapabilityName.TTS):
            assert report[name.value]["blocked_by"] == BlockedBy.NOT_BUILT.value

    def test_serialiser_key_set_matches_the_model(self) -> None:
        """A field added to the model must not be forgotten in as_dict().

        Same optimistic-failure argument the report's completeness check makes:
        a silently dropped field is the direction that hides a problem.
        """
        from dataclasses import fields

        entry = next(iter(current_capabilities().as_dict().values()))
        model_fields = {f.name for f in fields(Capability)} - {"name"}
        assert model_fields <= set(entry), model_fields - set(entry)
