# Ma trận: 5 gốc lỗi → lớp sửa → false-positive phải đo → test chứng minh

**Revision:** `1b6d308`. **Chưa sửa gì trong `src/`.** Tài liệu này là **kế
hoạch**, thực hiện **sau** khi Sơn duyệt nhãn ở
[bộ eval](2026-10-10-bo-eval-can-son-duyet.md).

> **Bản này đã sửa sau review độc lập, và review bắt được bốn lỗi của tôi — ba
> trong số đó làm một bản sửa theo kế hoạch cũ sẽ KHÔNG hoạt động:** (1) gốc 1
> là **hai** cơ chế, không một; (2) **EV-05 thuộc gốc 3**, không gốc 2, và
> mutation tôi hứa cho nó **không viết được**; (3) gốc 5 **bị loại theo đúng quy
> tắc 4 của chính tài liệu này** — nó làm **3 case đã ổn định** thành false
> abstention; (4) bản sửa EV-03 là một vị từ **mới**, không phải cơ chế đã có.
> Tôi **tự tái lập từng phát hiện bằng phép đo** trước khi sửa.

**Và một phép đo đổi tiêu chí xếp hạng:** chạy từng câu trả lời qua authority
gate thật cho thấy gate chỉ từ chối **4/16** case. Trong **12/16** case gate cho
qua, **11 là false answer mà answerability là lớp phòng vệ duy nhất** (case thứ
12 là EV-12b, hành vi đúng) — đó mới là tiêu chí, chứ không phải phỏng đoán của
tôi về mức nghiêm trọng. *(Mẫu số `/15` ở bản trước đã được sửa ở lượt 24 sau
khi đếm lại từ code.)*

Mục đích: **12 cơ chế** false answer (**13 case** trong bộ eval — EV-01 và
EV-02 chung một cơ chế) **không** phải 12 chỗ vá. Chúng rơi vào **5
gốc**, và vá theo gốc thì ít rủi ro hơn vá theo biểu hiện — một bản vá theo
biểu hiện đóng được case trong suite rồi để nguyên lớp sinh ra nó.

**Mỗi dòng phải có bốn thứ trước khi được code:** gốc, lớp sửa, **false-positive
cần đo**, và **test/mutation chứng minh**. Thiếu cột ba là cách một bản sửa mua
an toàn bằng việc làm MeetAI im lặng; thiếu cột bốn là cách một control thành
trang trí.

---

## Gốc 1 — Phép chứa coi việc XOÁ là đồng ý

**Gốc này là HAI cơ chế, không một** *(review bắt được, tôi đã đo lại)*. Bản
trước ghi một cơ chế — *"phép chứa coi việc xoá là đồng ý"* — và điều đó làm
**mutation một dòng mà tôi hứa cho gốc 1 không thể tồn tại**:

| Cơ chế | Đường | Đo được |
|---|---|---|
| **1-X: tokeniser XOÁ SỔ token phân biệt** | EV-03, EV-08, EV-09 | Với EV-08 viết claim **đầy đủ**: `subject_tokens(claim)` **BẰNG ĐÚNG** `subject_tokens(card)` — **không có việc bỏ chữ nào cả**. Với EV-03: subject **rỗng** cả hai phía. Một bộ dò "claim bỏ chữ" **không** đóng được chúng |
| **1-D: phép chứa dung thứ token chỉ có ở CARD** | EV-04, EV-10 | `đề xuất` / `đào tạo` **có** trong subject của card và **vắng** khỏi claim. Đây mới là "xoá" theo nghĩa gốc 1 cũ |

EV-09 là **lai**: thay `hai`→`một` mà `một` là stopword, nên một **phép thay**
**trở thành** một **phép xoá**. Với `ba` thay cho `một` thì `claim ⊆ card` là
**False** và nó **từ chối**.

