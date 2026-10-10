# Bộ eval cần Sơn duyệt — 16 case, 13 đường false answer trên 12 cơ chế

**Revision:** `29983d9`. **Xác nhận:** lượt 22–24 **không sửa một dòng nào**
trong `src/` — `git diff 2ed4519 HEAD -- src/` **rỗng**.

**Phép đếm, đối chiếu lại từ code ở lượt 24** *(không suy từ prose)*:

| | Số | Cách đếm |
|---|---|---|
| Case | **16** | `grep -c '^### EV-'`, và 16 dòng trong bảng duyệt |
| **false answer** | **13 case** / **12 cơ chế** | EV-01 và EV-02 **chung một cơ chế** (động từ đảo nghĩa), nên số **case** và số **cơ chế** lệch nhau một |
| false abstention | **2** | EV-14, EV-15 — chiều MeetAI im quá mức |
| positive control | **1** | EV-12b — hành vi **đúng**, có mặt để chứng minh đường "khai gap" hoạt động |
| | **= 16** | 13 + 2 + 1 |

> **Bản trước ghi tiêu đề "15 case" và "12 đường false answer".** Số 12 là
> số **cơ chế**, không phải số **case** — tôi đã dùng lẫn hai đơn vị. Đếm lại
> bằng code: **16 case**, trong đó **13** là false answer. Không nhãn nào đổi.

**Nhãn trong tài liệu này là [ĐỀ XUẤT], chưa phải quyết định.** Chúng là nhãn
*tôi* đề nghị, trên corpus *tôi* tự viết. Chúng **không** được tính là "bộ eval
Sơn kiểm soát" mà `AGENTS.md` yêu cầu trước khi sửa tokeniser/lexicon — chính
tài liệu này là thứ để Sơn biến chúng thành bộ đó.

> **Bản này đã được sửa sau hai review độc lập, và chúng bắt được ba lỗi của
> tôi:** (1) tôi viết rằng authority gate **không** bắt được nhóm consent —
> **đo ra thì nó bắt**; (2) nhãn tôi đề xuất cho EV-01 **mô tả sai** cái card;
> (3) tôi chỉ sai chỗ cần sửa cho EV-01. Chi tiết ở từng case. Tôi **tự tái lập
> mọi phát hiện bằng phép đo** trước khi sửa tài liệu.

## Cách duyệt

Mỗi case có một dòng để Sơn đánh: **OK** / **SỬA: &lt;nhãn&gt;** / **BỎ**.

Không cần duyệt hết một lượt. **Nhóm A là phần đáng đọc trước** — đó là những
case mà **answerability là lớp phòng vệ DUY NHẤT**.

### Bốn nhãn

| Nhãn | Nghĩa | MeetAI làm gì |
|---|---|---|
| `SUPPORTED` | Card đỡ đúng claim | **Được nói** |
| `UNSUPPORTED` | Subject hoặc giá trị **vắng** khỏi card được dẫn | Im, nói cần hỏi Sơn |
| `PARTIAL_UNDECLARED` | Câu hỏi đòi thứ **không claim nào** đáp và **không gap nào** khai | Im |
| `UNCLEAR` | **Không kiểm được** — không có gì để đối chiếu | Im, nói cần hỏi Sơn |

`UNSUPPORTED` và `UNCLEAR` khác nhau ở chỗ đáng quan tâm: `UNSUPPORTED` nghĩa
là *đã kiểm và sai*; `UNCLEAR` nghĩa là *không kiểm được*. Operator đọc nhãn
như **lý do**, nên gán sai là trao cho Sơn một lý do **mô tả sai cái card**.
**Đúng lỗi tôi đã mắc hai lần** — EV-07 và EV-01.

### Phân biệt phải giữ — trả lời một phần vs thay thế

| | Việc gì | Nhãn |
|---|---|---|
| Câu hỏi **nhiều phần**, trả lời phần có căn cứ, **im** về phần còn lại | **thiếu phần trả lời** | `PARTIAL_UNDECLARED` |
| Câu hỏi **một giá trị**, đưa một dữ kiện **liên quan nhưng khác** | **trả lời sai thứ** | `UNSUPPORTED` |

**`P.undeclared.01` thuộc loại thứ nhất.** Đo được, cùng một claim: câu hỏi
**hai phần** → `PARTIAL_UNDECLARED` (không phát); câu hỏi **một phần** →
`SUPPORTED` (phát). Nên claim đó tự nó **không sai**; cái sai là **sự im lặng**.

### Lớp nào là phòng vệ cuối — đã đo qua authority gate thật

Tôi đã chạy **từng** câu trả lời qua `evaluate_response` (gate tất định, bước 7
pipeline). Kết quả **đảo thứ tự ưu tiên** của bản trước:

