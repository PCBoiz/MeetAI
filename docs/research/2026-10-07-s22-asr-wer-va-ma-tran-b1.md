# S2.2 phần 2 — WER tiếng Việt, noise, và đối chiếu B-1

Đo 2026-10-07 (lượt 10). Mọi số do tôi chạy trên máy này. Tái lập:
`benchmarks/README.md`.

Phần 1 (co-residency + nhóm non-speech + scorer):
[tại đây](2026-10-07-s22-coresidency-va-hallucination.md).

---

## 0. Lượt nào hợp lệ, lượt nào bị loại

Minh bạch trước khi đưa số, vì phiên này có nhiều lượt bị hỏng.

| Lượt | Trạng thái | Lý do |
|---|---|---|
| FLEURS `asr-fleurs-small-gpu-20261007-210717.json` | **HỢP LỆ** | 361/361 clip, exit 0, 0 failure, lock `24456` giải phóng đúng |
| Noise `asr-fleurs-noise-gpu-20261007-215231.json` | **HỢP LỆ** | 120/120 clip, exit 0, 0 failure, lock giải phóng |
| Co-residency `coresidency-20261007-212808.json` | **HỢP LỆ** | ASR + LLM 0.5B, cả hai rc=0 |
| 2 lượt ASR chạy chồng nhau (~20:24–20:35) | **LOẠI** | hai `whisper-cli` cùng sống, tranh GPU → mọi số latency/RTF vô giá trị |
| `coresidency-20261007-202049.json` | **LOẠI** | rc=-1 do **tôi kill tay**, không phải phép đo |
| `coresidency-20261007-194935.json` | **GIỮ, THIẾU BẰNG CHỨNG** | cả hai process chết nhưng **chưa có stderr capture** ở thời điểm đó |
| Interim SyER 26.0% ở n=49 | **KHÔNG PHẢI KẾT QUẢ** | chỉ số tiến độ |

**Bằng chứng process cho lượt FLEURS hợp lệ:** shell 21344 → trampoline uv
24292 → interpreter **24456** → đúng một `whisper-cli` (ppid=24456). Lock giữ
24456, khớp. Trampoline và interpreter là **một lượt logic** — `ppid` của
interpreter là trampoline, nên hai dòng cùng command line **không** phải hai
lượt.

---

## 1. Hợp đồng đo

`syer.v1.nfc.punct-to-space.case-sensitive.no-fold`

| Thành phần | Định nghĩa |
|---|---|
| **SyER** | `(S+D+I)/N`, **micro-average** (tổng lỗi / tổng token), **không** phải trung bình các tỷ lệ từng câu |
| Token | **âm tiết** = token phân tách bằng dấu cách. Tiếng Việt viết âm tiết cách nhau bằng dấu cách, nên token whitespace **không** phải từ. VLSP dùng Syllable Error Rate đúng vì lý do đó. |
| **CER** | ký tự NFC, **tính cả dấu cách** (khai rõ; loại dấu cách sẽ che lỗi ranh giới âm tiết) |
| **IER** | `I/N`, tách riêng vì insertion là lớp liên quan an toàn |
| Chuẩn hoá | NFC → control/separator → dấu câu & symbol **thành dấu cách** (không phải rỗng) → gộp khoảng trắng |
| **Không** làm | fold dấu, fold case, đổi số↔chữ, giãn viết tắt |
| folded | **chỉ diagnostic**; đại lượng có nghĩa là **gap** so với headline |
| CI | **bootstrap theo utterance**, seed **7** — không phải Wilson (SyER không phải tỷ lệ, có thể >1, và lỗi cụm trong utterance) |
| Failure | timeout / OOM / output rỗng / lỗi process → **mọi token reference tính là deletion**, denominator **không đổi** |
| Bất đối xứng | reference **rỗng** + hypothesis rỗng là **đáp án đúng**, không phải failure |

**`SyER > 1` là hợp lệ**, không phải lỗi: insertion không chặn trên. Đo được
2.00 trên một repetition loop tổng hợp. Đó cũng là lý do `Rate` của
`meetai.evaluation` **không** dùng được cho SyER (nó raise), còn vẫn dùng đúng
cho các count failure.