| | |
|---|---|
| **Lớp sửa [ĐỀ XUẤT]** | **Ba lớp riêng, không một lớp.** (a) **subject rỗng** → claim không có subject token nào thì phải là quotation. **Đây là một vị từ MỚI, không phải cơ chế đã có** *(review sửa chỗ này)*: quy tắc hiện có khoá vào *"không có anchor"*, và đo được claim của EV-03 **CÓ** anchor (`approval: da duoc duyet`) — nên quy tắc cũ **không với tới nó**. Hình dạng được tái dùng; vị từ là mới. (b) **designator** → R1b: nhận token một ký tự **chỉ sau từ chỉ nhãn**. (c) **qualifier / vế liệt kê** → **chưa có lớp sửa**; cần khái niệm "từ bổ nghĩa cho giá trị" |
| **False-positive phải đo** | (a) claim có **một** từ không phải stopword vẫn phải trả lời được — `"hợp đồng đã được duyệt"`. (b) toàn bộ **lớp** từ fold thành một ký tự (`ý`, `à`, `ờ`, `ạ`, `ừ`) phải vẫn trả lời được; và **từ chỉ nhãn đứng một mình** (`an toàn`, `mục tiêu`) không được đổi gì. (c) claim **giữ** qualifier hoặc **giữ** cả hai vế phải vẫn trả lời được |
| **Test/mutation chứng minh** | Xoá quy tắc (a) → EV-03 trả lời lại. Xoá (b) → cả **24** cặp designator trả lời lại. Mỗi control là một test **riêng**, không gộp, vì chúng fail vì lý do khác nhau |
| **Trạng thái** | (a) **sẵn sàng**, nhưng là **vị từ mới** (không phải "dùng cơ chế đã có" như bản trước ghi). (b) **sẵn sàng, đã đo cả lớp** (xem dưới). (c) **chưa**, cần thiết kế |

**Đã đo cho (b), cả lớp chứ không một case:** 8 từ chỉ nhãn × 3 cặp chữ = **24
case**. Baseline trả lời **24/24** (sai). R1b từ chối **24/24**. Số case
baseline trả lời mà R1b **vẫn** trả lời: **0**. Và trên **8** từ khẩu ngữ fold
thành một ký tự, R1b làm mất **0** câu trả lời — vì một tiểu từ **không bao giờ
đứng sau** một từ chỉ nhãn, nên quy tắc liên kết AND không với tới chúng.

---

## Gốc 2 — Inheritance mang subject nhưng không mang polarity hay sự gắn kết

**Cơ chế:** clause sau **kế thừa** subject của clause trước;
`supporting_clause` kiểm `_NEGATED` trên `clause.text` **chứ không** trên phần
kế thừa.

**Đường thuộc gốc này:** **chỉ EV-06** (giá trị chuyển qua dấu phẩy, gồm biến
thể **không có từ phủ định nào** và biến thể chuyển **ngày tháng**).

**EV-05 ĐÃ CHUYỂN SANG GỐC 3** *(review bắt được, tôi đo lại và xác nhận)*. Đo
trên clause nguồn `"Chi phí hạ tầng vẫn đang xem xét"`: **không có từ phủ định
nào** (`_NEGATED` không khớp) và **không có anchor nào** (`_APPROVAL` không phủ
`đang xem xét`). Nên **cả hai nửa** của lớp sửa gốc 2 đều là **no-op** trên
EV-05, và mutation tôi hứa — *"xoá phép kiểm polarity-trên-phần-kế-thừa → EV-05
và EV-06 trả lời lại"* — **không viết được**. Nguyên nhân thật của EV-05:
**trạng thái "đang chờ" không hề có trong lexicon APPROVAL** → gốc 3, tức **cần
Sơn duyệt**, không phải "không cần lexicon". Inheritance *có* xảy ra (đo được)
nhưng là điều kiện **cần, không đủ**.

| | |
|---|---|
| **Lớp sửa [ĐỀ XUẤT]** | Kiểm polarity **trên cả phần kế thừa**, và **không** cho một clause kế thừa subject khi clause nguồn mang anchor **cùng lớp** với anchor của clause đích. Lý do điều kiện thứ hai: nếu clause nguồn đã nói về *approval* và clause đích cũng nói về *approval*, thì hai clause đang nói về **hai việc khác nhau**, không phải một việc được tiếp tục |
| **False-positive phải đo** | Inheritance **tồn tại vì một lý do thật** — nó giữ phép phòng vệ chéo clause. Nên phải đo: card một câu nhiều clause **cùng** chủ thể, claim hợp lệ → **vẫn** trả lời được. Đây là lớp dễ bị phá nhất trong cả 5 gốc |
| **Test/mutation chứng minh** | Xoá phép kiểm polarity-trên-phần-kế-thừa → **EV-06** trả lời lại (**không** EV-05 — xem trên). Cộng: card **cùng hai câu, thay dấu phẩy bằng dấu chấm** phải **vẫn** bị từ chối (hôm nay đúng) — nếu bản sửa làm case đó *trả lời*, nó đã phá đường vốn đang đúng |
| **Trạng thái** | **Chưa đo.** Rủi ro over-refusal cao nhất, và nó đụng đúng ví dụ mở đầu docstring của module |

