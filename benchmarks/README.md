# benchmarks/ — S2.1 model feasibility harness

Ngoài `src/meetai/` một cách **cố ý**, không phải cho gọn.
`tests/test_environment_invariants.py` cấm `socket`, `httpx`, `subprocess`-kiểu
module mạng trong `src/meetai/`, và `tests/test_no_value_in_errors.py` cấm nhúng
giá trị vào message exception ở đó. Harness này cần spawn process.
*(Câu này trước đây còn ghi "và cần in đường dẫn file khi báo lỗi" — **không còn
đúng từ lượt 26**: mọi nhánh từ chối sớm in một **role** từ allowlist đóng kín,
không in đường dẫn. Lý do đặt ngoài `src/` giờ chỉ còn là việc spawn process.)* Đặt nó ở đây giữ các bất biến kia **đúng thật** thay
vì phải nới chúng — và benchmark vốn không phải phần của app được ship.

**Hệ quả phải nói rõ:** vì vậy hai bất biến đó **không** bao phủ thư mục này.
`benchmarks/` không được import vào `meetai`, và không có test nào bắt điều đó
hôm nay.

## Môi trường riêng, không phải extra của dự án

Benchmark **không** được thêm dependency nào vào `pyproject.toml`. Nó dùng một
venv riêng, và các gói CUDA của NVIDIA là **proprietary** (xem
`docs/research/2026-10-07-model-artifacts.md`), nên chúng không thuộc installed
set của app.

```bash
# Cache của uv mặc định nằm trên C:, mà C: chỉ còn ~2.8 GB. Phải chuyển.
export UV_CACHE_DIR="D:/MeetAI/var/uv-cache"

uv venv var/bench-venv --python 3.12
uv pip install --python var/bench-venv/Scripts/python.exe \
    "nvidia-cuda-runtime-cu12==12.9.79" "nvidia-cublas-cu12==12.9.2.10"
```

Không cài CUDA toolkit, không cài MSVC, không đổi PATH hệ thống.

## Lấy binary llama.cpp (pin theo build)

```bash
mkdir -p var/llamacpp && cd var/llamacpp
curl -sL -o llama-b11464-cuda.zip \
  "https://github.com/ggml-org/llama.cpp/releases/download/b11464/llama-b11464-bin-win-cuda-12.4-x64.zip"
sha256sum llama-b11464-cuda.zip
# phai bang: a626c2091bbf0ae2b26024e04410b39e8f27b80e9564f2bfd82f236bbb34bea0
python -c "import zipfile; zipfile.ZipFile('llama-b11464-cuda.zip').extractall('b11464')"
```

**Rồi copy CUDA runtime DLL vào CÙNG thư mục với binary.** Để trên `PATH` là
không đủ: backend load động không tra `PATH` như import tĩnh, nên `ggml-cuda.dll`
sẽ **im lặng không load**, `-ngl` bị bỏ qua, và lần chạy báo `backend = CPU`.
Đúng chuyện đã xảy ra lần đầu.

```bash
NV=var/bench-venv/Lib/site-packages/nvidia
cp "$NV/cuda_runtime/bin/cudart64_12.dll" \
   "$NV/cublas/bin/cublas64_12.dll" \
   "$NV/cublas/bin/cublasLt64_12.dll" var/llamacpp/b11464/
```

## Lấy weights

Pin theo **revision sha**, không theo `main`. Hash kỳ vọng ở
`docs/research/2026-10-07-model-artifacts.md`.

```bash
mkdir -p models/llm
curl -sL -o models/llm/Qwen3-4B-Q4_K_M.gguf \
  "https://huggingface.co/Qwen/Qwen3-4B-GGUF/resolve/bc640142c66e1fdd12af0bd68f40445458f3869b/Qwen3-4B-Q4_K_M.gguf"
sha256sum models/llm/Qwen3-4B-Q4_K_M.gguf
# phai bang: 7485fe6f11af29433bc51cab58009521f205840f5b4ae3a32fa7f92e8534fdf5
```

`models/` và `var/` đều gitignored. Weights **không bao giờ** vào git.

## Chạy

```bash
# GPU. Thoat khac 0 neu khong chung minh duoc la da chay tren GPU.
var/bench-venv/Scripts/python.exe benchmarks/bench_llamacpp.py \
    --model models/llm/Qwen3-4B-Q4_K_M.gguf \
    --ngl 99 -r 5 -p 128,512 -n 64 --label qwen3-4b-q4km --expect gpu

# CPU that su. `-ngl 0` KHONG phai CPU-only: no van dang ky CUDA backend
# va van cap 741 MiB VRAM. Phai dung -dev none.
var/bench-venv/Scripts/python.exe benchmarks/bench_llamacpp.py \
    --model models/llm/Qwen3-4B-Q4_K_M.gguf \
    --ngl 0 --device none -r 5 -p 128,512 -n 64 --label qwen3-4b-q4km --expect cpu
```

