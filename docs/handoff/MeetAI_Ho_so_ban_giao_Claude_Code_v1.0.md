---
title: "MeetAI - Hồ sơ bàn giao để bắt đầu xây dựng"
version: "1.0"
date: "2026-10-07"
language: "vi"
status: "Tổng hợp baseline thiết kế đến vòng 18; các lựa chọn sản phẩm còn mở được đánh dấu riêng"
source_baseline: "MeetAI v0.6.15 + System Design v0.6.7 + kế hoạch chiến lược dài hạn"
---

# MeetAI - Hồ sơ bàn giao để bắt đầu xây dựng

**Mục đích:** đưa toàn bộ bối cảnh sản phẩm, baseline kiến trúc, giới hạn, quyết định còn mở và thứ tự triển khai sang Claude Code. Đây là hồ sơ bàn giao kỹ thuật; không phải khẳng định rằng đường nhận âm thanh Discord đã được hỗ trợ hay kiểm chứng.

## 0. Chỉ dẫn đọc và trạng thái quyết định

Tài liệu phân biệt bốn loại thông tin:

- **Đã nói trực tiếp:** yêu cầu người dùng có trong hội thoại.
- **Hội tụ thiết kế:** khuyến nghị kỹ thuật được các vòng phản biện đồng tình; vẫn chưa đồng nghĩa người dùng đã chọn mọi chi tiết.
- **Đề xuất mặc định an toàn:** dùng để thiết kế và scaffold cho tới khi có quyết định khác; không tự coi là quyết định người dùng.
- **Cổng chưa đóng:** cần người dùng, Discord hoặc prototype cung cấp bằng chứng trước khi bật tính năng tương ứng.

Không tự nâng bất kỳ quyết định AI nào thành quyết định của Sơn. Các giới hạn từng xuất hiện trong tài liệu nhưng chưa truy được về lời trực tiếp của Sơn - ví dụ “dưới 10 giờ họp/tháng”, “chỉ nhóm kín”, “MVP 2–4 tuần” - không phải yêu cầu đã chốt. Giữ nguyên câu trực tiếp “Cả hai nếu được. Trong 1 tuần” nếu cần tham chiếu, không diễn dịch thành thời hạn MVP. “Máy chủ riêng” không có nghĩa là chỉ họp nhóm kín.

## 1. Tóm tắt sản phẩm

MeetAI là trợ lý AI cá nhân, biết bối cảnh và có thể đại diện Sơn trong cuộc họp với quyền hạn giới hạn. MVP ưu tiên Discord, tiếng Việt, lịch Google Calendar và trải nghiệm desktop bật/tắt theo nhu cầu. Bot dùng danh tính bot riêng, tên hiển thị theo tên Sơn, tự giới thiệu là trợ lý AI; không cần avatar giống Sơn. Có thể tự trả lời khi ngữ cảnh đủ rõ, chủ động nêu quan điểm có căn cứ, nhưng tuyệt đối không hứa hẹn, xác nhận, nhận việc, chốt deadline, bỏ phiếu hay phê duyệt thay Sơn.

Thiết kế hướng tới xử lý nội dung cuộc họp cục bộ. Mặc định không chủ đích lưu raw audio, transcript hay reply journal. Dữ liệu có thể đi qua RAM trong phiên. Các loại lưu trữ bền vững, thời hạn lưu, lưu ghi chú và lịch sử trả lời vẫn cần Sơn chọn. Không dùng nội dung cuộc họp để huấn luyện. Không gửi audio/transcript tới dịch vụ AI bên ngoài trong MVP.

**MVP không được mô tả là hoàn chỉnh** cho tới khi xác minh được đường nhận audio inbound của standard Discord bot trong guild voice, ánh xạ người nói, chính sách Discord hiện hành và consent gate an toàn. Có thể bắt đầu xây phần độc lập với Discord để kiểm chứng policy/data lifecycle trước.

## 2. Yêu cầu sản phẩm đã nói trực tiếp

