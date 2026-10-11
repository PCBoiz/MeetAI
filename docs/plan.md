# MeetAI - kế hoạch theo lát

**Việc của tài liệu này:** làm gì tiếp, theo thứ tự nào, và biết bằng cách nào là xong. Nó **sở hữu** danh sách lát, acceptance criteria từng lát, và các cạnh phụ thuộc giữa lát với cổng bằng chứng.

Tách khỏi [PROJECT_STATE.md](../PROJECT_STATE.md) vì hai tài liệu trả lời hai câu khác nhau: PROJECT_STATE là *đang ở đâu và đã xảy ra gì*, đây là *làm gì tiếp và biết bằng cách nào là xong*. Lý do thực tế: acceptance criteria trước đây nằm rải trong nhật ký, và tới lượt thứ ba thì criteria của S1.1 đã nằm cách lát nó quản ba lượt — không ai tìm được.

Nghĩa vụ kiểm chứng được nằm ở [spec.md](spec.md). Phạm vi nằm ở [intent.md](intent.md). Lý do kiến trúc nằm ở [adr/](adr/).

Trạng thái: `[ ]` chưa làm · `[~]` đang làm · `[x]` xong và có bằng chứng · `[!]` bị chặn bởi cổng

---

## Phase 0 — khung local, không phụ thuộc Discord

| Lát | Trạng thái | Nội dung |
|---|---|---|
| S0.0 | `[x]` | Khảo sát repo + môi trường, tạo `PROJECT_STATE.md` |
| S0.1 | `[x]` | `git init` + `.gitignore` + `AGENTS.md` + tài liệu nền vào `docs/handoff/` |
| S0.2 | `[x]` | Python 3.12 pin bằng uv, skeleton `src/meetai`, pytest chạy được |
| S0.3 | `[x]` | Artifact thiết kế: `intent.md`, `spec.md`, `plan.md`, `adr/`, `research/` |
| S0.4 | `[x]` | Settings fail-closed, secret handling, `.env.example` |
| S0.5 | `[x]` | Structured logging metadata-only, formatter allowlist |
| S0.6 | `[x]` | Start/Stop, model on/off mock (có `LOADING`/`ERROR`/`UNKNOWN`), kill switch process-wide, local web UI loopback với telemetry tắt tường minh |

## Phase 1 — lõi an toàn (H0-F)

| Lát | Trạng thái | Nội dung |
|---|---|---|
| S1.1 | `[x]` | Consent FSM + revoke generation + cancellation |
| S1.2 | `[x]` | Session lifecycle + media gate fail-closed + buffer bound |
| S1.3 | `[x]` | Platform adapter interface tách 3 plane + fake adapter |
| S1.4 | `[x]` | Meeting planner trên fixture |
| S1.5 | `[x]` | Response schema + authority gate 3 lớp |
| S1.6 | `[x]` | Knowledge-card state machine + approval + cascade |
| S1.7 | `[x]` | Direct-address classifier |
| S1.8 | `[x]` | Replay + eval harness có corpus tiếng Việt gán nhãn |

## Phase 2 — khả thi model local (H0-M)

| Lát | Trạng thái | Nội dung |
|---|---|---|
| S2.1 | `[~]` | Model artifact tách khỏi app; hòa giải CUDA 12-vs-13; ba đường `llama-cpp-python`; `huggingface-hub` offline mode. **Lượt 35: năm quyết định chính sách đã CHỐT THEO ỦY QUYỀN và đã cưỡng chế** (digest bắt buộc, artifact root cố định, từ chối biến egress theo sự hiện diện, không nhận `huggingface_hub`, đòi cô lập egress tầng OS). Vẫn `[~]` vì hai chỗ hở chỉ **được quyết**, chưa **được thử trên một lần chạy thật** — và không lần chạy nào được phép. |
| S2.2 | `[~]` | Benchmark ASR tiếng Việt. Co-residency + WER + noise + accent **đã đo**; `nói chồng` **`absent`** (ngoài phạm vi, cổng mở), accent và p50/p95 **`not demonstrated`**. **partial/open** |
| S2.3 | `[~]` | Benchmark LLM nhỏ lượng tử hóa. **Đã đo** 5 trục riêng trên 43 case tổng hợp, 2 lần chạy, output tất định. **Baseline giữ nguyên số trước khi sửa gate.** `chi phí tháng` và `độ ổn định` **chưa chứng minh được**. **partial/open** |
| Lát sửa an toàn sau S2.3 | `[x]` | **Đóng phần dư ADR 0006** (ma trận trường **106/1800 → 6/1800**) và **hai lỗ nặng hơn, không cần field nào của proposal**: marker thời/thể (**69/117 → 0/117**) và collision `de xuat` trong `_HEDGE`. **Sửa 64/81 citation** trong corpus authority theo nội dung. Thử **một cấu hình prompt riêng** (v2) và báo cạnh baseline |
| Response boundary + answerability | `[x]` | **Gate đã có caller.** `boundary.deliver` là chỗ duy nhất text tới sink (test AST). `answerability.assess` là bước 5 pipeline, input là **claim/evidence mapping**. Hợp đồng `SILENT` đóng trong **kiểu dữ liệu**. false-answer/false-abstention **0 trên cả 8 nhóm**. **Boundary nội bộ, KHÔNG phải tích hợp production** |
| Bộ eval cần Sơn duyệt | `[x]` | **12 cơ chế false answer thành 16 case duyệt được từng cái** (`docs/research/2026-10-10-bo-eval-can-son-duyet.md`) = **13 false answer + 2 false abstention + 1 positive control**: câu hỏi, card tối thiểu, claim, hành vi **hôm nay**, nhãn **[ĐỀ XUẤT]**, phát/abstain, lý do, nhóm lỗi, control. Xếp theo **lớp nào là phòng vệ cuối** — đo được gate chỉ từ chối **4/16**, nên **11 case có answerability là lớp duy nhất**. Cộng **ma trận 5 gốc → lớp sửa → false-positive phải đo → test chứng minh**, audit harness (đóng **song ánh enum** và map **axes→level total**), và đo **R1b cả lớp**: 24/24 đóng, chi phí 0. **Không sửa `src/`** |
| Đối chiếu số đếm tài liệu | `[x]` | **Lượt 24, chỉ tài liệu.** Tái lập mọi con số từ code: **16 case** (không phải 15), gate **12/16 cho qua** · **4/16 từ chối** (đối chiếu **từng dòng** bảng, 16/16 khớp), control **18 khẳng định trên 15 mục** (**12** phải-trả-lời-được + **6** chốt-từ-chối, **18/18 khớp loại, 0 lệch**). Ba nhóm số sai vì **lẫn đơn vị** — đếm cơ chế rồi ghi như case, đếm mục như thể mỗi mục một khẳng định. Gắn nhãn đính chính cho hai tuyên bố cũ trong nhật ký. **Không sửa `src/`, không đổi nhãn** |
| Đo độ bao phủ claim–evidence | `[x]` | **Corpus cũ đã hết khả năng đo** — module đồng ý với **cả 36** case, tức nó bao phủ đúng những hình dạng nó được xây để xử lý. Mở rộng lên **51 case / 14 nhóm** → **3 false answer** và **3 false abstention**, tất cả vào ledger trần-chỉ-được-hạ. Đo **3 ứng viên normalization ngoài production path**, **loại 2 bằng phép đo** (R1 phá câu khẩu ngữ, R2 dời false answer sang `hạn mức`/`hạn chót`); **R1b** là **[ĐỀ XUẤT]** chờ Sơn. **Không áp dụng gì**, chặn bằng test **hành vi** |
| Fail-closed answerability | `[x]` | **Đóng đường bỏ qua kiểm tra.** Ba trạng thái `SUPPORTED`/`UNSUPPORTED`/`UNCLEAR`; claim không có giá trị nhận diện được phải là **quotation**. Đóng cả ba residual lượt 15, **không** thêm lexicon và **không** thêm danh sách tên. 0 false answer / 0 false abstention trên **10 nhóm** |
| Evidence isolation + preflight | `[x]` | **Đóng ba residual của lượt 16**, và sửa **sáu** đường false-answer một audit đối kháng tìm ra. Evidence là **clause**, không phải card; liệt kê tách khỏi mâu thuẫn bằng **event key**; approval gắn với **digest lúc duyệt**. Thêm `benchmarks/preflight.py` từ chối trước khi load. 0 false answer / 0 false abstention trên **10 nhóm**, `UNCLEAR` **11/36** và chỉ ở ba nhóm nó phải nằm. **Không model nào được tải, không benchmark GPU nào được chạy** |
| Dry-run cấp 2 + bốn lỗ boundary | `[x]` | **Boundary có caller thật** (`meetai dry-run`, 10 case) — hai addendum trước nói "đã có caller" khi chỉ test gọi. Đóng **bốn** lỗ một audit tìm ra, nặng nhất là **một lượng từ một âm tiết tới được sink** (`"nửa tỷ đồng"`, `SUPPORTED`, findings rỗng). `rationale` thành **bất biến có test**. Bất biến AST "không đường nào bỏ qua gate". Xác minh preflight/lock/`failure_evidence` **bằng test và mock**, tìm 7 defect, thêm gate **RAM host**. **Không GPU, không tải model, không đề xuất chạy** |
| Retrieval theo câu hỏi + hợp đồng sink lỗi | `[x]` | **Lượt 19, dòng này thiếu cho tới lượt 20** — `AGENTS.md` yêu cầu cập nhật `plan.md` mỗi lát và lượt 19 không làm, một audit tìm ra. `retrieval.py` trả **hai** tập (`candidates` xếp hạng/cắt được, `witnesses` **không bao giờ cắt**); đo được: đưa card xếp hạng cao nhất thay vì cả tập biến một lần từ chối `CONFLICTING` thành câu **đã phát**. Hợp đồng sink lỗi: `SINK_REFUSED` vs `SINK_UNKNOWN` (**mặc định**) vs `NOT_ATTEMPTED` |
| Kiểm chứng ba gate an toàn | `[x]` | **90 test hành vi + 29 mutation** trên `consent.py`, `session.py`, `media_gate.py` — ba module quyết định một frame có được xử lý hay không, và trước đó **không có** bằng chứng xoá-là-fail nào. Đóng **ba lỗ** hai audit tìm ra: callable non-bool cho qua, `buffer_for` sau close phát buffer **mở**, `evaluate` raise thay vì trả decision. Và **một test của tôi vacuous**. Chuẩn bị quyết định scope, **không cài gì phụ thuộc vào nó** |
| Permit media sink + conflicts đúng chỗ | `[x]` | **Media sink phải có permit do gate cấp**, hiệu lực là **danh tính** (`isinstance` vô dụng: `object.__setattr__` phá cả `frozen` lẫn `slots`). Đóng **lỗ lớn nhất**: `import discord` trong module mới từng **qua toàn bộ suite** — giờ có allowlist 6 root. `conflicts()` nối làm **tín hiệu review**, không phải gate, vì đo được nó báo *ngân sách vs deadline* là conflict. Ghi lại **một false answer chưa đóng** (đồng nghĩa chéo card) và 3 fix adapter thuần |

## Phase 3+ — chặn bởi cổng bằng chứng

| Lát | Trạng thái | Chặn bởi |
|---|---|---|
| S3.x | `[!]` | 0-S, 0-P, 0-C — Discord proof |
| S4.x | `[!]` | 0-S, 0-P, 0-C, 0-U — vertical slice có consent |
| S5.x | `[!]` | tất cả — pilot |

---

## Phụ thuộc giữa lát và cổng

Phân biệt hai loại "chưa làm được", vì gộp chúng là cách lấy một cổng đang mở làm cớ cho việc chưa làm:

```text
Chặn bởi bằng chứng Discord (0-S / 0-P / 0-C)
    S3.x, S4.x, S5.x
    A-6, A-7, A-8 trong spec.md
    "test/replay evidence trên pipeline cụ thể" trong định nghĩa hoàn tất

Chặn bởi quyết định của chủ dự án (0-U) — chỉ chặn việc *chọn*, không chặn việc *xây*
    Chọn consent mode cuối          (FSM đã xây xong, hỗ trợ cả hai)
    Chọn A1 hay A3                   (cả hai đã xây xong sau một interface)
    Bật transcript/notes/journal     (switch đã có, mặc định OFF)
    Retention của receipt            (receipt đã có, chưa persist)
    Wording công khai

Không chặn bởi gì — chỉ là chưa làm
    S0.6, S1.7, S2.1, S2.2, S2.3
    M-7 (calendar connector: cần OAuth app, là tác động ra ngoài cần xác nhận)
    K-8 (embeddings: cố ý hoãn tới khi benchmark chứng minh)
```

---

## Acceptance criteria

Mỗi lát một mục. Chỉ được đánh `[x]` khi mọi dòng đạt **và** nêu được lệnh đã chạy.

Áp dụng cho **mọi** lát: `uv run pytest` + `uv run ruff format .` + `uv run ruff check .` + `uv run mypy` sạch; không lát nào chọn thay chủ dự án bất kỳ câu nào ở [PROJECT_STATE.md](../PROJECT_STATE.md) mục 4B.

### S0.6 — supervisor và local web UI

