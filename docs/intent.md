# MeetAI - ý định và phạm vi

**Việc của tài liệu này:** trả lời câu hỏi "cái này có thuộc phạm vi MeetAI không, và theo tiêu chuẩn nào thì coi là xong". Đây là tài liệu *sửa được* của repo, khác với hồ sơ bàn giao trong [docs/handoff/](handoff/) là bản sao đóng băng.

Không chứa trạng thái (xem [PROJECT_STATE.md](../PROJECT_STATE.md)), không chứa quy ước làm việc (xem [AGENTS.md](../AGENTS.md)), không chứa lý do kỹ thuật (xem [adr/](adr/)), không chứa danh sách nghĩa vụ (xem [spec.md](spec.md)).

---

## 1. Mục đích

MeetAI là trợ lý AI cá nhân, biết bối cảnh, có thể đại diện chủ dự án trong cuộc họp với **quyền hạn giới hạn**. Nó nói khi được gọi và khi có căn cứ; nó im lặng khi không.

Mục tiêu không phải là một trợ lý nói nhiều. Mục tiêu là một trợ lý mà **mỗi lần nó nói, lời đó đều có thể truy về một căn cứ đã được duyệt hoặc là kiến thức phổ thông**, và mỗi lần nó không chắc, nó im lặng thay vì đoán.

## 2. Ai dùng, và chạy ở đâu

Một người dùng. Máy của chính người đó. Ứng dụng **bật khi cần**, không phải một dịch vụ.

Hệ quả thiết kế, không phải chi tiết triển khai:

- Không có multi-tenant, không có phân quyền giữa người dùng, không có account system. Một người, một máy.
- Không có uptime. "Máy chủ riêng" trong hồ sơ **không** có nghĩa 24/7; nếu máy tắt thì MeetAI không họp.
- Không có cloud control plane. UI chỉ bind loopback.
- Không có hạ tầng để scale. `system-design-primer` là tài liệu tham khảo về trade-off, không phải bản vẽ cho ứng dụng này.

## 3. Những điều không thương lượng

Thứ tự này là thứ tự ưu tiên thật: khi hai điều xung đột, điều ở trên thắng.

1. **Một cổng bằng chứng đang mở, hoặc một quyết định đang chờ, thắng mọi yêu cầu tính năng.** Không tự đóng cổng, không tự chọn thay chủ dự án. Đây là nguyên tắc meta: nó quyết định cách xử lý mọi xung đột khác.
2. **MeetAI không bao giờ cam kết thay chủ dự án.** Không hứa hẹn, xác nhận thay, nhận việc, chốt deadline, bỏ phiếu, phê duyệt, tạo side effect. Đây là quyền hạn, không phải giọng điệu — nên không mức confidence nào và không lượng evidence nào mở được.
3. **Nội dung cuộc họp không ra khỏi máy.** Không gửi audio/transcript tới dịch vụ AI bên ngoài. Không upload lên cloud. Không telemetry.
4. **Không ghi âm, không lưu transcript mặc định.** Mọi loại lưu bền vững là opt-in riêng, sau một quyết định tường minh.
5. **Không học tự động từ hội thoại cuộc họp.** Không có đường từ transcript sang knowledge card.
6. **Không lách nền tảng.** Không self-bot, user token, sửa client, lách rate limit.
7. **Transcript là dữ liệu không tin cậy.** Lời người nói, kể cả khi tiêm chỉ thị, không cấp thêm quyền cho MeetAI.

Danh sách ràng buộc đã chốt từ chủ dự án nằm ở [PROJECT_STATE.md](../PROJECT_STATE.md) mục 3; không chép lại ở đây.

## 4. Ngoài phạm vi

MeetAI **không phải**:

- một dịch vụ chạy liên tục
- một sản phẩm transcription — nó không bán bản ghi, và mặc định không giữ bản ghi
- một trợ lý cloud
- một Discord self-bot
- một dự án huấn luyện foundation model (fine-tune LoRA/QLoRA model mở là hướng mong muốn; train từ đầu thì không)
- một nền tảng đa người dùng

**Parking lot** — đã xem xét, chưa chọn, không được dùng làm workaround: Discord Social SDK lobby. Nó là voice call với user token trong SDK lobby, **không phải** bot token trong guild voice. Chỉ xem xét lại sau một quyết định pivot sản phẩm rõ ràng.

**Nhánh nghiên cứu tùy chọn**, không phụ thuộc core và không có timeline: accessibility, multimodal, BCI. Không tuyên bố "đọc suy nghĩ"; nếu làm thì phải có task chủ động, hiển thị uncertainty, calibration, xác nhận và privacy gate.

## 5. Những điều KHÔNG phải yêu cầu đã chốt