---

## Gốc 3 — Ba lớp anchor là tất cả những gì có ai chịu trách nhiệm

**Cơ chế:** chỉ `NUMBER`, `TIME`, `APPROVAL` được so và được tính. Mọi giá trị
ngoài ba lớp đó **không ai chịu trách nhiệm**.

**Đường thuộc gốc này:** EV-01 (consent bị rút), EV-02 (đề xuất bị từ chối),
EV-05 (**chuyển từ gốc 2** — `đang xem xét` không có trong lexicon APPROVAL),
EV-11 (tên người mồ côi trong câu nói ra).

| | |
|---|---|
| **Lớp sửa [ĐỀ XUẤT]** | **Hai lớp khác nhau, đừng gộp.** (a) **đảo nghĩa** (`từ chối`, `bác bỏ`, `huỷ`, `rút`, `ngừng`) → mở rộng dấu hiệu **rút lại/phủ định**, và **ưu tiên** clause sau khi có dấu hiệu thứ tự (`sau đó`). (b) **giá trị mồ côi ngoài anchor** → phép kiểm giá trị mồ côi phải tính **cả** token không phải anchor trong câu phát ra mà **không claim nào** đỡ |
| **False-positive phải đo** | (a) thuật lại một lời **từ chối** phải hợp lệ: `"Sơn không đồng ý phương án B"` → **vẫn** trả lời được; và `từ chối` trong vai **chủ đề** (`"quy trình từ chối đã duyệt"`) không được biến card thành vô dụng. (b) câu phát ra **không** có vế mồ côi phải **vẫn** trả lời được; và câu phát ra có **khung attribution** (`theo ghi chú đã duyệt`) không được bị tính là giá trị mồ côi |
| **Test/mutation chứng minh** | Xoá (a) → EV-01, EV-02 trả lời lại. Xoá (b) → EV-11 trả lời lại. Control (b) đã có sẵn trong suite: giá trị mồ côi dạng **số** vẫn phải bị bắt (`MALFORMED`) |
| **Trạng thái** | (a) **sẵn sàng về cơ chế**, nhưng là **mở rộng lexicon** → cần Sơn duyệt theo `AGENTS.md`. (b) **sẵn sàng**, không cần lexicon — nó là phép đếm token, không phải nhận dạng từ |

**Sửa lại một tuyên bố của tôi.** Bản trước ghi EV-01 là *"đường nặng nhất"* vì
*"authority gate không bắt được"*. **Đo ra thì gate BẮT** — nó từ chối EV-01
bằng **hai** rule (`detected_confirmation_on_behalf`, `detected_vote`). EV-01
vẫn là một lỗ answerability thật và vẫn phải sửa, nhưng nó **có phòng vệ lớp
hai**, nên **bớt** cấp bách hơn các đường mà gate **cho qua**.

**Hai mục con của gốc 3 cần tách** *(review bắt sự gộp này)*: `bị từ chối`
**có** là anchor `APPROVAL`, còn `bác bỏ` / `huỷ` / `đang xem xét` **không nằm
trong `_APPROVAL` chút nào**. Cùng nhãn, **hai chỗ sửa khác nhau**.

**Và `_NEGATED` KHÔNG phải chỗ sửa cho EV-01.** Đo được: thêm `bác bỏ` vào
`_NEGATED` **đóng được không gì cả** — `supporting_clause` vẫn trả về clause
**thứ nhất** (`"Sơn đồng ý phương án B"`), vì clause đó tự nó không bị phủ định
và **chứa** claim.

---

## Gốc 4 — Key theo token không thấy từ đồng nghĩa

**Cơ chế:** `_event_key` và phép so subject chéo card đều là **tập token**, và
phép thử là **phép chứa**. Hai cách viết khác nhau cho cùng một sự việc không
bao giờ được ghép.

**Đường thuộc gốc này:** EV-13 (hai card trái nhau, khác từ — **và** biến thể
trong **cùng một card**). Chiều ngược: EV-14 (paraphrase thật bị từ chối).