| | Số case | Nghĩa |
|---|---|---|
| **Gate CHO QUA** | **12/16** | Trong đó **11 là false answer** mà **answerability là lớp phòng vệ DUY NHẤT** giữa một câu sai và cuộc họp; case thứ 12 là **EV-12b**, hành vi đúng |
| **Gate TỪ CHỐI** | **4/16** | EV-01, EV-09, EV-14, EV-15 — có phòng vệ lớp hai |

Đã đối chiếu **từng dòng** của bảng duyệt với `evaluate_response`: cả 16 dòng
khớp. Trong 4 case gate từ chối, **2 là false answer** (EV-01, EV-09) và **2 là
false abstention** (EV-14, EV-15). Cộng lại: **11 + 2 = 13** false answer.

**Bản trước của tài liệu này mở đầu bằng *"authority gate không bắt được"* cho
nhóm consent. Sai, và đo ra thì ngược lại:** gate từ chối EV-01 bằng **hai**
rule (`detected_confirmation_on_behalf`, `detected_vote`). Nên EV-01 **bớt**
nguy hiểm hơn tôi xếp, không phải hơn.

### Control — và 6 trong số đó không phải control theo nghĩa đó

Đếm lại từ code ở lượt 24, và **cả hai con số bản trước đều sai** (bản trước
ghi "14 control, 8 + 6"):

| | Số | |
|---|---|---|
| **Mục control có tên** | **15** | EV-15c được tách thành `EV-15c-1` và `EV-15c-2` |
| **Khẳng định control** | **18** | vì **3 mục** mang **cả hai** loại: `EV-03c`, `EV-06c`, `EV-13c` |
| — loại "phải tiếp tục trả lời được" | **12** | việc của chúng là bắt một bản sửa mua an toàn bằng cách từ chối thêm. **Cả 12 đã đo: trả lời được hôm nay** |
| — loại "chốt từ chối" | **6** | khẳng định một case **phải tiếp tục bị từ chối**. Chúng **không** làm được việc của loại trên |

**Đã đo từng khẳng định và so với loại nó tự khai: 18/18 khớp, 0 lệch.** Nên
phép phân loại là đúng; chỉ con số tổng là sai, và nó sai vì tôi đếm **mục** như
thể mỗi mục mang đúng một khẳng định. `EV-15c-2` từ chối ở mức
`evidence_self_contradictory` chứ không phải `UNSUPPORTED` — đúng chiều, sai lý
do, và điều đó đã được ghi tại chỗ.

---

## NHÓM A — answerability là lớp phòng vệ DUY NHẤT (gate cho qua)

### EV-02 — Đề xuất bị từ chối, phát thành con số ⚠️

| | |
|---|---|
| **Card** | `"Đề xuất ngân sách 240 triệu đồng đã bị từ chối."` |
| **Câu hỏi / Claim** | `"Ngân sách là bao nhiêu?"` → `"ngân sách là 240 triệu đồng"` |
| **Hôm nay** | `SUPPORTED`, findings **rỗng**, **đã phát** |
| **Authority gate** | **CHO QUA** — answerability là lớp duy nhất |
| **Nhãn [ĐỀ XUẤT]** | **`UNSUPPORTED`** |
| **Phát?** | **Không** |
| **Nhóm lỗi** | Gốc 3 — `bị từ chối` **có** là anchor `APPROVAL` mà module thấy, nhưng nó **không ràng buộc** một claim không tự khai anchor approval nào |

**Biến thể — cùng kết quả, KHÁC cơ chế** *(review bắt được sự gộp này của
tôi)*: `"đã bị bác bỏ"` và `"đã bị huỷ"` cũng phát — nhưng `bác bỏ`/`huỷ`
**không nằm trong `_APPROVAL` chút nào**, nên ở hai biến thể đó **không bên nào**
có anchor approval. **Cùng nhãn, hai chỗ sửa khác nhau.**

**Control EV-02c** *(phải tiếp tục trả lời được)* — card `"Sơn không đồng ý
phương án B."`, claim `"Sơn không đồng ý phương án B"` → **phải vẫn
`SUPPORTED`**: thuật lại một lời **từ chối** là việc hợp lệ. *(đo: trả lời
được)*

> **Sơn đánh:** ☐ OK  ☐ SỬA: ______  ☐ BỎ

### EV-11 — Tên người không có căn cứ trong CHÍNH câu nói ra ⚠️

| | |
|---|---|
| **Card** | `"Ngân sách hạ tầng đã duyệt là 240 triệu đồng."` |
| **Claim** | `"ngân sách hạ tầng là 240 triệu đồng"` *(đúng)* |
| **Câu phát ra** | `"Theo ghi chú đã duyệt, ngân sách hạ tầng là 240 triệu đồng, do Trâm phụ trách."` |
| **Hôm nay** | `SUPPORTED`, **đã phát** |
| **Authority gate** | **CHO QUA** |
| **Nhãn [ĐỀ XUẤT]** | **`UNCLEAR`** *(mức `MALFORMED`)* |
| **Phát?** | **Không** |
| **Nhóm lỗi** | Gốc 3 — phép kiểm giá trị mồ côi chỉ soi **ba lớp anchor** |

