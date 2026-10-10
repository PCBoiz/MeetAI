# S2.1 — khả thi model local trên GTX 1660 Ti

Đo 2026-10-07 (lượt 8). Mọi số trong file này do tôi chạy trên máy này. Không
số nào lấy từ model card, wheel index hay báo cáo trước.

Tái lập: xem `benchmarks/README.md`.

---

## 1. Ma trận phần cứng — verify bằng lệnh

| Hạng mục | Giá trị đo được | Lệnh |
|---|---|---|
| OS | Windows 11 Pro build **26200**, x64 | `Get-CimInstance Win32_OperatingSystem` |
| CPU | Intel i7-9750H, **6 core / 12 thread** | `Get-CimInstance Win32_Processor` |
| RAM | 15.86 GB tổng, **4.21 GB free** lúc audit | như trên |
| GPU | **GTX 1660 Ti**, compute capability **7.5** (Turing TU116) | `nvidia-smi` |
| VRAM | 6144 MiB tổng; **855 MiB đã dùng khi idle**; `--list-devices` báo **5134 MiB free** | `nvidia-smi` |
| Driver | **610.62**, CUDA UMD **13.3** | `nvidia-smi` |
| CUDA toolkit / nvcc | **KHÔNG CÓ** | `nvcc --version` → not found |
| MSVC / Build Tools | **KHÔNG CÓ** | `vswhere.exe` → not found |
| cmake | **KHÔNG CÓ** | `cmake --version` → not found |
| Python | 3.12.13 qua uv | `uv run python -V` |
| Đĩa | D: còn **24 GB** sau khi tải; **C: chỉ còn 2.77 GB** | `Get-PSDrive` |

### 1.1 Hai giới hạn phần cứng quyết định mọi số phía dưới

**GPU bị cap ở 40 W trên card 80 W.**

| | Giá trị |
|---|---|
| `enforced.power.limit` | **40.00 W** |
| `power.max_limit` | **80.00 W** |
| `clocks.max.memory` | 6001 MHz |
| memory clock **khi đang chạy** | **810 MHz** |
| SM clock khi đang chạy | 1875 MHz (gần boost tối đa) |
| GPU utilisation | 100% |

Memory clock nằm ở state thứ ba trong bốn state được hỗ trợ (6001 / 5001 / 810 /
405 MHz), tức **~13.5% clock bộ nhớ danh định**. Sinh token là tác vụ **giới hạn
bởi băng thông bộ nhớ**, nên con số tokens/giây dưới đây mô tả **profile điện
này** ít nhất ngang với mức nó mô tả model.

Bằng chứng nội tại rằng đây đúng là nút cổ chai: Qwen3-4B (2.49 GB) đạt 8.55 t/s
còn Qwen2.5-0.5B (0.46 GB) đạt 43.8 t/s — tỷ lệ 5.1×, gần đúng tỷ lệ kích thước
5.4×. Đó là dấu hiệu của bandwidth-bound, không phải compute-bound.

Máy đang cắm điện (`PowerLineStatus = Online`, không có battery object), nên 40 W
**không** phải do chạy pin.

**Đo thêm 2026-10-07 (theo yêu cầu A15): 40 W là một cap cấu hình đang chủ động
giới hạn clock, không phải mức tiêu thụ tự nhiên.** Đây là phân biệt quan trọng
và một ảnh chụp `power.draw` một lần không trả lời được.

| Chỉ số | Giá trị |
|---|---|
| `power.default_limit` | **80.00 W** |
| `power.max_limit` | 80.00 W |
| `power.min_limit` | 10.00 W |
| `enforced.power.limit` | **40.00 W** |
| `power.limit` | `[N/A]` |

Default của card là **80 W**; cái đang có hiệu lực là **40 W**, tức có thứ gì
bên ngoài đang áp cap, không phải card tự đặt.

Lấy mẫu 40 lần **trong lúc đang chạy** benchmark:

| Quan sát | Kết quả |
|---|---|
| `clocks_event_reasons.sw_power_cap` | **Active ở 39/40 mẫu** |
| `clocks_event_reasons.hw_thermal_slowdown` | Not Active ở **mọi** mẫu |
| `clocks_event_reasons.hw_power_brake_slowdown` | Not Active ở **mọi** mẫu |
| `power.draw` khi tải | ghim ở **40.0–40.4 W**, đúng bằng enforced limit |
| `pstate` | **P5** (không bao giờ P0) |
| memory clock | **810 MHz** suốt, không nhích |
| nhiệt độ | **59–63 °C** |

