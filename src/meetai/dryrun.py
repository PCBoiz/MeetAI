"""A local, offline dry-run of the response boundary (testing level 2).

**What this is.** A hand-runnable path from a synthetic question to a sink:
synthetic case -> in-memory :class:`~meetai.knowledge.KnowledgeStore` ->
:class:`~meetai.boundary.ResponseRequest` -> answerability -> authority gate ->
:class:`~meetai.boundary.RecordingSink`. It exists so the boundary stops being
a control that only tests call. ``docs/research/`` calls this **level 2**, and
the distinction from level 3 is load-bearing: this reaches a list in memory.

**What this is NOT, stated because it is the easy thing to overstate.** Not a
Discord test, not a meeting, not a production integration, not evidence that
anything is ready. No audio, no transcript, no listener, no network, no
persistence, no inference, no model. Every card here is synthetic text written
for this file; there is no real meeting content and no real person's name. The
only sink is :class:`~meetai.boundary.RecordingSink`, which reaches nothing,
and gate 0-U is open so a sink that reached a meeting would be refused by
``Settings.require_media_processing_allowed()`` anyway.

**Why it builds the store rather than hand-building cards.** A card can be
constructed approved in one expression, but then nothing exercised the
approval step, and ``approved_content_hash`` - the record that detects a card
edited after review - would be a field this path never set. So the fixture
ingests ``CANDIDATE`` cards and calls :meth:`KnowledgeStore.approve`, which is
the same code a future review UI would call. The case that cites an
*unapproved* card then demonstrates something real: ``store.retrieve`` never
returns it, so the claim has nothing to rest on.

**Why nothing prints the question or the answer.** The content here is
synthetic, so printing it would leak nothing - but the boundary's discipline is
that an outcome describes shape, never values, and a tool that prints content
"because this content is safe" is a tool whose next caller prints content that
is not. The report prints the case id, the hand-written ``shape`` line, and the
outcome's metadata. ``findings`` is included deliberately: every finding is a
stable rule name with at most an index, never text, which is what makes a
refusal diagnosable without quoting what was refused.

**The distinction the report exists to make visible.** ``UNSUPPORTED`` means
checked and contradicted; ``UNCLEAR`` means not checkable. Collapsing them
would hide whether the layer is working or merely silent, so the report prints
the three-state verdict next to the detailed level.

Framework-free, like the modules it drives. No pydantic, no argparse here, no
I/O except the string the CLI prints.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from meetai.answerability import Claim, ClaimKind, Verdict
from meetai.boundary import (
    DeliveryOutcome,
    OutputSink,
    RecordingSink,
    ResponseRequest,
    Stage,
    deliver,
)
from meetai.content import MeetingContent
from meetai.knowledge import (
    CardType,
    KnowledgeStore,
    Sensitivity,
    SourceAllowlist,
)
from meetai.knowledge import KnowledgeCard as Card
from meetai.response import (
    AddressContext,
    ProposedResponse,
    ResponseDecision,
    SpeechAct,
)
from meetai.retrieval import RetrievalResult, retrieve_for_question, witnesses_for

SYNTHETIC_SOURCE = "note://synthetic"
"""The only source the fixture store accepts.

An explicit allowlist prefix, so the fixture cannot accidentally ingest from
anywhere a future caller might point it: ``SourceAllowlist`` is empty by
default and permits nothing, and this adds exactly one synthetic scheme.
"""

GLOSS: dict[str, str] = {
    "supported": "da kiem, card dung do claim",
    "unsupported": "da kiem, gia tri khong co trong card nay",
    "conflicting": "hai card da duyet khong dong y voi nhau",
    "no_citable_evidence": "khong card nao citable: chua duyet, het han, "
    "hoac bi supersede",
    "partial_undeclared": "tra loi mot phan ma khong khai phan con thieu",
    "gap_asserts": "claim khai la thieu can cu nhung van neu mot gia tri",
    "unverifiable_claim": "khong kiem duoc: khong co gia tri nhan dien duoc "
    "va khong phai trich nguyen van",
    "evidence_self_contradictory": "card tu mau thuan ve chinh lop dang hoi",
    "malformed": "cau truc claim khong mo ta cau tra loi",
}
"""Plain-language gloss for each :class:`SupportLevel`, keyed by its value.

