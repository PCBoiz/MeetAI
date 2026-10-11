---
title: "Runbook — thử nghiệm cục bộ MeetAI"
owner: "Sơn"
created: "2026-10-10"
last_updated: "2026-10-10 (lượt 35)"
purpose: "Sơn chạy được gì hôm nay, bằng lệnh nào, kết quả chứng minh điều gì — và điều gì nó KHÔNG chứng minh."
---

# Runbook — thử nghiệm cục bộ

**[CHỐT]** Sơn chọn: làm **cấp A trước**, chuẩn bị **cấp B song song**, và
**chưa chạy model thật**. Năm quyết định S2.1 đã được triển khai theo uỷ quyền; cấp B vẫn bị chặn bởi ngưỡng RAM riêng cho LLM/ASR, digest model chưa ghim và egress OS chưa attested. Tiêu chí thành
công: không vượt quyền / không rò nội dung; trả lời được khi có bằng chứng; lặp
lại được; và biết rõ nó không chứng minh gì.

> **Không có mục nào trong tài liệu này là tuyên bố production readiness.**
> Gate 0-S / 0-P / 0-C / 0-U đều **còn mở**. `consent_mode` còn
> `pending_decision`, nên mọi xử lý media bị **chặn theo thiết kế**.

## 0. Ba cách nói "chạy được" — đừng trộn chúng

| Cụm từ | Nghĩa | Ai quyết |
|---|---|---|
| **Có thể chạy ngay** | Lệnh tồn tại, dependency đủ, exit 0 | đo được |
| **Được phép chạy** | Không vượt ranh giới nào trong `AGENTS.md` | `AGENTS.md` + Sơn |
| **Đã chứng minh** | Có phép đo, có test xoá-là-fail | đo được |

Một thứ **có thể chạy** mà **chưa được phép** thì không được chạy. Một thứ
**được phép và chạy được** vẫn **chưa chứng minh** gì cho tới khi có phép đo.

## 1. Bảng ba cấp

| | **A — dry-run tổng hợp** | **B — model local trên fixture** | **C — Discord sandbox** |
|---|---|---|---|
| **Lệnh** | `uv run meetai dry-run` | *(chưa có lệnh hợp lệ)* | *(không có)* |
| **Input** | 9 card + 12 case **hằng số trong module**, không đọc file nào | GGUF đã staged + corpus tổng hợp | server Discord thật |
| **Output** | text hoặc JSON ra stdout; **0 ghi đĩa** | JSON artifact dưới `var/bench/` | — |
| **Có thể chạy ngay** | **CÓ** (đo: exit 0) | **một phần** — xem mục 4 | **KHÔNG** |
| **Được phép chạy** | **CÓ** | **CHƯA** — năm quyết định S2.1 đã triển khai; hai ngưỡng RAM giữ pending, digest thực chưa ghim, egress OS chưa attested | **KHÔNG** — Gate 0 còn mở |
| **Đã chứng minh** | xem mục 2 | chưa gì | chưa gì |
| **Rủi ro** | không đáng kể: không model, không mạng, không ghi | **OOM thật** — mục 4 | rò nội dung họp, vượt quyền |
| **Blocker** | không | ngưỡng RAM riêng, digest model, egress OS + mục 4 | Gate 0-S/0-P/0-C/0-U + consent |

## 2. Cấp A — chạy ngay

```bash
uv run meetai status           # cấu hình + bảng capability
uv run meetai dry-run          # 12 case qua boundary, báo cáo người đọc
uv run meetai dry-run --json   # cùng dữ liệu, dạng máy đọc
```

Thêm `--log-level INFO` nếu muốn một dòng log metadata trên stderr. Mặc định
`WARNING`, và đường thành công **không in gì** ra stderr.

**Exit code:** `0` mọi case khớp dự kiến · `5` có case lệch · `2` cấu hình bị
từ chối. Lưu ý `argparse` cũng exit `2` khi sai đối số — **hai nguyên nhân cùng
một số**, nên đọc stderr chứ không chỉ đọc `$?`.

