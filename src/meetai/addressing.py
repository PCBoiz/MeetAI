"""Who is being spoken to (S1.7), kept separate from whether to speak.

This module estimates an *addressee*. It grants nothing. The handoff document
asks for a four-way classification - directly addressed, mentioned in the third
person, a colliding alias, or unclear - and states that an alias match alone is
not enough to interject (handoff:108). That second half is the reason this is a
separate module rather than a branch inside :mod:`meetai.authority`: the gate
answers "may this be said", and merging the two questions would let a name in a
transcript widen what MeetAI is permitted to do.

Four stages stay distinct, and the separation is load-bearing:

1. **Addressee** (:class:`AddressClass`) - who the utterance is aimed at.
2. **Response intent** (:class:`ResponseIntent`) - whether anything was
   actually asked. Being named is not being asked.
3. **Authority** (:mod:`meetai.authority`) - evidence and permitted acts.
4. **Confidence** - not calibrated. ``MINIMUM_CONFIDENCE`` remains a
   placeholder and nothing here treats it as a measured threshold.

Stages 1 and 2 are separate because of a decision the operator made directly:
a bare vocative with MeetAI's own alias ("MeetAI oi") *does* identify MeetAI as
the addressee, and still must not produce a reply, because nothing was asked.
Collapsing the two would force a choice between losing the addressee
information and interjecting on a greeting. So :meth:`AddressAssessment.to_address_context`
requires **both** before it reports ``directly_addressed``.

Speaker identity is deliberately absent as a positive signal. Mapping an RTP
source to a participant is what Gate 0-C is about, and that gate is open, so
there is no trustworthy turn context to read. The flag that exists
(:attr:`Utterance.speaker_mapping_reliable`) can only ever make the answer more
cautious; it is never required to reach ``UNCLEAR``.
"""

from __future__ import annotations

import enum
import re
from dataclasses import dataclass, field

from meetai.authority import fold_diacritics
from meetai.errors import MeetAIError
from meetai.response import AddressContext


class AddressingError(MeetAIError):
    """An addressing input is malformed.

    Messages describe shape, never the utterance, because an utterance is
    meeting content.
    """


class AddressClass(enum.Enum):
    """Who the utterance is aimed at.

    ``DIRECTED_TO_ME`` is the only truthy member, so ``if assessment.address_class:``
    fails closed on every other answer. The project has been bitten by the
    opposite arrangement: a truthy "unclear" reads like a sensible guard while
    permitting exactly the state that must not permit anything.

    The handoff document names four classes. ``NOT_DIRECTED_TO_ME`` is a fifth,
    added because the operator ruled that a question put to the room ("moi
    nguoi nghi sao?") is positively *not* aimed at MeetAI rather than unclear.
    Folding it into ``UNCLEAR`` would inflate the unclear rate with cases that
    are in fact recognisable, and that rate is the number this slice reports.
    """

    DIRECTED_TO_ME = "directed_to_me"
    THIRD_PERSON_REFERENCE = "third_person_reference"
    ALIAS_COLLISION = "alias_collision"
    NOT_DIRECTED_TO_ME = "not_directed_to_me"
    UNCLEAR = "unclear"

    def __bool__(self) -> bool:
        return self is AddressClass.DIRECTED_TO_ME


class ResponseIntent(enum.Enum):
    """Whether the utterance asks for anything.

    ``NONE`` is falsy and is the default, so an utterance that asked nothing
    cannot accumulate a reason to answer. ``QUESTION`` and ``REQUEST`` are kept
    apart because they are not interchangeable downstream: a question wants
    information, a request wants an action, and MeetAI is permitted far less of
    the second.
    """

    NONE = "none"
    QUESTION = "question"
    REQUEST = "request"

    def __bool__(self) -> bool:
        return self is not ResponseIntent.NONE


