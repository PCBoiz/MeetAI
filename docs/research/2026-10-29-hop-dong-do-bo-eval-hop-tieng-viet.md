---
title: "D2 — Hợp đồng đo cho bộ eval cuộc họp tiếng Việt"
status: "[ĐỀ XUẤT] — viết TRƯỚC khi có dữ liệu, theo đúng thứ tự S2.2 đã dùng"
created: "2026-10-29"
purpose: "Trả lời: cần bao nhiêu audio, gán nhãn thế nào, và một con số đo được ra sẽ có nghĩa gì — trước khi thu một giây nào."
scope: "Nghiên cứu chỉ đọc. Không chạy model, không thu âm, không tải dữ liệu, không thêm dependency."
---

# D2 — Hợp đồng đo cho bộ eval cuộc họp tiếng Việt

> **Vì sao viết trước.** Một hợp đồng đo viết **sau** khi nhìn thấy dữ liệu sẽ bị
> uốn theo dữ liệu đang có. Repo đã đi đúng thứ tự này ở S2.2 và nó **cứu được một
> kết luận**: chính sách **không khử dấu** tự chứng minh bằng khoảng lệch
> **+5,62 điểm phần trăm** — nếu chọn cách chuẩn hoá sau khi thấy số, rất dễ chọn
> cái đẹp hơn.

---

## 0. Trạng thái ba trở ngại, sau khi Sơn trả lời

Ghi chú dữ liệu cùng ngày *(bản đầy đủ giữ **cục bộ**, không công khai, theo
**[CHỐT]** của Sơn 2026-10-29)* nêu ba trở ngại độc lập. Sau phát ngôn của Sơn (2026-10-29):

| # | Trở ngại | Trạng thái |
|---|---|---|
| (b) | Đồng thuận của người nói trong băng | **[CHỐT] ĐÃ GIẢI QUYẾT.** Sơn xác nhận người trong băng là **cộng tác viên của Sơn** và **đã đồng thuận**. Đây là quyết định của Sơn về cộng tác viên của Sơn; ghi nhận, không hỏi lại |
| (a) | Điều khoản YouTube cấm tải xuống | **GIẢI QUYẾT ĐƯỢC — bằng đường chính thức**, xem §1. Không cần công cụ bên thứ ba |
| (c) | Không có nhãn thì không đo được | **CÒN NGUYÊN, và nay là toàn bộ bài toán.** Đồng thuận không tạo ra transcript |

**[CHỜ SƠN] Hai câu hỏi làm rõ, không chặn việc nghiên cứu:**

1. Playlist đó có phải do **chính kênh của Sơn đăng** không? Quyết định §1 đi nhánh
   nào.
2. Trong các cuộc họp đó, ngoài cộng tác viên đã đồng thuận, **còn người nào khác
   nói** không? Nếu có thì đồng thuận cần phủ cả họ — đây là cùng một nguyên tắc
   `(phiên, người, phạm vi, phiên bản thông báo)` mà dự án đã dùng, không phải một
   rào mới.

---

## 1. Lấy file về: có đường chính thức, và nó tốt hơn công cụ bên thứ ba

**[ĐÃ ĐO] `support.google.com/youtube/answer/56100`, truy cập 2026-10-29** —
trang *"Download YouTube videos that you've uploaded"*:

- **YouTube Studio** cho tải **MP4** video **do chính mình đăng**, ở **720p hoặc
  360p** tuỳ kích thước; giới hạn **5 lần/video/24 giờ**.
- **Google Takeout** cho tải **hàng loạt** mọi video mình đã đăng.
- **Không** tải được video của người khác; không tải được video bị gỡ, bị gậy bản
  quyền/Community Guidelines, hoặc dùng nhạc preapproved.

Đây đúng là nhánh *"trừ khi được Dịch vụ cho phép"* trong Điều khoản. **Nếu
playlist là của kênh Sơn, trở ngại (a) biến mất hoàn toàn** — và không cần công cụ
bên thứ ba nào.

### 1.1 Nhưng xếp hạng nguồn audio theo chất lượng, vì nó là một confound thật

| Hạng | Nguồn | Vì sao |
|---|---|---|
| **1** | **File ghi gốc** (nếu Sơn còn giữ) | Chưa qua nén lần hai. Đây là thứ đúng để đo |
| **2** | **Google Takeout** | Tải hàng loạt; **[CHỜ BẰNG CHỨNG]** liệu có giữ bitstream gốc — trang hỗ trợ **không nói**. Đo được: xem codec/sample rate/bitrate của file xuất ra |
| **3** | **YouTube Studio 720p/360p** | Trang **nói thẳng** là 720p hoặc 360p ⇒ **audio đã được mã hoá lại** (lossy, có thể đổi sample rate) |