**Đo cả lớp:** vế mồ côi dạng **số** / **thời gian** / **phê duyệt** → **bị
bắt** (`MALFORMED`). Dạng **tên người** / **địa điểm** / **nhãn phương án** →
**cho qua**. Nên `"do Trâm phụ trách"` được nói ra mà **không claim nào và
không card nào** đỡ — đúng điều dự án ghi là **không được xảy ra**.

**Quan trọng về cách sửa:** **không** được thêm một lớp anchor "tên người".
Docstring của `UNVERIFIABLE_CLAIM` cam kết ngược lại — dự án **không giữ danh
sách tên người tham gia**, và **suy tên từ transcript là việc không được làm**.
Hình dạng duy nhất làm được là một phép kiểm **không cần lớp từ**: không span
nào của câu nói ra được nằm ngoài văn bản của các claim.

**Control EV-11c** *(phải tiếp tục trả lời được)* — **cùng** card và claim, câu
phát ra **không** có vế mồ côi → **phải `SUPPORTED`**. *(đo: trả lời được)*

> **Sơn đánh:** ☐ OK  ☐ SỬA: ______  ☐ BỎ

### EV-05 — "Đã duyệt" mượn từ một chủ thể khác trong cùng câu ⚠️

| | |
|---|---|
| **Card** | `"Chi phí hạ tầng vẫn đang xem xét, đề xuất thiết bị đã được duyệt."` |
| **Câu hỏi / Claim** | `"Chi phí hạ tầng đã duyệt chưa?"` → `"chi phí hạ tầng đã được duyệt"` |
| **Hôm nay** | `SUPPORTED`, **đã phát** |
| **Authority gate** | **CHO QUA** |
| **Nhãn [ĐỀ XUẤT]** | **`UNSUPPORTED`** |
| **Phát?** | **Không** |
| **Nhóm lỗi** | **Gốc 3**, không phải gốc 2 *(review sửa chỗ này của tôi)* |

**Vì sao đổi nhóm lỗi — đã đo:** clause nguồn `"Chi phí hạ tầng vẫn đang xem
xét"` **không có từ phủ định nào** và **không có anchor nào** (`_APPROVAL` chỉ
phủ `đã duyệt` / `chưa duyệt` / `chờ duyệt` / `bị từ chối`…, **không** phủ
`đang xem xét`). Nên cả hai nửa của bản sửa tôi đề nghị cho gốc 2 — kiểm
polarity trên phần kế thừa, và chặn kế thừa khi nguồn có anchor cùng lớp — đều
là **no-op** trên case này. Nguyên nhân thật: **một trạng thái "đang chờ" không
hề có trong lexicon APPROVAL**. Inheritance *có* xảy ra (đo được) nhưng là điều
kiện **cần, không đủ**.

**Control EV-05c** *(phải tiếp tục trả lời được)* — card `"Ngân sách hạ tầng đã
duyệt là 240 triệu đồng."`, claim `"ngân sách hạ tầng là 240 triệu đồng"` →
**phải vẫn `SUPPORTED`**. *(đo: trả lời được)*

> **Sơn đánh:** ☐ OK  ☐ SỬA: ______  ☐ BỎ

### EV-03 — Claim không có một subject token nào

| | |
|---|---|
| **Card** | `"Quy trình tuyển dụng đã được duyệt."` |
| **Câu hỏi / Claim** | `"Tài liệu đã duyệt chưa?"` → `"Tài liệu đã được duyệt"` |
| **Hôm nay** | `SUPPORTED`, **đã phát** |
| **Authority gate** | **CHO QUA** |
| **Nhãn [ĐỀ XUẤT]** | **`UNCLEAR`** |
| **Phát?** | **Không** |
| **Nhóm lỗi** | Gốc 1 — `subject_tokens("Tài liệu đã được duyệt")` **rỗng** (mọi từ là stopword), và phép khớp subject là **phép chứa**, nên **∅ là tập con của mọi card** |

**Điều kiện thật, hẹp hơn bản trước của tôi** *(review bắt được)*: bản trước ghi
*"hoặc bất kỳ card nào"* — **sai**. Đo được: card phải **tự nó mang một anchor
`APPROVAL` khớp**. Với card `"Ngân sách tổng là 240 triệu đồng."` thì **bị từ
chối** (`unsupported_anchor:approval`). Phép khớp **subject** sụp đổ với mọi
card, nhưng phép khớp **anchor** vẫn cắn. Nên tôi cũng **bỏ** chữ "dễ gặp nhất".

**Lý do `UNCLEAR` chứ không `UNSUPPORTED`:** không có subject nào để **vắng**.
Không có gì được *kiểm và thấy sai*.

