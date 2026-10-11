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

    #: Names the matcher does **not** catch today. This is a ledger of a known
    #: gap, in the sense ``AGENTS.md`` means: "một lỗ đã biết nằm trong suite
    #: tốt hơn một lỗ phát hiện trong pilot". It is **not** a list of names
    #: that are safe to use.
    KNOWN_UNMATCHED_NEAR_MISSES = ("discord-real", "Discord Bot", "zoom.us", "my-teams")

    def test_the_matcher_is_exact_and_these_near_misses_get_through(self) -> None:
        """A measured limit, recorded rather than hidden or quietly widened.

        **[CHỐT THEO ỦY QUYỀN CỦA SƠN QUA CODEX] 2026-10-11: do not extend.**
        The matcher stays an exact comparison after ``strip().lower()`` against
        the existing reserved names. Prefix, suffix, substring or fuzzy
        matching is **not** added, because no measurement shows it is needed
        and a wider rule would start rejecting legitimate synthetic names -
        trading a hole nobody has hit for false refusals nobody asked for.

        So these names construct successfully today. That is the hole, stated
        plainly. **It is not evidence that such an adapter is safe**, and
        nothing here should be read as approving the names: a synthetic
        adapter calling itself "discord-real" is still misleading to a human,
        and the only reason this is tolerable is the separate fact asserted in
        :meth:`test_a_near_miss_name_still_cannot_hide_that_it_is_synthetic`.

        If anyone widens the matcher, this test fails, and the right response
        is to move the name out of the ledger - not to delete the test.
        """
        for name in self.KNOWN_UNMATCHED_NEAR_MISSES:
            adapter = _Adapter(
                AdapterCapabilities(platform=name, version="1", synthetic=True)
            )
            assert adapter.capabilities.platform == name, (
                f"{name!r} is now refused. The matcher was widened; update "
                "KNOWN_UNMATCHED_NEAR_MISSES and say so in the documents."
            )

    def test_a_near_miss_name_still_cannot_hide_that_it_is_synthetic(self) -> None:
        """What makes the gap above tolerable, asserted rather than assumed.

        The name is not the control. ``synthetic=True`` is, and it survives
        whatever the platform is called - so a consumer deciding whether a
        result counts as real integration evidence has a field to read that a
        misleading name cannot touch. If that ever stopped being true, the
        recorded gap would stop being tolerable and would need closing.
        """
        for name in self.KNOWN_UNMATCHED_NEAR_MISSES:
            capabilities = _Adapter(
                AdapterCapabilities(platform=name, version="1", synthetic=True)
            ).capabilities
            assert capabilities.synthetic is True
            assert capabilities.as_dict()["synthetic"] is True
            assert capabilities.supports_inbound_audio is False

    def test_the_reserved_names_are_still_refused(self) -> None:
        """The other direction, so "do not extend" cannot become "do nothing".

        Without this beside the ledger, deleting the check entirely would make
        every near-miss test pass and the suite would report no problem.
        """
        for name in ("discord", "google meet", "zoom", "teams", "slack"):
            with pytest.raises(AdapterMisrepresentationError, match="ten platform that"):
                _Adapter(AdapterCapabilities(platform=name, version="1", synthetic=True))

    #: Values that look like a citation and are not one. Measured on the real
    #: constructor before this slice: every one of these was accepted while
    #: the adapter claimed inbound audio. ``""`` was already refused, by the
    #: plain truthiness check that used to be the whole rule.
    NON_EVIDENCE = ("", "   ", "\t\n ", "TODO", " TODO ", "N/A", "n/a", "ToDo")

    #: Deliberately **not** rejected. Widening past the two placeholders the
    #: decision names would be guessing at what an operator meant, and a
    #: citation system that second-guesses its input starts refusing real
    #: ones. Kept as a test so the boundary is visible rather than implied.
    NOT_PLACEHOLDERS = ("na", "none-yet", "TODO-1234", "ticket n/a-7")

    @pytest.mark.parametrize("evidence", NON_EVIDENCE)
    def test_a_placeholder_is_not_evidence_for_inbound_audio(self, evidence: str) -> None:
        """**[CHỐT THEO ỦY QUYỀN CỦA SƠN QUA CODEX] 2026-10-11.**

        ``evidence`` is documented as a short citation - a URL, a ticket, a
        test manifest. Empty or blank is not one, and neither are the exact
        placeholders ``TODO`` and ``n/a`` once trimmed and case-folded. The
        gate exists so a capability is claimed *together with* what
        substantiates it; a claim substantiated by the word "TODO" is the
        claim without the substantiation.
        """
        with pytest.raises(AdapterMisrepresentationError, match="0-S"):
            _Adapter(
                AdapterCapabilities(
                    platform="discord",
                    version="1",
                    synthetic=False,
                    supports_inbound_audio=True,
                    evidence=evidence,
                )
            )

    @pytest.mark.parametrize("evidence", NON_EVIDENCE)
    def test_a_placeholder_is_not_evidence_for_speaker_mapping_either(
        self, evidence: str
    ) -> None:
        """Speaker mapping rides the same check, so it is asked the same way.

        The module notes that mapping-without-audio is already refused, so the
        audio branch subsumes the mapping one. That makes this a test of the
        combination an adapter would really declare, not of a second rule.
        """
        with pytest.raises(AdapterMisrepresentationError, match="0-S"):
            _Adapter(
                AdapterCapabilities(
                    platform="discord",
                    version="1",
                    synthetic=False,
                    supports_inbound_audio=True,
                    supports_speaker_mapping=True,
                    evidence=evidence,
                )
            )

    def test_a_real_citation_is_still_accepted(self) -> None:
        """The contract is unchanged for anything that is actually a citation.

        Without this, refusing everything would satisfy the cases above and
        the suite would call it stricter.
        """
        for citation in (
            "https://discord.com/developers/docs/topics/voice-connections",
            "ticket MEET-412",
            "tests/manifest/0-S-trace.json",
        ):
            adapter = _Adapter(
                AdapterCapabilities(
                    platform="discord",
                    version="1",
                    synthetic=False,
                    supports_inbound_audio=True,
                    evidence=citation,
                )
            )
            assert adapter.capabilities.evidence == citation

    @pytest.mark.parametrize("evidence", NOT_PLACEHOLDERS)
    def test_the_placeholder_list_is_not_widened_by_guesswork(
        self, evidence: str
    ) -> None:
        """The boundary of the decision, pinned in the other direction.

        ``na``, ``TODO-1234`` and ``ticket n/a-7`` are **not** on the list.
        Substring or fuzzy matching would catch them and would also start
        refusing real citations that merely contain those letters - trading a
        hole nobody has hit for false refusals nobody asked for. If the list
        is ever widened, that is a decision with evidence behind it, and this
        test is where it gets recorded.
        """
        adapter = _Adapter(
            AdapterCapabilities(
                platform="discord",
                version="1",
                synthetic=False,
                supports_inbound_audio=True,
                evidence=evidence,
            )
        )
        assert adapter.capabilities.evidence == evidence

    @pytest.mark.parametrize("evidence", NON_EVIDENCE)
    def test_adapters_that_claim_nothing_are_unaffected(self, evidence: str) -> None:
        """The check is about a *claim*, so no claim means nothing to check.

        A control-plane-only adapter may carry whatever it likes in that
        field; it is not substantiating anything with it.
        """
        adapter = _Adapter(
            AdapterCapabilities(
                platform="meetai-fixture",
                version="1",
                synthetic=False,
                supports_control=True,
                supports_inbound_audio=False,
                supports_speaker_mapping=False,
                evidence=evidence,
            )
        )
        assert adapter.capabilities.supports_inbound_audio is False

    @pytest.mark.parametrize("evidence", NON_EVIDENCE)
    def test_the_refusal_never_echoes_the_rejected_value(self, evidence: str) -> None:
        """A rejected value must not travel in the message.

        ``evidence`` is operator-supplied text that ends up in reports, and
        this project has already closed one leak of that shape in the
        benchmark CLIs. The message describes the shape of the problem, so an
        implementation that helpfully quoted what it rejected - the obvious
        ``f"... {evidence!r}"`` - fails here.

        Asked of every rejected value rather than of a planted canary: the
        values that *are* rejected are exactly the short placeholders, so a
        canary cannot be smuggled inside one without making it something else
        that is legitimately accepted.
        """
        with pytest.raises(AdapterMisrepresentationError) as caught:
            _Adapter(
                AdapterCapabilities(
                    platform="discord",
                    version="1",
                    synthetic=False,
                    supports_inbound_audio=True,
                    evidence=evidence,
                )
            )
        rendered = str(caught.value)
        trimmed = evidence.strip()
        if trimmed:
            assert trimmed not in rendered, (
                f"the refusal quoted the value it rejected: {rendered!r}"
            )

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

    @pytest.mark.parametrize("method", ["join", "participant_events"])
    def test_every_operation_that_reaches_discord_raises(self, method: str) -> None:
        """No partially-working integration to accidentally rely on.

        ``leave`` is deliberately **not** in this list any more - see
        :meth:`test_leave_is_safe_when_never_joined`. Everything that would
        have to *reach* Discord still refuses.
        """
        adapter = BlockedDiscordAdapter()
        with pytest.raises(NotImplementedError, match="0-S"):
            if method == "join":
                adapter.join("some-channel")
            else:
                list(adapter.participant_events())

    def test_leave_is_safe_when_never_joined(self) -> None:
        """``ControlPlane.leave`` says "must be safe to call when not joined".

        Raising broke that contract, and the contract is the useful one: a
        caller unwinding after a failure should not have to know whether the
        join succeeded. A cleanup verb on an adapter that has never joined has
        nothing to undo, so "you are not in a channel" is already true.

        **This opens no Discord capability.** Nothing here connects, and
        :meth:`test_leave_changes_nothing_a_caller_could_act_on` asserts the
        rest of the surface is untouched by calling it.
        """
        BlockedDiscordAdapter().leave()

    def test_leave_is_idempotent(self) -> None:
        """Repeatedly, because once-only would still fail an unwind path."""
        adapter = BlockedDiscordAdapter()
        for _ in range(3):
            adapter.leave()

    def test_leave_changes_nothing_a_caller_could_act_on(self) -> None:
        """The negative half: a no-op must also be a no-change.

        Without this, implementing ``leave`` as something that set a flag, or
        flipped a capability, would satisfy the two tests above. The adapter
        has to look exactly the same afterwards.
        """
        adapter = BlockedDiscordAdapter()
        before = adapter.capabilities.as_dict()
        before_health = adapter.health()

        adapter.leave()

        assert adapter.capabilities.as_dict() == before
        after_health = adapter.health()
        assert (after_health.connected, after_health.detail) == (
            before_health.connected,
            before_health.detail,
        )
        assert adapter.capabilities.supports_control is False
        assert adapter.capabilities.supports_inbound_audio is False
        # The operations that would reach Discord still refuse afterwards.
        with pytest.raises(NotImplementedError, match="0-S"):
            adapter.join("some-channel")
        with pytest.raises(NotImplementedError, match="0-S"):
            adapter.send_text(MeetingContent("hello"))

    def test_the_docstring_no_longer_claims_every_operation_raises(self) -> None:
        """The sentence was accurate until this slice; now it would mislead.

        Checked rather than trusted, because a docstring that contradicts the
        code is how the next reader concludes ``leave`` is still blocked and
        writes a workaround for it.
        """
        doc = BlockedDiscordAdapter.__doc__ or ""
        assert "Every operation raises" not in doc
        assert "leave" in doc, "the docstring should say what leave does instead"

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