| Chủ đề | Yêu cầu trực tiếp / phạm vi đã nêu |
|---|---|
| Tên | Dự án tên MeetAI. |
| Nền tảng đầu tiên | Discord; có thể mở rộng nghiên cứu sang Google Meet, Zoom và nền tảng khác về sau. |
| Lịch | Google Calendar. Link Discord nằm trong Location hoặc Description của sự kiện. |
| Kích hoạt | Mở ứng dụng trên máy tính trước khi cần; không cần chạy dịch vụ liên tục. Có thể bật/tắt model khi cần. Máy tính phải bật, app/mạng/model sẵn sàng để bot thực hiện lịch. |
| Trả lời | Có thể tự trả lời. Nếu tên Sơn được nhắc, phản hồi khi đúng ngữ cảnh; tự chủ theo bối cảnh và có thể nêu quan điểm như một “tôi thứ hai”. |
| Quyền hạn | Không hứa hẹn hay chốt thay Sơn. |
| Danh tính | Dùng tên Sơn nhưng không cần diện mạo giống; tự công khai là trợ lý AI. |
| Ghi âm | Mặc định không ghi âm/lưu âm thanh cuộc họp. Trường hợp ngoại lệ phải thông báo rõ; transcript/notes persistence chưa được chọn. |
| Mô hình | Muốn tự xây hệ thống, dùng model mở/self-host; không huấn luyện foundation model từ đầu. Fine-tune model mở và RAG là hướng mong muốn khi có dữ liệu phù hợp. |
| Ngôn ngữ | Tiếng Việt. |
| Phần cứng | Windows 11, i7-9750H, RAM 16 GB, GTX 1660 Ti 6 GB. Máy không đủ khỏe cho pipeline model đồng thời nặng. Có thể cân nhắc Google Colab Pro L4 22.5 GB VRAM cho thử nghiệm; upload dữ liệu lên Colab là xử lý cloud và cần quyết định riêng. |
| Chi phí | Mục tiêu khoảng 500.000 VND/tháng nếu khả thi; phải tính điện, lưu trữ, mạng và thuê GPU. Chưa có estimate được xác nhận. |
| Triển khai | Máy chủ riêng / máy của người dùng; không đồng nghĩa với 24/7. |
| Thử nghiệm | Người dùng có thể tạo channel Discord riêng để thử. |

## 3. Kiến trúc mục tiêu

```text
Google Calendar (read-only, khi desktop app đang chạy)
                 │ event + Discord URL
                 ▼
Desktop Supervisor ── UI, Start/Stop, health, consent, logs không chứa nội dung
   ├── Meeting Planner / allowlist / join window / idempotency
   ├── Platform Adapter: Discord (send/receive tách biệt; receive còn là cổng chặn)
   ├── Session & Consent Gate: fail-closed theo session/người/scope
   ├── Media Pipeline: jitter/frames → VAD/endpointing → ASR tiếng Việt
   ├── Context & Knowledge: lượt thoại gần nhất + cards đã duyệt (RAG tùy chọn)
   ├── Response Policy: evidence + quyền hạn + abstain/ask/speak
   ├── Local Model Runtime: ASR / LLM / embeddings / TTS qua interfaces
   └── Local Data Vault: metadata, consent receipts, knowledge cards; persistence opt-in
```

### Thành phần và trách nhiệm

