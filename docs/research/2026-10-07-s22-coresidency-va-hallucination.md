# S2.2 phần 1 — co-residency và hallucination trên nền không có tiếng nói

Đo 2026-10-07 (lượt 9). Mọi số do tôi chạy trên máy này. Tái lập:
`benchmarks/README.md`.

**Thứ tự theo đúng acceptance criteria: co-residency trước, WER sau.** File này
là phần co-residency cộng nhóm non-speech. Số WER trên FLEURS nằm ở phần 2.

---

## 1. Môi trường

Giống S2.1, không đổi gì ở mức hệ thống: GTX 1660 Ti 6144 MiB (compute 7.5,
**không tensor core**), driver 610.62, **enforced power limit 40 W trên card
80 W**, memory clock 810 MHz trên 6001 MHz. Baseline VRAM idle **786–855 MiB**
vì GPU đang chạy desktop.

**ASR runtime mới:** whisper.cpp build `b5454` (commit
`d1be6fde11ac6e0407606b4e42fe72d34add8037`), asset
`whisper-bin-win-cuda-12.4.0-x64.zip`, SHA-256
`afef0b881c500958921c3f5523b50e59ee2ec9b6f5cbd25b324c51ed308a957a`.

Hai điểm khác llama.cpp, đã verify bằng cách mở zip:

- Nó **bundle sẵn** `cudart64_12.dll`, `cublas64_12.dll`, `cublasLt64_12.dll`,
  nên **không cần** gói PyPI của NVIDIA như đường llama.cpp đã cần.
- Nó ship **9 biến thể `ggml-cpu-*`** và dispatch lúc chạy; trên máy này chọn
  `ggml-cpu-haswell.dll`.

**Không thêm dependency Python nào.** `pyproject.toml` và `uv.lock` không đổi.

### 1.1 Một quan sát về sm_75 giải thích con số đầu tiên trông sai

Lần chạy whisper đầu tiên có `encode time = 18813 ms` cho 5 giây audio; các lần
sau là **~1000 ms**. Không phải lỗi, cũng không phụ thuộc clip: build CUDA của
whisper.cpp ship `75-virtual` (PTX) chứ không phải cubin cho Turing, nên
**driver JIT-compile lần đầu** rồi cache lại. Cold run vì vậy **không** được
trộn với warm run.

---

## 2. Co-residency: **KHÔNG đạt**

### 2.1 Phương pháp, và điều Windows không cho phép đo

**Per-process VRAM không tồn tại trên máy này.**
`nvidia-smi --query-compute-apps=used_memory` trả `[N/A]` cho **mọi** process
dưới WDDM, và `nvidia-smi -q -d PIDS` nói thẳng
*"Used GPU Memory : Not available in WDDM driver model"*. Nên không thể quy VRAM
cho từng process.

Danh sách process **thì đo được**, nên tính đồng thời vẫn chứng minh được dù
tính quy thuộc thì không. Harness đòi ba bằng chứng:

1. cả hai process xuất hiện trong **cùng một mẫu** của compute-app list,
2. tổng VRAM khi cả hai chạy gần bằng tổng hai delta đơn,
3. **không process nào fail, OOM, hay âm thầm rơi về CPU**.

Điều kiện 3 quan trọng nhất, và nó là điều kiện đã fail.

### 2.2 Số đo đơn lẻ (cùng một session, nên so được)

| | VRAM Δ | load | note |
|---|---|---|---|
| `ggml-small.bin` (ASR) một mình | **901 MiB** | 832 ms | encode 1023 ms, total 2426 ms, rc=0 |
| `Qwen3-4B-Q4_K_M` (LLM) một mình | **2866 MiB** | — | rc=0 |
| **Tổng hai số đơn** | **3767 MiB** | | VRAM khả dụng ≈ 6143 − 800 = **5343 MiB** |

Cộng lại thì *vừa*. Đó chính là lý do acceptance criteria cấm kết luận bằng
phép cộng.

### 2.3 Chạy đồng thời: bốn lần, bốn kết quả, không lần nào đạt

| Lần | `-b` | LLM | ASR | mẫu có cả hai | VRAM Δ |
|---|---|---|---|---|---|
| 1 | 2048 | crash `0xC0000409` | crash `0xC0000409` | 5 | 3297 MiB |
| 2 | 2048 | **OOM tường minh** | rc=0 | 3 | — |
| 3 | 2048 | rc=0 | crash `0xC0000409` | 13 | 3628 MiB |
| 4 | 512 | rc=0 | crash `0xC0000005` | 17 | 3670 MiB |

