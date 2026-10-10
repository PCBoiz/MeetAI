# Đo độ bao phủ quan hệ claim–evidence (2026-10-09)

**Revision đo:** `2ed4519` (corpus và harness commit tại `84c4693`)
**Phạm vi:** corpus tổng hợp, local, in-memory. Không GPU, không tải model, không
persistence, không media sink, không Discord. Không đóng Gate 0 nào.

> **Không phải tuyên bố về năng lực grounding tổng quát.** Mọi con số dưới đây
> đo trên **51 case tổng hợp do tôi tự viết**, nội dung bịa. Một corpus tự viết
> thì ứng viên nào nhắm vào chính nó cũng trông hoàn hảo — đó là lý do có thêm
> bộ hard negative riêng, và là lý do con số không được đọc như tỉ lệ đúng trên
> dữ liệu thật.

## 1. Vì sao phải mở rộng corpus

Corpus cũ có 36 case và **module đồng ý với cả 36**. Nghĩa là nó đã **hết khả
năng đo**: nó bao phủ đúng những hình dạng mà module được xây để xử lý. Lát này
thêm 15 case vào bốn quan hệ nó chưa bao giờ với tới, nhãn viết từ **chính
sách** (handoff 119/121, quyết định operator 2026-10-08) **trước** khi chạy.

Kết quả: **51 case, 7 bất đồng**. Ba trong số đó là **false answer**.

## 2. Ba false answer — đo được, chưa đóng

| Case | Tình huống | Vì sao mọi lớp khác đều qua |
|---|---|---|
| `R.crosscard.01` | Hai card đã duyệt **trái nhau** về một sự việc, viết **khác từ**: `"Deadline báo cáo… thứ sáu"` vs `"Hạn chót nộp báo cáo… thứ ba"` | Phép so chéo card chỉ ghép card có subject token **chứa** subject của claim. `"hạn chót nộp"` **không chia token nào** với `"deadline"`, nên hai card không bao giờ được đặt cạnh nhau |
| `Y.letter.01` | Card nói **phương án B** duyệt 240 triệu; câu trả lời nói **phương án C** duyệt 240 triệu | Token phân biệt hai phương án **dài một ký tự**, và `subject_tokens` bỏ token một ký tự như rác. Card vẫn đã duyệt, còn hạn, đúng subject, con số **dẫn đúng** |
| `Q.attribute.01` | Hỏi ai phụ trách **giai đoạn 2**; trả lời **nguyên văn** card về **giai đoạn 1** | Claim **đúng sự thật** và dẫn đúng. Cả hai trục nhãn cũ đều nói "ổn" và **đều đúng** — chúng so claim với **card**. Không gì so claim với **câu hỏi** |

**`Y.letter.01` là một lớp, không phải một câu bất thường.** Đo thêm `"Mục A"`
vs `"Mục B"` → cũng **được trả lời**. Và `"Phương án 2"` vs `"Phương án 3"` thì
**bị từ chối** — nhưng **không** bởi cơ chế người đọc sẽ đoán: chữ số bị lột
như *giá trị* nên thành anchor lệch. Tức **độ an toàn của một designator phụ
thuộc vào nó viết bằng chữ hay bằng số**, và ai đóng `Y.letter.01` bằng cách
nhìn case chữ số sẽ kết luận sai.

**`R.crosscard.01` nói một điều đáng lưu ý về `C.conflict.01`** — case cùng hình
dạng đang **bị từ chối** đúng. Khác biệt duy nhất là hai card ở `C` **dùng chung
từ vựng**. Nên lớp bảo vệ ở `C` là **phụ thuộc từ vựng**, không phải cấu trúc —
điều mà đọc riêng `C` sẽ không kết luận được.

## 3. Ba chi phí năng lực (chiều rẻ)

| Case | Tình huống | Cơ chế thiếu |
|---|---|---|
| `R.paraphrase.01` | Hỏi `"hạn chót nộp báo cáo"` về card viết `"deadline báo cáo"`, **cùng ngày, đúng** → từ chối | Không có khái niệm tương đương từ vựng |
| `N.corrected.01` | Card hai mốc, **sửa một mốc**; claim nêu **giá trị mới đã sửa** → từ chối | `_CORRECTION_FORWARD` cho về hưu **mọi** clause đứng trước dấu hiệu sửa, không riêng clause **cùng event key** |
| `N.corrected.02` | Cùng card, claim về mốc **correction không hề chạm tới** → cũng từ chối | Cùng cơ chế |

