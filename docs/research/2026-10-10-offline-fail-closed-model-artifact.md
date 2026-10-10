---
title: "S2.1 — offline fail-closed cho model artifact"
date: "2026-10-10"
revision: "2d69797"
status: "nghiên cứu; mục 2b và 2c đã đóng (lượt 25, 26), phần còn lại chờ Sơn"
last_updated: "2026-10-10 (lượt 28)"
---

# Offline fail-closed cho model artifact (S2.1)

**Revision đo:** `2d69797`, 73 commit, working tree sạch (`git status --porcelain`
exit 0, không output). **Không tải model, không gọi GPU, không cài dependency,
không mở server.**

`docs/plan.md:150` ghi tiêu chí *"`huggingface-hub` offline fail-closed"* là
**CHƯA**. Lát này đo lại và kết luận rằng **câu hỏi đã được đặt sai**: không có
`huggingface-hub` nào trong hệ thống, và đường đi hiện tại **đã fail-closed ở
chiều quan trọng nhất** — nhưng **hở ở hai chiều khác** mà tiêu chí cũ không
nêu.

## 1. Luồng thực tế hôm nay — đo, không suy

| | |
|---|---|
| `huggingface_hub` | **chưa cài** (`importlib.util.find_spec` → None). `transformers`, `torch`, `requests`, `urllib3` cũng vậy. **`httpx` CÓ** — dev dep cho FastAPI `TestClient`, nên **không được** nói "venv không có HTTP client" |
| Cách weights tới máy | **`curl` thủ công**, `benchmarks/README.md`, URL pin **commit 40 ký tự** (`.../resolve/bc640142c66e1fdd12af0bd68f40445458f3869b/...`) — **không** phải `main` |
| Cách digest được kiểm | `sha256sum` rồi **người đọc so bằng mắt** với comment `# phai bang: <64 hex>` trong README |
| Artifact trên đĩa | `models/{asr,llm}`, 4 file ≈ 5 GB, **gitignored** (`.gitignore`: `models/`, `*.gguf`, `var/`, `data/`) |
| Cách benchmark tìm artifact | **đường dẫn local thuần**, `argparse --model`, rồi `pathlib.Path(...).is_file()` |
| Khi artifact vắng | **`return 2` trước mọi loader/subprocess** |
| Có đường tải trong code? | **KHÔNG.** 0/16 file `benchmarks/` import bất cứ gì có khả năng ra mạng |

**Đo fail-closed bằng audit hook** (`sys.addaudithook`, bắt `socket.*`,
`urllib.*`, `http.*`, `subprocess.*`, `ssl.*`, `os.exec*`):

```
bench_llm_policy  --model <absent>   → exit 2, 0 network event, không ghi output
bench_asr         --model <absent>   → exit 2, 0 network event
```

Nên **tiêu chí "không thử truy cập mạng khi thiếu model" đã ĐẠT**, và đạt theo
cách mạnh nhất có thể: **không có code tải nào để vô hiệu hoá**. Đó không phải
một cờ cấu hình — đó là sự **vắng mặt của năng lực**.

## 2. Ba chỗ hở — đo được

### 2a. Digest được GHI, không được CƯỠNG CHẾ ⚠️

`sha256(model)` có **đúng một** call site: `bench_llm_policy.py:639`, **bên
trong record output**, tức **sau** khi cả run đã xong. `--no-hash` bỏ luôn cả
việc ghi.

**Không một file `.py` nào** trong `src/`, `benchmarks/`, `tests/` chứa bất kỳ
digest nào của ledger. Kiểm 12 digest trong
`docs/research/2026-10-07-model-artifacts.md`: 2 cái xuất hiện trong repo, và
**cả hai ở `benchmarks/README.md`** — dưới dạng `# phai bang:`, tức **chỉ thị
cho người**, không phải code.

Nên **ledger nối với thực tế chỉ qua một câu lệnh README và một con mắt**. Một
file đúng tên, đúng kích thước, sai nội dung sẽ **chạy hết run** rồi mới xuất
hiện trong report — và nếu dùng `--no-hash` thì không xuất hiện ở đâu cả.

Và `plan.md:396` ghi *"SHA-256 model harness **tự tính lại** và khớp ledger"* —
đúng ở chữ *"tự tính lại"*, **nói quá** ở chữ *"khớp"*: harness **tính và ghi**;
việc **so khớp** do người làm. Đã sửa lại trong `plan.md` ở lát này.

### 2b. Guard import của benchmark chỉ phủ 3/16 file — **ĐÃ SỬA ở lát này** ✅

`tests/test_llm_boundary.py::TestTheBenchmarkHasNoEgress` cấm
`huggingface_hub`, `socket`, `urllib`… nhưng chạy trên một tuple **ghi tay 3
file** (`bench_llm_policy`, `policy_scoring`, `rescore_llm_policy` — harness
S2.3). **13 file còn lại không được phủ**, trong đó có
**`make_vietmed_manifest.py`** — đúng loại script sẽ muốn tải dataset.

Đo được: **0/16 file** hiện import gì có khả năng ra mạng, nên đây là lỗ
**tiềm ẩn**, không phải đang chảy. **Cùng hình dạng với lỗ media**: guard tồn
tại, và **độ phủ** của nó là phần không ai kiểm.

