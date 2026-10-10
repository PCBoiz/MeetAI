# Model artifact ledger (S2.1)

Cập nhật 2026-10-07 (lượt 8). **Artifact tách khỏi app:** không gói nào ở đây là
dependency của `meetai`; chúng nằm trong `models/` và `var/`, đều gitignored.

`uv.lock` pin wheel bằng hash. **Weights và binary native không được pin bởi gì
cả**, nên file này là nơi pin chúng: version, URL, revision, SHA-256, license.
Không có file này thì "cùng một benchmark" là một câu không kiểm được.

## Quy ước

- SHA-256 đo trên file đã tải về máy, bằng `sha256sum`, **không** copy từ trang
  phát hành.
- Revision pin bằng commit sha của repo HuggingFace, **không** bằng `main`.
  `main` di chuyển; một số đo trỏ tới `main` là một số đo không tái lập được.
- License ghi theo đúng tên upstream khai, kể cả khi không phải SPDX.

## LLM weights

| Artifact | `Qwen3-4B-Q4_K_M.gguf` |
|---|---|
| Repo | `Qwen/Qwen3-4B-GGUF` |
| Revision | `bc640142c66e1fdd12af0bd68f40445458f3869b` |
| URL | `https://huggingface.co/Qwen/Qwen3-4B-GGUF/resolve/bc640142c66e1fdd12af0bd68f40445458f3869b/Qwen3-4B-Q4_K_M.gguf` |
| Bytes | 2 497 280 256 (2.326 GiB) |
| SHA-256 | `7485fe6f11af29433bc51cab58009521f205840f5b4ae3a32fa7f92e8534fdf5` |
| License | **apache-2.0** (tag trên repo), gated: no |
| Quant | Q4_K_M |
| Params | 4.02 B (llama.cpp đọc được: `model_n_params = 4022468096`) |
| Mục đích | Ứng viên LLM có kích thước **thực tế** cho 6 GB VRAM. Dùng để đo VRAM/RAM/throughput ở S2.1. |

| Artifact | `qwen2.5-0.5b-instruct-q4_k_m.gguf` |
|---|---|
| Repo | `Qwen/Qwen2.5-0.5B-Instruct-GGUF` |
| URL | `https://huggingface.co/Qwen/Qwen2.5-0.5B-Instruct-GGUF/resolve/main/qwen2.5-0.5b-instruct-q4_k_m.gguf` |
| Bytes | 491 400 032 (0.458 GiB) |
| SHA-256 | `74a4da8c9fdbcd15bd1f6d01d621410d31c6fc00986f5eb687824e7b93d7a9db` |
| License | **apache-2.0**, gated: no |
| Mục đích | **Chỉ để kiểm tra harness**, không phải ứng viên. Nhỏ nên vòng lặp sửa-chạy nhanh. Tải bằng `main` nên **không pin revision** — chấp nhận được vì không có số đo nào của S2.1 phụ thuộc nó. |

⚠️ **Bẫy license trong cùng một họ model.** `Qwen/Qwen2.5-7B-Instruct-GGUF` là
`apache-2.0`, nhưng `Qwen/Qwen2.5-3B-Instruct-GGUF` là **`other`** (Qwen
Research License, không phải permissive). Kiểm license **theo từng repo**, không
theo họ model.

## Native binary

| Artifact | llama.cpp prebuilt Windows CUDA |
|---|---|
| Release | `b11464` (ggml-org/llama.cpp), publish 2026-10-07 |
| Build | `0.6.0-dev (build 11464, commit 005a1e127)`, built with Clang 20.1.8 |
| Asset | `llama-b11464-bin-win-cuda-12.4-x64.zip` |
| Bytes | 264 528 404 |
| SHA-256 | `a626c2091bbf0ae2b26024e04410b39e8f27b80e9564f2bfd82f236bbb34bea0` |
| License | MIT (llama.cpp). Zip cũng kèm `LICENSE-LLVM-OpenMP`. |
| Giải nén tới | `var/llamacpp/b11464/` (gitignored) |