**Trông đợi gì:** 12 case, **1 được nói** (`D1.du-evidence`), **11 im lặng**, và
dòng cuối `Tong: 12 case, 1 duoc noi, 1 lan toi sink.`

### Kết quả này CHỨNG MINH gì

Mỗi mục dưới đây có test xoá-là-fail đứng sau.

1. **Một câu chỉ ra được khi có bằng chứng đủ.** 11/12 case im lặng, mỗi case vì
   một lý do khác nhau và **lý do được in ra**: thiếu giá trị, sai chủ đề, hai
   card mâu thuẫn, không kiểm được, chưa duyệt, card PRIVATE, cắt candidate
   không che được mâu thuẫn.
2. **Hai lớp độc lập, và lớp sau không thấy lớp trước.** `D7` và `D10`
   answerability **đồng ý** mà gate quyền hạn vẫn **từ chối**.
3. **Không nội dung họp nào ra khỏi báo cáo.** Đo được: câu đã phát nằm trong
   `sink.emitted[0]` **trong tiến trình**, và **không** xuất hiện trong JSON lẫn
   text report.
4. **Lặp lại được byte-for-byte.** 3 lần chạy, md5 trùng, cho cả 4 lệnh.
5. **Không ghi dữ liệu bền vững.** Snapshot ~8900 đường dẫn quanh cả 4 lệnh:
   0 tạo, 0 xoá, 0 đổi. (`__pycache__` loại trừ — bytecode không phải dữ liệu;
   lần chạy lạnh đầu tiên sẽ ghi nó.)
6. **Báo cáo tự khai giới hạn.** `is_production_integration=False`,
   `is_discord_test=False`, bằng **dữ liệu** chứ không chỉ bằng lời.
7. **Thử nghiệm này có thể FAIL.** Một case lệch → exit 5 và case id in ra.

### Kết quả này KHÔNG chứng minh gì

- **Không** chứng minh chất lượng model — **không có model nào chạy**.
- **Không** chứng minh ASR tiếng Việt — không có audio nào.
- **Không** chứng minh dùng được trong họp thật — card là hằng số viết riêng
  cho đường này, không phải transcript.
- **Không** chứng minh grounding tổng quát. 12 case tổng hợp. Riêng
  answerability còn **16 case eval đang chờ Sơn duyệt** và **12 cơ chế
  false-answer đã đo**; cấp A **không** chạm tới chúng.
- **Không** chứng minh `MINIMUM_CONFIDENCE` đã calibrate — nó vẫn là placeholder.
- **Không** chứng minh gì về Discord, persistence hay media.

### Phần dư đã đo của cấp A

- `sink.emitted` là `list[str]` **công khai, mutable**, giữ nguyên văn câu đã
  phát. `__repr__` chỉ in hình dạng và báo cáo không chứa nó, nhưng thứ ngăn
  đọc trực tiếp là **test cấu trúc**, không phải kiểu dữ liệu.
- Báo cáo người đọc là **tập con thực sự** của JSON. JSON có mà text không có:
  `level`, `is_production_integration`, `is_discord_test`, `emitted_chars`,
  `error_type`, `may_claim_sent`, `must_not_retry`, `divergent_pairs`,
  `divergence_is_a_review_signal_not_a_refusal`, `query_token_count`. Dùng
  `--json` khi cần đủ.
- `meetai status` dạng người đọc cũng bỏ bớt so với `--json`: `ui_host`,
  `ui_port`, `state_dir`, bốn cờ `persist_*`, `raw_audio_debug_acknowledged`,
  `blocked_by` và `operator_can_act` từng capability.
- `assert_tripwires_disarmed()` nằm **ngoài** `try/except` trong `cli.main`, nên
  nếu nó raise thì ra traceback chứ không ra exit code gọn. Chỉ tới được qua một
  đường bỏ qua validation.
- `meetai serve` **chưa có test** cho nhánh `ImportError` → exit 3, và không test
  nào khẳng định `serve` không ghi đĩa.

## 3. `meetai serve` — chạy được, nhưng đọc trước