**Control EV-03c** *(chốt từ chối — không phải control "phải trả lời được")* —
claim `"hợp đồng đã được duyệt"` với card không liên quan → **phải
`UNSUPPORTED`**; và với card `"Hợp đồng đã được duyệt."` → **phải `SUPPORTED`**
*(cái thứ hai mới là control theo nghĩa phải-trả-lời-được; đo: trả lời được)*.

> **Sơn đánh:** ☐ OK  ☐ SỬA: ______  ☐ BỎ

### EV-13 — Hai card đã duyệt trái nhau, **viết khác từ**

| | |
|---|---|
| **Cards** | `"Deadline báo cáo tháng… đã duyệt là thứ sáu."` **và** `"Hạn chót nộp báo cáo tháng… đã duyệt là thứ ba."` |
| **Câu hỏi / Claim** | `"Deadline báo cáo tháng… là ngày nào?"` → `"deadline báo cáo tháng là thứ sáu"` |
| **Hôm nay** | `SUPPORTED`, **đã phát** |
| **Authority gate** | **CHO QUA** |
| **Nhãn [ĐỀ XUẤT]** | **`CONFLICTING`** *(verdict `unsupported`)* |
| **Phát?** | **Không** |
| **Nhóm lỗi** | Gốc 4 — phép so chéo card chỉ ghép card có subject **chứa** subject của claim, và `hạn chót nộp` **không chia token nào** với `deadline` |

**Nó nói một điều về case đang được từ chối đúng:** cùng hình dạng với
`C.conflict.01`, khác biệt **duy nhất** là hai card ở đó **dùng chung từ vựng**.
Đã đo riêng: đổi **loại giá trị** (thứ trong tuần vs ngày số) **không** ảnh
hưởng; đổi **từ vựng** thì có.

**Biến thể trong CÙNG một card:** `"Deadline báo cáo là thứ sáu. Hạn chót báo
cáo là thứ ba."` → vẫn phát. Nhãn [ĐỀ XUẤT] **`UNCLEAR`**.

**Control EV-13c** — *(chốt từ chối)* hai card **cùng từ vựng**, trái ngày →
**phải `CONFLICTING`**; *(phải trả lời được)* **một** card một ngày → **phải
`SUPPORTED`**. *(đo: trả lời được)*

> **Sơn đánh:** ☐ OK  ☐ SỬA: ______  ☐ BỎ

### EV-04 — Qualifier bị xoá khỏi giá trị

| | |
|---|---|
| **Card** | `"Ngân sách hạ tầng đề xuất là 240 triệu đồng."` |
| **Claim** | `"ngân sách hạ tầng là 240 triệu đồng"` *(mất `đề xuất`)* |
| **Hôm nay** | `SUPPORTED`, **đã phát** · **Gate CHO QUA** |
| **Nhãn [ĐỀ XUẤT]** | **`UNSUPPORTED`** · **Phát? Không** |
| **Nhóm lỗi** | Gốc 1 — phép chứa **không thấy được việc xoá** |

Khung phát ngôn là *"theo ghi chú đã duyệt"*, nên câu nói ra khẳng định **hai**
điều — đây là con số, **và** nó đã được duyệt — trong khi card **không** nói
điều nào. **Biến thể cùng gốc, cùng nhãn:** `sơ bộ`, `tạm tính`, `khoảng`,
`dự kiến`.

**Control EV-04c** *(phải tiếp tục trả lời được)* — claim **giữ** qualifier →
**phải vẫn `SUPPORTED`**. MeetAI **được** thuật lại một đề xuất, miễn là **gọi
nó là đề xuất**. *(đo: trả lời được, cả với `sơ bộ` và `chờ duyệt`)*

> **Sơn đánh:** ☐ OK  ☐ SỬA: ______  ☐ BỎ

### EV-06 — Giá trị bị chuyển sang chủ thể khác qua dấu phẩy

| | |
|---|---|
| **Card** | `"Chi phí hạ tầng chưa chốt, ngân sách tổng đã duyệt là 240 triệu đồng."` |
| **Claim** | `"chi phí hạ tầng là 240 triệu đồng"` |
| **Hôm nay** | `SUPPORTED`, **đã phát** · **Gate CHO QUA** |
| **Nhãn [ĐỀ XUẤT]** | **`UNSUPPORTED`** · **Phát? Không** |
| **Nhóm lỗi** | Gốc 2 — inheritance mang subject, không mang polarity |

Đây **đúng ví dụ mở đầu docstring của chính module**, cái mà
`supporting_clause` nói đã đo và đã đóng: **đóng qua dấu chấm**, **mở qua dấu
phẩy** ở thứ tự ngược. **Không cần một từ phủ định nào.** Và nó cũng chuyển
**ngày tháng** sang chủ thể sai.

**Control EV-06c** — *(chốt từ chối)* **cùng hai câu, thay dấu phẩy bằng dấu
chấm** → **phải `UNSUPPORTED`**; *(phải trả lời được)* card `"Ngân sách tổng đã
duyệt là 240 triệu đồng."` + claim đúng → **phải `SUPPORTED`**. *(đo: đúng cả
hai)*

