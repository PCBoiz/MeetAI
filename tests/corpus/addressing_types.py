"""Record types for the addressing corpus (S1.7).

Separate from ``tests/corpus/types.py`` on purpose. That file describes cases
for the authority gate, where the question is "may this be said"; this one
describes cases for the addressee classifier, where the question is "who is
being spoken to". Sharing one record would mean every case carried fields
belonging to the other problem, and a field that is meaningless for half the
corpus is a field nobody can label honestly.

Imports nothing from ``meetai``, enforced by a test that reads this source. A
corpus able to call the classifier it judges could copy that classifier's
output into its own labels, and the evaluation would be measuring the code
against itself. Labels are plain strings for the same reason: importing
``AddressClass`` would import the module under test.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass


class AddressGroup(enum.Enum):
    """The slices reported separately.

    Grouped by what kind of mistake a failure in the group would be. A wrong
    answer in ``P_DIRECT_REQUEST`` is a missed reply; a wrong answer in
    ``T_NO_ADDRESSEE`` is MeetAI speaking when nobody asked it to. Those are
    not the same event and a single pooled number would hide the difference.
    """

    P_DIRECT_REQUEST = "P_direct_request"
    """Dedicated alias plus a question or a request. The only group where a
    reply is the correct outcome."""

    Q_VOCATIVE_ONLY = "Q_vocative_only"
    """Named, but nothing asked. Addressee is identifiable; a reply is not
    permitted."""

    R_THIRD_PERSON = "R_third_person"
    """A name mentioned in the third person."""

    S_WORD_COLLISION = "S_word_collision"
    """A name that folds onto an ordinary word, used as the ordinary word."""

    T_NO_ADDRESSEE = "T_no_addressee"
    """Generic pronouns, questions to the room, sentences naming nobody."""

    U_QUOTE_NEGATION = "U_quote_negation"
    """Reported speech, jokes, self-correction, negation."""

    V_AMBIGUOUS_SPEAKER = "V_ambiguous_speaker"
    """Several possible addressees, unreliable speaker mapping, or a partial
    transcript."""


class ExpectedClass(enum.Enum):
    """The address classes, as strings so the corpus need not import the enum.

    Five members, matching the classifier. The handoff document names four;
    ``NOT_DIRECTED_TO_ME`` is the fifth, which the operator ruled is the right
    answer for a question put to the room rather than ``UNCLEAR``.
    """

    DIRECTED_TO_ME = "directed_to_me"
    THIRD_PERSON_REFERENCE = "third_person_reference"
    ALIAS_COLLISION = "alias_collision"
    NOT_DIRECTED_TO_ME = "not_directed_to_me"
    UNCLEAR = "unclear"


class ExpectedIntent(enum.Enum):
    """Whether the utterance asks for anything."""

    NONE = "none"
    QUESTION = "question"
    REQUEST = "request"


@dataclass(frozen=True, slots=True)
class AddressCase:
    """One labelled utterance.

    ``expected_reply`` is stored rather than derived, even though the
    classifier derives it from the pair of stages. Writing it out means the
    corpus states the outcome that actually matters - did MeetAI speak - and a
    disagreement between the stated outcome and the conjunction of the two
    stated stages is itself a labelling error a test can catch.

    ``policy_basis`` cites the decision the label follows. A label justified
    only by "that is what the classifier returned" cannot produce one, which
    is what makes classifier-sourced labels hard to write by accident.
    """

    case_id: str
    text: str
    group: AddressGroup
    expected_class: ExpectedClass
    expected_intent: ExpectedIntent
    expected_reply: bool
    policy_basis: str
    speaker_mapping_reliable: bool = False
    transcript_complete: bool = True
    addressed_to_me_by_turn: bool = False
    known_gap: bool = False
    notes: str = ""

    def __post_init__(self) -> None:
        if not self.policy_basis:
            raise ValueError(f"{self.case_id}: thieu policy_basis")
        if self.expected_reply:
            if self.expected_class is not ExpectedClass.DIRECTED_TO_ME:
                raise ValueError(
                    f"{self.case_id}: expected_reply=True can DIRECTED_TO_ME"
                )
            if self.expected_intent is ExpectedIntent.NONE:
                raise ValueError(
                    f"{self.case_id}: expected_reply=True can mot intent khac NONE"
                )
        if self.addressed_to_me_by_turn and not self.speaker_mapping_reliable:
            raise ValueError(
                f"{self.case_id}: addressed_to_me_by_turn can speaker mapping tin cay"
            )
