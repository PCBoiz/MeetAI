---
title: "MeetAI System Design v0.6.7 hop nhat"
source_pdf: "MeetAI_System_Design_v0.6.7_hop_nhat.pdf"
language: vi
conversion: PDF text extraction; recurring headers and footers removed
note: "System design hợp nhất v0.6.7."
---

# MeetAI System Design v0.6.7 hop nhat

> Nguồn: `MeetAI_System_Design_v0.6.7_hop_nhat.pdf`. System design hợp nhất v0.6.7.

System design hợp nhất v0.6.7 Discord trước · local-first · tiếng Việt · trợ lý đại diện có giới hạn

## Mục đích tài liệu Hợp nhất các nội dung Luna và Claude đã trao đổi đến vòng 10: yêu cầu, kiến trúc, ranh giới quyền phát ngôn, consent, media, RAG, lưu trữ, mô hình, vận hành và cổng prototype. Đây là thiết kế để tiếp tục góp ý và mang sang Claude Code sau khi người dùng chốt; không khẳng định Discord voice receive/DAVE hoặc crypto-erasure đã chạy thành công.

## Trạng thái đồng thuận Hai bên hiện không còn bất đồng kiến trúc lớn. v0.6.7 được xem là baseline thiết kế có điều kiện. Ba lựa chọn sản phẩm vẫn thuộc Son: policy consent/late entrant, bật reply journal hay không, và retention. Prototype còn phải chứng minh voice pipeline, consent gate, model feasibility và thao tác xóa.

## Nguyên tắc thiết kế

• Chỉ dùng bot account Discord; không tự động hóa tài khoản người dùng. Dùng tên Son nhưng tự giới thiệu rõ là trợ lý AI.

• MVP chạy khi desktop app được mở; inference AI trong cuộc họp chạy local, không chuyển audio/transcript tới API AI ngoài.

• Không lưu raw audio trong vận hành bình thường; tách consent cho live processing, saved notes/transcript, bot reply journal và debug audio.

• Phát ngôn bám bằng chứng đã duyệt; thiếu căn cứ thì hỏi Son, ghi follow-up, không hứa/chốt/nhận việc thay.

• RAG lưu hiểu biết riêng về Son, không xây vector database cho mọi tình huống giao tiếp.

## 1. Mục tiêu, phạm vi và quyết định đã thống nhất Chủ đề Thiết kế hợp nhất Tên MeetAI. Nền tảng MVP Discord voice, trong server/channel thử nghiệm do Son kiểm soát; tạo riêng một channel để thử. Nền tảng tương lai Adapter architecture để có thể nghiên cứu Google Meet, Zoom và nền tảng khác sau; không hứa parity API/voice. Lịch Google Calendar. URL Discord trong Location hoặc Description. OAuth read-only, quyền hẹp nhất phù hợp; khi app mở mới đồng bộ/lập lịch. Kích hoạt Người dùng mở desktop app và có thể bật/tắt model khi cần. Không chạy service 24/7, không VPS để đánh thức PC; PC phải thức, app online, mạng/model sẵn sàng.

## Vai trò Một ‘tôi thứ hai’ có thể nêu quan điểm chủ động khi có căn cứ, nhận ra khi Son được gọi/hỏi, phản hồi tự động trong giới hạn policy. Danh tính hiển thị Tên của Son, không cần avatar giống Son; bot giới thiệu là AI. Giọng clone chỉ thử nếu chất lượng/trễ/chi phí hợp lý; nếu không dùng voice preset miễn phí hoặc text. Ngôn ngữ Tiếng Việt là ưu tiên; xử lý tên riêng, nhiều accent, nói chồng và thuật ngữ nội bộ trong đánh giá. Hạ tầng hiện có Windows 11, i7-9750H, RAM 16 GB, NVIDIA GTX 1660 Ti 6 GB VRAM; máy yếu cho pipeline đồng thời.

## Mục tiêu Độ trễ 1–2 giây là stretch goal cần đo; khoảng 500.000 VND/tháng là ngân sách mục tiêu cần tính điện, GPU, storage, mạng.