**Đây là một blob native chưa được audit.** Dependency inventory ở
`docs/research/2026-10-07-dependency-baseline.md` đã verify toàn bộ installed set
Python bằng `sys.addaudithook`; binary này **nằm ngoài** phạm vi audit đó. Hash ở
trên là cách duy nhất hiện có để biết mình đang chạy đúng cái đã kiểm.

## CUDA runtime (không phải toolkit)

Hai gói PyPI **của chính NVIDIA**, có wheel `win_amd64` thật. Chúng cung cấp
đúng những DLL mà `ggml-cuda.dll` import, nên **không cần cài CUDA toolkit** và
không có thay đổi nào ở mức hệ thống.

| Gói | Version | License |
|---|---|---|
| `nvidia-cuda-runtime-cu12` | 12.9.79 | **`LicenseRef-NVIDIA-Proprietary`** ⚠️ |
| `nvidia-cublas-cu12` | 12.9.2.10 | NVIDIA proprietary (metadata không khai SPDX) |
| `nvidia-cuda-nvrtc-cu12` | 12.9.86 | NVIDIA proprietary (kéo theo) |

⚠️ **Proprietary, không phải open source.** Khác hẳn mọi dependency hiện tại của
dự án. Chỉ ở trong môi trường benchmark (`var/bench-venv/`), **không** vào
`pyproject.toml`, **không** vào `uv.lock`.

**CUDA 12.9 runtime chạy được binary build bằng 12.5 và 12.4.** Đo trên máy, không
suy từ số version.

## Dữ liệu benchmark

**Chưa có.** S2.1 không đo chất lượng, nên chưa tải dataset nào. Việc chọn
dataset tiếng Việt thuộc S2.2 và còn một câu hỏi license chưa được Sơn trả lời
(xem `PROJECT_STATE.md` mục 4A).

Khi tới S2.2: repo **không thể** tái lập một số WER một mình, vì `.gitignore` cố
ý chặn `*.wav`, `*.tsv` và mọi thứ hình dạng transcript. Cách đúng là commit
**manifest + hash của reference**, không commit media hay text; và commit
**generator** cho bất cứ gì tự sinh ra, giống như corpus S1.7/S1.8 là file `.py`
được commit.

---

## Bổ sung S2.2 (lượt 9) — ASR runtime, weights, và dữ liệu đánh giá

### ASR runtime

| Artifact | whisper.cpp prebuilt Windows CUDA |
|---|---|
| Release | `b5454` (ggml-org/whisper.cpp), publish 2026-10-06 |
| Commit | `d1be6fde11ac6e0407606b4e42fe72d34add8037` |
| Asset | `whisper-bin-win-cuda-12.4.0-x64.zip` |
| Bytes | 684 913 404 |
| SHA-256 | `afef0b881c500958921c3f5523b50e59ee2ec9b6f5cbd25b324c51ed308a957a` |
| License | **MIT** (whisper.cpp) |
| Giải nén tới | `var/whispercpp/b5454/` (gitignored) |

Khác llama.cpp hai điểm, verify bằng cách mở zip: nó **bundle sẵn**
`cudart64_12.dll` / `cublas64_12.dll` / `cublasLt64_12.dll` nên **không cần**
gói PyPI của NVIDIA, và nó ship **9 biến thể `ggml-cpu-*`** dispatch lúc chạy
(chọn `ggml-cpu-haswell.dll` ở đây).

⚠️ **Nghĩa vụ license thứ hai, ghi lại để khỏi phát hiện muộn:** các DLL CUDA
runtime trong zip chịu **NVIDIA CUDA Toolkit EULA** (điều khoản
redistributable), không phải MIT. Không ảnh hưởng gì tới thử nghiệm riêng tư,
nhưng nếu MeetAI có ngày được phân phối kèm các DLL đó thì đây là một nghĩa vụ
tách biệt khỏi MIT của whisper.cpp.

### ASR weights

Repo `ggerganov/whisper.cpp` (HF), license **MIT**, gated: no, revision
`5359861c739e955e79d9a303bcbc70fb988958b1`.