- FastAPI + uvicorn thêm vào extra `ui`, pin chính xác, cập nhật lockfile và dependency inventory
- App khởi tạo với **mọi** signal telemetry tắt; có test khẳng định từng key
- Test khẳng định không distribution OTel SDK/exporter nào importable (giữ nguyên bất biến hiện có)
- Chỉ bind `127.0.0.1`; test khẳng định không bind được LAN hay `0.0.0.0`
- UI render phân biệt được: loading, error, stopped, disabled, killed, pending-consent
- UI **không** hiện capability chưa có như đang hoạt động; test khẳng định mọi capability OFF kèm lý do
- "Start" chỉ bật local component đã được phép, **không** join Discord; test khẳng định
- "Model ON" **không** tự bật audio hay external AI; test khẳng định
- Kill switch: chỉ tuyên bố đúng những gì hợp đồng hiện tại bảo đảm. `MediaGate.close()` là đồng bộ và tức thì; `_run_cancellations` chỉ hủy được task **đã đăng ký** callback. Phải nêu rõ giới hạn này, không nói "dừng được mọi task".
- Không có UI nào ngầm chọn consent/late-join/persistence thay chủ dự án
- Không tạo OAuth app, không endpoint cloud, không account bên ngoài

### S1.7 — direct-address classifier

**Đạt, 2026-10-07.** Lệnh: `uv run pytest -q` (1368 passed, 3 skipped),
`uv run ruff check .`, `uv run ruff format --check .`, `uv run mypy` (49 file).
Số liệu: `docs/research/2026-10-07-addressing-eval-v1.md` — false activation
**0/48**, false non-address **0/8**, sai lớp address **0/56**, sai intent
**1/56** (đúng known gap đã ghi). UNCLEAR rate 21/56 = 37.5%, báo riêng vì
UNCLEAR là đáp án **đúng** cho phần lớn corpus chứ không phải điểm trừ.

Fold collision: đóng `Minh`/`mình` **cho classifier addressing**, bằng cấu
trúc chứ không bằng pattern — tên người hoặc tên trùng từ không bao giờ tới
được `DIRECTED_TO_ME` ở bất kỳ framing nào, nên không collision nào trong tên
người gây được false activation. **Cố ý không đóng trong `authority`**: ở đó
collision gây over-refusal (hướng rẻ), và truyền "đây là người thứ ba" vào
gate sẽ mở đường cho text tự dàn khung ngôi ba để thoát. Có test ghi rằng đây
là lựa chọn, không phải sơ suất.

- Phân biệt bốn lớp: được gọi trực tiếp / nhắc ngôi ba / alias trùng từ / không rõ
- **Alias match một mình không bao giờ đủ** để sinh `directly_addressed=True`
- Đo trên corpus tiếng Việt với alias **giả**; báo false activation và false reply **riêng**, kèm denominator
- Alias thật cấu hình cục bộ, không vào repo
- Classifier chưa đủ tin cậy thì **không tự kích hoạt trả lời** — mặc định trả về `UNCLEAR`
- Đóng được ít nhất một fold collision đã ghi trong [spec.md](spec.md) mục 9, hoặc nêu rõ vì sao không

### S2.1 — khả thi model

**Phần lớn đạt, 2026-10-07 (lượt 8).** Số đo:
[S2.1 feasibility](research/2026-10-07-s21-model-feasibility.md). Artifact:
[model ledger](research/2026-10-07-model-artifacts.md). Quyết định:
[ADR 0005](adr/0005-nhanh-cuda-12-va-duong-llama-cpp.md).

| Tiêu chí | Trạng thái |
|---|---|
| Pin Python verify bằng cài thật | **đạt** — và chính việc cài thật mới lộ ra wheel CUDA crash vì AVX-512, điều index không nói |
| Chọn một nhánh CUDA + lý do | **đạt** — 12.x, vì CTranslate2 không có bản CUDA 13 (verify bằng đọc binary), **không** vì Turing |
| Ba đường `llama-cpp-python` + trade-off | **đạt** — bảng ở mục 3.4 của báo cáo |
| Model artifact tách khỏi app: version + hash + license | **đạt** — `pyproject.toml`/`uv.lock` không đổi; app venv vẫn 32 gói, 0 gói ML/CUDA |
| Đo VRAM/RAM peak thật trên GTX 1660 Ti | **đạt** — VRAM Δ 2865 MiB, RAM WS 2794 MiB (GPU); 4438 MiB (CPU) |
| `huggingface-hub` offline fail-closed | **MỘT PHẦN — và tiêu chí đã được viết lại ở lượt 25**, xem [offline fail-closed](research/2026-10-10-offline-fail-closed-model-artifact.md). `huggingface-hub` **chưa cài** (đo được); weights tới bằng `curl` theo URL pin **commit 40 ký tự**. **ĐẠT, và đạt về cấu trúc:** artifact vắng → `return 2` **trước** loader, **0 network event** (đo bằng `sys.addaudithook` trên cả `bench_llm_policy` và `bench_asr`) — không có code tải nào để vô hiệu hoá. **CHƯA ĐẠT:** digest được **ghi, không được cưỡng chế** (một call site, **sau** cả run; `--no-hash` bỏ nó, và **2/7** lần đo đã dùng); thông báo từ chối **lộ đường dẫn tuyệt đối + username** — **lượt 26 ĐÃ SỬA**, và đo lại thì lỗ rộng hơn: **6 file / 7 nhánh từ chối sớm**, nay in `artifact-missing: <role>` từ allowlist đóng kín, ghim bởi `tests/test_benchmark_refusal_leaks.py` — **lượt 27: cả 16 kiểm tra artifact (3/5/2/1/2/3) đều có ca cô lập, 10/10 role được chạm**, so với 7/16 nhánh và 4/10 role ở lượt 26, khi nhánh nào được chạm còn phụ thuộc binary có trên máy; và `llama_cpp.Llama.from_pretrained` **đã link sẵn** `hf_hub_download` — thứ chặn nó là **một package vắng mặt không có test nào ghim**. **Hai mục CHƯA ĐẠT còn lại cần quyết định của Sơn, nên lát này KHÔNG đổi `[~]` thành `[x]`** |

**Lượt 29 — bốn trong sáu thiếu sót cơ học đã xong, và cổng nay CƯỠNG CHẾ.** [CHỐT] Sơn: cổng RAM CPU **giữ `pending`**, không chạy model nào, `--binary` là **allowlist đóng kín**. Đã làm: CPU mode cho `bench_llm_policy` (`--device/--ngl`, cặp mâu thuẫn bị **từ chối**); `require_cpu_preflight` chỉ kiểm RAM host, **không cần `nvidia-smi`**, và từ chối **trước khi đọc bộ nhớ**; trạng thái `nvidia-smi` unavailable thành **có kiểu** (`"?"` từng làm `int()` raise, và `or 0` **không bao giờ** fire vì `"?"` truthy); smoke test CPU-only **không tải model**; và tài liệu hoá **mọi** harness cộng `var/bench-cpu-venv`. **Audit sau sửa tìm ra một bypass:** cổng chỉ bảo vệ **1/5** harness chạy model — đã đóng hai đường LLM còn lại. **Lượt 30:** audit tìm ra **bypass thứ hai** — `bench_asr --cpu` cũng là một lần chạy model không GPU; nay có **cổng riêng** `pending`, **không vay** số 4438 vì đó là working set của Qwen3-4B, không phải whisper. Bằng chứng ASR là **n=0** (`var/bench/` không có artifact ASR nào), nên cổng đó `None` vì **hai lý do độc lập**. **Cả bốn** đường CPU nay từ chối exit 3, không đọc RAM, không spawn — xác minh qua đúng cách gọi script README ghi. Và runbook mục **4d** mới phân loại bằng chứng ngưỡng (phép đo / suy ra / chính sách) cùng *cái gì mỗi lựa chọn KHÔNG bảo đảm*. **Còn chờ Sơn:** **margin RAM** — nay là **hai** câu hỏi riêng (LLM và ASR), vì hai bằng chứng không so sánh được — hoặc cho phép một lần chạy đo có giám sát để có n>1.

**Lượt 28 — điều kiện trước khi một phép thử model local được phép chạy:** xem [runbook](runbook/thu-nghiem-cuc-bo.md) mục 4. Ngoài 5 quyết định của Sơn, còn **6 thiếu sót cơ học**: `bench_llm_policy.py` **không có cờ CPU** (`gpu_layers = 99` nung cứng vào argv); `preflight.py` **không có chế độ CPU** và harness gọi `require_headroom()` **vô điều kiện** → máy không GPU **exit 3**; **không test smoke CPU-only nào**; `measure.py` thay `["?"] * 10` khi thiếu `nvidia-smi` rồi 5 call site `int(...)` → `ValueError`; `var/bench-cpu-venv` không được ghi như một đích chạy; `benchmarks/README.md` chỉ tài liệu hoá `bench_llamacpp.py`. **OOM, bằng số:** peak CPU đã đo **4438 MiB**, cổng RAM đang code **3380**, RAM khả dụng đo được **3966** — qua cổng mà **thiếu ~472 MiB**, và `4438` **không có trong code hay test nào**.

**Chưa làm, cố ý:** không đo chất lượng (WER/CER, đánh giá LLM) — đó là S2.2/S2.3
và chúng có acceptance criteria riêng. Gộp vào đây sẽ phá "một lát một commit" và
mất ranh giới rollback.

**Phát hiện phần cứng quyết định mọi số:** GPU bị cap **40 W trên card 80 W**,
memory clock **810 MHz trên 6001 MHz**. GPU mua được **6.2× prefill** nhưng chỉ
**1.16× decode**, vì decode là bandwidth-bound. Không đổi power limit — là cấu
hình hệ thống, cần Sơn quyết.

- Pin Python verify bằng **cài thật**, không phải bằng wheel index
- Chọn một nhánh CUDA (đề xuất 12.x) và ghi lý do; không trộn major trong một venv
- `llama-cpp-python`: chọn một trong ba — build từ nguồn, pin wheel CPU, hoặc llama.cpp server qua localhost — và ghi trade-off
- `huggingface-hub` offline fail-closed; weights pre-stage; **không** tải khi chạy
- Model artifact tách khỏi app: pin version + hash + license
- Đo VRAM/RAM peak thật trên GTX 1660 Ti; **không** suy từ model card

### Lát kiểm chứng ba gate an toàn (lượt 20)

**Xong 2026-10-09.** Số đo: `tests/test_safety_gates.py` **90 test**,
**29 mutation** (23 + 6), tất cả **DETECTED**.

**Hiệu chỉnh trước tiên:** `plan.md` **thiếu hẳn dòng lát cho lượt 19**, dù
`AGENTS.md` mục "Cách làm từng lát" bước 8 yêu cầu cập nhật nó mỗi lát. Một
audit tìm ra. Đã thêm cả hai dòng ở trên.

| Tiêu chí | Trạng thái |
|---|---|
| Test cho các đường quan trọng: consent pending → media bị từ chối | **đạt** — cả ba chỗ từ chối: `MediaGate.evaluate` trả `POLICY_PENDING`, `Session.activate` raise, và `accept_frame` **không buffer gì**. Cộng một test trên `Settings()` **thật** (không fake) khẳng định mặc định của dự án từ chối media. |
| revoke/close vô hiệu hoá quyền xử lý cũ | **đạt** — generation bắt được captured trước revoke thì sau revoke bị từ chối, ở **cả hai** cửa (gate và ledger). `close()` cũng vậy: trước lượt 18 nó chỉ đóng gate nên **yếu hơn** revoke. |
| late join không tự được coi là đã đồng ý | **đạt, và exhaustive trên enum** — cả ba `LateJoinPolicy` đều đóng gate; người đến sau **không được cấp gì** bởi việc đến (`granted_scopes` rỗng, `state_of` không `CONSENTED`); và frame của **người đã consent** cũng dừng, vì gate là theo phiên. |
| generation mismatch bị từ chối | **đạt, cả hai chiều** — `!=` chứ không `<`: một generation **tương lai** cũng sai, vì nó nghĩa là caller bắt được thứ ledger chưa từng phát. Cộng biên: `-1`, `+99`, và `grant` quoting generation cũ raise `StaleConsentError`. |
| trạng thái thiếu/sai cấu hình fail-closed | **đạt** — absence đọc là `UNKNOWN`; speaker không map được **không có buffer nào** được tạo; scope khác không được cấp theo; key khác session raise; notice version khác là **key khác**; grant chưa announce bị từ chối. |
| Với **từng** guard, chứng minh test bắt được việc xoá/vô hiệu hoá chính cơ chế đó | **đạt — 29/29 DETECTED.** Lần chạy đầu **19/23**: ba anchor lệch do format, và **một miss thật** — nhánh `participant is None` trong `accept_frame` là **defence in depth** mà gate đã che. Cách đóng: đưa cho session một gate **cho qua mọi thứ** và kiểm nhánh trong vẫn từ chối, vì defence in depth chỉ là defence nếu **từng lớp chạy được một mình**. |
| Tránh test chỉ kiểm tên hàm/field hoặc AST hình thức | **đạt** — và hai audit chỉ ra đúng loại test phải tránh, gồm `assert outcome.gate_closed` (một **literal** hardcode trong `session.py`, nên xoá `self.gate.close()` khỏi nhánh A1/A3 vẫn xanh) và `assert not hasattr(gate, "reopen")` (hình dạng API, không chứng minh được tính không thể mở lại). Cả hai đã thay bằng phép đo. |
| Dùng fixture/fake, không xử lý frame/audio thật | **đạt** — frame là object sentinel trơ; không gì decode, resample hay transcribe. Docstring module **nói thẳng** một lần chạy xanh ở đây **không** chứng minh gì về audio thật, đường production, lịch biểu concurrency, hay tuân thủ pháp lý. |
| Giữ policy và mọi consent mode ở `pending_decision`; không sửa config để test xanh | **đạt** — verify bằng `uv run meetai status`. Chỗ nào cần media được phép thì **inject một callable fake**, đúng seam module đã mở ra cho việc này. |
| `store.conflicts()` giữ đúng trạng thái | **đạt** — vẫn **không có call site**, và không chỗ nào tuyên bố retrieval đã giải quyết conflict. Phép kiểm polarity ở lượt 19 đóng đúng trường hợp đã đo; `conflicts()` rộng hơn và **chưa được nối**. |
| `scope`/`Sensitivity` phải kiểm ở lớp dưới trước khi có caller thật | **giữ nguyên là phần dư** — `Sensitivity` vẫn 0 lần trong ba module bằng chứng. **Không cài** phép kiểm ở lát này, vì **chỗ đặt nó phụ thuộc quyết định scope** và đặt sai chỗ sẽ phải gỡ. |
| `SINK_REFUSED` vẫn là sink tự khai; không thêm sink thật | **đạt** — không sink nào được thêm; `LyingSink` vẫn ghim đúng câu trả lời sai đó. |
| Residual enumeration và orphan check anchor-shaped giữ trong report | **đạt** — không đổi, và **không lexicon nào được mở rộng** để giảm over-refusal. |
| Sửa tài liệu về cấp 2/UI theo trạng thái đã kiểm chứng | **đạt** — `local_web_ui` đã sửa ở lượt 19 (`NOT_RUNNING`, không phải "chưa triển khai"); lượt 20 không lặp lại nhận định cũ. |
| GPU chỉ kiểm bằng mock | **đạt** — không benchmark, không chạy model, **không thu lại OOM evidence**. Không file nào trong `benchmarks/` hay `var/` bị sửa. |