## Không thuộc MVP Huấn luyện foundation model từ đầu; tự động biểu quyết/duyệt/cam kết; avatar/video; speaker identification sinh trắc học; nhiều nền tảng cùng lúc; AI cloud fallback trong họp; tự học trực tiếp từ transcript Discord; nói như người thật mà che giấu danh tính AI.

## 2. Kiến trúc logic và luồng hệ thống Một desktop supervisor điều phối connector và policy; thành phần audio/model được cách ly sau interfaces để thay library/model mà không kéo logic sản phẩm vào Discord SDK. Khối Trách nhiệm / hợp đồng Desktop supervisor UI trạng thái Calendar/Discord/model/storage/consent; Start/Stop/Pause/Leave/Delete; quản lý model on/off; không join nếu health gate fail. Calendar connector OAuth read-only; initial + incremental sync; chỉ giữ metadata sự kiện cần join; parse location/description và xác thực domain/channel. Meeting planner Timezone Asia/Ho_Chi_Minh; resolve guild/channel; allowlist; join window configurable; idempotency; xử lý event đổi/hủy; không join event quá hạn sau restart. Discord adapter Bot application account; Gateway/voice; DAVE; participant/SSRC map; send/receive tách riêng; consent admission; reconnect/epoch health. Media + consent gate Speaker-specific frame path; unknown/unmapped/revoked drop; bounded RAM; VAD/endpointing/ASR; metadata-only telemetry. Inference runtime Local ASR, LLM, embedding, TTS behind model adapters; one heavyweight GPU workload at a time until benchmark; queue/cancel/timeout; no AI cloud failover. Conversation policy Direct-address/mention classifier, context builder, evidence retrieval, answerability and hard action rules; structured response then validate before output. Local data vault Consent receipts, meeting RAM state/optional saved notes, output journal, approved knowledge cards; encrypted sensitive data; per-scope TTL/delete. Luồng cuộc họp Google Calendar event → xác thực link/channel và meeting allowlist → health/consent preflight → bot account join + AI/consent disclosure → map participant/SSRC → gated audio stream → VAD/ASR → direct-address/intent gate → context + approved knowledge → grounded draft → policy validator → text/TTS response or abstain → follow-up/reminder/store according to selected mode → stop/purge/leave. Ranh giới dữ liệu Audio/transcript hội thoại không gửi ra API AI ngoài. Google Calendar chỉ cung cấp lịch/link/brief cần thiết; không đưa toàn bộ calendar vào LLM. Model package/download và Calendar/Discord control plane là kết nối mạng riêng, không phải AI inference bên ngoài.

## 3. Lịch, join flow và consent Calendar behavior