> **Sơn đánh:** ☐ OK  ☐ SỬA: ______  ☐ BỎ

### EV-07 — Claim đúng, nhưng trả lời câu hỏi khác

| | |
|---|---|
| **Cards** | `"Khuê phụ trách kiểm thử giai đoạn 1…"` **và** `"Trâm phụ trách kiểm thử giai đoạn 2…"` |
| **Câu hỏi / Claim** | `"Ai phụ trách kiểm thử giai đoạn 2?"` → `"Khuê phụ trách kiểm thử giai đoạn 1"` |
| **Hôm nay** | `SUPPORTED`, **đã phát** · **Gate CHO QUA** |
| **Nhãn [ĐỀ XUẤT]** | **`PARTIAL_UNDECLARED`** · **Phát? Không** |
| **Nhóm lỗi** | Không có phép so subject của claim với subject của **câu hỏi** |

**Đây là nhãn tôi đã sửa một lần.** Claim **đúng sự thật**, **nguyên văn** card,
dẫn **đúng**. Tôi gán `UNSUPPORTED` lúc đầu; review chỉ ra `UNSUPPORTED` **định
nghĩa là** "subject hoặc giá trị **vắng** khỏi card nó dẫn" — **sai** với một
span nguyên văn.

**Retrieval không cứu được:** hai card **score bằng nhau** (đo: 9 và 9), vì chữ
số bị lột như *giá trị* trước khi tokenise.

**Control EV-07c** *(phải tiếp tục trả lời được)* — **đổi duy nhất câu hỏi**
thành `"…giai đoạn 1…"` → **phải `SUPPORTED`**. *(đo: trả lời được)*
**Giới hạn của control này:** subject token của hai câu hỏi **giống nhau** (chữ
số bị lột), nên nó **không** phát hiện được một bản sửa so subject theo token —
không có gì phân biệt hai câu hỏi ở mức đó.

> **Sơn đánh:** ☐ OK  ☐ SỬA: ______  ☐ BỎ

### EV-08 — Nhãn designator một ký tự

| | |
|---|---|
| **Card / Claim** | `"Phương án B … 240 triệu đồng."` → `"phương án C … 240 triệu đồng"` |
| **Hôm nay** | `SUPPORTED`, **đã phát** · **Gate CHO QUA** |
| **Nhãn [ĐỀ XUẤT]** | **`UNSUPPORTED`** · **Phát? Không** |
| **Nhóm lỗi** | Gốc 1 — `subject_tokens` bỏ token dài **một ký tự** |

**Đã đo cả lớp:** 8 từ chỉ nhãn × 3 cặp chữ = **24/24** đều được trả lời. Còn
`"Phương án 2"` vs `"3"` **bị từ chối** — bởi cơ chế **khác** (chữ số bị lột
như giá trị). Nên **an toàn phụ thuộc designator viết bằng chữ hay bằng số**.

**Lưu ý về cơ chế** *(review bắt được)*: viết claim **đầy đủ** thì subject của
claim **bằng đúng** subject của card — **không có việc xoá nào cả**. Nên đây là
**sự xoá sổ của tokeniser**, không phải "phép chứa dung thứ một từ bị bỏ". Một
bộ dò "claim bỏ chữ" sẽ **không** đóng được case này.

**Control EV-08c** *(phải tiếp tục trả lời được)* — claim nói **đúng**
`"phương án B"` → **phải `SUPPORTED`**. *(đo: trả lời được)*

> **Sơn đánh:** ☐ OK  ☐ SỬA: ______  ☐ BỎ

### EV-10 — Một vế liệt kê bị bỏ

| | |
|---|---|
| **Card / Claim** | `"Ngân sách cho thiết bị và đào tạo là 240 triệu đồng."` → `"ngân sách thiết bị là 240 triệu đồng"` |
| **Hôm nay** | `SUPPORTED`, **đã phát** · **Gate CHO QUA** |
| **Nhãn [ĐỀ XUẤT]** | **`UNSUPPORTED`** · **Phát? Không** |
| **Nhóm lỗi** | Gốc 1 — `và` là stopword và từ của vế kia **vắng mặt** khỏi claim |

**Control EV-10c** *(phải tiếp tục trả lời được)* — claim **giữ** cả hai vế →
**phải `SUPPORTED`**. *(đo: trả lời được)*

> **Sơn đánh:** ☐ OK  ☐ SỬA: ______  ☐ BỎ

### EV-12 — Độ phủ câu hỏi được tính cho CARD chứ không cho claim