class AliasKind(enum.Enum):
    """What kind of name an alias is, which decides what a match can mean.

    This distinction exists because of two operator rulings that pull in
    opposite directions. A clear alias of MeetAI's own ("MeetAI oi") may mark
    MeetAI as the addressee. A human name may **never** - if "Son" is called
    and Son is in the meeting, the classifier must not conclude it was being
    summoned, because answering would be MeetAI replying in place of a person
    who is present. The classifier cannot tell the two situations apart from
    the text, so the registry has to carry the distinction.

    ``DEDICATED`` therefore has to be registered deliberately. There is no
    default: the operator has not settled what MeetAI is called, so an empty
    registry is the honest state and it recognises nobody.
    """

    DEDICATED = "dedicated"
    """A name belonging to MeetAI alone. The only kind that can reach DIRECT."""

    HUMAN_NAME = "human_name"
    """A name a person in the meeting may also answer to. Never reaches DIRECT."""

    AMBIGUOUS_WORD = "ambiguous_word"
    """A name that folds onto an ordinary word, so a match may not be a name
    at all. "Son" folds to "son" (paint); "Minh" folds to "minh" (the
    first-person pronoun). Never reaches DIRECT, and a match with no address
    evidence is reported as a collision rather than as a mention."""


@dataclass(frozen=True, slots=True)
class Alias:
    """One name MeetAI should recognise, and what kind of name it is.

    Stored folded, because every comparison happens after folding and storing
    the accented form would invite a caller to compare against the raw text and
    silently miss unaccented ASR output.
    """

    text: str
    kind: AliasKind

    def __post_init__(self) -> None:
        if not self.text.strip():
            raise AddressingError("alias khong duoc rong")
        folded = fold_diacritics(self.text).strip()
        if not folded:
            raise AddressingError(f"alias fold thanh rong ({len(self.text)} ky tu)")
        object.__setattr__(self, "text", folded)

    @property
    def can_reach_direct(self) -> bool:
        """Only a dedicated alias can identify MeetAI as the addressee."""
        return self.kind is AliasKind.DEDICATED


@dataclass(frozen=True, slots=True)
class AliasRegistry:
    """The aliases MeetAI recognises. Empty permits nothing.

    Same shape as :class:`meetai.planner.ChannelAllowlist`, for the same
    reason: a registry that shipped a default name would be deciding how the
    operator addresses MeetAI, and real aliases are configured locally and stay
    out of the repository. Tests use invented names.
    """

    aliases: frozenset[Alias] = frozenset()

    def matches(self, folded_text: str) -> frozenset[Alias]:
        """Every alias occurring in already-folded text, on a word boundary.

        Word boundaries matter more than they look. Without them "son" matches
        inside "khong" and every sentence becomes a mention.
        """
        found = {
            alias
            for alias in self.aliases
            if re.search(rf"\b{re.escape(alias.text)}\b", folded_text)
        }
        return frozenset(found)

    @property
    def has_dedicated_alias(self) -> bool:
        return any(alias.can_reach_direct for alias in self.aliases)


# --------------------------------------------------------------------------- #
# Signals.
#
# Three families, each answering a different question, because the failure
# modes are different: a missing address signal costs a missed reply, a missing
# competing-addressee signal costs a reply aimed at somebody else. They are
# written as families rather than as one pattern per sentence so that a gap is
# a gap in a class of utterance, which is diagnosable, rather than a gap in a
# sentence, which is only ever fixed one sentence at a time.
# --------------------------------------------------------------------------- #

_VOCATIVE_PARTICLE = r"(?:oi|a|ah|nay|nhe|nhi)"
"""Particles that turn a name into a summons. Vietnamese marks the vocative
with a trailing particle rather than with word order, so "Minh oi" is a call
and "Minh se lam" is a statement about Minh - the particle is the signal.

Separators between the name and the particle are skipped - see
:data:`_VOCATIVE_SEPARATOR`."""

_DASHES = "".join(chr(code) for code in (0x2D, 0x2013, 0x2014))
"""Hyphen-minus, en dash, em dash - built from code points rather than written
literally so the source stays ASCII. Pasted dash characters are
indistinguishable on review, and this file has already had one regex corrupted
by a tool rewriting its source."""