| | |
|---|---|
| **Lớp sửa** | **KHÔNG CÓ ĐỀ XUẤT.** Đây là gốc duy nhất tôi **không** đề nghị sửa |
| **Lý do** | Đã đo: bảng đồng nghĩa gộp `hạn`/`chốt` về `deadline` đóng được **cả** EV-13 và EV-14 trên corpus — nhưng biến **10/10** compound `hạn`/`chốt` thử nghiệm từ **từ chối** thành **trả lời**. Một *giới hạn* không phải một *mốc thời gian*. Mọi bảng đồng nghĩa đủ rộng để ghép `deadline` với `hạn chót` cũng đủ rộng để ghép nó với `hạn mức` |
| **False-positive phải đo nếu vẫn làm** | **Toàn bộ lớp** compound của mỗi âm tiết được đưa vào bảng, không phải một case. Đây là điều kiện tối thiểu, và nó đã **bác** phương án duy nhất tôi thử |
| **Test/mutation chứng minh** | Đã có: sweep 10 compound, ghim trong `test_normalisation_study.py` |
| **Trạng thái** | **Chặn bởi thiếu một cơ chế**, không bởi effort. Cần một khái niệm tương đương **được Sơn kiểm soát** (ví dụ: bảng alias do Sơn khai cho từng scope), chứ không phải suy từ âm tiết |

---

## Gốc 5 — Độ phủ câu hỏi được tính cho CARD chứ không cho claim

**Cơ chế:** `covered_subjects |= claim_subjects | card_subjects`.

**Đường thuộc gốc này:** EV-12. Liên quan: EV-07 (không có phép so claim với
**câu hỏi** — gốc riêng, xem dưới).

| | |
|---|---|
| **Lớp sửa** | ❌ **BỊ LOẠI như đã đề xuất** *(review bắt, tôi đo lại và xác nhận)*. Ý tưởng — bỏ `card_subjects` khỏi `covered_subjects` — **đúng là một dòng**, nhưng đo trên một bản sao của `src` thì nó làm **5/51** case đổi mức độ và sinh **3 false abstention trên case ĐÃ ỔN ĐỊNH**: `S.direct.01` *(chính "case đơn giản" của corpus)*, `R.paraphrase.02`, `Y.letter.02`. Theo **quy tắc 4 của chính tài liệu này**, bản sửa đó **bị loại** |
| **False-positive phải đo** | Cột này ở bản trước **thiếu đúng chỗ quan trọng**: nó kể `P.declared.*` và câu hỏi một phần — **cả ba đều qua**. Thứ vỡ lại nằm ở `S_supported`, `R_paraphrase`, `Y_designator`, **không nhóm nào được nêu**. `S.direct.01` vỡ vì câu hỏi của nó nói `dự án Hải Đăng` mà claim thì không, nên hôm nay **card** là thứ phủ cụm đó. Bài học: cột false-positive phải được **đo trên toàn corpus**, không viết từ suy luận |
| **Test/mutation chứng minh** | Xoá phép sửa → EV-12 trả lời lại. Control: cùng sự im lặng, card **không** nhắc deadline → đã là `PARTIAL_UNDECLARED` hôm nay, phải **giữ** |
| **Trạng thái** | **Cần thiết kế lại**, **không** phải rẻ nhất. Bản sửa phải phân biệt *card nhắc tên dự án* (**ngữ cảnh**, phải tiếp tục phủ được) với *card nhắc nửa sau của câu hỏi hai phần* (**một đòi hỏi chưa đáp**). Đó là một vấn đề thiết kế thật, không phải một dòng. **Chiều thì vẫn đúng**: cả 5 thay đổi đều đi về phía từ chối, **0 false answer mới** |

---

## Ngoài 5 gốc — hai mục cần LỚP KIỂM MỚI

Hai đường **không** thuộc gốc nào ở trên, vì chúng không phải lỗi của một cơ
chế đang có mà là **một phép kiểm chưa tồn tại**.

| Đường | Phép kiểm còn thiếu | Rủi ro |
|---|---|---|
| **EV-07** claim đúng, trả lời sai câu hỏi | So subject của claim với subject của **câu hỏi**. Hiện `question_demands()` chỉ đối chiếu **lớp anchor** (số / thời gian / phê duyệt), nên một claim đúng về giai đoạn 1 thoả một câu hỏi về giai đoạn 2 | **Cao.** Đây là lớp kiểm **mới**, nó sẽ **đẩy over-refusal lên**, và **chưa có phép đo**. Phải là một lát **khảo sát** trước khi là một lát xây |
| **EV-15** sửa một mốc làm im cả card | Giới hạn phạm vi correction theo `_event_key` | **Thấp.** Cơ chế **đã có**, đây là **thu hẹp** một quy tắc quá rộng, và chiều deny-biased **không đổi** |

---

## Thứ tự đề nghị

Xếp theo **(rủi ro của lỗ) ÷ (rủi ro của bản sửa)**, không theo độ dễ:

| # | Việc | Gốc | Vì sao thứ tự này |
|---|---|---|---|
| 1 | **Giá trị mồ côi ngoài anchor** (EV-11) | 3 | Không cần lexicon — là phép đếm token. Gate **cho qua** case này, nên answerability là lớp duy nhất. Nó đóng đúng điều dự án ghi là không được xảy ra: một **tên người** nói ra không căn cứ. **Cách sửa KHÔNG được là một lớp anchor "tên người"** — dự án không giữ danh sách tên |
| 2 | **Subject rỗng** (EV-03) | 1-X | Không mở lexicon. Là **vị từ mới**, không phải cơ chế đã có. Điều kiện thật hẹp hơn bản trước của tôi: card phải tự nó mang anchor `APPROVAL` khớp |
| 3 | **Correction theo event key** (EV-15) | — | Đóng **hai false abstention**, cơ chế **đã có** (`_event_key`), không mở rủi ro mới |
| 4 | **R1b designator** (EV-08) | 1-X | Đã đo **cả lớp**: 24/24 đóng, chi phí **0**. **Cần Sơn duyệt** — tokeniser dùng chung với retrieval |
| 5 | **Đảo nghĩa + trạng thái chờ** (EV-01, EV-02, EV-05) | 3 | **Mở rộng lexicon** → cần Sơn duyệt. Cần **tách hai mục con**, và `_NEGATED` **không** phải chỗ sửa cho EV-01 — đã đo |
| 6 | **Inheritance polarity** (EV-06) | 2 | Rủi ro over-refusal **cao nhất**; đụng phép phòng vệ chéo clause. **Chỉ EV-06** — EV-05 đã chuyển sang mục 5 |
| 7 | **Độ phủ tính cho claim** (EV-12) | 5 | **Hạ từ vị trí 3.** Đo ra: làm **3 case đã ổn định** thành false abstention, gồm `S.direct.01`. Cần **thiết kế lại** |
| 8 | **Qualifier / vế liệt kê** (EV-04, EV-10) | 1c | **Chưa có lớp sửa**; cần thiết kế |
| 9 | **So claim với câu hỏi** (EV-07) | — | Lớp kiểm mới, khảo sát trước |
| — | **Đồng nghĩa** (EV-13, EV-14) | 4 | **Chặn bởi thiếu cơ chế**, cần bảng alias do Sơn kiểm soát |

**Mục 1–3 không cần Sơn duyệt từ vựng.** **Mục 4–5 cần Sơn duyệt** (tokeniser
dùng chung, và mở rộng lexicon). **Mục 6–9 cần đo thêm trước khi ước lượng
được.**

**Một phụ thuộc thứ tự đã đo** *(review nêu)*: nếu gốc 5 được làm **trước** R1b,
nó đổi **cơ sở đo** của R1b — `Y.letter.01` chuyển sang `partial_undeclared`,
nên nhóm `Y_designator` hết false answer **vì lý do sai**. Phép đo **cả lớp** của
R1b thì **không** bị ảnh hưởng (24/24 vẫn trả lời ở cả hai bản), nhưng đó là một
**sự thật về các input này**, không phải một bảo đảm cấu trúc. Thứ tự mới tránh
được phụ thuộc đó.

**Một mâu thuẫn nội bộ tôi phải ghi:** quy tắc 1 dưới đây nói *"một gốc một lát
một commit"*, nhưng thứ tự này **chia gốc 1 ra ba mục** và **gốc 3 ra hai**. Sau
phát hiện 1-X/1-D thì chúng **buộc** phải tách, nên quy tắc cần đọc là *"một
**cơ chế** một lát"* — và **rollback theo gốc không có** cho gốc 1 và gốc 3.

## Quy tắc chung khi thực hiện

1. **Một gốc một lát một commit.** Gộp hai gốc là mất khả năng rollback theo
   gốc, và hai gốc fail vì lý do khác nhau.
2. **Chạy corpus đã duyệt cùng toàn bộ control.** Báo false-answer /
   false-abstention **theo nhóm, denominator riêng**, **không gộp**.
3. **Chỉ đóng một residual khi test của nó thực sự đảo chiều** — tức test ghim
   hành vi hiện tại **fail**, và tôi **đảo** assertion thay vì xoá.
4. **Không control nào được sinh false-positive mới.** Nếu có, bản sửa bị loại
   chứ không nới control.
5. **Không sửa config, không sửa nhãn corpus để test xanh.**