• Dùng narrowest OAuth read-only scope phù hợp. Chọn polling/incremental sync khi desktop app chạy để không cần public webhook host; Google push notifications cần HTTPS callback và subscription renew nên không phải MVP default. Sync token hết hạn → full resync. [Google Calendar scopes](https://developers.google.com/workspace/calendar/api/auth), [incremental sync](https://developers.google.com/workspace/calendar/api/guides/sync), [push notifications](https://developers.google.com/workspace/calendar/api/guides/push).

• Join chỉ khi event có URL Discord hợp lệ/guild-channel allowlist và trong join window; link lạ, thiếu link, invite mơ hồ hoặc kênh mới thì báo user/xác nhận trước. Không đoán channel.

• Calendar event bị hủy/đổi, app offline, token hết hạn, Discord permissions lỗi hoặc model chưa sẵn: không join im lặng; hiển thị lý do. App restart không tự vào meeting cũ đã qua. Disclosure và consent scopes Scope/tầng Quy tắc thiết kế Nhận media qua mạng Bot là thành viên voice; disclosure nói có thể nhận voice packet. Consent policy cuối vẫn chờ Son. DAVE decrypt Có thể xảy ra trước consent tùy API voice; báo riêng nếu prototype quan sát thấy. Không gọi đây là AI inference. Speaker mapping SSRC → user để áp policy; map chưa chắc chắn/stale thì drop, không gán nhầm. Live PCM/VAD/ASR/LLM/TTS Gate theo session/user/scope. Chỉ route live-consented speaker; unknown/revoked drop. Hiển thị trạng thái rõ. Lưu transcript/notes Separate opt-in và retention. Có thể tắt lưu bền vững nhưng vẫn xử lý live nếu policy cho phép. Reply journal Chỉ nội dung bot trả lời + evidence/card IDs, scope riêng, off mặc định theo khuyến nghị; Son chưa chọn. Debug raw audio Off mặc định; chỉ test có thông báo/consent rõ và xóa theo test policy. Join và người mới Bot tự giới thiệu là MeetAI, trợ lý AI của Son; nếu raw recording được bật thì báo rõ trước khi bắt đầu. Bình thường không lưu raw audio. Mỗi participant phải có trạng thái consent theo session và từng scope; host được hỏi có muốn cuộc họp tiếp tục hay bot rời, nhưng host không thể ghi đè opt-out của cá nhân. Nếu người chưa consent xuất hiện sau khi vào, A1 circuit-breaker fail-closed: đóng gate, hủy ASR/LLM/TTS, purge state liên quan; shared/mixed context không chắc chắn thì purge toàn bộ; ngắt voice và tắt auto-reconnect. Strict A3 host-controlled admission là fallback nếu prototype không gate được trước PCM/ASR hoặc Son không chấp nhận cửa sổ đã đo.

## 4. Media race, consent state và response runtime A1 không được quảng bá là zero packet/decrypt. Pass 0c là quan sát trên build/library/version/test matrix cụ thể; test hữu hạn không chứng minh mọi lịch chạy. Instrumentation 0c Metadata timestamps/counters: first RTP, SSRC map, decrypt callback, PCM enqueue, ASR enqueue/start, Gateway voice-state, gate close, LLM start, TTS enqueue/first output, disconnect. Không ghi audio/frame/transcript để debug. Matrix gồm media/event order ép bằng barrier/delay, jitter, burst, nhiều lần join/reconnect, SSRC đổi/map trễ; báo build hash và số lần chạy. Pass: không quan sát thấy unconsented/unmapped frame qua PCM/ASR gate ở matrix được mô tả; không suy rộng thành bảo đảm phổ quát. [Discord Voice/DAVE](https://discord.com/developers/docs/topics/voice-connections). Consent state machine State/event Kết quả UNKNOWN/ANNOUNCED + accept hợp lệ CONSENTED chỉ cho session_id + user_id + scope + notice_version. UNKNOWN/ANNOUNCED + decline/expiry DECLINED/EXPIRED; không khởi pipeline scope đó. CONSENTED + revoke REVOKED; gate trước await, tăng generation, purge theo phạm vi. DECLINED/REVOKED/EXPIRED + duplicate/stale/late Terminal trong phiên; idempotent; không bật lại. accept Session kết thúc Session_id/nonce mới, roster/disclosure mới; không kế thừa accept cũ. Atomicity Serialize hoặc compare-and-set theo (session_id,user_id,scope); gắn generation vào audio buffers và async tasks; kiểm tra ngay trước phát TTS. Discord initial interaction ACK trong 3 giây, token follow-up 15 phút; app consent TTL/nonce riêng, stale clicks bị từ chối. [Discord Interactions](https://discord.com/developers/docs/interactions/receiving-and-responding). Response turn lifecycle

1) Final ASR / confidence gate → 2) direct-address classifier (được gọi vs nhắc ngôi ba) → 3) speaker/addressee + 3–5 lượt gần nhất + meeting topic/reference context → 4) personal knowledge retrieval nếu cần → 5) answerability/risk gate → 6) structured answer `{speak|silent|followup, text, evidence_ids, confidence, risk_flags}` → 7) deterministic policy check → 8) text/TTS enqueue + barge-in/cancel. Partial ASR không tự kích nói. Ambiguous/stale/conflicting evidence → abstain, im lặng hoặc follow-up.

