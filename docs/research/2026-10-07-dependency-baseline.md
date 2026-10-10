# Dependency baseline Phase 0/1

- **Ngày ghi:** 2026-10-07 (cập nhật lượt 3 sau audit)
- **Quyết định:** "FastAPI + Pydantic + pytest", kèm yêu cầu *"Trước khi thêm, ghi lại license, mục đích và dependency bắc cầu; không gửi dữ liệu ra ngoài."* Sau đó duyệt thêm **Ruff + mypy**.
- **Runtime:** Python 3.12.13 (`.python-version` + `requires-python = ">=3.12,<3.13"`), cài qua `uv python install 3.12`. Verify: `.venv/pyvenv.cfg` → `version_info = 3.12.13`.

## 1. Thay đổi lớn ở lượt 3: FastAPI/uvicorn rời khỏi installed set

FastAPI và uvicorn **không được import ở đâu trong `src/` hay `tests/`** (grep: 0 hit) — local web UI là lát S0.6, chưa làm. Chúng đã được chuyển sang `[project.optional-dependencies] ui`, nên không nằm trong `uv sync` mặc định.

Có hai lý do, lý do thứ hai mới là lý do quan trọng:

1. `AGENTS.md` cấm dependency mà yêu cầu hiện tại chưa cần.
2. **FastAPI 0.142.2 có telemetry subsystem first-party, không phải consumer thụ động của một transitive dep.** Audit truy được chuỗi import:
   ```
   fastapi/__init__.py:7          from .applications import FastAPI
   fastapi/applications.py:24-25  from fastapi.telemetry import TelemetryConfig
   fastapi/telemetry/_api.py:9-13 from opentelemetry import context, _logs, trace
   fastapi/telemetry/_asgi.py:17  from opentelemetry import _logs, metrics, propagate, trace
   ```
   `import fastapi` nạp 30 module `opentelemetry.*`. `FastAPI()._telemetry` cho thấy `auto_configure: True`, `tracing/metrics/logs: True`. `fastapi/telemetry/_runtime.py:42-70` đọc `OTEL_EXPORTER_OTLP_ENDPOINT` từ môi trường, và `_api.py:100-110` cho thấy `TelemetryData` mang cả `body` (raw request body) lẫn `errors` *"including the original input values"*.

   **Điều đang chặn export không phải là "chưa cấu hình exporter" — mà là `opentelemetry-sdk` chưa được cài.** `_runtime.py:112-131` raise `FastAPIError` khi thiếu SDK, và `_runtime.py:217-222` *bắt rồi log WARNING và bỏ qua*. Đó là một tai nạn đóng gói, không phải một control.

   Cần cả ba điều kiện mới có traffic: (a) `opentelemetry-sdk` + exporter importable, (b) một biến `OTEL_*_ENDPOINT` được đặt, (c) có ASGI lifespan startup. Một lệnh `uv add "fastapi[standard]"` là đủ cho (a).

**Đã làm để đóng:**
- FastAPI/uvicorn ra khỏi installed set → `opentelemetry-api`, `starlette`, `annotated-doc`, `certifi`, `httpx`, `anyio`, `h11`, `httpcore`, `idna` cũng rời khỏi venv.
- `tests/test_environment_invariants.py` khẳng định **không có** distribution/module OTel SDK hoặc exporter nào, và FastAPI chưa được cài. Đây là invariant đúng và dễ test, thay cho "không có exporter nào được bật".
- `load_settings()` từ chối khởi động nếu tồn tại bất kỳ biến `OTEL_*` (`PROHIBITED_EGRESS_PREFIXES`).
- `AGENTS.md` ghi điều kiện bắt buộc khi S0.6 thêm FastAPI lại: pin chính xác, telemetry tắt hoàn toàn, không bao giờ dùng `fastapi[standard]` (kéo theo `fastapi-cloud-cli`).

