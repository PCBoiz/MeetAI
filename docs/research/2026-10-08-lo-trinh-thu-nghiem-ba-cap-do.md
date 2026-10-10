# Lộ trình thử nghiệm — ba cấp độ, và "thử nghiệm được" nghĩa là cấp nào

Lập 2026-10-08 (lượt 17). **Dữ liệu tham khảo + đối chiếu repo**, không phải
quyết định sản phẩm. Mọi ước lượng theo **khoảng effort**, **không có ngày
lịch** — dự án này chưa có cơ sở nào để hứa ngày.

**Gate 0-S / 0-P / 0-C / 0-U vẫn mở. S2.2 và S2.3 vẫn `partial/open`.**

---

## 0. Câu hỏi "khi nào thử nghiệm được?" có ba câu trả lời khác nhau

Phần lớn nhầm lẫn đến từ việc ba thứ rất khác nhau cùng được gọi là "thử
nghiệm". Bảng này tách chúng ra, và **mỗi dòng dưới đây đều đối chiếu được với
repo** bằng lệnh ghi kèm.

| Cấp | Là gì | Trạng thái hôm nay |
|---|---|---|
| **1** | Offline synthetic/unit + integration, không media | **chạy được ngay**, **4511 test** (lượt 19) |
| **2** | Local integration qua `RecordingSink` | **đã có caller từ lượt 18** — `meetai dry-run`, 10 case. Trước đó: chỉ test |
| **3** | Discord sandbox meeting | **bị chặn bởi 4 gate + 5 thứ chưa tồn tại** |

---

## Cấp 1 — Offline synthetic / unit + integration

**Chạy được ngay, không cần quyết định nào của Sơn.**

| Module | Test | Có kiểm chứng xoá-là-fail? |
|---|---|---|
| `authority.py` | `test_authority.py`, `test_authority_eval.py`, `test_authority_residual.py` (2121 assertion) | **có** — 6 cơ chế, ADR 0006 addendum |
| `answerability.py` | `test_answerability_eval.py`, `_failclosed.py`, `_evidence.py` | **có** — 6 cơ chế, ADR 0007 addendum |
| `boundary.py` | `test_boundary.py` (92 test) | **có** — 6 cơ chế |
| `knowledge.py` | `test_knowledge.py` | một phần |
| `consent.py`, `session.py`, `media_gate.py` | test riêng từng module | một phần |
| `benchmarks/preflight.py` **(không thuộc `src/meetai/`)** | `test_preflight.py`, `test_bench_harness.py` | cấu trúc (AST: không subprocess, không model runtime). **Nằm ở `benchmarks/`, ngoài `pyproject.toml`** — không với tới được từ `meetai status`, `serve` hay `dry-run`. Dòng này từng nằm trong bảng toàn module `src/`, đọc liền mạch sẽ tưởng preflight là phần của app. |

**Phân biệt "có test" với "có test mà xoá cơ chế đi là fail".** Dự án ghi lại
mutation check cho ba module trên; các module còn lại chưa có.

`uv run pytest --collect-only -q` → **4514 collected**; `uv run pytest` →
**4511 passed, 3 skipped** (lượt 19). **Hai con số ở dòng này và ở bảng trên từng lệch nhau** — một audit tìm ra, và cách sửa là làm mới cả hai cùng lúc chứ không chỉ một.

**Effort để mở rộng:** nhỏ. Thêm corpus case hoặc mutation check cho module
chưa có là việc một lát.

---

## Cấp 2 — Local integration qua `RecordingSink`

**Đây là nơi dễ nói quá nhất.** Đường đi đã được kiểm thử **end to end trong
test**, nhưng không có gì ngoài test gọi nó.

### Đã kiểm thử