A **constant table**, which is why it is safe: it cannot leak content by
construction, because it holds no content. It exists because nine enum names
printed at an operator is not the same thing as an operator understanding the
difference, and comprehension is the entire purpose of a dry-run. A level
missing from this table is a bug, and a test asserts the table covers every
member - so adding a tenth level forces someone to write its sentence.
"""

VERDICT_GLOSS: dict[str, str] = {
    "supported": "answerability: card du do -> chuyen sang gate quyen han",
    "unsupported": "answerability: da kiem va bi phan doi -> im",
    "unclear": "answerability: KHONG kiem duoc -> im",
}
"""Gloss for the three-state verdict, and **each one names its layer**.

The distinction this keeps visible: ``unsupported`` means checked and
contradicted, ``unclear`` means not checkable. Collapsing them into one word
like "abstained" would destroy the only signal that says whether the layer is
working or merely silent.

Naming the layer is the second fix, and it came from reading this tool's own
output: ``supported`` first glossed as "noi duoc" (may speak), which printed
next to two cases the **authority gate refused**. The verdict answers one
question - did the evidence hold up - and reading it as the final answer is
precisely the conflation two independent layers exist to prevent.
"""

AUTHORITY_NOTE = (
    "gate quyen han TU CHOI du answerability da dong y: "
    "hai lop doc lap, va khong lop nao thay duoc lop kia"
)
"""Printed when the authority stage is the one that refused.

The single most informative line the dry-run produces: the operator sees
``verdict=supported`` and ``IM`` on the same case, which is the whole argument
for checking authority separately from evidence.
"""

MEETING_AUDIENCE = Sensitivity.GROUP
"""Who the answer would be spoken to, if a sink existed.

Required by :func:`~meetai.retrieval.retrieve_for_question` and set here
rather than defaulted there, because sensitivity is enforced in exactly one
place - ``KnowledgeStore.retrieve`` - and re-checked nowhere: ``Sensitivity``
appears zero times in ``answerability.py``, ``authority.py`` and
``boundary.py``. A permissive default would admit ``PRIVATE`` cards with
nothing downstream to catch it.

``GROUP`` and not ``PRIVATE``: the dry-run stands in for speaking into a
meeting, and a private note must not be relayed into one by a caller that
forgot to filter.
"""

NOW = 1000.0
"""The fixture's clock. Fixed so a dry-run is reproducible and so a
validity window is a property of the case rather than of the hour it ran."""


@dataclass(frozen=True, slots=True)
class CardFixture:
    """One synthetic card to put in the fixture store.

    ``approve`` is separate from the claim text because the unapproved case is
    one of the shapes the operator needs to see: the store filters it, and the
    claim citing it then has nothing to rest on.
    """

    card_id: str
    scope: str
    claim: str = field(repr=False)
    approve: bool = True
    sensitivity: Sensitivity = Sensitivity.GROUP
    """Who this card may be relayed to.

    Declared per card rather than inherited from
    :class:`~meetai.knowledge.KnowledgeCard`'s default, which is ``PRIVATE``.
    Found by running it: with the default, a ``GROUP`` audience retrieved
    **nothing** and every case reported ``cited_id_not_in_store``. The filter
    was right and the fixture was wrong - and it is the one filter no layer
    below ``KnowledgeStore.retrieve`` re-checks, so a fixture that silently
    depended on a permissive audience would have been testing nothing.
    """


@dataclass(frozen=True, slots=True)
class ClaimFixture:
    """One claim in a case's answer, and the single card it rests on."""

    text: str = field(repr=False)
    evidence_id: str | None = None
    kind: ClaimKind = ClaimKind.GROUNDED