**Đã đóng ở lát này**, bằng cách cho `ALL_BENCHMARK_FILES` **tự phát hiện bằng
glob** thay vì ghi tay, cộng một test khẳng định phép phát hiện tìm ra ≥16 file
và bằng đúng những gì trên đĩa (một glob không khớp gì là một test pass miễn
phí). Mở rộng **độ phủ**, **không** đổi tập bị cấm — thêm
`huggingface_hub`/`torch` vào tập đó là một quyết định của Sơn, nêu ở mục 5.

### 2c. Thông báo từ chối LỘ đường dẫn tuyệt đối và tên người dùng — **ĐÃ ĐÓNG (lượt 26)**

```
--model C:/Users/canary-operator/secret-staging/nope.gguf
→ stderr: "khong tim thay model: C:/Users/canary-operator/secret-staging/nope.gguf"
```

Lộ **cả đường dẫn tuyệt đối lẫn username**. `AGENTS.md` yêu cầu *"exception
message mô tả hình dạng, không bao giờ mô tả giá trị"*, và có
`tests/test_no_value_in_errors.py` cưỡng chế — nhưng nó scope vào
`SRC = src/meetai` nên **`benchmarks/` nằm ngoài**.

#### Lượt 26: đo lại thì lỗ rộng gấp sáu lần mục này ghi

Mục 2c ở trên đo **một** CLI rồi mô tả lỗ như một lỗ. Chạy canary qua mọi
nhánh từ chối sớm cho thấy **6 file / 7 nhánh** cùng in đường dẫn của người
chạy:

| File | Nhánh | Wording cũ |
|---|---|---|
| `bench_llm_policy.py` | binary, model | `khong tim thay {binary,model}: {args...}` |
| `bench_llm.py` | model | `model khong ton tai: {args.model}` |
| `bench_asr.py` | whisper / manifest / model | `khong ton tai: {path}` |
| `bench_coresidency.py` | llama / whisper / llm / asr / clip | `khong ton tai: {path}` |
| `bench_llamacpp.py` | model / llama-bench binary | `khong ton tai: {required}` |
| `postprocess_asr.py` | results / tsv / manifest | `khong ton tai: {path}` |

**Đóng bằng allowlist, không bằng denylist.** `benchmarks/refusals.py` (mới,
zero dependency, ASCII) giữ `ARTIFACT_ROLES` — 10 member đóng kín — và
`missing_artifact(role)` **raise** nếu role không thuộc đó. Thông báo thành
`artifact-missing: llm-model (duong dan khong duoc in)`. Một denylist "chuỗi
trông nhạy cảm" sẽ thua ngay cái tên đối số mới đầu tiên — **cùng lý lẽ đã
dùng cho `state_dir` và cho allowlist `ALLOWED_FIELDS` của formatter log**.

**Thông báo mới DIAGNOSTIC HƠN cái cũ ở 4/6 file.** Ba nhánh kiểu
`for path in (WHISPER, args.manifest, args.model)` in một đường dẫn nhưng
**không bao giờ nói** đối số nào sai; `artifact-missing: manifest` thì nói.
Nên đây không phải đánh đổi an toàn-đổi-lấy-tiện-dụng.

**Ghim bởi `tests/test_benchmark_refusal_leaks.py`** — 12 test, ba loại, vì
loại hiển nhiên pass miễn phí ("canary không xuất hiện" cũng đúng với một
`main()` không in gì):

1. **hành vi** — 7 nhánh: exit đúng 2, có mã ổn định, role thuộc allowlist,
   canary vắng ở `stdout`, `stderr` **và** text exception;
2. **control** — cắm lỗ rò tổng hợp và khẳng định chính checker đó từ chối
   nó, **gồm cả lỗ chỉ-basename** mà phép kiểm cả-đường-dẫn sẽ bỏ qua; cộng
   một control cho resolver cấu trúc;
3. **cấu trúc** — mọi call site phải **giải được về literal** trong
   allowlist, vì `missing_artifact(str(path))` sẽ qua được (1) và (2) trên
   những nhánh không ai chạy.

**Đo được là test đỏ trước khi sửa: 9 fail / 2 pass.** Và hai mutation check
bị bắt bởi **hai test khác nhau**: phục hồi wording cũ → regression pin fail;
`missing_artifact(str(args.model))` → resolver cấu trúc fail.

#### Lượt 27: độ phủ thật của phép sửa đó là 7/16 nhánh, nay là 16/16

Mục trên ghi *"6 file / 7 nhánh"*. **Số nhánh sai.** Đếm từ AST, sáu CLI có
**16** kiểm tra artifact — 7 là số **ca test**, không phải số nhánh:

| Module | Số kiểm tra | Role, theo thứ tự đánh giá |
|---|---|---|
| `bench_asr` | 3 | `whisper-binary`, `manifest`, `asr-model` |
| `bench_coresidency` | 5 | `llama-binary`, `whisper-binary`, `llm-model`, `asr-model`, `audio-clip` |
| `bench_llamacpp` | 2 | `llm-model`, `llama-bench-binary` |
| `bench_llm` | 1 | `llm-model` |
| `bench_llm_policy` | 2 | `llm-binary`, `llm-model` |
| `postprocess_asr` | 3 | `results-json`, `reference-tsv`, `manifest` |
| | **16** | |

**Và đó không chỉ là lỗi đếm.** Mỗi CLI dừng ở input **thiếu đầu tiên**, nên
nhánh nào được chạm **phụ thuộc máy**: cả hai binary dưới `var/` **đều có** trên
máy phát triển, nên `bench_asr` chạm `manifest` và nhánh `whisper-binary` của nó
**chưa bao giờ chạy**. Trên checkout mới, cùng test đó pass nhưng chạy nhánh
khác — và assertion cũ chỉ đòi role **thuộc allowlist**, nên không nhận ra.
**Độ phủ thật: 7/16 nhánh, 4/10 role.**