**Vì sao điều này không phải chuyện vặt:** nếu đo ASR trên audio đã qua YouTube
transcode, con số thu được là *"model này nhận dạng **audio đã nén lại** tốt đến
đâu"*, không phải *"model này nhận dạng **cuộc họp của Sơn** tốt đến đâu"*. Hai câu
khác nhau, và MeetAI chạy trên cái thứ hai.

**[ĐỀ XUẤT] Quy tắc:** mỗi clip trong bộ eval **phải ghi `audio_provenance`** —
`original` / `takeout` / `studio-720p` / `studio-360p`. Nếu bộ eval trộn nhiều
nguồn, mọi số phải **tách theo nguồn**, đúng cách repo đã tách nhánh license
permissive khỏi nhánh non-commercial.

---

## 2. Cần bao nhiêu audio — tính ra, không đoán

**[ĐÃ ĐO] Neo trên chính artifact của repo**
(`var/asr/results/asr-fleurs-small-gpu-20261007-210717.json`): 361 phát ngôn,
**10 422 âm tiết**, **71,7 phút** speech, SyER **23,47%**. Bootstrap tái lập lại
được khoảng tin cậy đã ghi trong artifact (**3,04 pp** so với **3,03 pp** đã lưu),
nên phép tính dưới đây dùng đúng cỗ máy đã được kiểm chứng.

Coi 361 clip đó là tổng thể, resample để hỏi: **một bộ eval cỡ n sẽ cho độ chính
xác nào?**

### 2.1 Đo tuyệt đối — "SyER của hệ thống là bao nhiêu"

| n phát ngôn | ~phút speech | CI95 nửa-rộng |
|---:|---:|---:|
| 40 | 8′ | **± 4,46 pp** |
| 80 | 16′ | ± 3,16 pp |
| 160 | 32′ | ± 2,26 pp |
| 240 | 48′ | ± 1,86 pp |
| **361** | **72′** | **± 1,51 pp** |
| 720 | 143′ | ± 1,07 pp |
| 1 200 | 238′ | ± 0,82 pp |

### 2.2 So sánh theo cặp — "sửa cái này có giúp không"

Neo: thí nghiệm nhiễu của repo, **n = 40**, bootstrap **trên hiệu số**, CI nửa-rộng
đo được **1,72 pp**. Quy mô theo `1/√n`:

| n phát ngôn | ~phút speech | Δ nhỏ nhất phân biệt được với 0 |
|---:|---:|---:|
| 40 | 8′ | ≥ 1,72 pp |
| 80 | 16′ | ≥ 1,22 pp |
| **160** | **32′** | **≥ 0,86 pp** |
| 240 | 48′ | ≥ 0,70 pp |
| 361 | 72′ | ≥ 0,57 pp |

### 2.3 Kết quả quan trọng nhất của mục này

> **So sánh theo cặp rẻ hơn đo tuyệt đối khoảng 2,6 lần.** Ở n = 361: đo tuyệt đối
> cho ± 1,51 pp, nhưng so theo cặp phát hiện được Δ ≥ 0,57 pp. Vì phép so theo cặp
> **khử** phương sai giữa các phát ngôn — cùng audio, chỉ đổi hệ thống.

Hệ quả thực tế, và nó đổi cách tiêu công sức:

- Muốn **công bố** "SyER họp tiếng Việt của MeetAI là X%" ⇒ cần ~**72 phút speech**
  cho ± 1,5 pp.
- Muốn **quyết định** "fine-tune/đổi model có giúp không" ⇒ chỉ cần ~**32 phút
  speech**, so theo cặp, là phát hiện được chênh lệch ≥ 0,86 pp.

**Và thứ MeetAI cần trước là cái thứ hai.** Không cần một con số để khoe; cần một
cái cân đủ nhạy để biết một thay đổi có cải thiện không.

### 2.4 Ba giới hạn của bảng trên — phải đọc kèm

1. **Neo là FLEURS: speech ĐỌC, 11,9 s/phát ngôn, 28,9 âm tiết/phát ngôn.** Lượt
   thoại trong họp thường **ngắn hơn và vụn hơn**. Cùng số phút, họp sẽ cho **nhiều
   phát ngôn hơn nhưng ít âm tiết mỗi phát ngôn hơn** — hai hướng ngược nhau, và
   **không ai biết biên độ**. Nên đọc bảng này là **bậc độ lớn**, không phải bảo
   đảm.