1. **Desktop Supervisor:** khởi động/dừng, hiển thị trạng thái, quản lý model on/off, health checks, kill switch và lý do không thể tham gia. Không join âm thầm khi model/consent/audio không sẵn.
2. **Calendar connector:** OAuth quyền đọc hẹp nhất; đồng bộ incremental/polling khi app chạy; chỉ lấy metadata sự kiện cần thiết. Không gửi toàn bộ lịch vào LLM. Xử lý token invalid, full resync và event thay đổi/hủy.
3. **Meeting planner:** timezone `Asia/Ho_Chi_Minh`; chỉ chấp nhận URL/domain/channel rõ ràng và allowlisted; join window cấu hình được; idempotent; không tự join event cũ sau restart.
4. **Platform adapter:** interface chuẩn hóa `join`, `leave`, `participant events`, `audio frames`, `send text/audio`, `health`. Tách control plane, outbound và inbound capability. Mỗi adapter khai báo capability/version/evidence; fake adapter không được báo là Discord integration.
5. **Consent/media gate:** gắn mọi buffer/job với session, speaker, scope và generation. Unknown/unmapped/stale/revoked bị loại trước ASR. Khi consent thu hồi: đóng gate trước await, cancel job, purge context theo scope, ngắt hoặc ngừng xử lý theo policy.
6. **ASR/context/model:** stream/chunk pipeline có backpressure, bounded queue, timeout/cancel. Không giữ pipeline heavyweight đồng thời trên 6 GB VRAM trước khi benchmark chứng minh được. Không AI cloud failover.
7. **Response policy:** phân biệt gọi trực tiếp, nhắc ngôi thứ ba và từ khóa trùng alias; truy xuất tri thức chỉ khi câu hỏi cần thông tin riêng về Sơn; tạo output có schema; validator xác thực evidence và quyền trước khi phát.
8. **Local data vault:** phân namespace/retention; mã hóa bí mật và nội dung nhạy cảm; log chỉ metadata; xóa theo phạm vi và version; không tự học từ transcript.

## 4. Các cổng bằng chứng Discord - không được bỏ qua

Vòng 18 xác nhận rằng tài liệu Voice Connections nói tới UDP receive và DAVE frames sent/received ở mức protocol; ví dụ Speaking update có SSRC nhưng chưa chứng minh mapping SSRC sang guild user. Social SDK có `UserAudioReceivedCallback` gồm `userId` và mẫu PCM int16 nhưng là voice call trong SDK lobby, không phải bot token nhận guild voice. Linked channels là text. Social SDK có rate limit khi development/testing; full-release access cần review và yêu cầu tích hợp hướng game/social. Vì vậy Social SDK chỉ là parking lot, không phải workaround MVP.

| Gate | Cần chứng minh | Không đạt thì |
|---|---|---|
| 0-S: kỹ thuật + phạm vi nền tảng | Standard bot account/token, guild voice hiện hữu, inbound audio/PCM, participant mapping, API/SDK/version và quyền cần thiết được Discord xác nhận/được tài liệu hóa. | Không bật live receive; giữ adapter interface, demo synthetic và báo block rõ. |
| 0-P: supported route + policy | Trace tái lập theo route được hỗ trợ; rà Developer Terms/Policy ở ngày triển khai; xác định review/approval. Ticket hỗ trợ không thay policy hoặc consent. | Không coi ticket trả lời chung là cho phép; unresolved vẫn là blocker. |
| 0-C: consent/media safety | Thứ tự packet/decrypt/PCM/ASR được quan sát trên build cụ thể; late join, reconnect, SSRC remap, revoke race và cancellation được kiểm tra. Không tuyên bố zero packet/decrypt tuyệt đối nếu chưa chứng minh. | Fail closed; không chuyển audio chưa consent vào ASR/LLM/TTS. |
| 0-U: người dùng chọn policy | Chọn consent mode, saved notes/transcript, reply journal, receipt retention, wording về persistence tầng ứng dụng. | Không bật lưu nội dung; giữ trạng thái pending decision. |

Không chạy thử với self-bot, user token, sửa client, hay người tham gia bên thứ ba không đồng thuận. Câu hỏi Discord ở vòng 18 là bản nháp chưa gửi.

## 5. Consent, lifecycle và riêng tư

Consent phải được quản lý theo `(session_id, user_id, scope, notice_version)`; không kế thừa sang phiên mới. Scope cần tách ít nhất: nhận/xử lý live media, tạo transcript/notes bền vững, lưu reply journal, debug raw audio. Consent receipt nên chứa metadata/timestamp/policy version, không audio.

**State gợi ý:** `UNKNOWN → ANNOUNCED → CONSENTED` hoặc `DECLINED/EXPIRED`; consent đã cấp có thể thành `REVOKED`. Declined/revoked/expired là terminal trong phiên; stale click không bật lại. Tăng generation khi revoke; mọi async task kiểm generation ngay trước xử lý/phát. Không gửi partial ASR để tự kích lời nói. Buffer và queue có TTL/size bound.

