---
title: "Các lựa chọn cần Sơn chốt — gom một lượt"
date: 2026-10-09
status: "[CHỜ SƠN]"
---

# Các lựa chọn cần Sơn chốt

Lập 2026-10-09 (lượt 21). **Không có quyết định nào trong tài liệu này.** Mọi ô
"khuyến nghị" là **[ĐỀ XUẤT]**; thứ đang chạy trong code là **[GIẢ ĐỊNH]**
fail-closed và giữ nguyên tới khi Sơn trả lời.

**Gate 0-S / 0-P / 0-C / 0-U vẫn mở. S2.2 và S2.3 vẫn `partial/open`.**

## Những điều đã chốt — không hỏi lại

Tra trước khi viết tài liệu này:

- **Không ghi âm.** *"Mặc định không ghi âm/lưu âm thanh cuộc họp. Trường hợp
  ngoại lệ phải thông báo rõ"* — hồ sơ v1.0. Nên **không hỏi** "có muốn ghi âm
  không".
- **Muốn có dữ liệu để dùng.** *"Fine-tune model mở và RAG là hướng mong muốn
  khi có dữ liệu phù hợp"* — hồ sơ v1.0. Nên **không hỏi** "có muốn lưu gì
  không". Câu còn lại là **lưu cái gì, và xoá thế nào**.
- **`scope` đến từ session, không bao giờ từ câu hỏi** — ADR 0007 addendum 4.
- **`PRIVATE` không tự thành nội dung `GROUP`** — có test `D11` ghim.
- **Trả lời một phần** — `[CHỐT] Sơn 2026-10-08`.
- **`rationale` không phải evidence** — đã thành bất biến có test ở lượt 19.
  Mục 5 dưới đây chỉ xin **xác nhận**, không hỏi lại.
- **Không có phân quyền giữa người dùng** — *"Một người, một máy"*,
  `docs/intent.md:21`. Nên không có mục nào bên dưới nhờ Sơn phát minh một mô
  hình quyền.

---

## 1. Gate 0-U: consent mode — A1 và A3 khác nhau thế nào trong code

Cả hai **đã xây xong** sau một interface, mặc định đóng. Đây là việc **chọn**,
không phải việc **xây**.

| | **A1 — circuit breaker** | **A3 — admission control** |
|---|---|---|
| Khi có người vào muộn | `gate.close()` **và** chạy mọi cancellation callback | `gate.close()`, **không** cancel |
| `reason` trả về | `circuit_breaker_tripped` | `awaiting_admission` |
| Công việc đang bay | bị **huỷ** | **không** bị huỷ, chỉ không nhận frame mới |
| Ý nghĩa | *tháo cả pipeline* — rời họp và chặn reconnect là việc của adapter | *người mới chờ ngoài* cho tới khi host cho vào |
| Chi phí khi sai | mất phiên đang chạy | người mới bị kẹt nếu host không để ý |
| Cả hai giống nhau ở | **gate đóng**, người mới **không được cấp gì**, và frame của người **đã** đồng ý **cũng dừng** | |

Dòng cuối là điều đáng chú ý nhất: fail-closed nghĩa là **cả phiên dừng**,
không phải chỉ người mới bị tắt tiếng — vì gate là theo phiên, và audio chưa
được đồng ý trong phòng vẫn là audio chưa được đồng ý. Có test exhaustive trên
cả ba giá trị enum.

**Hai câu con cần Sơn trả lời:**

1. **A1 hay A3?**
2. **Consent xin của host hay của từng người?** (`§4B B1`) — và nếu một người
   **không trả lời**, đó là từ chối hay chờ? Hiện là fail-closed: không trả
   lời = không nhận media.

**[ĐỀ XUẤT]** A3, và consent **từng người**. Lý do: A3 mất ít hơn khi đoán sai,
và hồ sơ đã chốt *"Host không được ghi đè opt-out của participant"* — nên
per-person là hướng đã ngả sẵn. **Không tự chọn.**

---

## 2. Persistence: lưu cái gì, và xoá thế nào

Audio **không lưu** — đã chốt, không hỏi lại. Câu hỏi là ba loại còn lại.

| Loại | Là gì | Hiện tại | Câu hỏi |
|---|---|---|---|
| **Transcript** | văn bản lời nói trong họp | OFF, rào tự từ chối khi đặt True | Lưu không? Nếu có thì **toàn bộ** hay chỉ đoạn MeetAI đã dùng? |
| **Card / ghi chú Sơn đã duyệt** | knowledge card — thứ RAG cần | OFF | Lưu không? Đây là loại **duy nhất** mà hồ sơ đã ngả về phía "muốn có" |
| **Metadata vận hành** | consent receipt, số đếm, lý do từ chối — **không có nội dung** | OFF | Lưu không, và bao lâu? |