| File | Bytes | SHA-256 |
|---|---|---|
| `ggml-small.bin` | 487 601 967 | `1be3a9b2063867b937e64e2ec7483364a79917e157fa98c5d94b5c1fffea987b` |
| `ggml-large-v3-turbo.bin` | 1 624 555 275 | `1fc70f774d38eb169993ac391eea357ef47c88757ef72ee5943879b7e8e2bc69` |

`ggml-large-v3-turbo.bin` **đã tải nhưng chưa dùng cho số đo nào** — nó là ứng
viên cho phần 2, và theo kết quả co-residency thì nó gần như chắc chắn thuộc
trường hợp **chỉ chạy tuần tự**.

⚠️ `ggml-org/whisper.cpp` trên HF trả **401** — namespace đó là GitHub org, không
phải repo weights. Dùng `ggerganov`.

**Bẫy tên quant:** tiny/base/small dùng `q5_1`; medium/large dùng `q5_0`. Và
**không có** `ggml-large-v3-q8_0.bin`. Một danh sách tải giả định lưới
`{q5_0,q8_0} × mọi size` sẽ 404.

### Dữ liệu đánh giá — nhánh PERMISSIVE

| Artifact | FLEURS `vi_vn` dev |
|---|---|
| Dataset | `google/fleurs`, license **CC-BY-4.0**, gated: no, không cần chấp nhận điều khoản |
| Revision | `70bb2e84b976b7e960aa89f1c648e09c59f894dd` |
| `data/vi_vn/audio/dev.tar.gz` | 214 500 592 B, SHA-256 `8821a394c99069409b3ce7bb5cd14b10b709f2ee2fea16f42b4701e1cc9ef673` |
| `data/vi_vn/dev.tsv` | 247 001 B, SHA-256 `c9bc17cede9765b1c75cb7a608f7066cb6bb6f8245cc75d721a5217a5dffb414` |
| Lưu ở | `data/fleurs/` (gitignored) |

**Số utterance: 361 — đo, không lấy từ card.** Dataset card ghi `415` cho
validation; parquet materialised ghi `361`. Tôi đếm: TSV có **đúng 361** dòng 7
cột (0 dòng lỗi), tar có **đúng 361** `.wav`, và **cả 361 đều khớp** theo
`file_name`. Card sai. Mọi số WER phải báo denominator **thật** chứ không
hardcode.

**Audio: mono, 16 kHz, 32-bit IEEE float** (`wFormatTag = 3`), đo từ header —
**không** phải 16-bit PCM như README của whisper.cpp yêu cầu. Nhưng
`whisper-cli` **vẫn đọc được** qua miniaudio; verify bằng cách chạy thật. Nên
câu "chỉ nhận 16-bit WAV" trong README là **lỗi thời** với build này.

**Cột TSV: 7 cột, không header.** `id, file_name, raw_transcription,
transcription, <char-level bị loader bỏ>, num_samples, gender`. Dùng **cột 2**
(`raw_transcription`, có hoa/thường và dấu câu) làm reference, vì contract
headline là case-sensitive. **Không đánh index từ cuối** — cột 4 là rác cho mục
đích này.

**Giới hạn cấu trúc, không phải giới hạn số lượng:** FLEURS là **đọc câu, một
người nói mỗi clip**. Nó **không chứa tiếng nói chồng** và độ phủ accent hẹp,
nên nghĩa vụ **B-1 trong spec vẫn `absent` cho "nói chồng"** và chỉ một phần
cho "accent". Không dataset nào trong phạm vi lát này đóng được hai trục đó.

### Dữ liệu đánh giá — nhánh NON-COMMERCIAL (chưa tải)

| Artifact | VIVOS |
|---|---|
| Dataset | `AILAB-VNUHCM/vivos`, license **CC BY-NC-SA 4.0** ⚠️ |
| Test split nhỏ nhất | `refs/convert/parquet` → `default/test/0000.parquet`, 84 956 101 B, SHA-256 `c37e8fc3cf5c4e446960cfa032683d74f759b5146ac475a087e1e327b0cf5d89` |
| Trạng thái | **chưa tải** |

Hai caveat bắt buộc kèm **mọi** số trên VIVOS, theo A13: dữ liệu là **đọc câu
trong môi trường yên tĩnh** nên không dự đoán trực tiếp hội thoại tự nhiên; và
**PhoWhisper có dùng VIVOS trong huấn luyện** nên kết quả VIVOS test chỉ để
**đối chiếu**, không phải bằng chứng tổng quát hoá sang cuộc họp.