- `boundary.deliver`: validation → answerability → authority gate → sink, fail-closed từng chặng
- `sink.emit` xuất hiện **đúng một lần** trong toàn `src/` (test AST)
- 7 câu bị cấm × 5 `SpeechAct` → không cái nào tới sink
- 4 hình dạng `UNCLEAR` × 5 `SpeechAct` → không cái nào tới sink
- `SILENT`/`FOLLOWUP` **không mang được** text (lỗi lúc khởi tạo)
- `DeliveryOutcome` **không có field text**

### Còn thiếu — đối chiếu bằng lệnh

**Cập nhật lượt 18:** hai dòng đầu của bảng này **đã đóng**. `src/meetai/dryrun.py` là caller trong `src/`, và `meetai dry-run` là lệnh CLI điều khiển nó. Phần còn lại của bảng vẫn đúng.

| Thiếu gì | Bằng chứng |
|---|---|
| ~~**Caller nào ngoài test**~~ **ĐÃ CÓ** (lượt 18) | `dryrun.py` gọi `deliver`; `meetai dry-run` gọi `dryrun.main` |
| **CLI entry điều khiển `boundary.deliver`** | `meetai status` là lệnh duy nhất; không có lệnh nào dựng `ResponseRequest` |
| **Đường retrieval từ `KnowledgeStore` vào `ResponseRequest`** | `grep -rln "ResponseRequest"` → chỉ `boundary.py` + `test_boundary.py`. `KnowledgeStore` có `approve/edit/supersede` nhưng **không có hàm nào trả về card cho một câu hỏi** |
| **Đường ASR → proposal** | không có module ASR; `meetai status` in `[OFF] asr` |
| **Đường LLM → proposal** | không có module inference; `[OFF] llm` |

**Nên gọi cấp này là gì:** *"boundary đã kiểm thử nội bộ"*. **Không** được gọi
là thử nghiệm họp thật, và **không** được gọi là tích hợp production.

### Việc nhỏ nhất biến cấp 2 thành "đã được dùng"

Một **CLI nhận một turn tổng hợp** — câu hỏi + proposal + claim + card, tất cả
từ một file JSON cục bộ — rồi gọi `boundary.deliver` và in `DeliveryOutcome`.
Nó không mở gate nào: không media, không mạng, không persistence, sink vẫn là
`RecordingSink`.

**Effort: 1 lát (nhỏ).** Nó đổi "sẵn sàng để bị bắt buộc dùng" thành "đã được
dùng", và nó là thứ duy nhất ở cấp 2 không phụ thuộc quyết định nào.

**Retrieval thật** (`KnowledgeStore` → `ResponseRequest`) là **1–2 lát (vừa)**
và chạm vào một quyết định: cards lấy theo tiêu chí gì, và `handoff:110` đã
chốt *"chỉ retrieval personal cards nếu câu hỏi cần lập trường riêng của Sơn"*
— nên phạm vi có sẵn, nhưng cơ chế thì chưa.

---

## Cấp 3 — Discord sandbox meeting

**Bị chặn, và không phải bởi một thứ.** Dưới đây là danh sách đầy đủ, mỗi mục
gắn với gate hoặc quyết định cai quản nó.

### Gate bằng chứng

| Gate | Nội dung | Đóng bằng gì |
|---|---|---|
| **0-S** | Standard bot token nhận được inbound guild voice audio **và** mapping SSRC → user | Bằng chứng tái lập được trên build cụ thể, hoặc tài liệu chính thức. **Không phải** Social SDK `UserAudioReceivedCallback` — đó là voice call trong SDK lobby với user token, đã ghi ở PROJECT_STATE vòng 18 |
| **0-P** | Route được Discord hỗ trợ + rà Developer Terms/Policy **tại ngày triển khai** + xác định review/approval | Đọc policy + xác định quy trình. Là **tác động ra ngoài** nếu phải liên hệ Discord → cần Sơn xác nhận trước |
| **0-C** | Thứ tự packet/decrypt/PCM/ASR quan sát trên build cụ thể; late join, reconnect, SSRC remap, revoke race, cancellation | Quan sát thực nghiệm. **Phụ thuộc 0-S** — không quan sát được thứ tự nếu chưa nhận được audio |
| **0-U** | Sơn chọn consent mode / persistence / retention wording | **Chỉ cần Sơn quyết.** Không chặn bởi kỹ thuật |