@dataclass(frozen=True, slots=True)
class DryRunCase:
    """One hand-written turn, and what it is meant to demonstrate.

    ``shape`` is unaccented Vietnamese because it is printed to a terminal,
    where a Windows console's code page is usually not UTF-8. The question,
    answer and claim text are accented because nothing prints them.

    ``expected_stage`` and ``expected_verdict`` are written from the policy,
    not copied from a run. A test asserts the observed outcome matches, so a
    change in the layer's behaviour shows up as a failure here naming the case
    - which is the point of writing them down rather than printing whatever
    happens.
    """

    case_id: str
    shape: str
    scope: str
    question: str = field(repr=False)
    expected_stage: Stage = Stage.DELIVERED
    expected_verdict: Verdict | None = None
    answer: str | None = field(default=None, repr=False)
    claims: tuple[ClaimFixture, ...] = ()
    cited_ids: tuple[str, ...] = ()
    decision: ResponseDecision = ResponseDecision.SPEAK
    intent: SpeechAct | None = SpeechAct.CITE_APPROVED_POSITION
    confidence: float = 0.8
    directly_addressed: bool = True
    max_candidates: int | None = None
    """Truncates the **candidate** list only, never the witnesses.

    Set on a case so the report can show that a truncated candidate list is a
    fact about what the model was shown, not a choice the model made - and so
    that a case can demonstrate truncation without it ever being able to hide
    a contradiction.
    """


CARDS: tuple[CardFixture, ...] = (
    CardFixture(
        card_id="card-ngansach",
        scope="duan-alpha",
        claim="Ngân sách tổng dự án Alpha đã duyệt là 240 triệu đồng.",
    ),
    CardFixture(
        card_id="card-hatang",
        scope="duan-beta",
        claim="Chi phí hạ tầng dự án Beta đã duyệt là 60 triệu đồng.",
    ),
    CardFixture(
        card_id="card-deadline-sau",
        scope="duan-gamma",
        claim="Deadline báo cáo tháng dự án Gamma đã duyệt là thứ sáu.",
    ),
    CardFixture(
        card_id="card-deadline-ba",
        scope="duan-gamma",
        claim="Deadline báo cáo tháng dự án Gamma đã duyệt là thứ ba.",
    ),
    CardFixture(
        card_id="card-kiemthu",
        scope="duan-delta",
        claim="Bên kiểm thử dự án Delta do trưởng nhóm chất lượng phụ trách.",
    ),
    CardFixture(
        card_id="card-deadline-epsilon",
        scope="duan-epsilon",
        claim="Deadline báo cáo tháng dự án Epsilon đã duyệt là thứ sáu.",
    ),
    CardFixture(
        card_id="card-dongy",
        scope="duan-eta",
        claim="Son đồng ý phương án B.",
    ),
    CardFixture(
        card_id="card-rieng",
        scope="duan-theta",
        claim="Quan điểm riêng của Son về phương án C là chưa nên làm.",
        sensitivity=Sensitivity.PRIVATE,
    ),
    CardFixture(
        card_id="card-chuaduyet",
        scope="duan-zeta",
        claim="Ngân sách tổng dự án Zeta đề xuất là 90 triệu đồng.",
        approve=False,
    ),
)
"""Synthetic cards. Separate scopes so retrieval returns a case's own cards.

Scope is how the fixture keeps the cases independent without filtering by id
afterwards. Filtering afterwards would make the store decorative: the whole
value of going through :meth:`KnowledgeStore.retrieve` is that the *store*
decides what a selection resolves to.
"""