**Late join:** hai thiết kế A1 circuit-breaker (đóng media gate, hủy pipeline, purge state và rời/tắt reconnect khi người mới chưa consent) và A3 host-controlled admission (chỉ bắt đầu sau kiểm soát admission) vẫn là lựa chọn Sơn chưa chốt. Thiết kế module để hỗ trợ, nhưng default fail-closed; không chọn A1/A3 thay người dùng.

**Lưu trữ mặc định triển khai:** nội dung phiên ephemeral; không ghi raw audio, transcript, notes hoặc bot reply bền vững cho tới khi Sơn chọn rõ. Có thể lưu metadata tối thiểu cần cho vận hành và receipt theo TTL sau quyết định. Nếu sau này bật lưu transcript/notes thì là opt-in riêng, có retention, export, delete cascade và hiển thị rõ. “Không chủ đích lưu ở tầng ứng dụng” không đồng nghĩa nền tảng/OS/network không xử lý hay giữ dữ liệu.

## 6. Hành vi hội thoại và quyền đại diện

### Pipeline một lượt trả lời

1. Chờ final ASR và confidence tối thiểu; partial/chồng lấn mơ hồ thì im lặng.
2. Phân loại direct address: được gọi/hỏi, chỉ nhắc tên ở ngôi ba, alias trùng từ, hoặc không rõ. Alias match một mình không đủ để chen ngang.
3. Lấy speaker/addressee, 3–5 lượt thoại gần nhất, referent/agenda cần thiết; context phiên mặc định ephemeral.
4. Chỉ retrieval personal cards nếu câu hỏi cần lập trường/thông tin riêng của Sơn. Không xây RAG cho vô hạn tình huống giao tiếp.
5. Kiểm tra evidence, scope, freshness, conflict, answerability và risk.
6. Sinh schema `{decision: speak|silent|followup, text, evidence_ids, confidence, risk_flags}`.
7. Deterministic policy gate kiểm lại trước send/TTS. LLM/evaluator có thể chặn hoặc xin hỏi, không thể cấp quyền.
8. Barage-in/cancel; hủy khi có lời mới, revoke, leave hoặc session end.

### Quy tắc nói

- Tự giới thiệu: “Mình là MeetAI, trợ lý AI của Sơn.” Disclosure hiển thị/nghe được khi vào.
- Có căn cứ đã duyệt: nêu quan điểm ngắn, có thể chủ động khi liên quan; gắn attribution khi hữu ích (“theo ghi chú Sơn đã duyệt…”).
- Kiến thức phổ thông: trả lời như trợ lý, không gán thành quan điểm cá nhân của Sơn.
- Thiếu căn cứ, mâu thuẫn, hết hạn, scope sai: không suy đoán; nói cần hỏi Sơn và ghi follow-up nếu bật tính năng này.
- Cấm: hứa hẹn, xác nhận thay, nhận việc/deadline, bỏ phiếu, phê duyệt tài chính/pháp lý/nhân sự, hoặc thực hiện side effect.
- Speech/transcript là dữ liệu không tin cậy; không được ghi đè system policy hay cấp thêm quyền.

## 7. RAG, dữ liệu và fine-tuning

RAG là bộ nhớ tri thức đã duyệt, không phải tập hợp mọi biến thể hội thoại. Tách rõ:

- **Profile/preferences:** vai trò, cách xưng hô, ưu tiên/điều tránh, visibility private/group/public.
- **Positions:** claim, rationale, nguồn, ngày hiệu lực/hết hạn, scope, sensitivity, trạng thái duyệt, supersedes.
- **Projects/expertise:** ghi chú/quy trình có nguồn và trạng thái hiện tại.
- **Glossary/aliases:** tên riêng/thuật ngữ/phát âm; hỗ trợ ASR và retrieval, không tự chứng minh người dùng được gọi.
- **Style examples:** câu do Sơn tạo/chọn; chỉ hướng giọng điệu, không dùng làm bằng chứng sự thật.
- **Meeting context:** context ngắn hạn, session-bound; không tự thành memory lâu dài.