### Chặn ngoài gate — những thứ chưa tồn tại

| Thiếu | Hệ quả |
|---|---|
| **Không có media sink nào** | Có test fail nếu một cái xuất hiện trong `src/`. Một sink tới cuộc họp phải gọi `require_media_processing_allowed()` và kiểm consent |
| **Không có TTS** | `[OFF] tts`, và hồ sơ ghi nó **không** phải phụ thuộc của MVP |
| **Không có persistence** | 4 switch mặc định OFF, 2 rào tự từ chối khi đặt True |
| **`require_media_processing_allowed()` raise khi consent còn pending** | Đây là fail-closed đúng thiết kế: mọi đường media **đang** bị chặn bằng code, không bằng lời hứa |
| **`AGENTS.md` cấm tường minh** | *"Không bật live Discord voice. Gate 0-S/0-P/0-C chưa đóng. `requested_live_discord_voice=True` bị từ chối. **Không được nới ràng buộc này.**"* |

### Bằng chứng nào mới tính là đóng

- **0-S:** một bản ghi tái lập được cho thấy bot token nhận PCM từ guild voice **và** SSRC ánh xạ sang user id ổn định qua reconnect.
- **0-C:** quan sát thứ tự trên build cụ thể, kèm late join / reconnect / SSRC remap / revoke race / cancellation — tức là **sau** 0-S.
- **0-P:** trích dẫn policy tại ngày triển khai + đường review xác định.
- **0-U:** phát ngôn trực tiếp của Sơn, ghi vào `PROJECT_STATE.md` mục 3.

**Effort:** không ước lượng được cho 0-S/0-C vì chúng là **khảo sát**, không
phải xây dựng — effort phụ thuộc vào thứ tìm được. 0-P là đọc tài liệu (nhỏ)
cộng một bước có thể cần Sơn. 0-U là **một quyết định**, không phải effort.

---

## Critical path

**0-U mở khoá nhiều việc downstream nhất, và nó không cần một dòng code nào.**

Lý do: 0-U chặn **persistence, retention, consent mode** — và consent mode là
thứ `require_media_processing_allowed()` kiểm. Chừng nào nó còn pending, **mọi**
đường media bị từ chối ở mức code, nên cả cấp 3 lẫn bất kỳ sink thật nào đều
không khởi động được, **kể cả khi 0-S/0-P/0-C đã đóng**.

PROJECT_STATE mục 4B ghi rõ đây là việc **chọn**, không phải việc **xây**: FSM
và cả hai chiến lược late join **đã xây xong** sau một interface, mặc định
đóng.

**Thứ tự đề xuất, không phải quyết định:**

1. **0-U** — một quyết định của Sơn, mở khoá nhiều nhất
2. **CLI cho cấp 2** — 1 lát, không phụ thuộc gate nào
3. **0-P** — đọc policy, rẻ, và nó quyết định 0-S có đáng khảo sát không
4. **0-S** rồi **0-C** — theo thứ tự, vì 0-C phụ thuộc 0-S

---

## Những thứ tài liệu và code từng nói khác nhau

| Chỗ | Đã sửa ở lượt 17 |
|---|---|
| `meetai status` in `asr`/`llm` là *"chưa benchmark model nào"* | **Sai từ sau S2.2/S2.3.** Capability vẫn đúng là OFF (không có đường nào trong pipeline), nhưng lý do thì sai. Đã sửa thành *"đã benchmark ở S2.2/S2.3, nhưng chưa có đường nào trong pipeline và vẫn partial/open"* |

Đây là output người dùng đọc, nên một lý do sai là một tuyên bố sai — không
phải một chi tiết tài liệu.