CASES: tuple[DryRunCase, ...] = (
    DryRunCase(
        case_id="D1.du-evidence",
        shape="du evidence: card da duyet mang dung gia tri duoc hoi",
        scope="duan-alpha",
        question="Ngân sách tổng dự án Alpha là bao nhiêu?",
        answer=("Theo ghi chú đã duyệt, ngân sách tổng dự án Alpha là 240 triệu đồng."),
        claims=(
            ClaimFixture(
                text="ngân sách tổng dự án Alpha là 240 triệu đồng",
                evidence_id="card-ngansach",
            ),
        ),
        cited_ids=("card-ngansach",),
        expected_stage=Stage.DELIVERED,
        expected_verdict=Verdict.SUPPORTED,
    ),
    DryRunCase(
        case_id="D2.thieu-evidence",
        shape="thieu evidence: cau hoi doi mot gia tri khong co trong card",
        scope="duan-alpha",
        question="Chi phí hạ tầng dự án Alpha là bao nhiêu?",
        answer=("Theo ghi chú đã duyệt, chi phí hạ tầng dự án Alpha là 60 triệu đồng."),
        claims=(
            ClaimFixture(
                text="chi phí hạ tầng dự án Alpha là 60 triệu đồng",
                evidence_id="card-ngansach",
            ),
        ),
        cited_ids=("card-ngansach",),
        expected_stage=Stage.ANSWERABILITY,
        expected_verdict=Verdict.UNSUPPORTED,
    ),
    DryRunCase(
        case_id="D3.evidence-sai-chu-de",
        shape="evidence sai chu de: card that, da duyet, nhung tra loi cau khac",
        scope="duan-beta",
        question="Ngân sách tổng dự án Beta là bao nhiêu?",
        answer=("Theo ghi chú đã duyệt, ngân sách tổng dự án Beta là 60 triệu đồng."),
        claims=(
            ClaimFixture(
                text="ngân sách tổng dự án Beta là 60 triệu đồng",
                evidence_id="card-hatang",
            ),
        ),
        cited_ids=("card-hatang",),
        expected_stage=Stage.ANSWERABILITY,
        expected_verdict=Verdict.UNSUPPORTED,
    ),
    DryRunCase(
        case_id="D4.evidence-mau-thuan",
        shape="evidence mau thuan: hai card da duyet noi hai deadline khac nhau",
        scope="duan-gamma",
        question="Deadline báo cáo tháng dự án Gamma là khi nào?",
        answer=("Theo ghi chú đã duyệt, deadline báo cáo tháng dự án Gamma là thứ sáu."),
        claims=(
            ClaimFixture(
                text="deadline báo cáo tháng dự án Gamma là thứ sáu",
                evidence_id="card-deadline-sau",
            ),
        ),
        cited_ids=("card-deadline-sau",),
        expected_stage=Stage.ANSWERABILITY,
        # UNSUPPORTED, not UNCLEAR, and this corrected a wrong expectation of
        # mine. Two *approved* cards disagreeing about the asked-about class is
        # a definite finding: the store was checked and it holds a
        # contradiction. Within one card it is UNCLEAR instead, because a card
        # contradicting itself says nothing about which half to trust. Note
        # also that only one of the two was cited - retrieval returns both, and
        # the check is over what the store holds, not over what the model
        # chose to mention.
        expected_verdict=Verdict.UNSUPPORTED,
    ),
    DryRunCase(
        case_id="D5.unclear",
        shape="unclear: paraphrase khong co gia tri kiem duoc, khong phai quotation",
        scope="duan-delta",
        question="Ai phụ trách phần kiểm thử dự án Delta?",
        answer=(
            "Theo ghi chú đã duyệt, phần kiểm thử dự án Delta "
            "thuộc trưởng nhóm chất lượng."
        ),
        claims=(
            ClaimFixture(
                text="phần kiểm thử dự án Delta thuộc trưởng nhóm chất lượng",
                evidence_id="card-kiemthu",
            ),
        ),
        cited_ids=("card-kiemthu",),
        expected_stage=Stage.ANSWERABILITY,
        expected_verdict=Verdict.UNCLEAR,
    ),
    DryRunCase(
        case_id="D6.citation-chua-duyet",
        shape="citation chua duyet: store khong tra card, claim khong tua vao gi",
        scope="duan-zeta",
        question="Ngân sách tổng dự án Zeta là bao nhiêu?",
        answer=("Theo ghi chú đã duyệt, ngân sách tổng dự án Zeta là 90 triệu đồng."),
        claims=(
            ClaimFixture(
                text="ngân sách tổng dự án Zeta là 90 triệu đồng",
                evidence_id="card-chuaduyet",
            ),
        ),
        cited_ids=("card-chuaduyet",),
        expected_stage=Stage.ANSWERABILITY,
        expected_verdict=Verdict.UNSUPPORTED,
    ),
    DryRunCase(
        case_id="D7.hard-deny",
        shape="hard deny: claim co can cu, nhung cau noi la mot cam ket",
        scope="duan-epsilon",
        question="Deadline báo cáo tháng dự án Epsilon là khi nào?",
        answer=(
            "Theo ghi chú đã duyệt, deadline báo cáo tháng dự án Epsilon "
            "là thứ sáu, và tôi hứa sẽ lo phần này."
        ),
        claims=(
            ClaimFixture(
                text="deadline báo cáo tháng dự án Epsilon là thứ sáu",
                evidence_id="card-deadline-epsilon",
            ),
        ),
        cited_ids=("card-deadline-epsilon",),
        intent=SpeechAct.INFORM,
        expected_stage=Stage.AUTHORITY,
        expected_verdict=Verdict.SUPPORTED,
    ),
    DryRunCase(
        case_id="D8.silent",
        shape="silent: khong noi gi, va kieu du lieu khong cho mang text",
        scope="duan-alpha",
        question="Ngân sách tổng dự án Alpha là bao nhiêu?",
        decision=ResponseDecision.SILENT,
        intent=None,
        confidence=0.0,
        expected_stage=Stage.NOT_SPEAKING,
        expected_verdict=None,
    ),
    DryRunCase(
        case_id="D9.cam-ket-mang-gia-tri-chua-khai",
        shape="cam ket mang gia tri khong claim nao khai: malformed truoc gate",
        scope="duan-epsilon",
        question="Deadline báo cáo tháng dự án Epsilon là khi nào?",
        answer=(
            "Theo ghi chú đã duyệt, deadline báo cáo tháng dự án Epsilon "
            "là thứ sáu, và tôi xác nhận sẽ xong trước thứ sáu."
        ),
        claims=(
            ClaimFixture(
                text="deadline báo cáo tháng dự án Epsilon là thứ sáu",
                evidence_id="card-deadline-epsilon",
            ),
        ),
        cited_ids=("card-deadline-epsilon",),
        intent=SpeechAct.INFORM,
        expected_stage=Stage.ANSWERABILITY,
        expected_verdict=Verdict.UNCLEAR,
    ),
    DryRunCase(
        case_id="D10.citation-khong-noi-long-duoc",
        shape="citation da xac minh KHONG noi long duoc mot pattern neo chu the",
        scope="duan-eta",
        question="Son có đồng ý phương án B không?",
        answer="Theo ghi chú đã duyệt, Son đồng ý phương án B.",
        claims=(
            ClaimFixture(
                text="Son đồng ý phương án B",
                evidence_id="card-dongy",
            ),
        ),
        cited_ids=("card-dongy",),
        expected_stage=Stage.AUTHORITY,
        expected_verdict=Verdict.SUPPORTED,
    ),
    DryRunCase(
        case_id="D11.card-rieng-khong-ra-hop",
        shape="card PRIVATE khong duoc dua ra hop du duoc dan dung ID",
        scope="duan-theta",
        question="Quan điểm của Son về phương án C là gì?",
        answer=(
            "Theo ghi chú đã duyệt, quan điểm riêng của Son về phương án C "
            "là chưa nên làm."
        ),
        claims=(
            ClaimFixture(
                text="quan điểm riêng của Son về phương án C là chưa nên làm",
                evidence_id="card-rieng",
            ),
        ),
        cited_ids=("card-rieng",),
        expected_stage=Stage.ANSWERABILITY,
        expected_verdict=Verdict.UNSUPPORTED,
    ),
    DryRunCase(
        case_id="D12.cat-candidate-khong-che-duoc-mau-thuan",
        shape="cat candidate xuong 1 van KHONG che duoc mau thuan giua hai card",
        scope="duan-gamma",
        question="Deadline báo cáo tháng dự án Gamma là khi nào?",
        answer=("Theo ghi chú đã duyệt, deadline báo cáo tháng dự án Gamma là thứ sáu."),
        claims=(
            ClaimFixture(
                text="deadline báo cáo tháng dự án Gamma là thứ sáu",
                evidence_id="card-deadline-sau",
            ),
        ),
        cited_ids=("card-deadline-sau",),
        max_candidates=1,
        expected_stage=Stage.ANSWERABILITY,
        # The headline property of the retrieval design, as a case. With
        # `max_candidates=1` the model is shown one card, and the verifier is
        # still shown both - so the disagreement is still found. Measured
        # before the module was written: passing the ranked single card as
        # `cards` instead delivers this same answer as SUPPORTED with empty
        # findings. The report shows `candidate=1  (bi cat)` beside
        # `witness=2`, which is exactly the distinction being made.
        expected_verdict=Verdict.UNSUPPORTED,
    ),
)
"""The shapes an operator needs to see, one case each.

``D7`` is the reason the order of the stages matters and the reason its claim
is genuinely supported: a commitment with unsupported evidence would be
refused by answerability and the authority stage would never run, so the case
would demonstrate nothing about the gate.
"""