**Đính chính tài liệu cũ:** bản trước ghi `opentelemetry-api` vào repo "như transitive dep của `fastapi`/`starlette`". Sai một nửa: nó là hard dep của **fastapi only** (`Requires-Dist: opentelemetry-api>=1.44.0`, không có marker `extra`); `starlette` chỉ cần nó dưới extra `[full]`, không được cài.

## 2. Installed set hiện tại

`uv pip list` sau `uv sync` — 20 gói kể cả `meetai`:

```
annotated-types  ast-serialize  colorama   iniconfig   librt
meetai           mypy           mypy-extensions        packaging
pathspec         pluggy         pydantic   pydantic-core
pydantic-settings  pygments     pytest     python-dotenv
ruff             typing-extensions        typing-inspection
```

### Gói khai báo trực tiếp

| Gói | Version | License (từ dist-info METADATA) | Mục đích | Gửi dữ liệu ra ngoài? |
|---|---|---|---|---|
| `pydantic` | 2.13.5 | `License-Expression: MIT` | Response schema, validate dữ liệu biên | Không |
| `pydantic-settings` | 2.15.0 | `License-Expression: MIT` | Settings validation fail-closed | Không. Env/dotenv source **đã bị tắt** (xem dưới). |
| `pytest` (dev) | 9.1.1 | `License-Expression: MIT` | Chạy kiểm tra | Không |
| `ruff` (dev) | 0.16.10 | MIT | Lint + format | Không |
| `mypy` (dev) | 2.4.0 | MIT | Typecheck strict | Không |

### Khai báo nhưng CHƯA cài (`[project.optional-dependencies] ui`)

| Gói | Version pin | License | Khi nào cài |
|---|---|---|---|
| `fastapi` | `==0.142.2` | MIT | Lát S0.6, với telemetry tắt hoàn toàn |
| `uvicorn` | `>=0.54,<1` | BSD-3-Clause | Cùng S0.6 |

### Ghi chú kỹ thuật: tại sao env source của pydantic-settings bị tắt

`settings_customise_sources` chỉ trả về `(init_settings,)`. Không phải vì phong cách: dotenv source biến một key lạ thành lỗi `extra_forbidden` mà **payload là giá trị thô** — nên một credential gõ sai tên trong `.env` (đúng cái mà guard tồn tại để bắt) sẽ bị in ra. `load_settings()` tự đọc `.env` qua `python-dotenv`, kiểm tra **tên trước**, và chỉ đưa giá trị của field đã nhận dạng vào pydantic.

## 3. License: đã verify từ wheel metadata thật

Audit đọc `*.dist-info/METADATA` và file license trong `*.dist-info/licenses/` của **toàn bộ** 25 gói ở bản cài trước. Kết quả:

- **Cả 6 license ghi trong bản tài liệu đầu đều ĐÚNG.** fastapi MIT, pydantic MIT, pydantic-settings MIT, uvicorn BSD-3-Clause, pytest MIT, httpx BSD-3-Clause. Caveat "chưa đọc file LICENSE" đã được rút cho 6 gói này.
- **Không có GPL / LGPL / AGPL / license thiếu ở bất kỳ gói nào.**
- Phát hiện quan trọng mà bản cũ bỏ sót: **`certifi` 2026.7.22 là MPL-2.0 (weak copyleft)**. Nó vào repo qua `httpx` (dev-only). Nghĩa vụ chỉ phát sinh nếu *sửa* file nguồn của certifi hoặc đóng gói thành binary Windows. **Sau lượt 3, `httpx` và `certifi` đã rời khỏi venv**, nên MPL-2.0 không còn trong cây dependency.
- `typing-extensions` 4.16.0 là **PSF-2.0** (permissive, GPL-compatible) — bản cũ không nêu.
- `packaging` 26.3 là dual **`Apache-2.0 OR BSD-2-Clause`**.
- `colorama` 0.4.6 **không có field `License:` trong METADATA**, chỉ có `Classifier: BSD License`. Đọc file thì là 3-clause BSD. Nghĩa là tool SBOM tự động sẽ báo "BSD (unspecified)" — cần override tay nếu sau này thêm license gate.
- **`meetai` trước đây không khai license nào.** Đã thêm `license = "MIT"` vào `pyproject.toml`.

