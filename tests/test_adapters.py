"""Tests for the platform adapter interfaces and the synthetic adapter.

The property that matters most: a fake adapter must be unable to present itself
as a real integration. A passing test against a fake would otherwise look like
evidence that Discord works, which is the exact confusion the evidence gates
exist to prevent.
"""

from __future__ import annotations

import pytest

from meetai.adapters.base import (
    AdapterCapabilities,
    AdapterHealth,
    AdapterMisrepresentationError,
    AudioFrame,
    InboundAudio,
    ParticipantEventKind,
    PlatformAdapter,
)
from meetai.adapters.fake import FAKE_PLATFORM, BlockedDiscordAdapter, FakeAdapter
from meetai.content import MeetingContent


class _Adapter(PlatformAdapter):
    """Minimal concrete adapter for testing the base class's checks."""


class TestMisrepresentationChecks:
    def test_synthetic_adapter_cannot_take_a_real_platform_name(self) -> None:
        """The check the handoff document asks for by name."""
        with pytest.raises(AdapterMisrepresentationError, match="ten platform that"):
            _Adapter(AdapterCapabilities(platform="discord", version="1", synthetic=True))

    @pytest.mark.parametrize(
        "name", ["Discord", "DISCORD", " discord ", "Google Meet", "zoom", "Teams"]
    )
    def test_real_platform_names_are_matched_case_and_space_insensitively(
        self, name: str
    ) -> None:
        with pytest.raises(AdapterMisrepresentationError):
            _Adapter(AdapterCapabilities(platform=name, version="1", synthetic=True))

    def test_real_adapter_claiming_inbound_audio_needs_evidence(self) -> None:
        """Gate 0-S: the claim cannot be made without something backing it."""
        with pytest.raises(AdapterMisrepresentationError, match="0-S"):
            _Adapter(
                AdapterCapabilities(
                    platform="discord",
                    version="1",
                    supports_inbound_audio=True,
                    synthetic=False,
                )
            )

    def test_a_combined_claim_without_evidence_is_refused_for_inbound(self) -> None:
        """Renamed and retargeted: it was passing on the wrong branch.

        It was called ``..._claiming_speaker_mapping_needs_evidence`` and
        matched on ``"evidence"``, which the **inbound** message also contains.
        There was a separate speaker-mapping branch below it, and it was
        unreachable - so this test never exercised the rule its name claimed.
        The branch is gone (the first check subsumes it) and the match is now
        specific to the message that actually fires.
        """
        with pytest.raises(AdapterMisrepresentationError, match="inbound audio"):
            _Adapter(
                AdapterCapabilities(
                    platform="discord",
                    version="1",
                    supports_inbound_audio=True,
                    supports_speaker_mapping=True,
                    evidence=None,
                )
            )

    def test_speaker_mapping_without_inbound_audio_is_refused_first(self) -> None:
        """The rule the deleted branch spelled out, where it actually lives."""
        with pytest.raises(AdapterMisrepresentationError, match="speaker mapping"):
            _Adapter(
                AdapterCapabilities(
                    platform="discord",
                    version="1",
                    supports_inbound_audio=False,
                    supports_speaker_mapping=True,
                    evidence=None,
                )
            )

    def test_speaker_mapping_without_inbound_audio_is_incoherent(self) -> None:
        with pytest.raises(AdapterMisrepresentationError, match="khong co y nghia"):
            _Adapter(
                AdapterCapabilities(
                    platform="x",
                    version="1",
                    supports_inbound_audio=False,
                    supports_speaker_mapping=True,
                    evidence="some evidence",
                )
            )

    def test_real_adapter_with_evidence_is_accepted(self) -> None:
        adapter = _Adapter(
            AdapterCapabilities(
                platform="discord",
                version="1",
                supports_inbound_audio=True,
                supports_speaker_mapping=True,
                evidence="https://example.invalid/ticket/123 checked 2026-10-07",
            )
        )
        assert adapter.capabilities.evidence
        assert adapter.is_synthetic is False

    def test_outbound_only_adapter_needs_no_evidence(self) -> None:
        """Sending text is documented and supported; it needs no gate."""
        adapter = _Adapter(
            AdapterCapabilities(
                platform="discord",
                version="1",
                supports_control=True,
                supports_outbound_text=True,
            )
        )
        assert adapter.capabilities.supports_inbound_audio is False