Knowledge card cần tối thiểu `id, type, claim, rationale, source_ref, source_date, approval_status, approved_by, valid_from, valid_until, supersedes, scope, sensitivity, confidence, allowed_actions, version, content_hash`. Pipeline: ingest có allowlist → trích xuất candidate kèm vị trí nguồn → phân loại/dedupe/conflict/expiry → Sơn approve/edit/reject → index approved only → sửa/xóa cascade qua chunks, embeddings, cache. Candidate/pending tuyệt đối không retrieve như fact đã duyệt.

Bắt đầu bằng metadata + exact/lexical retrieval; thêm embeddings đa ngôn ngữ chỉ nếu benchmark cho thấy cải thiện trên bộ eval do Sơn kiểm soát. Không ingest toàn bộ account/repo/mailbox/calendar. Nguồn phải do Sơn tạo hoặc có quyền sử dụng. Không học trực tiếp từ meeting transcript.

**Fine-tuning:** sau khi có corpus tự tạo/được cấp quyền và eval split; LoRA/QLoRA chỉ để dạy style/format/refusal, không thay RAG cho facts cập nhật. Manifest license/consent/model hash, train/validation/test tách riêng, rollback. Nội dung Discord API không đưa vào AI training khi chưa có permission rõ theo Developer Policy. Colab là cloud; chỉ thử bằng dữ liệu synthetic/public có license trừ khi Sơn quyết định riêng việc upload dữ liệu cụ thể.

## 8. Model/runtime và chỉ tiêu

- ASR tiếng Việt, LLM nhỏ lượng tử hóa, embeddings, TTS đều là **ứng viên cần benchmark**, không phải lựa chọn đã chốt.
- GTX 1660 Ti 6 GB + RAM 16 GB: model manager serialize workload, bounded queue, unload/preload, cancellation; không mặc định ASR + LLM + TTS đồng thời resident.
- Tắt model thì không join/không giả vờ nghe và trả lời; UI báo rõ capability offline.
- 1–2 giây là mục tiêu thử nghiệm, không SLA. Ưu tiên đúng, grounded, không chen ngang hơn độ trễ.
- Benchmark p50/p95 endpoint-to-final-ASR, LLM first token, TTS first audio, end-to-end; WER/CER theo tiếng Việt/accent/noise/nói chồng/tên riêng; RTF, VRAM/RAM peak, CPU, thermal, idle/active watts và chi phí tháng.
- Giọng clone chỉ thử khi chất lượng/độ trễ/chi phí/license/privacy đạt và Sơn duyệt; nếu không dùng text hoặc voice preset miễn phí tự host. Không phải MVP dependency.
- Kiến trúc không khóa model engine, ASR, vector DB hay Discord library trước benchmark và Gate 0.

## 9. Roadmap xây dựng

### Phase 0 - Repo reconnaissance và khung local

Claude Code đọc repo, `AGENTS.md`, toolchain, secrets/config hiện có trước khi sửa. Không áp đặt framework nếu repo đã có. Tạo kiến trúc module/interfaces, settings validation, structured metadata-only logging, health/status UI/CLI, Start/Stop, model on/off mock, secret handling. Chưa kết nối live Discord voice.

### Phase 1 - Core safety (H0-F)

Triển khai consent FSM + revoke generation, session lifecycle, meeting planner trên fixture, policy gate, answer schema, evidence IDs, knowledge-card state machine, deletion/retention abstraction, fake platform adapter và synthetic replay harness. Tạo đánh giá red-team cho direct address, third-person mention, no evidence, conflict/expiry, prompt injection, unauthorized promises, revoke race và late join. Không log nội dung/audio. Đây là phần có thể làm trước khi Discord giải quyết Gate 0-P.

### Phase 2 - Local model feasibility (H0-M)

Benchmark ASR/LLM tuần tự trên GTX/CPU bằng dữ liệu synthetic/public được cấp phép. Model artifacts tách khỏi app; pin version/hash/license. Đo chất lượng/latency/memory/thermal/cost. Colab benchmark là tùy chọn, dữ liệu họp/giọng Sơn không upload mặc định.

### Phase 3 - Discord proof (H0-P)