def build_store(*, now: float = NOW) -> KnowledgeStore:
    """The fixture store: synthetic cards, approved through the real path.

    ``ingest`` then ``approve``, not an approved card handed over whole.
    ``ingest`` refuses anything already approved - approval is an act the
    operator performs - and ``approve`` is what records
    ``approved_content_hash``. A fixture that skipped both would be a fixture
    whose cards were citable for a reason no production path produces.
    """
    store = KnowledgeStore(
        now=lambda: now,
        source_allowlist=SourceAllowlist(frozenset({SYNTHETIC_SOURCE})),
    )
    for fixture in CARDS:
        store.ingest(
            Card(
                card_id=fixture.card_id,
                card_type=CardType.PROJECT,
                claim=MeetingContent(fixture.claim),
                rationale=MeetingContent("ghi chú tổng hợp cho dry-run"),
                source_ref=SYNTHETIC_SOURCE,
                source_date=0.0,
                scope=fixture.scope,
                sensitivity=fixture.sensitivity,
            )
        )
        if fixture.approve:
            store.approve(fixture.card_id, approved_by="Son")
    return store


def retrieve_for(
    case: DryRunCase, store: KnowledgeStore, *, now: float = NOW
) -> RetrievalResult:
    """Run the case's question through retrieval.

    The scope comes from the **case**, standing in for a session, and never
    from the question. There is no safe lexical path from a question to a
    scope: measured, a question naming no project is answered from whichever
    project's card shares the most words, and the answer is delivered as
    ``SUPPORTED``. Which body of knowledge may answer is a decision, and the
    operator makes it.
    """
    # `now` is accepted here and not forwarded: retrieval reads the store's
    # own clock, and a second clock parameter that looked authoritative is the
    # dead-parameter trap that signature just lost. A real branch rather than
    # an assert, because an assert disappears under `python -O` and because
    # this project's lint forbids one in `src/`.
    if now != NOW:
        raise ValueError(
            "dong ho cua fixture va dong ho cua store phai trung nhau: "
            "retrieval doc dong ho cua store"
        )
    return retrieve_for_question(
        MeetingContent(case.question),
        store,
        scope=case.scope,
        max_sensitivity=MEETING_AUDIENCE,
        max_candidates=case.max_candidates,
    )


