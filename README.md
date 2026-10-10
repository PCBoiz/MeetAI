# MeetAI

Trợ lý AI cá nhân cho cuộc họp, chạy local-first trên máy của chủ dự án.

**Đọc trước khi làm gì:** [PROJECT_STATE.md](PROJECT_STATE.md) rồi [AGENTS.md](AGENTS.md).

## Trạng thái

**Phase 0 xong. Phase 1 gần xong** (còn S1.7). Chưa kết nối Discord, chưa có ASR/LLM/TTS, chưa lưu nội dung cuộc họp.

Live Discord voice bị chặn bởi các cổng bằng chứng 0-S / 0-P / 0-C (xem [PROJECT_STATE.md](PROJECT_STATE.md) mục 5). Việc chọn stack Python **không** phải bằng chứng rằng bot nhận được inbound guild voice audio.

`meetai status` báo đúng những gì build này làm được; mọi capability chưa có đều hiện `OFF` kèm lý do, và fake adapter hiện `MOCK` chứ không phải `ON`.

## Chạy

```bash
uv sync                  # cài dependency theo uv.lock
uv run meetai status     # capability + cấu hình, đã lọc bỏ secret
uv run meetai status --json
uv run meetai status --log-level DEBUG

# Local web UI (chỉ loopback). Cần extra: uv sync --extra ui
uv run meetai serve
uv run pytest            # test
uv run ruff format .     # format
uv run ruff check .      # lint
uv run mypy              # typecheck (strict)

# Đánh giá authority gate: in số liệu + ghi var/authority-eval.md
uv run pytest tests/test_authority_eval.py -q
```

Cấu hình: copy [.env.example](.env.example) thành `.env`. Mặc định là fail-closed; `.env.example` giải thích hệ quả từng biến.

Ba hành vi dễ gây bất ngờ, đều là cố ý:

- Biến `MEETAI_*` **không được nhận dạng** làm app từ chối khởi động. Gõ sai tên một biến consent hoặc persistence sẽ trông như đã bật trong khi thực tế vẫn giữ mặc định, nên im lặng là lựa chọn sai.
- Bất kỳ biến `OTEL_*` nào tồn tại cũng làm app từ chối khởi động. Đó là đường gửi dữ liệu ra ngoài mà thư viện đọc trực tiếp, không qua MeetAI.
- `MEETAI_STATE_DIR` chỉ nhận đường dẫn **tương đối** trong thư mục dự án. Đường dẫn tuyệt đối có thể trỏ ra ổ mạng hoặc thư mục cloud-sync, khi đó state rời khỏi máy.

## Cấu trúc

| Đường dẫn | Nội dung |
|---|---|
| [src/meetai/policy.py](src/meetai/policy.py) | Quy tắc cấu hình deterministic + vocabulary (`ConsentScope`, `Violation`). **Không import framework nào.** |
| [src/meetai/authority.py](src/meetai/authority.py) | **Authority gate 3 lớp** — ranh giới quyền hạn lúc runtime, cho từng phát ngôn |
| [src/meetai/response.py](src/meetai/response.py) | Response schema, allowlist `SpeechAct`, `Evidence` |
| [src/meetai/consent.py](src/meetai/consent.py) | Consent FSM, generation chống revoke race, receipt chỉ metadata |
| [src/meetai/session.py](src/meetai/session.py) | Session lifecycle, late join (cả A1 và A3), thứ tự revoke |
| [src/meetai/media_gate.py](src/meetai/media_gate.py) | Gate từng frame + buffer bound theo size và tuổi |
| [src/meetai/planner.py](src/meetai/planner.py) | Meeting planner trên fixture: allowlist channel, join window, idempotency |
| [src/meetai/knowledge.py](src/meetai/knowledge.py) | Knowledge card, approval, cascade khi xóa/sửa |
| [src/meetai/adapters/](src/meetai/adapters/) | Platform adapter tách 3 plane + fake adapter tự khai `synthetic` |
| [src/meetai/settings.py](src/meetai/settings.py) | Cấu hình fail-closed; adapt policy sang pydantic, không sở hữu policy |
| [src/meetai/capabilities.py](src/meetai/capabilities.py) | Capability registry; không cho phép capability OFF mà thiếu lý do |
| [src/meetai/logging_setup.py](src/meetai/logging_setup.py) | Logging metadata-only, formatter dùng allowlist |
| [src/meetai/evaluation.py](src/meetai/evaluation.py) | Metric cho eval harness; không có accuracy, không có F1 |
| [src/meetai/content.py](src/meetai/content.py) | `MeetingContent` — nội dung họp, `repr` chỉ in hình dạng |
| [src/meetai/errors.py](src/meetai/errors.py) | Exception; message mô tả hình dạng, không mô tả giá trị |
| [src/meetai/supervisor.py](src/meetai/supervisor.py) | Start/Stop, model on/off mock, **kill switch process-wide** |
| [src/meetai/ui.py](src/meetai/ui.py) | Local web UI loopback; telemetry FastAPI tắt tường minh, chặn CSRF, chặn DNS rebinding |
| [src/meetai/cli.py](src/meetai/cli.py) | `meetai status`, `meetai serve` |
| [tests/corpus/](tests/corpus/) | Corpus eval tiếng Việt có nhãn. **Không import `meetai`** — có test khẳng định. |
| [docs/handoff/](docs/handoff/) | Tài liệu nguồn sự thật sản phẩm |
| [docs/adr/](docs/adr/) | Quyết định kiến trúc và lý do |
| [docs/research/](docs/research/) | Dependency inventory, license, kết quả eval |

## Những gì MeetAI không làm

Bốn mức khác nhau, cố ý nói rõ vì chúng **không** cùng độ mạnh:

**Ranh giới thiết kế, có test khẳng định:**

- Không hứa hẹn, xác nhận thay, nhận việc, chốt deadline, bỏ phiếu, phê duyệt hay tạo side effect. Không mức confidence nào và không lượng evidence nào mở được. Đo trên corpus đối kháng: [kết quả eval](docs/research/2026-10-07-authority-eval-v1.md).
- Không xử lý media khi consent policy còn là `pending_decision`.
- Không retrieve card chưa duyệt như fact đã duyệt.
- Không log nội dung hội thoại, token hay audio.

**Đúng vì vắng mặt, không phải vì có cơ chế chặn:** không gửi audio/transcript ra ngoài máy. Cái *được test* là tripwire `requested_external_ai` bị từ chối và không module mạng nào được import. Hiện chưa có audio hay transcript nào để gửi, nên lời khẳng định này sẽ cần một test khác khi pipeline media tồn tại.

**Mặc định OFF, không phải bất biến:** không lưu bền vững raw audio, transcript, notes hay reply journal. Đây là một **công tắc mặc định tắt**, không mở được khi `consent_mode` còn pending. Hồ sơ bàn giao nói rõ nếu sau này bật thì là opt-in riêng — nên gọi nó là "ranh giới thiết kế" sẽ là nói quá.

**Chưa có code, nên chưa có test:** không self-bot, user token, sửa client Discord hay lách giới hạn. Chưa có code Discord nào để vi phạm; đây là ràng buộc cho người viết lát tiếp theo, ghi trong [AGENTS.md](AGENTS.md).

## License

MIT.