```bash
uv run meetai serve            # UI loopback; Ctrl-C để dừng
```

Chỉ bind loopback dạng số, `localhost` **bị từ chối**. Docs tích hợp tắt. Mọi
request đổi trạng thái cần header `X-MeetAI-Request: 1` và phải là POST.
**Không endpoint nào trả về nội dung cuộc họp** — đó là thuộc tính thiết kế.
Bind thất bại → exit 4 và **không tự đổi cổng**.

## 4. Cấp B — điều kiện TRƯỚC khi một phép thử model thật được phép chạy

**Chưa chạy — và từ lượt 29, điều đó được CƯỠNG CHẾ chứ không chỉ được ghi.**

[CHỐT] Sơn, 2026-10-10: *cổng RAM CPU giữ `pending` — từ chối mọi lần chạy CPU cho
tới khi duyệt ngưỡng; peak 4438 MiB chỉ là số đo lấy mẫu một lần, chưa đủ cơ sở.*

Đo được, cả **bốn** đường chạy model trên CPU đều từ chối exit 3 — và đường GPU tương ứng vẫn exit 2 ở `artifact-missing`, nên không lần chạy GPU nào bị cổng mới chặn:

```
uv run python -m benchmarks.bench_llm_policy --device none            -> exit 3
.venv/Scripts/python.exe benchmarks/bench_llamacpp.py --device none   -> exit 3
.venv/Scripts/python.exe benchmarks/bench_llm.py --gpu-layers 0       -> exit 3
.venv/Scripts/python.exe benchmarks/bench_asr.py --cpu                -> exit 3
```

Tất cả báo `chua co nguong RAM duoc duyet ... Day KHONG phai loi thieu RAM`. Cổng
từ chối **trước khi đọc bộ nhớ** — đo được: truyền `available_mib=10**9` vẫn bị từ
chối. Nên không lượng RAM nào biến nó thành pass.

**Lượt 30 tìm ra bypass thứ hai và đóng nó:** `bench_asr.py --cpu` truyền `-ng` cho `whisper-cli` — một lần chạy model **không GPU** — và chưa gated. Nó có **cổng riêng**, cũng `pending`, và **không vay** số 4438 (xem mục 4d).

**Một bypass đã được tìm ra và đóng ở lượt 29.** Cổng ban đầu chỉ bảo vệ
`bench_llm_policy.py` — **1 trong 5** harness chạy model. `bench_llamacpp.py` và
`bench_llm.py` không có cổng nào, và `bench_llm.py` nạp model **in-process**, tức
một lần chạy không cổng ở đó hạ **máy**, không phải một tiến trình con.
`bench_asr.py` và `bench_coresidency.py` cố ý **không** gated (audio, và `-ngl 99`
nung cứng) — ghi trong ledger kèm lý do, và một harness không nằm trong tập nào sẽ
làm test fail.

**Ba lý do từ chối, cố ý không gộp:** ngưỡng chờ duyệt / không có GPU / thiếu RAM.
Gộp chúng sẽ gửi người chạy đi đóng bớt process vì một quyết định mà không lượng
RAM nào thay đổi được.

**Dưới đây là thứ còn thiếu, tách theo việc cần hay không cần Sơn quyết.**

### 4a. Cần Sơn quyết (5 mục, chi tiết ở [research note](../research/2026-10-10-offline-fail-closed-model-artifact.md) mục 7)

digest check bắt buộc hay tư vấn · vị trí artifact · mở rộng
`PROHIBITED_EGRESS_PREFIXES` quá `OTEL_` · có nhận `huggingface_hub` · cô lập
mạng tầng OS.

### 4a. Năm quyết định — **ĐÃ CHỐT THEO ỦY QUYỀN, lượt 35**

Không còn là blocker. Chi tiết và trade-off: mục 7 của
[research note](../research/2026-10-10-offline-fail-closed-model-artifact.md).