`N.corrected.*` đáng chú ý: **sửa một dòng của ghi chú làm im luôn các dòng
khác**. Một ghi chú đã được sửa một lần — tức hình dạng bình thường của ghi chú
đã sửa — **không trả lời được gì**.

## 4. Ứng viên normalization — đã đo, **chưa áp dụng**

Đo ngoài production path bằng cách rebind global trong test; `answerability.py`
**không đổi một dòng nào**. Tái lập được: `tests/test_normalisation_study.py`.

| Ứng viên | Quy tắc | Corpus 51 case | Hard negative | Kết luận |
|---|---|---|---|---|
| **R1** | Thôi bỏ token một ký tự | Đóng `Y.letter.01`, không mở lỗ nào | **Từ chối `"Theo ý mình thì…"` và `"À ngân sách…"`** (baseline trả lời) | ❌ **Loại** |
| **R1b** | Nhận token một ký tự **chỉ khi token trước nó là từ chỉ nhãn** | Đóng `Y.letter.01`, không mở lỗ nào | Giữ nguyên các câu khẩu ngữ; đóng thêm `"Mục A"/"Mục B"` | ✅ **[ĐỀ XUẤT]** |
| **R2** | Bảng đồng nghĩa `hạn`/`chốt` → `deadline` | **Tốt hơn hẳn: 3→2 ở cả hai chiều** | **10/10** compound `hạn`/`chốt` chuyển từ **từ chối** sang **trả lời** | ❌ **Loại** |

**Sửa lại tuyên bố của chính tôi.** Bản trước của memo này viết *"R2 không giảm
false answer, nó dời false answer đi"*. **Sai như đã viết**, và một review độc lập
bắt được: **trên corpus R2 tốt hơn hẳn** — 3→2 false answer **và** 3→2 false
abstention, **không** case nào trên corpus xấu đi.

Thứ thật sự loại R2 nằm **ngoài** corpus, và chỉ trở nên dứt khoát khi đo **cả
lớp** thay vì một instance: `hạn` và `chốt` là âm tiết **sinh sản**, nên gộp
chúng về `deadline` biến **10 trên 10** compound thử nghiệm — `hạn mức`,
`hạn chế`, `thời hạn`, `gia hạn`, `quá hạn`, `hết hạn`, `giới hạn`, `hạn ngạch`,
`chốt sổ`, `chốt giá` — từ **từ chối** thành **trả lời**. R2 mua 2 thắng lợi trên
corpus bằng cái giá là **cả một lớp từ**, và corpus **không thể** hiện cái giá đó
vì nó chứa **đúng một** compound `hạn`.

**Kết luận sống, lý lẽ thì không** — và đây đúng là bài học *"đo cả lớp, đừng đo
một instance"* mà dự án đã ghi.

**R1 bị loại bởi một dự đoán cũ, và dự đoán đó đúng một nửa.** Ghi chú tại
`tests/test_answerability_evidence.py:469` đã cảnh báo nới token rule sẽ "đưa
`_NUMBER` và subject matcher một vấn đề tệ hơn nhiều". Đo ra:

- **Đúng** về subject matcher: `ý`, `à` fold thành một ký tự, nên dưới R1 một
  tiểu từ mà card không có sẽ **phá phép chứa subject**. ASR output đầy những
  từ này, nên chi phí rơi **đúng chỗ dữ liệu vào nằm**.
- **Sai** về `_NUMBER`: giá trị bị lột **trước** khi tokenise, nên tập token
  được nhận **không thể** chứa chữ số. Đã kiểm.

**R1b là quy tắc theo vị trí, không phải nới tập token**, và nó là **liên kết
AND**: một từ chỉ nhãn đứng một mình không đổi gì, nên `"an toàn"` không bị
ảnh hưởng trong khi `"phương án B"` giữ được `B`.

### Trade-off của R1b trên TOÀN LỚP (bổ sung 2026-10-10)

R2 bị loại chỉ sau khi đo **cả lớp**; R1b được đề xuất mà chỉ dựa trên **một**
case corpus cộng ba hard negative. Nền bằng chứng không cân, nên đã đo lại R1b
theo đúng cách đã đo R2.

**Lớp lợi ích — 8 từ chỉ nhãn × 3 cặp chữ liên tiếp = 24 case**, giá trị giữ
**y nguyên** nên chỉ designator khác:

| | Kết quả |
|---|---|
| Baseline **trả lời** (sai) | **24/24** — mỗi câu là một phát ngôn rằng **phương án sai** đã được duyệt |
| R1b **từ chối** | **24/24** |
| Baseline trả lời mà R1b **vẫn** trả lời | **0** |