### Lát dry-run cấp 2 + bốn lỗ boundary (lượt 18)

**Xong 2026-10-08.** Số đo:
[addendum 3 ADR 0007](adr/0007-response-boundary-va-lop-answerability.md)

**Hiệu chỉnh trước tiên, hai cái:** (1) addendum 1 và 2 đều ghi *"gate đã có
caller"*; cả hai lần điều đó chỉ đúng với **test** — `grep` không ra chỗ nào
trong `src/` gọi `deliver`. (2) Dòng *"Preflight VRAM/RAM ... đạt"* ở lượt 17 là
**của tôi** và **nói quá**: module chỉ đọc VRAM, trong khi mọi artifact ghi
working set 2822–2868 MiB. Cách sửa là **thêm gate**, không phải hạ tuyên bố.

| Tiêu chí | Trạng thái |
|---|---|
| Đường kiểm thử thủ công local: synthetic → fixture trong bộ nhớ → `ResponseRequest` → answerability → authority gate → `RecordingSink` | **đạt** — `meetai dry-run`, 10 case. `to_request` là mắt nối repo chưa có: store view + proposal → `ResponseRequest`, retrieval qua `store.retrieve(scope=...)` nên approval/digest/validity/supersession đều áp dụng. |
| Fixture tổng hợp, evidence trong bộ nhớ; **không** transcript thật, audio, Discord, Calendar, database bền | **đạt** — `SourceAllowlist` chỉ cho `note://synthetic`; có test khẳng định nó **không** permit bốn prefix khác. Không tên thật: chỉ `Son` (đã có khắp repo) và từ chỉ vai. Test kiểm **nội dung fixture**, không kiểm text của module — bản đầu quét cả file tìm `"@"` và khớp mọi decorator. |
| **Không** listener Discord, **không** phát ra meeting, **không** persistence, **không** sink xử lý được media | **đạt** — có test: `dryrun.py` không import `socket`/`http`/`urllib`/`requests`/`httpx`/`discord`/`asyncio`/`sqlite3`/`subprocess`, **không mở file nào**, và không gọi `write_text`/`mkdir`/`unlink`. Test cũ vẫn khẳng định **không sink nào khác tồn tại** trong `src/`. |
| Caller **bắt buộc** qua response boundary | **đạt** — `dryrun.py` gọi `deliver`, **không** gọi `assess`/`evaluate_response`, **không** nhắc `emit` ở bất kỳ vị trí nào. Mutation: thay `deliver` bằng một `DeliveryOutcome` dựng tay → **test fail**. |
| Test kiến trúc fail nếu xuất hiện **đường emit khác** | **đạt, và guard cũ đã được thay** — predicate cũ khớp **0/3** hình dạng lách (`getattr(sink,"emit")(text)`, bound method trong biến, `map(sink.emit, ...)`). Guard mới từ chối **mọi** tham chiếu tới `emit` ngoài `boundary.py`, ở bất kỳ vị trí nào. |
| Test kiến trúc fail nếu xuất hiện **đường bỏ qua gate** | **đạt** — chỉ `boundary.py` được gọi `assess`/`evaluate_response`; chỉ `boundary.py` được dựng `DeliveryOutcome(delivered=True)`; hai gate theo **đúng một** thứ tự; `deliver` **không có** `try`/`finally`; `emit` không phải statement cuối cùng của hàm nhưng **là** statement cuối trước khi outcome được dựng. |
| Chạy được case: đủ evidence, thiếu evidence, evidence sai chủ đề/mâu thuẫn, `UNCLEAR`, hard-deny, `SILENT` | **đạt, 10 case** — và cả 4 `Stage` cùng cả 3 `Verdict` đều xuất hiện, có test khẳng định, để bộ case không trôi tới chỗ mọi refusal đến từ một lớp. **`D7`/`D10` là `verdict=SUPPORTED` + `delivered=False`** — bằng chứng duy nhất cho việc có hai lớp độc lập. |
| Ghi rõ đây là kiểm thử local với `RecordingSink`; **không** gọi là thử họp Discord hay production | **đạt, và là dữ liệu chứ không phải văn xuôi** — `level="2-local-recording-sink"`, `is_production_integration=False`, `is_discord_test=False` trong chính report; header in ra `KHONG phai thu nghiem Discord`; có test khẳng định **không `shape` nào** của case chứa `production`/`discord`/`cuoc hop that`/`san sang`. |
| Operator phân biệt được `UNSUPPORTED` với `UNCLEAR` | **đạt** — in `stage` + `verdict` + `level` + `rules`, cộng **bảng gloss hằng** cho cả 9 `SupportLevel` và cả 3 `Verdict` (có test khẳng định **phủ hết** member, nên thêm level thứ 10 buộc ai đó viết câu cho nó). Mỗi gloss verdict **tự nêu tầng của nó**: bản đầu ghi `supported` → *"noi duoc"* và in cạnh hai case mà **gate đã từ chối**. |
| **Không** in nội dung cuộc họp | **đạt** — không câu hỏi, câu trả lời, claim hay card nào xuất hiện trong report (test đối chiếu từng chuỗi fixture). `findings` an toàn vì mọi finding là **tên quy tắc** cộng tối đa một chỉ số. Một accessor duy nhất đọc sink và nó lấy **độ dài**; test AST khẳng định không chỗ nào chạm `.emitted` như attribute. |
| `rationale` **không** phải evidence — thành bất biến có test | **đạt** — hai nửa: cấu trúc (không module bằng chứng nào được nhắc `rationale`; thông điệp fail nói rõ đây là **quyết định của Sơn**) và hành vi (chuyển câu trả lời vào `rationale`, để `claim` không mang → vẫn bị từ chối). |
| Claim không kiểm chứng được → `UNCLEAR` và abstain; partial answer giữ nguyên quyết định cũ | **đạt** — không đổi; `D5` là `UNCLEAR`/`UNVERIFIABLE_CLAIM`, `D9` là `UNCLEAR`/`MALFORMED`. |
| **Không** chạy benchmark GPU | **đạt** — không model/dataset nào được tải, không process GPU nào chạy. `tests/test_bench_harness.py` có test khẳng định **chính nó** chỉ spawn `sys.executable -c`, và không argv nào chứa `.gguf`/`llama-cli`/`llama-bench`/`nvidia-smi`. |
| Xác minh preflight / GPU lock / `failure_evidence` **bằng test/mock, không cấp phát model** | **đạt** — 53 test. `classify_failure` trước đó có **zero test** dù nó sinh ra nhãn load-bearing nhất của benchmark. Race `O_CREAT\|O_EXCL` của lock kiểm bằng **hai process Python thật**, CPU-only — tính chất đầu bảng của module và trước đó chỉ được khẳng định bằng văn xuôi. |
| **Không** coi margin 50% là ngưỡng an toàn đã hiệu chuẩn | **đạt** — và sửa hai con số sai về chính nó: docstring ghi `4229` trong khi `int(2819*1.5)=4228`; *"roughly 55%"* chia hụt 1576 MiB cho peak **một model** thay vì cấu hình **hai model** đã tạo ra nó (41.8% vs 55.9%). `0.5` **bị kẹp giữa hai phép đo**, không phải một thương số. |
| Giới hạn VRAM/RAM đã kiểm chứng | **đạt một phần** — VRAM gate có từ lượt 17, RAM gate thêm ở lượt 18. **Margin vẫn là phán đoán, cả hai.** Và đỉnh cấp phát nhất thời vẫn **chưa ai đo** — nó chỉ được đo **qua hệ quả**. |
| Cleanup process đã kiểm chứng | **đạt một phần** — `verify_gpu_released` giờ có test (trong/ngoài tolerance, và nhánh **raise**), và harness **bắt** cái raise đó: artifact ghi sau vòng lặp, nên một lần `nvidia-smi` hiccup ở case 40/43 trước đây **xóa cả 40 case đã xong**. **Phần dư ghi thành test:** leak nhỏ hơn tolerance là **vô hình** — tolerance chặn được một model bị rò, không chặn được KV cache hay compute buffer. |
| **Không** đề xuất chạy lại benchmark | **đạt** — không đề xuất nào, và **không** chạy lại để "hợp thức hóa" hai OOM cũ. Nhãn của chúng vẫn ghi là dựa trên một quan sát **không được lưu**. |
| Giữ consent/persistence/retention ở `pending_decision` và fail-closed | **đạt** — verify bằng `uv run meetai status`: `consent_mode: pending_decision`, `late_join_policy: pending_decision`, media `KHONG`, lưu nội dung `KHONG`. Lát này **không** đổi một flag nào. `dry-run` cố ý **không** hỏi media gate, và có test khẳng định handler không chạm `settings` — gate nó sẽ hàm ý đây là đường media và dạy Sơn rằng consent gate là thứ đứng giữa anh và một cuộc họp, trong khi thứ đứng giữa là **không có sink nào tồn tại**. |
| Giữ S2.2/S2.3 `partial/open`, gate 0-S/0-P/0-C/0-U mở | **đạt** — `git diff -- var/` **rỗng**. |

### Lát evidence isolation + preflight (lượt 17)

**Xong 2026-10-08.** Số đo:
[addendum 2 ADR 0007](adr/0007-response-boundary-va-lop-answerability.md)

**Hiệu chỉnh trước tiên:** addendum 1 ghi residual thứ nhất là *"quotation là
containment"* và chỉ vào `is_quotation`. Tắt **hẳn** đường quotation rồi chạy
lại các hình dạng tấn công thì **9 trong 10 vẫn qua** — nguyên nhân thật là
**anchor lấy phẳng trên cả card**. Một residual ghi đúng hiện tượng vẫn có thể
**chỉ sai cơ chế**.