1. Digest **bắt buộc**, `--no-hash` **đã bỏ**, ledger digest **rỗng → từ chối**.
2. Artifact root **cố định** `var/`, tương đối, gitignored; **6 writer** đi qua helper.
3. Từ chối **theo sự hiện diện** `OTEL_*`, `HF_*`, `HUGGINGFACE*`, `TRANSFORMERS*`,
   `*_PROXY`. `XDG_CACHE_HOME` **cố ý không** chặn.
4. **Không** nhận `huggingface_hub`; sự vắng mặt **nay có test ghim**.
5. **Đòi** cô lập egress tầng OS trước binary native; `EGRESS_ISOLATION_ATTESTED =
   False` nên **mọi** runner từ chối exit 4.

**Năm quyết định này KHÔNG mở cấp B.** Cấp B vẫn **CHƯA an toàn**: hai ngưỡng RAM còn
pending, lựa chọn A/B/C còn pending, và nay thêm hai cổng nữa cùng từ chối.

### 4b. Thiếu về cơ học — **4/6 đã xong ở lượt 29**

| # | Trạng thái |
|---|---|
| 1. CPU mode cho `bench_llm_policy` | **XONG** — `--device none` + `--ngl` suy từ `--device`; cặp mâu thuẫn bị **từ chối** chứ không sửa ngầm. argv mang `-ngl 0` **và** `-dev none`, **không chứa "99"**; argv `auto` **y nguyên** nên không lần chạy S2.3 nào bị vô hiệu. |
| 2. CPU preflight có RAM gate riêng | **XONG** — `require_cpu_preflight()` chỉ kiểm RAM host, **không gọi `nvidia-smi`**, và cổng VRAM **không** được gọi trong CPU mode. |
| 3. Smoke test CPU-only | **XONG** — chạy toàn bộ đường CLI in-process, dừng ở cổng, **không tải model**, không spawn, không ghi artifact. |
| 4. Hành vi khi thiếu `nvidia-smi` | **XONG** — trạng thái unavailable thành **có kiểu**. `"?"` từng làm `int()` raise, và `or 0` **không bao giờ** fire vì `"?"` **truthy**. |
| 5. Tài liệu venv CPU | **XONG** — `benchmarks/README.md`. |
| 6. Tài liệu các harness | **XONG** — mọi script có `main()` kèm interpreter cần thiết. |

*(Mục dưới giữ lại làm bản ghi của lượt 28, đã bị đính chính bởi bảng trên.)*

1. **`bench_llm_policy.py` không có cờ CPU.** `Decoding.gpu_layers = 99` nung
   cứng vào argv; argparse không có `--ngl` lẫn `--device`. Đây đúng là harness
   chạy corpus chính sách.
2. **`preflight.py` không có chế độ CPU**, và `bench_llm_policy` gọi
   `require_headroom()` **vô điều kiện** → trên máy không GPU nó **từ chối, exit
   3**. Không có đường xin cổng RAM mà bỏ cổng VRAM.
3. **Không test smoke CPU-only nào.** Và `tests/test_bench_harness.py` khẳng
   định suite chỉ spawn `sys.executable -c` — nên **không test nào có thể** là
   smoke test đó.
4. **Trên máy không có `nvidia-smi`, `Environment.capture()` crash chứ không từ
   chối.** `measure.py` thay bằng `["?"] * 10`, rồi 5 call site làm
   `int(env.vram_idle_mib or 0)` → `int("?")` raise `ValueError`. Đọc từ source,
   **chưa chạy để xác nhận**.
5. **`var/bench-cpu-venv` không được ghi ở đâu như một đích chạy.** Đó là venv
   duy nhất có `llama_cpp` **không kèm CUDA DLL** (0.3.19). `benchmarks/README.md`
   chỉ có recipe cho `bench-venv` + CUDA.
6. **`benchmarks/README.md` chỉ tài liệu hoá `bench_llamacpp.py`** — không nhắc
   `bench_llm_policy.py`, `bench_asr.py`, `bench_coresidency.py`, kể cả việc
   `bench_llm_policy` cần đúng `.venv` vì nó `import meetai`.

### 4c. Nguy cơ OOM — số đo, không phải lo xa

