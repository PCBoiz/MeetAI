# ADR 0003 - Local web UI và kill switch

- **Ngày:** 2026-10-07
- **Trạng thái:** [CHỐT] cho lựa chọn stack (Sơn đã duyệt FastAPI cho local web UI, và đồng ý hoãn tới khi UI được triển khai). [ĐỀ XUẤT đã triển khai] cho các quyết định bảo mật dưới đây — chúng là quyết định kỹ thuật của tôi để đóng những lỗ đã verify, **không** phải quyết định sản phẩm.
- **Bối cảnh:** một threat model read-only đã verify FastAPI 0.142.2 từ source thật trong uv cache (hash khớp lockfile), rồi tôi verify lại trên bản cài thật.

## Mô hình đe dọa

Một người dùng, một máy, Windows 11 desktop. Không multi-tenant, không truy cập từ xa. Tài sản: audio/transcript cuộc họp và hai credential.

**Đối thủ quan trọng là một trang web mà người dùng đang mở**, vì đó là đối thủ duy nhất tiếp cận được **mà không cần chỗ đứng nào** trên máy.

Một đối thủ đã chạy được code dưới quyền người dùng thì đọc được `.env`, `state_dir`, và bộ nhớ của tiến trình này. **Loopback UI không phòng được lớp đó**, và mọi control thêm vào (token trên disk, allowlist process, kiểm peer-PID) đều bị chính đối thủ đó vô hiệu bằng cách đọc file token. Xây những cái đó là nghi lễ.

Control thật cho lớp đó: **UI này không có gì đáng lấy.** Không endpoint nào trả về nội dung cuộc họp. Đó là một thuộc tính thiết kế phải giữ, không phải một control để thêm. Ghi ra đây để sau này không ai tin rằng UI được làm cứng chống malware cục bộ.

## Quyết định, xếp theo rủi ro thật

### 1. Telemetry của FastAPI phải tắt tường minh

**Đã verify trên bản cài thật.** `FastAPI()` mặc định resolve ra:

```
tracing = True, metrics = True, logs = True,
operation_spans = True, auto_configure = True
```

`logs` ghi exception message **và** request body **và** validation error *kèm giá trị input gốc*. Với một endpoint sửa cấu hình, đó chính là lỗ rò raw-input mà toàn bộ kỷ luật `sanitised_validation_errors` tồn tại để đóng, bị mở lại qua một đường thứ hai. Endpoint exporter đọc từ `OTEL_EXPORTER_OTLP_ENDPOINT` cùng năm họ biến khác.

Thứ đang chặn export là `opentelemetry-sdk` chưa được cài, và cơ chế chặn là một `ImportError` bị catch rồi hạ xuống `logger.warning` để startup tiếp tục — một thất bại mềm, im lặng, đúng hình dạng sẽ lật sang export thật ngay khi có gì kéo SDK vào.

**Quyết định:** `create_app()` là **chỗ duy nhất** `FastAPI(...)` được gọi, có test enforce bằng AST. `TELEMETRY_OFF` tắt cả năm signal. Test assert **exact-dict** chứ không phải subset — subset sẽ pass khi một version sau thêm signal thứ sáu mặc định bật. FastAPI pin **chính xác** `0.142.2`: một pin `>=` không giữ được một lần review về default telemetry.

**Ba extra kéo SDK, không phải một:** `opentelemetry`, `standard`, `standard-no-fastapi-cloud-cli` và `all`. `AGENTS.md` trước đây chỉ cấm `fastapi[standard]` — không đủ. Có test cấm cả `fastapi-cloud-cli`, `fastapi-cli`, `fastar`, `logfire`.

**Lưu ý giữ cho đúng:** `opentelemetry-api` là hard dependency **không tránh được** của FastAPI và được import ở module scope, nên `import fastapi` luôn import opentelemetry. Có test ghi rõ sự phân biệt này, để sau này không ai "làm cứng" suite bằng cách cấm luôn package api và làm UI hỏng.

### 2. CSRF — rủi ro số một, và là rủi ro duy nhất khai thác được không cần chỗ đứng

Bất kỳ trang nào đang mở cũng `fetch('http://127.0.0.1:8765/api/kill', {method:'POST'})` được. Response là opaque, nhưng **side effect vẫn xảy ra**. CORS không giúp: nó quản việc *đọc* response, không bao giờ quản việc *gửi* request đơn giản.

**Quyết định:** mọi request đổi trạng thái phải có header `X-MeetAI-Request: 1`. Một `<form>` không đặt được header đó, và `fetch` đặt được nhưng sẽ kích hoạt preflight mà không middleware nào trả lời. Mọi endpoint đổi trạng thái là POST — `GET /kill` thì một `<img src>` cũng gọi được.

**Chọn header thay vì CSRF token:** token cần state phía server, một cookie, và một chính sách hết hạn, để mua đúng cùng một bảo đảm trước đúng cùng một đối thủ.

### 3. Docs tích hợp phải tắt