### 1.1 NFC: bắt buộc, nhưng **no-op cho đúng corpus này**

| | NFC sẵn | cần NFC |
|---|---|---|
| 361 reference FLEURS | **361** | 0 |
| 361 hypothesis whisper | **361** | 0 |

Con số **SyER 0.875** tôi từng nêu là trên một **case NFD dựng thủ công**, và
nó **không mô tả lượt chạy này**. Nó biện minh cho việc *giữ* bước NFC (không
phía nào bảo đảm dạng), chứ không phải công lao với kết quả ở đây.

---

## 2. FLEURS `vi_vn` dev — nhánh PERMISSIVE

Dataset `google/fleurs`, **CC-BY-4.0**, ungated, revision
`70bb2e84b976b7e960aa89f1c648e09c59f894dd`.
`dev.tar.gz` SHA-256 `8821a394c990…`, `dev.tsv` SHA-256 `c9bc17cede97…`.
Model `ggml-small.bin` SHA-256 `1be3a9b2063867b9…` (MIT).
Runtime whisper.cpp `b5454` commit `d1be6fde11ac…`, zip SHA-256 `afef0b881c50…`.
Artifact SHA-256 `e10c832c3e3f…`.

**Denominator: 361 clip / N = 10 422 âm tiết / 4 299.5 s audio.** Dataset card
ghi **415**; tôi đếm được **361** (TSV đúng 361 dòng 7 cột, tar đúng 361 wav,
cả 361 khớp theo `file_name`) — **card sai**. Reference lấy từ **cột 2**
(`raw_transcription`, có hoa/thường và dấu câu).

### 2.1 Headline

| Chỉ số | Giá trị |
|---|---|
| S / D / I / N | 2152 / 151 / 143 / 10 422 |
| **SyER** | **23.47%**  CI95 **[22.05, 25.08]** |
| IER | 1.37% |
| CER | 11.23% |
| folded *(diagnostic)* | 17.85% → **gap +5.62 pp** |
| Failure | **0** (timeout 0, OOM 0, output rỗng 0, lỗi process 0) |

**Gap +5.62 pp là kết quả phương pháp quan trọng nhất ở đây:** fold dấu sẽ báo
**17.85%** thay vì **23.47%** — đẹp hơn 5.6 điểm, và che đúng lớp lỗi thanh điệu
dự án quan tâm. Chính sách không-fold vừa tự chứng minh bằng số.

### 2.2 Ba đường tính độc lập khớp tuyệt đối

| Đường | S | D | I | N |
|---|---|---|---|---|
| summary của runner | 2152 | 151 | 143 | 10 422 |
| tổng counts **từng clip** trong artifact | 2152 | 151 | 143 | 10 422 |
| postprocessor **tính lại từ TSV** | 2152 | 151 | 143 | 10 422 |

SyER tính tay: **23.47%**. Và `N = 10 422` được **dự đoán trước khi chạy
postprocessor**, nên đây là kiểm chéo thật cho việc ghép TSV↔artifact.

### 2.3 RTF — báo **cả hai cách tổng hợp**

| Cách | Giá trị |
|---|---|
| **ratio-of-totals** (tổng wall / tổng audio) | **0.315** |
| mean-of-per-clip-ratios | **0.346** |
| p50 / p95 của RTF từng clip | 0.331 / 0.534 |
| min–max | 0.142–0.708 |
| wall p50 / p95 | 3.661 s / 4.775 s (tổng 1352.9 s) |

Hai số khác nhau vì clip ngắn có chi phí load model cố định chiếm tỷ lệ lớn
hơn. Trích một số rồi gọi chung là "RTF" sẽ che mất câu hỏi nào đang được trả
lời — cùng lý do SyER là micro-average chứ không phải trung bình các tỷ lệ.

**RTF < 1 chỉ nói về đúng phép đo CLI tuần tự này**, và **đã bao gồm load model
mỗi clip**. Nó **không** chứng minh streaming, **không** phải latency
đầu-cuối, và **không** nói gì về mốc 1–2 giây.

### 2.4 Theo lớp — và hai giới hạn phải đọc kèm

