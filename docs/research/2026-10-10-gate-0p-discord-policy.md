---
title: "Gate 0-P — Discord Developer Terms/Policy và route nhận voice"
status: "[CHỜ BẰNG CHỨNG]"
gate: "0-P (và dữ liệu liên quan cho 0-S)"
created: "2026-10-10 (lượt 34)"
last_updated: "2026-10-10 (lượt 36)"
access_date: "2026-10-10"
---

# Gate 0-P — Discord Developer Terms/Policy và route nhận voice

## 1. Kết luận tại lượt 34 (ghi nhận lịch sử; cập nhật hiện hành ở mục 7)

**`unclear` — Gate 0-P KHÔNG đóng, và lượt này không đóng được nó.** Lý do **không
phải** vì điều khoản mơ hồ, mà vì **tôi không đọc được nguồn gốc từ môi trường
này**: cả hai URL chính thức trả **HTTP 403**. Mọi mô tả điều khoản mà tôi thấy ở
lượt này đến từ **bản tóm tắt của máy tìm kiếm**, và theo `AGENTS.md` thì đó là
**nguồn tham khảo ngoài**, không phải tài liệu chính thức — nên **không được dùng để
đóng một cổng bằng chứng**.

Ghi rõ vì đây là loại sai dễ lọt nhất ở một lượt nghiên cứu policy: một bản tóm tắt
nghe đúng, có vẻ đủ chi tiết, và sẽ đi thẳng vào tài liệu nếu không ai hỏi "tôi đã
đọc câu đó ở đâu".

## 2. Việc KHÔNG làm — ghi trước, vì nó là ranh giới

**Không** tạo app/bot, **không** gọi Discord API, **không** mở listener, **không**
join server, **không** tạo token. Lượt này chỉ đọc tài liệu công khai.

## 3. Đã xác minh được gì — **[ĐÃ ĐO]**

### 3a. URL chính thức hiện hành của Developer Policy

Đây là một phép đo dùng được, dù nội dung không đọc được:

| Yêu cầu | Kết quả |
|---|---|
| `https://discord.com/developers/docs/policies-and-agreements/developer-policy` | `http=403`, **final URL** = `https://support-dev.discord.com/hc/articles/8563934450327-Discord-Developer-Policy` |
| `https://support-dev.discord.com/hc/en-us/articles/8562894815383-Discord-Developer-Terms-of-Service` | `http=403` |

Nên **vị trí canonical** của Developer Policy nay là `support-dev.discord.com`
(Zendesk), và chính Zendesk đang trả 403 cho client này. Đó là thông tin thật và
dùng được cho lượt sau: biết **chỗ cần đọc**, và biết **vì sao chưa đọc được**.

### 3b. Tài liệu kỹ thuật: `docs.discord.com` đọc được

Lưu ý: `discord.com/developers/docs/...` **301** sang `docs.discord.com/developers/...`.