def to_request(
    case: DryRunCase, store: KnowledgeStore, *, now: float = NOW
) -> ResponseRequest:
    """Turn a case plus the store into the boundary's input.

    This function is the link the repository did not have: something that
    takes a store's view and a model's proposal and produces a
    :class:`ResponseRequest`. Retrieval runs the **question** through
    :mod:`meetai.retrieval`, so the store's filters - approval, the
    approved-content digest, validity, supersession, sensitivity - apply here
    exactly as they would anywhere else. The case's ``cited_ids`` stay the
    *model's* claim about what it used; nothing reconciles the two here,
    because deciding what a citation resolves to is the boundary's job.

    **``cards`` is the witness set, never the ranked candidates**, and the
    difference is a measurement rather than a preference. Hand ``assess`` both
    of two disagreeing approved cards and it refuses with
    ``cards_disagree``; hand it the ranked better one and it answers
    ``SUPPORTED`` with empty findings and the text is emitted. Ranking affects
    what a model may cite from. It must not affect what the verifier may see,
    which is why the tuple comes from :func:`~meetai.retrieval.witnesses_for`
    and not from whichever field looks most relevant.
    """
    proposal = ProposedResponse(
        decision=case.decision,
        text=None if case.answer is None else MeetingContent(case.answer),
        intent=case.intent,
        evidence_ids=case.cited_ids,
        confidence=case.confidence,
    )
    return ResponseRequest(
        question=MeetingContent(case.question),
        proposal=proposal,
        address=AddressContext(directly_addressed=case.directly_addressed),
        claims=tuple(
            Claim(
                text=MeetingContent(claim.text),
                kind=claim.kind,
                evidence_id=claim.evidence_id,
            )
            for claim in case.claims
        ),
        cards=witnesses_for(retrieve_for(case, store, now=now)),
        now=now,
    )


