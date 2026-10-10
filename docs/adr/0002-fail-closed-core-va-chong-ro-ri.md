# ADR 0002 - Lõi fail-closed và các ranh giới chống rò rỉ

- **Ngày:** 2026-10-07
- **Trạng thái:** [ĐỀ XUẤT đã triển khai] - các quyết định kỹ thuật dưới đây do tôi đưa ra để đóng lỗi bảo mật đã verify. Chúng **không** phải quyết định sản phẩm của chủ dự án, và không chốt thay bất kỳ câu nào ở `PROJECT_STATE.md` mục 4B.
- **Bối cảnh:** ba audit read-only (repo/architecture, dependency/license, security/privacy) chạy trên commit `8976a42` tìm ra 2 lỗ rò credential CRITICAL đã verify end-to-end, 4 đường bypass rail, và một rủi ro egress ở tầng dependency.

## Vấn đề 1: `ValidationError` của pydantic in cả raw input ra stderr

**Đã verify, không phải suy đoán.** Với `MEETAI_DISCORD_BOT_TOKEN=<token>` và `MEETAI_ALLOW_EXTERNAL_AI=true`, lệnh `meetai status` in ra stderr:

```
input_value={'allow_external_ai': 'tr...aaaaaaaa_SENTINEL_TAIL'}
```

pydantic truncate **giữa** repr và giữ **đuôi**. Credential được khai báo **cuối cùng** trong model nên chính là phần sống sót. `exc.errors()[0]["input"]` còn chứa credential **đầy đủ, không truncate**, nên `logger.exception` sẽ ghi nguyên credential vào disk vĩnh viễn.

Gốc rễ: `_reject_prohibited_combinations` là `@model_validator` raise `ValueError`. Lỗi **model-level** của pydantic mang theo *toàn bộ* mapping input thô, trong đó credential còn là `str` thuần, chưa phải `SecretStr` — nên repr masking của `SecretStr` không có cơ hội hoạt động. Lỗi **field-level** chỉ mang giá trị của field đó.

**Quyết định — bốn lớp, không phải một:**

1. Rail chuyển sang `@field_validator`. Error khi đó chỉ mang một bool. Đây là sửa **lớp lỗi**, không phải sửa một ca.
2. Thêm `sanitised_validation_errors()` dùng `exc.errors(include_input=False, include_url=False)`. CLI **không bao giờ** `print(exc)`.
3. `model_config["hide_input_in_errors"] = True` làm defence in depth. Nó chỉ xóa `input_value` khỏi `str(exc)`, **không** xóa `errors()["input"]` — nên lớp 2 vẫn là lớp thật sự đóng lỗ.
4. Credential khai báo **đầu tiên** trong model, để nằm ở phần bị truncate thay vì phần được giữ. Mang tính bảo hiểm, miễn phí.
5. Cross-field rule chuyển sang raise `ConfigurationRejectedError` (không phải `ValueError`), nên pydantic để nó propagate nguyên vẹn thay vì bọc thành model-level error.

## Vấn đề 2: credential gõ sai tên trong `.env` bị in nguyên văn

**Đã verify.** `.env` chứa `MEETAI_DISCORD_TOKEN=<secret>` (field thật là `MEETAI_DISCORD_BOT_TOKEN` — đúng cái typo mà guard tồn tại để bắt) in ra:

```
input_value='SUPER-SECRET-CANARY-12345', input_type=str
```

Nguyên nhân: `_reject_unknown_env_vars` chỉ quét `os.environ`. Dotenv source của pydantic-settings, với `extra="forbid"`, giữ key không khớp **kèm prefix** làm extra field → `extra_forbidden` với `input_value` là **giá trị thô, không truncate**. Đây là lỗ rò xác suất cao nhất: `.env` chính là nơi tài liệu bảo người dùng đặt credential.

**Quyết định:** tắt hẳn env source và dotenv source của pydantic-settings (`settings_customise_sources` → chỉ `init_settings`). `load_settings()` tự đọc `.env` qua `python-dotenv`, **kiểm tra tên trước**, và chỉ đưa giá trị của field đã nhận dạng vào pydantic.

Hệ quả phụ có giá trị: input trở thành tham số tường minh (`env=`, `env_file=`) thay vì global ngầm. Test không còn cần `monkeypatch.chdir` + `delenv` để có kết quả xác định.

## Vấn đề 3: bốn đường tạo `Settings` với rail bị vô hiệu

`frozen=True` chỉ chặn gán attribute thông thường. Đã verify cả bốn đều tạo được object với rail bật: `model_construct()`, `model_copy(update=...)`, `object.__setattr__`, ghi `__dict__`. Và `redacted_summary()` **không** hiển thị rail, nên một object đã bị vô hiệu render **giống y hệt** một object an toàn.

**Quyết định:**
- `model_construct` → `NotImplementedError`.
- `model_copy(update=...)` → đi qua `model_validate`.
- Rail có trong `redacted_summary()`, và CLI in cảnh báo rõ khi thấy bật.
- `assert_tripwires_disarmed()` kiểm lại tại điểm dùng: validation lúc construct là tiện lợi, không phải control duy nhất.

Đây không phải tấn công từ xa — cần code execution trong process. Nó là rủi ro **maintainer tương lai**: một `model_copy(update=...)` thiện chí trong fixture sẽ tháo hết rail mà không test nào, UI nào thấy.

## Vấn đề 4: `pending_decision` truthy — fail-open dễ xảy ra nhất

`bool(ConsentMode.PENDING_DECISION)` từng là `True`, vì enum là `(str, Enum)`. Một guard trông rất hợp lý như `if settings.consent_mode:` sẽ **fail open** đúng vào trạng thái phải chặn. Và không có code nào biến `PENDING_DECISION` thành một cái chặn — ý nghĩa đó chỉ được *ghi trong docstring*.

