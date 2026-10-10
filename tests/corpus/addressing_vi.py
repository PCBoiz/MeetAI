"""Labelled Vietnamese corpus for the addressee classifier (S1.7), version 1.

Synthetic. Every utterance was written for this corpus; none is a transcript,
and every personal name is invented. Real aliases are configured locally and
stay out of the repository, so the operator's own name appears nowhere here -
including in the collision group, which uses invented names that fold onto
ordinary words instead.

**Labels come from the decisions recorded below, never from the classifier.**
Each case cites the decision it follows in ``policy_basis``. Where the code
disagrees with a label, ``known_gap=True`` records the disagreement and the
harness requires it to *persist*, so closing a gap fails the suite with a
message telling the author to clear the flag rather than quietly improving a
number.

Decisions this corpus is labelled against, all answered directly by the
operator this slice:

- ``op:Q1`` - a bare vocative with MeetAI's own alias identifies MeetAI as the
  addressee and still must not produce a reply. Addressee detection and reply
  triggering are separate stages.
- ``op:Q2`` - a generic second-person pronoun with no alias and no trustworthy
  turn context is ``UNCLEAR``, not a direct address.
- ``op:Q3`` - a question put to the room is positively **not** aimed at
  MeetAI. Being present in the meeting does not make it an addressee.
- ``op:Q4`` - when a person's name is called and that person may be present,
  the classifier must never conclude MeetAI was summoned. ``UNCLEAR``.
- ``agents:fail-closed`` - uncertain speaker mapping, diarization or transcript
  means ``UNCLEAR``.
- ``handoff:108`` - an alias match alone is not enough to interject.
- ``plan:S1.7`` - the four-way taxonomy, and the rule that an alias match alone
  can never produce ``directly_addressed``.

Names used, all invented, chosen for how they behave once folded:

- ``MeetAI`` is the only dedicated alias, and it is a **fixture value, not a
  product decision**: the operator has not settled what MeetAI is called, and
  the registry ships empty precisely so this file cannot settle it.
- ``Hoa`` folds to "hoa" (flower), ``Thu`` to "thu" (autumn, and "thu thập",
  to collect), ``Bình`` to "binh" (a vase, and "bình tĩnh", calm), ``Lan`` to
  "lan" (and "lần", a time), ``Tuấn`` to "tuan" (and "tuần", a week). All five
  are word-collision names: a match may not be a name at all.
- ``Khuê`` is the control, and finding one took measuring rather than
  guessing. The first version of this corpus listed ``Lan`` and ``Tuấn`` as
  names that "collide with nothing", and the harness disproved it immediately:
  "để tuần sau xử lý" matched the name Tuấn. Folding is why. Diacritics carry
  most of the contrast between Vietnamese syllables, so once they are stripped
  a given name almost always lands on an ordinary word. **The non-colliding
  name is the rare case, not the common one** - which is the measured reason a
  dedicated alias is required before anything can be treated as a summons.
"""

from __future__ import annotations

from tests.corpus.addressing_types import (
    AddressCase,
    AddressGroup,
    ExpectedClass,
    ExpectedIntent,
)

CORPUS_VERSION = "1"

DEDICATED_ALIASES: tuple[str, ...] = ("MeetAI",)
HUMAN_NAME_ALIASES: tuple[str, ...] = ("Khuê",)
AMBIGUOUS_WORD_ALIASES: tuple[str, ...] = ("Hoa", "Thu", "Bình", "Lan", "Tuấn")

_D = ExpectedClass.DIRECTED_TO_ME
_TP = ExpectedClass.THIRD_PERSON_REFERENCE
_COL = ExpectedClass.ALIAS_COLLISION
_ND = ExpectedClass.NOT_DIRECTED_TO_ME
_UN = ExpectedClass.UNCLEAR

_NONE = ExpectedIntent.NONE
_Q = ExpectedIntent.QUESTION
_R = ExpectedIntent.REQUEST