| | |
|---|---|
| **Card** | `"Ngân sách đã duyệt là 240 triệu đồng, deadline chưa chốt."` |
| **Câu hỏi** | `"Ngân sách bao nhiêu và deadline bao giờ?"` |
| **Claim** | `"ngân sách là 240 triệu đồng"` — **im** về deadline |
| **Hôm nay** | `SUPPORTED`, **đã phát** · **Gate CHO QUA** |
| **Nhãn [ĐỀ XUẤT]** | **`PARTIAL_UNDECLARED`** · **Phát? KHÔNG** |
| **Nhóm lỗi** | Gốc 5 — `covered_subjects` hấp thụ subject của **card** |

**Càng chắc khi card càng tự nhận là thiếu:** card nói deadline **chưa chốt**,
tức card **tự khai gap**, và chính điều đó **tắt** phép kiểm gap.

> **Sơn đánh:** ☐ OK  ☐ SỬA: ______  ☐ BỎ

### EV-12b — Cùng câu hỏi, nhưng câu trả lời **khai rõ** phần thiếu

| | |
|---|---|
| **Câu phát ra** | `"…ngân sách là 240 triệu đồng. Chưa có căn cứ về deadline, cần hỏi Sơn."` |
| **Claims** | claim thường cho ngân sách **+ một claim `GAP`** cho deadline |
| **Hôm nay** | `SUPPORTED`, **được phát** — đo được, ở **cả hai** biến thể card |
| **Nhãn [ĐỀ XUẤT]** | **`SUPPORTED`** · **Phát? CÓ** |

**Tách khỏi EV-12 vì bản trước gộp chúng, và đó là một lỗi trình bày có hậu
quả** *(review bắt được)*: `PARTIAL_UNDECLARED` map sang `permits_answering =
False`, nên EV-12 **phải bị từ chối** — thứ trở nên phát được là một **câu trả
lời khác**, có claim `GAP`. Viết thành một case với verdict có điều kiện sẽ tạo
ra một case mà **nhãn và khả năng phát mâu thuẫn nhau**.

**Đây chính là "được trả lời phần có căn cứ nếu nói rõ phần thiếu" của quyết
định operator**, và nó **đã hoạt động hôm nay**.

> **Sơn đánh:** ☐ OK  ☐ SỬA: ______  ☐ BỎ

---

## NHÓM B — gate đã từ chối, nhưng answerability vẫn sai

Bốn case này **không** tới được cuộc họp hôm nay vì authority gate chặn. Vẫn
đáng sửa — gate chặn vì **từ ngữ** của câu trả lời, không vì nó biết claim
không có căn cứ, nên một câu diễn đạt khác cùng lỗi sẽ qua.

### EV-01 — Consent bị rút trong cùng một card

| | |
|---|---|
| **Card** | `"Sơn đồng ý phương án B, sau đó bác bỏ."` |
| **Câu hỏi / Claim** | `"Sơn đồng ý phương án B chưa?"` → `"Sơn đồng ý phương án B"` |
| **Hôm nay (answerability)** | `SUPPORTED`, findings **rỗng** |
| **Authority gate** | **TỪ CHỐI** — `detected_confirmation_on_behalf`, `detected_vote` |
| **Nhãn [ĐỀ XUẤT]** | **`UNCLEAR`** *(mức `EVIDENCE_SELF_CONTRADICTORY`)* |
| **Phát?** | **Không** |
| **Nhóm lỗi** | **KHÔNG phải** `_NEGATED` — xem dưới |

**Ba lỗi của tôi ở case này, review bắt, tôi đã đo lại:**

1. **Nhãn `UNSUPPORTED` của tôi mô tả sai card.** Đo được:
   `is_quotation` = **True** (claim là tiền tố **nguyên văn**), `_anchors(card)`
   = **`{}`** (vì `đồng ý`/`bác bỏ` **không** nằm trong `_APPROVAL`), và subject
   của claim **nằm trọn** trong subject của card. **Không có gì vắng.** Nhãn
   đúng là `UNCLEAR` — card **không giữ nổi câu chuyện của chính nó**, và đó là
   `handoff:121` mục *mâu thuẫn*. Nó cũng **nhất quán** với EV-15, nơi hình
   dạng "card đổi ý" cũng trả `UNCLEAR`.
2. **Nhóm lỗi tôi ghi là sai, và sai theo hướng nguy hiểm.** Bản trước chỉ vào
   `bác bỏ` không có trong `_NEGATED`. **Đo được: thêm `bác bỏ` vào `_NEGATED`
   đóng được KHÔNG GÌ CẢ** — `supporting_clause` vẫn trả về clause **thứ nhất**
   (`"Sơn đồng ý phương án B"`), vì clause đó tự nó **không bị phủ định** và
   **chứa** claim. Nếu Sơn đọc dòng cũ như chỗ cần sửa, bản sửa sẽ được làm và
   **lỗ vẫn mở**.
3. **Tôi viết rằng gate không bắt được. Nó bắt**, bằng hai rule.