| Lớp | N | S | D | I | biên nhập nhằng | rate |
|---|---|---|---|---|---|---|
| date | 114 | 19 | 12 | 2 | 3 | 28.95% |
| number | 522 | 152 | 14 | 0 | 27 | 31.80% |
| **proper_noun** | **768** | **499** | 32 | 11 | 61 | **70.57%** |

**Giới hạn 1 — đây là heuristic, không phải nhãn vàng.** `proper_noun` gán bằng
**hoa/thường**, không phải annotation thủ công. Tên riêng tiếng Việt là danh từ
thường (`Thu` mùa thu, `Hoa` hoa, `Minh` sáng, `Lan` lan), nên hoa/thường là
tín hiệu duy nhất ở mức text; **token đầu câu không bao giờ được gán** nên
denominator **đếm thiếu** tên thật. Con số trộn **lỗi nhận dạng** với **lỗi gán
lớp**. Insertion ở biên span đếm **riêng** (61) vì không quyết được bên nào sở
hữu.

**Giới hạn 2 — chỉ 13.5% token được gán lớp** (1404 / 10 422). Bảng này mô tả
một phần nhỏ của corpus.

Nên 70.57% là **tín hiệu rủi ro** cần điều tra, **không** phải WER tên riêng.
Nó **không** đủ để kết luận model dùng được hay không dùng được cho MeetAI:
FLEURS là văn bản tin/wiki, không phải tên người trong cuộc họp, và muốn kết
luận cần **bộ tên gán nhãn thủ công trong bối cảnh họp**.

---

## 3. Noise — phép thử **tổng hợp có kiểm soát**

**Gọi đúng tên:** white noise cộng thêm, sinh bằng LCG seed **1234567**, trộn
vào chính audio FLEURS. Đây **không** phải tiếng ồn phòng họp thật: không có
hình phổ phòng, **không có vang**, và **không liên quan tới nói chồng**. Nó
đóng trục *noise* của B-1 ở dạng **có kiểm soát**, không phải dạng **thực tế**.

License: **CC-BY-4.0** (phái sinh từ `google/fleurs`) → vẫn nhánh permissive.

Kiểm chứng sinh dữ liệu: SNR đo **20.04 / 10.03 / 5.02 dB** so với target
20/10/5 (lệch ≤ 0.04 dB), **không clipping**, 16 kHz mono, 40 utterance × 3 mức
= **120 clip**, 0 failure.

### 3.1 So sánh **theo cặp** — cùng 40 utterance

**Comparator là baseline paired trên đúng 40 utterance đó (SyER 25.66%), không
phải số toàn corpus 23.47%.** Subset này khó hơn trung bình, nên so với 23.47%
sẽ **thổi phồng** hình phạt của noise thêm ~2.2 pp.

| Điều kiện | n | N | S | D | I | SyER | IER | CER |
|---|---|---|---|---|---|---|---|---|
| **clean (paired)** | 40 | 1056 | 232 | 19 | 20 | **25.66%** | 1.89% | 11.68% |
| SNR 20 dB | 40 | 1056 | 243 | 20 | 22 | 26.99% | 2.08% | 12.71% |
| SNR 10 dB | 40 | 1056 | 297 | 20 | 24 | 32.29% | 2.27% | 16.24% |
| SNR 5 dB | 40 | 1056 | 412 | 23 | 32 | 44.22% | 3.03% | 24.63% |

### 3.2 Chênh lệch theo cặp, bootstrap **hiệu số**

So sánh khoảng tin cậy **lề** của hai điều kiện trên dữ liệu paired là
**thiếu lực**. Cách đúng: resample utterance, tính **lại cả hai** điều kiện
trên cùng resample, rồi lấy hiệu. Seed 7, 4000 replicate, n=40.

| Điều kiện | ΔSyER | CI95 của **hiệu số** | Phân biệt được với 0? |
|---|---|---|---|
| SNR 20 dB | **+1.33 pp** | [−0.39, +3.05] | **chưa phát hiện được** |
| SNR 10 dB | **+6.63 pp** | [+4.00, +9.33] | có |
| SNR 5 dB | **+18.56 pp** | [+14.95, +22.23] | có |