**Đã verify:** `/docs` serve HTML trỏ tới `cdn.jsdelivr.net`; `/redoc` trỏ tới đó cộng `fonts.googleapis.com`; cả hai lấy favicon từ `fastapi.tiangolo.com`. Mở một trang là browser của người dùng liên lạc bốn host thứ ba, rò timing, IP và một referer tiết lộ MeetAI đang chạy.

Guard `MEETAI_*` và `OTEL_*` **không thấy được** việc này: request đi từ browser, không từ tiến trình này.

**Quyết định:** `docs_url=None, redoc_url=None, openapi_url=None`. Test assert cả 404 **và** không response nào chứa host ngoài loopback.

### 4. Host header — đóng DNS rebinding

Một trang của attacker có hostname re-resolve về `127.0.0.1` vẫn giữ origin của nó, nên same-origin policy ngừng bảo vệ và nó **đọc** được response.

**Quyết định:** `TrustedHostMiddleware` với đúng địa chỉ bind. `localhost` **cố ý không** có trong allowlist, khớp với rail trong settings: nó là một *cái tên*, phân giải lúc bind.

### 5. Không CORS middleware, không WebSocket

Cài CORS chỉ có thể **nới** mặc định hiện tại (không có header `Access-Control-Allow-Origin` nào được phát, nên không trang cross-origin nào đọc được response).

**Đã verify:** starlette **không** kiểm `Origin` trên WebSocket handshake. Nên một socket sẽ reachable cross-origin, hai chiều — **tệ hơn HTTP**, nơi ít nhất việc đọc response bị chặn. Trạng thái được poll qua HTTP thường.

### 6. Bind thất bại phải là một từ chối ồn ào

**Đây là chỗ bản triển khai đầu của tôi sai, và tôi đo ra chứ không đoán.** uvicorn tự catch lỗi bind, log nó, rồi gọi `sys.exit(3)`. `except OSError` của tôi **không bao giờ** chạy, và tiến trình exit 3 — **trùng** với `EXIT_UI_UNAVAILABLE`, nên một cổng bị chiếm sẽ được báo cho người dùng là "thiếu extra ui".

**Quyết định:** catch `(OSError, SystemExit)`, exit `EXIT_UI_BIND_FAILED = 4`. **Không bao giờ** thử cổng khác: bookmark của người dùng là neo tin cậy, và tự ý đổi cổng chính là cuộc tấn công chiếm cổng do mình tự thực hiện.

### 7. Không authentication

Lập luận từ mô hình đe dọa, không từ thói quen. Một secret trên loopback phòng được **đối thủ nào**? Trang web không đọc được nó (same-origin + header check đã chặn). Process cục bộ đọc được file chứa nó. Nên nó không thêm bảo vệ trước đối thủ nào cả, mà thêm một file secret, một đường rò, và một failure mode.

**Điều phải đúng để điều này an toàn:** không endpoint nào trả về nội dung cuộc họp, và header check cộng Host check phải còn nguyên.

### 8. Những thứ cố ý **không** xây

| Không xây | Vì sao |
|---|---|
| CSRF token có server-side state | Header check mua cùng bảo đảm, không state, không cookie, không expiry |
| TLS trên loopback | Phòng một on-path attacker không tồn tại trên interface loopback; thêm một thay đổi trust store và một failure mode gia hạn |
| Rate limiting | Đe dọa nó giải quyết (brute force) giả định có một secret để đoán; mục 7 lập luận là không nên có |
| Mã hóa token at rest với key cạnh nó | Nghi lễ |
| Kiểm peer-PID | Bị vô hiệu bởi chính đối thủ cùng quyền |

## Kill switch — hợp đồng, và chỉ tuyên bố đúng những gì đo được

### Đã sửa ba lỗ verify được

**(d) `close()` yếu hơn `revoke()`.** Đã verify: một stage downstream có **hai** chỗ để hỏi lại quyền — object gate, hoặc ledger trực tiếp qua `is_granted(key, generation=captured)`. `MediaGate.close()` chỉ trả lời chỗ thứ nhất. `revoke()` bump generation nên trả lời cả hai. Nghĩa là **một revocation mạnh hơn một kill** — ngược với điều cả hai cái tên gợi ra. Sửa: `close()` gọi `ledger.invalidate_outstanding_work()`. Có test; test đó fail trước khi sửa.

**(f) Buffer đã purge vẫn nhận push.** `self._buffers.clear()` bỏ reference *của session*, nhưng consumer nào đã gọi `buffer_for()` trước đó vẫn giữ object — và một buffer purged-nhưng-mở vẫn nhận `push` tiếp. Nên "audio trong buffer không còn với tới được" là **không đúng** với một holder. Sửa: `BoundedBuffer.close()` terminal, `push` thành no-op, `drain` trả rỗng.

**(h) Kill switch không process-wide.** Không có session registry, nên một nút kill chỉ kill được session nó giữ reference. `Settings` là `frozen=True` và `model_copy` re-validate thành object **mới**, nên không thể lật `media_processing_allowed` trên settings đang chạy. Sửa: một `KillSwitch` latch, composed vào `policy_allows_media` — đây là thiết kế **duy nhất** mà "kill everything" là đúng thay vì "kill everything tôi đang giữ".

