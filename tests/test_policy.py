"""Tests for the framework-free policy rules.

These run without constructing a settings object, which is the point of keeping
:mod:`meetai.policy` free of pydantic: the prohibitions are testable as pure
functions, and slice S1.5's runtime gate will reuse them unchanged.
"""

from __future__ import annotations

import itertools

import pytest

from meetai.policy import (
    ConfigurationFlags,
    ConsentMode,
    ConsentScope,
    LateJoinPolicy,
    media_processing_allowed,
    pending_decisions,
    rejected_configuration,
)


def flags(**overrides: object) -> ConfigurationFlags:
    """A fully fail-closed configuration, with named fields overridden."""
    base: dict[str, object] = {
        "consent_mode": ConsentMode.PENDING_DECISION,
        "late_join_policy": LateJoinPolicy.PENDING_DECISION,
        "persist_transcript": False,
        "persist_notes": False,
        "persist_reply_journal": False,
        "persist_raw_audio_debug": False,
        "raw_audio_debug_acknowledged": False,
        "requested_external_ai": False,
        "requested_live_discord_voice": False,
    }
    base.update(overrides)
    return ConfigurationFlags(**base)  # type: ignore[arg-type]


class TestDefaultsArePermitted:
    def test_fully_closed_configuration_is_allowed_to_start(self) -> None:
        """Fail-closed must still boot - it just must not process media."""
        assert rejected_configuration(flags()) == ()


class TestOutOfScopeRequests:
    def test_external_ai_rejected(self) -> None:
        violations = rejected_configuration(flags(requested_external_ai=True))
        assert [v.rule for v in violations] == ["external_ai"]

    def test_live_discord_voice_rejected(self) -> None:
        violations = rejected_configuration(flags(requested_live_discord_voice=True))
        assert [v.rule for v in violations] == ["live_discord_voice"]

    def test_both_reported_together(self) -> None:
        """An operator fixing one should learn about the other in the same run."""
        violations = rejected_configuration(
            flags(requested_external_ai=True, requested_live_discord_voice=True)
        )
        assert {v.rule for v in violations} == {"external_ai", "live_discord_voice"}


class TestPersistenceOrdering:
    @pytest.mark.parametrize(
        "field",
        ["persist_transcript", "persist_notes", "persist_reply_journal"],
    )
    def test_persistence_requires_a_consent_decision_first(self, field: str) -> None:
        violations = rejected_configuration(flags(**{field: True}))
        assert "persistence_before_consent_decision" in {v.rule for v in violations}

    @pytest.mark.parametrize(
        "field",
        ["persist_transcript", "persist_notes", "persist_reply_journal"],
    )
    def test_persistence_allowed_once_consent_is_decided(self, field: str) -> None:
        violations = rejected_configuration(
            flags(consent_mode=ConsentMode.PER_PARTICIPANT, **{field: True})
        )
        assert violations == ()

    def test_raw_audio_needs_its_own_acknowledgement(self) -> None:
        """Granting transcripts must not grant the most sensitive scope."""
        violations = rejected_configuration(
            flags(
                consent_mode=ConsentMode.PER_PARTICIPANT,
                persist_transcript=True,
                persist_raw_audio_debug=True,
            )
        )
        assert "raw_audio_debug_unacknowledged" in {v.rule for v in violations}

    def test_raw_audio_allowed_when_acknowledged(self) -> None:
        violations = rejected_configuration(
            flags(
                consent_mode=ConsentMode.PER_PARTICIPANT,
                persist_raw_audio_debug=True,
                raw_audio_debug_acknowledged=True,
            )
        )
        assert violations == ()

    def test_acknowledgement_alone_grants_nothing(self) -> None:
        """The acknowledgement is a precondition, not a switch."""
        assert rejected_configuration(flags(raw_audio_debug_acknowledged=True)) == ()


class TestMediaGate:
    def test_blocked_while_either_decision_is_pending(self) -> None:
        assert media_processing_allowed(flags()) is False
        assert (
            media_processing_allowed(flags(consent_mode=ConsentMode.PER_PARTICIPANT))
            is False
        )
        assert (
            media_processing_allowed(
                flags(late_join_policy=LateJoinPolicy.A1_CIRCUIT_BREAKER)
            )
            is False
        )

    def test_allowed_only_for_fully_decided_combinations(self) -> None:
        """Enumerates the whole cross product rather than sampling it."""
        decided_modes = [ConsentMode.PER_PARTICIPANT, ConsentMode.HOST_COORDINATED]
        decided_late = [
            LateJoinPolicy.A1_CIRCUIT_BREAKER,
            LateJoinPolicy.A3_ADMISSION_CONTROL,
        ]
        for mode, late in itertools.product(ConsentMode, LateJoinPolicy):
            expected = mode in decided_modes and late in decided_late
            actual = media_processing_allowed(
                flags(consent_mode=mode, late_join_policy=late)
            )
            assert actual is expected, f"{mode.value} + {late.value}"


class TestPendingDecisions:
    def test_both_pending_by_default(self) -> None:
        assert pending_decisions(flags()) == ("consent_mode", "late_join_policy")

    def test_decided_choice_drops_out(self) -> None:
        assert pending_decisions(flags(consent_mode=ConsentMode.HOST_COORDINATED)) == (
            "late_join_policy",
        )

    def test_none_pending_when_both_decided(self) -> None:
        assert (
            pending_decisions(
                flags(
                    consent_mode=ConsentMode.PER_PARTICIPANT,
                    late_join_policy=LateJoinPolicy.A3_ADMISSION_CONTROL,
                )
            )
            == ()
        )


class TestVocabulary:
    def test_pending_members_are_falsy(self) -> None:
        assert not ConsentMode.PENDING_DECISION
        assert not LateJoinPolicy.PENDING_DECISION

    def test_decided_members_are_truthy(self) -> None:
        assert ConsentMode.PER_PARTICIPANT
        assert ConsentMode.HOST_COORDINATED
        assert LateJoinPolicy.A1_CIRCUIT_BREAKER
        assert LateJoinPolicy.A3_ADMISSION_CONTROL

    def test_enums_are_not_string_equal(self) -> None:
        """A str-mixed enum compares equal to its raw value, which invites
        stringly-typed comparisons that silently stop matching."""
        # mypy flags this as a non-overlapping comparison, which is exactly
        # the property being asserted: the enum is not its raw string.
        assert ConsentMode.PER_PARTICIPANT != "per_participant"  # type: ignore[comparison-overlap]
        assert ConsentMode.PER_PARTICIPANT.value == "per_participant"

    def test_live_media_is_a_distinct_consent_scope(self) -> None:
        """Processing audio at all is its own grant, not a side effect."""
        assert ConsentScope.LIVE_MEDIA in set(ConsentScope)
        assert len(set(ConsentScope)) == 4

    def test_violations_carry_no_values(self) -> None:
        """A violation message must describe a rule, never a configuration value."""
        violations = rejected_configuration(
            flags(requested_external_ai=True, requested_live_discord_voice=True)
        )
        for v in violations:
            assert v.rule
            assert v.reason
            assert "True" not in v.reason