_VOCATIVE_SEPARATOR = rf"[\s.{re.escape(_DASHES)}]*"
"""Whitespace, dots and dashes between a name and its particle.

"MeetAI-oi" was read as a non-address until this was allowed. A transcriber's
choice of punctuation should not decide whether MeetAI noticed it was called."""

_GENERIC_PRONOUN = r"\b(?:ban|anh|chi|em|cau|bac|co)\b"
"""Second-person pronouns that address somebody without naming them. On their
own these reach UNCLEAR, never DIRECT: in a meeting with several people "anh
oi" is almost always aimed at one of them."""

_GROUP_MARKER = (
    r"\b(?:moi\s*nguoi|ca\s*nhom|cac\s*ban|ca\s*team|"
    r"moi\s*ben|ai\s*(?:lam|biet|co|se|phu\s*trach)|ben\s*nao|nhom\s*minh)\b"
)
"""Markers that the room, not a person, is being addressed. ``ai`` is only
counted when followed by a verb, because bare "ai" also appears inside
ordinary words once folded."""

_QUESTION_WORD = (
    r"\b(?:gi|nao|sao|the\s*nao|bao\s*nhieu|bao\s*lau|khi\s*nao|"
    r"o\s*dau|dau|may\s*gio|co\s*phai|phai\s*khong|dung\s*khong)\b"
)

_REQUEST_VERB = (
    r"(?:giup|tom\s*tat|nhac|tra\s*loi|kiem\s*tra|tim|liet\s*ke|"
    r"cho\s*(?:\w+\s*)?biet|noi\s*lai|giai\s*thich|xem\s*lai|bao\s*cao)"
)

_REQUEST_POLITENESS = r"\b(?:hay|lam\s*on|vui\s*long)\b"
"""Markers that make a following verb an imperative regardless of position.
``nho`` is deliberately absent: it folds together with "nho" (small) and
"nho" (remember), so it would fire on ordinary description."""

_REQUEST_BENEFACTIVE = r"\b(?:giup|gium|ho)\b"
"""A benefactive marks a request even mid-clause: "gui lai link giup minh" is
asking, while "minh gui lai link" is reporting. Vietnamese has no imperative
inflection, so position and these markers are the only mood signals there are."""

_ADDRESS_VERB_BEFORE = r"\b(?:chao|xin\s*chao|hi|hello|kinh\s*gui)\s*$"
"""A greeting verb before a name addresses that name. Without this, "chao
MeetAI" has a name and no vocative particle, and the classifier would report
unclear - a false non-address whose cause is a missing signal family rather
than a missing sentence."""

_THIRD_PERSON_FRAME = r"(?:theo|cua|cho|gap|hoi|noi\s*voi|nho|giao\s*cho|ben|tu|den)\s*$"
"""A preposition immediately before a name makes it a reference, not a
summons: "theo Minh", "noi voi Minh", "giao cho Minh".

Bare ``voi`` and ``cung`` are deliberately absent, although they look like
they belong. They are conjunctions as often as prepositions, so "moi nguoi voi
MeetAI cung ra lai" - the room and MeetAI jointly - was being reported as a
third-person reference to MeetAI. That is a whole class of collective address
misread as a mention, and the group marker already labels it correctly. The
compound ``noi voi`` stays, because there the preposition reading is the only
one."""

_THIRD_PERSON_PREDICATE = (
    r"^\s*(?:se|da|dang|vua|khong|chua|noi|bao|lam|nhan|phu\s*trach|"
    r"gui|chiu|dong\s*y|tu\s*choi|bao\s*rang|cho\s*rang)\b"
)
"""A name followed directly by a predicate is a statement about that person:
"Minh se lam", "Minh da gui". This is what separates a third-person mention
from a vocative without relying on punctuation, which ASR output lacks.

``cung`` was here and had to come out. It folds together from "cũng" (also,
which does mark a predicate) and "cùng" (together, which marks joint action),
so "MeetAI cung ra lai" - MeetAI included in a shared task - was read as a
statement about MeetAI. The aspect markers ``se``, ``da``, ``dang`` and
``vua`` carry the predicate reading without that ambiguity."""