**Control EV-01c** — card `"Sơn đồng ý phương án B."`, cùng claim → answerability
**phải vẫn `SUPPORTED`**. *(đo: answerability trả lời được)* **Nhưng gate cũng
từ chối control này** (cùng hai rule), nên nó **không** phải control
đầu-cuối: nó chốt answerability, **không** chốt khả năng phát.

> **Sơn đánh:** ☐ OK  ☐ SỬA: ______  ☐ BỎ

### EV-09 — Ordinal viết chữ, `một` là stopword

| | |
|---|---|
| **Card / Claim** | `"Giai đoạn hai hoàn thành ngày 20."` → `"giai đoạn một hoàn thành ngày 20"` |
| **Hôm nay (answerability)** | `SUPPORTED` |
| **Authority gate** | **TỪ CHỐI** — `detected_deadline_commitment` |
| **Nhãn [ĐỀ XUẤT]** | **`UNSUPPORTED`** · **Phát? Không** |
| **Nhóm lỗi** | Gốc 1 — `một` **là** stopword, `hai`/`ba`/`bốn` **không** |

**Lỗ một chiều:** card `một` + claim `hai` thì **bị từ chối**. Lỗ chỉ mở khi
**claim** là bên mơ hồ hơn.

**Control EV-09c** *(chốt từ chối)* — card `"Giai đoạn một…"`, claim
`"giai đoạn hai…"` → **phải `UNSUPPORTED`** *(hôm nay đúng)*.

> **Sơn đánh:** ☐ OK  ☐ SỬA: ______  ☐ BỎ

### EV-14 — Paraphrase thật bị từ chối *(chiều ngược)*

| | |
|---|---|
| **Card** | `"Deadline báo cáo tháng… đã duyệt là thứ sáu."` |
| **Câu hỏi / Claim** | `"Hạn chót nộp báo cáo tháng… là ngày nào?"` → `"hạn chót nộp báo cáo tháng là thứ sáu"` — **đúng ngày** |
| **Hôm nay (answerability)** | `UNSUPPORTED` — **im, dù card trả lời đúng** |
| **Authority gate** | **TỪ CHỐI** — `detected_deadline_commitment` |
| **Nhãn [ĐỀ XUẤT]** | **`SUPPORTED`** |
| **Phát?** | **Không phát được hôm nay dù sửa answerability** — gate chặn |

**Điều này làm EV-14 khó hơn tôi trình bày** *(review bắt được)*: chính cụm
`hạn chót nộp` nằm trong denylist của authority gate, trong khi từ vựng của
card (`deadline báo cáo … là thứ sáu`) thì **được phép**. Nên EV-14 **không
đóng được chỉ trong answerability** — nó cần một thay đổi lexicon, mà
`AGENTS.md` gate riêng.

**Control EV-14c** *(chốt từ chối — case này trước đây KHÔNG có control, vi phạm
quy tắc của chính tài liệu)* — card `"Hạn mức báo cáo đã duyệt là thứ sáu."`
*(giới hạn, không phải mốc)*, cùng claim → **phải tiếp tục `UNSUPPORTED`**.
*(đo: từ chối hôm nay)* Đây là control **quan trọng nhất** trong tài liệu: bảng
đồng nghĩa hiển nhiên nhất biến **10/10** compound `hạn`/`chốt` từ từ chối
thành trả lời, và control này bắt đúng điều đó.

> **Sơn đánh:** ☐ OK  ☐ SỬA: ______  ☐ BỎ

### EV-15 — Sửa một mốc làm im cả card *(chiều ngược)*

| | |
|---|---|
| **Card** | `"Giai đoạn 1 xong ngày 10. Giai đoạn 2 xong ngày 20, nay đổi sang ngày 25."` |
| **Claim** | `"giai đoạn 2 xong ngày 25"` *(giá trị **mới**)* |
| **Hôm nay (answerability)** | `UNCLEAR` — **im** |
| **Authority gate** | **TỪ CHỐI** — `detected_deadline_commitment` |
| **Nhãn [ĐỀ XUẤT]** | **`SUPPORTED`** · **Phát? Không phát được hôm nay** — gate chặn |
| **Nhóm lỗi** | Phạm vi correction không giới hạn theo **event key** |

Nặng hơn: claim về **giai đoạn 1** — mốc correction **không hề chạm tới** —
**cũng bị từ chối**. **Sửa một dòng ghi chú làm im các dòng khác.**

**Control EV-15c đã được thay** *(control cũ của tôi là vô nghĩa — review bắt
được)*. Bản cũ chốt "claim giá trị đã bị thay phải `UNSUPPORTED`", nhưng đo ra
**cả ba** claim trên card đó (giá trị cũ, giá trị mới, và mốc không bị chạm)
đều trả **đúng cùng một** `evidence_self_contradictory` — nên control cũ được
thoả **một cách rỗng bởi chính cái bug** nó định canh.