Từ chỉ nhãn đã đo: `Phương án`, `Mục`, `Nhóm`, `Loại`, `Cấp`, `Phiên`, `Kiểu`,
`Bản`.

**Lớp chi phí — từ khẩu ngữ fold thành một ký tự:** `ý`, `à`, `ờ`, `ạ`, `ừ`.
**R1b làm mất 0 câu trả lời.** Lý do **cấu trúc**, không may mắn: R1b nhận token
một ký tự **chỉ khi token trước nó là từ chỉ nhãn**, và một tiểu từ **không bao
giờ** đứng sau một từ chỉ nhãn — nên nửa AND của quy tắc **không với tới** chúng.
Đây đúng chỗ **R1 thất bại**: R1 nhận **mọi** token một ký tự nên nó từ chối
`"theo ý mình thì…"` và `"à ngân sách…"`.

**Và nửa AND được kiểm riêng:** `an toàn`, `mục tiêu`, `bản kế hoạch`, `cấp
trên`, `loại hình dịch vụ` — tokenise **y nguyên** như production. Nếu R1b bị
"đơn giản hoá" thành R1 sau này, phép kiểm đó **fail trước tiên**, và đó là sai
sót dễ xảy ra nhất ở đây.

**So sánh hai ứng viên trên cùng một thước đo:**

| | Lợi trên corpus | Lợi/chi phí **cả lớp** ngoài corpus | Kết luận |
|---|---|---|---|
| **R1b** | đóng 1 false answer | **đóng 24/24** designator, **chi phí 0/5** khẩu ngữ | ✅ **[ĐỀ XUẤT]** |
| **R2** | đóng 1 FA **+** 1 FAb — *tốt hơn R1b trên corpus* | **mất khả năng từ chối 10/10** compound `hạn`/`chốt` | ❌ **Loại** |

**Dòng này là toàn bộ bài học của lát:** nếu chỉ đọc cột corpus thì **R2 thắng**.
Cột thứ hai đảo kết luận, và nó chỉ xuất hiện khi đo **lớp** thay vì **case**.

**Vẫn chưa đo cho R1b:** `subject_tokens` **dùng chung với retrieval**, nên R1b
đổi cả **thứ hạng**. Toàn bộ suite chạy sạch dưới R1b (4773 pass, 2 fail đều là
ledger test khai hoả đúng thiết kế), nhưng suite **không** phải một phép đo chất
lượng xếp hạng. Và `_event_key` là một tokeniser **thứ hai** mà R1b **không**
chạm tới, nên lợi ích trên là lợi ích của một lần **áp dụng một phần**.

### Bằng chứng mutation cho R1b

Chạy **toàn bộ suite** với R1b cài lúc runtime: **4773 pass, đúng 2 fail**, và
cả hai là **invert-on-fix ledger test khai hoả đúng như thiết kế**:

1. `test_a_known_gap_still_disagrees[Y.letter.01]` — lỗ mới của lát này **đóng**.
2. `test_a_single_letter_option_label_over_refuses` — over-refusal **đã ghim từ
   trước** cũng **đóng**.

Tức hai hướng của **cùng một cơ chế**: một card thì claim đổi chữ designator →
**false answer**; hai card khác designator → **over-refusal giả**. R1b sửa cả
hai. Và việc `Y.letter.01` lật đúng khi đổi đúng cơ chế đó là bằng chứng case
này **đo cơ chế**, không đo chuyện ngẫu nhiên.

## 5. Cần Sơn chốt

**[CHỜ BẰNG CHỨNG] Acceptance criterion.** `subject_tokens` **dùng chung với
retrieval**, nên đổi nó đổi cả ranking. `AGENTS.md` yêu cầu đo trên bộ eval
**Sơn kiểm soát** trước khi một thay đổi lexicon/tokeniser được áp dụng, và
corpus này là **tôi tự viết** — nó không thay thế được bộ đó.

| Câu hỏi | Lựa chọn | Khuyến nghị |
|---|---|---|
| Áp dụng **R1b**? | (a) áp dụng ngay trên bằng chứng hiện có; (b) chờ bộ eval của Sơn; (c) không làm | **(b)** — bằng chứng thuận nhưng corpus là của tôi. Nếu Sơn muốn (a), tôi áp dụng kèm đảo hai ledger test, **không xoá** |
| Tiêu chí nhận | Số false answer/false abstention nào là đạt, trên bộ nào | Cần Sơn cho một bộ câu hỏi + card thật (đã duyệt) để đo |
| `Q.attribute.01` | So subject của claim với subject của **câu hỏi**? | **[ĐỀ XUẤT]** có, nhưng **chưa đo** — đây là lớp kiểm **mới**, không phải sửa tokeniser, và nó sẽ đẩy over-refusal lên. Cần một lát đo riêng |
| `N.corrected.*` | Giới hạn phạm vi correction theo **event key**? | **[ĐỀ XUẤT]** có. Cơ chế **đã có sẵn** (`_event_key`), đây là thu hẹp phạm vi một quy tắc quá rộng — chiều deny-biased không đổi |