2. **SyER của họp gần như chắc chắn CAO HƠN 23,47%** (nói tự phát, nói chồng, mic
   xa). CI nở theo tỷ lệ lỗi, nên các con số trên là **lạc quan**.
3. **Quy mô `1/√n` ở §2.2 là phép SUY RA, không phải phép đo.** Chỉ điểm n = 40 là
   đo thật; phần còn lại là ngoại suy từ một điểm. **[CHỜ BẰNG CHỨNG]** cho tới khi
   có bộ thật để bootstrap lại.

### 2.5 Quy ra giờ ghi âm thô

Một cuộc họp không phải 100% speech chấm được: có im lặng, nói chồng, tiếng không
phải lời. **[GIẢ ĐỊNH]** 50–65% thời lượng là speech đơn-người chấm được —
**con số này chưa đo trên dữ liệu của Sơn** và phải đo lại ngay khi có clip đầu
tiên.

| Mục tiêu | Speech cần | ⇒ Giờ ghi thô **[GIẢ ĐỊNH]** |
|---|---:|---:|
| Cân đủ nhạy để quyết định (Δ ≥ 0,86 pp, theo cặp) | 32′ | **~1 giờ** |
| Công bố một con số ± 1,5 pp | 72′ | **~2 – 2,5 giờ** |
| Thêm biên cho các trục phụ (§4) | +50% | **~3 – 4 giờ** |

**Nên "2–5 giờ" nói ở lượt trước nay có cơ sở tính toán, không còn là trực giác.**

---

## 3. Transcript — nút thắt thật, và một cái bẫy phải đo

Đồng thuận không tạo ra nhãn. Đây là phần tốn công nhất và là nơi dễ tự lừa nhất.

### 3.1 Ba cách làm, và cái giá của từng cách

| Cách | Tốc độ **[GIẢ ĐỊNH]** | Vấn đề |
|---|---|---|
| Gõ từ đầu, không nhìn ASR | ~5–10× realtime | Đắt: 72′ speech ⇒ **6–12 giờ** công |
| **Sửa đầu ra ASR** | ~2–4× realtime | **Thiên lệch** — xem §3.2 |
| Nhận phụ đề tự động làm nhãn | ~0 | **Không phải nhãn.** Đo model A bằng đầu ra model B |

### 3.2 Cái bẫy: sửa đầu ra ASR làm nhãn **thiên về chính model đó**

Khi người sửa nhìn đầu ra của Whisper rồi chỉnh, họ sẽ sửa những chỗ **sai rõ** và
**bỏ qua những chỗ sai nhưng nghe hợp lý** — đặc biệt với thanh điệu tiếng Việt,
nơi một âm sai dấu vẫn tạo ra một từ có thật.

Hệ quả: đo **chính Whisper** trên bộ nhãn đã sửa từ Whisper sẽ **báo SyER thấp hơn
thật**. Và đó đúng là lớp lỗi dự án quan tâm — repo đã đo được rằng khử dấu che mất
**+5,62 pp**.

Đây **không** phải lo xa: repo đã ghi một tiền lệ cùng hình dạng ở quyết định
**A13** — PhoWhisper **có dùng VIVOS trong dữ liệu huấn luyện**, nên điểm trên
VIVOS test *"đo trí nhớ nhiều hơn"*.

### 3.3 [ĐỀ XUẤT] Cách đo chính cái thiên lệch đó, thay vì giả vờ nó không có

Không cấm sửa-từ-ASR — nó rẻ hơn 2–3 lần và với vài giờ audio thì đó là khác biệt
giữa làm được và không. Thay vào đó, **đo nó**:

1. Chọn ngẫu nhiên **~15–20 phút speech** (≈ 80 phát ngôn), **seed ghi lại**.
2. Gõ nhóm đó **từ đầu, mù** — người gõ **không được xem** đầu ra ASR.
3. Phần còn lại: sửa-từ-ASR như bình thường.
4. **So theo cặp trên đúng nhóm mù đó**: SyER đo bằng nhãn-mù so với SyER đo bằng
   nhãn-đã-sửa. **Hiệu số đó chính là độ thiên lệch.**

**Vì sao đúng 80 phát ngôn:** theo §2.2, n = 80 theo cặp phát hiện được Δ ≥ 1,22 pp.
Thiên lệch nhỏ hơn 1,22 pp thì **không phát hiện được với cỡ này** — và câu đúng
phải viết ra là *"chưa phát hiện được"*, **không** phải *"không có"*. Repo đã nhấn
đúng phân biệt này ở thí nghiệm nhiễu 20 dB.

