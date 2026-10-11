---
title: "Checklist privacy, consent và dữ liệu Discord — Gate 0-P"
status: "working note; Gate 0-P remains open"
last_updated: "2026-10-10 (lượt 39 — phân loại khẳng định và ghim 2 invariant)"
created: "2026-10-10 (lượt 36)"
source: "docs/research/2026-10-10-gate-0p-discord-policy.md"
---

# Checklist privacy, consent và dữ liệu Discord — Gate 0-P

## Mục đích và giới hạn

Đổi các yêu cầu đã đọc trong Discord Developer Terms/Policy thành việc cần chứng minh trước pilot. Đây là checklist kỹ thuật, **không phải kết luận pháp lý** và không khẳng định Discord đã chấp thuận một route voice của MeetAI. Không mục nào dưới đây tự đóng Gate 0-P, 0-S, 0-C hoặc 0-U.

## Checklist có thể kiểm chứng

| ID | Yêu cầu trước pilot | Trạng thái repo hiện tại | Bằng chứng cần có để đóng |
|---|---|---|---|
| P0-1 | Privacy notice công khai, hiện hành; nêu dữ liệu thu thập, mục đích, nơi xử lý/chia sẻ, thời hạn và cách liên hệ | **Thiếu**: repo có intent/spec, chưa có notice hướng tới người tham gia | Bản notice được duyệt; đối chiếu từng trường dữ liệu với data-flow và cấu hình triển khai |
| P0-2 | Xin phép/đưa disclosure trước khi MeetAI bắt đầu xử lý cho phiên; người tham gia hiểu bot đang làm gì | **Một phần**: FSM `consent.py` có default-deny và receipt metadata trong bộ nhớ; chưa có Discord adapter/UI/notice thực tế; consent mode sản phẩm còn pending | Luồng notice và hành động rõ ràng được kiểm thử trên fixture; quyết định 0-U; sau đó mới tích hợp được phép |
| P0-3 | Từ chối/rút lại có hiệu lực, dừng công việc đang bay và loại dữ liệu tạm liên quan | **Một phần**: revoke generation, kill switch, media gate và purge logic có test; chưa có đường điều khiển Discord hay persistence để xác nhận end-to-end | Test adapter→revoke→cancel/purge trên pipeline thật được phép; đo thời gian dừng và xác nhận không phát sinh xử lý mới |
| P0-4 | Có cách dễ tiếp cận để yêu cầu truy cập/chỉnh sửa/xoá dữ liệu khi có dữ liệu bền vững | **Chưa áp dụng ở runtime hiện tại**: không có store bền vững; nghĩa vụ triển khai vẫn phải có trước khi thêm persistence | Quy trình tiếp nhận và hoàn tất yêu cầu; test xoá toàn bộ bản sao/backup trong phạm vi lưu trữ đã khai báo |
| P0-5 | Chỉ giữ dữ liệu còn cần cho chức năng đã nêu; xoá khi hết mục đích hoặc theo yêu cầu áp dụng | **Chưa chốt**: retention/persistence thuộc 0-U; hiện không có transcript/audio store trong sản phẩm | Chủ dự án chốt retention; inventory các bản sao, cache, log và backup; test thời điểm hết hạn và purge |
| P0-6 | Không dùng message content/API Data để huấn luyện model nếu chưa có cho phép của Discord | **Đang giữ giới hạn**: repo không có pipeline huấn luyện; benchmark dùng fixture/dataset có license riêng | Quy tắc dữ liệu trong vận hành và hợp đồng nhà cung cấp; rà soát thay đổi trước khi thêm training/fine-tuning |
| P0-7 | Chỉ dùng API Data cho chức năng đã mô tả/được phép; không dựa vào route không tài liệu hoá như thể đã được duyệt | **Chưa chứng minh**: route nhận voice guild, SSRC→user, DAVE trên bản dựng cụ thể vẫn chưa xác minh | Tài liệu/ý kiến Discord phù hợp với route cụ thể, version và quyền; protocol docs đơn lẻ không đủ |
| P0-8 | Tách consent xử lý media khỏi quyền thực hiện hành động thay mặt người dùng/server | **Có nền tảng, chưa tích hợp**: consent FSM và authority gate riêng; chưa có Discord sink/adapter | Ma trận quyền: media consent, address/intent, evidence, action approval; negative tests cho từng ranh giới |
| P0-9 | Thu thập tối thiểu; log/telemetry không chứa nội dung họp hoặc định danh không cần thiết | **Một phần**: logging metadata-only, FastAPI telemetry tắt rõ ràng; chưa có triển khai Discord để audit lưu lượng | Kiểm thử log ở đường tích hợp; kiểm kê event/telemetry và xác minh payload/redaction |