@dataclass(frozen=True, slots=True)
class DryRunResult:
    """One case and what the boundary decided. Carries no content.

    No text field, for the same reason :class:`DeliveryOutcome` has none: a
    report object that could hand back the refused sentence would be a second
    way out of the boundary.
    """

    case_id: str
    shape: str
    outcome: DeliveryOutcome
    retrieval: dict[str, object] = field(default_factory=dict)
    """The retrieval shape: scope, counts, candidate ids and scores.

    Ids and scores rather than a bare rank, because the project's rule is that
    a finding stays re-checkable against a specific card - and a rank alone is
    not something an operator can go and look at. No card text.
    """
    matches_expectation: bool = True
    """Whether the outcome matched the case's written expectation.

    A plain field rather than a derived property: the comparison needs the
    case, and a result object that still held the case could be asked for its
    answer text. This keeps the result content-free.
    """

    def metadata(self) -> dict[str, object]:
        return {
            "case_id": self.case_id,
            "shape": self.shape,
            "matches_expectation": self.matches_expectation,
            "retrieval": dict(self.retrieval),
            **self.outcome.metadata(),
            "answerability_verdict": (
                None
                if self.outcome.answerability_verdict is None
                else self.outcome.answerability_verdict.value
            ),
        }


def run(
    *,
    sink: OutputSink | None = None,
    cases: tuple[DryRunCase, ...] = CASES,
    now: float = NOW,
) -> tuple[tuple[DryRunResult, ...], OutputSink]:
    """Run the cases through the boundary. Returns the results and the sink.

    The sink defaults to a fresh :class:`RecordingSink`; a caller may pass one
    to inspect it afterwards. Nothing here calls ``emit`` - every case goes
    through :func:`~meetai.boundary.deliver`, which an AST test asserts is the
    only place in ``src/`` that does.
    """
    target: OutputSink = RecordingSink() if sink is None else sink
    store = build_store(now=now)
    results: list[DryRunResult] = []
    for case in cases:
        found = retrieve_for(case, store, now=now)
        outcome = deliver(to_request(case, store, now=now), sink=target)
        matches = outcome.stage is case.expected_stage and (
            outcome.answerability_verdict is case.expected_verdict
        )
        results.append(
            DryRunResult(
                case_id=case.case_id,
                shape=case.shape,
                outcome=outcome,
                retrieval=found.metadata(),
                matches_expectation=matches,
            )
        )
    return tuple(results), target


def emitted_count(sink: OutputSink) -> int:
    """How many times this sink was reached. A **count**, never an element.

    One typed accessor rather than ``getattr`` at each call site, so the
    narrowing happens once and a caller cannot reach past the length into the
    text. :class:`~meetai.boundary.OutputSink` deliberately declares only
    ``emit`` - a real sink has nothing to read back - so this returns 0 for any
    sink that keeps no record, which is the honest answer rather than an error.
    """
    recorded = getattr(sink, "emitted", ())
    return len(recorded) if isinstance(recorded, list | tuple) else 0


def report(results: tuple[DryRunResult, ...], *, emitted: int) -> dict[str, object]:
    """The dry-run's findings, as metadata. Safe to print or serialise."""
    return {
        "level": "2-local-recording-sink",
        "is_production_integration": False,
        "is_discord_test": False,
        "case_count": len(results),
        "delivered": sum(1 for result in results if result.outcome.delivered),
        "emitted_to_sink": emitted,
        "unexpected": [
            result.case_id for result in results if not result.matches_expectation
        ],
        "cases": [result.metadata() for result in results],
    }


