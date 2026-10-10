"""The corpus record type.

Imports nothing from ``meetai``, on purpose. If the corpus could call the code
it judges, it could copy that code's output into its own labels, and the
evaluation would be measuring the classifier against itself. The ban is
enforced by a test that reads the corpus source.

Act and intent names are plain strings for the same reason: importing
``ProhibitedAct`` would mean importing the module under test.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass, field


class RiskGroup(enum.Enum):
    """The slices of behaviour measured separately.

    Grouped by *what kind of mistake* a failure would be, not by topic, because
    the whole point of reporting per group is that a false-allow in group F
    (prohibited acts) is a different event from a false-block in group A
    (ordinary permitted speech).
    """

    A_DIRECT_ADDRESS = "A_direct_address"
    B_THIRD_PERSON = "B_third_person"
    C_ALIAS_COLLISION = "C_alias_collision"
    D_NEGATION = "D_negation"
    E_PROPOSAL_VS_DECISION = "E_proposal_vs_decision"
    F_PROHIBITED_ACTS = "F_prohibited_acts"
    G_COLLOQUIAL = "G_colloquial"
    H_KNOWN_GAPS = "H_known_gaps"


class AddressLabel(enum.Enum):
    """The four-way address taxonomy the handoff document requires.

    A label on the *input* to the gate, not something derived from the text:
    the gate consumes an ``AddressContext`` and never looks at the words for
    this. The classifier that would produce it is a separate, unbuilt slice, so
    these cases test the gate's handling of a given address - not an address
    classifier.
    """

    DIRECT = "direct"
    THIRD_PERSON = "third_person"
    ALIAS_ONLY = "alias_only"
    UNCLEAR = "unclear"


class EvidenceSetup(enum.Enum):
    """What evidence the gate is given for a case."""

    NONE = "none"
    APPROVED = "approved"
    PENDING = "pending"
    EXPIRED = "expired"
    SUPERSEDED = "superseded"
    MISSING_ID = "missing_id"


@dataclass(frozen=True, slots=True)
class Case:
    """One labelled utterance.

    ``expected_acts`` holds the acts **policy** names, which is not always what
    the current code returns. A disagreement is the finding, and
    ``known_gap=True`` is how a disagreement is recorded rather than hidden -
    the harness then requires it to *keep* disagreeing, so a fix shows up as a
    failure telling the author to clear the flag.

    ``policy_basis`` cites the line of policy the label comes from. A label
    whose only justification is "that is what the regex said" cannot produce
    one, so the field makes classifier-sourced labels hard to write.
    """

    case_id: str
    text: str
    group: RiskGroup
    expected_allow: bool
    policy_basis: str
    address: AddressLabel = AddressLabel.DIRECT
    intent: str = "inform"
    confidence: float = 0.9
    evidence: EvidenceSetup = EvidenceSetup.NONE
    states_personal_position: bool = False
    expected_acts: frozenset[str] = field(default_factory=frozenset)
    known_gap: bool = False
    notes: str = ""

    def __post_init__(self) -> None:
        if self.expected_allow and self.expected_acts:
            raise ValueError(
                f"{self.case_id}: expected_allow=True khong the co expected_acts"
            )
        if not self.policy_basis:
            raise ValueError(f"{self.case_id}: thieu policy_basis")
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError(f"{self.case_id}: confidence ngoai [0, 1]")