**[ĐỀ XUẤT]**, để Sơn gạch bỏ hoặc sửa:

- **Card đã duyệt: LƯU, không hết hạn.** Đó là thứ Sơn duyệt từng cái và là
  thân tri thức RAG cần. Xoá bằng tay, và đã có `reject`/`edit`/`supersede` +
  cascade xoá mọi thứ dẫn xuất.
- **Transcript: KHÔNG lưu.** Nếu cần, chỉ lưu **đoạn đã được dẫn vào một card
  đã duyệt** — khi đó nó là nguồn của card, không phải một bản ghi cuộc họp.
- **Metadata: LƯU, có hạn.** Nó là thứ duy nhất trả lời được *"vì sao MeetAI im
  lặng lúc đó"*, và nó không mang nội dung.

---

## 3. Retention wording — câu thông báo, xin Sơn duyệt

**[ĐỀ XUẤT]** câu ngắn, tiếng Việt, nói đúng những gì làm được:

> *"Tôi là trợ lý AI của Sơn. Tôi **không ghi âm** cuộc họp. Tôi có thể ghi lại
> ý chính dưới dạng ghi chú để Sơn xem và duyệt; chỉ phần Sơn duyệt được giữ
> lại. Ai không muốn tôi xử lý tiếng của mình thì nói, tôi sẽ dừng."*

Thời hạn tương ứng, **[ĐỀ XUẤT]**:

| Loại | Thời hạn | Vì sao |
|---|---|---|
| Âm thanh | **không lưu** | đã chốt |
| Transcript thô | **không lưu** (hoặc trong phiên rồi bỏ) | mục 2 |
| Card đã duyệt | **tới khi Sơn xoá** | Sơn đã duyệt từng cái |
| Consent receipt | **đề xuất 90 ngày** | đủ để trả lời "ai đã đồng ý gì, lúc nào" |
| Metadata vận hành | **đề xuất 30 ngày** | đủ để chẩn đoán một phiên |

Hai con số 90/30 là **[ĐỀ XUẤT] chưa có căn cứ** — tôi không có cơ sở nào để
chọn chúng ngoài "đủ dùng". Xin Sơn sửa.

---

## 4. Session scope — chỉ phần còn thiếu

**Đã chốt:** scope đến từ session, không từ câu hỏi. **Còn thiếu:** session lấy
scope từ đâu.

| | Nguồn | Được | Mất |
|---|---|---|---|
| **S1** | operator **chọn tay** mỗi phiên | không cần connector, không suy diễn. **Chạy được ngay — đây là [GIẢ ĐỊNH] đang chạy** | một bước tay mỗi họp; chọn sai thì trả lời bằng tri thức dự án khác |
| **S2** | **Calendar event** | tự động; hồ sơ đã chốt Calendar là nguồn lịch | cần OAuth app — **tác động ra ngoài, cần Sơn xác nhận trước**. Và event không gắn dự án thì rơi về đâu? |
| **S3** | **channel Discord** | có sẵn khi đã có adapter | **chặn bởi 0-S/0-P/0-C**, không khảo sát được bây giờ |

**Câu con dùng được nhất: một cuộc họp có gắn với một project không, và gắn bằng
gì?** Repo **không có gì** cho câu này — không `project_id`, không quy tắc từ
người tham gia sang scope, và tên người tham gia **cố ý giữ ngoài repo**.

**[ĐỀ XUẤT] mặc định không kế thừa**: nếu không có mapping rõ, **không kế thừa
scope project hay global**. MeetAI vẫn nói được bằng năng lực ngôn ngữ của model
và meeting context; nó chỉ không dẫn card riêng của Sơn. Đó là một lần im lặng,
còn kế thừa sai là một con số sai trong họp.

---

## 5. Hai câu hỏi riêng

### 5a. `rationale` luôn luôn không phải evidence?

**Đã thành bất biến có test ở lượt 19**, và khuyến nghị hiện tại là **không**
bao giờ coi nó là evidence. Lý do: `claim` là thứ Sơn duyệt từng câu;
`rationale` là văn bản tự do không review nào chứng kiến như một khẳng định —
và đã đo được rationale mang được chỉ thị tiêm.