**Sửa (test-only, lượt 27):** mỗi nhánh một ca. Prerequisite dàn bằng placeholder
trong `tmp_path`; `WHISPER`/`LLAMA`/`BUILD_DIR` **monkeypatch** nên không ca nào
đọc `var/`; nhánh đích **và mọi nhánh sau** mang canary, nên nếu nhánh đích không
fire thì một nhánh sau fire với role khác và ca **fail** thay vì chạy benchmark.
Role phải **khớp chính xác**. Một *fence* monkeypatch `subprocess`/`preload_cuda`/
`gpu_benchmark_lock` để một test lọt qua chuỗi kiểm tra fail to tiếng thay vì
khởi động model.

**Ma trận được khẳng định bằng AST**, không bằng chính nó
(`test_the_matrix_matches_the_source`, theo thứ tự), cộng **10/10 role** được
chạm. Đó là thứ cho phép ghi "16/16"; trước đó con số chỉ là lời khẳng định.

**Bốn mutation đều bị bắt**: role hợp lệ-nhưng-sai; nhánh **cuối** của
`bench_coresidency` in path trực tiếp (**một trong 9 nhánh lượt 26 không chạm** —
test cũ sẽ pass); harness ngừng dàn prerequisite; và nhánh thứ **17** không có ca.
`test_benchmark_refusal_leaks.py`: **12 → 28 test**.

**Phần dư, cố ý không sửa:** đường **thành công** vẫn in đường dẫn —
`written: {target}` ×5, `manifest: {target}`, và `bench_llm_policy.py:503-504`
in basename model. Đổi chúng sẽ đổi nội dung artifact của các lần đo đã có.
`gpulock.py:141` nhúng đường dẫn tuyệt đối của lock vào exception — đường dẫn
repo cố định, đã được docstring khai, và đổi nó sẽ đụng hành vi lock mà
`test_bench_harness.py` đang ghim.

### 2d. Đường tải ĐÃ được link vào thư viện inference ⚠️ **nặng nhất**

`var/bench-venv/Lib/site-packages/llama_cpp/llama.py:2331` có
`Llama.from_pretrained`, và thân nó làm đúng việc ta không muốn:

```
:2356  from huggingface_hub import hf_hub_download, HfFileSystem
:2366  hffs = HfFileSystem()
:2400  hf_hub_download(...)
```

Đo được: `huggingface_hub` **vắng ở cả hai** bench venv, nên hôm nay nó raise
`ImportError`. Nghĩa là **đường tải đã nằm trong thư viện**, cách một
`pip install` — và **thứ chặn nó là một package vắng mặt, không phải một
guard**.

Đó **chính xác** là hình dạng phòng vệ OTel-SDK mà `AGENTS.md:69` mô tả. Khác
biệt quan trọng: OTel-SDK **có** test ghim sự vắng mặt đó
(`test_environment_invariants.py` assert `PackageNotFoundError`), còn
`huggingface_hub` thì **không có test nào**. `uv add huggingface-hub` hôm nay
qua toàn bộ suite.

**Và hai bench venv nằm ngoài `uv.lock`.** `var/bench-venv` (llama_cpp_python
0.3.36) và `var/bench-cpu-venv` (0.3.19) không nằm trong lockfile và **không
test nào soi chúng** — `llama-cpp-python` vắng ở `.venv` của dự án, nên
`bench_llm.py:72 from llama_cpp import Llama` **không chạy được dưới `uv run`**
hôm nay; nó chỉ chạy dưới hai venv kia.

### 2e. `--no-hash` đã được dùng thật, không phải giả định

Trong 7 artifact đo S2.3 ở `var/bench/`:

| | |
|---|---|
| 5 file | `"sha256": "7485fe6f11af…"` — khớp ledger |
| **2 file** | **`"sha256": "skipped"`** — `llm-policy-s23-power.json`, `llm-policy-smoke.json` |

Nên cờ override **không phải nguy cơ lý thuyết**: hai lần đo đã chạy mà
**không có bản ghi provenance nào cả**, và field thậm chí **không ổn định
kiểu** — một consumer không thể giả định nó là digest.

*(`var/` **gitignored**, nên đây là artifact đo cục bộ, **không** phải file đã
commit.)*

### 2f. Binary mở cổng mạng nằm trên đĩa, không ai nói gì về chúng

`var/llamacpp/b11464/` chứa `llama-server.exe`, `llama-server-impl.dll`,
`ggml-rpc-server.exe`, `ggml-rpc.dll`.

#### Lượt 28: mục này đếm thiếu, và grep không đóng được nó

**Thiếu một binary thứ năm.** Đo được còn
**`var/whispercpp/b5454/Release/whisper-server.exe`** (728576 byte). Bản ghi
trên chỉ soi `var/llamacpp/`, nên nó bỏ qua artifact listener của whisper.cpp
do cùng loại archive giải nén ra.

**Và `grep -rn "rpc\|llama-server" benchmarks/` → 0 hit không phải bằng
chứng đầy đủ.** AST cho thấy `argv[0]` là **biến hoặc lời gọi helper ở 7
trong 9** spawn site: `command`, `executable`, `llm_command(...)`,
`asr_command(...)`. Giải ra, tập binary thật mà `benchmarks/` có thể spawn là:

| Binary | Nguồn |
|---|---|
| `nvidia-smi` | `measure.py:58`, `bench_coresidency.py:64` |
| `tasklist` | `measure.py:155` |
| `llama-bench.exe` | `bench_llamacpp.py:90`, `bench_coresidency.py:46` |
| `llama-cli.exe` | `bench_llm_policy.py:445` (mặc định `--binary`) |
| `whisper-cli.exe` | `bench_asr.py:55`, `bench_coresidency.py:47` |

`src/` có **0 spawn site**. Không có launcher `.ps1`/`.bat`/`.cmd`/`.sh` nào
được track — đáng kiểm, vì một script như vậy sẽ **bỏ qua Python hoàn toàn**.

**Đã ghim (lượt 28)** ở `tests/test_llm_boundary.py`: allowlist executable khớp
**fragment** (`llama-server`, `ggml-rpc`, `rpc-server`, `whisper-server`) thay vì
khớp tên file, nên một bản build đổi tên vẫn bị bắt; cộng khẳng định allowlist
**tự nó** không chứa server, và không launcher ngoài Python nào được track. **Ba
mutation, bắt bởi hai cơ chế khác nhau.**

**Lỗ còn lại — cần Sơn quyết, không tự chọn:** `bench_llm_policy.py:445` nhận
`--binary` là **chuỗi tự do**, giải qua `shutil.which` ở `:471`. Nên
`--binary var/llamacpp/b11464/llama-server.exe` **chạy được hôm nay** và không gì
từ chối. Việc harness có nên từ chối executable **theo tên** là quyết định chính
sách về thứ nó được phép chạy.

## 3. Hai lỗ hổng của *mọi* phương án — đo trên máy này

| Phép thử | Kết quả |
|---|---|
| `os.link` (hardlink) vào staging, target **ngoài** staging | **thành công, không cần quyền admin**. `is_file()` True, `is_symlink()` **False**, và `resolve()` **vẫn nằm trong** staging |
| `Path.symlink_to` | **bị từ chối**, `winerror 1314` (không có quyền) |
| AST import check với `importlib.import_module("huggingface_hub")` | **không thấy gì** — AST chỉ thấy `['importlib']` |

Hệ quả phải ghi thẳng, theo đúng kiểu `AGENTS.md`:

- **Phép kiểm chứa đường dẫn KHÔNG giới hạn được bytes nào bị đọc.** Một
  hardlink đi qua mọi phép kiểm `resolve()`-prefix. Thứ duy nhất chặn được là
  **digest**. (`st_nlink > 1` là tín hiệu phát hiện được, nhưng nó không phải
  phép kiểm nội dung.)
- **AST không phải phép kiểm mạng**, nó là phép kiểm **hình dạng source**. Một
  import động đi qua nó. Nên nó phải là **một lớp trong nhiều lớp**, không phải
  lớp duy nhất — đúng lý lẽ ba-lớp của authority gate.

## 4. So sánh ba phương án — không cài gì

### Phương án A — đường local + digest **được cưỡng chế**, giữ Hub ngoài runtime

| | |
|---|---|
| **Dependency** | **KHÔNG CÓ.** `hashlib`, `pathlib`, `os` là stdlib |
| **Failure mode** | File vắng / sai kích thước / sai digest → raise **trước** khi gọi loader. Đã đo: chiều "vắng" hoạt động hôm nay |
| **Nguy cơ fallback mạng** | **Về cấu trúc là không**: không có code tải nào để cấu hình sai. Không cờ nào, không biến môi trường nào bật nó lên được |
| **Tái lập** | Digest 64 hex trong một constant đã commit, chéo-kiểm với ledger bằng test |
| **Còn thiếu** | Cưỡng chế digest (2a). *(Vá lộ đường dẫn (2c): **đã làm ở lượt 26**.)* |

### Phương án B — `huggingface_hub` + offline mode tường minh

Tra tài liệu chính thức **2.2.0** (chưa cài, nên **không introspect được** —
mọi điều dưới đây từ tài liệu/source upstream, và cần **đo lại sau khi cài**):

| Phát hiện | Vì sao nó quan trọng ở đây |
|---|---|
| `HF_HUB_OFFLINE=1` chặn ở **event hook của client HTTP** | Mạnh — nhưng là **cấu hình**, không phải vắng mặt |
| Lỗi khi artifact không có cache là **`LocalEntryNotFoundError`** — **cùng type** cho "offline" và "mạng chết", và message còn bảo *"check your connection"* | **Không phân biệt được bằng type.** Một thiết kế fail-closed phải tự gọi `is_offline_mode()` hoặc dò `__cause__` |
| `revision="main"` giải quyết từ **`refs/` trên đĩa** — nội dung là *"commit tải lần cuối trên máy này"* | **Thay artifact im lặng.** Một lần chạy online ở đâu đó ghi lại `refs/main`, lần offline sau nạp **artifact khác**, không lỗi, không cảnh báo. Chỉ **hash commit 40 ký tự** đi vòng qua `refs/` |
| **Không verify toàn vẹn khi nạp từ cache** — chỉ kiểm tồn tại | Đúng cái lỗ 2a, nhưng giờ nằm trong thư viện |
| Windows không có developer mode → **bỏ lớp `blobs/` đặt tên theo hash** | **Đã đo trên máy này: symlink bị từ chối, winerror 1314.** Nên đây là đường áp dụng, và lớp "tên file chính là hash" biến mất |
| Cache mặc định `~/.cache/huggingface` — **ngoài thư mục dự án** | Đụng thẳng quy tắc đường-dẫn-tương-đối của chính dự án |
| Biến môi trường đọc **lúc import**, có alias `TRANSFORMERS_OFFLINE`, và `set_client_factory()` **tháo được** hook offline | Ba cách để tư thế offline bị mất mà không ai sửa dòng code nào |
| `hf cache verify` cần **mạng** | Nên nó không dùng được làm phép kiểm toàn vẹn offline |