**(i)** `PurgeResult.gate_closed` giờ **quan sát** `gate.is_closed` thay vì hardcode `True`.

### Những gì được phép tuyên bố

> Kill switch đóng media gate **ngay và không gỡ được**, vô hiệu mọi lần kiểm lại ở cả gate và ledger, loại bỏ mọi frame trong buffer kể cả với một holder, và **yêu cầu** hủy những công việc đã đăng ký.

Không mạnh hơn thế.

### Những gì **không** được tuyên bố, và vì sao

- **"Dừng mọi công việc đang chạy."** `register_cancellation` là opt-in, append-only. Không có registry công việc, nên công việc chưa đăng ký callback là **vô hình** — và không gì làm cho con số đếm được đầy đủ. Đây là điều quan trọng nhất không được nói quá.
- **"N task đã bị hủy."** `_run_cancellations` bọc mỗi callback trong `suppress`, cố ý, rồi trả `len(callbacks)` bất kể. Một callback raise ở dòng đầu vẫn được đếm. `tasks_cancelled` đếm **lần gọi**, không phải lần thành công. Có test nói rõ điều đó.
- **"Hủy là dừng."** Callback là `Callable[[], None]`: không return, không join, không await, không timeout, không xác nhận. Với asyncio đó là `Task.cancel()`, có hiệu lực ở `await` tiếp theo — một lời gọi ASR CPU-bound không bao giờ tới đó.

### Còn thiếu machinery, ghi lại chứ không che

| Muốn tuyên bố | Cần gì |
|---|---|
| Mọi công việc đang chạy **đã dừng** | Work registry với acknowledge-stopped từng job, cộng một bounded wait và một timeout được báo. **Không** dựng được từ `Callable[[], None]`. |
| Con số công việc đang chạy là **đầy đủ** | Công việc phải đăng ký **lúc bắt đầu**, không phải lúc đăng ký callback hủy — khi đó công việc chưa đăng ký là một vi phạm bất biến **phát hiện được** thay vì vô hình. |
| An toàn khi kill đồng thời với media | **(g)** `Session` dùng `list`/`dict`/`set` không lock. Cụ thể: `_run_cancellations` làm `callbacks, self._cancellations = self._cancellations, []` — một `register_cancellation` chen vào giữa lần đọc và lần rebind sẽ **rơi vào list đã drain, bị mất im lặng, không bao giờ được gọi**. Hiện mọi thứ single-threaded nên đây là latent; một HTTP handler gọi `close()` trong khi một media thread đăng ký công việc làm nó thành thật. **UI hiện không tạo ra tình huống đó** (không thread nào xử lý media), nhưng lát đầu tiên thêm concurrency phải chọn: một lock, hoặc một quy tắc single-task-affinity tường minh. |

## Capability model — tôi đi chệch khuyến nghị, có lý do

Threat model đề xuất đổi `Capability.available: bool` thành một status enum với `STOPPED`, `KILLED`, `LOADING`...

Tôi **không** làm, và tách biệt thay vì gộp: `Capability` trả lời *tính năng này có tồn tại không, và nếu không thì vì sao*; `Supervisor` trả lời *có đang chạy không*. Gộp hai cái sẽ làm `asr` mang trạng thái runtime của một thứ chưa được xây.

Những gì **đã** làm theo khuyến nghị: thêm `blocked_by: BlockedBy` — một mã **ổn định** cạnh prose, vì UI không được phép string-match một câu tiếng Việt mà người ta sẽ sửa lại. Và `operator_can_act` phân biệt *người dùng có làm gì được không*, vì render một nút cạnh một thứ không sửa được cũng là một kiểu không trung thực.

Trạng thái `LOADING`/`ERROR`/`UNKNOWN` sống ở `ModelSwitch`, nơi chúng thuộc về. `ModelState.UNKNOWN` là member **falsy**, nên `if model.state:` fail closed — một bool sẽ buộc UI render ON hoặc OFF trong lúc đang probe, tức là **đoán**.

## Phần dư, ghi lại

- **[GIẢ ĐỊNH]** Threat model nêu rằng wheel của FastAPI ship `.agents/skills/fastapi/SKILL.md` — text của bên thứ ba đặt vào một đường tìm kiếm agent-skill. Tôi **chưa verify** liệu tooling agent có thực sự discover `.agents/` trong site-packages. Không phải đường egress, nhưng thuộc bề mặt supply-chain.
- **[CHƯA VERIFY]** `--reload`/`--workers` của uvicorn có re-import gì liên quan telemetry trong child process không. S0.6 chạy single-process, reload tắt, nên nghi là không liên quan — nhưng chưa kiểm.
- `starlette.testclient` cảnh báo deprecation về `httpx`, khuyên `httpx2`. Dev-only, không ảnh hưởng runtime; chưa đổi.