Kết quả JSON ghi vào `var/bench/` (gitignored). Snapshot đã commit nằm ở
`docs/research/2026-10-07-s21-model-feasibility.md`.


## Mọi script trong thư mục này, và cái nào cần interpreter nào

Trước lát này README chỉ tài liệu hoá `bench_llamacpp.py`. Bảng dưới là **toàn
bộ** script có `main()`, vì một harness không được ghi ở đâu là một harness
không ai chạy đúng.

**Hai nhóm interpreter, và chúng không thay thế nhau được:**

- Script dùng **import tương đối** (`from measure import ...`, sau một
  `sys.path.insert` tự khai) chạy được dưới **bất kỳ** Python 3.12 nào —
  `.venv`, `var/bench-venv` hay `var/bench-cpu-venv`.
- `bench_llm_policy.py` dùng **import tuyệt đối** và `from meetai.response import
  SpeechAct` cộng `from tests.corpus...`, nên nó **chỉ** chạy dưới `.venv` của dự
  án, tức qua `uv run`. Hai bench venv không có `meetai`.
- `bench_llm.py` cần `llama_cpp`, thứ **không** có trong `.venv`.

| Script | Chạy bằng | Cần gì sẵn | Ghi chú |
|---|---|---|---|
| `bench_llamacpp.py` | bất kỳ 3.12 | `llama-bench.exe`, model | Harness duy nhất có `--expect`. Xem mục lệnh phía trên. |
| `bench_llm_policy.py` | **`uv run`** (chỉ `.venv`) | `llama-cli.exe`, model, corpus S2.3 | Harness chạy corpus chính sách. Có `--device`/`--ngl` từ lượt 29. |
| `bench_llm.py` | **`var/bench-cpu-venv`** | `llama_cpp`, model | In-process qua `llama-cpp-python`. Wheel CUDA crash trên CPU này (AVX-512). |
| `bench_asr.py` | bất kỳ 3.12 | `whisper-cli.exe`, manifest, model, **audio** | Có audio nên **ngoài phạm vi** mọi lát hiện tại. |
| `bench_coresidency.py` | bất kỳ 3.12 | cả hai binary + cả hai model + clip | GPU **và** audio, `-ngl 99` nung cứng. Ngoài phạm vi. |
| `postprocess_asr.py` | bất kỳ 3.12 | results/tsv/manifest | Thuần chấm điểm, không model. |
| `rescore_llm_policy.py` | `uv run` | generation đã lưu | Chấm lại, **không** chạy lại model. |
| `make_vietmed_manifest.py`, `make_noise_group.py`, `make_nonspeech_clips.py` | bất kỳ 3.12 | dataset | Dựng manifest/clip. Không tải dataset trong lát nào hiện tại. |
| `measure.py`, `scoring.py`, `policy_scoring.py`, `preflight.py`, `gpulock.py`, `cuda_preload.py`, `refusals.py` | — | — | Thư viện, không có `main()`. |
| `winmem.py` | — | — | **Prototype lượt 32**, không có `main()` và **chưa ai gọi**. Đọc counter bộ nhớ của một process bằng Windows API theo **handle**. Chưa nối vào `measure.py`, chưa đổi artifact, chưa đổi ngưỡng. |

## Hai bench venv, và cái nào nạp được model trên CPU

Cả hai **nằm ngoài `uv.lock`** và **không test nào soi chúng**. Đây là bản ghi,
không phải lời khuyên nên dùng.

| Venv | `llama_cpp` | CUDA DLL | Dùng được cho |
|---|---|---|---|
| `.venv` | **không có** | — | `bench_llm_policy.py`, `rescore_llm_policy.py` |
| `var/bench-venv` | 0.3.36 | **có** (`ggml-cuda.dll`) | GPU in-process — nhưng **crash trên CPU này** (AVX-512) |
| `var/bench-cpu-venv` | 0.3.19 | **không** | **Đường CPU in-process duy nhất** |

`var/bench-cpu-venv` là venv duy nhất có `llama_cpp` **không kèm** CUDA DLL, nên
nó là chỗ duy nhất một phép nạp model CPU in-process chạy được. Trước lát này nó
**không được nhắc ở bất kỳ lệnh nào** trong repo — chỉ xuất hiện một lần trong
một research note, như một lỗ hổng lockfile.