**Ở 20 dB: chưa phát hiện được suy giảm trong dữ liệu này; CI của hiệu số bao
gồm 0.** Đó **không** phải bằng chứng rằng noise ở 20 dB không có ảnh hưởng —
với n=40 và CI rộng tới +3.05 pp, một ảnh hưởng nhỏ hoàn toàn có thể tồn tại mà
phép đo này không thấy. Phân biệt hai câu đó là quan trọng: "chưa phát hiện" nói
về **độ mạnh của phép đo**, "không có ảnh hưởng" nói về **thế giới**, và tôi chỉ
đo được cái thứ nhất.

Nếu chỉ so khoảng tin cậy **lề** thì sẽ dễ kết luận sai rằng đã phát hiện được.
Suy giảm trở thành phát hiện được ở 10 dB và lớn ở 5 dB.

---

## 4. Ma trận B-1 — đối chiếu từng trục

Nghĩa vụ `spec.md` B-1: *"WER/CER theo accent/noise/nói chồng/tên riêng, RTF,
VRAM/RAM peak, p50/p95"*.

| Trục | Dữ liệu | Kết quả | Giới hạn | Trạng thái |
|---|---|---|---|---|
| **WER/CER** | FLEURS vi_vn dev, 361 clip, N=10 422 | SyER **23.47%** [22.05, 25.08], CER **11.23%**, IER 1.37%, 0 failure | **Đọc câu, một người nói mỗi clip.** Không đại diện hội thoại tự nhiên. | **đạt** (cho đọc câu) |
| **noise** | FLEURS + white noise tổng hợp, 3 mức SNR, 120 clip | Δ theo cặp: 20 dB **không phân biệt được**, 10 dB **+6.63 pp**, 5 dB **+18.56 pp** | **Tổng hợp**, không có hình phổ phòng, **không vang** | **đạt cho noise tổng hợp có kiểm soát**; **noise thực tế: `not demonstrated`** |
| **tên riêng** | heuristic hoa/thường trên FLEURS | 70.57% trên N=768 | **Heuristic, không phải nhãn vàng.** Token đầu câu không gán; trộn lỗi nhận dạng với lỗi gán lớp; chỉ 13.5% token được gán lớp; FLEURS là tin/wiki chứ không phải tên người trong họp | **`not demonstrated`** — có tín hiệu rủi ro, **chưa** có phép đo trên nhãn thủ công |
| **nói chồng** | **không có** | — | FLEURS và VIVOS **đều** là đọc câu một người. Không corpus nào trong phạm vi lát này chứa tiếng nói chồng. | **`absent`** |
| **accent** | FLEURS: **không nhãn**. VietMed: **có nhãn**, đã chạy thăm dò (421 clip, 5 nhóm, 8 kHz, y tế) | SyER theo nhóm 38.0–57.6%, pooled 46.0% | **Accent lồng gần hoàn toàn với speaker và điều kiện thu**: cả test split chỉ **27 speaker**, hai nhóm có **1 và 2** speaker, và CI của nhóm 1-speaker **sụp thành một điểm**. Một số theo-nhóm-speaker không phải phép đo accent. | **`not demonstrated`** — có số thăm dò, **không** đóng trục |
| **RTF** | 361 clip | ratio-of-totals **0.315**; mean-of-ratios 0.346; p50 0.331 / p95 0.534 | Bao gồm load model mỗi clip. **Tuần tự CLI, không phải streaming.** | **đạt** (cho lời gọi tuần tự) |
| **VRAM/RAM peak** | S2.1 + S2.2 | LLM 4B +2865 MiB / RAM WS 2794 MiB; ASR +900 MiB; ASR+0.5B đồng thời 1862 MiB | **Peak là chặn dưới** (sampling 200–300 ms). Per-process VRAM **không tồn tại** dưới WDDM. | **đạt một phần** — có số, nhưng là chặn dưới |
| **p50/p95** | RTF và wall mỗi clip, n=361 | RTF p50 0.331 / p95 0.534; wall p50 3.661 s / p95 4.775 s | Đây là p50/p95 của **lời gọi CLI mỗi clip**, **không** phải "endpoint-to-final-ASR" hay "LLM first token" hay "end-to-end" mà spec nêu. | **`not demonstrated`** cho ba chỉ số spec nêu |
| **co-residency ASR+LLM** | 5 lần thử | **0.5B, đúng cấu hình đã đo, trong đúng lần đo đó:** cùng hiện diện trên GPU (1862 MiB, cả hai rc=0, 2371/2390 mẫu có cả hai), **và ASR chậm 527×** (2204 → 1 161 714 ms). **Không** suy rộng sang model khác hay sang production. 4B: 2/5 lần có stderr đều `cudaMalloc` fail | Chênh lệch peak/free/request **chưa giải thích được**; power cap 40 W là điều kiện phần cứng, **không** phải nguyên nhân đã chứng minh | 0.5B **đồng thời đạt trong lần đo đó**, throughput **không dùng được**; 4B **`chưa chứng minh`** |