CASES: tuple[AddressCase, ...] = (
    # ------------------------------------------------------------------ #
    # Group P - dedicated alias plus a question or request. The only
    # group where replying is correct.
    # ------------------------------------------------------------------ #
    AddressCase(
        case_id="P.direct.01",
        text="MeetAI ơi, tóm tắt lại quyết định vừa rồi giúp mình.",
        group=AddressGroup.P_DIRECT_REQUEST,
        expected_class=_D,
        expected_intent=_R,
        expected_reply=True,
        policy_basis="op:Q1 vocative alias + yeu cau ro rang",
    ),
    AddressCase(
        case_id="P.direct.02",
        text="MeetAI, deadline của việc này là khi nào?",
        group=AddressGroup.P_DIRECT_REQUEST,
        expected_class=_D,
        expected_intent=_Q,
        expected_reply=True,
        policy_basis="op:Q1 alias + dau phay + cau hoi",
    ),
    AddressCase(
        case_id="P.direct.03",
        text="MeetAI ơi, cho mình biết trạng thái hiện tại.",
        group=AddressGroup.P_DIRECT_REQUEST,
        expected_class=_D,
        expected_intent=_R,
        expected_reply=True,
        policy_basis="op:Q1 vocative + yeu cau cung cap thong tin",
    ),
    AddressCase(
        case_id="P.direct.04",
        text="MeetAI kiểm tra lại số liệu này nhé.",
        group=AddressGroup.P_DIRECT_REQUEST,
        expected_class=_D,
        expected_intent=_R,
        expected_reply=True,
        policy_basis="op:Q1 alias o vi tri chu ngu cua cau menh lenh",
        notes="Khong co vocative particle; alias chiem slot chu ngu.",
    ),
    AddressCase(
        case_id="P.direct.05",
        text="MeetAI, mọi người đã chốt gì ở phần trước?",
        group=AddressGroup.P_DIRECT_REQUEST,
        expected_class=_D,
        expected_intent=_Q,
        expected_reply=True,
        policy_basis="op:Q1 thang op:Q3 khi alias dedicated duoc goi truc tiep",
        notes="Co ca group marker. Vocative cua alias rieng phai thang.",
    ),
    AddressCase(
        case_id="P.direct.06",
        text="MeetAI giải thích giúp mình phần này với.",
        group=AddressGroup.P_DIRECT_REQUEST,
        expected_class=_D,
        expected_intent=_R,
        expected_reply=True,
        policy_basis="op:Q1 alias + benefactive 'giup'",
    ),
    AddressCase(
        case_id="P.direct.07",
        text="MeetAI ơi, hãy liệt kê các mục còn treo.",
        group=AddressGroup.P_DIRECT_REQUEST,
        expected_class=_D,
        expected_intent=_R,
        expected_reply=True,
        policy_basis="op:Q1 vocative + 'hay' + dong tu yeu cau",
    ),
    AddressCase(
        case_id="P.direct.08",
        text="MeetAI à, phần tích hợp đang ở bước nào?",
        group=AddressGroup.P_DIRECT_REQUEST,
        expected_class=_D,
        expected_intent=_Q,
        expected_reply=True,
        policy_basis="op:Q1 vocative particle 'a'",
    ),
    # ------------------------------------------------------------------ #
    # Group Q - named, nothing asked. Addressee identifiable, reply not
    # permitted. This group exists because of op:Q1 and is the reason the
    # two stages are separate.
    # ------------------------------------------------------------------ #
    AddressCase(
        case_id="Q.voc.01",
        text="MeetAI ơi.",
        group=AddressGroup.Q_VOCATIVE_ONLY,
        expected_class=_D,
        expected_intent=_NONE,
        expected_reply=False,
        policy_basis="op:Q1 vocative don thuan: nhan dien duoc, khong tra loi",
    ),
    AddressCase(
        case_id="Q.voc.02",
        text="MeetAI này.",
        group=AddressGroup.Q_VOCATIVE_ONLY,
        expected_class=_D,
        expected_intent=_NONE,
        expected_reply=False,
        policy_basis="op:Q1 particle 'nay'",
    ),
    AddressCase(
        case_id="Q.voc.03",
        text="Chào MeetAI.",
        group=AddressGroup.Q_VOCATIVE_ONLY,
        expected_class=_D,
        expected_intent=_NONE,
        expected_reply=False,
        policy_basis="op:Q1 dong tu chao truoc ten la mot loi goi",
    ),
    AddressCase(
        case_id="Q.voc.04",
        text="MeetAI ơi, mình nói chuyện một chút.",
        group=AddressGroup.Q_VOCATIVE_ONLY,
        expected_class=_D,
        expected_intent=_NONE,
        expected_reply=False,
        policy_basis="op:Q1 vocative, chua co yeu cau cu the",
    ),
    AddressCase(
        case_id="Q.voc.05",
        text="Xin chào MeetAI, hôm nay họp về phần tích hợp.",
        group=AddressGroup.Q_VOCATIVE_ONLY,
        expected_class=_D,
        expected_intent=_NONE,
        expected_reply=False,
        policy_basis="op:Q1 chao + thong bao, khong hoi gi",
    ),
    AddressCase(
        case_id="Q.voc.06",
        text="MeetAI nhé.",
        group=AddressGroup.Q_VOCATIVE_ONLY,
        expected_class=_D,
        expected_intent=_NONE,
        expected_reply=False,
        policy_basis="op:Q1 particle 'nhe'",
    ),
    # ------------------------------------------------------------------ #
    # Group R - third-person mention.
    # ------------------------------------------------------------------ #
    AddressCase(
        case_id="R.tp.01",
        text="Lan sẽ làm phần báo cáo.",
        group=AddressGroup.R_THIRD_PERSON,
        expected_class=_TP,
        expected_intent=_NONE,
        expected_reply=False,
        policy_basis="plan:S1.7 ten + vi ngu la cau ke ve nguoi do",
    ),
    AddressCase(
        case_id="R.tp.02",
        text="Theo Lan thì nên hoãn lại một tuần.",
        group=AddressGroup.R_THIRD_PERSON,
        expected_class=_TP,
        expected_intent=_NONE,
        expected_reply=False,
        policy_basis="plan:S1.7 gioi tu truoc ten la tham chieu",
    ),
    AddressCase(
        case_id="R.tp.03",
        text="Mình đã nói với Tuấn về việc đó.",
        group=AddressGroup.R_THIRD_PERSON,
        expected_class=_TP,
        expected_intent=_NONE,
        expected_reply=False,
        policy_basis="plan:S1.7 'noi voi <ten>' la tham chieu",
    ),
    AddressCase(
        case_id="R.tp.04",
        text="Tuấn đang kiểm tra lại số liệu.",
        group=AddressGroup.R_THIRD_PERSON,
        expected_class=_TP,
        expected_intent=_NONE,
        expected_reply=False,
        policy_basis="plan:S1.7 bao cao tien do, khong phai yeu cau",
        notes="Chua dong tu yeu cau 'kiem tra' nhung o the tran thuat.",
    ),
    AddressCase(
        case_id="R.tp.05",
        text="Hoa đã gửi file rồi.",
        group=AddressGroup.R_THIRD_PERSON,
        expected_class=_TP,
        expected_intent=_NONE,
        expected_reply=False,
        policy_basis="plan:S1.7 ten trung tu nhung co vi ngu ngoi ba",
    ),
    AddressCase(
        case_id="R.tp.06",
        text="Mình giao cho Lan phần này.",
        group=AddressGroup.R_THIRD_PERSON,
        expected_class=_TP,
        expected_intent=_NONE,
        expected_reply=False,
        policy_basis="plan:S1.7 'giao cho <ten>' la tham chieu",
    ),
    AddressCase(
        case_id="R.tp.07",
        text="MeetAI đã tóm tắt phần trước rồi.",
        group=AddressGroup.R_THIRD_PERSON,
        expected_class=_TP,
        expected_intent=_NONE,
        expected_reply=False,
        policy_basis="handoff:108 alias rieng bi nhac ngoi ba, khong phai goi",
        notes="Alias dedicated o ngoi ba. Khong duoc thanh DIRECTED_TO_ME.",
    ),
    AddressCase(
        case_id="R.tp.08",
        text="Tuấn nói rằng phần đó chưa xong.",
        group=AddressGroup.R_THIRD_PERSON,
        expected_class=_UN,
        expected_intent=_NONE,
        expected_reply=False,
        policy_basis="agents:fail-closed loi thuat lai thi chua xac dinh nguoi nhan",
        notes="Vua la ngoi ba vua la reported speech. UNCLEAR la lua chon than trong.",
    ),
    # ------------------------------------------------------------------ #
    # Group S - the name is being used as an ordinary word.
    # ------------------------------------------------------------------ #
    AddressCase(
        case_id="S.col.01",
        text="Phòng họp cần thêm một bình hoa.",
        group=AddressGroup.S_WORD_COLLISION,
        expected_class=_COL,
        expected_intent=_NONE,
        expected_reply=False,
        policy_basis="plan:S1.7 alias trung tu, khong co bang chung goi",
        notes="Trung ca 'Binh' va 'Hoa' trong mot cau.",
    ),
    AddressCase(
        case_id="S.col.02",
        text="Mùa thu năm nay mưa nhiều.",
        group=AddressGroup.S_WORD_COLLISION,
        expected_class=_COL,
        expected_intent=_NONE,
        expected_reply=False,
        policy_basis="plan:S1.7 'thu' la tu thuong",
    ),
    AddressCase(
        case_id="S.col.03",
        text="Cần thu thập thêm dữ liệu trước khi chốt.",
        group=AddressGroup.S_WORD_COLLISION,
        expected_class=_COL,
        expected_intent=_NONE,
        expected_reply=False,
        policy_basis="plan:S1.7 'thu' trong 'thu thap'",
    ),
    AddressCase(
        case_id="S.col.04",
        text="Giữ bình tĩnh, mình xem lại sau.",
        group=AddressGroup.S_WORD_COLLISION,
        expected_class=_COL,
        expected_intent=_NONE,
        expected_reply=False,
        policy_basis="plan:S1.7 'binh' trong 'binh tinh'; 'xem lai' o the tran thuat",
    ),
    AddressCase(
        case_id="S.col.05",
        text="Bình đã xác nhận phần của mình xong.",
        group=AddressGroup.S_WORD_COLLISION,
        expected_class=_TP,
        expected_intent=_NONE,
        expected_reply=False,
        policy_basis="plan:S1.7 alias trung tu nhung co vi ngu ngoi ba",
        notes="Cung ten voi S.col.04, khac framing. La cap doi chan doan.",
    ),
    AddressCase(
        case_id="S.col.07",
        text="Phần này để tuần sau xử lý.",
        group=AddressGroup.S_WORD_COLLISION,
        expected_class=_COL,
        expected_intent=_NONE,
        expected_reply=False,
        policy_basis="plan:S1.7 'tuan' trong 'tuan sau' trung voi ten Tuan",
        notes=(
            "Case nay bat dau la T.none.08 voi nhan UNCLEAR va gia dinh sai "
            "rang 'Tuan' khong trung tu nao. Harness bac bo ngay."
        ),
    ),
    AddressCase(
        case_id="S.col.08",
        text="Khuê sẽ trình bày phần sau.",
        group=AddressGroup.S_WORD_COLLISION,
        expected_class=_TP,
        expected_intent=_NONE,
        expected_reply=False,
        policy_basis="plan:S1.7 ten khong trung tu, co vi ngu ngoi ba",
        notes="Control: ten duy nhat trong corpus khong trung tu thong dung.",
    ),
    AddressCase(
        case_id="S.col.06",
        text="Hoa trong phòng đã nở hết rồi.",
        group=AddressGroup.S_WORD_COLLISION,
        expected_class=_COL,
        expected_intent=_NONE,
        expected_reply=False,
        policy_basis="plan:S1.7 'hoa' la tu thuong",
    ),
    # ------------------------------------------------------------------ #
    # Group T - nobody in particular, or the room.
    # ------------------------------------------------------------------ #
    AddressCase(
        case_id="T.none.01",
        text="Mọi người nghĩ sao về phương án này?",
        group=AddressGroup.T_NO_ADDRESSEE,
        expected_class=_ND,
        expected_intent=_Q,
        expected_reply=False,
        policy_basis="op:Q3 cau hoi huong ca nhom khong nham vao MeetAI",
    ),
    AddressCase(
        case_id="T.none.02",
        text="Ai làm phần tích hợp nhỉ?",
        group=AddressGroup.T_NO_ADDRESSEE,
        expected_class=_ND,
        expected_intent=_Q,
        expected_reply=False,
        policy_basis="op:Q3 'ai lam' huong vao nhom",
    ),
    AddressCase(
        case_id="T.none.03",
        text="Cả nhóm xem lại tài liệu trước buổi sau.",
        group=AddressGroup.T_NO_ADDRESSEE,
        expected_class=_ND,
        expected_intent=_NONE,
        expected_reply=False,
        policy_basis="op:Q3 'ca nhom' la nguoi nhan tap the",
    ),
    AddressCase(
        case_id="T.none.04",
        text="Bạn gửi lại link giúp mình nhé.",
        group=AddressGroup.T_NO_ADDRESSEE,
        expected_class=_UN,
        expected_intent=_R,
        expected_reply=False,
        policy_basis="op:Q2 dai tu chung, khong alias, khong turn context",
        notes="Co yeu cau that nhung nguoi nhan khong xac dinh.",
    ),
    AddressCase(
        case_id="T.none.05",
        text="Anh ơi, cho mình hỏi một chút.",
        group=AddressGroup.T_NO_ADDRESSEE,
        expected_class=_UN,
        expected_intent=_NONE,
        expected_reply=False,
        policy_basis="op:Q2 vocative voi dai tu chung van la khong ro",
    ),
    AddressCase(
        case_id="T.none.06",
        text="Chị nghĩ thế nào?",
        group=AddressGroup.T_NO_ADDRESSEE,
        expected_class=_UN,
        expected_intent=_Q,
        expected_reply=False,
        policy_basis="op:Q2 dai tu chung + cau hoi, nguoi nhan khong xac dinh",
    ),
    AddressCase(
        case_id="T.none.07",
        text="Hôm nay trời mưa to.",
        group=AddressGroup.T_NO_ADDRESSEE,
        expected_class=_UN,
        expected_intent=_NONE,
        expected_reply=False,
        policy_basis="agents:fail-closed khong co bang chung nguoi nhan",
    ),
    AddressCase(
        case_id="T.none.09",
        text="Các bạn chuẩn bị tài liệu giúp mình với.",
        group=AddressGroup.T_NO_ADDRESSEE,
        expected_class=_ND,
        expected_intent=_R,
        expected_reply=False,
        policy_basis="op:Q3 'cac ban' la nguoi nhan tap the",
    ),
    # ------------------------------------------------------------------ #
    # Group U - reported speech, jokes, self-correction, negation. The
    # adversarial group: each case contains a summons that is not live.
    # ------------------------------------------------------------------ #
    AddressCase(
        case_id="U.quote.01",
        text="Lúc đó bạn ấy nói là MeetAI ơi, giúp mình với.",
        group=AddressGroup.U_QUOTE_NEGATION,
        expected_class=_UN,
        expected_intent=_R,
        expected_reply=False,
        policy_basis="agents:fail-closed loi goi da xay ra voi nguoi khac",
        notes="Khong co guard thuat lai thi day la mot false activation.",
    ),
    AddressCase(
        case_id="U.quote.02",
        text="Ví dụ như MeetAI tóm tắt giúp mình thì sao.",
        group=AddressGroup.U_QUOTE_NEGATION,
        expected_class=_UN,
        expected_intent=_R,
        expected_reply=False,
        policy_basis="agents:fail-closed cau gia dinh khong phai loi goi",
    ),
    AddressCase(
        case_id="U.quote.03",
        text="Không phải MeetAI, mình hỏi Lan.",
        group=AddressGroup.U_QUOTE_NEGATION,
        expected_class=_UN,
        expected_intent=_NONE,
        expected_reply=False,
        policy_basis="agents:fail-closed nguoi noi dang phu dinh chinh minh",
    ),
    AddressCase(
        case_id="U.quote.04",
        text="Ý mình là MeetAI ơi, tóm tắt lại giúp.",
        group=AddressGroup.U_QUOTE_NEGATION,
        expected_class=_UN,
        expected_intent=_R,
        expected_reply=False,
        policy_basis="agents:fail-closed tu sua cau thi chua on dinh",
        notes="Co the that su dang goi MeetAI. UNCLEAR la false non-address co y.",
    ),
    AddressCase(
        case_id="U.quote.05",
        text="Mình nói đùa thôi, MeetAI ơi.",
        group=AddressGroup.U_QUOTE_NEGATION,
        expected_class=_UN,
        expected_intent=_NONE,
        expected_reply=False,
        policy_basis="agents:fail-closed noi dua khong phai loi goi",
    ),
    AddressCase(
        case_id="U.quote.06",
        text="Đừng tóm tắt gì cả nhé.",
        group=AddressGroup.U_QUOTE_NEGATION,
        expected_class=_UN,
        expected_intent=_R,
        expected_reply=False,
        policy_basis="op:Q2 menh lenh phu dinh, khong xac dinh nguoi nhan",
        known_gap=True,
        notes=(
            "Lop loi: menh lenh phu dinh. 'dung <dong tu>' la mot yeu cau "
            "nhung detector doi dong tu o dau menh de nen tra NONE. "
            "Khong gay hai hom nay vi class la UNCLEAR."
        ),
    ),
    AddressCase(
        case_id="U.quote.07",
        text="Trích lại lời Tuấn: MeetAI ơi, chốt giúp mình.",
        group=AddressGroup.U_QUOTE_NEGATION,
        expected_class=_UN,
        expected_intent=_R,
        expected_reply=False,
        policy_basis="agents:fail-closed trich dan tuong minh",
    ),
    AddressCase(
        case_id="U.quote.08",
        text="Xin lỗi, mình nói lại: phần này chưa xong.",
        group=AddressGroup.U_QUOTE_NEGATION,
        expected_class=_UN,
        expected_intent=_NONE,
        expected_reply=False,
        policy_basis="agents:fail-closed tu sua cau",
    ),
    # ------------------------------------------------------------------ #
    # Group V - several possible addressees, or the capture itself is
    # uncertain. This is where Gate 0-C being open shows up.
    # ------------------------------------------------------------------ #
    AddressCase(
        case_id="V.amb.01",
        text="MeetAI ơi, tóm tắt giúp mình.",
        group=AddressGroup.V_AMBIGUOUS_SPEAKER,
        expected_class=_UN,
        expected_intent=_R,
        expected_reply=False,
        transcript_complete=False,
        policy_basis="agents:fail-closed transcript khong day du",
        notes="Van ban giong P.direct.01. Chi khac provenance.",
    ),
    AddressCase(
        case_id="V.amb.02",
        text="Lan ơi, cho mình biết tiến độ.",
        group=AddressGroup.V_AMBIGUOUS_SPEAKER,
        expected_class=_UN,
        expected_intent=_R,
        expected_reply=False,
        policy_basis="op:Q4 goi ten nguoi, nguoi do co the dang co mat",
    ),
    AddressCase(
        case_id="V.amb.03",
        text="Tuấn ơi, kiểm tra lại giúp mình phần này.",
        group=AddressGroup.V_AMBIGUOUS_SPEAKER,
        expected_class=_UN,
        expected_intent=_R,
        expected_reply=False,
        policy_basis="op:Q4 vocative voi ten nguoi khong bao gio thanh DIRECT",
    ),
    AddressCase(
        case_id="V.amb.04",
        text="Hoa ơi, xem lại phần này nhé.",
        group=AddressGroup.V_AMBIGUOUS_SPEAKER,
        expected_class=_UN,
        expected_intent=_R,
        expected_reply=False,
        policy_basis="op:Q4 ten trung tu duoc goi: co the la nguoi that",
    ),
    AddressCase(
        case_id="V.amb.05",
        text="Đúng rồi, tiếp tục đi.",
        group=AddressGroup.V_AMBIGUOUS_SPEAKER,
        expected_class=_D,
        expected_intent=_NONE,
        expected_reply=False,
        speaker_mapping_reliable=True,
        addressed_to_me_by_turn=True,
        policy_basis="op:Q1 turn context tin cay xac dinh nguoi nhan, khong co yeu cau",
        notes="Chi dat duoc khi Gate 0-C dong. Hom nay la duong code chua dung.",
    ),
    AddressCase(
        case_id="V.amb.06",
        text="Lan ơi, đúng rồi.",
        group=AddressGroup.V_AMBIGUOUS_SPEAKER,
        expected_class=_UN,
        expected_intent=_NONE,
        expected_reply=False,
        speaker_mapping_reliable=True,
        addressed_to_me_by_turn=True,
        policy_basis="op:Q4 ten nguoi canh tranh thang turn context",
        notes="Turn context khong duoc ghi de mot nguoi nhan canh tranh.",
    ),
    AddressCase(
        case_id="V.amb.07",
        text="Mọi người với MeetAI cùng rà lại nhé.",
        group=AddressGroup.V_AMBIGUOUS_SPEAKER,
        expected_class=_ND,
        expected_intent=_NONE,
        expected_reply=False,
        policy_basis="op:Q3 nguoi nhan la ca nhom, khong phai loi goi rieng",
        notes="Alias xuat hien nhung khong o vi tri duoc goi rieng.",
    ),
    AddressCase(
        case_id="V.amb.08",
        text="MeetAI",
        group=AddressGroup.V_AMBIGUOUS_SPEAKER,
        expected_class=_UN,
        expected_intent=_NONE,
        expected_reply=False,
        policy_basis="handoff:108 alias tran, khong bang chung goi",
        notes="Truong hop ranh gioi: alias mot minh, khong framing, khong yeu cau.",
    ),
    AddressCase(
        case_id="V.amb.09",
        text="MeetAI ơi, tóm tắt giúp mình phần",
        group=AddressGroup.V_AMBIGUOUS_SPEAKER,
        expected_class=_UN,
        expected_intent=_R,
        expected_reply=False,
        transcript_complete=False,
        policy_basis="agents:fail-closed doan noi chong hoac bi cat",
    ),
    AddressCase(
        case_id="V.amb.10",
        text="Thu ơi, gửi lại tài liệu giúp mình.",
        group=AddressGroup.V_AMBIGUOUS_SPEAKER,
        expected_class=_UN,
        expected_intent=_R,
        expected_reply=False,
        policy_basis="op:Q4 ten trung tu duoc goi vocative",
    ),
)