⚠️ **ShareAlike là nghĩa vụ thứ hai ngoài NC, và nó lan truyền.** Đó là một lý
do **mạnh hơn cả lý do riêng tư** để reference text không vào git: commit text
VIVOS vào repo này có thể gắn nghĩa vụ ShareAlike lên chính repo.

### Clip non-speech (synthetic)

**Generator được commit, audio thì không** — cùng nguyên tắc với corpus
S1.7/S1.8 là file `.py` được commit. Sinh bằng LCG có seed cố định nên clip
byte-identical mỗi lần tạo lại. Ba clip: im lặng số tuyệt đối (RMS 0),
nhiễu tổng hợp ~−60 dBFS, tone 440 Hz. Tất cả mono/16 kHz/16-bit.

### PhoWhisper ở định dạng GGML — có, và nó mở được đường Việt-chuyên-biệt

Ứng viên cho phần 2, **chưa tải**. Upstream `vinai/PhoWhisper-*` là
**BSD-3-Clause**; các bản convert GGML của bên thứ ba (`dongxiat/*`) tự khai
**apache-2.0**, nhưng người convert **không thể** relicense tác phẩm phái sinh
ra khỏi điều khoản upstream — license **có hiệu lực là BSD-3-Clause**, và khai
Apache-2.0 ghi lại như **lỗi của người upload**. Cả hai đều permissive nên
không phát sinh vấn đề NC.

`dongxiat/ggml-PhoWhisper-small` 487 601 984 B — **lớn hơn đúng 17 byte** so với
`ggml-small.bin` của OpenAI (487 601 967). Chênh đúng 17 byte lặp lại trên
nhiều size là dấu hiệu của một lần chạy `convert-h5-to-ggml.py` thật (cùng
shape tensor, khác metadata header). Đó là **tín hiệu nhất quán, không phải
bằng chứng provenance** — đánh dấu **[GIẢ ĐỊNH]** và ghi hash để một lần thay
file sau này phát hiện được.

Giá trị thực tế: **không cần cài torch.** Script convert của whisper.cpp cần
`torch` **và** `transformers` **và** một checkout `openai/whisper` (để lấy
`mel_filters.npz`) — khoảng 4–5 GB cộng một cài đặt torch vĩnh viễn mà A14 đã
loại.

### Bổ sung S2.2 phần 2 (lượt 10) — dữ liệu đánh giá đã dùng

| Artifact | Giá trị |
|---|---|
| `google/fleurs` revision | `70bb2e84b976b7e960aa89f1c648e09c59f894dd` |
| `data/vi_vn/audio/dev.tar.gz` | 214 500 592 B · SHA-256 `8821a394c99069409b3ce7bb5cd14b10b709f2ee2fea16f42b4701e1cc9ef673` |
| `data/vi_vn/dev.tsv` | 247 001 B · SHA-256 `c9bc17cede9765b1c75cb7a608f7066cb6bb6f8245cc75d721a5217a5dffb414` |
| License | **CC-BY-4.0**, ungated, không cần chấp nhận điều khoản → **nhánh permissive** |
| Số utterance | **361** (đo; card ghi 415 → **card sai**) |
| Audio | mono 16 kHz **32-bit IEEE float**; `whisper-cli` đọc được qua miniaudio |
| Reference | **cột 2** `raw_transcription` (có hoa/thường và dấu câu) |

**Noise group (phái sinh).** 40 utterance × SNR 20/10/5 dB = 120 clip, sinh bởi
`benchmarks/make_noise_group.py`, LCG seed **1234567**. SNR đo được
**20.04 / 10.03 / 5.02 dB**, không clipping, 16 kHz. License **CC-BY-4.0**
(phái sinh từ FLEURS). **Generator được commit; audio thì không.**

**VIVOS: KHÔNG tải.** Cân nhắc và loại — là đọc câu một người nên không đóng
được trục B-1 nào đang thiếu, và mang nghĩa vụ CC BY-NC-SA với **ShareAlike lan
truyền**. Đó là lý do mạnh hơn cả riêng tư để reference text không vào git.