## 4. Lockfile và pin

- `uv.lock` `requires-python = "==3.12.*"` — là dạng normalize của `>=3.12,<3.13`, **không xung đột**.
- Mọi gói registry trong lock đều pin version chính xác kèm `sha256` cho cả sdist và wheels (verify 25/25 ở bản cài trước). `meetai` là `editable = "."`, không hash — đúng và dự kiến.
- **Đã sửa ở lượt 3:** `pyproject.toml` trước đây chỉ có floor pin (`fastapi>=0.115`, `pydantic>=2.9`...). Đó chính là cách `fastapi` 0.142.2 trôi tới và kéo `opentelemetry-api` vào im lặng. Giờ mọi dependency đều có upper bound, nên `uv lock --upgrade` trở thành việc review được.
- **Còn lại:** `.python-version` pin `3.12` chứ không phải `3.12.13`. Trên máy sạch `uv` sẽ lấy 3.12.x hiện hành. Vô hại với các gói pure-Python/ABI-stable hiện tại. **[ĐỀ XUẤT]** pin patch nếu cần interpreter byte-identical.

## 5. Python 3.12 cho ML: pin ĐÃ ĐƯỢC VERIFY, nhưng lý do thì khác

Audit truy vấn PyPI JSON API và wheel index của PyTorch, đọc tên file wheel thật. **Kiểm tra ngày 2026-10-07.**

| Gói | Latest | cp312 win_amd64? | Python mới nhất hỗ trợ |
|---|---|---|---|
| torch | 2.14.1 | **CÓ** (`torch-2.14.1-cp312-cp312-win_amd64.whl`; cả `+cu126`, `+cu130`, `+cu132`) | cp315 |
| ctranslate2 | 4.8.2 | **CÓ** | cp314 |
| onnxruntime-gpu | 1.30.0 | **CÓ** | cp314; **floor là `requires_python >=3.11`** |
| faster-whisper | 1.2.1 | **CÓ** (pure Python) | không giới hạn |
| transformers | 5.19.0 | **CÓ** (pure Python) | không giới hạn |
| llama-cpp-python | 0.3.36 | **KHÔNG — PyPI chỉ có sdist** | prebuilt off-PyPI: CPU tới 0.3.19, CUDA tới 0.3.4 |

**Kết luận: pin 3.12 là ĐÚNG, nhưng lý do ban đầu đã lỗi thời.** "3.12 có diện wheel rộng nhất" đúng vào 2024; tính đến 2026-10-07 **cp313 được phủ tương đương**. 3.12 giờ là **lựa chọn bảo thủ nhất trong nhiều lựa chọn phủ tương đương** — vẫn là quyết định đúng cho pilot, nhưng là một lập luận khác. Chỗ diện wheel **thật sự** mỏng đi là **3.14+**: prebuilt index của llama-cpp-python dừng ở cp313, và `torch.compile` không hỗ trợ 3.15. **Không đi quá 3.13.**

Ghi chú bảo vệ: `onnxruntime-gpu` 1.30.0 khai `requires_python >=3.11`. Nếu trước đó pin 3.10 "cho phủ wheel tối đa" thì giờ đã không dùng được.

### Rủi ro thật cho S2.1 là CUDA và build toolchain, không phải phiên bản Python