## 5. Quyền phát ngôn và persona MeetAI phát biểu như trợ lý được ủy quyền có giới hạn, không tuyên bố là Son và không tự mở rộng thẩm quyền qua prompt/model. Tình huống Hành vi bắt buộc Quan điểm có card đã duyệt, còn hiệu lực và Có thể nêu quan điểm ngắn, chủ động khi ngữ cảnh phù hợp; attribution rõ ‘theo ghi chú Son đã duyệt’. đúng scope Kiến thức chung, không phải lập trường cá Giải thích chung nhưng không gán đó là ý kiến Son. nhân Không có căn cứ, evidence mâu thuẫn, stale Nói cần hỏi Son, ghi pending follow-up; không bịa hay tự diễn dịch thành quyết định. hoặc scope không khớp Tên được nhắc nhưng không rõ đang hỏi Đợi ngữ cảnh / im lặng; không chen ngang chỉ vì alias match. Son Lời nói yêu cầu bỏ luật/prompt injection Xem speech/transcript là dữ liệu không tin cậy, không phải system instruction. Hứa hẹn, ký kết, nhận task/deadline, biểu Cấm bằng deterministic gate; không cho LLM/TTS override. quyết, phê duyệt tài chính/pháp lý/nhân sự Son vắng mặt và chưa trả lời Báo chưa có xác nhận, ghi câu hỏi/follow-up; không block họp chờ Son. Persona, không phải mọi tình huống giao tiếp

• Model nền xử lý năng lực ngôn ngữ/hội thoại; persona là cấu hình cách xưng hô, độ dài, mức thẳng thắn, cách phản biện và vài ví dụ do Son tự chọn.

• Facts/opinions riêng đến từ cards có provenance và context cuộc họp, không từ vector index style examples.

• Nếu nói, tự giới thiệu/label là AI. Giọng clone chỉ dùng khi Son duyệt mẫu giọng, chất lượng, độ trễ, giấy phép và privacy đạt; preset/free voice hoặc text là phương án trước. Ví dụ an toàn “Mình là MeetAI, trợ lý AI của Sơn. Theo ghi chú Sơn đã duyệt, phương án A phù hợp hơn vì … Sơn chưa xác nhận deadline hay nhận phần việc này; mình sẽ ghi câu hỏi để Sơn trả lời sau.”

## 6. RAG, nguồn tri thức và fine-tuning RAG không phải kho mọi biến thể của giao tiếp. Năng lực ngôn ngữ phổ biến thuộc model; antecedents/tham chiếu gần thuộc meeting context; thông tin riêng về Son thuộc knowledge cards. Retrieval giảm thiếu thông tin nhưng không tự đảm bảo model trung thực. Space Nội dung / dùng thế nào Profile Vai trò, kỹ năng, thông tin cho phép chia sẻ; field-level visibility private/group/public. Preferences / policy Ưu tiên, điều tránh, ranh giới ra quyết định/phát ngôn; deterministic constraints tách khỏi LLM. Positions Quan điểm đã Son xác nhận: claim, rationale, source, scope, effective dates, sensitivity, supersedes. Projects / expertise Ghi chú, quyết định, quy trình tự viết/được quyền dùng; trạng thái hiện tại và nguồn. Glossary Tên, alias, thuật ngữ/phát âm; hỗ trợ ASR/retrieval, không phải bằng chứng đã được gọi. Style examples Câu do Son tạo/chọn làm mẫu; không dùng làm factual memory. Meeting context Lượt thoại gần nhất, referents, agenda, open questions, draft decisions; session-bound, ephemeral hoặc lưu theo opt-in. Nạp và duyệt Son tự nhập form 3–5 câu trước họp, tài liệu do Son sở hữu/được quyền dùng, câu trả lời Son duyệt sau họp, hoặc knowledge card tự tạo. Pipeline: ingest → extract with source location → suggest category/scope/sensitivity/validity → dedupe/atomic fact chunk → Son reviews/edits/declines → index approved only → update/supersede/delete cascade through chunks, embeddings, caches. Pending content không được retrieve. Card schema tối thiểu id, type, subject, claim, rationale, source_id/URI/date, approval_status, approved_by, valid_from/until, supersedes, scope, sensitivity, confidence, allowed_actions, created_at, reviewed_at, version, content_hash. Retrieval / conflict