| | MiB |
|---|---|
| Peak working set đã đo của **bản CPU** | **4438** |
| Peak working set đã đo của bản GPU | 2794 |
| Cổng RAM **đang code** (`REQUIRED_FREE_RAM_MIB` = 2868 + 512) | **3380** |
| RAM khả dụng trên máy này, đo 2026-10-10 | **3966** |

**Đọc bảng này:** một lần chạy CPU hôm nay sẽ **qua cổng** (3966 > 3380) nhưng
thiếu **~472 MiB** so với peak đã đo (3966 < 4438). Con số `4438` **không xuất
hiện trong bất kỳ code hay test nào** — cổng hiện tại được suy từ các lần chạy
**GPU**. Thêm nữa, 4438 là **max lấy mẫu 300 ms**, tức **chặn dưới** của peak
thật; và Working Set **nói quá** nhu cầu với GGUF mmap. Hai chiều sai số đều đã
ghi, và **không** triệt tiêu nhau một cách biết trước được.

Tiền lệ: S2.2 từng OOM với hai peak chặn dưới tổng 3767 MiB trong 5343 MiB khả
dụng — **dự đoán thiếu ít nhất 1576 MiB**. Nên "còn chỗ" theo số không phải bằng
chứng là sẽ không OOM.

**Kết luận mục này, cập nhật lượt 29:** (b) và (c) **đã xong** — cổng RAM riêng
cho CPU đã tồn tại và đã cưỡng chế, và harness chạy corpus đã có đường CPU-only.
Còn lại (a) Sơn chốt 4a, và (d) RAM khả dụng đủ so với một ngưỡng **được duyệt**.

**Và RAM khả dụng dao động mạnh:** đo **3966 MiB** đầu lượt 29, **2897 MiB** cuối
cùng lượt đó. Con số thứ hai nằm **dưới cả cổng GPU** (3380). Nên "còn chỗ" đọc
một lần không phải bằng chứng cho lần chạy kế tiếp.

**Câu hỏi còn lại cho Sơn, đúng một câu:** margin RAM cho CPU là bao nhiêu — hoặc
có cho phép một lần chạy đo có giám sát để có n>1. Mọi phần cơ học không phụ thuộc
câu trả lời đó **đã xong**.


### 4d. Cách đọc các lựa chọn ngưỡng — và cái gì mỗi lựa chọn KHÔNG bảo đảm

Mục này **không chọn** margin. Nó phân loại bằng chứng, vì toàn bộ câu hỏi ngưỡng
nằm ở chỗ mỗi con số thuộc loại nào.

#### Ba loại, đừng trộn

| Loại | Nghĩa | Ví dụ trong repo |
|---|---|---|
| **Phép đo** | Một quan sát đã xảy ra, ghi lại được, truy về lệnh đã chạy | peak CPU **4438 MiB**; peak GPU **2868 MiB** (lớn nhất của 4) |
| **Phép suy ra** | Kết luận từ phép đo cộng một lập luận | *"peak thật ≥ 4438"* — suy từ việc lấy mẫu bỏ sót |
| **Chính sách** | Một phán đoán không có phép đo nào quyết định được | margin `+512`; margin `×1.5`; margin CPU **chưa có** |

`preflight.py` gọi thẳng `RAM_HEADROOM_MIB` là *"a judgement"*. Đó là nhãn đúng, và
nó áp dụng y nguyên cho mọi margin CPU.

#### Hai chiều sai số, và vì sao chúng KHÔNG triệt tiêu nhau

- `ProcessRamSampler` lấy mẫu **mỗi 300 ms**, nên một peak giữa hai mẫu **chưa bao
  giờ được thấy**. ⇒ 4438 là **chặn dưới của peak**.
- Working Set **đếm cả trang file-backed** của GGUF mmap, mà những trang đó
  **evictable**. ⇒ 4438 **nói quá nhu cầu thật**.

Hai chiều ngược nhau. Nhưng **không ai biết biên độ của chiều nào**, nên không thể
nói chúng bù trừ. Một con số vừa là chặn dưới của thứ này vừa là chặn trên của thứ
khác thì **không phải chặn của cái gì cả** theo nghĩa dùng được cho một cổng.