_QUOTE_FRAME = (
    r"\b(?:noi\s*la|noi\s*rang|bao\s*la|bao\s*rang|kieu\s*nhu|"
    r"vi\s*du|gia\s*su|neu\s*ai|dua\s*thoi|noi\s*dum|trich)\b"
)
"""Reported or hypothetical speech. "Luc do ban ay noi 'MeetAI oi'" contains a
summons that already happened to somebody else; treating it as a live one is a
false activation with a clear cause."""

_SELF_CORRECTION = (
    r"\b(?:y\s*la|y\s*minh\s*la|khong\s*phai|xin\s*loi|noi\s*lai|"
    r"a\s*khong|nham|sorry)\b"
)
"""A speaker retracting what they just said. The retraction may well follow
the name, so the whole utterance is treated as unsettled rather than being
split on it."""

_ADDRESS_RULES = "addressing.v1"


@dataclass(frozen=True, slots=True)
class Utterance:
    """One transcript segment, with what is known about how it was captured.

    ``text`` is meeting content, so it is excluded from ``repr`` and the
    generated ``repr`` is replaced below. Every flag defaults to the cautious
    value: an utterance constructed with no provenance at all is treated as
    having unreliable speaker mapping and no turn context, which is the true
    state today with Gate 0-C open.
    """

    text: str = field(repr=False)
    speaker_mapping_reliable: bool = False
    """Whether the speaker could be identified. Gate 0-C is open, so the
    honest default is False. A True here never *creates* a direct address; it
    only removes a reason for caution."""

    transcript_complete: bool = True
    """False when ASR reported a partial or overlapping segment."""

    addressed_to_me_by_turn: bool = False
    """Set only when a trustworthy turn context says MeetAI spoke last and
    this is a reply to it. Requires ``speaker_mapping_reliable``; asserting it
    without that is refused rather than ignored, because an input that is
    quietly dropped looks like a working feature."""

    def __post_init__(self) -> None:
        if self.addressed_to_me_by_turn and not self.speaker_mapping_reliable:
            raise AddressingError("addressed_to_me_by_turn can speaker_mapping_reliable")

    def __repr__(self) -> str:
        return (
            f"Utterance(chars={len(self.text)}, "
            f"speaker_mapping_reliable={self.speaker_mapping_reliable}, "
            f"transcript_complete={self.transcript_complete})"
        )


@dataclass(frozen=True, slots=True)
class AddressAssessment:
    """What the classifier concluded, and why.

    ``reasons`` carries stable rule codes rather than prose. A UI or a log that
    string-matched a Vietnamese sentence would break the first time somebody
    rewords it, and the same codes are what make an over-broad signal
    diagnosable on the corpus.
    """

    address_class: AddressClass
    response_intent: ResponseIntent = ResponseIntent.NONE
    alias_mentioned: bool = False
    reasons: tuple[str, ...] = ()
    rules_version: str = _ADDRESS_RULES

    @property
    def permits_reply(self) -> bool:
        """Both stages must agree before anything may be said.

        This is the operator's ruling about a bare vocative, expressed as a
        conjunction: being identified as the addressee and being asked
        something are different findings, and only the pair permits a reply.
        """
        return bool(self.address_class) and bool(self.response_intent)

    def to_address_context(self) -> AddressContext:
        """Hand the authority gate the input it already expects.

        ``directly_addressed`` is set from :attr:`permits_reply`, not from the
        address class. The gate's own ``permits_speaking`` is exactly this
        field, so writing the address class into it would make a greeting
        sufficient to interject.
        """
        return AddressContext(
            directly_addressed=self.permits_reply,
            alias_mentioned=self.alias_mentioned,
            third_person_reference=(
                self.address_class is AddressClass.THIRD_PERSON_REFERENCE
            ),
        )


_CLAUSE_SPLIT = re.compile(r"[,.;:!?]+|\bva\b|\bnhung\b|\broi\b")