Chỉ sau khi có evidence từ Discord/support/docs về standard bot account + guild voice + inbound audio + mapping + approval. Tạo test server/channel riêng, adapter sau capability boundary, first metadata-only voice trace; sau đó synthetic tone/audio do chính Sơn kiểm soát; sau cùng consent-gated end-to-end. Lưu test manifest/build/version và kết quả, không raw audio mặc định. Không tuyên bố production-ready từ một trace.

### Phase 4 - Vertical slice có consent

Calendar event test → app preflight → disclosure/consent → join route đã được xác nhận → audio gate → ASR → mention/direct-address → grounded safe answer → text response trước, TTS là lựa chọn sau → leave/purge. Nếu receive route chưa được supported, phase dừng ở mock/synthetic adapter; không lén thay bằng self-bot/client automation.

### Phase 5 - Pilot rồi mới mở rộng

Pilot trong channel Sơn kiểm soát; đo false activation/false reply/abstain, consent errors, grounding, correction burden, p50/p95, failure/reconnect, storage deletion. Sửa trước khi thêm transcript persistence, voice cloning, chủ động đa kênh hoặc Google Meet/Zoom.

### Hướng xa hạn

H1: lõi knowledge/policy qua nhiều adapter có API/consent phù hợp. H2: chủ động chuẩn bị brief/reminder/draft và hành động reversible có duyệt. H3/H4: accessibility/multimodal/BCI chỉ là nhánh nghiên cứu tùy chọn, không phụ thuộc core; không tuyên bố “đọc suy nghĩ”, cần task chủ động, uncertainty hiển thị, calibration, xác nhận và privacy gate. Không đặt timeline theo năm nếu chưa có evidence.

## 10. Quyết định còn chờ Sơn

Không chặn scaffold an toàn; phải chặn bật chức năng liên quan cho tới khi được trả lời:

1. Consent policy: từng người tự đồng ý hay host điều phối? Late join A1 circuit-breaker hay A3 admission control? Host không được ghi đè opt-out của participant.
2. Disclosure và handling nếu participant từ chối/không phản hồi: MeetAI rời ngay hay session dừng? (Đề xuất an toàn: fail closed; exact UX do Sơn chọn.)
3. Có lưu transcript/meeting notes không? Nếu có: scope, TTL, vị trí, export/delete.
4. Có lưu reply journal không? Mặc định đề xuất off.
5. Retention consent receipts và metadata vận hành.
6. Có chấp nhận câu công khai “MeetAI không chủ đích lưu ở tầng ứng dụng” với giới hạn chính xác không?
7. Có benchmark Colab không? Có upload voice sample của Sơn lên cloud hay không là quyết định tách biệt.
8. Có gửi draft câu hỏi Discord không? Chưa gửi.
9. Gate 0: nếu Discord không xác nhận supported guild receive thì có dừng Discord voice MVP, hay xem xét đổi sản phẩm sang Social SDK lobby? H0-ALT hiện là parking lot và chỉ dùng sau product pivot rõ.

## 11. Định nghĩa hoàn tất cho MVP

Không tính là xong chỉ vì bot join được hoặc demo nói được. Cần đạt và lưu evidence:

- Có nguồn/ticket chính thức đủ cụ thể cho platform route, account type, audio receive, mapping, version và review requirements; rà policy/terms riêng.
- Consent state machine và late join/revoke handling có test/replay evidence trên pipeline cụ thể; không tuyên bố phổ quát hơn phạm vi thử nghiệm.
- Không có unauthorized promise/commitment/approval trong evaluation suite; thiếu evidence thì abstain/follow-up.
- Direct-address classifier không nói chỉ vì alias bị nhắc ở ngôi thứ ba; chất lượng đo trên Vietnamese test set.
- Không có raw audio/transcript persistence ngoài opt-in đã chọn; deletion/retention được kiểm chứng.
- Hiển thị AI disclosure, consent/status, capability offline, failures và kill switch.
- Đo p50/p95, tài nguyên, thermal và chi phí trên máy thật; độ trễ mục tiêu 1–2 giây chỉ được báo đạt nếu benchmark chứng minh.
- Test channel/pilot được giới hạn và có participant consent.

## 12. Nguồn tham khảo đã dùng trong các vòng