def render(findings: dict[str, object]) -> str:
    """Human-readable report. Unaccented Vietnamese, ASCII only.

    A Windows console's code page is usually not UTF-8, and a report that
    renders as mojibake is worse than a plain one. No question, answer or card
    text appears: the ``shape`` line is the author's description of the case,
    and ``findings`` are rule names.
    """
    cases = findings["cases"]
    if not isinstance(cases, list):
        raise TypeError("report shape khong dung")

    lines = [
        "MeetAI dry-run cap 2 - boundary noi bo, sink trong bo nho",
        "",
        "KHONG phai thu nghiem Discord, KHONG phai tich hop production.",
        "Khong audio, khong transcript, khong persistence, khong model.",
        "Toan bo card la du lieu tong hop viet rieng cho duong nay.",
        "",
    ]
    for entry in cases:
        if not isinstance(entry, dict):
            raise TypeError("case shape khong dung")
        mark = "NOI " if entry["delivered"] else "IM  "
        flag = "" if entry["matches_expectation"] else "  <- KHAC DU KIEN"
        lines.append(f"  [{mark}] {entry['case_id']}{flag}")
        lines.append(f"         {entry['shape']}")
        lines.append(
            f"         stage={entry['stage']}"
            f"  verdict={entry['answerability_verdict']}"
            f"  level={entry['support_level']}"
        )
        verdict = entry["answerability_verdict"]
        if isinstance(verdict, str) and verdict in VERDICT_GLOSS:
            lines.append(f"         -> {VERDICT_GLOSS[verdict]}")
        level = entry["support_level"]
        if isinstance(level, str) and level in GLOSS:
            lines.append(f"         -> {GLOSS[level]}")
        if entry["stage"] == Stage.AUTHORITY.value:
            lines.append(f"         -> {AUTHORITY_NOTE}")
        found = entry.get("retrieval")
        if isinstance(found, dict) and found:
            names = found.get("candidates")
            shown = (
                ", ".join(
                    f"{item['card_id']}({item['score']})"
                    for item in names
                    if isinstance(item, dict)
                )
                if isinstance(names, list) and names
                else "khong co"
            )
            lines.append(
                f"         retrieval scope={found['scope']}"
                f"  witness={found['witness_count']}"
                f"  candidate={found['candidate_count']}"
                f"{'  (bi cat)' if found.get('truncated') else ''}"
            )
            lines.append(f"         candidates: {shown}")
        rules = entry["rules"]
        if isinstance(rules, list) and rules:
            lines.append(f"         rules={', '.join(str(rule) for rule in rules)}")
        lines.append("")

    unexpected = findings["unexpected"]
    lines += [
        f"Tong: {findings['case_count']} case, "
        f"{findings['delivered']} duoc noi, "
        f"{findings['emitted_to_sink']} lan toi sink.",
    ]
    if isinstance(unexpected, list) and unexpected:
        lines.append(f"KHAC DU KIEN: {', '.join(str(x) for x in unexpected)}")
    else:
        lines.append("Moi case khop du kien da ghi trong dryrun.CASES.")
    return "\n".join(lines)


def main() -> tuple[str, bool]:
    """Run the dry-run and render it. Returns the text and whether all matched.

    Returns rather than prints, so the CLI owns output and this stays testable
    without capturing streams.
    """
    results, sink = run()
    findings = report(results, emitted=emitted_count(sink))
    unexpected = findings["unexpected"]
    ok = not (isinstance(unexpected, list) and unexpected)
    return render(findings), ok


__all__ = [
    "AUTHORITY_NOTE",
    "CARDS",
    "CASES",
    "GLOSS",
    "MEETING_AUDIENCE",
    "NOW",
    "SYNTHETIC_SOURCE",
    "VERDICT_GLOSS",
    "CardFixture",
    "ClaimFixture",
    "DryRunCase",
    "DryRunResult",
    "build_store",
    "emitted_count",
    "main",
    "render",
    "report",
    "retrieve_for",
    "run",
    "to_request",
]