**Nếu thiên lệch đo được là đáng kể:** báo cáo mọi SyER kèm **hai con số** — đo trên
nhãn-đã-sửa, và đo trên nhóm-mù — chứ không chọn một.

---

## 4. Gán nhãn gì, và nó đóng được trục nào trong `spec.md`

| Nhãn | Công sức | Đóng được gì |
|---|---|---|
| **Transcript có dấu, không khử dấu** | nút thắt chính | Trục **SyER/CER** cho **miền họp** — trục duy nhất hiện có số, nhưng trên **speech đọc** |
| **Ranh giới lượt + ai nói** | rẻ nếu chỉ 2 người | Tiền đề cho mọi thứ còn lại; và là thứ cổng **0-S** cần (ánh xạ luồng → người nói) |
| **Khoảng nói chồng (bắt đầu/kết thúc)** | trung bình | Trục **nói chồng**, đang `absent`. **Lần đầu có số tiếng Việt** nếu làm đúng |
| **Tên riêng trong ngữ cảnh họp** | trung bình | Trục **tên riêng**, đang `not demonstrated`. Repo đo FLEURS **70,57%** nhưng tự ghi đó là *"tín hiệu rủi ro, KHÔNG phải tỷ lệ lỗi tên riêng"* vì nhãn gán bằng hoa/thường và chỉ **13,5%** token được gán lớp. **Nhãn thủ công trong bối cảnh họp đúng là thứ còn thiếu** |
| **Số / ngày / giờ** | rẻ | FLEURS đo 31,80% / 28,95% — đáng đối chiếu, và đây là lớp MeetAI hay phải trả lời đúng |
| **`rec_condition`** (mic, phòng, gần/xa) | rẻ, ghi lúc thu | Tách *"model kém"* khỏi *"điều kiện thu kém"*. VietMed có trường này và nó hữu ích |
| **`audio_provenance`** (§1.1) | rẻ | Chặn confound YouTube transcode |

### 4.1 Ngân sách cho trục nói chồng — nó mỏng, nói trước

**[GIẢ ĐỊNH]** Nói chồng trong họp thật thường **5–15%** thời lượng. Với 72′ speech
⇒ **4–11 phút** có nói chồng ⇒ **~20–55 phát ngôn**. Theo §2.1, n = 40 cho
**± 4,46 pp**.

**Nên trục nói chồng sẽ có số, nhưng là số RỘNG.** Viết điều này ra **trước** quan
trọng, vì sau khi thấy một CI ± 4 pp thì rất dễ bị cám dỗ gộp nó vào con số tổng
cho đẹp — mà repo **cố ý không có số tổng**, và có kiểm thử ghim điều đó.

---

## 5. Hợp đồng đo — chốt trước khi thu

Kế thừa nguyên văn hợp đồng S2.2, vì đổi nó sẽ làm mọi số cũ không so được:

```
syer.v1.nfc.punct-to-space.case-sensitive.no-fold
```

| Thành phần | Quy định |
|---|---|
| Đơn vị lỗi | **âm tiết** (token phân tách bằng dấu cách) |
| Chỉ số chính | **SyER = (S+D+I)/N**, **micro-average** — tổng lỗi / tổng token, **không** phải trung bình các tỷ lệ |
| Chuẩn hoá | NFC → control/separator → dấu câu & symbol **thành dấu cách** → gộp khoảng trắng |
| **Không** làm | **khử dấu**, fold case, đổi số↔chữ, giãn viết tắt |
| Khử dấu | **chỉ diagnostic**; đại lượng có nghĩa là **khoảng lệch** so với headline |
| CI | **bootstrap theo phát ngôn**, seed **7**; so sánh hai hệ thống thì bootstrap **trên hiệu số** |
| Failure | timeout / hết bộ nhớ / output rỗng / lỗi process ⇒ **mọi token reference tính là deletion**, mẫu số **không đổi** |
| Bất đối xứng | reference rỗng + hypothesis rỗng = **đúng**, không phải failure |
| `SyER > 1` | **hợp lệ** — phép chèn không có chặn trên |

**Thêm ba điều riêng cho bộ họp:**

1. **Mẫu số công bố theo nhóm, không có một số tổng.** Mỗi trục có mẫu số của chính
   nó, kèm nguồn audio.