Các giới hạn sau từng xuất hiện trong tài liệu nhưng **không truy được về phát ngôn trực tiếp của chủ dự án**:

- "dưới 10 giờ họp/tháng"
- "chỉ nhóm kín" — "máy chủ riêng" không có nghĩa là chỉ họp nhóm kín
- "MVP 2–4 tuần"
- "độ trễ 1–2 giây" — là **mục tiêu cần đo**, không phải SLA, và chỉ được báo là đạt nếu benchmark chứng minh

Giữ chúng ở trạng thái chưa chốt quan trọng vì một con số bị coi là ràng buộc sẽ bắt đầu định hình thiết kế: "1–2 giây" mà thành SLA sẽ biến thành lý do để bỏ qua một bước kiểm tra, và đó đúng là bước mà hồ sơ coi là quan trọng hơn độ trễ.

Câu trực tiếp cần giữ nguyên văn, không diễn dịch thành deadline: *"Cả hai nếu được. Trong 1 tuần"*.

## 6. Định nghĩa hoàn tất, phân theo cái gì đang chặn

Hồ sơ bàn giao mục 11 nêu tám tiêu chí nhưng không phân loại, và điều đó dễ bị đọc thành "cả tám đều bị chặn". Phân loại:

### Làm được ngay, không chờ gì

| Tiêu chí | Trạng thái |
|---|---|
| Không có unauthorized promise/commitment/approval trong evaluation suite; thiếu evidence thì abstain | **đạt trên corpus synthetic** — xem [eval v1](research/2026-10-07-authority-eval-v1.md). Chưa đo trên dữ liệu thật. |
| Không có raw audio/transcript persistence ngoài opt-in; deletion/retention được kiểm chứng | cascade đã có và có test; chưa có vault nào để xóa |
| Hiển thị AI disclosure, consent/status, capability offline, failures, kill switch | **đã có** (sửa ở lượt 19 — dòng này nói **thiếu** cả ba từ lượt ~6): `supervisor.py` có Start/Stop và `KillSwitch.engage`, `ui.py` có `POST /api/kill` và 7 route, `meetai serve` chạy UI. **Còn thiếu:** UI chưa hiển thị answerability/retrieval, và chưa có sink nào để hiển thị một lần phát thật. |

### Chờ cổng bằng chứng Discord (0-S / 0-P / 0-C)

| Tiêu chí | Vì sao chặn |
|---|---|
| Nguồn/ticket chính thức đủ cụ thể cho platform route, account type, audio receive, mapping, version, review requirements | Discord chưa trả lời; không tự suy ra từ protocol chung |
| Consent state machine + late join/revoke có test/replay evidence **trên pipeline cụ thể** | FSM và replay đã có trên fake adapter; "pipeline cụ thể" cần một đường audio thật |
| Test channel/pilot có giới hạn và participant consent | cần một cuộc họp thật |

### Chờ quyết định của chủ dự án (0-U)

| Tiêu chí | Quyết định đang thiếu |
|---|---|
| Direct-address classifier không nói chỉ vì alias bị nhắc ngôi ba; **chất lượng đo trên Vietnamese test set** | classifier chưa xây (S1.7); corpus đã có nhưng alias thật thì chưa |

### Chờ benchmark Phase 2

| Tiêu chí | Vì sao |
|---|---|
| Đo p50/p95, tài nguyên, thermal, chi phí trên máy thật; độ trễ 1–2 giây chỉ báo đạt nếu benchmark chứng minh | chưa cài gói ML nào |

## 7. Những thất bại dự án này chấp nhận

Nêu ở đây vì chúng là **ý định**, và chính chúng cho phép các lựa chọn kỹ thuật trong ADR và trong `authority.py`.

**Im lặng thắng chen ngang sai.** Một lần MeetAI đáng nói mà không nói là một bất tiện. Một lần nó nói sai trong cuộc họp là một thiệt hại cho uy tín của chủ dự án. Hai cái không cùng độ lớn.

**Một lần từ chối oan thắng một lần cam kết trái phép.** Hệ quả: lexicon chặn commissive được viết **thiên về từ chối**, và eval báo false-allow và false-block **riêng** chứ không gộp — một con số trung bình sẽ coi một thiệt hại ngang với một bất tiện.

**Một cổng đóng thắng một tính năng chạy được.** Khi consent chưa quyết, MeetAI không họp. Điều đó trông như một tính năng chưa xong, và đó là trạng thái đúng.

**Một lỗ đã biết thắng một lỗ đã che.** Giới hạn của lexicon được ghi thành test với ceiling chỉ giảm, chứ không được vá từng câu cho đến khi số liệu đẹp. Một lỗ nằm trong suite thì có người đọc; một lỗ bị vá bằng literal thì không ai biết lớp lỗi vẫn còn đó.