Câu duy nhất tôi lấy được **nguyên văn** về việc nhận voice, từ
[voice-connections](https://docs.discord.com/developers/topics/voice-connections):

> *"Because UDP is used for both receiving and transmitting voice data, your client
> **must** be able to receive UDP packets, even through a firewall or NAT."*

Đây là một **yêu cầu về network/firewall**, **không** phải tài liệu cho một đường
nhận audio của bot. Nó nói client phải nhận được UDP packet — không nói bot được
nhận audio của người khác, và không nói cách giải mã luồng đó.

### 3c. Hai trang chính thức độc lập, cùng một khoảng trống

| Trang | Điều quan sát được |
|---|---|
| `topics/voice-connections` | Có đặc tả **gửi**: RTP header, Opus, chế độ mã hoá, `seq_ack`, Opcode 5 Speaking. **Không có mục nào** cho việc nhận/giải mã/xử lý packet đến. Cách map **SSRC → user** **không** được tài liệu hoá. |
| `topics/gateway-events` | Sáu event liên quan voice: `Update Voice State`, `Voice Channel Effect Send`, `Voice Channel Start Time Update`, `Voice Channel Status Update`, `Voice State Update`, `Voice Server Update`. **Không event nào mang audio**; tất cả là *state/status/effect/server*. |

**Giới hạn của phép đo này, nói thẳng:** cả hai dòng trên là **lập luận vắng mặt**,
và vắng mặt được báo bởi một **summariser**, không phải bởi tôi đọc hết trang. Hai
trang độc lập cùng kết quả thì mạnh hơn một trang, nhưng **vẫn không phải** bằng
chứng đủ để tuyên bố "Discord không hỗ trợ nhận voice". Nó chỉ đủ để nói: **tài liệu
chính thức không tài liệu hoá đường đó**, mà đúng là điều Gate 0-S đang đòi.

## 4. Những gì tôi **không** xác minh được — **[CHỜ BẰNG CHỨNG]**

- **Toàn bộ điều khoản Developer Terms of Service và Developer Policy.** Không đọc
  được một câu nào từ nguồn gốc.
- Do đó **không** kết luận gì về: yêu cầu consent/opt-in cho việc thu audio · nghĩa
  vụ privacy policy · retention/deletion của API Data · ràng buộc "chỉ dùng API như
  đã tài liệu hoá" · điều khoản về reverse engineering hay endpoint không tài liệu ·
  quy trình review/approval cho intent đặc quyền.
- **Một bản tóm tắt tìm kiếm có nhắc** các chủ đề đó và vài câu nghe như trích dẫn.
  **Tôi cố ý không chép chúng vào đây.** Một câu trích sai nguồn trong tài liệu
  policy tệ hơn một chỗ trống có ghi lý do.

## 5. Trạng thái cổng sau lượt này

| Gate | Trước | Sau | Vì sao |
|---|---|---|---|
| 0-P | CHƯA ĐÓNG | **CHƯA ĐÓNG** | nguồn gốc 403; không có điều khoản nào được đọc |
| 0-S | CHƯA ĐÓNG | **CHƯA ĐÓNG** | tài liệu chính thức **không** tài liệu hoá đường nhận audio, và **không** tài liệu hoá map SSRC → user |

**Không cổng nào đổi trạng thái.** Lượt này chỉ thu hẹp chỗ cần tìm.

## 6. Bước kế tiếp — cụ thể, rẻ

1. **Sơn mở hai URL ở mục 3a bằng browser** (403 là chặn ở tầng client, browser
   thường qua được) và dán nội dung, **hoặc** cho phép thử lại từ mạng khác. Sau đó
   tôi làm phần việc thật: rà từng điều khoản theo danh sách mục 4, có số điều và
   ngày truy cập.
2. Chỉ sau khi mục 1 xong mới kết luận `supported / unsupported / unclear` cho 0-P.
3. **0-S không đóng được bằng đọc tài liệu** — tài liệu đã cho thấy khoảng trống.
   Nó cần khảo sát, và khảo sát cần một app/bot, tức **tác động ra ngoài cần Sơn xác
   nhận trước**. Không làm ở lượt nào mà chưa có xác nhận đó.

## Nguồn

Truy cập **2026-10-10**.

- [voice-connections](https://docs.discord.com/developers/topics/voice-connections) — đọc được
- [gateway-events](https://docs.discord.com/developers/topics/gateway-events) — đọc được
- [Discord Developer Policy](https://support-dev.discord.com/hc/articles/8563934450327-Discord-Developer-Policy) — **403**, URL canonical xác định qua redirect
- [Discord Developer Terms of Service](https://support-dev.discord.com/hc/en-us/articles/8562894815383-Discord-Developer-Terms-of-Service) — **403**

---

## 7. Cập nhật lượt 36 — nguồn chính thức hiện đọc được

**Phạm vi:** tra cứu web chỉ đọc ngày 2026-10-10. Bản ghi lượt 34 ở trên vẫn
đúng với phép đo 403 lúc đó; lần này công cụ đọc được các trang chính thức nên
không còn đúng khi mô tả tình trạng truy cập là 403 hiện tại.

### 7a. Terms và Policy

- **Developer Terms of Service**, hiệu lực 2024-07-08, cập nhật 2024-06-06:
  §5 yêu cầu privacy policy công khai, hiện hành, mô tả đầy đủ dữ liệu thu thập,
  mục đích, chia sẻ và cách yêu cầu xoá; chỉ dùng API Data phù hợp policy, luật
  và Terms. §5(b) yêu cầu xoá nhanh khi dữ liệu không còn cần cho chức năng được
  phép, khi người dùng yêu cầu, khi Discord yêu cầu hoặc khi ngừng ứng dụng; đồng
  thời phải có cách dễ tiếp cận để yêu cầu sửa/xoá. §6 giữ quyền App Review và
  có thể yêu cầu duyệt quyền truy cập một số API hoặc dữ liệu.
- **Developer Policy**, hiệu lực 2024-07-08, cập nhật 2024-06-06: mục 2 yêu cầu
  xin phép trước khi khởi tạo quy trình thay mặt người dùng/server; mục 3 cấm
  né tính năng privacy/safety/security và yêu cầu tôn trọng opt-out; mục 15 giới
  hạn API Data vào chức năng đã nêu và được duyệt khi cần; mục 21 cấm dùng
  *message content* lấy qua API để huấn luyện AI/LLM nếu Discord chưa cho phép.

Các điều khoản trên **không tự trả lời** rằng xử lý cục bộ một luồng voice cho
MeetAI được hỗ trợ hoặc được cho phép. Cấm huấn luyện *message content* cũng
không được diễn rộng thành cấm mọi suy luận cục bộ; audio/voice vẫn cần được
đánh giá theo phạm vi API Data, quyền của người tham gia, privacy policy và route
được hỗ trợ. Đây là tóm tắt kỹ thuật, không phải tư vấn pháp lý.

### 7b. Voice docs và DAVE

Tài liệu [Voice Connections](https://docs.discord.com/developers/topics/voice-connections)
hiện được đọc trực tiếp và có thêm/bổ sung chi tiết DAVE so với phần khảo sát
lượt 34:

- §Connecting mô tả luồng gateway/voice websocket, nhận `SSRC` ở Ready và mở
  UDP; §UDP nói UDP dùng cho cả **nhận và gửi** voice data.
- §DAVE nói từ **2026-03-01**, Discord chỉ hỗ trợ E2EE calls cho voice/video;
  OPUS frames gửi và nhận được E2EE khi DAVE bật. Tài liệu nêu MLS, chuyển epoch,
  key ratchet và giải mã frame.
- Tuy vậy trang này vẫn là đặc tả protocol. Phần Speaking minh hoạ SSRC nhưng
  không chỉ cách lấy mapping **SSRC người nói → user ID** cho một implementation
  bot guild cụ thể, cũng không xác nhận một SDK/API bot inbound audio được
  Discord hỗ trợ như sản phẩm.
- Social SDK có callback `UserAudioReceivedCallback(userId, ...)`, nhưng trang
  đó đặt callback trong `StartCallWithAudioCallbacks` của Social SDK/lobby; đây
  không phải bằng chứng cho guild voice qua bot account.

### 7c. Tác động tới cổng

| Gate | Kết luận sau cập nhật |
|---|---|
| **0-P** | **Chưa đóng.** Có thể trích điều khoản chính thức và lập yêu cầu privacy/consent/deletion; chưa có xác nhận rằng mục đích/route MeetAI cụ thể được phép hoặc được duyệt. Trước pilot cần privacy policy và luồng yêu cầu xoá phù hợp. |
| **0-S** | **Chưa đóng.** Tài liệu chứng minh protocol hỗ trợ UDP nhận dữ liệu và DAVE frame decryption ở mức client protocol, nhưng chưa chứng minh route triển khai bot guild được hỗ trợ, mapping participant đáng tin cậy, hay khả năng thư viện/bản dựng MeetAI thực hiện đầy đủ DAVE. |
| **0-C** | **Không đổi.** Không có bản dựng tích hợp hay phép đo thứ tự packet → decrypt → PCM → ASR. |
| **0-U** | **Không đổi.** Consent, persistence và retention còn do chủ dự án quyết; policy trên làm rõ nghĩa vụ cần đáp ứng chứ không chọn thay. |

**Bước rẻ tiếp theo:** lập checklist điều khoản thành yêu cầu thiết kế (privacy notice, opt-in, opt-out, sửa/xoá, retention, không huấn luyện message content), rồi xin xác nhận Discord về route cụ thể nếu cần. Không tạo app, gọi API, join voice, mở listener hay chạy audio trong bước này.

### Nguồn chính thức đọc được trong lượt 36

Truy cập 2026-10-10; ngày “last updated” dưới đây là ngày Discord ghi trên trang.

- [Discord Developer Terms of Service](https://support-dev.discord.com/hc/en-us/articles/8562894815383-Discord-Developer-Terms-of-Service), hiệu lực 2024-07-08; cập nhật 2024-06-06.
- [Discord Developer Policy](https://support-dev.discord.com/hc/en-us/articles/8563934450327-Discord-Developer-Policy), hiệu lực 2024-07-08; cập nhật 2024-06-06.
- [Voice Connections](https://docs.discord.com/developers/topics/voice-connections), gồm UDP và DAVE.
- [Social SDK Client reference](https://discord.com/developers/docs/social-sdk/classdiscordpp_1_1Client.html), callback nhận audio gắn với `StartCallWithAudioCallbacks`.