#### n=1 nghĩa là không có ước lượng biến thiên

Cổng GPU dùng peak **lớn nhất của 4 lần** (2827 / 2827 / 2868 / 2822) — bốn lần đo
cho biết độ tản là **~46 MiB**, nên `+512` là một biên **so sánh được** với độ tản
đã thấy. Phía CPU **chỉ có một lần đo**, nên **không có độ tản nào** để so. Đó là
khác biệt thật giữa hai cổng, không phải chuyện cẩn thận nhiều hay ít.

*(Ba artifact CPU tồn tại; hai cái còn lại **không có key RAM nào** và chạy
`device_flag=None` — đúng loại "`-ngl 0` không phải CPU-only". Nên **đúng một** phép
đo RAM host của bản CPU tồn tại.)*

#### Mỗi lựa chọn bảo đảm gì, và KHÔNG bảo đảm gì

| Lựa chọn | Bảo đảm | **KHÔNG** bảo đảm |
|---|---|---|
| **Giữ `pending`** *(đang áp dụng, [CHỐT])* | Không lần chạy CPU nào xảy ra | Không cho thêm bất kỳ bằng chứng nào; vòng đo lường vẫn đóng |
| **4438 + 512 = 4950** | RAM khả dụng ≥ peak **đã thấy** cộng cùng biên như cổng GPU | **Không** bảo đảm nó ≥ pech **thật**: biên `+512` được chọn so với độ tản của **4 lần đo**, mà ở đây không có độ tản nào |
| **4438 × 1.5 = 6657** | Biên lớn hơn, phủ được một peak bị bỏ sót khá lớn | **Không** bảo đảm đúng, và `preflight.py` ghi lại phép đo rằng một biên nhân trên Working Set **đã từ chối oan** một lần chạy vừa đủ chỗ. Máy 16 GB sẽ gần như luôn trượt ⇒ dạy người ta truyền `--force` |
| **Đo lại trước** | Cho độ tản thật | Cần được phép chạy CPU — **vòng tròn**, và chính lần chạy đó là lần có rủi ro OOM |

#### Lượt 31: tầng OS giúp ít hơn tưởng, và phép đo của ta yếu hơn cần thiết

Xem [giới hạn RAM Windows](../research/2026-10-10-gioi-han-ram-windows-cho-cpu.md).
Ba điểm đổi cách đọc bảng trên:

1. **Commit limit của Job object không chặn weights GGUF.** `SEC_COMMIT` *“has no
   effect”* cho data file, nên phần weights **không bị tính commit**. Giới hạn tầng
   OS chỉ làm phần **KV cache/heap** fail sạch.
2. **Hard working-set max cưỡng chế bằng trim/paging**, không làm allocation fail —
   nó biến OOM thành **thrashing**, và vì thế **phá luôn khả năng đo** latency.
3. **`4438` là chặn dưới do lấy mẫu một cách không cần thiết.** Windows duy trì
   `PeakWorkingSetSize` chính xác; harness của ta spawn `tasklist` mỗi 300 ms rồi
   lấy `max()`. Sửa được — nhưng nó đổi nội dung artifact, nên thuộc protocol chờ
   Sơn.

Và `ullAvailPhys` mà cổng đang so là **standby + free + zero** — gồm **trang
cache**, nên nó **không phải “RAM trống”**. Đó là lời giải thích cho dao động
3966 → 2897 MiB.

#### Lượt 32: dụng cụ đo đã có, vẫn chưa cắm vào

`benchmarks/winmem.py` đọc counter bộ nhớ của **một** process bằng Windows API
(`ctypes`, không dependency mới), xác định đối tượng bằng **handle** chứ không bằng
tên ảnh, và **từ chối** thay vì trả `0`/`"?"` khi không đo được. **Chưa nối vào
`measure.py`, chưa harness nào gọi, chưa trường artifact nào dùng.**