1. **Phân mảnh CUDA major — CAO, cần quyết định trước khi cài.** torch default wheel là CUDA 13.0 nhưng cũng build cu126; ctranslate2 docs chỉ ghi *"Install CUDA 12.x to use the GPU"*; `onnxruntime-gpu[cuda]` pin runtime CUDA 13 (`nvidia-cuda-runtime~=13.0`). Cài cả ba vào một venv là trộn CUDA major. **[ĐỀ XUẤT] chuẩn hóa về CUDA 12.x**: torch từ index `cu126`, ctranslate2 nguyên bản, onnxruntime-gpu biến thể CUDA 12.8. Phải verify bằng thực nghiệm.
2. **sm_75 (GTX 1660 Ti) được hỗ trợ nhưng đã là sàn — TRUNG BÌNH.** CUDA 13.0 bỏ Maxwell/Pascal/Volta, Turing (7.5) thành kiến trúc cũ nhất còn hỗ trợ. Card chạy được, nhưng nằm trên biên deprecation. Thêm một lý do ưu tiên nhánh CUDA 12.x.
   **[CHỜ BẰNG CHỨNG]** Audit thấy một claim "cuDNN 9.x cho CUDA 13.x không hỗ trợ Windows" nhưng **không xác minh được từ nguồn NVIDIA/PyTorch chính thức** — không được coi là sự thật.
   **[CHỜ BẰNG CHỨNG]** Ngân sách 6 GB VRAM: chưa có gì kiểm tra một LLM lượng tử hóa + Whisper có vừa 6 GB hay không. Cần thực nghiệm ở S2.1.
3. **`llama-cpp-python` không có prebuilt Windows wheel hiện hành — CAO, đây là blocker khó nhất.** `uv add llama-cpp-python` sẽ cố build CMake + MSVC tại máy. Lựa chọn cần đánh giá ở S2.1: chấp nhận build từ nguồn, pin wheel CPU 0.3.19, hoặc dùng llama.cpp server binary qua localhost HTTP (giữ hẳn build C++ ra khỏi env Python).
4. **`faster-whisper` kéo theo `huggingface-hub` (tải model qua mạng theo thiết kế) và `av` (bundle FFmpeg) — TRUNG BÌNH, liên quan trực tiếp ràng buộc privacy.** Cần policy fail-closed tường minh: pre-stage weights + offline mode. Lưu ý `faster-whisper` depend `onnxruntime` (CPU) chứ không phải `onnxruntime-gpu` — phải hòa giải để không cài cả hai.

## 6. Supply-chain surface: đã verify sạch

Audit `sys.addaudithook` bắt mọi event `socket*`/`urllib*`/`http.client*`/`ssl.*`/`subprocess*` khi import toàn bộ 25 gói ở bản cài trước: **EVENTS: NONE**.

- **Không gói nào có `setup.py`/`setup.cfg`** → không có đường thực thi code lúc install. Tất cả cài từ binary wheel.
- **Không post-install script.**
- **Binary bundle: đúng một cái** — `pydantic_core/_pydantic_core.cp312-win_amd64.pyd`, wheel build bằng maturin (Rust/PyO3), MIT, hash-pinned trong lock. Đây là dependency duy nhất **không audit được bằng cách đọc Python source**; hash pin là mitigation.
- **Không telemetry nào được bật.** Grep `posthog|segment|sentry_sdk|mixpanel|amplitude|scarf` chỉ ra false positive trong keyword list của pygments lexer.
- `_virtualenv.pth` chạy code mỗi lần interpreter start — đây là machinery chuẩn của virtualenv, không phải dependency, nhưng là hook import-time duy nhất trong env.
- `certifi` từng mang theo trust store 240 KB (`cacert.pem`) — **đã rời khỏi venv** ở lượt 3.

## 7. Còn chờ

- **[CHỜ BẰNG CHỨNG]** Toàn bộ mục 5: chưa cài gói ML nào. Thuộc S2.1.
- **[ĐỀ XUẤT]** Pin `.python-version` xuống patch level.
- **[ĐỀ XUẤT]** Nếu thêm license gate tự động: override tay cho `colorama`.

---

# Cập nhật lượt 6 (S0.6): extra `ui` đã được cài

Sơn duyệt: *"có thể thêm FastAPI và Uvicorn vào extra phù hợp, project-local, có pin và inventory; chỉ bind loopback."* Đây là hoãn theo thời điểm đã kết thúc, không phải một lựa chọn mới.

## Gói mới trong installed set

`uv sync --extra ui` + `httpx` (dev, cho `fastapi.testclient`). Từ 20 lên **32** gói.