• Intent gate chỉ truy xuất khi câu hỏi cần thông tin về Son; lọc scope/privacy/date trước search; exact lexical/metadata cho tên/mã, semantic retrieval cho diễn đạt; rerank chỉ nếu benchmark cải thiện.

• Lấy ít evidence liên quan kèm provenance; kiểm tra freshness/conflict/answerability. Mâu thuẫn ngang cấp hoặc card hết hạn → hỏi Son.

• Ưu tiên chỉ thị xác nhận trực tiếp mới nhất của Son, rồi tài liệu chính thức Son đánh dấu, rồi note/card đã duyệt. Transcript chưa duyệt không phải tri thức dài hạn. Fine-tune Tự build hệ thống + self-host model mở; không train foundation model từ đầu trong ngân sách/máy hiện tại. Sau khi có corpus tự tạo/được cấp quyền: thử LoRA/QLoRA để dạy format/style/refusal, train/validation/test tách riêng, manifest/license/consent, rollback. Không dùng message content qua Discord API để huấn luyện AI khi chưa có express permission theo Discord Developer Policy. [Discord Developer Policy](https://support-dev.discord.com/hc/en-us/articles/8563934450327-Discord-Developer-Policy).

## 7. Local runtime, phần cứng và ngân sách Chức năng Ứng viên nghiên cứu; chưa chốt model Vietnamese ASR Qwen3-ASR 0.6B baseline để benchmark; so với PhoWhisper/whisper.cpp theo accent, noise, nói chồng, proper nouns và stream chunks. Repo hiện nêu Vietnamese support cho 0.6B/1.7B; xác minh weights/license/version lúc build. [Qwen3-ASR](https://github.com/QwenLM/Qwen3-ASR). LLM local Small instruct model quantized (v0.4 nêu Qwen3 1.7B/4B làm ứng viên). Đo grounding, Vietnamese turn-taking, structured output, VRAM/KV cache; không lựa chọn theo model card đơn thuần. Embeddings/search SQLite metadata + BM25/FTS-free option cho nhạy cảm; embedding multilingual nhỏ chỉ khi lexical+metadata retrieval chưa đủ. Không cần GPU reranker hot path MVP. TTS MVP ưu tiên text hoặc preset Vietnamese voice local miễn phí; voice clone không phải dependency. Tự host, license weights/voice rõ, benchmark pronunciation/RTF trên i7. Fine-tune Colab Pro L4 22.5 GB VRAM chỉ dùng thí nghiệm LoRA/QLoRA; không làm live inference host hoặc chứa dữ liệu nhạy cảm nếu chưa đồng ý đưa dữ liệu ra đó. Quản lý tài nguyên

• GTX 1660 Ti 6 GB và RAM 16 GB không nên chạy ASR+LLM+embedding+TTS heavyweight resident cùng lúc. Model manager serialize GPU jobs, unload/preload, queue giới hạn, warm-up và cancellation.

• Model có thể tắt/bật theo nhu cầu; scheduler chỉ join nếu audio adapter, ASR, policy và response mode đã healthy. Không giả vờ nghe/nói được khi model offline.

• Measure RAM/VRAM peak, CPU, thermal, endpoint-to-final-ASR, LLM first token, TTS first byte, end-to-end p50/p95. 1–2 giây stretch target, không cam kết; câu trả lời đúng và không chen ngang quan trọng hơn. Chi phí Chưa thể xác nhận 500.000 VND/tháng đủ: tính điện năng toàn máy khi idle/active, thời gian bật, internet, SSD/backup và GPU rental nếu cần. Chỉ thuê GPU ngoài cho thí nghiệm offline sau khi xem privacy/data transfer; live AI API/cloud inference bị loại theo yêu cầu. Colab session không phải dịch vụ realtime bền vững.

## 8. Lưu trữ, xóa và threat model Mặc định không persist raw audio; không dùng cuộc họp để train. Nội dung meeting có thể đi qua RAM trong lúc xử lý. Storage capability tồn tại, nhưng loại transcript/notes/journal và TTL cụ thể vẫn chờ Son chọn. Mode Persist Trạng thái quyết định Ephemeral Không lưu nội dung meeting hay bot replies; giữ metadata vận hành tối Thiết kế khả dụng; TTL receipt thiểu/receipt theo TTL nếu đã duyệt. chưa chốt. Ephemeral + reply journal Chỉ lưu nội dung bot nói + evidence/card IDs/scope; không raw audio hoặc Off mặc định; Son chưa bật/tắt. transcript. Saved notes/transcript Lưu transcript/summary/metadata theo meeting, mã hóa, retention và delete Tính năng thiết kế; cascade. consent/retention vẫn cần chốt. Debug audio Raw audio tạm chỉ ở test đã thông báo/consent, off mặc định; auto-purge. Cần prototype 0c, không dùng ở live mặc định. Consent receipts và deletion

• State lưu tối thiểu: session_id, notice_version, user_id, scope, choice, timestamp, expiry; nội dung receipt không phải transcript. Host hỏi tiếp tục/rời, không override opt-out cá nhân.

• Delete user action đóng read gate, hủy tasks, invalidates generation, purge meeting state/index/blob/key according to scope. ‘Xóa khỏi bản sao MeetAI quản lý’ là câu mặc định; không hứa ghi đè vật lý SSD.

• Crypto-erasure mới là thiết kế cần chứng minh: random per-session DEK (đề xuất), wrapped key file ngoài SQLite/WAL, DPAPI CurrentUser (đề xuất), không backup content nhạy cảm (đề xuất). Chưa thông qua crash/restore/WAL/key-copy test thì không quảng bá crypto-erasure.

• SQLite secure_delete bật trước delete là lớp phụ; không dùng FTS3/FTS5 trên nội dung nhạy cảm vì shadow table. Xử lý WAL/checkpoint/cache/temp và startup recovery theo prototype.

• Threat model: Discord audio/identity, transcript, personal cards, Calendar OAuth, bot token, voice samples, local Windows account, prompt injection, supply chain, backup/profile restore, crash/pagefile/hibernation, accidental opt-out leakage. Khóa Secrets Discord/Google không vào source/log; Windows Credential Manager/DPAPI, scopes/perms tối thiểu; local dashboard bind 127.0.0.1, không mở inbound port. DPAPI CurrentUser bảo vệ at rest theo tài khoản, không ngăn app/process đang chạy dùng secret. Volume encryption bảo vệ khi máy tắt/ổ bị lấy, không khi session đang mở. Không bật crash dump nội dung.

## 9. Discord permissions, failures và safety MeetAI phải là Discord bot application account được tạo qua Developer Portal, không self-bot. Discord nói automated normal user accounts bị cấm; bot user là loại account riêng dành cho automation. [Discord Self-Bots](https://support.discord.com/hc/en-us/articles/115002192352-Automated-User-Accounts-Self-Bots). Voice permissions/admission

• Không cấp bot MOVE_MEMBERS, MANAGE_CHANNELS hoặc Administrator để vượt user_limit; host quản lý Connect/lobby admission. User limit chỉ defense-in-depth, không nhận dạng consent.

• DAVE là E2EE participant flow, không bypass/reverse engineer. Bot phải hỗ trợ đúng giao thức và library; audio receive là blocker cần chứng minh trên pin cụ thể. Discord docs nói bot respect user_limit; MOVE_MEMBERS có thể bypass. [Discord Voice Connections](https://discord.com/developers/docs/topics/voice-connections).

• Gateway intents tối thiểu; button/slash interactions thay phụ thuộc MESSAGE_CONTENT nếu không cần đọc message content. Discord chính sách hạn chế dùng API message content để train model khi chưa được express permission. Failure table Lỗi Hành vi an toàn App/PC tắt, sleep, mạng down Không join; khi bật lại không tự join meeting đã qua; báo missed event. Calendar link/channel không hợp lệ hoặc Không đoán; hỏi Son/xác nhận allowlist. mới Bot permission/voice/DAVE/SSRC lỗi Không transcript/nói giả; đóng pipeline, báo degraded, rời hoặc chờ theo state rõ. Newcomer chưa consent / revoke A1 gate/cancel/purge/disconnect; không reconnect tự động. Shared context mơ hồ thì clear toàn bộ. GPU/model timeout hoặc model off Không giả vờ; không nói thay. Báo app/host và đứng ngoài/leave theo config. ASR thấp confidence, overlap/ambiguous Không phát lời; đợi lượt sau hoặc ghi follow-up theo mode. call RAG thiếu, stale, conflict, private scope Abstain; hỏi Son. Không leak private card sang group. mismatch Delete IO/crash giữa chừng Fail closed; trạng thái DELETE_PENDING, startup reconcile; không báo hoàn tất khi chưa đạt invariant. Prompt injection qua speech/document Xem input là untrusted data; không gọi tool side effect hoặc đổi policy.

## 10. Evals, test gates và roadmap Một tuần là feasibility week, không phải lịch giao một đại diện đáng tin trong production. Không làm RAG/voice cloning trước khi qua blocker Discord audio. Gate Nội dung Điều kiện qua 0a App + Calendar OAuth read-only, event sync, parse link, timezone, idempotency, app health. Chỉ event hợp lệ đi tới planner; không stale auto-join. 0b Consent Notice/buttons/slash, ACK ≤3s, nonce/session/user/scope/expiry, Không consent nhầm user/session/scope; revoke duplicate/late click. thắng. 0c DAVE + A1/A3 Receive/decrypt, epoch, SSRC, jitter/order stress, reconnect, per-stage Mô tả kết quả đúng phạm vi; unknown/unconsented timestamps; không payload logs. không qua PCM/ASR gate trên matrix; report gaps. 0d Purge/state Revoke trong ASR/LLM/TTS, simultaneous accept/revoke, mixed buffers, Không output mới sau gate; uncertain shared state generation cancel. purge.

## 1 Model eval ASR Vietnamese WER/CER/name error, trigger precision/recall, grounding, Held-out set; ambiguous abstain; zero boundary safety, p50/p95, RAM/VRAM/thermal. violation trong test suite; không claim universal proof.

## 2 Storage/delete DB/WAL/key files, crash injection, restart, restore, cache/temp, TTL/delete. App không giải mã theo định nghĩa xóa đã chốt; report backup/SSD limitations.

## 3 Limited pilot Text-only or preset TTS, private test server, named participants, explicit Human review, stop/leave works, incident log has scope notice. metadata only. Metrics DAVE receive pass/fail by pinned build; consent leakage; ASR WER/CER by accent/noise/speaker; trigger precision/recall (mentions vs direct address); grounded claim rate/provenance; policy boundary violations; latency stages p50/p95; crash/packet gap/CPU/RAM/VRAM/thermal; delete recovery checks. Logs metadata only; transcript content in scoped vault only. MVP order Calendar + desktop supervisor → Discord bot join/disclosure → voice/DAVE/consent spike → ASR and local transcript/summary → personal cards/RAG eval → text answer with hard policy → TTS preset if feasible → clone only after separate approval and quality/privacy/latency gate → future platform adapters.

## 11. Open decisions, assumptions and ADRs Mục này phân biệt những gì đã thống nhất giữa hai bên với điều Son chưa quyết. Claude/Luna không tự lựa chọn thay chủ sản phẩm. ID Quyết định Trạng thái / ảnh hưởng D-01 Consent/late join A1 default là khuyến nghị; strict A3 fallback nếu gate không đủ sớm hoặc Son không chấp nhận cửa sổ đo. Son cần chốt quy tắc: ai consent trước join, newcomer, decline, host hỏi tiếp tục/rời. D-02 Reply journal Off mặc định. Son chưa quyết định có bật opt-in journal; nếu off thì không thể tái dựng chính xác bot đã nói gì sau họp. D-03 Retention 30d receipt / 7d reminder / 7d journal chỉ là đề xuất; để trống tới khi có trải nghiệm thực cũng hợp lệ. TTL saved notes/transcript chưa chốt. D-04 Consent receipts metadata Schema/TTL và có persist hay không phải khóa cùng D-01/D-03; receipt metadata không phải meeting content. D-05 Delete strength Default language ‘xóa khỏi app-managed copies’. Crypto-erasure chỉ sau ADR + test key inventory, file/WAL/crash/recovery/backup. Không cam kết physical SSD wipe. D-06 TTS/voice clone Clone chỉ nếu Son chủ động duyệt mẫu, chất lượng Việt, latency, cost, legal/license. Default text/preset. D-07 Model choice ASR/LLM candidates là benchmark shortlist, chưa pin dependency/model. Recheck upstream docs, license/weight terms/version before implementation. D-08 Operational budget 500k VND/month target, not confirmed; measure power/hosting/storage/network/GPU experiments. D-09 Response trigger Recognize mention vs direct address, but uncertain intent abstains. Thresholds require labeled evaluation from synthetic/user-authored data. Các đồng thuận lõi đã có

• Tên MeetAI; Discord trước; Google Calendar; app desktop mở trước khi cần; local-only AI inference; user-controlled private test server/channel.

• Một bot account riêng, AI identity disclosed; no avatar clone; text/default free voice first; no promises or decisions for Son.

• Grounded persona + scoped personal RAG + ephemeral meeting context; no training on Discord API message content without Discord express permission.

• Individual opt-out not overridden by host; consent scopes separate; A1 fail-safe/A3 fallback behavior subject to user final policy and prototype.

• No raw audio persistence by default; content retention modes/TTL and journal still to decide. Architecture Decision Record needed before coding live voice ADR-01: selected Discord voice library/version + DAVE and receive capability; ADR-02: consent and newcomer state policy; ADR-03: storage modes/TTL/delete threat model and crash invariants; ADR-04: local model versions/quantization and GPU scheduling after benchmark. Implementation should not treat this document's candidates as confirmed dependencies.

## 12. References and interpretation notes Các nguồn chính thức dưới đây được dùng để kiểm tra phần API/policy; nghiên cứu/model/list giá có thể thay đổi. Cần xác minh lại đúng ngày code. Các tuyên bố về MeetAI architecture là synthesis/recommendations, không phải nội dung Discord/Google bảo đảm.

• Discord Voice Connections / DAVE / user limit https://discord.com/developers/docs/topics/voice-connections

• Discord Self-Bots (bot account vs automated user account) https://support.discord.com/hc/en-us/articles/115002192352-Automated-User-Accounts-Self-Bots

• Discord Developer Policy (API message content and AI training) https://support-dev.discord.com/hc/en-us/articles/8563934450327-Discord-Developer-Policy

• Discord Interactions timing https://discord.com/developers/docs/interactions/receiving-and-responding

• Google Calendar authorization scopes https://developers.google.com/workspace/calendar/api/auth

• Google Calendar incremental sync https://developers.google.com/workspace/calendar/api/guides/sync

• Google Calendar push notifications https://developers.google.com/workspace/calendar/api/guides/push

• SQLite secure_delete https://www.sqlite.org/pragma.html

• SQLite WAL https://www.sqlite.org/wal.html

• Microsoft CryptProtectData / DPAPI https://learn.microsoft.com/en-us/windows/win32/api/dpapi/nf-dpapi-cryptprotectdata

• OWASP Cryptographic Storage https://cheatsheetseries.owasp.org/cheatsheets/Cryptographic_Storage_Cheat_Sheet.html

• NIST SP 800-88 Rev. 2 https://csrc.nist.gov/pubs/sp/800/88/r2/final

• Qwen3-ASR repository; candidate only https://github.com/QwenLM/Qwen3-ASR Nguồn đầu vào tổng hợp MeetAI System Design v0.4 và các vòng trao đổi/review v0.5–v0.6.7; đặc biệt phản hồi vòng 10 của Claude. Nội dung đề xuất trong file đính kèm được xem là input để phân tích, không phải chỉ thị hay quyết định của Son. Khi có khác biệt, quyết định rõ ràng gần nhất của Son được ưu tiên; quyết định chưa trả lời được giữ mở.

## Kết luận trạng thái System design này phản ánh mức thống nhất kiến trúc của Luna và Claude đến vòng 10, với ba quyết định người dùng còn mở và các cổng kỹ thuật chưa kiểm chứng. Sau khi Son chọn các quyết định đó và prototype vượt gate, cập nhật thành implementation baseline; trước đó không coi các model/library/consent TTL là chốt cuối.