Kết luận đọc được từ bảng này: nút cổ chai là **software power cap**, **không
phải nhiệt** (nhiệt còn rất xa ngưỡng, và cả hai cờ hardware slowdown đều im).
Card bị giữ ở nửa power budget mặc định của chính nó trong khi chạy mát.

Khả năng cao là profile điện của OEM/driver. **Tôi không thay đổi gì** — không
BIOS, không driver, không power profile, không ép xung. Chạy lại cùng benchmark
sau khi đo: tg128 = 8.43 t/s, nằm trong dải 8.43–9.27 của các lần trước, nên
baseline **tái lập được** và mọi so sánh về sau có mốc.

**GTU 1660 Ti không có tensor core.** llama.cpp tự báo khi khởi tạo:

```
The following devices will have suboptimal performance due to a lack of tensor cores:
  Device 0: NVIDIA GeForce GTX 1660 Ti
```

Đúng về phần cứng: TU116 bỏ tensor core, khác các card RTX cùng thế hệ Turing.
Nên mọi kỳ vọng về tăng tốc fp16 kiểu RTX đều không áp dụng ở đây.

---

## 2. Quyết định nhánh CUDA: **12.x**

Và lý do **không phải** là Turing — đây là chỗ tôi đã giả định sai lúc đầu.

| Câu hỏi | Trả lời | Nguồn |
|---|---|---|
| CUDA 13 có bỏ Turing/sm_75? | **Không.** CUDA 13 bỏ **Maxwell, Pascal, Volta**. *"CUDA 13.0 supports all NVIDIA architectures from Turing through Grace Blackwell."* sm_75 hiện là kiến trúc **thấp nhất và mặc định** của nvcc. | CUDA 13.0 release notes (2025-08-08); nvcc docs (2026-09-13) |
| Driver 610.62 chạy được binary CUDA 12.x? | **Được.** Binary backward compatibility: *"applications built against any of the older CUDA Toolkits always continued to function on newer drivers"*. CUDA 12.x cần driver ≥525; 13.x cần ≥580. | NVIDIA CUDA compatibility docs (2026-09-09) |
| Vậy vì sao chọn 12.x? | **Vì CTranslate2 không có bản CUDA 13.** Và CTranslate2 là thứ faster-whisper phụ thuộc (`ctranslate2>=4.0,<5`), tức là toàn bộ đường ASR bị khóa vào thế hệ CUDA 12. | đo trực tiếp, xem 2.1 |

### 2.1 Tôi tự verify khẳng định quyết định nhánh

Không đọc doc — đọc binary. Tải `ctranslate2-4.8.2-cp312-cp312-win_amd64.whl`
(19.2 MB) và quét bảng chuỗi/import của `ctranslate2.dll`:

| Tên DLL thuộc họ CUDA mà `ctranslate2.dll` tham chiếu | |
|---|---|
| `cublas64_12.dll` | ← **CUDA major 12** |
| `nvcuda.dll` | driver |

Và wheel có bundle `cudnn64_9.dll` (266 288 bytes) — **cuDNN 9**, không phải 8.
Doc cài đặt của CTranslate2 vẫn ghi "cuDNN 8"; release notes v4.5.0 (2024-10-22)
ghi *"now supports CUDNN 9 and is no longer compatible with CUDNN 8"*. Theo thứ
tự ưu tiên nguồn của dự án, **release notes thắng doc**.

Hệ quả thực tế, chưa cần tới S2.2 để biết: **PyTorch `cu130`/`cu132` không dùng
chung được với CTranslate2**, vì wheel torch cu13x bundle `cublas64_13.dll` chứ
không có `cublas64_12.dll`. Nếu sau này cần torch, nhánh là **`cu126`**.

---

## 3. Ba đường `llama-cpp-python` — bằng chứng, không phải ý kiến

### 3.1 Đường 1 — build từ nguồn với CUDA trên Windows/MSVC

**Bị chặn trên máy này.** Thiếu cả ba: nvcc, MSVC, cmake. Và PyPI chỉ có sdist:

```
llama-cpp-python 0.3.36 (latest)  files: sdist llama_cpp_python-0.3.36.tar.gz
0.3.4 ... 0.3.9: ['sdist']  wheels=0
```

Nên `pip install llama-cpp-python` **bắt buộc** phải compile. Mở đường này cần
cài build toolchain ở mức hệ thống — việc cần Sơn cho phép, và **không cần
thiết**, vì đường 3 đã chạy được.

### 3.2 Đường 2 — pin prebuilt wheel

Hai biến thể, kết quả khác nhau hẳn.

**2a. Wheel CUDA (index `cu125`, 0.3.36, 511 MB) — CÀI ĐƯỢC, KHÔNG CHẠY ĐƯỢC.**

Đây là chỗ "verify bằng cài thật" trả công. Index nói có wheel; cài vào thì:

1. Cài sạch trong 75 s, không cần toolchain nào.
2. `import llama_cpp` **fail**: `Could not find module 'llama.dll' (or one of its dependencies)`.
3. Đọc bảng import PE trực tiếp thì ra nguyên nhân: `ggml-cuda.dll` import
   `cudart64_12.dll` + `cublas64_12.dll`, và máy không có CUDA toolkit. Tệ hơn,
   **`ggml.dll` import `ggml-cuda.dll` tĩnh**, nên wheel không load được **kể cả
   khi chỉ muốn chạy CPU**.
4. `os.add_dll_directory` **không** sửa được — nó không với tới import bắc cầu
   của một DLL load bằng đường dẫn tuyệt đối. Preload từng DLL theo đúng thứ tự
   phụ thuộc thì được.
5. Sau khi preload: GPU nhận đúng, `llama_supports_gpu_offload() = True`, load
   model báo **`offloaded 25/25 layers to GPU`**, `CUDA0 model buffer size = 373.73 MiB`.
6. Rồi `llama_init_from_model` **chết với `STATUS_ILLEGAL_INSTRUCTION` (0xc000001d)**.

Nguyên nhân, do chính build tự khai:

```
CPU : SSE3 = 1 | SSSE3 = 1 | AVX = 1 | AVX2 = 1 | F16C = 1 | FMA = 1 | AVX512 = 1 | ...
```

`ggml-cpu.dll` trong wheel được build **bật AVX-512**. i7-9750H (Coffee Lake-H)
**không có AVX-512**. Wheel này không dùng được trên CPU này, dù phần GPU của nó
hoàn toàn ổn (`CUDA : ARCHS = 600,610,700,750,...` — có 750).

**2b. Wheel CPU (index `cpu`, 0.3.19 cp312) — chạy được, nhưng chỉ CPU.**

```
CPU : SSE3 = 1 | SSSE3 = 1 | AVX = 1 | AVX2 = 1 | F16C = 1 | FMA = 1 | LLAMAFILE = 1 | OPENMP = 1 | REPACK = 1
```

Không có AVX-512 → load được. Nhưng là bản CPU, và version dừng ở **0.3.19**
(wheel CUDA cp312 trên các index `cu121`/`cu124` dừng ở **0.3.4**).

### 3.3 Đường 3 — binary chính thức của llama.cpp

**Chạy được.** Build `b11464`, commit `005a1e127`.

Điểm quyết định: release chính thức ship **14 biến thể `ggml-cpu-*`** và
**dispatch lúc chạy**:

```
ggml-cpu-sse42 / sandybridge / ivybridge / haswell / piledriver / alderlake /
skylakex / cannonlake / icelake / cascadelake / cooperlake / sapphirerapids /
zen4 / x64
```

Trên máy này nó tự chọn `ggml-cpu-haswell.dll` (AVX2) — đúng thứ mà wheel đơn
biến thể ở 3.2a không làm được.

**Một lỗi tôi mắc và cần ghi lại.** Lần chạy đầu tôi để CUDA DLL trên `PATH` và
nhận được:

```
load_backend: loaded RPC backend ...
load_backend: loaded CPU backend from ggml-cpu-haswell.dll
| qwen2 1B Q4_K | ... | CPU | 6 | pp128 | 132.82 ± 5.32 |
```

`ggml-cuda.dll` **im lặng không load** (backend load động không tra `PATH` như
import tĩnh), `-ngl 99` bị bỏ qua, và nó báo `backend = CPU`. Nếu tôi không đọc
cột đó, tôi đã ghi một số CPU vào bảng GPU. Sửa bằng cách copy
`cudart64_12.dll`, `cublas64_12.dll`, `cublasLt64_12.dll` vào **cùng thư mục**
với binary.