Chỉ xin **xác nhận**. Nếu Sơn muốn khác, nó mở lại một đường false-answer nên
cần nói rõ.

### 5b. Có cho một lượt benchmark GPU đơn lẻ không?

**Chưa chạy, và sẽ không chạy trước khi Sơn trả lời.**

Trạng thái preflight hôm nay:

| Điều kiện | Trạng thái |
|---|---|
| VRAM gate | **có** — 4228 MiB, từ peak đã ghi × 1.5 |
| RAM gate | **có** — 3380 MiB, peak 2868 + 512 **cộng** (không nhân) |
| Fail-closed khi không đo được | **có** |
| Lock vào trước preflight | **có** |
| Kiểm GPU đã giải phóng sau mỗi case | **có**, nhưng tolerance 256 MiB **không thấy** leak nhỏ hơn |
| `failure_evidence` được ghi | **có code, có test bằng mock**, **chưa có** một failure thật nào được bắt cùng nó |
| Đỉnh cấp phát nhất thời | **chưa ai đo** — chỉ đo **qua hệ quả** |

**[ĐỀ XUẤT]: chưa chạy.** Hai điều kiện trong bảng còn hở, và cái thứ hai là
đúng thứ một lần chạy sẽ cần tới. Nếu Sơn muốn chạy, tôi đề nghị **một case**,
không phải 43, để mục đích là *bắt một failure kèm bằng chứng* chứ không phải
lấy lại số.

---

## 6. Những mục khác đang chờ Sơn — liệt kê để không bỏ sót

Không cần trả lời bây giờ.

- **§4B B1–B10** — cả mười mục.
- **MeetAI được gọi bằng gì** — alias registry rỗng cố ý.
- **Consent TTL** — mặc định `None`, **[ĐỀ XUẤT]**.
- **Calendar OAuth app** (`M-7`) — tác động ra ngoài, cần xác nhận trước.
- **`evidence` truthiness** — `" "`, `"TODO"`, `"n/a"` hiện **đều** thoả
  "có evidence". Sửa là **thay đổi hành vi**, nên **không** làm ở lượt này.
- **`BlockedDiscordAdapter.leave()` raise** trái hợp đồng `ControlPlane.leave`
  (*"must be safe to call when not joined"*), và **có test ghim việc raise**.
  Sửa kiểu nào cũng đảo một assertion hoặc làm yếu một hợp đồng.
  **[ĐỀ XUẤT]** cho `leave()` im lặng trả về — nó là động từ **dọn dẹp**, và
  một adapter bị chặn thì chưa từng join, nên "bạn không ở trong channel" đã là
  sự thật.
- **Permit cho media sink: ba mục chưa quyết** — registration tiêu thụ
  `ConsentScope` nào; permit có chết khi **revoke** (không chỉ khi close) không;
  một phiên **không có** sink đăng ký là lỗi hay bình thường. Hiện lấy vị trí
  **hẹp nhất rõ ràng đúng**: permit chết cùng gate, không khẳng định gì thêm.
- **Sensitivity theo field hay theo card** — hồ sơ nói field-level, code làm
  card-level.
- **Chỗ đặt phép kiểm scope** — ba tài liệu nói ba chỗ.
- **Mở rộng matcher tên platform** — hiện khớp **đúng token**, nên
  `"discord-real"`, `"Discord Bot"` qua được như synthetic. **[ĐỀ XUẤT] không
  mở rộng**: không có phép đo nào đỡ một lexicon rộng hơn.

---

## 8. Bổ sung lượt 22 — một quyết định giờ đã có số để quyết

Trước lượt 22 mọi mục ở trên là *chờ Sơn chọn chính sách*. Mục này khác: nó là
một thay đổi kỹ thuật **đã đo xong trade-off**, nên Sơn quyết trên số thật chứ
không phải trên lời hứa.

### 8a. Có áp dụng **R1b** không?

**Vấn đề nó đóng.** Card nói **phương án B** đã duyệt 240 triệu; câu trả lời
nói **phương án C** đã duyệt 240 triệu → MeetAI **trả lời**, findings rỗng.
Mọi lớp khác qua **trung thực**: card đã duyệt, còn hạn, đúng subject, con số
dẫn **đúng**. Token phân biệt hai phương án dài **một ký tự**, và tokeniser bỏ
token một ký tự như rác.

