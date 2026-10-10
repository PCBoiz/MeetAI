# ADR 0005 — Nhánh CUDA 12.x, và đường llama.cpp cho benchmark

- **Trạng thái:** [ĐỀ XUẤT] — quyết định kỹ thuật của tôi để mở S2.2/S2.3; **không** phải quyết định sản phẩm
- **Ngày:** 2026-10-07 (lượt 8)
- **Lát:** S2.1
- **Số đo:** [S2.1 feasibility](../research/2026-10-07-s21-model-feasibility.md) · [artifact ledger](../research/2026-10-07-model-artifacts.md)

## Bối cảnh

`docs/plan.md` S2.1 yêu cầu chọn một nhánh CUDA kèm lý do, chọn một trong ba
đường `llama-cpp-python` kèm trade-off, và **đo VRAM/RAM peak thật** trên GTX
1660 Ti chứ không suy từ model card.

## Quyết định 1 — nhánh CUDA **12.x**

Và lý do **không phải** là hỗ trợ phần cứng. Tôi đã giả định sai điều đó lúc
bắt đầu lát này.

CUDA 13 **không** bỏ Turing. Nó bỏ Maxwell, Pascal, Volta; release notes CUDA
13.0 ghi *"CUDA 13.0 supports all NVIDIA architectures from Turing through Grace
Blackwell"*, và trong nvcc hiện tại `sm_75` là kiến trúc **thấp nhất và mặc
định**. Driver 610.62 (≥580) chạy được binary của cả 12.x và 13.x nhờ binary
backward compatibility.

Lý do thật là **hệ sinh thái**: **CTranslate2 không có bản build CUDA 13.** Tôi
verify bằng cách đọc binary chứ không đọc doc — quét `ctranslate2.dll` trong
wheel `cp312-win_amd64` cho đúng một tên DLL họ CUDA: **`cublas64_12.dll`**. Và
`faster-whisper` pin `ctranslate2>=4.0,<5`, nên toàn bộ đường ASR bị khóa vào thế
hệ CUDA 12 cho tới khi CTranslate2 phát hành bản 13.

Hệ quả kéo theo, ghi ở đây để khỏi phải phát hiện lại: nếu sau này cần PyTorch
thì nhánh là **`cu126`**, không phải `cu130`/`cu132` — wheel torch cu13x bundle
`cublas64_13.dll` và **không** có `cublas64_12.dll`, nên không dùng chung được
với CTranslate2 trong một environment.

Cũng ghi: wheel CTranslate2 bundle `cudnn64_9.dll` — **cuDNN 9**. Doc cài đặt
của CTranslate2 vẫn ghi "cuDNN 8"; release notes v4.5.0 ghi *"no longer
compatible with CUDNN 8"*. Theo thứ tự ưu tiên nguồn trong `AGENTS.md`, release
notes thắng doc.

## Quyết định 2 — đường llama.cpp: **binary chính thức, dạng CLI**, cho benchmark

Ba đường mà plan nêu, và kết quả đo:

**Đường 1 — build từ nguồn với CUDA.** Bị chặn: không có nvcc, MSVC, cmake. PyPI
chỉ phát hành **sdist** cho mọi version gần đây kể cả 0.3.36, nên
`pip install llama-cpp-python` bắt buộc compile. Mở đường này cần cài toolchain ở
mức hệ thống, việc cần Sơn cho phép. **Không chọn**, vì đường 3 đã chạy được nên
không có lý do đổi cấu hình máy.

**Đường 2 — pin prebuilt wheel.** Đây là chỗ "verify bằng cài thật, không bằng
wheel index" trả công, và nó cũng **đính chính một claim của lượt trước**: báo
cáo cũ nói wheel CUDA dừng ở 0.3.4, nhưng index `cu125` có
`llama_cpp_python-0.3.36-py3-none-win_amd64.whl` — bản mới nhất, tag `py3-none`
vì nó ship binary sẵn. Claim cũ chỉ đúng cho các wheel tag `cp312`.

Cài được, 511 MB, không cần toolchain. Rồi:

1. `import llama_cpp` fail. Đọc bảng import PE: `ggml-cuda.dll` cần
   `cudart64_12.dll` + `cublas64_12.dll`, và **`ggml.dll` import `ggml-cuda.dll`
   tĩnh** — nên wheel không load được kể cả khi chỉ muốn chạy CPU.
2. Giải bằng redistributable PyPI **của chính NVIDIA** (`nvidia-cuda-runtime-cu12`,
   `nvidia-cublas-cu12` — có wheel `win_amd64` thật). Không cần toolkit. CUDA
   **12.9** runtime chạy được binary build bằng **12.5** — đo được, không suy.
   `os.add_dll_directory` **không** sửa được; phải preload từng DLL theo thứ tự
   phụ thuộc.
3. Sau đó GPU nhận đúng, model báo `offloaded 25/25 layers to GPU`.
4. Rồi `llama_init_from_model` chết với **`STATUS_ILLEGAL_INSTRUCTION`**.

Nguyên nhân do chính build khai: `AVX512 = 1`. `ggml-cpu.dll` của wheel được
build bật AVX-512; i7-9750H không có AVX-512. **Wheel CUDA không dùng được trên
CPU này**, dù phần GPU của nó hoàn toàn ổn. Wheel từ index `cpu` (0.3.19) không
bật AVX-512 nên load được, nhưng là bản CPU và version cũ hơn.