2. **Mọi số kèm `audio_provenance`.** Trộn nguồn thì tách số.
3. **Số trên nhãn-đã-sửa và số trên nhóm-mù báo CẢ HAI** nếu §3.3 đo được thiên
   lệch.

---

## 6. Cái này mở khoá gì, và KHÔNG mở khoá gì

**Mở khoá:**

- Một cái cân. Hôm nay **không có cách nào** biết một thay đổi có cải thiện nhận
  dạng tiếng Việt trong họp không — vì không có bộ đo nào thuộc miền đó.
- Trục **nói chồng** (`absent`) và **tên riêng** (`not demonstrated`) có đường tiến,
  lần đầu.
- Một tiền đề của **0-S**: nhãn ai-nói-lượt-nào là chính thứ cổng đó đòi.

**KHÔNG mở khoá — nói thẳng:**

- **Không** mở cổng cấp B. Bốn cổng đó về **chạy** model; bộ eval không chạm tới.
- **Không** mở cổng cấp C. Bộ eval không nói gì về route nhận audio của nền tảng.
- **Không** biến fine-tune thành bước kế tiếp. Nó cho **cái cân**; cân trước, sửa
  sau.
- **Không** thay 16 nhãn eval đang **[CHỜ SƠN]**. Đó là bộ đo **quyền hạn**; cái này
  đo **nhận dạng**. Hai thứ khác nhau, không thay nhau được.
- **Không** tự cho phép thu âm gì. D1 (giao thức ghi âm có đồng thuận) vẫn là một
  phần cổng **0-U**.

---

## 7. Bước kế tiếp, xếp theo thứ tự

| # | Việc | Ai | Chặn bởi |
|---|---|---|---|
| 1 | Trả lời hai câu §0: playlist có phải của kênh Sơn; có người thứ ba nói không | **Sơn** | — |
| 2 | Nếu còn **file ghi gốc** thì dùng nó; nếu không, xuất bằng **Takeout** và **đo codec/sample rate/bitrate** của file nhận được | Sơn | (1) |
| 3 | **Đo tỷ lệ speech/giờ** trên một cuộc họp, để thay **[GIẢ ĐỊNH]** 50–65% ở §2.5 bằng số thật | tác nhân kỹ thuật | (2) |
| 4 | Gán nhãn **lô đầu ~30 phút speech**, kèm nhóm mù ~15′ của §3.3 | Sơn + tác nhân | (3) |
| 5 | Chạy hợp đồng đo §5 trên lô đầu; báo **CI**, **thiên lệch**, và **tỷ lệ nói chồng thật** | tác nhân | (4) + cổng cấp B cho mọi phép chạy có model |

**Vì sao dừng ở lô ~30 phút trước:** đó đã đủ cho **cái cân so theo cặp** (§2.2,
Δ ≥ 0,86 pp), và nó trả lời ba **[GIẢ ĐỊNH]** của ghi chú này bằng số thật — tỷ lệ
speech, độ dài lượt thoại, tỷ lệ nói chồng — **trước khi** Sơn bỏ 6–12 giờ công gán
nhãn cho bộ đầy đủ.

---

## 8. Nguồn

| Nguồn | Ngày truy cập | Kết luận nó đỡ |
|---|---|---|
| `support.google.com/youtube/answer/56100` — *Download YouTube videos that you've uploaded* | **2026-10-29** | Studio cho tải MP4 **720p/360p** video của chính mình, 5 lần/24 h; **Takeout** tải hàng loạt; không tải được video người khác — §1 |
| `var/asr/results/asr-fleurs-small-gpu-20261007-210717.json` (361 clip, per-clip counts) | — | Neo cho §2; bootstrap tái lập CI đã ghi (**3,04** vs **3,03 pp**) |
| `…-derived.json` → `denominators.audio_seconds = 4299.5` | — | Quy phát ngôn ra phút speech — §2.1 |
| [S2.2 phần 2 — WER, nhiễu, ma trận B-1](2026-10-07-s22-asr-wer-va-ma-tran-b1.md) | — | Hợp đồng đo §5; neo **n=40 ⇒ ±1,72 pp** theo cặp; khoảng lệch khử dấu **+5,62 pp**; giới hạn nhãn tên riêng |
| [Khảo sát corpus nói chồng](2026-10-07-overlapping-speech-corpora.md) | — | Vì sao không corpus sẵn nào đóng được trục này — §6 |
| `PROJECT_STATE.md` A13 | — | Tiền lệ "model đã thấy dữ liệu test thì đo trí nhớ" — §3.2 |