def _clauses(folded: str) -> list[str]:
    """Split on clause boundaries.

    Mood scopes over a clause: in "giu binh tinh, minh xem lai sau" the second
    clause reports and the first instructs. Checking the whole sentence would
    let one clause's imperative make the other one a request.
    """
    return [clause.strip() for clause in _CLAUSE_SPLIT.split(folded) if clause.strip()]


def detect_response_intent(
    text: str, *, registry: AliasRegistry | None = None
) -> ResponseIntent:
    """Whether the utterance asks for information or for an action.

    A question mark counts but is not required: ASR output frequently carries
    no punctuation, so a signal that depended on it would vanish on exactly
    the input this system receives.

    A request needs **imperative mood**, not merely a request verb, and that
    is the whole difficulty. Vietnamese does not inflect for mood, so "Tuan
    dang kiem tra lai so lieu" (reporting) and "Kiem tra lai so lieu" (asking)
    differ only in position and in markers. Treating the verb alone as a
    request made every third-person progress report look like an instruction -
    an error class, not a handful of sentences. So a request is recognised
    only clause-initially, after a politeness marker, or with a benefactive.

    A dedicated alias is stripped from the front of a clause first, because it
    occupies the subject slot in "MeetAI kiem tra lai giup minh" while the
    clause is still an imperative addressed to MeetAI. Only dedicated aliases
    are stripped: doing it for a person's name would turn a report about them
    into an instruction.
    """
    folded = fold_diacritics(text)
    dedicated = (
        [a.text for a in registry.aliases if a.can_reach_direct] if registry else []
    )
    for clause in _clauses(folded):
        stem = clause
        for alias in dedicated:
            stem = re.sub(
                rf"^{re.escape(alias)}\s*{_VOCATIVE_PARTICLE}?\s*", "", stem
            ).strip()
        if (
            re.match(rf"\s*{_REQUEST_VERB}\b", stem)
            or re.search(_REQUEST_BENEFACTIVE, stem)
            or re.search(rf"{_REQUEST_POLITENESS}\s*{_REQUEST_VERB}\b", stem)
        ):
            return ResponseIntent.REQUEST
    if "?" in text or re.search(_QUESTION_WORD, folded):
        return ResponseIntent.QUESTION
    return ResponseIntent.NONE


def _alias_clauses(folded: str, alias: Alias) -> list[str]:
    """The clauses in which this alias actually appears."""
    pattern = re.compile(rf"\b{re.escape(alias.text)}\b")
    return [clause for clause in _clauses(folded) if pattern.search(clause)]


def _alias_framing(folded: str, alias: Alias) -> tuple[bool, bool]:
    """Return ``(vocative, third_person)`` for one alias in folded text.

    Both can be false - a name can appear with no framing at all - and that
    absence is itself informative, so the caller is not given a single verdict
    to misread.
    """
    vocative = False
    third_person = False
    for match in re.finditer(rf"\b{re.escape(alias.text)}\b", folded):
        before = folded[: match.start()]
        after = folded[match.end() :]

        # Three independent ways a name reads as a summons. Kept as separate
        # named conditions rather than one boolean expression: each is a
        # distinct signal family, and the corpus diagnoses them separately.
        particle = bool(re.match(rf"{_VOCATIVE_SEPARATOR}{_VOCATIVE_PARTICLE}\b", after))
        greeted = bool(re.search(_ADDRESS_VERB_BEFORE, before))
        set_off_by_punctuation = bool(re.match(r"\s*[,:]", after)) and not re.search(
            _THIRD_PERSON_PREDICATE, after.lstrip(" ,:")
        )
        if particle or greeted or set_off_by_punctuation:
            vocative = True

        if re.search(_THIRD_PERSON_FRAME, before) or re.match(
            _THIRD_PERSON_PREDICATE, after
        ):
            third_person = True
    return vocative, third_person