- [Discord Voice Connections](https://docs.discord.com/developers/topics/voice-connections)
- [Discord Social SDK - Managing Voice Chat](https://docs.discord.com/developers/discord-social-sdk/development-guides/managing-voice-chat)
- [Discord Social SDK - Communication Features](https://docs.discord.com/developers/discord-social-sdk/core-concepts/communication-features)
- [Discord Social SDK - Managing Lobbies](https://docs.discord.com/developers/discord-social-sdk/development-guides/managing-lobbies)
- [Discord Developer Policy](https://support-dev.discord.com/hc/en-us/articles/8563934450327-Discord-Developer-Policy)
- [Google Calendar API - OAuth scopes](https://developers.google.com/workspace/calendar/api/auth)
- [Google Calendar API - Incremental synchronization](https://developers.google.com/workspace/calendar/api/guides/sync)
- [Google Calendar API - Push notifications](https://developers.google.com/workspace/calendar/api/guides/push)
- [Google Colab FAQ](https://research.google.com/colaboratory/faq.html)
- Model/research sources in strategy doc are candidates, not frozen choices; re-check versions, licenses and hardware before implementation.

## 13. Prompt khởi động cho Claude Code

```text
Đọc toàn bộ tài liệu MeetAI_Ho_so_ban_giao_Claude_Code_v1.0.md trước khi sửa code. Đây là source of truth tổng hợp đến vòng 18; phân biệt yêu cầu người dùng đã nói trực tiếp, đề xuất kỹ thuật và quyết định còn mở. Không tự coi khuyến nghị là quyết định của Sơn.

Trước tiên, khảo sát repository hiện tại, AGENTS.md, toolchain, cấu trúc, trạng thái git và secrets/config mà không in giá trị bí mật. Báo ngắn gọn kiến trúc repo hiện có, xung đột với hồ sơ này, các lựa chọn cần hỏi và kế hoạch theo Phase 0/1. Không thay framework hoặc tạo cấu trúc trùng lặp nếu repo đã có chuẩn.

Chỉ bắt đầu phần không phụ thuộc Discord: desktop supervisor khung, interface platform adapter + fake adapter, session/consent state machine fail-closed, revoke generation/cancellation, policy gate, structured response schema, knowledge-card approval model và synthetic replay/evaluation harness. Không triển khai live Discord voice receive, self-bot, user-token automation, client modification, meeting recording/persistence hay cloud AI. Không ingest dữ liệu cá nhân hoặc upload lên Colab. Không chọn model/vendor/license chưa benchmark.

Giữ raw audio/transcript/reply journal persistence off. Log chỉ metadata, không nội dung hội thoại, tokens hay audio. UI phải thể hiện rõ model/platform offline và không giả vờ đã nghe. Mọi lời hứa/chốt/nhận việc/approve/vote phải bị deterministic policy gate chặn độc lập với LLM. Với các quyết định consent/retention chưa chốt, scaffold configurable nhưng mặc định fail-closed và không tự chọn chính sách thay Sơn.

Làm theo từng lát nhỏ. Sau khảo sát, trình bày kế hoạch và các file dự kiến sửa; triển khai Phase 0/1 theo conventions của repo, cập nhật tài liệu kiến trúc và nêu rõ bằng chứng nào là synthetic/mock. Không gọi test suite hoặc thực hiện thay đổi ngoài yêu cầu mà chưa được giao; trước khi dừng, tóm tắt thay đổi, lệnh kiểm tra đã chạy (nếu có), giới hạn và blocker. Các Phase Discord/live chỉ bắt đầu khi Gate 0-P/0-S có bằng chứng và Sơn giao tiếp tục.
```

## 14. Lịch sử nguồn tổng hợp

Hồ sơ này tổng hợp system design v0.6.7, chiến lược dài hạn, các bản phản hồi vòng 12–18 và các lựa chọn trực tiếp của Sơn trong hội thoại. Vòng 18 là điểm dừng trao đổi AI hiện tại; chỉ mở lại phản biện khi có trả lời Discord, prototype/evaluation evidence, quyết định mới của Sơn hoặc nguồn chính thức mới. Tài liệu này không thay lời chấp thuận của participant, Discord, đánh giá pháp lý hay nghiệm thu prototype.