### Bổ sung lượt 11 — VietMed (phép thử accent thăm dò)

Sơn duyệt tải **chỉ subset test**, giữ ngoài Git. Đã làm.

| Artifact | Giá trị |
|---|---|
| Dataset | `leduckhai/VietMed`, revision `cc7980cd1392d2d85cf1c692b1d96e8581fc7eec` |
| License | tag HF **`mit`**, ungated. Paper ghi **CC BY 4.0** → **[CHỜ BẰNG CHỨNG]** mâu thuẫn chưa giải quyết. Permissive dưới cả hai cách đọc. |
| `labeled_medical_data/test_audio.zip` | 68 236 828 B · SHA-256 `e379ea4cd7e32184f3553cfb0510e235628e9c3439012055482c3cf378e8c7fe` |
| `labeled_medical_data/test_transcript.txt` | 1 092 362 B · SHA-256 `dfc710d7cde9966977828a08e9cb02efbfa98da23ce3e45bf649e05c03d4c6a8` |
| `Metadata_labeled_medical.xlsx` | 53 110 B · SHA-256 `3536b58dd67710bcb3963357eb691f38a44f4baf1bd8a5418c8844749bdc5c08` |
| Tổng tải | **69.3 MB** |
| Lưu ở | `data/vietmed/` (gitignored), giải nén `var/asr/vietmed/` (gitignored) |

⚠️ **Tag MIT không phải một cuộc audit quyền.** Nó phủ phần đóng góp của tác giả;
audio gốc thu từ nguồn công khai theo lập luận fair-use. **Chỉ đánh giá cục bộ,
không phát hành lại gì.**

**Đo được, không lấy từ paper:**

- **Audio: OGG/Vorbis, mono, 8000 Hz** — đọc Vorbis identification header,
  **500/500 file**. Xác nhận claim 8 kHz của paper. Nên **không so được** với
  FLEURS 16 kHz.
- **3437 file `.ogg`** trong zip, khớp đúng số dòng test.
- **Transcript là list literal Python các dict**, không phải `<id> <text>` như
  khảo sát nói. Parse bằng `ast.literal_eval`, **không** `eval`.
- **Metadata `.xlsx` đọc bằng stdlib** (`zipfile` + `ElementTree`), nên **không
  thêm dependency** nào. Cột `Accent` theo speaker, cộng cột split.
- **27 speaker** trong test split; hai nhóm accent có **1 và 2** speaker.

**ViMD: KHÔNG tải.** Sơn không duyệt vào phép thử hiện tại — license
**CC BY-NC-ND 4.0** (tag HF, tôi xác minh), và **ND** nghĩa là bản resample
(bắt buộc, vì ViMD không chuẩn hoá sample rate) **không được phát hành**.

### Bổ sung lượt 13 — S2.3 dùng Qwen3-4B, hash tự tính lại

Harness `bench_llm_policy.py` **tự tính SHA-256 của model mỗi run** và ghi vào
artifact, thay vì đọc lại từ bảng trên. Giá trị đo được ở cả hai run:

| Hạng mục | Giá trị |
|---|---|
| Model | `Qwen3-4B-Q4_K_M.gguf` |
| SHA-256 đo lại | `7485fe6f11af29433bc51cab58009521f205840f5b4ae3a32fa7f92e8534fdf5` |
| Khớp bảng trên | **có** |
| Binary | `b11464-005a1e127`, `llama-cli.exe` |
| System prompt SHA-256 | `0b4068712fd1f199…` (1424 ký tự) |
| Corpus | `llm_policy_vi.py` version `s23-v1`, 43 case |

**0.5B chỉ dùng kiểm harness, và lần này có số để nói vì sao điều đó đúng:**
4/4 case cho lỗi cấu trúc (thiếu `answer`, bọc trong code fence, bịa 4 field
`causes*`, dẫn `"15"` — một **ngày** — làm evidence id). Nó **không** được báo
như một kết quả benchmark: 4 case, và repo tải bằng `main` nên **không pin
revision**.