## Bảng traceability — đối chiếu với code, lượt 37

**Cách đọc.** Cột *Đã có trong code* chỉ ghi thứ **tự kiểm chứng được ở HEAD**, kèm
cách kiểm. Cột *Thiếu* là khoảng trống **đo được**, không phải ước đoán. Bảng này
**không quyết** consent mode, late-join, persistence, retention hay wording — đó là
0-U và thuộc chủ dự án.

**Một phân biệt chi phối cả bảng, và dễ đọc trượt:** *có cơ chế* ≠ *cơ chế đang chạy
trên một đường thật*. Hầu hết các dòng dưới đây là **cơ chế đã có và có test**, trên
một đường **chưa tồn tại**.

| ID | Đã có trong code (kiểm chứng ở HEAD) | Thiếu | Bằng chứng cần có | Gate |
|---|---|---|---|---|
| P0-1 | **Không có gì.** `docs/intent.md`, `docs/spec.md` là tài liệu kỹ thuật, không phải notice hướng tới người tham gia | Toàn bộ privacy notice | Bản notice được duyệt; đối chiếu từng trường dữ liệu với data-flow thực tế | 0-P, 0-U |
| P0-2 | `consent.py`: `ConsentState` **6 trạng thái** (`UNKNOWN`, `ANNOUNCED`, `CONSENTED`, `DECLINED`, `EXPIRED`, `REVOKED`); receipt **chỉ metadata** (docstring + test). `ConsentMode`/`LateJoinPolicy` có member `PENDING_DECISION` **falsy**. Đo: `media_processing_allowed` = `False` ở mặc định; `require_media_processing_allowed()` **raise `PendingDecisionError`**. **86 test** `test_consent.py` | Luồng notice→hành động cho người tham gia; Discord adapter; UI thao tác | Test luồng notice trên fixture; quyết định 0-U | 0-U, 0-P |
| P0-3 | `consent.py` có **generation counter** tăng mỗi lần revoke, grant trích generation của nó. `supervisor.py`: `RunState.KILLED` **terminal**, `engage()`/`kill()`. **45 test** supervisor, **31 test** media gate | Đường điều khiển từ một adapter thật tới revoke; không có persistence nên chưa có gì để purge | Test adapter→revoke→cancel/purge trên pipeline được phép; đo thời gian dừng | 0-U, 0-C |
| P0-4 | **Đo được: không có store bền vững.** Quét `src/meetai/`: không `sqlite3`, không `pickle`, không ghi file; `json.dumps` chỉ ra **stdout** (`cli.py`) và vào formatter log | Nghĩa vụ chỉ phát sinh **khi** thêm persistence | Quy trình tiếp nhận yêu cầu; test xoá mọi bản sao trong phạm vi đã khai | 0-U |
| P0-5 | Mặc định **OFF** cho transcript/notes/reply journal; không bật được khi `consent_mode` còn pending | Retention chưa chốt | Chủ dự án chốt retention; inventory bản sao/cache/log/backup; test hết hạn + purge | 0-U |
| P0-6 | **Đo được bằng AST, không bằng grep:** `src/meetai/` có **0** định danh dạng huấn luyện (`train`, `fit`, `backward`, `epoch`, `optimizer`, `fine_tune`). *(Phép grep chuỗi đầu tiên báo 2 file — **sai**, vì `train` khớp trong `con**strain**t`.)* | Quy tắc vận hành khi thêm training/fine-tuning | Rà soát trước khi thêm; điều khoản nhà cung cấp | — |
| P0-7 | **Không có gì chứng minh route.** Lượt 36 đọc được protocol docs: UDP dùng cho **cả nhận và gửi**, DAVE E2EE từ 2026-03-01 | Mapping **SSRC → user ID** cho bot guild; xác nhận route được hỗ trợ; khả năng bản dựng làm đủ DAVE | Tài liệu/ý kiến Discord cho **đúng** route, version, quyền. Protocol docs **không đủ** | 0-S, 0-P |
| P0-8 | Hai cơ chế **tách biệt** và độc lập: `consent.py` (media) và `authority.py` (quyền phát ngôn, **ba lớp**). `policy.py`/`content.py`/`errors.py` **không import framework nào** — có test | Chưa có Discord sink/adapter để kiểm ranh giới trên đường thật | Ma trận quyền + negative test cho từng ranh giới | 0-U, 0-P |
| P0-9 | `logging_setup.py`: **allowlist 23 trường** (`ALLOWED_FIELDS`), đếm được. `ui.py`: `docs_url=None`, `redoc_url=None`, `openapi_url=None`. **25 test** logging, **62 test** UI | Chưa có lưu lượng Discord để audit | Kiểm thử log trên đường tích hợp; kiểm kê event/telemetry | 0-P |