**Dependency — tự kiểm lại bằng PyPI JSON, khớp:** `huggingface_hub` **2.2.0**,
**Apache-2.0**, `requires_python >=3.10.0`, 10 dep trực tiếp:

```
click, filelock, fsspec, httpx2, packaging, pyyaml, tqdm, typing-extensions,
tomli (py<3.11), hf-xet  [marker: x86_64/amd64/AMD64/arm64/ARM64/aarch64]
```

Hai mục đáng nêu riêng: **`hf-xet` là bắt buộc trên máy này** (marker khớp
`AMD64`) và là **binary Rust tự làm network I/O** — egress của nó **không** do
hook Python quản; và `tqdm` là **`MPL-2.0 AND MIT`**, giấy phép duy nhất không
thuần permissive trong tập.

### Phương án C — giữ Hub hoàn toàn ngoài runtime (tư thế hiện tại, không cưỡng chế)

Đúng những gì đang có: staging thủ công, so digest bằng mắt. **Không nhận thêm
rủi ro nào**, và cũng **không đóng** 2a.

### Khuyến nghị — **[ĐỀ XUẤT] Phương án A**

Lý do quyết định **không phải** "ít dependency hơn", mà là **doctrine của chính
dự án**. `AGENTS.md:69`, về FastAPI telemetry:

> *"Nó không export được **chỉ vì `opentelemetry-sdk` chưa được cài** — không
> phải vì 'chưa cấu hình exporter'"*

`HF_HUB_OFFLINE=1` **chính là** "đã cấu hình exporter": một cờ trên một thư
viện **có** năng lực tải. Phương án A là **vắng mặt năng lực**. Và ba sự thật đã
tra được ở mục B — lỗi không phân biệt được bằng type, `refs/` thay artifact im
lặng, không verify khi nạp — nghĩa là ngay cả khi cấu hình hoàn hảo, B vẫn
**yếu hơn** A ở đúng ba thuộc tính S2.1 đòi.

Phương án A cũng **đã đi được 80%** và phần đó **đã đo**.

**Và mục 2d làm lý lẽ này mạnh hơn, không yếu hơn.** Người ta có thể đọc 2d
là *"đường tải đã ở đó rồi, nhận `huggingface_hub` cho tử tế đi"*. Đọc ngược
lại mới đúng: hôm nay thứ duy nhất chặn `Llama.from_pretrained` là **một
package vắng mặt**, và điều đó **đang hiệu quả** — đã đo, nó raise
`ImportError`. Cài `huggingface_hub` **biến phòng vệ đang hiệu quả thành một
cờ cấu hình**, và mục 4B cho thấy cờ đó không phân biệt được lỗi offline với
lỗi mạng, giải quyết revision từ một `refs/` khả biến, và không verify gì khi
nạp.

## 5. Acceptance criteria — kiểm được CPU-only, không cần artifact, không mạng

Mỗi tiêu chí kèm **mutation phải làm nó fail**, theo quy tắc của dự án.

| # | Tiêu chí | Mutation phải fail | Cần Sơn? |
|---|---|---|---|
| **A1** | Artifact vắng → raise với `reason=ABSENT` **trước** loader; không log nào chứa đường dẫn | xoá phép kiểm tồn tại, hoặc đổi thành `return None` | **không** |
| **A2** | Sai kích thước → `SIZE_MISMATCH`, và kiểm size **trước** khi hash (spy `_digest` để `pytest.fail` nếu bị gọi) | bỏ kiểm size, hoặc đảo thứ tự hash-trước-size | **không** |
| **A3** | Sai nội dung đúng kích thước → `DIGEST_MISMATCH`, so bằng `hmac.compare_digest`, và **canary** không xuất hiện ở `str/repr/args/caplog/stdout/stderr` | **giữ nguyên trạng hôm nay** (tính digest "để ghi" mà không so) → fail | **CÓ** (mục 1 dưới) |
| **A4** | Mọi entry trong manifest có `revision` khác rỗng và `sha256` 64 hex, và **mỗi cặp (path, sha256) xuất hiện nguyên văn trong ledger** | sửa digest ở code mà không sửa doc (hoặc ngược lại) → fail | **không** |
| **A5** | Đúng **một** `root`; AST **allowlist** trên module loader: không `shutil.which`, `os.environ`, `Path.home()`, `glob`/`rglob` | thêm một thư mục ứng viên thứ hai, hoặc một `which` | **không** |
| **A6** | Biến ảnh hưởng việc tải bị từ chối **bất kể giá trị**, kể cả `=1` | thu nhỏ `PROHIBITED_EGRESS_PREFIXES` | **CÓ** (mục 3) |
| **A7** | `huggingface_hub`/`transformers`/`hf-xet`/`requests`/`aiohttp` **không được cài** (`PackageNotFoundError`), cùng hình dạng test OTel-SDK đã có | `uv add huggingface_hub` → fail | **CÓ** (mục 4) |
| **A8** | Junction → `OUTSIDE_ROOT` (đo được: `resolve()` bắt); **hardlink → phải bị `DIGEST_MISMATCH` hoặc `st_nlink>1`, KHÔNG phải `OUTSIDE_ROOT`**, vì đo được containment mù với nó; symlink trong `skipif` winerror 1314 | bỏ kiểm `resolve()`-prefix → junction fail; đổi digest thành `is_symlink()` → hardlink fail | **không** |
| **A9** | AST: node so digest **đứng trước** node hand-off, và `sha256` **không** xuất hiện trong phần dựng record | chuyển digest ra sau hand-off | **không** |
| **A10** | **Không socket attempt**: audit hook trong **tiến trình con**, assert danh sách `socket.*`/`urllib.*`/`subprocess.Popen` **rỗng** | bất kỳ đường tải nào, kể cả import động | **không** |
| **A11** | `huggingface_hub` **vắng mặt** được ghim bằng test, **cùng hình dạng** test OTel-SDK đã có — vì đó là thứ duy nhất đang chặn `Llama.from_pretrained` (mục 2d) | `uv add huggingface-hub` → fail | **CÓ** (mục 4) |
| **A12** | ~~Không script nào gọi `llama-server` / `ggml-rpc-server`~~ **[XONG — lượt 28]** — và phép đo tìm thêm `whisper-server.exe`. Lỗ còn lại (`--binary` là chuỗi tự do) **cần Sơn quyết** | 3 mutation, 2 cơ chế | **không** cho phần đã làm |