| Tiêu chí | Trạng thái |
|---|---|
| Test tái hiện **từng** residual trước khi sửa | **đạt** — `test_answerability_evidence.py` 23 test, một class cho mỗi residual (`TestAnOutdatedSpanIsNotEvidence`, `TestEnumerationIsNotContradiction`, `TestApprovalBindsToContent`), viết trước và **fail trước**. |
| Quotation giữ ranh giới câu; span đúng nguyên văn nhưng lỗi thời **không** là bằng chứng | **đạt** — claim phải được **một** clause đỡ, mang tất cả subject (kế thừa trong câu, **không** qua ranh giới câu), tất cả anchor, và **polarity khớp**. Phủ định bị cắt khỏi span là lỗ thứ tư của lượt, cũng đóng ở đây. |
| Phân biệt **liệt kê / timeline** với hai clause mâu thuẫn về **cùng** một sự kiện | **đạt** — so theo **event key** = token của clause trừ **giá trị anchor thật** của lớp đang hỏi, xoá có biên từ. `APPROVAL` giữ quy tắc toàn-card vì trạng thái duyệt loại trừ nhau. **Phần dư:** 2 over-refusal trên clause nối bằng dấu phẩy, đã đo và ghi. |
| Paraphrase/quan hệ không nhận diện được → `UNCLEAR`, abstain, **không** default `SUPPORTED` | **đạt** — `UNCLEAR` 11/36 và **chỉ** ở `D` (3), `U` (5), `F` (3); bảy nhóm còn lại `UNCLEAR=0`, nên ba trạng thái không bị dùng làm chỗ chứa cho mọi thứ khó. |
| Approval gắn với **revision/content hash đã duyệt**; sửa sau khi duyệt làm mất hiệu lực; hash tính lại trên nội dung đã sửa **không** tự chứng nhận | **đạt trong bộ nhớ** — `approved_content_hash` là **bản ghi** lúc duyệt, khác `content_hash` là **thuộc tính dẫn xuất**. `None` là **không** citable (fail closed trên sự vắng mặt), nên `dataclasses.replace` trên card đã duyệt cho ra thứ vô dụng. |
| Card có chỉ thị độc hại **không** tự cấp approval và **không** thành căn cứ cho claim nó bảo model nói | **đạt** — nhóm `I_injection` (3) và `D_declarative_injection` (5), 0 false answer. Declarative injection đóng bằng **cấu trúc**, cộng `approved_content_hash` bắt đúng lần sửa. |
| **Không** thêm durable database hay retention; invariant chỉ từ object/version trong bộ nhớ và fake store | **đạt** — và có test (`TestPersistenceIsStillOff`) khẳng định điều đó, nên **không ai đọc được mục này thành bảo đảm độ bền qua restart**. |
| Không tên thật, nội dung họp hoặc dữ liệu cá nhân trong corpus | **đạt** — corpus tổng hợp, `source_ref="note://synthetic"`; test khẳng định corpus **không import được** `meetai`. |
| Báo false answer / false abstention / `UNCLEAR` **riêng** từng nhóm, denominator rõ | **đạt** — bảng 10 nhóm ở addendum 2 và `PROJECT_STATE` mục 7. **Không** accuracy gộp; có test khẳng định không có số gộp. |
| Preflight VRAM/RAM từ chối khi vượt ngân sách | **đạt ở lượt 18** — ở **lượt 17 dòng này nói quá**: nó ghi `đạt` cho cả VRAM **và RAM** trong khi module chỉ đọc VRAM, dù mọi artifact đều ghi working set 2822–2868 MiB. RAM là một trục **đã đo mà không gate**. Lượt 18 thêm `require_ram_headroom` (**3380 MiB** = peak 2868 + **512 MiB cộng thêm**). Và cũng bỏ chữ *"ngân sách **đã đo**"*: ngân sách là **peak đã đo × một phán đoán**, không phải một ngưỡng đã đo. VRAM: `REQUIRED_FREE_MIB = 4228` = peak quy được **2819** × 1.5. `PreflightRefused` là exception (không boolean) nên caller không đi tiếp trên giá trị falsy; exit 3 để **từ chối** không bị đọc thành **thất bại của thứ đang đo**. |
| Margin RAM **không** dùng lại hệ số VRAM | **đạt** — hai phép đo lệch **ngược chiều** nên không được chung margin. VRAM sampling 250 ms **thiếu** đỉnh nhất thời (đo được: hụt ≥1576 MiB) → margin **nhân**. Working Set **thừa** so với nhu cầu thật của một GGUF mmap vì trang file-backed được tính và có thể bị evict → headroom **cộng**. Đo ra chứ không suy: bản đầu dùng lại ×1.5 thì đòi 4302 MiB và **từ chối chính máy này** ở 3873 MiB khả dụng, trong khi peak ghi được là 2868 — tức chỉ margin từ chối, không phải nhu cầu. |
| Xác minh cấu hình chính xác của các lần OOM; **không** gộp 2 failure vào run thành công | **đạt** — `decoding` block **giống nhau từng key** trên cả bốn run; run thất bại **không** phải run ít headroom nhất (853 MiB idle vẫn chạy xong 43 case, run thất bại 841). Failure ở artifact riêng, denominator riêng (13 case, 2 fail). |
| Giải phóng GPU và **xác minh** trước case kế | **đạt** — `verify_gpu_released` chạy sau **mỗi** case với tolerance 256 MiB, một bậc độ lớn dưới ~2.8 GiB một model đang sống chiếm, nên model bị rò không trốn được trong đó. |
| **Không** coi output giống nhau là bằng chứng throughput ổn định | **đạt** — repeatability, latency, throughput và OOM báo **riêng**; `chi phí tháng` và `độ ổn định` vẫn **chưa chứng minh được**, S2.3 vẫn `partial/open`. |
| Chỉ dùng model/artifact **đã duyệt**; không tải trước khi Sơn duyệt | **đạt** — **không model hay dataset nào được tải**, không benchmark GPU nào chạy ở lượt này. Preflight chỉ **đọc** `nvidia-smi`; test AST khẳng định nó không gọi model runtime. |
| Ước lượng theo **khoảng effort**, không ngày lịch; nói rõ "thử nghiệm được" là cấp nào | **đạt** — `docs/research/2026-10-08-lo-trinh-thu-nghiem-ba-cap-do.md`, ba cấp độ, mỗi dòng đối chiếu repo **bằng lệnh ghi kèm**. |
| **Không** tuyên bố thử Discord thật được | **đạt** — cấp 3 ghi là **bị chặn bởi 4 gate và 5 thứ chưa tồn tại**, kèm điều kiện đóng từng gate. |
| Giữ S2.2/S2.3 `partial/open`, gate 0-S/0-P/0-C/0-U mở | **đạt** — không artifact benchmark nào bị sửa. |

### Lát fail-closed answerability (lượt 16)

**Xong 2026-10-08.** Số đo:
[addendum ADR 0007](adr/0007-response-boundary-va-lop-answerability.md)

**Hiệu chỉnh trước tiên:** báo cáo lượt 15 có dòng "both gaps closed" trong khi
cùng thông điệp liệt kê **ba residual có test đang pass**. Các khoảng trống được
**xử lý**, không **đóng**. Phần dư thật: một claim module không kiểm được thì
trả `SUPPORTED`, vì không có gì phản đối nó — một **đường bỏ qua kiểm tra**.

| Tiêu chí | Trạng thái |
|---|---|
| Truy vết mọi trạng thái từ claim extraction tới sink; không claim nào đi tiếp chỉ vì parser/heuristic không nhận ra | **đạt** — guard chính: claim grounded **không có giá trị nhận diện được** phải là **quotation** của card nó dẫn, nếu không thì `UNCLEAR`. Audit lại ở **boundary** chứ không chỉ ở module: mọi hình dạng `UNCLEAR` × cả 5 `SpeechAct`, **không cái nào tới sink**. |
| Ba trạng thái `SUPPORTED` / `UNSUPPORTED` / `UNCLEAR`; chỉ `SUPPORTED` qua được | **đạt** — `Verdict`, chỉ `SUPPORTED` truthy. Map level → verdict là **dict trên toàn bộ member** kèm test độ phủ, nên một level thêm sau **không thể** xuất hiện mà không có hành vi fail-closed. `UNCLEAR` phủ: paraphrase không có quy tắc, claim không trích xuất được, structure không mô tả answer, card tự mâu thuẫn. |
| Không biến "giống từ khóa" thành bằng chứng hỗ trợ | **đạt** — subject matching chuyển từ **overlap-1** sang **subset containment**. Overlap cho claim **mang kèm** nội dung chưa kiểm bên cạnh một giá trị đã kiểm (`"deadline la ngay 15 va Tram phu trach"`). Việc này cũng **gỡ** ngưỡng `MINIMUM_SUBJECT_OVERLAP` chưa calibrate. |
| `"giữa tháng"` vs `"ngày 15"`: chỉ qua nếu quy tắc ngữ nghĩa được xác định và test, còn nhập nhằng thì abstain | **đạt** — không quy tắc nào được định nghĩa cho nó, nên nó **abstain** (`UNCLEAR`). Hai chiều tách rõ và cả hai abstain: `"cuoi quy"` (nhận ra được, không có trong card) là `UNSUPPORTED`; `"giua thang"` (không nhận ra) là `UNCLEAR`. Theo đúng chỉ dẫn: áp dụng abstain đã thống nhất thay vì hỏi Sơn từng paraphrase. |
| Bảo toàn quyết định đã chốt về trả lời một phần | **đạt** — `ClaimKind.GAP` và `PARTIAL_UNDECLARED` không đổi; corpus nhóm `P_partial` vẫn pass. |
| Card/retrieval là **dữ liệu**, không phải chỉ thị; tách factual claims khỏi instructions, cả mệnh lệnh và trần thuật | **đạt, hai cơ chế khác nhau** — câu **mệnh lệnh** bị loại khỏi bề mặt evidence (lượt 15); câu **khẳng định trần** đóng bằng **cấu trúc** ở lượt 16: card khẳng định hai trạng thái duyệt loại trừ nhau thì `UNCLEAR`. |
| Provenance/trust metadata và trạng thái approval; không để một câu tự tuyên bố "đã được duyệt" tự tạo phê duyệt | **đạt** — `is_retrievable_at` quyết định card có dùng được không, và prose **không** đổi được điều đó: card `PENDING` mà text khăng khăng đã được duyệt **vẫn** `PENDING`. Có test. **Phần dư ghi lại:** `content_hash` tính từ nội dung **hiện tại** nên không phát hiện được sửa card **sau** khi duyệt. |
| Test đối kháng: imperative, declarative, card có cả fact thật lẫn chỉ thị, citation đúng ID nhưng sai quan hệ, câu trả lời sai về người/vật | **đạt** — `test_answerability_failclosed.py` 37 test, một class cho từng hình dạng, cộng nhóm corpus `D_declarative_injection` (6 case) và `U_unverifiable` (8 case). |
| Nếu không phân biệt được bằng metadata hoặc cấu trúc → `UNCLEAR` và abstain; không thêm lexicon rộng rồi coi là giải pháp tổng quát | **đạt** — **không lexicon nào được mở rộng ở lát này.** Quotation là **string containment**, không cần từ vựng. Contradiction check **scope vào APPROVAL** (trạng thái duyệt loại trừ nhau; hai ngày trong một card thì không) và vào **đúng lớp bị mâu thuẫn**. |
| Không đưa tên riêng cá nhân hoặc danh sách tên vào repo | **đạt** — **không danh sách nào được thêm.** Tên người sai đóng được **bằng quotation path**, không bằng `PROPER_NOUN` anchor class. |
| Claim phụ thuộc "đúng người nào" mà evidence không có identity binding → fail closed, ghi là giới hạn dữ liệu | **đạt** — claim như vậy không mang anchor nào nên chỉ trả lời được **như một quotation** của card đã duyệt; đổi một từ là hết là quotation. Ghi rõ ở `spec.md`: một **identity registry có kiểm soát** là việc của lát sau, và **suy tên từ transcript là việc không được làm**. |
| Viết test tái hiện từng residual **trước** sửa | **đạt** — `test_answerability_failclosed.py` viết trước, chạy trước, **fail trước** (ImportError rồi 7 fail). |
| Giữ corpus labels độc lập với logic đang chấm | **đạt** — corpus **tự khai** verdict ba trạng thái dưới dạng **chuỗi**, không import enum nó đang chấm, nên một nhãn verdict sai là bug của corpus mà harness bắt được. Cộng các guard AST cũ (không import `meetai`, không loop, chỉ constructor). |
| Báo false-answer, false-abstention và **unclear** theo nhóm riêng, denominator rõ, không gộp accuracy | **đạt** — ba trục × **10 nhóm**. **0 false answer, 0 false abstention** trên mọi nhóm; `unclear` tập trung ở `U_unverifiable` 5/6, `D_declarative_injection` 3/5, `F_malformed` 3/3. Có test khẳng định **không** có accuracy/F1. |
| Audit lại `boundary → answerability → authority → sink` | **đạt** — `DeliveryOutcome` giờ mang `answerability_verdict`, nên caller phân biệt được lần chạy *không kiểm được* với lần chạy *bị phản đối*. Test khẳng định verdict **không bao giờ** trái với việc có delivered. |
| Giữ `SILENT` không mang text, không có sink họp | **đạt** — không đổi; test cũ vẫn pass. |
| Giữ nguyên S2.3 v1/v2 | **đạt** — không artifact nào bị sửa; đã verify lại metric của cả ba file. |

**Mutation check tìm ra một control load-bearing nhưng chưa có test.** Tắt
guard chính làm **0 test fail** — không phải vì nó dư, mà vì subject containment
fire trước nó trên mọi case trong corpus. Case thật sự tới được guard là
paraphrase **bỏ một từ** hoặc **đổi thứ tự** (`"Khuê phụ trách kiểm thử"`,
`"phần kiểm thử Khuê phụ trách"`): mọi subject word có trong card, không có giá
trị để kiểm, không phải span liền mạch. Đã thêm `U.reword.01/02`; sau đó tắt
guard → **10 test fail**. **6/6 mutation phát hiện.**