### Ba đính chính từ việc đối chiếu

1. **`require_media_processing_allowed()` có ZERO caller trong `src/`.** Đo được: bốn
   kết quả grep gồm **một định nghĩa** (`settings.py:416`) và **ba docstring**
   (`boundary.py:14,65`, `dryrun.py:17`). Nên nó là **nghĩa vụ hướng tới** cho code
   media tương lai, **không** phải một control đang chạy. `AGENTS.md` và
   `PROJECT_STATE.md` mục 6 đã ghi đúng điều này; bảng trên nhắc lại vì một người đọc
   checklist dễ hiểu "media gate có test" thành "media gate đang chặn một đường thật".

2. **`ConsentState` không có member falsy.** Sáu trạng thái, **không** trạng thái nào
   falsy. Tính fail-closed ở tầng *chính sách* đến từ `ConsentMode` và
   `LateJoinPolicy` — hai enum này **có** `PENDING_DECISION` falsy. Phân biệt đáng
   giữ: FSM consent chặn bằng **xử lý trạng thái tường minh**, không bằng truthiness.

3. **P0-6 suýt được ghi sai.** Phép grep chuỗi đầu tiên báo có "train" trong
   `boundary.py` và `session.py`; kiểm lại bằng AST cho **0** định danh huấn luyện —
   `train` khớp trong `con**strain**t`. Giữ lại ở đây vì đây là lần thứ sáu trong dự
   án một phép quét chuỗi con cho kết quả sai, và luật đã chốt là **hỏi AST, đừng hỏi
   văn bản**.

### Điều bảng này KHÔNG làm

Không đóng cổng nào. Không chọn consent mode, late-join, persistence, retention hay
wording. Không khẳng định Discord cho phép route của MeetAI. Không biến việc **đọc
được** điều khoản thành việc **đáp ứng** điều khoản.

## Phân loại trước khi ghim — lượt 39

Đề xuất lượt 38 là "ghim các khẳng định traceability thành test hồi quy". Trước khi
viết test, **18 khẳng định** đã được phân thành ba loại. Phân loại này là phần việc
chính; viết test chỉ là hệ quả của nó.

Lý do phải phân loại: một khẳng định **đúng hôm nay** không tự động đáng ghim. Ghim
nhầm một **số đo** biến nó thành **hợp đồng**, và lần đầu con số thay đổi hợp lệ thì
test đỏ vì một lý do không liên quan gì tới an toàn — đúng kiểu "tín dụng coverage
giả" mà `AGENTS.md` bước 3 cảnh báo, chỉ là theo chiều ngược lại.

### Loại 1 — invariant đáng bảo vệ (**đã có test, không nhân bản**)

| Khẳng định | Đã được ghim ở đâu |
|---|---|
| `ConsentMode`/`LateJoinPolicy` có `PENDING_DECISION` **falsy** | `test_policy.py:162-163`, `test_settings.py:116-117`, `test_session.py:300` |
| `media_processing_allowed` = `False`; `require…()` raise ở mặc định | 8 file test nhắc tới, gồm `test_settings.py`, `test_safety_gates.py` |
| `policy`/`content`/`errors` **không** import framework | `test_environment_invariants.py::TestDomainIndependence` |
| `ALLOWED_FIELDS` là **allowlist** (không phải số 23) | `test_logging_setup.py` |
| `/docs`, `/redoc`, `/openapi.json` **không phục vụ** | `test_ui.py:139` — và đây là test **hành vi**, mạnh hơn việc so ba giá trị `None` trong config |

**Không thêm test nào cho nhóm này.** Nhân bản một bất biến đã được ghim không làm nó
chắc hơn; nó chỉ làm hai chỗ phải sửa khi thiết kế đổi.

### Loại 1b — invariant đáng bảo vệ **và chưa có test** → **đã thêm ở lượt 39**

| Khẳng định | Vì sao đáng ghim | Test mới |
|---|---|---|
| `src/` **không** import module persistence, **không** ghi file nào | *"Mặc định **không** ghi ... bền vững"* là **[CHỐT]** của chủ dự án, không phải giai đoạn tình cờ. Hôm nay nó đúng vì lý do mạnh nhất: **không có code nào ghi được** | `TestNoPersistenceYet` (2 test + 1 control hai chiều) |
| `require_media_processing_allowed()` **không có call site** trong `src/` | Dễ đọc ngược: hàm **có** test, nhưng **chưa chặn gì cả**. Ledger ngăn kết luận sai đó rút ra được từ **tài liệu** | `TestTheMediaGateHasNoCallerYet` (ledger + **khoá hai chiều** với `PROJECT_STATE`) |