def classify_address(
    utterance: Utterance,
    *,
    registry: AliasRegistry,
) -> AddressAssessment:
    """Estimate who is being addressed. Never grants permission to speak.

    The order of the checks is the policy, so it is written as one readable
    sequence rather than spread across helpers:

    1. An incomplete transcript is unclear, whatever it appears to say.
    2. A self-correction is unclear, because the retraction may follow the name.
    3. Reported speech is not a live address.
    4. A dedicated alias with vocative framing is a direct address - the only
       path to ``DIRECTED_TO_ME`` that an alias provides. Failing a vocative,
       a request **in the alias's own clause** also counts, and the clause
       scoping is the whole point: with the request taken from anywhere in the
       utterance, "MeetAI thi de sau, gio moi nguoi tom tat giup minh" reached
       a reply - a sentence that explicitly defers MeetAI and asks the room.
       Three such false activations were measured before this was scoped.
    5. A human or ambiguous name is never direct: framed as a reference it is a
       third-person mention, framed as a call it is unclear, because a person
       in the room may be the one being called.
    6. A question to the room is not aimed at MeetAI.
    7. A generic pronoun with no name is unclear.
    8. Anything else is unclear.

    ``UNCLEAR`` is the default rather than a branch, so a sentence this
    function does not understand cannot reach a reply.
    """
    folded = fold_diacritics(utterance.text)
    intent = detect_response_intent(utterance.text, registry=registry)
    matched = registry.matches(folded)
    alias_mentioned = bool(matched)
    reasons: list[str] = []

    def done(cls: AddressClass, *codes: str) -> AddressAssessment:
        return AddressAssessment(
            address_class=cls,
            response_intent=intent,
            alias_mentioned=alias_mentioned,
            reasons=tuple(reasons) + codes,
        )

    if not utterance.transcript_complete:
        return done(AddressClass.UNCLEAR, "transcript_incomplete")
    if re.search(_SELF_CORRECTION, folded):
        return done(AddressClass.UNCLEAR, "self_correction")
    if re.search(_QUOTE_FRAME, folded):
        return done(AddressClass.UNCLEAR, "reported_speech")

    dedicated = sorted((a for a in matched if a.can_reach_direct), key=lambda a: a.text)
    human = sorted((a for a in matched if not a.can_reach_direct), key=lambda a: a.text)

    for alias in dedicated:
        vocative, third_person = _alias_framing(folded, alias)
        if vocative:
            return done(AddressClass.DIRECTED_TO_ME, "dedicated_alias_vocative")
        if third_person:
            return done(
                AddressClass.THIRD_PERSON_REFERENCE, "dedicated_alias_third_person"
            )
        if any(
            detect_response_intent(clause, registry=registry)
            for clause in _alias_clauses(folded, alias)
        ):
            return done(AddressClass.DIRECTED_TO_ME, "dedicated_alias_with_request")
        reasons.append("dedicated_alias_unframed")

    if utterance.addressed_to_me_by_turn and not human:
        return done(AddressClass.DIRECTED_TO_ME, "turn_context")

    for alias in human:
        vocative, third_person = _alias_framing(folded, alias)
        if third_person:
            return done(AddressClass.THIRD_PERSON_REFERENCE, "human_alias_third_person")
        if vocative:
            return done(AddressClass.UNCLEAR, "human_alias_vocative_ambiguous")
        if alias.kind is AliasKind.AMBIGUOUS_WORD:
            return done(AddressClass.ALIAS_COLLISION, "ambiguous_word_no_framing")
        return done(AddressClass.THIRD_PERSON_REFERENCE, "human_alias_unframed")

    if re.search(_GROUP_MARKER, folded):
        return done(AddressClass.NOT_DIRECTED_TO_ME, "group_marker")
    if dedicated:
        return done(AddressClass.UNCLEAR, "dedicated_alias_no_evidence")
    if re.search(_GENERIC_PRONOUN, folded):
        return done(AddressClass.UNCLEAR, "generic_pronoun_only")
    return done(AddressClass.UNCLEAR, "no_address_evidence")


__all__ = [
    "AddressAssessment",
    "AddressClass",
    "AddressingError",
    "Alias",
    "AliasKind",
    "AliasRegistry",
    "ResponseIntent",
    "Utterance",
    "classify_address",
    "detect_response_intent",
]