**Đường 3 — binary chính thức.** Chọn cái này. Release ship **14 biến thể
`ggml-cpu-*`** và **dispatch lúc chạy**, tự chọn `ggml-cpu-haswell.dll` (AVX2) ở
đây — đúng thứ wheel đơn-biến-thể không làm được. Pin bằng build `b11464`, commit
`005a1e127`, SHA-256 của zip.

**Dùng ở dạng CLI, không phải server, và đó là một phân biệt có tải trọng.**
Plan nêu đường thứ ba là "llama.cpp server qua localhost", nhưng benchmark chỉ
cần `llama-bench.exe`. Không có listener nào được mở, nên lát này **không** thêm
bề mặt mạng, và toàn bộ phân tích threat về server không áp dụng cho S2.1.

## Quyết định 3 — harness phải tự chứng minh nó đo đúng thiết bị

Không phải nguyên tắc chung; nó có nguyên nhân cụ thể. Lần chạy đầu tôi để CUDA
DLL trên `PATH` và nhận:

```
load_backend: loaded CPU backend from ggml-cpu-haswell.dll
| qwen2 1B Q4_K | ... | CPU | pp128 | 132.82 |
```

`ggml-cuda.dll` **im lặng không load** — backend load động không tra `PATH` như
import tĩnh — `-ngl 99` bị bỏ qua, và kết quả là một số CPU. Nếu không đọc cột
backend, nó đã vào bảng GPU. Sửa: copy CUDA DLL vào **cùng thư mục** với binary.

Nên `benchmarks/bench_llamacpp.py` **thoát khác 0** khi không chứng minh được
bằng **hai nguồn độc lập**: chuỗi backend từ llama-bench **và** VRAM tăng
≥ 64 MiB so với baseline idle.

Một hệ quả nữa, cũng đo được: **`-ngl 0` không phải một lần chạy CPU.** Nó vẫn
đăng ký CUDA backend, vẫn cấp 741 MiB VRAM, và cho tg **chậm hơn cả CPU thật**
(5.43 vs 7.35 t/s). Baseline CPU thật cần `-dev none`. Vì vậy phía `--expect cpu`
xét theo **VRAM**, không theo chuỗi backend: llama-bench báo `backends: CUDA` bất
cứ khi nào backend đó được *đăng ký*, nên xét theo chuỗi sẽ loại mọi baseline CPU.

## Những gì đo được, và điều quan trọng nhất trong đó

`Qwen3-4B-Q4_K_M`, n=5 mỗi ô:

| | pp128 | pp512 | tg64 | VRAM Δ | RAM WS |
|---|---|---|---|---|---|
| GPU `-ngl 99` | 161.8 t/s | 168.9 t/s | **8.55 t/s** | 2865 MiB | 2794 MiB |
| CPU `-dev none` | 26.3 t/s | 26.7 t/s | 7.35 t/s | 11 MiB | 4438 MiB |
| GPU/CPU | **6.2×** | 6.3× | **1.16×** | | |

**GPU mua được prefill, gần như không mua được decode.** Và nguyên nhân là phần
cứng, không phải model: GPU bị cap ở **40 W trên card 80 W**, và dưới cap đó
memory clock đứng ở **810 MHz trên 6001 MHz được hỗ trợ** — ~13.5% băng thông
danh định — trong khi SM chạy gần boost tối đa. Prefill là compute-bound nên
hưởng lợi; decode là bandwidth-bound nên không.

Bằng chứng nội tại: Qwen3-4B (2.49 GB) cho 8.55 t/s, Qwen2.5-0.5B (0.46 GB) cho
43.8 t/s — tỷ lệ 5.1× so với tỷ lệ kích thước 5.4×. Đó là dấu hiệu bandwidth-bound.

Vì một trợ lý họp có context là transcript dài, **prefill là phần quan trọng**,
nên GPU vẫn đáng dùng — chỉ là không vì lý do thường được giả định.

Máy đang cắm điện, nên 40 W không do chạy pin. **Tôi không đổi power limit**: đó
là cấu hình hệ thống và là quyết định của Sơn.

## Hệ quả

- `benchmarks/` nằm **ngoài** `src/meetai/` một cách cố ý, để hai bất biến
  (`test_environment_invariants`, `test_no_value_in_errors`) vẫn **đúng thật**
  thay vì bị nới. Hệ quả phải nói rõ: hai bất biến đó **không** bao phủ
  `benchmarks/`.
- Không dependency nào vào `pyproject.toml`. Gói CUDA của NVIDIA là
  **proprietary** (`LicenseRef-NVIDIA-Proprietary`), khác hẳn mọi dependency
  hiện có, và chỉ nằm trong `var/bench-venv/`.
- `.gitignore` được bổ sung `*.gguf`, `*.safetensors`, `*.tsv`, `data/`,
  `bench*.json` — vì `git check-ignore` cho thấy một `weights.gguf` ở gốc repo
  **commit được**, và một file JSON kết quả có thể nhúng prompt hoặc hypothesis.
- Đường inference cho **production chưa chốt**, và S2.1 không nên chốt hộ. Xem
  mục 6 của báo cáo feasibility.

## Rollback

Không có gì để rollback trong app: lát này không đổi `src/`, không đổi
`pyproject.toml`, không đổi `uv.lock`. Bỏ `var/bench-venv/`, `var/llamacpp/` và
`models/` là máy trở về trạng thái trước lát. Phần commit chỉ là docs, script
benchmark và `.gitignore`.