Nó **không** đổi bảng trên, và **không** mở cấp B. Nó chỉ đổi một điều: khi Sơn duyệt
một phép đo ở mục 6 của research note, phép đo đó sẽ lấy **`PeakWorkingSetSize` do OS
duy trì** cho **đúng** process, thay vì `max()` của các mẫu `tasklist` mỗi 300 ms lọc
theo tên ảnh. Chi tiết, giới hạn và ba bước tích hợp: mục **4b** của
[giới hạn RAM Windows](../research/2026-10-10-gioi-han-ram-windows-cho-cpu.md).

Điều nó **chưa** chứng minh: chưa chạy trên child process, và chưa có quan sát nào mà
peak lệch khỏi giá trị hiện tại. Số nó in ra khi smoke-test là của `python.exe` chạy
test — **không phải của model nào**.

#### Lượt 34: M2 đo trên child thật, và một đính chính

`winmem.py` nay **đã đo trên child process**, không chỉ trên chính tiến trình test:
handle **sống qua cái chết của child** (đọc được counter sau khi nó thoát), và peak
**lệch** khỏi current (0.03 MiB current vs 5.23 MiB peak ngay sau exit). Chi tiết:
mục **4c** của [giới hạn RAM Windows](../research/2026-10-10-gioi-han-ram-windows-cho-cpu.md).

**Đính chính cho bảng mục 4d:** phép đo đầu-đối-đầu cho thấy `max(mẫu 300 ms)` thiếu
so với counter OS **4.0%** trên một child tầm thường — và **lấy mẫu nhanh 30× không
giảm được**. Nên đừng đọc "`4438` là chặn dưới" thành "`4438` thấp hơn nhiều": độ lớn
cho một lần chạy **model** vẫn **[CHƯA ĐO]**.

**Vẫn chưa đổi gì:** `measure.py` chưa gọi helper, schema artifact chưa đổi, cả bốn
hằng ngưỡng vẫn `None`. **Cấp B vẫn CHƯA an toàn.**

#### Thứ KHÔNG đổi được bằng lập luận

**RAM khả dụng biến động, và đã đo được trong một lượt:** **3966 MiB** rồi
**2897 MiB**. Con số thứ hai **dưới cả cổng GPU** (3380). Nên một ngưỡng vượt được
lúc 14h có thể trượt lúc 15h, và điều đó đúng với **mọi** lựa chọn ở trên. Cổng là
phép kiểm **lúc khởi động**, không phải một bảo đảm trong suốt lần chạy.

**Đường ASR trên CPU còn yếu hơn: n=0.** `var/bench/` **không có artifact ASR nào**,
nên không có phép đo RAM host nào cho `bench_asr --cpu`. Nó có **cổng riêng**, cũng
`pending`, và cố ý **không vay** số 4438 — 4438 là của **Qwen3-4B**, không phải của
whisper. Hai cổng tách nhau để **một lần duyệt không mở hai đường** mà bằng chứng
không so sánh được với nhau.

## 5. Cấp C — Discord

**Không có lệnh, và sẽ không có trong lát này.** Gate 0-S / 0-P / 0-C / 0-U đều
còn mở. `AGENTS.md` ghi: `requested_live_discord_voice=True` **bị từ chối**, và
ràng buộc này **"không được nới"**. `consent_mode` còn `pending_decision`, là
member **falsy** của enum, nên mọi đường media **chặn**.

## 6. Tuyên bố bị CẤM rút ra từ bất kỳ mục nào ở trên

- "MeetAI đã sẵn sàng dùng trong họp." — **không**. Không gate nào đóng.
- "Dry-run xanh nên grounding đã ổn." — **không**. 12 case tổng hợp; 16 nhãn
  eval còn chờ Sơn và 12 cơ chế false-answer đã đo.
- "Không rò nội dung" như một tuyên bố tổng quát — chỉ đúng cho **đường và các
  lệnh đã liệt kê**, với phần dư ở mục 2.
- "Offline fail-closed đã đạt." — **một phần**. Chiều *artifact vắng* đạt về cấu
  trúc; digest **chưa được cưỡng chế**.
- Bất kỳ con số latency/chất lượng nào từ cấp A — **cấp A không đo gì loại đó**.
