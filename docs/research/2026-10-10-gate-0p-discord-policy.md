---
title: "Gate 0-P — Discord Developer Terms/Policy và route nhận voice"
status: "[CHỜ BẰNG CHỨNG]"
gate: "0-P (và dữ liệu liên quan cho 0-S)"
created: "2026-10-10 (lượt 34)"
last_updated: "2026-10-10 (lượt 34)"
access_date: "2026-10-10"
---

# Gate 0-P — Discord Developer Terms/Policy và route nhận voice

## 1. Kết luận một dòng

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