**Về A10, phải nói rõ nó KHÔNG phủ được gì:** audit hook **không thấy gì bên
trong tiến trình con** — đo được, parent chỉ thấy `subprocess.Popen`. Nên nó
**không** nói gì về việc `llama-cli.exe` có gọi mạng hay không. Đóng chỗ đó cần
một control ở **tầng OS** (firewall rule / chạy cô lập), là loại control khác và
là **quyết định của Sơn** (mục 5). Ngoài ra `sys.addaudithook` **không có API
tháo**, nên hook phải chạy trong tiến trình con, không thì nó nhiễm toàn bộ
session pytest còn lại.

**Hình dạng lỗi khi sai digest** — báo *hình dạng*, không báo *giá trị*:

```
artifact llm.qwen3-4b-q4km: digest_mismatch
  (expected 7485fe6f11af, observed 3a9c01ffb210; 2497280256 bytes)
```

**Không được xuất hiện:** đường dẫn tuyệt đối; segment user profile; username;
**đường dẫn do caller truyền vào** (kể cả tương đối — nó là text do người gọi
kiểm soát và là đúng vector để một canary chui vào message); bất kỳ byte nào của
file; **digest 64 ký tự đầy đủ** (12 hex đủ để phân biệt và để grep; digest đầy
đủ của một file *bất kỳ* là một **giá trị**, không phải hình dạng).

## 6. Những gì lát này ĐÃ làm

| Việc | File |
|---|---|
| Mở rộng guard import của benchmark **3 → 16 file**, tự phát hiện bằng glob, cộng test khẳng định phép phát hiện không rỗng và khớp đĩa | `tests/test_llm_boundary.py` |
| Mở rộng guard `eval`/`exec` sang cả 16 file, cùng lý do | `tests/test_llm_boundary.py` |

**Không** sửa `src/`, không sửa `answerability`, không đụng corpus hay nhãn eval
16 case, **không** thêm dependency nào vào `pyproject.toml`/`uv.lock`.

## 7. Cần Sơn chốt — **không tự chọn**

| # | Quyết định | Hệ quả | Khuyến nghị |
|---|---|---|---|
| 1 | **Digest check là bắt buộc hay tư vấn?** | Nếu bắt buộc, fail-closed, **không cờ override**: lần đầu một artifact hợp lệ được tải lại với digest mới, app **từ chối chạy** tới khi ai đó sửa một constant đã commit. `--no-hash` hiện tại **chính là** hình dạng override làm mất bảo đảm | **[ĐỀ XUẤT]** bắt buộc, không override, và `--no-hash` bị bỏ. Nhưng **không chọn thay Sơn** — đây là **[CHỜ BẰNG CHỨNG]** |
| 2 | **Artifact ở đâu, và root có cấu hình được không?** | Hoặc hard-code tương đối trong repo (mạnh nhất, kế thừa lý lẽ `state_dir`), hoặc thêm field `MEETAI_ARTIFACT_ROOT` dùng cùng validator | **[ĐỀ XUẤT]** tương đối, hard-code |
| 3 | **Mở rộng `PROHIBITED_EGRESS_PREFIXES` quá `OTEL_`?** | Đo được: `HF_HUB_OFFLINE`, `HF_HOME`, `HF_ENDPOINT`, `TRANSFORMERS_OFFLINE`, `HTTPS_PROXY`, `XDG_CACHE_HOME` **đều được nhận**, không guard nào thấy. Từ chối chúng nghĩa là MeetAI **không khởi động** trên máy có developer đặt chúng vì việc khác | **[ĐỀ XUẤT]** từ chối họ `HF_*`/`HUGGINGFACE_*`/`TRANSFORMERS_*` và các biến proxy — **bất kể giá trị**, kể cả `=1`. Một guard cho qua `HF_HUB_OFFLINE=1` dạy operator rằng biến đó có tác dụng, và ngày nó thành `0` thì guard im |
| 4 | **Có nhận `huggingface_hub` vào runtime không?** | Thiết kế ở mục 4A **không cần** nó. Nếu nhận: 10 dep trực tiếp, trong đó `hf-xet` là **binary Rust tự networking** không do hook Python quản, cộng `tqdm` **MPL-2.0** | **[ĐỀ XUẤT]** không nhận. Nếu Sơn muốn, `AGENTS.md` đòi một entry `docs/research/` về license/mục đích/transitive **trước** khi cài |
| 5 | **Cô lập mạng ở tầng OS có nằm trong phạm vi không?** | `llama-cli.exe` là binary native **không được audit**; audit hook **không thấy gì** bên trong nó — đo được. Chỉ firewall rule hoặc chạy cô lập mới tới được | **[CHỜ BẰNG CHỨNG]** — là nghĩa vụ trong `docs/spec.md`, hay là phần dư đã ghi? |
| 6 | ~~**Vá lộ đường dẫn trong `benchmarks/` (2c)?**~~ | **[XONG — lượt 26]** Chỉ các nhánh **từ chối sớm** đổi sang `artifact-missing: <role>`; đường **thành công** giữ nguyên, nên **không artifact S2.3 nào đổi nội dung** và mối lo ban đầu không phát sinh. Scope `test_no_value_in_errors.py` **không** nới — thay vào đó là một file test riêng, vì canary cần chạy `main()` chứ không chỉ đọc source. Năm quyết định còn lại không đổi. |