**Tính đồng thời đã được chứng minh** (3–17 mẫu có cả hai process giữ CUDA
context cùng lúc), và VRAM gần như cộng dồn đúng. Nhưng **lần nào cũng có một
bên chết**, và bên chết đổi theo lần — đây là một **race**, không phải một
ngưỡng tất định.

Bằng chứng tốt nhất là lần 2, vì nó fail **sạch** và tự nói lý do:

```
ggml_backend_cuda_buffer_type_alloc_buffer: allocating 317.27 MiB on device 0:
    cudaMalloc failed: out of memory
ggml_gallocr_reserve_n_impl: failed to allocate CUDA0 buffer of size 332677120
graph_reserve: failed to allocate compute buffers
llama_init_from_model: failed to initialize the context
```

**Vì sao OOM khi phép cộng nói là vừa?** Vì peak tôi lấy mẫu là **chặn dưới**,
không phải peak. Sampling 200–300 ms bỏ sót đúng cái đỉnh nhất thời khi
`graph_reserve` xin compute buffer. Cộng hai *chặn dưới* rồi so với dung lượng
là phép so sai hướng, và đây là bằng chứng trực tiếp của nó.

Giảm `-b` từ 2048 xuống 512 **không** cứu được: nó chỉ đổi bên nào chết.

**Kết luận:** `ggml-small` + `Qwen3-4B-Q4_K_M` **không co-resident ổn định**
trên 6 GB với ~800 MiB đã bị desktop chiếm. **Chạy tuần tự thì cả hai đều
chạy tốt** — mọi phép đo đơn lẻ ở 2.2 đều rc=0.

**Không suy ra "khả thi" từ hai phép đo đơn.** Khả thi được chứng minh là
**tuần tự**, và chi phí của tuần tự là **load model mỗi lượt** (ASR 832 ms;
LLM chưa đo riêng ở chế độ này) — một con số khác hẳn mọi thứ S2.1 đã đo.

### 2.4 Hai phát hiện vận hành, một trong đó là lỗi của tôi

**ASR binary crash thay vì fail sạch.** llama.cpp báo `cudaMalloc failed: out of
memory` rồi thoát với mã lỗi. whisper.cpp **crash** (`0xC0000409`
STATUS_STACK_BUFFER_OVERRUN, `0xC0000005` ACCESS_VIOLATION). Với một pipeline
thật, một bên fail sạch còn một bên crash là hai hợp đồng lỗi khác nhau.

**Harness của tôi để sót process con, và nó làm hỏng mọi phép đo sau đó.** Sau
lần chạy đồng thời thứ tư, GPU từ chối cấp cả 373 MiB (`CUDA-capable device(s)
is/are busy or unavailable`), rồi inference CPU cũng fail vì không cấp nổi
465 MiB RAM. Tôi đã kết luận sai một lúc rằng đó là **CUDA context mồ côi của
process đã chết** — `tasklist` với filter tên ảnh trả về rỗng nên tôi tin là
process đã chết. **Sai.** `Get-Process` cho thấy `llama-bench` **vẫn sống**,
working set **2734 MB**, và commit charge còn **0.41 GB trên 19.86 GB**. Kill
nó thì VRAM về 786 MiB và commit về 5.23 GB ngay.

Nên nguyên nhân thật là **lifecycle, không phải driver**. Đã sửa: harness giờ
luôn reap process con, có timeout và escalate sang kill, và ghi việc đó vào
record. Đây đúng là điều kiện đầu tiên mà A14 đặt ra trước khi được mở
llama.cpp server — và nó vừa tự chứng minh là điều kiện thật chứ không phải lo
xa.

---

## 3. Hallucination trên nền không có tiếng nói: **100%**

### 3.1 Vì sao nhóm này cần metric riêng

SyER không biểu diễn được: reference rỗng nên denominator bằng 0. Thư viện phổ
biến trả `wer = số insertion`, tức một **count không chặn trên** được báo dưới
đơn vị của một **rate**. Nên nhóm này báo theo **clip**, là một tỷ lệ nhị thức
thật:

- **NSOR** = số clip phát ra bất kỳ token nào / tổng clip.
- **Severity**, vì NSOR bão hoà: token/phút audio. Một model phát 3 token và
  một model phát 300 token đều ra 100%.

### 3.2 Số đo

Model `ggml-small.bin` (SHA-256 `1be3a9b2…`), GPU, `-l vi`, `-t 6`,
`flash_attn = 1` (mặc định), VAD **tắt** — cố ý, vì ở đây đang đo hành vi của
chính model, không đo biện pháp giảm thiểu.

| Chỉ số | Giá trị |
|---|---|
| NSOR | **3/3 = 100.0%** |
| Token hallucinate | **34** |
| Audio | 13.0 s |
| Severity | **156.9 token/phút** |
| Failure | **0** |