**Cả hai được thiết kế để một thay đổi HỢP LỆ không bị coi là lỗi sản phẩm.**
Persistence *sẽ* đến khi 0-U đóng; một caller cho media gate *là mục đích* của hàm
đó. Nên thông báo lỗi của cả hai test **nói rõ đây không phải defect** và liệt kê
việc cần làm: ghi vào ledger · thêm test **hành vi** chứng minh đường đó thật sự từ
chối · cập nhật tài liệu. Ledger chỉ thấy **lời gọi**, không thấy nó có chặn hay
không — nên nó **không thay** được test tích hợp, và nói thẳng điều đó.

**Khoá hai chiều** đáng nói riêng: khi ledger rỗng, `PROJECT_STATE` **phải** còn câu
"chưa có caller nào trong"; khi ledger có mục, câu đó **phải** biến mất. Sửa một bên
mà quên bên kia thì test đỏ — đúng loại trôi dạt mà dự án này vẫn đang bắt bằng tay.

### Loại 2 — hiện trạng có thể đổi hợp lệ, **chỉ cập nhật tài liệu**

| Khẳng định | Vì sao KHÔNG ghim |
|---|---|
| `ConsentState` có **6** trạng thái | Thêm trạng thái thứ bảy là tiến hoá bình thường. Ghim **số lượng** là hợp đồng giòn, không có giá trị an toàn |
| **Không** member nào của `ConsentState` falsy | Falsiness **không được dùng** ở FSM này; nó chặn bằng xử lý trạng thái tường minh. Ghim một thuộc tính ngẫu nhiên sẽ cản một thiết kế hợp lệ sau này |
| `src/` có **0** định danh huấn luyện | Hồ sơ bàn giao ghi **fine-tune (LoRA/QLoRA) là hướng mong muốn**. Ghim cái này là **chủ động cản** một hướng đã được chốt |

### Loại 3 — số đo/báo cáo, **không bao giờ biến thành hợp đồng test**

| Khẳng định | Vì sao |
|---|---|
| **86 / 45 / 31 / 25 / 62** test trong năm file | Số test là **phép đo**, không phải tiêu chí sản phẩm. Ghim nó khiến mỗi lần thêm một test tốt lại phải sửa một con số ở chỗ khác — và tệ hơn, biến "số test" thành mục tiêu |
| `ALLOWED_FIELDS` có đúng **23** mục | Bất biến là **"allowlist chứ không denylist"**, đã được ghim. Con số 23 là hệ quả |
| "grep `train` vẫn khớp 3 file" | Đó là tính chất của **script kiểm chứng**, không phải của sản phẩm |

**Kết quả:** 18 khẳng định → **5** đã có test (không đụng) · **2** đáng ghim và đã
ghim · **3** chỉ ghi tài liệu · **3** là số đo, cố ý không ghim · phần còn lại là
hệ quả của các mục trên.

## Điều kiện đóng cổng

- **0-P**: P0-1 đến P0-9 có người chịu trách nhiệm và bằng chứng; mục P0-7 có căn cứ cho mục đích/route cụ thể, không suy từ tài liệu protocol. Nếu cần xác nhận Discord hoặc rà pháp lý thì giữ `unclear` cho tới khi có phản hồi/chuyên gia phù hợp.
- **0-U**: chủ dự án quyết consent mode, late-join, persistence, retention và wording công khai. Checklist không quyết thay.
- **0-S / 0-C**: cần riêng bằng chứng triển khai route guild, mapping participant, packet→decrypt→PCM→ASR; checklist policy không thay thế các phép thử đó.

## Việc làm an toàn tiếp theo

1. Giữ Cấp A; không bật media, không tạo bot/app, không gọi API, không mở listener.
2. Soạn bản privacy notice nháp chỉ sau khi data inventory và retention được chốt; để trạng thái draft, không xuất bản.
3. Khi được phép nghiên cứu route Discord, lập câu hỏi kỹ thuật hẹp cho Discord: bot account, guild inbound voice, quyền cần thiết, SSRC mapping, DAVE support và review yêu cầu.
4. Chỉ bắt đầu Cấp B sau khi các điều kiện S2.1 có bằng chứng riêng: ngưỡng RAM LLM/ASR, digest model được ghim, egress isolation OS được kiểm chứng.

## Nguồn

- [Discord Developer Terms of Service](https://support-dev.discord.com/hc/en-us/articles/8562894815383-Discord-Developer-Terms-of-Service)
- [Discord Developer Policy](https://support-dev.discord.com/hc/en-us/articles/8563934450327-Discord-Developer-Policy)
- [Voice Connections](https://docs.discord.com/developers/topics/voice-connections)
- Phép đọc và giới hạn suy luận: [Gate 0-P research note](2026-10-10-gate-0p-discord-policy.md), mục 7.