class TestCapabilitySeparation:
    def test_the_three_planes_are_separate_protocols(self) -> None:
        """One fat interface would force every adapter to claim inbound audio."""
        from meetai.adapters.base import ControlPlane, OutboundText

        assert not issubclass(ControlPlane, InboundAudio)
        assert not issubclass(OutboundText, InboundAudio)
        assert not issubclass(InboundAudio, ControlPlane)

    def test_blocked_discord_adapter_does_not_implement_inbound_audio(self) -> None:
        """The honest shape of the gap, expressed as a type."""
        assert not isinstance(BlockedDiscordAdapter(), InboundAudio)

    def test_fake_adapter_implements_all_three(self) -> None:
        from meetai.adapters.base import ControlPlane, OutboundText

        adapter = FakeAdapter()
        assert isinstance(adapter, ControlPlane)
        assert isinstance(adapter, OutboundText)
        assert isinstance(adapter, InboundAudio)


class TestBlockedDiscordAdapter:
    def test_capabilities_claim_nothing(self) -> None:
        caps = BlockedDiscordAdapter().capabilities
        assert caps.supports_inbound_audio is False
        assert caps.supports_speaker_mapping is False
        assert caps.supports_control is False
        assert caps.synthetic is False

    def test_health_explains_the_gate(self) -> None:
        health = BlockedDiscordAdapter().health()
        assert health.connected is False
        assert "0-S" in health.detail

    @pytest.mark.parametrize("method", ["join", "leave", "participant_events"])
    def test_every_operation_raises(self, method: str) -> None:
        """No partially-working integration to accidentally rely on."""
        adapter = BlockedDiscordAdapter()
        with pytest.raises(NotImplementedError, match="0-S"):
            if method == "join":
                adapter.join("some-channel")
            elif method == "leave":
                adapter.leave()
            else:
                list(adapter.participant_events())

    def test_send_text_raises(self) -> None:
        with pytest.raises(NotImplementedError, match="0-S"):
            BlockedDiscordAdapter().send_text(MeetingContent("hello"))


class TestFakeAdapterIsMarkedSynthetic:
    def test_platform_is_not_a_real_one(self) -> None:
        assert FakeAdapter().capabilities.platform == FAKE_PLATFORM

    def test_declares_itself_synthetic(self) -> None:
        assert FakeAdapter().is_synthetic is True
        assert FakeAdapter().capabilities.synthetic is True

    def test_evidence_states_it_proves_nothing(self) -> None:
        evidence = FakeAdapter().capabilities.evidence or ""
        assert "khong phai bang chung" in evidence

    def test_every_frame_carries_the_synthetic_mark(self) -> None:
        """The marking must survive into the pipeline, not stop at the boundary."""
        adapter = FakeAdapter()
        adapter.script_frame("p-1")
        adapter.script_frame(None)
        frames = list(adapter.audio_frames())
        assert len(frames) == 2
        assert all(frame.synthetic for frame in frames)

    def test_capability_dict_is_metadata_only(self) -> None:
        data = FakeAdapter().capabilities.as_dict()
        assert data["synthetic"] is True
        assert data["platform"] == FAKE_PLATFORM