**Mốc 1–2 giây: không tuyên bố gì.** Chưa đo pipeline đầu-cuối nào.

---

## 3A. Accent — phép thử **thăm dò** trên VietMed, và vì sao nó KHÔNG đóng trục

Sơn duyệt VietMed **chỉ như một đánh giá thăm dò**, kèm cảnh báo không coi nó là
bằng chứng bao phủ accent tiếng Việt nói chung. Kết quả dưới đây xác nhận cảnh
báo đó, với lý do mạnh hơn tôi dự kiến.

**Nguồn:** `leduckhai/VietMed`, revision `cc7980cd1392…`, license tag **MIT**
(paper ghi CC BY 4.0 → **[CHỜ BẰNG CHỨNG]**, mâu thuẫn chưa giải quyết).
Ungated. Chỉ tải subset test (**69.3 MB**), giữ ngoài Git.

⚠️ **Tag MIT không phải một cuộc audit quyền.** Nó phủ phần đóng góp của tác
giả; audio gốc thu từ nguồn công khai theo lập luận fair-use. Đánh giá cục bộ là
mức dùng nhẹ nhất; **không phát hành lại gì**.

### Hai thứ tôi đo, không tin theo tài liệu

| Claim | Kết quả |
|---|---|
| 8 kHz | **XÁC NHẬN** — đọc Vorbis identification header: **8000 Hz mono, 500/500 file** |
| Định dạng transcript | **Khảo sát SAI.** Không phải `<id> <text>`; là **list literal Python các dict**. Parse bằng `ast.literal_eval`, **không** `eval` — dữ liệu bên thứ ba không được thực thi. |
| Định dạng audio | **OGG/Vorbis**, không phải WAV. `whisper-cli` đọc được qua miniaudio (đã thử). |

**8 kHz là lý do đầu tiên số này không so được với FLEURS 16 kHz.** Băng tần
điện thoại là một điều kiện âm học khác. Đây là **benchmark riêng**, không phải
một slice của lần chạy FLEURS.

### Số đo (thăm dò)

whisper-small, `-l vi`, 421 clip, **0 failure**. CI bootstrap **block theo
speaker**, seed 7.

| accent | n | **speakers** | N | S | D | I | SyER | CER | CI95 |
|---|---|---|---|---|---|---|---|---|---|
| South East | 100 | 6 | 2219 | 375 | 324 | 144 | **38.0%** | 28.0% | [33.5, 41.5] |
| South West | 100 | 12 | 2360 | 427 | 436 | 154 | 43.1% | 33.2% | [38.6, 48.5] |
| North | 100 | 6 | 2231 | 406 | 488 | 86 | 43.9% | 34.3% | [38.2, 50.1] |
| South Central Coast | 100 | **2** | 2222 | 683 | 432 | 164 | **57.6%** | 41.6% | [52.2, 64.8] |
| North Central Coast | 21 | **1** | 355 | 114 | 38 | 44 | 55.2% | 40.4% | **[55.2, 55.2]** |
| **POOLED** | 421 | 27 | 9387 | 2005 | 1718 | 592 | **46.0%** | 34.5% | |

folded (diagnostic) 40.8% → **gap +5.1 pp**, cùng hướng với FLEURS (+5.62 pp).