| Gói | Version | License | Vì sao có | Gửi dữ liệu ra ngoài? |
|---|---|---|---|---|
| `fastapi` | **==0.142.2** (pin chính xác) | MIT | Local web UI | Không — telemetry tắt tường minh, xem dưới |
| `uvicorn` | 0.54.0 | BSD-3-Clause | ASGI server, bind loopback | Không — `access_log=False`, `log_config=None` |
| `starlette` | 1.7.0 | BSD-3-Clause | của fastapi; `TrustedHostMiddleware` dùng trực tiếp | Không |
| `opentelemetry-api` | 1.45.1 | Apache-2.0 | **hard dep không tránh được** của fastapi | Không — chỉ API layer, SDK không cài |
| `annotated-doc` | 0.0.5 | MIT | hard dep của fastapi | Không |
| `anyio` | 4.15.1 | MIT | của starlette | Không |
| `idna` | 3.20 | BSD-3-Clause | của anyio | Không |
| `click` | 8.5.0 | BSD-3-Clause | của uvicorn | Không |
| `h11` | 0.16.0 | MIT | HTTP/1.1 của uvicorn | Không |
| `httpx` (dev) | 0.28.1 | BSD-3-Clause | `fastapi.testclient` | Không — chỉ gọi app in-process |
| `httpcore` (dev) | 1.0.9 | BSD-3-Clause | của httpx | Không |
| `certifi` (dev) | 2026.7.22 | **MPL-2.0** | của httpx/httpcore | Không — trust store thụ động |

**`certifi` MPL-2.0 quay lại cây dependency**, chỉ ở nhóm dev qua `httpx`. Weak copyleft ở mức file: nghĩa vụ chỉ phát sinh nếu *sửa* file nguồn của certifi, hoặc nếu đóng gói thành binary Windows (khi đó phải kèm notice và cách lấy source). MeetAI import nguyên bản nên hiện không phát sinh gì. Nó cũng ship trust store 240 KB — blob dữ liệu giá trị cao nhất trong venv, pin bằng sha256 trong lock.

## Vì sao pin **chính xác** `fastapi==0.142.2`

Không phải thói quen. FastAPI 0.142 có telemetry subsystem first-party, và **đã verify trên bản cài thật** rằng `FastAPI()` mặc định resolve ra:

```
tracing=True  metrics=True  logs=True  operation_spans=True  auto_configure=True
```

`logs` ghi exception message **và** request body **và** validation error *kèm giá trị input gốc*. Endpoint exporter đọc từ `OTEL_EXPORTER_OTLP_ENDPOINT`.

Một pin `>=` **không giữ được** một lần review về default telemetry: version sau có thể thêm signal thứ sáu mặc định bật. Với pin chính xác, nâng version là một hành động có chủ ý, và test assert exact-dict sẽ fail đến khi signal mới được tắt tường minh.

## Ba extra kéo SDK, không phải một

`fastapi-0.142.2.dist-info/METADATA`: các extra `opentelemetry`, `standard`, `standard-no-fastapi-cloud-cli` và `all` **đều** require `opentelemetry-sdk` + `opentelemetry-exporter-otlp-proto-http`. `AGENTS.md` trước đây chỉ cấm `fastapi[standard]` — không đủ.

Có test cấm `fastapi-cloud-cli`, `fastapi-cli`, `fastar`, `logfire`, và mọi `opentelemetry-sdk`/`-exporter-*`. `logfire` không phải giả thuyết: `_runtime.py` có nhánh tương thích riêng cho meter provider của logfire.

## `opentelemetry-api` không tránh được — và test phải biết điều đó

`Requires-Dist: opentelemetry-api>=1.44.0`, **không** marker `extra`, và `fastapi/telemetry/_api.py` import nó ở module scope. Nên `import fastapi` luôn import opentelemetry.

Điều đó **không sao**: không có SDK thì provider của API là no-op (`NoOpTracerProvider`, `NoOpMeterProvider` trong `entry_points.txt`). Có một test ghi rõ sự phân biệt này, để sau không ai "làm cứng" suite bằng cách cấm luôn package api và làm UI hỏng.