Theo từng clip:

| Clip | Loại | Token phát ra | RTF | Hình dạng output |
|---|---|---|---|---|
| `silence_digital_5s` | **im lặng số tuyệt đối** (RMS 0, peak 0) | **15** | 1.371 (cold) | boilerplate kiểu quảng cáo kênh/phụ đề, 69 ký tự |
| `silence_roomnoise_5s` | nhiễu tổng hợp ~−60 dBFS | **15** | 0.650 | cùng hình dạng, 69 ký tự |
| `tone_440hz_3s` | tone thuần 440 Hz | **4** | 0.952 | hình dạng khác, 16 ký tự |

**Không in text hallucinate ra terminal và không commit nó.** Nó nằm trong
`var/asr/results/` (gitignored). Mô tả ở đây chỉ theo **hình dạng**, vì một
dòng "ref/hyp" minh hoạ trong `docs/` là vĩnh viễn.

### 3.3 Đọc kết quả này cho đúng

**Im lặng số tuyệt đối vẫn sinh 15 token.** Không có tín hiệu nào để nhận sai —
file toàn số 0 — và model vẫn phát ra một câu boilerplate trôi chảy. Đây đúng
là thất bại khiến MeetAI *"nói về thứ không ai nói"*, và nó **liên quan trực
tiếp tới authority gate**: boilerplate tự tin là một đường để text trông có
thẩm quyền đi vào pipeline từ chỗ không có ai nói gì.

**Nhóm này gần như chắc chắn ĐÁNH GIÁ THẤP hallucination thật.** Whisper
hallucinate mạnh nhất trên nhiễu **có hình phổ giống tiếng nói**, không phải
trên im lặng số. Nhiễu phẳng −60 dBFS yếu hơn nền phòng họp thật (−50 đến
−35 dBFS). Nhóm realistic phải cắt từ khoảng lặng đầu/cuối của clip thật —
việc của phần 2.

**n = 3.** Quá nhỏ để nói gì ngoài "xảy ra, và xảy ra ở cả ba". Không có CI.
Clip là **synthetic**, generator được commit, audio thì không.

---

## 4. Bộ scorer: SyER, không phải WER

Tên quan trọng. Tiếng Việt viết **âm tiết** cách nhau bằng dấu cách, nên một
token whitespace là một âm tiết chứ không phải một từ. VLSP dùng **Syllable
Error Rate** đúng vì lý do đó, và một paper dự thi cùng challenge báo rằng áp
word segmentation lên label **không** cải thiện hệ thống. Gọi một metric
whitespace-token là "WER" mời đúng cái phản biện rằng token không phải từ.

### 4.1 NFC là bắt buộc, và đây là số đo chứng minh

| | SyER | CER | số ký tự |
|---|---|---|---|
| NFC ref vs **NFD** hyp, **cùng một câu** | **0.875** | 0.548 | 31 vs 41 |
| sau khi NFC cả hai bên | **0.0** | 0.0 | 31 vs 31 |

**87.5 điểm phần trăm sai trên text giống nhau từng ký tự**, chỉ vì bỏ một
bước chuẩn hoá. NFC là toàn phần và không mất mát cho tiếng Việt
(`NFC(NFD(x)) == x` cho cả 146 dạng chữ), nên nó **không che gì**. Và `đ` là
**một code point duy nhất** mà NFD không tách — đúng lý do dự án vẫn cần map
`đ→d` riêng khi fold.

Có test: cùng một câu, ref NFC và hyp NFD, assert SyER == 0. Bỏ bước NFC đi là
test fail.

### 4.2 Những gì scorer từ chối làm

| Từ chối | Lý do |
|---|---|
| Fold dấu ở headline | Chính sách đã chốt. Fold gộp `Thư/Thứ/Thu/Thủ` và `Minh/Mình` — đúng lớp lỗi dự án quan tâm nhất. Số đã fold chỉ là **diagnostic**, và **gap** mới là đại lượng có nghĩa. |
| Fold case ở headline | Hoa/thường là tín hiệu duy nhất ở mức text cho tên riêng. |
| Bỏ dấu câu thành **rỗng** | Gộp token qua dấu câu, sinh ra một substitution và một deletion từ không khí. Thay bằng **dấu cách**. Helper thư viện phổ biến làm đúng cái sai này. |
| Đổi số ↔ chữ, giãn viết tắt | Là inverse text normalisation, một chương trình có bug riêng theo cả hai chiều. Variant thuộc **dữ liệu corpus**, không thuộc scorer. |
| accuracy, F1, `1 − SyER` | Cùng lý do `meetai.evaluation` không có: một deletion (bỏ sót cam kết) và một insertion (bịa ra cam kết) không so sánh được. |
| Dùng `Rate` cho SyER | **`Rate` sẽ raise.** SyER vượt 1.0 được (insertion không chặn trên), và có test assert `Rate(6, 2)` raise. `Rate` **được** dùng cho các count failure, đúng chỗ của nó. |
| `wilson_interval` cho SyER | Sai hai lần: SyER không phải tỷ lệ, và lỗi **cụm trong một utterance** nên coi N token là N phép thử độc lập làm khoảng tin cậy hẹp đi theo hướng có lợi. Dùng **bootstrap theo utterance**, có tuỳ chọn **block** theo recording. |