**Không có ứng viên nào được áp dụng trong lát này.** Ba lỗ false answer vẫn
**mở** và nằm trong ledger với trần chỉ-được-hạ, cộng một test cho mỗi lỗ khẳng
định nó **vẫn bất đồng** — nên khi sửa, test **fail** và bảo tác giả xoá cờ,
thay vì cờ sống mãi thành lời bào chữa.


## 7. Bổ sung sau review độc lập — 9 đường false answer nữa

Ba review độc lập trên `9371fb0`. Tôi **tự tái lập từng case kèm control** trước
khi ghi; **cả ba report đều đúng**. Ghim ở
`tests/test_answerability_false_answers.py`, **không sửa gì**.

**Tổng cộng 12 đường false answer đã đo**, tất cả trả `supported` với findings
**rỗng** — không rule name để tra, không gì để log, không act nào cho authority
gate từ chối. **Một bug từ chối thì tự báo; những đường này im lặng theo cấu
trúc.**

| Gốc | Biểu hiện nặng nhất |
|---|---|
| **Phép chứa coi việc XOÁ là đồng ý** | `subject_tokens("Tài liệu đã được duyệt")` **rỗng** (mọi từ là stopword) và **∅ ⊆ mọi card** → được trả lời từ card về *quy trình tuyển dụng*. Cộng: bỏ `đề xuất` → một **đề xuất** phát thành ngân sách, dưới khung *"theo ghi chú đã duyệt"* |
| **Inheritance mang subject, không mang polarity** | `"Chi phí hạ tầng chưa chốt, ngân sách tổng đã duyệt là 240 triệu đồng."` → trả lời `"chi phí hạ tầng là 240 triệu đồng"`. **Đúng ví dụ mở đầu docstring của module**, cái được nói là đã đóng — đóng qua **dấu chấm**, mở qua **dấu phẩy** |
| **Ba lớp anchor là tất cả những gì có ai chịu trách nhiệm** | `"Sơn đồng ý phương án B, sau đó bác bỏ"` → phát thành **consent**. Và **tên người không căn cứ trong ANSWER** không bị tính |
| **Key token không thấy đồng nghĩa** | Kể cả **trong cùng một card**: hai ngày cho một sự việc không bị coi là mâu thuẫn |
| **Độ phủ tính cho CARD, không cho claim** | Card **nhắc tới** nửa sau câu hỏi là `PARTIAL_UNDECLARED` bị vô hiệu — **càng chắc** khi card tự nhận nửa đó **chưa chốt** |

**Hệ quả cho quyết định của Sơn ở mục 5:** R1b vẫn là **[ĐỀ XUẤT]** và vẫn đáng
làm, nhưng nó đóng **1 trong 12** đường. Nếu Sơn muốn ưu tiên theo mức nguy hiểm
thì **subject rỗng**, **`đề xuất`**, và **`từ chối`/`bác bỏ`** đứng trước — cái
cuối phát ra một **consent** mà Sơn đã rút lại.

## 6. Giới hạn của chính phép đo này

- **51 case tổng hợp, nội dung bịa, tôi tự viết.** Không phải dữ liệu họp thật.
- **Không nói gì về ASR, về model, hay về đường production.** Chỉ đo một hàm
  deterministic trên một mapping claim/evidence.
- **Hard negative cũng do tôi chọn.** Chúng bác được R1 và R2, nhưng một bộ do
  người khác viết sẽ bác được những thứ khác.
- **`_event_key` là tokeniser THỨ HAI**, quy tắc `len(token) > 1` riêng, **không**
  đi qua `subject_tokens`. Không ứng viên nào ở đây chạm tới nó, nên lợi ích đo
  được là lợi ích của một lần **áp dụng một phần**.
- **Chưa đo:** retrieval top-k sai/cũ, scope/audience, citation chọn lọc ở
  **cấp retrieval** (corpus này trao `cards` trực tiếp cho `assess`). Đó là lát
  riêng, và `scope`/`Sensitivity` vẫn **chưa enforce** dưới retrieval vì chỗ đặt
  phụ thuộc quyết định scope còn chờ.