**Quyết định:**
- Bỏ `str` mixin. Enum thuần, serialize tường minh qua `.value`. Điều này cũng loại footgun `str(member)` trả `"ClassName.MEMBER"` khác với chuỗi trong file config.
- `__bool__` trả `False` cho `PENDING_DECISION`.
- Thêm `media_processing_allowed` và `require_media_processing_allowed()`: một cái gate có tên, mà code media **phải** gọi. "pending_decision chặn media" trở thành thuộc tính code enforce.
- Test enumerate **toàn bộ** cross product 3×3 của hai enum, không sample.

## Vấn đề 5: FastAPI mang theo telemetry subsystem bật sẵn

Chi tiết trong `docs/research/2026-10-07-dependency-baseline.md` mục 1. Tóm lại: FastAPI 0.142 không phải consumer thụ động của `opentelemetry-api` — nó có telemetry riêng, `auto_configure` mặc định bật, đọc `OTEL_EXPORTER_OTLP_ENDPOINT` từ môi trường, và `logs` ghi cả exception message lẫn request body. Thứ đang chặn export là **`opentelemetry-sdk` chưa được cài**, không phải "chưa cấu hình exporter" — và cơ chế chặn là một `ImportError` bị catch rồi log WARNING và bỏ qua.

**Quyết định:** FastAPI + uvicorn chuyển sang `[project.optional-dependencies] ui`, chưa cài. `load_settings()` từ chối khởi động nếu có bất kỳ biến `OTEL_*`. Test khẳng định không có OTel SDK/exporter nào importable.

**[CHỜ QUYẾT ĐỊNH]** Việc này **thu hẹp** phạm vi dependency mà chủ dự án đã duyệt ("FastAPI chỉ phục vụ local web UI"). Tôi cho rằng nó trung thành với *mục đích* đã nêu — UI chưa tồn tại — nhưng đây là thay đổi cần được biết và có thể bị bác.

## Vấn đề 6: `state_dir` nhận đường dẫn mạng

`ui_host` được bảo vệ cẩn thận trong khi **đích ghi** thì không ràng buộc gì. Đã verify `MEETAI_STATE_DIR=\\evil-nas\share\state` được chấp nhận. `state_dir` sẽ giữ consent receipt và metadata vận hành, nên một đường UNC / ổ mạng / thư mục OneDrive khiến state rời khỏi máy, im lặng, chỉ bằng cấu hình.

**Quyết định:** thêm field validator từ chối UNC và ổ mạng. Đồng thời `ui_host` bỏ `localhost` khỏi allowlist — đó là một *cái tên*, phân giải lúc bind, nên một file hosts bị sửa sẽ đổi chỗ UI thật sự lắng nghe trong khi check vẫn pass.

## Vấn đề 7: logging là bề mặt rò rỉ lớn nhất phía trước

S0.5 được thiết kế quanh năm đường rò mà audit nêu tên, chứ không chỉ "ghi log có cấu trúc":

| Đường rò | Phòng tuyến |
|---|---|
| `logger.exception` trên `ValidationError` (payload chứa credential đầy đủ) | `MetadataOnlyFilter` thay exception bằng type + message đã sanitise, xóa `exc_info`/`exc_text`/`stack_info` |
| `__repr__` tự sinh của dataclass giữ transcript | `MeetingContent` - repr chỉ in `chars=N`; mọi dataclass giữ nội dung phải `field(repr=False)` |
| `extra=` truyền thẳng vào formatter | **Allowlist** `ALLOWED_FIELDS`, không phải denylist. Denylist thua ngay cái tên field mới đầu tiên. Key bị bỏ được **đếm** và báo, nên mất mát là thấy được. |
| Logger thư viện propagate lên root handler | Filter + formatter áp cho **mọi** record bất kể nguồn; test đẩy canary qua logger `fastapi`/`opentelemetry.trace`/`uvicorn.access` |
| Exception message nhúng giá trị | Quy tắc: message mô tả **hình dạng**, không bao giờ mô tả giá trị. Đã bỏ `got {value!r}` khỏi validator `ui_host`. |

Sink mặc định là stderr. **Không ghi file**: vị trí log và retention là quyết định chưa có (hồ sơ mục 10 câu 5), và stderr thì không có retention nào cả.

## Phương án đã cân nhắc và loại

| Phương án | Lý do loại |
|---|---|
| Chỉ thêm sanitiser, giữ rail ở model-level | Sửa một ca, không sửa lớp lỗi. Model validator tiếp theo sẽ tái tạo đúng lỗ đó. |
| Giữ dotenv source của pydantic-settings, thêm quét `.env` song song | Hai nguồn sự thật về cùng một file; lỗ rò phụ thuộc internals của library mà `pyproject.toml` chỉ pin floor. |
| Denylist tên field trong logging | Thua ngay cái tên mới đầu tiên. Allowlist fail về phía mất một chẩn đoán, không fail về phía publish transcript. |
| Giữ `(str, Enum)` cho tiện round-trip config | Truthiness của `PENDING_DECISION` là fail-open dễ xảy ra nhất. `.value` tường minh là giá đáng trả. |
| Giữ FastAPI đã cài để sẵn sàng cho S0.6 | Mang vào một telemetry subsystem bật sẵn cho một UI chưa tồn tại. |

## Khả năng đảo ngược

Cao. Toàn bộ là code Phase 0/1 không có dữ liệu bền vững, không có API công khai, không có người dùng ngoài. Thứ đắt nhất để đảo là lựa chọn bỏ `str` mixin ở enum (mọi chỗ serialize phải dùng `.value`) — nhưng đó cũng là chỗ dễ test nhất.