### 4.3 Thư viện: tự viết, có lý do

`python-Levenshtein` là **GPL-2.0-or-later** còn dự án này MIT. `evaluate` tải
và **thực thi** một module từ Hugging Face Hub lúc load metric — remote code
execution ngay trên đường scoring, không thể chấp nhận với một dự án offline.
`jiwer` (Apache-2.0) không chuẩn hoá ngầm gì ở mặc định, nhưng vẫn cần
alignment có tie-break mình khai, `(S,D,I,N)` lưu theo từng utterance cho
bootstrap, và quy tắc reference-rỗng riêng. Nên scorer là **stdlib**, ~60 dòng
DP có backtrace, tie-break **khai rõ** là
substitute/equal > delete > insert.

**39 test** cho scorer, chạy không cần dataset và không cần GPU.

---

## 5. Đóng bốn lỗ rò `.gitignore`, và thêm một test giữ chúng

`git check-ignore` cho thấy những đường này **commit được**:

| Đường | Vì sao nguy hiểm |
|---|---|
| `prompts.txt`, `references.txt` | **VIVOS ship reference transcript đúng tên `prompts.txt`**, và `whisper-cli -otxt` ghi hypothesis ra `.txt` cạnh clip |
| `dev.tar.gz`, `corpus.zip`, `clips.tar` | corpus tiếng nói đến dưới dạng archive; chỉ phần *đã giải nén* vào `data/`/`var/` được chặn |
| `report.csv`, `hyp.lrc` | `-ocsv`/`-olrc` ghi transcript |
| `benchmarks/asr/hyp.json` | `benchmarks/*.json` chỉ khớp **một tầng**, và `bench*.json` không bắt vì basename không bắt đầu bằng `bench` |

Đã thêm rule cho cả bốn lớp, **theo extension và theo thư mục**. Verify: **0
file đang tracked bị ignore**, và `benchmarks/README.md`,
`docs/research/*.md` vẫn commit được.

**Và giờ có test.** `tests/test_gitignore.py`, 46 case theo hai chiều: nội dung
**phải** bị chặn, file repo cần **phải không** bị chặn, và **không file tracked
nào** bị ignore. Đã verify là nhạy với việc xoá cơ chế: bỏ rule `*.txt` ra thì
**4 test fail**; trả lại thì 46 pass. Trước đây hai lần sửa `.gitignore` đều là
hành động tay không có gì giữ.

---

## 6. Giới hạn, và những gì phần này KHÔNG chứng minh

- **Chưa có số WER nào.** Phần 2.
- **Co-residency đã đo là KHÔNG đạt** cho đúng cặp model này ở đúng kích thước
  này. **Chưa** thử `ggml-small` + một LLM nhỏ hơn, cũng chưa thử biến thể
  một-process (`whisper-talk-llama.exe` có trong build, chạy cả hai model
  trong **một** CUDA context — đó là một kiến trúc **khác**, và A14 chưa chốt
  kiến trúc production nên đo rồi gọi nó là "co-resident" sẽ trả lời một câu
  hỏi chưa được chọn).
- **Peak VRAM/RAM là chặn dưới**, không phải peak. Và lần này có bằng chứng
  trực tiếp rằng điều đó quan trọng: phép cộng hai chặn dưới nói "vừa", thực tế
  OOM.
- **n = 3** cho nhóm non-speech, toàn **synthetic**, và gần như chắc chắn
  **đánh giá thấp** hallucination trên phòng thật.
- **Chưa đo** latency p50/p95 mức request, RTF theo nhóm độ dài, nhiệt dài hạn.
- **spec B-1 vẫn `absent` cho "nói chồng"** và **chỉ một phần cho "accent"**:
  FLEURS và VIVOS đều là **đọc câu, một người nói mỗi clip**. Không dataset nào
  trong phạm vi lát này chứa tiếng nói chồng. Không được để bảng theo nhóm ngụ
  ý một độ phủ không có.
- Gate 0-S / 0-P / 0-C / 0-U vẫn **OPEN**.