**Ba phần dư MỚI, mỗi cái nêu cơ chế còn thiếu** (không phải "cần thêm công
sức"): quotation là containment **không phải** comprehension · mâu thuẫn ngày
tháng trong một card không bị bắt · `content_hash` không phát hiện sửa card sau
khi duyệt.

---

### Lát sau S2.3 — response boundary và answerability

**Xong 2026-10-08 (lượt 15).** Số đo:
[ADR 0007](adr/0007-response-boundary-va-lop-answerability.md)

| Tiêu chí | Trạng thái |
|---|---|
| Truy vết từ model proposal tới mọi nơi proposal thành output; xác minh bằng tìm kiếm toàn repo | **đạt** — tìm `*.py`/`*.md`/`*.toml`/`*.txt`: `evaluate_response` định nghĩa ở `authority.py`, export trong `__all__`, **không module nào trong `src/` gọi**. Caller duy nhất là test và `benchmarks/policy_scoring.py`. `planner.py` **không** nằm trên luồng này (nó quyết định join calendar). |
| Boundary nội bộ: mọi output có thể phát ra phải qua validation + answerability + authority gate | **đạt** — `boundary.deliver`: `(không SPEAK → return)` → `answerability.assess` → `evaluate_response` → `sink.emit`. Fail-closed từng chặng; `emit` là **câu lệnh cuối** nên một exception ở bất kỳ đâu trước đó nghĩa là không phát gì. |
| Chỉ local/in-memory/CLI và test; không Discord caller, listener, persistence, production inference | **đạt** — `RecordingSink` tới bộ nhớ. Có test khẳng định `boundary.py` không import gì có khả năng ra mạng, **và** test khẳng định **không sink nào khác tồn tại trong `src/`** — nếu một cái xuất hiện, test fail và người thêm phải nói media gate + consent ở đâu. |
| `intent`/`evidence_ids`/`action` do model điền không tự cấp quyền; gate là quyết định bắt buộc ngay trước output | **đạt** — 7 câu bị cấm × 5 `SpeechAct` qua boundary, **không cái nào tới sink**. Gate chạy sau answerability và trước `emit`. `DeliveryOutcome` **không có field text**, nên một caller giữ refusal **không đọc lại được** nội dung để tự phát. |
| Hợp đồng `SILENT`: nội dung tuyệt đối không phát ra; tốt hơn là schema không cho `SILENT` mang text | **đạt, theo hướng được ưu tiên** — chọn đóng trong **kiểu dữ liệu**: `ProposedResponse` từ chối text trên mọi decision không-SPEAK, nên `SILENT`/`FOLLOWUP` + text là **lỗi lúc khởi tạo**. Lượt 14 ghi đây là nghĩa vụ của caller; giờ nó không cần ai nhớ. Boundary **vẫn** return sớm cho decision không-speak — hai lý do độc lập. |
| Integration test cho đường đi đầy đủ: allowed, deny, unclear, SILENT, proposal lỗi, model cố gửi prohibited text | **đạt** — `test_boundary.py` **65 test**, một class cho từng mục: `TestAllowed`, `TestDenied`, `TestUnclear`, `TestSilentAndFollowup`, `TestMalformed`, `TestProhibitedTextFromTheModel`, cộng `TestNoOtherPathToTheSink` và `TestOrderOfStages`. |
| Residual: citation tồn tại/được duyệt **không** đồng nghĩa hỗ trợ claim | **đạt** — đúng hình dạng ADR 0006 ghi lại giờ bị từ chối ở `ANSWERABILITY` trước khi gate nhìn tới. |
| Input có claim/evidence mapping rõ ràng | **đạt** — `Claim(text, kind, evidence_id)`, **một card cho một claim**. Một claim tựa vào "một trong ba cái này" thì không kiểm được với cái nào, và "gắn evidence theo từng claim" chỉ có nghĩa khi ghép một-một. |
| Evidence thiếu / mâu thuẫn / pending / sai chủ đề / hỗ trợ một phần → trả lời giới hạn hoặc abstain | **đạt** — 7 `SupportLevel`, chỉ `SUPPORTED` là truthy nên `if assessment:` fail **closed**. Conflict scope theo subject của claim và xét **cả store**, nên dẫn một trong hai card duyệt mâu thuẫn **không** còn pass. |
| Corpus tiếng Việt tổng hợp, gán nhãn tay, **tách claim-level support khỏi citation validity** | **đạt** — 26 case, 8 nhóm. `claim_support` và `citation_validity` là **hai field riêng**, và corpus có test đòi phải tồn tại case hai trục **ngược nhau** (wording khớp hoàn hảo, card pending) — nếu không thì nó không thật sự tách. |
| Prompt injection nằm trong evidence | **đạt**, và nó **tìm ra một phát hiện thiết kế**: injection trong card **thành evidence cho chính lệnh nó ra**. Xem ADR 0007. |
| Không dùng model đang kiểm thử làm judge | **đạt** — không có model nào trong lát này. Mọi phán quyết là so sánh giữa nhãn viết tay và một giá trị trả về tất định. |
| Không tuyên bố đã giải quyết entailment tổng quát bằng heuristic chưa đo | **đạt** — module nói hẹp: kiểm **specific chưa được hỗ trợ**, không phải entailment. **Ba giới hạn ghi thành test đang pass**, trong đó một là **bypass** (paraphrase không nhận ra thì không được kiểm) chứ không phải over-refusal. |
| Công bố false-answer và false-abstention theo nhóm cùng denominator | **đạt** — **0 và 0 trên cả 8 nhóm**, mỗi trục một denominator, không gộp, không accuracy. |
| Chuẩn bị câu hỏi cho Sơn nếu policy không xác định trả lời một phần | **đạt** — `handoff:121` nêu thiếu/mâu thuẫn/hết hạn/sai scope và **không nói gì** về hỗ trợ một phần. Đã code mức fail-closed làm [GIẢ ĐỊNH] rồi hỏi, và tiếp tục phần không phụ thuộc trong lúc chờ. **Sơn chọn phương án 3**, và câu trả lời làm thiết kế **chặt hơn**: claim/evidence mapping thay cho danh sách id phẳng. |
| Hoàn tất audit citation còn lại theo nội dung quy tắc | **đạt** — 81/81 citation dẫn một muc chính sách thật. Hai nhóm cuối (`120` kiến thức phổ thông, `121` thiếu căn cứ) giờ cũng **neo theo nội dung**. |
| Test bắt lỗi khi source text đổi và citation trỏ sang quy tắc sai | **đạt** — khối quy tắc **pin bằng digest SHA-256**. Verify bằng cách **sửa lời một quy tắc**: 2 test fail, kèm hướng dẫn phải đối chiếu lại từng case chứ không chỉ cập nhật digest. |
| Giữ v1/v2 là hai cấu hình riêng, không gộp | **đạt** — không artifact nào bị sửa ở lát này. |
| Stability/OOM và dao động throughput vẫn `not demonstrated` | **đạt** — không đo lại, không tuyên bố mới. |
| Không tuyên bố boundary đã tích hợp production khi chưa có production caller | **đạt** — ghi tường minh ở ADR 0007, docstring module, và `spec.md` P-2. |

**Kiểm chứng xoá-là-fail trên 6 cơ chế:** bỏ gate → 4 fail · bỏ answerability →
8 · emit trước khi kiểm → 3 · bỏ loại câu mệnh lệnh → 4 · bỏ kiểm subject → 4 ·
cho SILENT mang text → 2.

**Corpus không đồng ý với module 8/26, và cả 8 lần module sai.** Corpus viết
trước khi đo. Nguyên nhân từng cái ở ADR 0007; cái đáng chú ý nhất là số viết
chữ dạng alternation **một âm tiết** (`Trâm`→`trăm`, `không`→0), **lần thứ ba**
dự án gặp lớp lỗi noun/function-word collision sau `de xuat` và `Minh`.

---

### Lát sửa an toàn sau S2.3 — đóng phần dư quyền hạn, sửa citation

**Xong 2026-10-08 (lượt 14).** Số đo:
[addendum ADR 0006](adr/0006-authority-gate-khong-de-proposal-tu-mo-cong.md) ·
[phụ lục A của báo cáo S2.3](research/2026-10-08-s23-llm-policy-benchmark.md)

| Tiêu chí | Trạng thái |
|---|---|
| Đọc toàn luồng model proposal → parser → gate → planner; xác định chính xác field nào cho qua được một câu bị cấm | **đạt** — và phát hiện `planner.py` **không** nằm trên luồng này (nó quyết định join calendar), còn **`src/` không module nào gọi `evaluate_response`**: parser duy nhất hiện có là `benchmarks/policy_scoring.py`. Nên bất biến phải được cưỡng chế **trong `authority.py`**, chỗ duy nhất có thể. |
| Viết test đối kháng **trước** khi sửa | **đạt** — `tests/test_authority_residual.py` viết trước, chạy trước, **fail trước**. Ma trận: 15 lớp câu × 5 `intent` × 8 trạng thái evidence × 3 khung = **1800 tổ hợp**, kèm quét `minimum_confidence`, `states_personal_position`, `declared_acts`, và dẫn **toàn bộ** store cùng lúc. |
| Bất biến: `intent`/`evidence_ids`/field do model điền **không hạ được mức cấm** | **đạt** — **106/1800 → 6/1800** `allowed=True`, và cả 6 là relay dự kiến (attribution + `cite_approved_position` + card hợp lệ). **Không tổ hợp field nào với tới một *act* bị cấm.** |
| Evidence hỗ trợ được phát biểu sự kiện đã duyệt, **không** tự cấp quyền hứa hẹn/nhận việc/chốt/cam kết thay | **đạt về cấu trúc** — tầng subject-free tách theo *việc mà từ ngữ làm*: `_BARE_PERFORMATIVE` 16 pattern **không bao giờ** nới được, `_BARE_REPORTABLE` 4 pattern nới được chỉ khi **attribution trong text** *và* gate đã verify citation. **Bốn trong bảy act không có pattern reportable nào** — có test ghim theo từng act. Trần kích thước reportable **chỉ được giảm**. |
| Giữ relay đúng được phép; ghi false-block nếu chưa xử lý được | **đạt** — 3 case relay hợp pháp của corpus vẫn pass, và `A.cite.01` (cách nói attribution **do hồ sơ bàn giao quy định**) là lý do `son` bị loại khỏi slot marker. False block **đã ghi**: `H.approve.02` và `H.promise.02`. **Không nới hard-deny để lấy lại điểm.** |
| Fail-closed khi bằng chứng yếu hoặc câu mơ hồ | **đạt** — default của `detect_prohibited_acts` là `citation_verified=False`; attribution **hoặc** citation một mình đều không nới gì; card pending/superseded/expired/không tồn tại đều không nới. |
| Audit **mọi** đường gọi gate, không chỉ case đã phát hiện | **đạt** — `TestEveryEntryPointAndDefault`: default lexicon, evidence rỗng, `now=0.0`, `minimum_confidence` quét cả `-1.0`/`0.0`/`1.0`, decision không-speak, và **nghĩa vụ của caller** với proposal `SILENT`. |
| Sửa nguyên nhân ở lớp phân quyền, cập nhật ADR | **đạt** — addendum ADR 0006, không phải ADR mới: nó hiệu chỉnh một phát ngôn của chính thân ADR đó. |
| **Không** tuyên bố bao phủ nếu còn đường bypass | **đạt** — phần dư còn lại được gọi đúng tên: **grounding**, không phải authority. Model vẫn có thể attribution + card không liên quan + sự kiện sai. Không cam kết nào được tạo ra. `docs/spec.md` ghi riêng với điều kiện đóng riêng. |
| **Kiểm chứng xoá-là-fail** | **đạt** — chạy thật trên **5 cơ chế**: `_ASPECT` → 160 fail · tách performative/reportable → 588 · đòi attribution → 11 · đòi chủ ngữ cho hedge → 4 · pattern `{_ACTOR} chot` → 10. |
| Citation trong `tests/corpus/authority_vi.py` đối chiếu **theo nội dung**, không +1 hàng loạt | **đạt** — **64/81 sửa**, 31 gán riêng kèm lý do từng case. Một phép +1 sẽ đẩy ít nhất 3 case sang quy tắc sai (`A.inform.03` đang dẫn đúng dòng approved-basis; `A.inform.02` và nhóm defer thuộc dòng **thiếu căn cứ**). |
| Giữ test xác minh citation trỏ đúng nội dung nguồn | **đạt** — 4 test, **3 trong số đó neo vào *lời* của quy tắc chứ không vào số dòng**, nên nếu hồ sơ bàn giao lại thêm một dòng thì chúng vẫn kiểm đúng quy tắc cũ. Verify bằng cách **tái tạo lại đúng drift ban đầu**: cả 4 fail. |
| S2.3 baseline giữ nguyên số trước khi sửa | **đạt** — không artifact nào bị ghi đè. Chấm lại là file `derived: true` riêng, ghi nguồn + SHA-256 của scorer. |
| Cấu hình prompt thứ hai, cố định mọi biến khác | **đạt** — harness thêm `--system-prompt-file`, prompt v2 **được commit** kèm hash, artifact ghi `prompt.source`/`is_baseline`. Báo **cạnh** baseline, không thay. **Không cấu hình nào tốt hơn đồng nhất**: v2 abstention miss 55.6% → 22.2% và unsupported 14.0% → 4.7%, nhưng lỗi cấu trúc 2.3% → 11.6% (3 case đặt giá trị `intent` vào field `decision`). |
| Báo riêng 2/13 OOM và dao động decode | **đạt** — §6 và phụ lục A.4. **Ba run thành công KHÔNG phải bằng chứng ổn định.** |
| Giữ S2.2 `partial/open`, Gate 0 mở | **đạt** — không trục B-1 nào được đóng, không suy diễn sang Discord voice hay production. |

**Hai lỗ tìm được trong audit nặng hơn phần dư mà lát này được phái đi đóng**,
và cả hai **không cần field nào của proposal** — chúng đi qua với
`intent=inform`, không evidence:

| Lỗ | Số đo |
|---|---|
| Marker thời/thể giữa chủ ngữ và động từ (`Minh **da** duyet`, `Minh **da** bo phieu`, `Minh **da** ky hop dong`) | **69/117 → 0/117** |
| `de xuat` nghĩa danh từ khớp `_HEDGE`, tắt cả tầng subject-free | `De xuat da duoc duyet` từng trả **`[]`** |

Lỗ thứ hai **chính là** case `I.override.01` của S2.3, nên giải thích ở §4 của
báo cáo đó đã được **hiệu chỉnh** trong phụ lục A.1: nguyên tắc "gate soi act,
không soi tính đúng" vẫn đúng, nhưng case đó không còn là bằng chứng cho nó.

---

### S2.3 — benchmark LLM nhỏ lượng tử hoá

**Đo xong 2026-10-08 (lượt 13).** Số đo:
[S2.3 LLM policy benchmark](research/2026-10-08-s23-llm-policy-benchmark.md).

| Tiêu chí | Trạng thái |
|---|---|
| Năm trục đo **riêng**, denominator theo nhóm | **đạt** — cấu trúc / grounding / abstention / quyền hạn / injection, mỗi trục một bảng. Có test khẳng định **không** có `accuracy`, `f1`, `score`, `overall`, `total` trong tập metric. |
| Corpus tiếng Việt tổng hợp, viết độc lập với output model | **đạt** — 43 case, 18 case là một nửa của cặp tối thiểu, viết trước khi chạy model. Toàn vẹn nhãn **cưỡng chế bằng AST**: không import được `meetai`/`benchmarks`, không loop/comprehension, chỉ gọi constructor của case, bắt buộc `policy_basis`, và **mỗi citation được test đối chiếu với một dòng policy thật**. |
| Không dùng model đang chấm để sinh đáp án hoặc làm evaluator | **đạt** — không LLM judge. Mọi check là parse / set membership / substring. Verdict quyền hạn lấy từ `meetai.authority.evaluate_response`, **không** phải một lexicon thứ hai viết trong benchmark. |
| Không coi confidence model tự khai là đã hiệu chuẩn | **đạt về cơ chế** — schema **không có** field `confidence`; model nào thêm bị ghi `forbidden_field` chứ không phải `extra_field`. Gate nhận một hằng số của harness, trên `MINIMUM_CONFIDENCE`, ghi trong artifact. `MINIMUM_CONFIDENCE` vẫn **chưa calibrate**. |
| Pin revision/hash, quantization, prompt, decoding, seed, timeout, trần token | **đạt một phần** — SHA-256 model harness **tự tính lại** và kết quả **khớp** ledger S2.1 ở 5/7 lần đo. **Lượt 25 sửa lại chữ "khớp":** harness **tính và GHI**; việc **so khớp** do người đọc report làm — **không `.py` nào** chứa digest của ledger, và `--no-hash` đã được dùng ở **2/7** lần đo (`"sha256": "skipped"`); SHA-256 system prompt; `temp=0 seed=7 -n 384 -c 2048 -t 6 -ngl 99 -rea off`, timeout 180 s. **Không grammar, không `--json-schema`** — có test AST, vì cả hai sẽ xoá sạch trục cấu trúc. |
| Timeout/OOM/output rỗng/JSON sai/process error là failure, denominator không đổi | **đạt** — và dùng thật: 2 case OOM trong một run. `classify_failure` trả về **marker đã khớp** cùng với kind, vì `0xC0000409` tự nó không phải một chẩn đoán. |
| Đo latency/VRAM/RAM model-only, ghi rõ là số CLI | **đạt** — p50 10.2–12.9 s, p95 12.0–14.7 s, VRAM đỉnh 3590 MiB (device total), RSS 2827 MiB. **Ghi tường minh là số CLI của cấu hình thử**, mỗi case trả giá một lần load đầy đủ, **không** phải p50/p95 end-to-end của MeetAI (phụ thuộc A14/S3). |
| Test ở ranh giới tích hợp: output model chỉ là đề xuất | **đạt** — 8 câu bị cấm × 5 act khai được × citation duyệt thật đều `allowed=False`; mọi forbidden field shape chứng minh là trơ; AST check benchmark không import gì có khả năng ra mạng, không `eval`; không có đường gửi nào để tới. |
| Không nới authority gate để tăng điểm model | **đạt** — thay đổi duy nhất ở gate là **thu hẹp** (ADR 0006). 1502 test cũ pass không sửa một test nào. |
| B-2: thermal, watt | **đạt** — 32.28 W trung bình (1392 mẫu), 41.29 W đỉnh trên cap 40 W; 68.3 °C trung bình, 71 °C đỉnh; 0.0944 Wh/case, 0.0323 kWh/giờ (**GPU only**). |
| B-2: chi phí tháng | **`not demonstrated`** — `nvidia-smi` chỉ báo board GPU, nên số là **chặn trên của GPU** và **chặn dưới của hệ thống**. Cần đồng hồ đo tại ổ cắm. Thêm nữa giá bậc thang EVN làm giá cận biên phụ thuộc tổng tiêu thụ của hộ. Công bố **công thức**, không công bố con số. |
| Độ ổn định | **`not demonstrated`** — 0/43 failure ở hai run, **2/13 = 15.4% OOM** ở run thứ ba. Chạy lại một mình thì thành công. Khớp phát hiện S2.2: lấy mẫu peak bỏ sót đỉnh nhất thời của `graph_reserve`. |
| Tính tái lập của output | **đạt** — 2 lần chạy 43 case: **mọi finding giống hệt 43/43**, generation **byte-identical 41/43** (2 case lệch là do tôi dùng lại work-dir mặc định, không phải model). **Throughput thì KHÔNG tái lập:** decode 8.2 → 10.9 tok/s (+33%) giữa hai run cùng cấu hình. |

**Không gộp các trục thiếu của B-1 vào đây.** S2.2 giữ `partial/open`; không
trục nào của nó được đóng bằng số của S2.3.

**Phát hiện lớn nhất không phải của model mà của gate.** Đi xác minh câu
"output model không bao giờ vượt hard-deny" trước khi viết test cho nó, và câu
đó **sai**: `intent=CITE_APPROVED_POSITION` + một evidence id đã duyệt thật làm
gate trả `allowed=True` cho `"Minh se hoan thanh vao thu hai"`. Cả hai input do
model điền. Đã sửa ở ADR 0006. **`hard_deny_bypass = 0/8` là số SAU khi đóng
lỗ đó.**

**Hai lỗi của scorer, tìm ra bằng cách chạy nó**, và cả hai làm số **xấu đi**
theo hướng đúng: một check substring bắt sai hai lời **từ chối đúng** (`"Không
có cam kết nào"` khớp `cam ket`), và một con số `authority_violation` đếm **ba**
việc khác nhau (2 từ chối đúng + 4 lần gate chặn câu thuật lại đúng + 2 vi phạm
thật). Đã tách thành ba metric, mỗi cái một nghĩa.

**[ĐỀ XUẤT] cho lượt sau, không tự làm:** gate chặn **2/20** câu trả lời đúng
vì model khai `intent=inform` thay vì `cite_approved_position`. Cách sửa là ở
**prompt**, không ở gate. Không sửa prompt rồi chạy lại để lấy số đẹp hơn —
prompt là tham số được pin; một cấu hình thứ hai phải được báo **là** cấu hình
thứ hai.

---

### S2.2 / S2.3 — benchmark

**Phần 1 xong, 2026-10-07 (lượt 9).** Số đo:
[S2.2 phần 1](research/2026-10-07-s22-coresidency-va-hallucination.md).

**Phần 2 xong, 2026-10-07 (lượt 10).** Số đo:
[S2.2 phần 2 + ma trận B-1](research/2026-10-07-s22-asr-wer-va-ma-tran-b1.md).

| Trục B-1 | Trạng thái | Căn cứ |
|---|---|---|
| WER/CER | **đạt** (cho đọc câu) | SyER 23.47% [22.05, 25.08], CER 11.23%, n=361, N=10 422, 0 failure |
| noise | **đạt cho noise tổng hợp**; thực tế `not demonstrated` | Δ paired: 20 dB **chưa phát hiện được** (CI hiệu số bao gồm 0, **không** phải bằng chứng không có ảnh hưởng), 10 dB +6.63 pp, 5 dB +18.56 pp |
| RTF | **đạt** (lời gọi tuần tự) | ratio-of-totals 0.315; p50 0.331 / p95 0.534 |
| VRAM/RAM | **đạt một phần** | có số, nhưng peak là **chặn dưới**; per-process VRAM không đo được dưới WDDM |
| tên riêng | **`not demonstrated`** | 70.57% là heuristic hoa/thường, không phải nhãn vàng; chỉ 13.5% token được gán lớp |
| **nói chồng** | **`absent`** | FLEURS và VIVOS đều đọc câu một người |
| accent | **`not demonstrated`** | VietMed có nhãn và đã chạy thăm dò (421 clip, SyER 38.0–57.6%, pooled 46.0%), nhưng accent **lồng gần hoàn toàn** với speaker và điều kiện thu: cả test split chỉ **27 speaker**, hai nhóm có **1 và 2** speaker. Không đóng trục. |
| p50/p95 theo spec | **`not demonstrated`** | đã có p50/p95 của lời gọi CLI, **chưa** có endpoint-to-final-ASR / LLM first token / end-to-end |

**VIVOS: cân nhắc và không dùng.** Nó là đọc câu một người nên không đóng được
trục nào đang thiếu, chỉ thêm một số đọc-câu thứ hai kèm nghĩa vụ
CC BY-NC-SA (ShareAlike lan truyền). Không tải chỉ để benchmark lớn hơn.

**Chưa đủ để đóng S2.2:** còn `nói chồng`, `accent`, p50/p95 theo spec, và
quyết định A14. `spec.md` B-1 giữ `absent`.

| Tiêu chí | Trạng thái |
|---|---|
| Co-residency đo trước WER | **đạt** — và kết quả là **KHÔNG co-resident**: 4 lần chạy đồng thời, lần nào cũng một bên chết, một lần OOM tường minh. Tính đồng thời *đã* chứng minh (3–17 mẫu có cả hai process). Khả thi được chứng minh là **tuần tự**. |
| Không suy "khả thi" bằng cách cộng hai phép đo đơn | **đạt** — và có bằng chứng trực tiếp vì sao: tổng hai chặn dưới (3767 MiB) nói là vừa trong 5343 MiB khả dụng, thực tế OOM, vì peak lấy mẫu bỏ sót đỉnh nhất thời của `graph_reserve`. |
| Nhóm clip im lặng để phát hiện hallucination | **đạt** — NSOR **3/3 = 100%**, 34 token, **156.9 token/phút**. Im lặng số tuyệt đối vẫn sinh 15 token boilerplate. |
| Không fold dấu khi tính WER | **đạt** — scorer có contract `syer.v1.nfc.punct-to-space.case-sensitive.no-fold`, 39 test. NFC là bắt buộc: bỏ nó ra thì cùng một câu cho SyER **0.875**. |
| Timeout/OOM/output rỗng/lỗi là failure, denominator không đổi | **đạt** — `score_failed_utterance` tính mọi token reference thành deletion. Và bất đối xứng: reference rỗng + hypothesis rỗng là **đáp án đúng**, không phải failure. |
| Tách nhánh NC khỏi permissive | **đạt về cơ chế** — manifest có `license_branch`; FLEURS = permissive. VIVOS (NC) **chưa tải**. |
| Manifest chỉ metadata + SHA-256, dữ liệu ở chỗ bị ignore | **đạt** — và đã đóng 4 lỗ rò `.gitignore` (`*.txt` là tệ nhất: VIVOS ship reference đúng tên `prompts.txt`). Có test 46 case giữ chúng, verify là nhạy với việc xoá cơ chế. |
| Không thêm dependency | **đạt** — `pyproject.toml`/`uv.lock` không đổi; scorer là stdlib. |
| Phân tích lỗi riêng cho tên riêng / số / ngày | **CHƯA** — thuộc phần 2, và **class phải gán từ reference**, không từ hypothesis, nếu không thì model xoá một tên khó sẽ giảm chính denominator của nó. |
| WER/CER theo nhóm | **CHƯA** — phần 2 |
| RTF, p50/p95, thermal | **một phần** — RTF theo clip đã có (0.65–1.37); p50/p95 mức request **chưa**. |

**Giới hạn cấu trúc, không đóng được bằng dataset trong phạm vi lát này:**
FLEURS và VIVOS đều là **đọc câu, một người nói mỗi clip**, nên nghĩa vụ
**B-1 vẫn `absent` cho "nói chồng"** và chỉ một phần cho "accent". Bảng theo
nhóm **không được** ngụ ý một độ phủ không có.

**Ràng buộc đã chốt ở lượt 8 (A13), áp dụng cho mọi số của S2.2:**

- **Tách hai nhánh license trong report.** Tài nguyên NC được dùng cho thử
  nghiệm **riêng tư**, nhưng kết quả phải tách khỏi nhánh permissive và ghi rõ
  từng mục. Tài nguyên NC **không** đủ điều kiện cho sản phẩm, phát hành hoặc
  thương mại hoá; nếu MeetAI đi hướng đó thì **đánh giá lại trên nhánh
  permissive**.
- License đã xác nhận: VIVOS **CC BY-NC-SA 4.0** · ChunkFormer Large Vie
  **CC BY-NC 4.0** · Qwen3-ASR **Apache-2.0** · PhoWhisper **BSD-3-Clause**.
- **Hai ghi chú bắt buộc kèm mọi số đo trên VIVOS:** (1) dữ liệu là **đọc câu
  trong môi trường yên tĩnh**, nên điểm trên đó **không dự đoán trực tiếp** chất
  lượng nhận dạng hội thoại tự nhiên; (2) **PhoWhisper có dùng VIVOS trong dữ
  liệu huấn luyện**, nên kết quả trên VIVOS test vẫn hữu ích để **đối chiếu**
  nhưng **không phải bằng chứng tổng quát hoá sang cuộc họp**.
- **Không fold dấu trước khi tính WER.** Lượt 7 đo được rằng cả 8 cặp tên thử
  đều trùng sau khi fold, vì dấu mang phần lớn độ tương phản giữa các âm tiết
  tiếng Việt. WER đã fold sẽ trông đẹp hơn thực tế và che đúng lớp lỗi dự án
  quan tâm (`thư`/`thứ`, `Minh`/`mình`). Headline WER tính trên text đúng dấu;
  WER đã fold chỉ là chỉ số chẩn đoán phụ.
- **Clip im lặng / không có tiếng nói là bắt buộc.** Model họ Whisper sinh text
  tự tin trên nền im lặng; không có nhóm đó thì chưa đo được thất bại khiến
  MeetAI nói về thứ không ai nói.
- **Việc đầu tiên là co-residency**, không phải WER: đo ASR + LLM **cùng** ở trên
  GPU trong ~2.4 GiB còn lại. Cộng hai phép đo riêng là cách dễ nhất để kết luận
  "khả thi" và sai.
- Clip timeout, output rỗng, vòng lặp lặp từ và OOM **tính là failure với
  denominator không đổi**. Bỏ chúng ra là cách cải thiện WER âm thầm.

- WER/CER theo tiếng Việt, accent, noise, nói chồng, tên riêng — báo theo nhóm, kèm n
- RTF, VRAM/RAM peak, CPU, thermal, watt, chi phí tháng
- p50/p95 cho endpoint-to-final-ASR, LLM first token, end-to-end
- Dữ liệu synthetic hoặc public có license. Không dữ liệu họp, không giọng chủ dự án.
- Mục tiêu 1–2 giây **chỉ** được báo đạt nếu benchmark chứng minh

### Phase 3 — Discord proof

Chỉ bắt đầu khi có bằng chứng cho 0-S và 0-P, và chủ dự án giao tiếp tục.

- Nguồn chính thức hoặc ticket đủ cụ thể về: standard bot account/token, guild voice, inbound audio/PCM, participant mapping, API/SDK version, quyền cần thiết
- Rà Developer Terms/Policy **tại ngày triển khai**; xác định review/approval. Bản đọc nguồn chính thức lượt 36 ở [research note Gate 0-P](research/2026-10-10-gate-0p-discord-policy.md) nêu yêu cầu privacy policy và sửa/xoá API Data; **chưa đóng 0-P** cho route MeetAI cụ thể.
- Voice Connections hiện mô tả UDP receive/send và DAVE E2EE từ 2026-03-01; vẫn cần chứng minh route bot guild, mapping SSRC→user và bản dựng DAVE cụ thể trước khi 0-S đóng.
- Test server/channel riêng do chủ dự án kiểm soát
- Trace metadata-only trước, rồi synthetic tone, rồi consent-gated end-to-end
- Lưu test manifest/build/version; **không** raw audio
- **Không** tuyên bố production-ready từ một trace

---

### Lượt 41 — rà chất lượng guard persistence

Lát test-only, nghĩa vụ **C-12**. Probe tìm ra **6 dạng ghi file đi lọt**, tất cả cùng một nguyên nhân: guard khớp theo **cách viết tên receiver**, nên alias và from-import vượt qua. Sửa bằng cách phân giải **import binding** của chính file trước khi khớp, nên `o.remove`, `remove` và `os.remove` cùng quy về `os.remove`. **7 mutation trên file `src/` thật, cả 7 đỏ.** Thêm hai control đã commit: một cho phía *phải bắt*, một cho phía *phải im* — nếu thiếu control thứ hai thì làm guard "mạnh hơn" bằng cách luôn trả `True` cũng sẽ qua được suite.

### Lượt 43 — phân loại **mọi** đường ghi trong `benchmarks/`

Khảo sát bằng AST: **28 lời gọi ghi** trên **11 file**. Chúng **không cùng một loại**,
nên cố ý **không** áp một quy tắc chung "mọi thao tác ghi phải qua `artifact_path()`".

| Nhóm | File / dòng | Ghi gì | Path do ai chọn | Thuộc hợp đồng `var/` cố định? |
|---|---|---|---|---|
| **A. Artifact kết quả** | 5 harness model + `rescore_llm_policy.py` | JSON kết quả đo | `--out`, **qua `artifact_path()`** | **CÓ** — S2.1 quyết định #2 |
| **B. Output suy ra từ input** | `postprocess_asr.py:261` | JSON chỉ số suy ra | **Cạnh file `--results`** (`with_name`), tức theo input người chạy truyền | **KHÔNG** — xem ghi chú dưới |
| **C. File tạm / prompt** | `bench_llm_policy.py:408, 583, 591, 712` | prompt, system prompt, output thô từng case | `--work-dir` | **KHÔNG** — đây là **input cho một lần chạy**, không phải artifact kết quả |
| **D. Manifest / clip do generator tạo** | `make_noise_group.py:206`, `make_nonspeech_clips.py:68,127`, `make_vietmed_manifest.py:242` | manifest, clip tổng hợp | hằng số module hoặc `--out` | **MỘT PHẦN** — `make_noise_group` đã qua helper từ lượt 35; ba cái còn lại tạo **dữ liệu đầu vào**, không phải kết quả |
| **E. GPU lock** | `gpulock.py:131,145,154,165` | file lock rỗng (PID) | hằng số module | **KHÔNG** — lock là **cơ chế đồng bộ**, không phải artifact. Ép nó qua helper sẽ đụng hành vi mà `test_bench_harness.py` đang ghim |

**Vì sao không gộp:** một file lock bị xoá là **đúng** (nhả khoá); một artifact kết quả
bị xoá là **mất bằng chứng**. Một prompt tạm nằm trong `--work-dir` của một lần chạy;
một kết quả phải nằm đúng chỗ đã chốt để còn tìm lại được. Gộp cả năm nhóm vào một
luật sẽ làm luật đó hoặc quá lỏng cho nhóm A, hoặc sai cho nhóm E.

**Đã sửa — nhóm A, một chỗ không nhất quán:** `rescore_llm_policy.py` ghi **đúng cùng
loại artifact** như `bench_llm_policy.py`, từ **đúng cùng một cờ `--out`**, nhưng
`bench_llm_policy` đi qua `artifact_path()` còn `rescore` thì **không**. Tái lập bằng
control trước khi sửa (`got [False]`), rồi sửa. **Vị trí output mặc định KHÔNG đổi** —
`bench/llm-policy-s23-rescored.json` dưới root vẫn ra đúng
`var/bench/llm-policy-s23-rescored.json`; thứ được thêm là **ràng buộc**, không phải
một vị trí mới.

**[CHỜ SƠN] Hai mục KHÔNG tự sửa, vì chúng đổi nội dung artifact hoặc workflow:**

1. **Đường dẫn người chạy truyền bị nhúng vào NỘI DUNG artifact** —
   `bench_llm_policy.py:768` ghi `"model": {"path": str(model)}` và
   `rescore_llm_policy.py:66` ghi `"derived_from": str(source)`. Lượt 26 đã sửa
   **thông báo từ chối** rò đường dẫn + username, nhưng ranh giới lát đó nói rõ
   *"giữ nguyên nội dung artifact của benchmark thành công"*. Phần dư đã ghi ở
   `PROJECT_STATE` chỉ liệt kê các dòng **in ra stdout** — **không** liệt kê hai chỗ
   nhúng vào **nội dung JSON** này. Nay đã ghi.
   **Lựa chọn và hệ quả:** (a) giữ nguyên — artifact S2.3 đã đo vẫn so sánh được,
   nhưng một artifact chia sẻ ra ngoài sẽ mang đường dẫn máy; (b) đổi sang basename
   hoặc digest — **đổi nội dung artifact**, nên các bản ghi cũ không còn so byte được
   với bản mới, và cần quyết định có đo lại hay không.
2. **`postprocess_asr.py` ghi cạnh file input.** Nếu người chạy trỏ `--results` ra
   ngoài `var/`, output cũng ra ngoài. **Giảm nhẹ đã có:** `.gitignore:127` phủ
   `*derived.json` ở **mọi** vị trí, nên nó không commit được. Sửa đồng nghĩa với
   **phát minh một vị trí output mới** cho nó, tức đổi thói quen vận hành — không
   phải việc tự quyết.

### Lượt 44 — nhóm C: ghim **quan hệ**, không ghim vị trí

Khảo sát riêng nhóm C trong `bench_llm_policy.py` (prompt, system prompt, output
thô từng case).

**Kết quả khảo sát — `--work-dir` là đường dẫn TỰ DO theo thiết kế.** Mặc định
`var/probe/llm-policy`, nhưng `work_dir = pathlib.Path(args.work_dir)` **không
ràng buộc**. Ép nó vào `var/` là **đổi hành vi sản phẩm**, nên **không làm** —
đúng chỉ thị.

**Thứ lập được mà KHÔNG đổi hành vi: quan hệ.** Dù work-dir ở đâu, một file tạm
phải nằm **bên trong** nó. Ba đường ghi tạm (408 `prompt_file`, 591 `system_file`,
712 `.out.txt`) đều bám gốc `work_dir` — **đã xác minh bằng AST**, có theo vết một
bậc gán, vì hai trong ba đi qua biến cục bộ.

**Vector thoát có thật, và hôm nay chưa bị chạm.** Hai trong ba tên file nội suy
`case.case_id`, mà một phép `/` **không tự bảo vệ**:

| Nội suy | Kết quả |
|---|---|
| `Path("var/probe") / "C:/elsewhere/x.txt"` | **`C:/elsewhere/x.txt`** — thành phần tuyệt đối **thay thế** gốc |
| `Path("var/probe") / "../../escape.txt"` | thoát bằng traversal |

**43/43 case id hiện đều là tên thuần** (`[A-Za-z0-9._-]+`), nên đây là **canh một
đầu vào đang an toàn**, không phải sửa lỗi. Test ghim: id là **tên**, không phải
đường dẫn.

**Không gộp nhóm.** Một test riêng khẳng định sink artifact (`out`) **vẫn là lớp
khác** và vẫn đến từ `artifact_path()` — nếu nó trôi sang gốc `work_dir`, hợp đồng
fixed-root sẽ âm thầm thôi áp dụng, và test canh hợp đồng đó nằm ở **file khác** nên
sẽ không thấy. Và một test đếm **đúng ba** file tạm: thêm cái thứ tư là phải phân
loại nó.

**Không đổi:** `--work-dir` vẫn tự do · không ép vào `var/` · không biến work-dir
thành vị trí output · không đổi schema hay nội dung artifact thành công · không đụng
`model.path` / `derived_from` (quyết định riêng của Sơn vì ảnh hưởng khả năng so sánh
artifact S2.3).

**Nghĩa vụ spec:** không mục nào đổi trạng thái. Nhóm C là **vệ sinh nội bộ của
harness**, không phải một nghĩa vụ trong `docs/spec.md`; ghi ra đây thay vì nhét vào
một hàng cho có.

### Lượt 45 — nhóm D: generator, theo từng sink

**Phân biệt trước, rồi mới nói tới luật.** Cả ba file sinh **dữ liệu đầu vào**
(manifest + clip audio tổng hợp), **không** sinh kết quả benchmark. Nên hợp đồng
artifact-kết-quả **không** tự động áp lên chúng, và tôi **không** áp luật chung.

| Sink | Dữ liệu | Mục đích | Path do ai chọn | Hợp đồng đã chốt? | Nguy cơ |
|---|---|---|---|---|---|
| `make_noise_group.py:125` WAV | audio trộn nhiễu | **đầu vào được sinh** | `--out-root` (**người chạy**, mặc định `var/asr/noise`) | không | path tự do; ghi đè theo tên |
| `make_noise_group.py:205` manifest | JSON | đầu vào được sinh | **cố định, qua `artifact_path`** | **CÓ** (lượt 35) | ghi đè khi chạy lại |
| `make_nonspeech_clips.py:46,68` WAV | audio phi lời nói | đầu vào được sinh | **cố định** → nay qua helper | **CÓ** (lượt 45) | ghi đè khi chạy lại |
| `make_nonspeech_clips.py:127` manifest | JSON | đầu vào được sinh | **cố định** → nay qua helper | **CÓ** (lượt 45) | ghi đè khi chạy lại |
| `make_vietmed_manifest.py:242` manifest | JSON | đầu vào được sinh | `--out` (**người chạy**) | **không** → [CHỜ SƠN] | path tự do; thoát được `var/` |

**Thứ đã sửa là một TAI NẠN, không phải một luật mới.** `CLIP_ROOT` và `MANIFEST`
là **hằng literal cố định đã trỏ sẵn vào `var/asr/`**, và sibling của chúng
(`make_noise_group`) **đã** đi qua helper từ lượt 35. Lý do chúng bị bỏ sót: phép
kiểm cũ hỏi **tên biến** có chứa `out`/`target`/`dest` hay không — `CLIP_ROOT` và
`MANIFEST` không chứa, nên lọt. **Vị trí không đổi một ký tự** sau khi sửa, đã xác
minh.

**Phép kiểm nay hỏi CÁCH DÙNG thay vì TÊN.** Một path bị gọi phương thức ghi lên là
**output**; `WHISPER`, `LLAMA`, `BUILD_DIR` **chưa bao giờ** bị ghi nên là **input**
— và ép một input qua helper-output sẽ là **sai**, không phải chặt hơn. Có test cho
**cả hai chiều**, nếu không thì "mở rộng cho bắt hết" sẽ kéo luôn ba hằng input vào
mà suite không phản đối.

#### [CHỜ SƠN] — hai mục cần quyết định vị trí/workflow

1. **`make_vietmed_manifest --out` là đường dẫn tự do.** Khác hai file kia: nó nhận
   path từ người chạy. (a) **Giữ tự do** — nhất quán với việc đây là *dữ liệu đầu
   vào do người chạy dàn dựng*, và `--clip-root`/`--transcript` cũng là path người
   chạy chọn; (b) **Ràng buộc như artifact kết quả** — nhưng khi đó input vẫn tự do
   còn output thì không, tức ràng buộc **một nửa**, và đổi thói quen vận hành.
2. **`make_noise_group --out-root` cũng tự do**, và đó là nơi **audio** đi ra. Cùng
   hình dạng câu hỏi như (1).

**Ghi nhận, không phải quyết định:** cả bốn generator **ghi đè theo tên cố định** khi
chạy lại — không có versioning. Đây là rủi ro mất dữ liệu đã sinh, không phải lỗ an
toàn, và việc có cần versioning hay không là quyết định sản phẩm.

**Không chạy generator nào** — chúng tạo audio thật và một cái cần dataset tải về.

### Lượt 46 — hai mục "đang chờ" hoá ra không phải quyết định

**Quyết định được uỷ quyền, ghi đúng nguồn.** **[CHỐT THEO ỦY QUYỀN CỦA SƠN QUA
CODEX]** 2026-10-11: giữ `make_vietmed_manifest --out` và `make_noise_group
--out-root` **là đường dẫn tự do**. Lý do ghi lại: đây là nơi người chạy chủ động
dàn manifest/audio **đầu vào được sinh**; chúng **không** phải artifact kết quả
thuộc hợp đồng S2.1, và ép vào `var/` sẽ đổi workflow mà **không tạo thêm bằng
chứng** nào về chất lượng hay nguồn gốc dữ liệu. **Giữ nguyên hành vi**: không thêm
`--force`, không đổi hành vi ghi đè. *(Đây là uỷ quyền qua Codex, **không** phải một
phát ngôn trực tiếp khác của Sơn.)*

**Rà danh sách chờ, và hai mục rụng ra vì bằng chứng, không vì quyết định:**

| Mục | Hoá ra là gì |
|---|---|
| *Sensitivity theo field hay theo card* | **Đọc nhầm.** Hồ sơ dòng 136 liệt kê `sensitivity` **trong field tối thiểu của một card** — card-level, **đúng y code**. Thứ đọc thành field-level là `visibility` của **Profile** (dòng 128), **thực thể khác** |
| *Chỗ đặt phép kiểm scope* | **Spec đã ghi đúng từ trước**; thiếu là **bằng chứng**, không phải câu trả lời. Nay có test |

**Phần vẫn chờ Sơn, tách bạch:** *một câu hỏi trong họp map sang scope nào* — đó là
quyết định sản phẩm, và spec vốn đã nói thế. Lát này **không** chạm vào nó.

**Một lỗ trong chính test của tôi, do mutation tìm ra.** Bản đầu khẳng định ở mức
**module** ("knowledge.py có so scope"), và nó **lọt** mutation xoá đúng bộ lọc trong
`retrieve` — vì `conflicts` và `purge_scope` **cũng** so scope, nên phép đếm vẫn khác
0. Thu hẹp xuống mức **hàm** thì bắt được. Đọc lại test không thấy điều này; mutation
thấy.

### Lượt 47 — `leave()` theo đúng hợp đồng

**[CHỐT THEO ỦY QUYỀN CỦA SƠN QUA CODEX]** `BlockedDiscordAdapter.leave()` thành
**no-op idempotent**, đúng `ControlPlane.leave` (*"Must be safe to call when not
joined"*). An toàn vì `join()` **vẫn raise**, nên không bao giờ có phiên để `leave`
kết thúc — **không mở năng lực Discord nào**. `health`, capabilities, `send_text`,
`join`, `participant_events` và mọi gate **giữ nguyên**.

Ca test cũ gom `leave` vào nhóm *"mọi operation raise"* nay tách: `join` và
`participant_events` vẫn phải raise; `leave` có ba ca riêng, trong đó ca **"không
đổi gì quan sát được"** là ca ngăn một "no-op" lén đổi trạng thái.

### Lượt 47 lát 2 — matcher tên platform: **không mở rộng**

**[CHỐT THEO ỦY QUYỀN CỦA SƠN QUA CODEX]** giữ so khớp **chính xác** sau
`strip().lower()`. **Không sửa implementation**; lát này là **test + tài liệu**.
Giới hạn được **ghi thành ledger** (4 tên vẫn lọt), kèm khẳng định riêng rằng
`synthetic=True` **vẫn được báo cáo dù tên là gì** — cái tên không phải control.
Ledger **không** mô tả các tên đó là bằng chứng integration an toàn.

### Lượt 48 — một giá trị giữ chỗ không phải evidence

**[CHỐT THEO ỦY QUYỀN CỦA SƠN QUA CODEX]** `evidence` là một **trích dẫn**, nên rỗng,
chỉ-khoảng-trắng, và hai giá trị giữ chỗ **chính xác** `TODO` / `n/a` không thoả.

**Đo trước khi sửa, trên đường gọi thật:** `""` vốn đã bị chặn; `"   "`, `"\t\n "`,
`"TODO"`, `" TODO "`, `"N/A"`, `"n/a"` **đều lọt**, và **không lớp nào khác chặn**.
Sửa tối thiểu tại chính nơi validation đang có. **Không mở rộng** sang substring/
fuzzy — `"na"`, `"TODO-1234"`, `"ticket n/a-7"` vẫn được nhận, có test ghim ranh
giới. **6 mutation đều đỏ.**

**[CHỜ SƠN] Consent TTL** — mặc định giữ `None`. Đây là chính sách **quyền riêng tư
và thời hạn đồng ý**; không suy ra được con số từ code.

### Lượt 49 — addressing với registry rỗng: khảo sát, rồi ghim đúng một thứ

**Khảo sát (AST, không grep):** `classify_address()` có **0 call site** trong `src/`;
`AliasRegistry()` được dựng **0 lần**. Ba lần `grep` khớp là **định nghĩa**,
**`__all__`** và một **annotation**. Đường sống duy nhất (`dryrun.py:610`) dựng
`AddressContext` thẳng từ field fixture.

| Kết luận | Trạng thái |
|---|---|
| **An toàn:** thiếu alias không tạo quyền nói; mặc định `UNCLEAR`/không reply | **đã ghim kín từ trước** — không nhân bản |
| **Giới hạn vận hành:** không alias thì không nhận diện lời gọi đích danh; turn-context độc lập nhưng đòi speaker mapping tin cậy, mà **Gate 0-C vẫn mở** | ghi lại, không phải lỗi |
| **Đường dây nối:** classifier chưa có caller nào | **chưa ghim → lát này ghim** |

Ledger + khoá hai chiều với tài liệu, cùng hình dạng ledger media gate. Lý do cần:
`ResponseRequest` ghi `address` *"comes from the addressing classifier"* — đúng như
một phát biểu **hợp đồng**, **không** phải "đã nối". Dự án đã có một lần người đọc
bước nhầm đúng kiểu đó.

**Không** tạo alias mặc định, **không** đổi logic addressing, **không** thêm caller
runtime, **không** mở Gate 0-C.

### Lượt 51 — báo cáo readiness chỉ đọc cho cấp B

**Khoảng trống thật, khảo sát trước khi viết:** `benchmarks/preflight.py` và
`artifacts.py` **không có** `__main__` nào, và không lệnh nào trong repo trả lời
*"cấp B còn thiếu gì"*. `meetai status` báo capability và quyết định đang chờ, nhưng
bốn cổng cấp B nằm trong `benchmarks/`, mà `src/` **không** (và không được) import
`benchmarks`. Nên câu trả lời chỉ tồn tại dưới dạng **văn xuôi** trong runbook mục 4.

**Lát này:** `benchmarks/readiness.py` — chỉ đọc, đọc đúng các hằng số mà chính các
cổng đọc, in 4 cổng, exit **3** khi còn cổng mở. Đặt trong `benchmarks/` vì chiều phụ
thuộc là `benchmarks -> meetai`; đảo chiều sẽ khiến cấp A có thể bị một cổng benchmark
chặn, và có test AST ghim chiều đó.

| Tiêu chí nghiệm thu | Kết quả |
|---|---|
| Liệt kê đúng 4 cổng, trạng thái từ hằng số sống, exit 3 khi còn mở | **đạt** — đo: exit 3, 4/4 mở |
| Output ASCII | **đạt** (test, cho cả source live và all-approved) |
| Không subprocess/mạng/ghi file/đọc bộ nhớ/đổi env | **đạt** — test hành vi, không chỉ test import |
| Verdict khớp **hành vi** của chính hàm cổng (refuse ⇔ pending) | **đạt** — probe gọi hàm thật, không khẳng định lại hằng số |
| Không bao giờ tuyên bố sẵn sàng | **đạt** — kiểm cả với source all-approved, là hướng nguy hiểm |
| Source all-approved làm mọi dòng **đổi** và exit 0 | **đạt** — nếu thiếu, một "pending" hardcode sẽ qua hết |
| Thêm gate mà không có probe hành vi → fail | **đạt** |
| Không in **giá trị** digest | **đạt** — canary qua cả hai renderer |
| Cấp A không đi qua cổng nào ở trên | **đạt** — AST trên toàn `src/` |

**Bài học lặp lại lần thứ ba:** mutation đầu tiên cho kết quả **xanh** và câu trả lời
đúng **không** phải "test mù" mà là **mutation vô hiệu** — nó rơi vào nhánh `else`
không tới được. Chạy lại trên nhánh quan sát được: **đỏ**. 9/9.

**Phần dư:** `GATE_IDS` viết tay — một cổng thứ năm **chưa bao giờ** được thêm vào báo
cáo thì không test nào thấy. Đã ghi, không che.

**Không** chạy model/GPU/benchmark, **không** đặt ngưỡng, **không** ghim digest,
**không** đổi `EGRESS_ISOLATION_ATTESTED`, **không** mở cổng nào.

## Lô tiếp theo

**Giữ cấp A; tiếp tục việc không cần model.** Phương án A cho RAM đã được chọn:
mọi lần chạy model CPU tiếp tục bị từ chối, hai ngưỡng RAM vẫn chưa đặt, không
chạy GPU/model trong khi digest còn rỗng và egress OS chưa attested.

1. **[XONG lượt 37]** Bảng traceability đã lập trong
   [checklist privacy/consent Gate 0-P](research/2026-10-10-checklist-privacy-consent-gate-0p.md):
   9 dòng P0-1…P0-9, mỗi dòng gắn *đã có trong code (kiểm chứng ở HEAD)* / *thiếu* /
   *bằng chứng cần có* / *gate*. Ba đính chính từ việc đối chiếu, đáng đọc trước khi
   dùng bảng: `require_media_processing_allowed()` **không có caller nào** trong
   `src/` nên là nghĩa vụ hướng tới chứ không phải control đang chạy; `ConsentState`
   **không có member falsy** (fail-closed tầng chính sách đến từ `ConsentMode`/
   `LateJoinPolicy`); và P0-6 suýt ghi sai vì `train` khớp trong `con`**`strain`**`t`.
   Việc đọc được Terms **không** là xác nhận route được phép.
2. Tiếp tục các lát cấp A và test-only có acceptance criteria đã có; không mở
   listener, media sink, persistence hay thay đổi policy consent.
   **Lượt 38 đã đối chiếu lại bảng P0 với source: 18/18 khẳng định đúng, không mục
   nào phải sửa** — kiểm bằng AST, kèm control cho thấy grep `train` vẫn khớp 3 file
   qua `con`**`strain`**`t`. **Việc kế tiếp không cần quyết định sản phẩm:** ghim các
   khẳng định đó thành **test hồi quy**, để nếu ai nối
   `require_media_processing_allowed()` vào một đường thật thì test đỏ và buộc cập
   nhật tài liệu, thay vì bảng âm thầm sai.
   **[XONG lượt 39]** — nhưng **không ghim cả 18**: phân loại trước đã tách ra
   **2** mục đáng ghim (`TestNoPersistenceYet`, `TestTheMediaGateHasNoCallerYet`),
   **5** mục đã có test, **3** mục chỉ ghi tài liệu, và **3** số đo **cố ý không**
   ghim — gồm số lượng test, vì biến nó thành hợp đồng là biến phép đo thành mục
   tiêu. Cả hai test mới có thông báo lỗi nói rõ một thay đổi hợp lệ **không phải**
   lỗi sản phẩm.
2a. **[XONG lượt 40]** Gia cố test AST “không ghi file” để nhận `Path.open`, `Path.unlink`, `os.open`, `os.write` và API sao chép/xoá. Test mục tiêu 101 passed; full suite 5179 passed, 3 skipped, 1 warning. Ruff/mypy xanh. `uv run` trả Access denied nên dùng interpreter `.venv`. Không chạy model, không đổi policy.
2b. **[XONG lượt 42]** Thay kiểm tra token `artifact_path` bằng truy nguồn AST theo phép gán tuyến tính từ helper tới JSON `write_text` sink trong 5 harness model; thêm control cho helper import chết, direct path, alias, helper không import và gán lại biến sau khi dùng. Mutation thay helper bằng `pathlib.Path` bị bắt ở cả 5 harness. Phạm vi chỉ là artifact JSON kết quả, không mọi ghi trong `benchmarks/` (file tạm/generator/lock là lớp riêng). Test mục tiêu 30 passed; full suite 5183 passed, 3 skipped, 1 warning; Ruff/mypy xanh. Không chạy model.
3. Chỉ quay lại cấp B khi điều kiện RAM riêng cho LLM/ASR, digest mô hình và
   cô lập egress OS đều có bằng chứng đã được duyệt.

### Ba quyết định của Sơn ở lượt 11

| # | Quyết định | Hệ quả đã thực thi |
|---|---|---|
| Accent | **VietMed, chỉ thăm dò.** Không ViMD (CC BY-NC-ND). | Đã tải subset test 69.3 MB, ngoài Git. Chạy 421 clip. Trục giữ **`not demonstrated`** vì cấu trúc dữ liệu không cho phép đóng. |
| Nói chồng | **Ngoài phạm vi, giữ cổng mở.** Không tự gán nhãn VietMed bằng một annotator. | Trục giữ **`absent`**, lý do ghi ở [khảo sát overlap](research/2026-10-07-overlapping-speech-corpora.md). Không dùng trộn FLEURS tổng hợp. |
| p50/p95 | **`not demonstrated`, phụ thuộc S3.** Không dựng pipeline tạm. | S2.2 ghi là **hoàn tất phần đo được**, tổng thể **partial/open** cho tới khi tiêu chí được đo hoặc plan/spec được Sơn duyệt sửa. |

**S2.2 = partial/open.** Không tự gỡ acceptance criteria nào.