Đây là **một lớp**, không phải một câu bất thường: `"Mục A"` vs `"Mục B"` cũng
được trả lời. Còn `"Phương án 2"` vs `"Phương án 3"` **bị từ chối** — nhưng bởi
cơ chế **khác** (chữ số bị lột như *giá trị*). Nên hiện tại **độ an toàn phụ
thuộc designator viết bằng chữ hay bằng số**.

**R1b là gì.** Nhận token một ký tự **chỉ khi token đứng trước nó là từ chỉ
nhãn** (`phương án`, `mục`, `nhóm`, `loại`…). Quy tắc **theo vị trí**, không
phải nới tập token, và **liên kết AND** — nên `"an toàn"` không bị ảnh hưởng
trong khi `"phương án B"` giữ được `B`.

| | Hệ quả |
|---|---|
| **(a) Áp dụng R1b** | Đóng `Y.letter.01` **và** một over-refusal đã ghim từ trước (hai card khác phương án bị đọc thành mâu thuẫn). Toàn bộ suite: **4773 pass, đúng 2 fail**, cả hai là ledger test khai hoả đúng thiết kế. **Rủi ro còn lại:** `subject_tokens` **dùng chung với retrieval**, nên nó đổi cả ranking; corpus đo điều này là **tôi tự viết** |
| **(b) Chờ bộ eval của Sơn** — **[ĐỀ XUẤT]** | Không nhận thêm rủi ro nào. Giá phải trả: false answer `Y.letter.01` **vẫn mở**, và nó là loại false answer **không có dấu hiệu gì** cho người nghe |
| **(c) Không làm** | Phải chấp nhận false answer về **"cái nào được duyệt"** là hành vi lâu dài |

**Khuyến nghị (b)**, nhưng xin nói thẳng lý do khuyến nghị **không** mạnh: bằng
chứng **thuận** R1b và tôi không tìm được chi phí nào của nó. Thứ tôi thiếu là
**quyền** chứ không phải số — `AGENTS.md` yêu cầu đo trên bộ eval Sơn kiểm soát
trước khi đổi tokeniser, và corpus tôi tự viết **không** thay thế bộ đó. Nếu
Sơn chọn (a), tôi áp dụng kèm **đảo** hai ledger test chứ không xoá.

**Nếu Sơn muốn làm (b) cho nhanh:** cần **một bộ nhỏ** — chừng 20–30 câu hỏi
thật kèm card đã duyệt tương ứng, Sơn tự gán nhãn nên-trả-lời / nên-im. Không
cần audio, không cần transcript, không cần nội dung họp thật nếu Sơn muốn bịa
nội dung — thứ cần là **nhãn do Sơn đặt**, vì đó chính là điều corpus của tôi
không có.

### 8b. Hai mục KHÔNG hỏi, ghi để Sơn biết là tôi đã cân nhắc

- **`R2` (bảng đồng nghĩa `hạn`/`chốt` → `deadline`)**: tôi **tự loại** bằng
  phép đo, không đưa lên thành câu hỏi. Nó đóng cả hai case paraphrase, nhưng
  **tạo ra một false answer mới**: trả lời câu hỏi về `hạn chót nộp báo cáo`
  (mốc thời gian) bằng card về `hạn mức báo cáo` (giới hạn), **kèm một ngày**.
  Không có phương án nào của nó đáng để Sơn phải đọc.
- **`N.corrected.*`** (sửa một mốc làm im cả card): **[ĐỀ XUẤT]** thu hẹp phạm
  vi correction theo `_event_key`. Cơ chế **đã có sẵn**, chiều deny-biased
  **không đổi**, nên tôi coi là **sửa lỗi** chứ không phải đổi chính sách — sẽ
  làm ở lát sau mà **không** cần Sơn duyệt, trừ khi Sơn muốn xem trước.

## 7. Lát này không chờ câu trả lời nào

Phần đã làm xong và **không** phụ thuộc mục nào ở trên: permit cho media sink
(fail-closed dưới cấu hình mặc định thật), allowlist import chặn
`discord`/`av`/`pyaudio`/`torch`, một biểu thức giao frame duy nhất, chặn khởi
tạo lúc import, divergence report có scope và có audience, và ba fix adapter
thuần.

**Bổ sung lượt 22:** corpus answerability 36 → **51 case** (3 false answer, 3 false abstention, tất cả vào ledger), đo **3 ứng viên normalization ngoài production path** và **loại 2 bằng phép đo**, ghim mù ordinal ở retrieval. **Không áp dụng ứng viên nào**, **không đổi flag config nào**, và `answerability.py` **không đổi một dòng**.