## 7. Năm quyết định — **[CHỐT THEO ỦY QUYỀN CỦA SƠN] 2026-10-10 (lượt 35)**

Sơn **ủy quyền** cho Claude quyết năm mục này dựa trên nghiên cứu và cấu hình máy.
Nhãn là **[CHỐT THEO ỦY QUYỀN CỦA SƠN]**, không phải [CHỐT] — Sơn **không** tự chọn
từng giá trị, và phân biệt đó quan trọng: nếu sau này Sơn muốn đổi, đây là quyết định
của một đại diện, không phải phát ngôn của chủ dự án.

**Không mục nào trong năm mục này mở cấp B.** Chúng là điều kiện *tiền đề*; hai ngưỡng
RAM, lựa chọn A/B/C, model chạy có giám sát và artifact schema **vẫn pending**.

| # | Quyết định | Căn cứ chính | Cưỡng chế ở đâu |
|---|---|---|---|
| 1 | **Digest BẮT BUỘC, không `--no-hash`** | Cờ đó **đã được dùng 2/7** lần đo, ghi `"sha256": "skipped"` vào artifact **trông vẫn đầy đủ** | `artifacts.PINNED_MODEL_DIGESTS` **rỗng** → từ chối; `bench_llm_policy` gọi sau cổng RAM |
| 2 | **Artifact root cố định, tương đối, gitignored** | Kế thừa lý lẽ `state_dir`: đường dẫn tương đối trong dự án chặn **cả** ổ mạng **và** thư mục cloud-sync mà **không cần nhận ra** cái nào | `artifacts.artifact_path()`; **6 writer** đi qua nó, có test cấu trúc |
| 3 | **Từ chối theo SỰ HIỆN DIỆN các biến đổi model resolution và proxy** | Đo được: **12/12** biến đó khởi động MeetAI bình thường, gồm `HF_HUB_OFFLINE` cả `1`, `0` và rỗng | `settings.PROHIBITED_EGRESS_PREFIXES` + `_SUFFIXES` |
| 4 | **KHÔNG nhận `huggingface_hub`** | Thiết kế không cần; nhận vào là **10 dep trực tiếp** gồm `hf-xet` — binary Rust **tự networking**, ngoài mọi control tầng Python | Test ghim **package vắng mặt** (lỗ lượt 25 nay đã đóng) |
| 5 | **Đòi cô lập egress tầng OS trước khi chạy binary native** | Đo được: binary native **không** nằm dưới audit hook, nên bằng chứng "0 network event" trong tiến trình Python **không nói gì** về nó | `preflight.require_egress_isolation()`, `EGRESS_ISOLATION_ATTESTED = False`; **5/5** runner gọi |

### Trade-off đã cân, không chỉ chọn theo khuyến nghị

**Quyết định 3 là mục tôi suy xét lâu nhất, và tôi tách nó thành hai họ với hai lý do
khác nhau** — vì gộp chúng sẽ là lấy cảm giác làm lý lẽ:

- Họ `HF_`/`HUGGINGFACE`/`TRANSFORMERS` **tạo ra được một đường tải**: `HF_ENDPOINT`
  là một host, `HF_HOME` là một thư mục. Một biến có thể biến thiết kế local-file
  thành thiết kế tải về **mà không dòng code nào đổi**. Lý lẽ mạnh.
- Họ `*_PROXY` **không tạo** được đường nào. Nếu dừng ở đó thì đáng lẽ **không** chặn.
  Nhưng chúng **route vòng qua** chính phép cô lập của quyết định #5: một firewall
  rule chặn `llama-cli.exe` là **vô ích** nếu một proxy được phép chuyển tiếp. Đó là
  một cơ chế cụ thể, nên chặn.
- `XDG_CACHE_HOME` **cố ý KHÔNG chặn** — và có test ghi điều đó để người sau không
  đọc thành sơ sót. Nó đổi chỗ cache: không tạo được đường mạng, không vô hiệu được
  firewall rule. Phần dư thật của nó (cache rơi vào thư mục đồng bộ) **đúng bằng** phần
  dư đã ghi cho `state_dir`.