class TestFakeAdapterBehaviour:
    def test_join_and_leave(self) -> None:
        # Read into a local at each step: narrowing a property across a
        # mutating call is exactly where a type checker and reality diverge.
        adapter = FakeAdapter()
        before = adapter.joined_channel
        assert before is None

        adapter.join("chan-1")
        joined = adapter.joined_channel
        assert joined == "chan-1"

        adapter.leave()
        after_leave = adapter.joined_channel
        assert after_leave is None

    def test_leave_is_safe_when_not_joined(self) -> None:
        """The interface says so, so the fake must honour it.

        A mock that is more permissive than the contract makes tests pass that
        the real implementation would fail.
        """
        adapter = FakeAdapter()
        adapter.leave()
        adapter.leave()
        assert adapter.leave_count == 2

    def test_health_reflects_join_state(self) -> None:
        adapter = FakeAdapter()
        assert adapter.health().connected is False
        adapter.join("chan-1")
        assert adapter.health().connected is True

    def test_participant_events_are_drained_once(self) -> None:
        adapter = FakeAdapter()
        adapter.script_participant_event(ParticipantEventKind.JOINED, "p-1")
        assert len(list(adapter.participant_events())) == 1
        assert list(adapter.participant_events()) == []

    def test_frames_are_drained_once(self) -> None:
        adapter = FakeAdapter()
        adapter.script_frame("p-1")
        assert len(list(adapter.audio_frames())) == 1
        assert list(adapter.audio_frames()) == []

    def test_unmapped_speaker_is_representable(self) -> None:
        """The gate needs to be able to receive the ambiguity, not a guess."""
        adapter = FakeAdapter()
        adapter.script_frame(None)
        assert next(iter(adapter.audio_frames())).participant is None

    def test_sent_text_stays_wrapped(self) -> None:
        adapter = FakeAdapter()
        adapter.send_text(MeetingContent("noi dung"))
        assert isinstance(adapter.sent_messages[0], MeetingContent)


class TestAudioFrameDoesNotLeak:
    def test_repr_reports_shape_only(self) -> None:
        """An auto-generated repr would put audio in the first log line."""
        pcm = b"SENTINEL-AUDIO-BYTES-MUST-NOT-APPEAR"
        frame = AudioFrame(participant="p-1", pcm=pcm, sample_rate=16_000, at=0.0)
        assert b"SENTINEL" not in repr(frame).encode()
        assert f"bytes={len(pcm)}" in repr(frame)

    def test_byte_count_is_exposed(self) -> None:
        frame = AudioFrame(participant="p", pcm=b"abcd", sample_rate=16_000, at=0.0)
        assert frame.byte_count == 4

    def test_participant_event_has_no_display_name(self) -> None:
        """A display name is unstable and personal, and this flows into logs."""
        from dataclasses import fields

        from meetai.adapters.base import ParticipantEvent

        names = {f.name for f in fields(ParticipantEvent)}
        assert names == {"kind", "participant", "at"}


class TestAdapterHealth:
    def test_disconnected_health_must_explain_itself(self) -> None:
        with pytest.raises(ValueError, match="phai co detail"):
            AdapterHealth(connected=False, detail="")

    def test_connected_health_needs_no_detail_rule(self) -> None:
        assert AdapterHealth(connected=True, detail="").connected is True


class TestABlockedAdapterCannotBeMadeToMisreport:
    """Its declaration is not injectable.

    Measured before the fix: ``BlockedDiscordAdapter(AdapterCapabilities(
    platform="discord", supports_inbound_audio=True, synthetic=False,
    evidence="trust me"))`` constructed, and ``capabilities.as_dict()``
    reported a real Discord integration with inbound audio.

    A **reporting** hole, not an audio one - and the distinction is the point,
    so both halves are asserted here.
    """

    def test_capabilities_cannot_be_supplied_by_a_caller(self) -> None:
        forged = AdapterCapabilities(
            platform="discord",
            version="2",
            supports_control=True,
            supports_outbound_text=True,
            supports_inbound_audio=True,
            supports_speaker_mapping=True,
            synthetic=False,
            evidence="trust me",
        )
        with pytest.raises(TypeError):
            BlockedDiscordAdapter(forged)  # type: ignore[call-arg]

    def test_the_declaration_is_what_it_always_was(self) -> None:
        declared = BlockedDiscordAdapter().capabilities
        assert declared.supports_inbound_audio is False
        assert declared.supports_speaker_mapping is False
        assert declared.supports_control is False
        assert declared.supports_outbound_text is False
        assert declared.platform == "discord"
        assert declared.evidence is None

    def test_it_could_never_have_delivered_audio_either_way(self) -> None:
        """The honest scope of the fix: what was at stake was the claim, not
        the capability. There is no code path on this object that produces an
        AudioFrame."""
        blocked = BlockedDiscordAdapter()
        assert not isinstance(blocked, InboundAudio)
        assert not hasattr(blocked, "audio_frames")