Đây là lý do `benchmarks/bench_llamacpp.py` **từ chối báo một lần chạy GPU mà nó
không chứng minh được bằng hai nguồn độc lập**: chuỗi backend từ llama-bench
*và* mức VRAM tăng ≥ 64 MiB so với baseline idle.

### 3.4 Bảng trade-off

| | Đường 1: build nguồn | Đường 2a: wheel CUDA | Đường 2b: wheel CPU | Đường 3: binary chính thức |
|---|---|---|---|---|
| Chạy trên máy này | **Không** | **Không** (AVX-512) | Có | **Có** |
| Cần toolchain | nvcc + MSVC + cmake | không | không | không |
| Cần thay đổi hệ thống | **Có** (cài global) | không | không | không |
| GPU | (nếu build được) | phần GPU ổn, phần CPU chết | không | **Có**, xác nhận |
| Runtime CPU dispatch | tuỳ flag build | **không** (1 biến thể) | không cần | **có** (14 biến thể) |
| Version mới nhất | 0.3.36 | 0.3.36 | **0.3.19** | b11464 (hằng ngày) |
| Reproducibility | thấp (phụ thuộc máy build) | cao (hash wheel) | cao | cao (hash zip + commit) |
| Ranh giới process | in-process | in-process | in-process | **process riêng** |
| Dùng được từ Python | trực tiếp | trực tiếp | trực tiếp | qua CLI hoặc HTTP server |

**Chọn cho S2.1: đường 3**, và dùng ở dạng **CLI** (`llama-bench.exe`), không
phải server. Benchmark không cần listener nào, nên lát này không mở thêm bề mặt
mạng.

**Đường cho production thì CHƯA chốt** và không nên để S2.1 tự chốt hộ — xem mục 6.

---

## 4. Số đo

Model: `Qwen3-4B-Q4_K_M.gguf`, SHA-256 `7485fe6f…`, 4.02 B params, Q4_K_M.
Build `b11464` / `005a1e127`. `-r 5` cho mỗi test, n=5 mẫu mỗi ô.

| Cấu hình | pp128 (t/s) | pp512 (t/s) | tg64 (t/s) | VRAM Δ | RAM working set | mem clock | power | temp |
|---|---|---|---|---|---|---|---|---|
| GPU, `-ngl 99` | **161.82 ± 2.22** | **168.85 ± 1.19** | **8.55 ± 0.07** | **2865 MiB** | 2794 MiB | 810 MHz | 40.7 W | 69 °C |
| CPU, `-dev none` | 26.25 ± 0.47 | 26.70 ± 0.44 | 7.35 ± 0.07 | 11 MiB | **4438 MiB** | 405 MHz | 13.0 W | 62 °C |
| Tỷ lệ GPU/CPU | **6.2×** | **6.3×** | **1.16×** | | | | | |

Nhiệt độ idle trước khi chạy: 57 °C.

### 4.1 Đọc bảng này cho đúng

**GPU mua được prompt processing, gần như không mua được generation.** 6.2× ở
prefill, 1.16× ở decode. Hoàn toàn khớp với mục 1.1: prefill là compute-bound và
SM chạy gần boost tối đa; decode là bandwidth-bound và bộ nhớ bị kẹt ở 13.5%
clock. Với một trợ lý họp — nơi context là transcript dài — **prefill là phần
quan trọng**, nên GPU vẫn đáng dùng, chỉ là không vì lý do người ta thường nghĩ.

**`-ngl 0` KHÔNG phải một lần chạy CPU.** Đo được: `-ngl 0` vẫn đăng ký CUDA
backend, vẫn cấp **741 MiB VRAM**, và cho tg64 = 5.43 t/s — **chậm hơn cả CPU
thật** (7.35 t/s). Cấu hình hybrid tệ hơn cả hai đầu. Baseline CPU thật cần
`-dev none`. Harness kiểm điều này bằng VRAM, không bằng chuỗi backend, vì
llama-bench báo `backends: CUDA` bất cứ khi nào backend CUDA được *đăng ký*.

