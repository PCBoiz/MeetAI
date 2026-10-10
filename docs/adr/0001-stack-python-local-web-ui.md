# ADR 0001 - Stack: Python 3.12 + local web UI

- **Ngày:** 2026-10-07
- **Trạng thái:** [CHỐT] - Sơn trả lời trực tiếp trong hội thoại ngày 2026-10-07
- **Bối cảnh:** `D:\MeetAI` trống hoàn toàn, chưa phải git repo, không có convention nào để kế thừa. Hồ sơ bàn giao cố ý không khóa stack trước benchmark.

## Quyết định

### 1. Ngôn ngữ chính: Python

Lời Sơn: *"Chọn Python. Giữ lõi MeetAI và model runtime trong cùng hệ sinh thái Python để giảm số toolchain ở Phase 0/1. Bọc Discord sau platform adapter; chưa xem lựa chọn stack là bằng chứng rằng bot có thể nhận audio voice."*

Hệ quả bắt buộc ghi nhớ: **chọn Python không phải bằng chứng cho Gate 0-S.** Việc Discord bot có nhận được inbound guild voice audio hay không vẫn là cổng chưa đóng, độc lập hoàn toàn với lựa chọn này.

### 2. Phiên bản: Python 3.12, pin bằng uv

Lời Sơn: *"Chọn Python 3.12 và pin bằng uv. Trước khi khóa dependency, kiểm tra khả năng tương thích của các gói dự kiến trên Windows và NVIDIA; chưa thêm gói ML khi Phase 0/1 chưa cần."*

- Máy có sẵn Python 3.14.4 nhưng **không dùng**: 3.14 quá mới, nhiều wheel ML có thể chưa build sẵn.
- Đã cài `cpython-3.12.13` qua `uv python install 3.12`.
- Pin ở hai chỗ: `.python-version` = `3.12`, và `requires-python = ">=3.12,<3.13"`.
- **Đã kiểm chứng, nhưng lý do ban đầu lỗi thời.** Ban đầu chọn 3.12 vì cho rằng diện wheel ML rộng nhất. Kiểm tra wheel index thật (2026-10-07, xem dependency inventory mục 5) cho thấy cp313 **phủ tương đương**, nên 3.12 là lựa chọn **bảo thủ nhất trong nhiều lựa chọn phủ tương đương** — vẫn đúng cho pilot, nhưng là một lập luận khác. Chỗ diện wheel thật sự mỏng đi là 3.14+.
- **[CHỜ BẰNG CHỨNG]** Chưa cài gói ML nào trên máy này. "Wheel tồn tại cho ABI tag cp312" không phải "đã chạy được trên GTX 1660 Ti". Thuộc S2.1.

### 3. UI: local web UI, chưa đóng gói desktop

Lời Sơn: *"Chọn local web UI chạy trên máy, mở bằng browser. Làm supervisor gọn, thể hiện rõ Start/Stop, health, trạng thái model, AI disclosure và consent. Chưa đóng gói thành desktop app; đánh giá lại sau khi UI và workflow ổn định."*

- FastAPI + uvicorn, **bind loopback bắt buộc** (`Settings._must_be_loopback` từ chối mọi địa chỉ khác).
- Không Electron, không Tauri (Tauri còn cần Rust, máy chưa có).
- Đánh giá lại việc đóng gói desktop sau khi workflow ổn định.

### 4. Git: local, không remote

Lời Sơn: *"Khởi tạo git local trong D:\MeetAI. Không tạo remote, không push. Dùng commit nhỏ để lưu artifact, review và rollback từng lát."*

### 5. Ngôn ngữ code vs docs

Lời Sơn: *"Identifier và code bằng tiếng Anh; tài liệu, ADR và nội dung hiển thị cho người dùng bằng tiếng Việt. Giữ UTF-8."*

Ngoại lệ thực tế: text in ra **terminal** dùng tiếng Việt không dấu, vì console codepage trên Windows không chắc là UTF-8 và sẽ hiện ký tự lỗi. Text trong web UI (slice S0.6) sẽ dùng tiếng Việt có dấu đầy đủ vì browser luôn đọc UTF-8.

## Phương án đã cân nhắc và loại

| Phương án | Lý do loại |
|---|---|
| TypeScript/Node toàn bộ | `discord.js` mạnh hơn, nhưng Phase 2 sẽ phải tách process Python cho model, thêm một ranh giới IPC phải tự bảo vệ (consent generation phải đi qua IPC) |
| Python core + Node cho Discord adapter | Ngay Phase 0 đã có 2 toolchain, 2 bộ lint/test, cho một nhu cầu chưa đo được |
| CLI/TUI thay web UI | Nhanh hơn ở Phase 0/1 nhưng hồ sơ yêu cầu hiển thị AI disclosure + consent rõ ràng; TUI sẽ phải làm lại |
| Dùng Python 3.14 có sẵn | Rủi ro wheel ML cao nhất, sẽ phải tạo lại venv ở Phase 2 |

## Khả năng đảo ngược

Cao khi ADR này được viết, thấp hơn bây giờ. Lúc đó code chỉ có `settings.py` + `cli.py`; hiện đã có 15 module trong `src/meetai/`. Tầng domain vẫn không phụ thuộc FastAPI — có test khẳng định (`TestDomainIndependence`). Nếu đổi stack thì mất khoảng một lát công việc. Đảo ngược sẽ đắt dần từ S1.3 (platform adapter) trở đi.