- **EV-15c-1** *(phải tiếp tục trả lời được)* — card **không có correction**
  (`"Giai đoạn 1 xong ngày 10. Giai đoạn 2 xong ngày 20."`), claim
  `"giai đoạn 2 xong ngày 20"` → **phải `SUPPORTED`**. *(đo: trả lời được)*
- **EV-15c-2** *(chốt từ chối, chỉ có nghĩa SAU khi sửa)* — trên card **có**
  correction, claim giá trị **đã bị thay** (`ngày 20`) → sau khi sửa **phải là
  `UNSUPPORTED`**. Hôm nay nó là `UNCLEAR` — **đúng chiều, sai lý do** — nên nó
  **chưa** canh được gì cho tới khi bản sửa được áp.

> **Sơn đánh:** ☐ OK  ☐ SỬA: ______  ☐ BỎ

---

## Bảng duyệt nhanh

| Case | Nhóm | Hôm nay | Gate | Nhãn [ĐỀ XUẤT] | Phát? | Sơn |
|---|---|---|---|---|---|---|
| **EV-02** đề xuất bị từ chối → con số | A | `SUPPORTED` | cho qua | `UNSUPPORTED` | Không | ☐ |
| **EV-11** tên người mồ côi | A | `SUPPORTED` | cho qua | `UNCLEAR` | Không | ☐ |
| **EV-05** "đã duyệt" mượn chủ thể khác | A | `SUPPORTED` | cho qua | `UNSUPPORTED` | Không | ☐ |
| **EV-03** subject rỗng | A | `SUPPORTED` | cho qua | `UNCLEAR` | Không | ☐ |
| **EV-13** hai card trái nhau, khác từ | A | `SUPPORTED` | cho qua | `CONFLICTING` | Không | ☐ |
| **EV-04** qualifier bị xoá | A | `SUPPORTED` | cho qua | `UNSUPPORTED` | Không | ☐ |
| **EV-06** giá trị chuyển qua dấu phẩy | A | `SUPPORTED` | cho qua | `UNSUPPORTED` | Không | ☐ |
| **EV-07** claim đúng, sai câu hỏi | A | `SUPPORTED` | cho qua | `PARTIAL_UNDECLARED` | Không | ☐ |
| **EV-08** designator một ký tự | A | `SUPPORTED` | cho qua | `UNSUPPORTED` | Không | ☐ |
| **EV-10** bỏ một vế liệt kê | A | `SUPPORTED` | cho qua | `UNSUPPORTED` | Không | ☐ |
| **EV-12** độ phủ tính cho card | A | `SUPPORTED` | cho qua | `PARTIAL_UNDECLARED` | Không | ☐ |
| **EV-12b** gap được khai rõ | A | `SUPPORTED` | cho qua | **`SUPPORTED`** | **Có** | ☐ |
| **EV-01** consent bị rút | B | `SUPPORTED` | **từ chối** | `UNCLEAR` | Không | ☐ |
| **EV-09** ordinal `một` | B | `SUPPORTED` | **từ chối** | `UNSUPPORTED` | Không | ☐ |
| **EV-14** paraphrase thật bị từ chối | B | `UNSUPPORTED` | **từ chối** | **`SUPPORTED`** | gate chặn | ☐ |
| **EV-15** sửa một mốc làm im cả card | B | `UNCLEAR` | **từ chối** | **`SUPPORTED`** | gate chặn | ☐ |

**13 dòng đầu là false answer** (MeetAI nói sai), trên **12 cơ chế** — EV-01 và
EV-02 chung một cơ chế. **EV-14, EV-15 là chiều ngược** (im quá mức) — có mặt để
một bản sửa không thể lấy điểm bằng cách từ chối thêm. **EV-12b** là case chứng
minh đường "trả lời một phần có khai gap" **đang hoạt động**. 13 + 2 + 1 = **16**.

---

## Sau khi Sơn duyệt

Chỉ khi đó mới sửa `src/`, theo **từng gốc lỗi, từng lát**:

1. Chạy corpus đã duyệt **cùng toàn bộ control**.
2. Báo false-answer / false-abstention **theo nhóm, denominator riêng**.
3. **Chỉ đóng một residual khi test của nó thực sự đảo chiều** và **không
   control nào** sinh false-positive mới.

**Chưa làm gì cả cho tới khi có nhãn của Sơn.**

## Giới hạn của chính tài liệu này

- **Nội dung bịa.** Không transcript thật, không cuộc họp thật, không thông tin
  cá nhân. Tên trong card (`Khuê`, `Trâm`) là nhân vật tổng hợp.
- **Nhãn do tôi đề xuất, case cũng do tôi chọn** — kể cả hard negative.
- **Ba lỗi của tôi đã bị review bắt** (xem đầu tài liệu). Điều đó nói rằng các
  nhãn còn lại cũng **chưa** được ai ngoài tôi kiểm — đó là việc của Sơn.
- **Không nói gì về ASR, model, hay đường production.**
- **Không đóng Gate 0 nào**, không tuyên bố năng lực grounding tổng quát.