## Bề mặt supply-chain mới

- **[CHƯA VERIFY]** Wheel của FastAPI ship `.agents/skills/fastapi/SKILL.md` cộng sáu file `references/*.md` — text của bên thứ ba đặt vào một đường tìm kiếm agent-skill. Tôi chưa kiểm liệu tooling agent có discover `.agents/` trong site-packages hay không. Không phải đường egress, nhưng là text không tin cậy nằm ở một chỗ có thể bị đọc thành chỉ thị.
- **[CHƯA VERIFY]** `--reload`/`--workers` của uvicorn có re-import gì liên quan telemetry trong child process không. S0.6 chạy single-process, reload tắt.
- `starlette.testclient` cảnh báo deprecation, khuyên `httpx2` thay `httpx`. Dev-only, chưa đổi.

## `/docs` là đường egress phía browser

`/docs` serve HTML trỏ `cdn.jsdelivr.net`; `/redoc` thêm `fonts.googleapis.com`; cả hai lấy favicon từ `fastapi.tiangolo.com`. Mở một trang là browser liên lạc bốn host thứ ba.

Guard `MEETAI_*` và `OTEL_*` **không thấy được** việc này — request đi từ browser, không từ tiến trình này. Đã tắt cả ba đường; có test assert 404 **và** không response nào chứa host ngoài loopback.

---

## Phụ lục — môi trường benchmark S2.1 (2026-10-07, lượt 8)

**Không gói nào dưới đây là dependency của `meetai`.** `pyproject.toml` và
`uv.lock` **không đổi** ở lát S2.1; verify bằng `git diff --stat HEAD` (rỗng) và
`uv pip list` (vẫn 32 gói, 0 gói khớp `torch|nvidia|llama|ctranslate|onnx|transformers`).

Chúng nằm trong một venv riêng ở `var/bench-venv/` (gitignored). Lý do tách hẳn
chứ không làm một extra: hai trong số đó là **proprietary**, khác hẳn mọi
dependency hiện có của dự án, và không có lý do để chúng xuất hiện trong
installed set của app.

| Gói | Version | License | Vì sao |
|---|---|---|---|
| `llama-cpp-python` | 0.3.36 (index `cu125`) | MIT | Thử đường 2. **Kết quả: không dùng được** — crash `STATUS_ILLEGAL_INSTRUCTION` vì `ggml-cpu.dll` build bật AVX-512, CPU này không có. |
| `nvidia-cuda-runtime-cu12` | 12.9.79 | **`LicenseRef-NVIDIA-Proprietary`** ⚠️ | Cung cấp `cudart64_12.dll` mà không cần cài CUDA toolkit |
| `nvidia-cublas-cu12` | 12.9.2.10 | NVIDIA proprietary ⚠️ | `cublas64_12.dll`, `cublasLt64_12.dll` |
| `nvidia-cuda-nvrtc-cu12` | 12.9.86 | NVIDIA proprietary ⚠️ | transitive |
| `numpy` | 2.5.3 | BSD-3-Clause | transitive của llama-cpp-python |
| `diskcache`, `jinja2`, `markupsafe` | — | Apache-2.0 / BSD-3 | transitive của llama-cpp-python |
| `ctranslate2` wheel | 4.8.2 | MIT | **Chỉ tải để đọc, không cài.** Dùng để verify nó cần `cublas64_12.dll` — căn cứ cho quyết định nhánh CUDA. |

**Binary native ngoài phạm vi audit.** llama.cpp `b11464` là blob native chưa
được audit; `sys.addaudithook` ở mục trên chỉ bao phủ installed set Python. Hash
trong [model ledger](2026-10-07-model-artifacts.md) là cơ chế duy nhất hiện có.

**Bất biến OTel vẫn đúng:** `uv run pytest -q` → 1368 passed, 3 skipped, trong đó
có test khẳng định không distribution OTel SDK/exporter nào importable.