**Chi phí "app không khởi động" — đo, không đoán.** Trên máy tham chiếu, **không một
biến nào** trong cả bốn họ đang được đặt (`HF_` 0, `HUGGINGFACE` 0, `TRANSFORMERS` 0,
`*_PROXY` 0, `XDG_` 0). Nên chi phí thực tế **hôm nay là 0**. Phần dư: trên một máy
có proxy cho việc khác, MeetAI **sẽ không khởi động** — đường thoát đã ghi trong
`.env.example` là bỏ biến khỏi môi trường của phiên chạy MeetAI, **không** sửa guard.
MeetAI chỉ triển khai trên máy riêng của chủ dự án, nên rủi ro này hẹp.

**Quyết định 1: hai tầng, và tầng thứ hai mới là phép kiểm.** Bỏ `--no-hash` chỉ làm
digest **được ghi**. Thứ làm nó thành **phép kiểm** là từ chối chạy khi digest không
khớp một giá trị **đã ghim trong source**. Ledger để **rỗng**: từ chối bằng **sự vắng
mặt của một digest được duyệt**, đúng hình dạng `CPU_RAM_MARGIN_MIB`. Chính sách do
tôi chốt; **giá trị vẫn là của Sơn**, vì ghim một digest là khẳng định rằng **một file
cụ thể đã staged là file đúng** — không suy luận nào thay được điều đó.

**Thứ tự của hai cổng mới do TEST quyết, không do tôi.** Digest check đặt trước cổng
RAM làm một lần chạy CPU exit 2 thay vì 3, và test *"không model runner nào bỏ qua
cổng của nó"* **fail** — đúng. Cổng RAM là control Sơn đã chốt, nó rẻ, và nó bảo vệ
máy, nên nó phải là từ chối **đầu tiên**. Tương tự, cổng egress đặt trước các phép
kiểm artifact làm **7 nhánh** của ma trận refusal-leak **không tới được**; cổng chỉ
cần đứng trước thứ **chạy** — một `stat` không spawn gì — nên nó nằm ngay trước phần
native, và một file thiếu vẫn nhận được từ chối **giàu thông tin hơn**.

### Phần dư của chính năm quyết định này

- **Quyết định 5 không tự cô lập được gì.** Nó chỉ **từ chối**. Việc đặt firewall rule
  là thay đổi hệ thống, và lượt này **không** thực hiện. `EGRESS_ISOLATION_ATTESTED`
  là một hằng **trong source**, cố ý không phải setting hay biến môi trường: một
  control egress mà biến môi trường bật được là control mà một lần gõ sai tắt được.
- **Quyết định 1 chưa được thử trên một digest thật**, vì ledger rỗng và không lần
  chạy model nào được phép. Đường **khớp** và **lệch** đã test bằng seam, không bằng
  file thật.
- **Quyết định 4 ghim sự vắng mặt của package, không ghim rằng `llama_cpp` không gọi
  `hf_hub_download`.** Lời gọi đó nằm **trong** một thư viện bên thứ ba; phép quét
  import của ta không thấy vào trong đó.

## 7b. Hai phát hiện của agent mà tôi đo ra là SAI

Ba review độc lập chạy trên `2d69797`. Phần lớn chính xác và đã được tôi tái
lập. **Hai điểm sai, và tôi sửa chúng ở đây chứ không chuyển tiếp:**

| Agent nói | Đo được |
|---|---|
| `benchmarks/` có **19** file `.py` | **16**, cả `glob` và `rglob`, không có `.py` nào dưới thư mục con. Con số 19 có lẽ đếm cả `__pycache__` |
| `var/bench/llm-policy-s23-power.json` là *"committed-measurement artifact"* | `var/` **gitignored**, `git ls-files var/` **rỗng** — nó **không** được commit |

Ghi lại vì chúng là loại sai dễ lọt: một con số và một tính từ, cả hai nghe
hợp lý, và cả hai sẽ đi vào tài liệu nếu không ai chạy lệnh.

## 8. Phần dư — ghi thẳng

- **Containment không giới hạn bytes.** Hardlink đi qua mọi `resolve()`-prefix —
  **đo được**. Chỉ digest chặn.
- **Nếu bản thân thư mục dự án nằm trong thư mục đồng bộ**, artifact đã stage
  cũng bị đồng bộ. Cùng phần dư đã ghi cho `state_dir`.
- **`llama-cli.exe` chưa được audit** và không audit được từ Python.
- **TOCTOU** giữa digest và lúc loader mở file: `llama-cli.exe` nhận **đường
  dẫn**, không nhận handle, và tự mở file trong tiến trình riêng. Giữ handle chỉ
  **thu hẹp** cửa sổ. Và bảo vệ đo được (`winerror 5`/`32`) là thuộc tính
  **share-mode của Windows**; hành vi POSIX **CHƯA ĐO**.
- **Mọi điều về `huggingface_hub` ở mục 4B đến từ tài liệu upstream, chưa cài
  nên chưa introspect được.** Hành vi phụ thuộc version rất mạnh (0.x dùng
  `requests`, 1.x `httpx`, 2.x `httpx2`), và tài liệu nói rằng **trước khi có
  `IncompleteSnapshotError`, snapshot thiếu được trả về IM LẶNG**. Nếu nhận,
  phải **đo lại trên đúng version được pin**, trong sandbox chặn mạng.
- **Chưa đo:** digest của các artifact FLEURS/VietMed/whisper có còn khớp ledger
  hôm nay không (không hash 5 GB ở lát này).

## 9. Không tuyên bố

Lát này **không** đóng Gate 0 nào, **không** tuyên bố production readiness,
**không** đổi trạng thái S2.1 từ `[~]`. Tiêu chí `huggingface-hub offline
fail-closed` được **viết lại cho đúng thứ đang tồn tại**, chứ không được đánh
dấu đạt.