**RAM ngược chiều với VRAM:** chạy CPU dùng **nhiều RAM hơn** (4438 vs 2794 MiB)
vì weights phải nằm trong RAM hệ thống. Với 4.21 GB free lúc audit, bản CPU
**sát trần RAM**.

**Biến động giữa các lần chạy ~5%.** Ba lần chạy GPU riêng biệt cho tg64 = 9.27 /
8.55 / 8.78 t/s và pp128 = 170.09 / 161.82 / 160.60. Nhiệt tăng 57→69 °C trong
một lần chạy ~60 s. Nên **không** coi chữ số thứ hai là có nghĩa.

### 4.2 VRAM headroom — con số bắt cầu sang S2.2

Peak **3691 MiB** trên 6143 MiB tổng, với **855 MiB** đã bị desktop chiếm trước
khi load. Còn lại **~2.4 GiB** cho bất cứ thứ gì phải cùng ở trên GPU.

**Chưa đo co-residency.** Hai phép đo riêng cộng lại **không** chứng minh được
cả hai cùng chạy: fragmentation và context allocation làm tổng lạc quan hơn thực
tế. Đây là phép đo đầu tiên S2.2 phải làm, không phải thứ suy ra từ bảng này.

---

## 5. Những gì file này KHÔNG chứng minh

- **Không có số chất lượng nào.** Không WER, không CER, không đánh giá LLM. Đó
  là S2.2/S2.3 và chúng có acceptance criteria riêng. S2.1 trả lời "máy này chạy
  được gì", không trả lời "chạy tốt không".
- **Không có latency p50/p95 ở mức request.** `llama-bench` báo throughput
  (t/s) với ±stddev trên n=5, không phải phân phối latency đầu-cuối. Một p95
  thật cần n lớn hơn nhiều và cần đo đúng đường mà app sẽ dùng.
- **Không tuyên bố gì về mốc 1–2 giây.** Mốc đó là mục tiêu thử nghiệm, không
  phải SLA, và chưa đo đúng pipeline nào để so.
- **Peak VRAM/RAM là chặn dưới, không phải peak.** Sampling 200 ms (VRAM) và
  300 ms (RAM) sẽ bỏ sót spike ngắn khi load.
- **Không phải bằng chứng Discord hỗ trợ bot voice receive.** Gate 0-S/0-P/0-C
  vẫn OPEN; kết quả phần cứng không liên quan tới câu hỏi đó.
- **cuDNN chưa test.** CTranslate2 bundle shim `cudnn64_9.dll` nhưng **không**
  bundle các sub-library mà shim load (`cudnn_graph64_9.dll`, `cudnn_cnn64_9.dll`,
  `cudnn_ops64_9.dll`, `cudnn_adv64_9.dll`). Liệu đường Conv1d pure-CUDA từ
  v4.6.3 có khiến chúng thành không cần thiết — **[CHỜ BẰNG CHỨNG]**, phải đo ở
  S2.2.

## 6. Câu hỏi còn lại, và vì sao S2.1 không tự trả lời

**Đường inference cho production.** S2.1 chọn được đường cho *benchmark* (CLI).
Cho production thì Python cần gọi được model, và hôm nay chỉ còn hai khả năng:

1. **llama.cpp server trên loopback.** Chạy được ngay, nhưng threat audit nội bộ
   cho thấy giá phải trả là thật: default `--cors-origins *` với
   `--cors-credentials` bật (bất kỳ trang web đang mở cũng **đọc** được
   response), `--api-key` default none, `/slots` bật mặc định, `--cache-prompt`
   bật mặc định (giữ prompt trước trong RAM, ngoài tầm mọi purge của MeetAI), và
   **kill switch hiện tại không với tới một process con** — `ModelSwitch.turn_off()`
   chỉ đổi một enum. Nó cũng đưa nội dung họp qua ranh giới process, ra khỏi
   vùng mà `MeetingContent` và allowlist logging có hiệu lực.
2. **Build `llama-cpp-python` từ nguồn**, cần cài MSVC + CUDA toolkit ở mức hệ
   thống — **việc cần Sơn cho phép.** Được cái giữ inference in-process, không
   listener, kill switch vẫn đúng nghĩa.

Hai đường này đánh đổi *bảo mật/độ trung thực của kill switch* với *một lần thay
đổi hệ thống*. Đó là quyết định của Sơn, không phải của benchmark.