**Deletion cao bất thường** (1718 trên 9387 token, so với 151/10422 ở FLEURS) —
đặc trưng của băng tần điện thoại cộng tiếng nói tự nhiên: model bỏ hẳn nhiều
đoạn thay vì nghe sai.

**Khoảng tin cậy của North Central Coast sụp thành một điểm `[55.2, 55.2]`** —
vì block theo speaker mà nhóm chỉ có **một** speaker, nên mọi lần resample đều ra
đúng block đó. Bootstrap đang **nói đúng** rằng ở đó **không có thông tin suy
diễn nào**, thay vì bịa ra một bề rộng nghe hợp lý. Đây là chỗ việc chọn block
theo speaker trả công.

### Vì sao đây **KHÔNG** phải phép đo accent

Trục accent của VietMed **lồng gần như hoàn toàn** với speaker và điều kiện thu:

| accent | speakers | điều kiện thu có mặt |
|---|---|---|
| North | 6 | Tel 84, Talkshow 16 |
| South Central Coast | **2** | Lectures 50, Consultation 50 |
| South East | 6 | News 66, Podcast 17, Diagnosis 17 |
| South West | 12 | Talkshow 76, Podcast/Diagnosis/News 8 mỗi loại |
| North Central Coast | **1** | Lectures 21 |

**Toàn bộ test split chỉ có 27 speaker**, và **lấy cả 3437 utterance không cứu
được** — số speaker là số speaker, thêm utterance không thêm người.

Nên `South Central Coast 57.6%` so với `South East 38.0%` **không** đọc được
thành "giọng Nam Trung Bộ khó hơn giọng Đông Nam Bộ". Nó tương thích hoàn toàn
với "hai người nói cụ thể đó khó hơn", và với "Lectures+Consultation khó hơn
News+Podcast". **Ba cách đọc không tách được** trên dữ liệu này.

**Một lỗi sampling của tôi, tự phát hiện và sửa.** Lần đầu tôi lấy prefix liên
tiếp; vì utterance sắp theo speaker nên mỗi nhóm accent rơi vào **đúng một** điều
kiện thu (Tel 100 / Lectures 121 / Podcast 100 / Talkshow 100). Bảng dựng trên đó
sẽ so điều kiện thu nhiều hơn so accent. Đã đổi sang **round-robin theo speaker**
(vẫn tất định, không cần seed) → trải cả 7 điều kiện. Confound **giảm nhưng không
hết**, nên cross-tab ở trên được in ra thay vì để ngầm.

### Kết luận về trục accent

**Giữ `not demonstrated`.** Một con số theo-nhóm-speaker không phải phép đo
accent, và `spec.md` B-1 hỏi về accent.

Phép thử này vẫn **có giá trị**, và giá trị không nằm ở con số: nó cho biết cấu
trúc VietMed **không cho phép** đóng trục accent — điều chỉ đọc dataset card thì
không thấy. Biết một con đường không dẫn tới đâu là một kết quả.

Giới hạn khác, đã ghi trong manifest: domain **y tế** lệch khỏi MeetAI; nhãn
accent là **cảm nhận của annotator** và chính tác giả nói họ **không chia nổi**
subregion miền Bắc nên `North` là rổ thô; **overlap có trong VietMed nhưng không
được gán nhãn**, nên nó là confound không kiểm soát bên trong các ô accent.

---

## 4A. p50/p95 và phụ thuộc A14 — vì sao không đo được bây giờ

**A14 đã được chốt là hoãn:** *"Chưa chốt, để S3 quyết"*. Tôi **không** hỏi lại.
Nhưng hệ quả cần ghi thành traceability chứ không để ngầm.

`spec.md` B-1 yêu cầu p50/p95 cho **ba** đại lượng:
`endpoint-to-final-ASR`, `LLM first token`, `end-to-end`. Cả ba là độ trễ của
một **pipeline**, và hình dạng pipeline chính là thứ A14 còn hoãn:

| Đường A14 | p50/p95 sẽ đo cái gì |
|---|---|
| in-process binding | không có IPC, không listener; độ trễ là lời gọi hàm |
| llama.cpp server trên loopback | thêm JSON + TCP loopback + scheduler + continuous batching của server |

Hai kiến trúc cho **hai phân phối độ trễ khác nhau**, nên một con số đo bây giờ
sẽ thuộc một kiến trúc chưa được chọn.