## CPU mode cho `bench_llm_policy.py` — và vì sao nó vẫn từ chối

```bash
# KHONG chay duoc hom nay: cong RAM CPU con cho Son duyet nguong.
uv run python -m benchmarks.bench_llm_policy --device none --only S23.A
```

`--device none` làm hai việc: truyền `-dev none` cho `llama-cli`, và chuyển
preflight sang **cổng RAM host**, không gọi cổng VRAM.

**`-ngl 0` một mình KHÔNG phải CPU-only** — đo được là nó vẫn đăng ký backend
CUDA và vẫn cấp 741 MiB VRAM. Nên `--ngl` mặc định **suy từ `--device`** (0 cho
`none`, 99 cho `auto`), và một cặp mâu thuẫn bị **từ chối** chứ không bị sửa
ngầm.

**Ba lý do từ chối khác nhau, cố ý không gộp:**

| Lệnh | Lý do | Exit |
|---|---|---|
| `--device none` | `chua co nguong RAM duoc duyet` — **ngưỡng chờ duyệt**, không phải thiếu RAM | 3 |
| `--device auto` trên máy không GPU | `khong doc duoc VRAM tu nvidia-smi` — **không có GPU** | 3 |
| `--device auto` khi RAM thấp | `khong du RAM host` — **thiếu RAM** | 3 |

Gộp chúng sẽ gửi người chạy đi đóng bớt process vì một quyết định mà không lượng
RAM nào thay đổi được.

**`--binary` là một allowlist đóng kín** (quyết định của chủ dự án,
2026-10-10): chỉ `llama-cli.exe` và `llama-bench.exe`, xét theo **basename**, và
xét **trước** phép kiểm tồn tại — nên một tên bị cấm nhận cùng một câu trả lời
dù file có trên đĩa hay không. Năm binary mở cổng mạng nằm giải nén sẵn cạnh hai
binary CLI dưới `var/`.

## Vì sao harness từ chối nhiều thứ

| Cơ chế | Lý do |
|---|---|
| `--expect gpu` fail nếu không chứng minh được | llama.cpp **im lặng** chạy CPU khi backend CUDA không load. Cần hai bằng chứng độc lập: chuỗi backend **và** VRAM tăng ≥ 64 MiB. |
| `--expect cpu` xét theo VRAM, không theo chuỗi backend | llama-bench báo `backends: CUDA` bất cứ khi nào backend CUDA được *đăng ký*, kể cả `-dev none`. Xét theo chuỗi sẽ loại mọi baseline CPU. |
| `summarise()` **giữ lại** p95 khi n < 20 | p95 từ 20 mẫu là quan sát tệ thứ hai. Gọi nó là p95 là tuyên bố một độ chính xác không có. |
| Mọi VRAM/RAM đều kèm ghi chú "lower bound" | Sampling 200/300 ms sẽ bỏ sót spike lúc load. Một peak lấy *sau* khi chạy thì đã muộn. |
| Peak VRAM luôn kèm baseline idle | GPU này đang chạy desktop; ~855 MiB bị chiếm trước khi load. "Peak VRAM" không kèm baseline là gộp cả window manager vào. |
| Ghi power limit và memory clock vào mọi record | GPU bị cap **40 W trên 80 W**, memory clock 810 MHz trên 6001 MHz. Generation là bandwidth-bound, nên tokens/giây không kèm hai số này là không đọc được. |
| Cổng RAM CPU **từ chối cho tới khi có ngưỡng được duyệt** | Peak working set CPU đo được **4438 MiB** là **n=1**, lấy mẫu 300 ms, nên là **chặn dưới** — không phải một mức an toàn. Chủ dự án chốt giữ `pending`. Cổng từ chối **trước khi đọc bộ nhớ**, nên thông báo không thể bị đọc thành "đóng bớt process rồi thử lại". |
| Cổng VRAM **không** được gọi trong CPU mode | `require_headroom` fail-closed khi không đo được — trên máy không GPU, điều đó biến *không có GPU* thành *không đủ GPU*, từ chối một lần chạy không cần GPU nào. |
| `bench_llm.py` còn đó nhưng không dùng cho GPU | Nó đi qua `llama-cpp-python`, mà wheel CUDA crash trên CPU này (AVX-512). Giữ lại để nếu sau này có wheel không-AVX512 thì so được in-process với CLI. |

## Không làm

Không tải weights lúc chạy benchmark: đường dẫn model phải tồn tại sẵn, nên một
lần đo không bao giờ âm thầm fetch. Không gọi API ngoài. Không ghi transcript
hay audio. Không chạy stress test dài — workload có giới hạn, và nhiệt được ghi
lại từng lần.