**Những số CLI hiện có KHÔNG thay thế được chúng.** RTF p50 0.331 / p95 0.534 và
wall p50 3.661 s / p95 4.775 s là độ trễ của **một lời gọi `whisper-cli` cho một
clip**, đã gồm **load model mỗi clip**. Không có LLM trong đó, không có
endpointing, không có bàn giao giữa hai tầng. Gọi chúng là p50/p95 của pipeline
sẽ là đổi tên một thứ khác.

**Và tôi sẽ không dựng một pipeline tạm để lấy số.** Một pipeline tạm sẽ đo
chính nó, rồi con số đó sẽ bị trích dẫn như bằng chứng về production — đúng kiểu
drift mà A14 đặt ba điều kiện để tránh. Nên trạng thái là **`not demonstrated`,
phụ thuộc A14 / S3**, ghi rõ trong ma trận.

---

## 5. VIVOS — cân nhắc và **không dùng**

`plan.md` **không yêu cầu** VIVOS; A13 chỉ quy định *cách xử lý* nếu dùng tài
nguyên NC. Đối chiếu B-1 ở trên: VIVOS là **đọc câu, một người nói mỗi clip**,
nên nó **không đóng được trục nào đang thiếu** (`nói chồng` vẫn `absent`,
`accent` vẫn thiếu nhãn). Nó chỉ thêm một số đọc-câu thứ hai, mà số đó lại
mang nghĩa vụ **CC BY-NC-SA** — **ShareAlike lan truyền**, và đó là lý do mạnh
hơn cả riêng tư để reference text không vào git.

**Quyết định: không tải.** Không tải chỉ để benchmark lớn hơn. Nếu sau này cần
VIVOS để đối chiếu với PhoWhisper (corpus mà PhoWhisper **đã huấn luyện trên**),
thì chạy riêng, tách nhãn NC, kèm hai caveat A13.

---

## 5A. Kiểm chứng chéo: mọi số trong file này đối chiếu với artifact

Chạy một pass đối chiếu **26 con số** được nêu trong file này với giá trị trong
artifact JSON tương ứng (`asr-fleurs-small-gpu-20261007-210717.json` và bản
`-derived`, `paired-clean-baseline.json`, `coresidency-20261007-212808.json`).

**Kết quả: 0 sai lệch.**

Pass đó cũng tìm ra một **lỗ hổng traceability thật**: con số RTF
**0.315** từng xuất hiện trong báo cáo nhưng **không có trong artifact nào** —
nó đến từ một phép tính tay trong lúc audit, vì bản `-derived` được sinh **trước**
khi tôi sửa postprocessor để báo cả hai cách tổng hợp. Đã sinh lại artifact nên
cả `aggregate_total_wall_over_total_audio` (0.3147) và
`mean_of_per_clip_ratios` (0.3464) đều **truy được về file**. Một số trong báo
cáo mà không có artifact đỡ thì không khác gì một số tôi nhớ.

---

## 6. Giới hạn tổng hợp — những gì phần này KHÔNG chứng minh

- **23.47% không nói gì về hội thoại tự nhiên.** FLEURS là đọc câu.
- **RTF < 1 không chứng minh streaming** và không nói gì về mốc 1–2 giây.
- **70.57% không phải WER tên riêng gán nhãn vàng** và không kết luận được
  model dùng được hay không cho MeetAI.
- **Noise tổng hợp không thay thế noise thực tế**; không có vang, không có
  nói chồng.
- **Nói chồng `absent`**, **accent `absent`** (thiếu nhãn).
- **p50/p95 của ba chỉ số spec nêu: `not demonstrated`.**
- **Peak VRAM/RAM là chặn dưới**, và per-process VRAM không đo được dưới WDDM.
- **Co-residency 4B `chưa chứng minh`** — có allocation thất bại, nhưng chênh
  lệch peak/free/request chưa giải thích được.
- Gate **0-S / 0-P / 0-C / 0-U** vẫn **OPEN**. A14 (đường inference production)
  **chưa chốt**, và lát này không chốt hộ.
- Không suy diễn gì về Discord voice receive.
