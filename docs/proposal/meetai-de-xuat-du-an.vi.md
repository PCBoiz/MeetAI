---
title: "MeetAI — Đề xuất dự án"
subtitle: "Trợ lý họp cá nhân chạy cục bộ, tiếng Việt, fail-closed theo thiết kế"
date: "2026-10-11"
lang: vi
---

# Mục lục

**Phần mở đầu**

- [0. Cách đọc tài liệu này](#0-cách-đọc-tài-liệu-này)
- [A. Thông tin dự án và tóm tắt điều hành](#a-thông-tin-dự-án-và-tóm-tắt-điều-hành)

**Phần I — Vấn đề và phạm vi**

- [B. Bối cảnh, người dùng và phạm vi](#b-bối-cảnh-người-dùng-và-phạm-vi)
- [C. Yêu cầu sản phẩm](#c-yêu-cầu-sản-phẩm)

**Phần II — Hiện trạng kỹ thuật**

- [D. Trạng thái hiện tại và kiến trúc](#d-trạng-thái-hiện-tại-và-kiến-trúc)
- [E. Tech stack](#e-tech-stack)
- [F. Hạ tầng và giới hạn máy](#f-hạ-tầng-và-giới-hạn-máy)
- [G. Mô hình dữ liệu, quyền riêng tư và bảo mật](#g-mô-hình-dữ-liệu-quyền-riêng-tư-và-bảo-mật)

**Phần III — Cách làm và lộ trình**

- [H. Quy trình phát triển, kiểm thử và đánh giá](#h-quy-trình-phát-triển-kiểm-thử-và-đánh-giá)
- [I. Lộ trình và tiêu chí nghiệm thu theo cổng](#i-lộ-trình-và-tiêu-chí-nghiệm-thu-theo-cổng)
- [J. Khả năng mở rộng và chiến lược dài hạn](#j-khả-năng-mở-rộng-và-chiến-lược-dài-hạn)

**Phần IV — Nguồn lực, rủi ro, quyết định**

- [K. Kỹ năng, gói công việc, kết quả bàn giao, rủi ro và quyết định](#k-kỹ-năng-gói-công-việc-kết-quả-bàn-giao-rủi-ro-và-quyết-định)
- [L. Kết luận](#l-kết-luận)
- [M. Tài liệu tham khảo](#m-tài-liệu-tham-khảo)

---

# 0. Cách đọc tài liệu này {#0-cách-đọc-tài-liệu-này}

## 0.1 Đối tượng và mục đích

**Viết cho:** chủ dự án, và bất kỳ người đọc kỹ thuật nào cần hiểu MeetAI
**trước khi** bàn bước tiếp. Tài liệu **không** giả định người đọc đã xem mã
nguồn, và mọi thuật ngữ nội bộ đều được giải thích ở chỗ xuất hiện lần đầu.

**Mục đích:** làm tài liệu định hướng và thảo luận — nêu vấn đề, phạm vi, kiến
trúc, trạng thái **có bằng chứng**, nguồn lực cần, lộ trình, và những quyết
định còn phải đưa ra.

**Đây là tài liệu có thể được công khai.** Vì vậy nó **không** chứa định danh cá
nhân, tên người dùng hệ điều hành, đường dẫn máy, thông tin đăng nhập, âm
thanh, bản ghi, tên người tham gia hay nội dung cuộc họp. Chủ dự án được gọi
bằng **vai trò**, không bằng tên.

## 0.2 Nhãn trạng thái — dùng suốt tài liệu

Mỗi phát biểu về năng lực đều mang một nhãn. Nếu một phát biểu không có nhãn,
nó là mô tả thiết kế hoặc văn bản dẫn nhập, không phải tuyên bố năng lực.

| Nhãn | Nghĩa |
|---|---|
| **[ĐÃ TRIỂN KHAI]** | Mã nguồn tồn tại, chạy được, có kiểm thử mà **xoá cơ chế đi thì kiểm thử sai** |
| **[ĐÃ ĐO]** | Có một phép đo cụ thể, truy được về lệnh đã chạy và ngày chạy |
| **[ĐỀ XUẤT]** | Khuyến nghị kỹ thuật **chưa được duyệt** — không phải cam kết |
| **[GIẢ ĐỊNH]** | Tạm dùng để không bị chặn; phải được ghi lại, **không** biến thành quyết định |
| **[CHỜ BẰNG CHỨNG]** | Cần tài liệu chính thức, hoặc một phép thử tái lập được |
| **[CHỜ SƠN]** | Cần quyết định của chủ dự án; **không ai quyết thay** |

## 0.3 Ba cách nói "chạy được" — đừng trộn chúng

Gộp ba cụm dưới đây là cách dễ nhất để nói quá, nên tài liệu tách chúng triệt để:

| Cụm từ | Nghĩa | Ai xác lập |
|---|---|---|
| **Có thể chạy** | Lệnh tồn tại, phụ thuộc đủ, kết thúc không lỗi | đo được |
| **Được phép chạy** | Không vượt ranh giới an toàn nào đã ghi | ranh giới + chủ dự án |
| **Đã chứng minh** | Có phép đo, và có kiểm thử xoá-là-sai | đo được |

Một thứ **có thể chạy** mà **chưa được phép** thì không chạy. Một thứ **được
phép và chạy được** vẫn **chưa chứng minh** gì cho tới khi có phép đo.

## 0.4 Hai điều tài liệu này cố ý không làm

1. **Không đưa phần trăm tiến độ tổng.** Không có mẫu số đo được cho phần việc
   còn lại, nên một con số như vậy sẽ là phát minh.
2. **Không gán ngày lịch cho mốc nào.** Thời gian chờ một quyết định không phải
   khối lượng công việc, và không có dữ kiện để ước lượng nó. Ở phần I, **khối
   lượng công việc** và **thời gian chờ quyết định/cấu hình máy** được tách
   thành hai cột riêng, đúng vì lý do này.

---

# A. Thông tin dự án và tóm tắt điều hành {#a-thông-tin-dự-án-và-tóm-tắt-điều-hành}

## A.1 Thông tin dự án

| Hạng mục | Nội dung |
|---|---|
| **Tên dự án** | MeetAI |
| **Chủ đề** | Trợ lý họp cá nhân tiếng Việt, chạy cục bộ, có cổng quyền hạn tất định |
| **Lĩnh vực** | Nhận dạng tiếng nói · mô hình ngôn ngữ cục bộ · kiến trúc an toàn/quyền riêng tư |
| **Người dùng mục tiêu** | **Một người** — chủ dự án, trên máy cá nhân của chính họ |
| **Nền tảng họp đầu tiên** | Một nền tảng có kênh thoại nhóm (Discord) — **[CHỜ BẰNG CHỨNG]** về route được hỗ trợ |
| **Ngôn ngữ sản phẩm** | Tiếng Việt |
| **Nơi triển khai** | Máy cá nhân của chủ dự án; **không** dịch vụ chạy 24/7 |
| **Giai đoạn** | Phase 0 và Phase 1 **hoàn tất**; Phase 2 **partial/open**; Phase 3+ **bị cổng bằng chứng chặn** |
| **Trạng thái tổng** | **Lõi quyết định chạy được và đo được. Chưa phải sản phẩm dùng được trong họp thật.** |
| **Ngày đo trạng thái** | 2026-10-11 |

## A.2 Vấn đề

Trong một cuộc họp trực tuyến, người chủ trì phải đồng thời **nghe**, **nhớ bối
cảnh** của những gì đã thống nhất trước đó, và **trả lời**. Phần "nhớ bối cảnh"
là phần máy làm tốt hơn người: nó đòi tra lại đúng thông tin đã được duyệt,
đúng thời điểm.

Nhưng một trợ lý **nói thay** người trong cuộc họp lại tạo ra một rủi ro mới, và
đó là rủi ro định hình toàn bộ thiết kế:

> **Một câu nghe có thẩm quyền, nói nhân danh người chủ trì, có thể tạo ra một
> cam kết mà người đó không hề đưa ra.**

Một câu trả lời sai về số liệu còn sửa được. Một lời hứa trái phép thì không.

## A.3 Đề xuất giá trị

MeetAI được xây quanh một nguyên tắc **hẹp hơn** "trợ lý thông minh":

- Nó **chỉ được nói những gì có bằng chứng đã duyệt đỡ phía sau**.
- Nó **không bao giờ** hứa, xác nhận thay, nhận việc, chốt hạn, bỏ phiếu hay
  phê duyệt — và **không mức độ tin cậy nào, không lượng bằng chứng nào** mở
  được các hành vi đó.
- Khi không đủ căn cứ, nó **im lặng hoặc đặt câu hỏi cho chủ dự án**, chứ không
  đoán.
- Dữ liệu **không ra khỏi máy**, và điều đó được cưỡng chế bằng **sự vắng mặt
  của năng lực**, không bằng một dòng cấu hình.

## A.4 Trạng thái hiện tại — bằng số đo

**[ĐÃ ĐO] 2026-10-11, tại commit `665a6c3`:**

| Hạng mục | Số đo |
|---|---|
| File được quản lý bởi Git | 154 |
| Module lõi (`src/meetai/`) | 23 + 3 module adapter |
| Module benchmark (`benchmarks/`) | 20 |
| Dòng mã lõi / dòng mã kiểm thử | 10 722 / 26 195 |
| File kiểm thử | 50 |
| **Bộ kiểm thử** | **5 271 passed, 3 skipped**, exit 0 |
| Dòng nghĩa vụ trong đặc tả | **72**, trong đó **58** mang nhãn `tested` |
| ADR (quyết định kiến trúc có lý do) | 7 |
| Ghi chú nghiên cứu | 20 |

Tỷ lệ mã kiểm thử/mã lõi là **≈ 2,4×**. Đó không phải chỉ số chất lượng, nhưng
nó nói đúng một điều về cách dự án được làm: phần lớn công sức nằm ở việc
**chứng minh một ranh giới an toàn còn nguyên**, không ở việc thêm tính năng.

## A.5 Kết luận thực tế — năm câu

1. **Lõi quyết định đã chạy được và đo được.** Đường từ *câu hỏi* → *tra cứu* →
   *đánh giá khả năng trả lời* → *cổng quyền hạn* → *nơi phát* là mã thật, chạy
   thật, tất định, và lặp lại được từng byte.
2. **Phần cảm nhận và phần suy luận chưa tồn tại.** Không có bộ nhận âm thanh
   vào, không có thành phần nhận dạng tiếng nói trong đường chạy, không có suy
   luận mô hình trong đường chạy, và **không nơi phát nào tới được cuộc họp**.
3. **Bốn cổng độc lập đang từ chối mọi lần chạy mô hình**, và mỗi cổng từ chối
   vì **sự vắng mặt của một trạng thái đã được duyệt**, không vì một lỗi.
4. **Bốn cổng bằng chứng của nền tảng họp đều còn mở**, và đóng hết chúng vẫn
   **chưa đủ** — ba thành phần vẫn phải được xây.
5. **Đây không phải tuyên bố sẵn sàng.** MeetAI hôm nay **không** dùng được
   trong một cuộc họp thật, và tài liệu này không đề nghị dùng nó như vậy.

---

# B. Bối cảnh, người dùng và phạm vi {#b-bối-cảnh-người-dùng-và-phạm-vi}

## B.1 Người dùng mục tiêu

**Một người.** Chủ dự án, trên máy cá nhân của chính họ, trong các cuộc họp mà
**họ tham gia**. Không phải sản phẩm nhiều người thuê, không phải dịch vụ chạy
liên tục, không có người quản trị tách biệt với người dùng.

Điều đó **không** phải hạn chế tạm thời mà là một **lựa chọn kiến trúc**: nó
cho phép "dữ liệu không ra khỏi máy" là một thuộc tính **cấu trúc** thay vì một
lời hứa trong chính sách. Hệ quả của lựa chọn này với khả năng mở rộng được nói
thẳng ở [phần J](#j-khả-năng-mở-rộng-và-chiến-lược-dài-hạn).

## B.2 Tình huống sử dụng

| # | Tình huống | MeetAI làm gì | Trạng thái |
|---|---|---|---|
| U1 | Có người hỏi một số liệu đã được chủ dự án duyệt trước đó | Tra card đã duyệt, trả lời kèm dẫn nguồn | **[ĐÃ TRIỂN KHAI]** ở lõi; chưa có đường vào/ra thật |
| U2 | Có người hỏi một điều **không** có trong tri thức đã duyệt | **Im lặng**, và nói rõ lý do trong báo cáo | **[ĐÃ TRIỂN KHAI]** |
| U3 | Hai card đã duyệt **mâu thuẫn** nhau | **Im lặng**, báo xung đột như tín hiệu cần review | **[ĐÃ TRIỂN KHAI]** |
| U4 | Có người đề nghị chủ dự án cam kết một việc | **Từ chối phát ngôn cam kết**, chuyển thành câu hỏi cho chủ dự án | **[ĐÃ TRIỂN KHAI]** (cổng quyền hạn) |
| U5 | Transcript chứa chỉ thị tiêm (prompt injection) tự nhận có quyền | Cổng vẫn soi đề xuất; text tự nhận quyền **không vì thế mà có quyền** | **[ĐÃ TRIỂN KHAI]** |
| U6 | Một người tham gia **chưa đồng thuận** vào họp giữa buổi | Chặn xử lý media | **[CHỜ SƠN]** — hai thiết kế đã xây, chưa chọn |
| U7 | Chủ dự án muốn dừng ngay lập tức | Kill switch đóng cổng, không gỡ được trong phiên | **[ĐÃ TRIỂN KHAI]** với giới hạn ở [§G.5](#g5-giới-hạn-đã-biết-của-kill-switch) |

## B.3 Những việc MeetAI được phép hỗ trợ

- Nhắc lại một thông tin **đã được duyệt**, kèm dẫn nguồn.
- Trả lời **từng phần** mà bằng chứng trực tiếp đỡ được, và **nói rõ phần nào
  thiếu căn cứ**. *(Nguồn: phát ngôn trực tiếp của chủ dự án, 2026-10-08.)*
- **Im lặng.**
- **Đặt câu hỏi** cho chủ dự án.

Hai mục cuối luôn được phép, vì không mục nào nói gì với cuộc họp. Thiết kế có
chủ ý làm cho việc **không nói** dễ viết hơn việc nói.

## B.4 Những việc MeetAI tuyệt đối không làm thay chủ dự án

**[ĐÃ TRIỂN KHAI]** — danh sách này là allowlist ở tầng mã, không phải hướng dẫn
giọng điệu:

> hứa hẹn · xác nhận thay · nhận việc · chốt deadline · bỏ phiếu · phê duyệt
> (tài chính / pháp lý / nhân sự) · tạo bất kỳ tác động ra bên ngoài thay chủ dự án

*(Nguồn: phát ngôn trực tiếp của chủ dự án qua hồ sơ bàn giao.)*

## B.5 Ngoài phạm vi — và vì sao

| Ngoài phạm vi | Lý do | Cưỡng chế bằng gì |
|---|---|---|
| Gửi âm thanh / bản ghi / nội dung họp tới dịch vụ AI bên ngoài | Vi phạm nguyên tắc dữ liệu không ra khỏi máy | Cờ yêu cầu bị **từ chối**; thư viện xuất dữ liệu **không được cài**; biến môi trường liên quan làm app **không khởi động** |
| Huấn luyện mô hình nền từ đầu | Không khả thi với phần cứng một máy cá nhân | — (phạm vi) |
| Học tự động từ nội dung họp | Biến mỗi cuộc họp thành dữ liệu huấn luyện là rủi ro không cần thiết | Không có đường ghi dữ liệu huấn luyện |
| Tự động hoá **tài khoản người dùng** trên nền tảng họp (self-bot, user token, sửa client, lách rate limit) | Trái điều khoản nền tảng | Ranh giới ghi trong quy ước repo; không có mã thực hiện |
| Lưu bản ghi / ghi chú / nhật ký trả lời **theo mặc định** | Là cam kết với người tham gia | Mặc định **tắt**; **[CHỜ SƠN]** |
| Chạy dịch vụ 24/7 | Ứng dụng bật khi cần; mô hình bật/tắt được | — (phạm vi) |
| Giao diện đọc được nội dung cuộc họp | Giảm giá trị của việc chiếm được giao diện | **Không endpoint nào** trả về nội dung họp — thuộc tính thiết kế, có kiểm thử |

## B.6 Những điều **không** được coi là đã chốt

Các cụm dưới đây từng xuất hiện trong tài liệu nền nhưng **không** phải quyết
định có hiệu lực, và tài liệu này **không** dùng chúng làm mục tiêu kỹ thuật:

> "dưới 10 giờ họp/tháng" · "chỉ nhóm kín" · "MVP 2–4 tuần" · "độ trễ 1–2 giây"
> *(là mục tiêu cần đo, **không** phải SLA)* · "máy chủ riêng = chỉ họp nhóm kín"

**[CHỜ SƠN]** Chi phí mục tiêu khoảng **500 000 VND/tháng** là mong muốn chủ dự
án đã nêu, **chưa có estimate nào xác nhận**. Tài liệu này **không** suy ra chi
phí từ đó, và cũng không suy ngược lại.

---

# C. Yêu cầu sản phẩm {#c-yêu-cầu-sản-phẩm}

## C.1 Cách đọc hai bảng dưới

Cột **Trạng thái** phân biệt ba thứ rất khác nhau:

- **[ĐÃ TRIỂN KHAI]** — có mã, có kiểm thử xoá-là-sai.
- **[ĐỀ XUẤT]** — đã thiết kế hoặc đã đặc tả, **chưa có mã**.
- **[CHỜ BẰNG CHỨNG]** / **[CHỜ SƠN]** — bị chặn bởi một phép thử hoặc một
  quyết định, không bởi khối lượng công việc.

## C.2 Yêu cầu chức năng, theo từng luồng

### C.2.1 Luồng họp và lịch

| # | Yêu cầu | Trạng thái |
|---|---|---|
| F1.1 | Lấy sự kiện lịch chỉ-đọc, chỉ metadata cần thiết, không đưa toàn bộ lịch vào mô hình | **[ĐỀ XUẤT]** — cần OAuth, là tác động ra ngoài |
| F1.2 | Chỉ nhận URL/kênh **nằm trong allowlist**; cửa sổ tham gia cấu hình được; **idempotent**; không tự tham gia sự kiện cũ sau khởi động lại | **[ĐÃ TRIỂN KHAI]** trên fixture |
| F1.3 | Múi giờ `Asia/Ho_Chi_Minh` | **[ĐÃ TRIỂN KHAI]** |
| F1.4 | Không tham gia âm thầm khi mô hình / đồng thuận / âm thanh chưa sẵn sàng | **[ĐÃ TRIỂN KHAI]** (báo cáo năng lực từ chối báo `ON` không có lý do) |

### C.2.2 Luồng tiếp nhận nội dung

| # | Yêu cầu | Trạng thái |
|---|---|---|
| F2.1 | Giao diện adapter nền tảng tách **ba mặt phẳng**: điều khiển, gửi ra, nhận vào | **[ĐÃ TRIỂN KHAI]** |
| F2.2 | Adapter phải tự khai năng lực + phiên bản + **bằng chứng**; adapter giả **không được** nhận mình là tích hợp thật | **[ĐÃ TRIỂN KHAI]** — một chuỗi giữ chỗ (`TODO`, `n/a`) **không** được nhận là bằng chứng |
| F2.3 | Nhận âm thanh kênh thoại nhóm bằng danh tính ứng dụng chuẩn | **[CHỜ BẰNG CHỨNG]** — cổng 0-S |
| F2.4 | Ánh xạ một luồng âm thanh về đúng người nói | **[CHỜ BẰNG CHỨNG]** — cổng 0-S |
| F2.5 | Pipeline media có backpressure, hàng đợi có chặn trên, timeout/cancel | **[ĐỀ XUẤT]** — buffer có chặn trên **[ĐÃ TRIỂN KHAI]**, pipeline chưa tồn tại |
| F2.6 | Loại bỏ **trước** nhận dạng tiếng nói các nguồn: không xác định / chưa map / hết hiệu lực / đã thu hồi | **[ĐÃ TRIỂN KHAI]** |

### C.2.3 Luồng tra cứu (retrieval)

| # | Yêu cầu | Trạng thái |
|---|---|---|
| F3.1 | Tra cứu theo **metadata + từ khoá**; **chưa** dùng embedding | **[ĐÃ TRIỂN KHAI]** — embedding cố ý vắng, xem [§J.4](#j4-những-lựa-chọn-tương-lai-và-điều-kiện-để-xét-chúng) |
| F3.2 | Hai tập giữ **riêng bằng kiểu dữ liệu**: tập ứng viên (xếp hạng, **cắt được**) cho phần sinh câu, và tập chứng cứ (**không bao giờ cắt**) cho phần kiểm chứng | **[ĐÃ TRIỂN KHAI]** |
| F3.3 | Phạm vi và mức độ nhạy cảm là **tham số bắt buộc**, không có giá trị mặc định | **[ĐÃ TRIỂN KHAI]** |
| F3.4 | Chỉ tra cứu khi câu hỏi **cần** thông tin riêng của chủ dự án | **[ĐÃ TRIỂN KHAI]** |
| F3.5 | Câu hỏi họp ánh xạ sang **phạm vi nào** | **[CHỜ SƠN]** |

### C.2.4 Luồng đánh giá khả năng trả lời (answerability)

| # | Yêu cầu | Trạng thái |
|---|---|---|
| F4.1 | Ba trạng thái, **chỉ một** trạng thái cho phép nói | **[ĐÃ TRIỂN KHAI]** |
| F4.2 | Đầu vào là **ánh xạ claim ↔ bằng chứng** (một card cho một claim), không phải text + danh sách id phẳng | **[ĐÃ TRIỂN KHAI]** — danh sách phẳng **che** đúng lỗi mà chủ dự án đã nêu tên |
| F4.3 | Không claim nào được qua **chỉ vì** module không nhận ra nó | **[ĐÃ TRIỂN KHAI]** — claim không có giá trị nhận diện được phải là **trích dẫn nguyên văn** của card nó dẫn |
| F4.4 | Card bị sửa **sau khi** duyệt phải trở thành không dùng được | **[ĐÃ TRIỂN KHAI]** — card ghi dấu nội dung **lúc duyệt**, so với dấu hiện tại; thiếu dấu là **không** citable |
| F4.5 | 16 nhãn của bộ dữ liệu đánh giá | **[CHỜ SƠN]** — xem [§H.4](#h4-16-nhãn-đánh-giá-và-vì-sao-chúng-không-thể-tự-duyệt) |

### C.2.5 Cổng quyền hạn (authority gate)

| # | Yêu cầu | Trạng thái |
|---|---|---|
| F5.1 | **Ba lớp độc lập**, không lớp nào được bỏ vì "lớp kia đã lo" | **[ĐÃ TRIỂN KHAI]** |
| F5.2 | Không mức độ tin cậy nào mở được hành vi bị cấm tuyệt đối | **[ĐÃ TRIỂN KHAI]** |
| F5.3 | Mô hình ngôn ngữ **không tự cấp quyền**: nó chặn hoặc xin hỏi được, **không cho phép được** | **[ĐÃ TRIỂN KHAI]** |
| F5.4 | Mọi vi phạm có **mã quy tắc ổn định**, để một mẫu quá rộng chẩn đoán được | **[ĐÃ TRIỂN KHAI]** |
| F5.5 | Khử dấu **trước** khi so khớp; `đ` xử lý riêng vì nó là chữ cái riêng mà phép chuẩn hoá Unicode không tách | **[ĐÃ TRIỂN KHAI]** |
| F5.6 | Giới hạn của từ điển mẫu được ghi thành kiểm thử, có **trần chỉ được giảm** | **[ĐÃ TRIỂN KHAI]** |
| F5.7 | Ngưỡng tin cậy tối thiểu đã được calibrate | **[CHỜ BẰNG CHỨNG]** — hiện là **placeholder**, cần số trên bộ eval tiếng Việt |

### C.2.6 Luồng phát ngôn (output)

| # | Yêu cầu | Trạng thái |
|---|---|---|
| F6.1 | Mọi đầu ra đi qua **đúng một** biểu thức phát; cổng chạy **trước** nó trong cùng hàm | **[ĐÃ TRIỂN KHAI]** — kiểm bằng phân tích cú pháp |
| F6.2 | Kết quả phát **không có trường chứa văn bản** đã phát | **[ĐÃ TRIỂN KHAI]** |
| F6.3 | Phân biệt *sink tự khai từ chối* / *không rõ* (**mặc định**) / *chưa thử*; **không trạng thái nào retry** | **[ĐÃ TRIỂN KHAI]** |
| F6.4 | Tự giới thiệu là trợ lý AI khi vào họp | **[ĐÃ TRIỂN KHAI]** phần văn bản; chưa có đường vào họp |
| F6.5 | Một nơi phát tới được cuộc họp | **[CHỜ SƠN]** + **[CHỜ BẰNG CHỨNG]** |
| F6.6 | Hủy giữa dòng khi có lời mới / thu hồi đồng thuận / rời / kết phiên | **[ĐÃ TRIỂN KHAI]** phần đăng ký hủy |

### C.2.7 Kill switch

| # | Yêu cầu | Trạng thái |
|---|---|---|
| F7.1 | Đóng cổng **ngay** và **không gỡ được** trong phiên | **[ĐÃ TRIỂN KHAI]** |
| F7.2 | Vô hiệu mọi lần kiểm lại ở cả cổng và sổ ghi | **[ĐÃ TRIỂN KHAI]** |
| F7.3 | Loại buffer **kể cả** với bên đang giữ nó | **[ĐÃ TRIỂN KHAI]** |
| F7.4 | **Yêu cầu** hủy các công việc đã đăng ký | **[ĐÃ TRIỂN KHAI]** |
| F7.5 | "Dừng mọi công việc" | **[KHÔNG tuyên bố]** — xem [§G.5](#g5-giới-hạn-đã-biết-của-kill-switch) |

## C.3 Yêu cầu phi chức năng

| # | Yêu cầu | Nghĩa cụ thể | Trạng thái |
|---|---|---|---|
| N1 | **Local-first** | Không đường gửi dữ liệu ra ngoài tồn tại trong môi trường chạy | **[ĐÃ TRIỂN KHAI]** |
| N2 | **Fail-closed** | Quyết định chưa trả lời là một trạng thái **chặn**, không phải một giá trị mặc định "hợp lý" | **[ĐÃ TRIỂN KHAI]** |
| N3 | **Quyền riêng tư** | Nhật ký **chỉ metadata**, theo allowlist; thông báo lỗi mô tả **hình dạng**, không mô tả giá trị | **[ĐÃ TRIỂN KHAI]** |
| N4 | **Khả năng truy vết** | Mỗi nghĩa vụ có dòng trong đặc tả, trỏ tới mã và tới kiểm thử | **[ĐÃ TRIỂN KHAI]** — 72 dòng |
| N5 | **Tái lập** | Cùng đầu vào cho **cùng byte** đầu ra | **[ĐÃ ĐO]** — 3 lần chạy × 4 lệnh, dấu kiểm trùng |
| N6 | **Khả năng dừng** | Dừng được bằng một hành động, và việc dừng **không gỡ được** | **[ĐÃ TRIỂN KHAI]** với giới hạn đã ghi |
| N7 | **Độ trễ đầu-cuối** | — | **[CHỜ BẰNG CHỨNG]** — phụ thuộc quyết định về đường suy luận |
| N8 | **Độ ổn định dưới tải** | — | **[CHỜ BẰNG CHỨNG]** — xem [§H.5](#h5-kết-quả-benchmark--và-phạm-vi-của-từng-con-số) |

## C.4 Yêu cầu đã có kiểm thử, so với yêu cầu còn cần thiết kế

**[ĐÃ ĐO]** Trong **72** dòng nghĩa vụ của đặc tả, **58** mang nhãn `tested`.
Phần còn lại, nêu đầy đủ chứ không chọn lọc:

| Dòng | Nghĩa vụ | Trạng thái và vì sao |
|---|---|---|
| A-6, A-7 | Nhận inbound audio nhóm; ánh xạ luồng → người nói | `gated:0-S` — **thật sự chưa có bằng chứng** |
| A-8 | Quan sát thứ tự *packet → giải mã → PCM → nhận dạng* trên một bản dựng cụ thể | `gated:0-C` |
| C-13 | Không gửi kết quả nhận dạng dở dang để tự kích lời nói | `absent` — chưa có nhận dạng tiếng nói |
| M-7 | Connector lịch với quyền đọc hẹp nhất | `absent` — cần OAuth, là **tác động ra ngoài** |
| K-8 | Embedding chỉ thêm nếu benchmark chứng minh có cải thiện | `absent` — **cố ý** |
| B-1 | Benchmark nhận dạng tiếng Việt đủ sáu trục | **phép hội**, 3 trục chưa đạt — [§H.5](#h5-kết-quả-benchmark--và-phạm-vi-của-từng-con-số) |
| B-2 | Benchmark mô hình ngôn ngữ lượng tử hoá, kèm nhiệt/điện/chi phí | `đạt một phần` |
| B-3 | Artifact mô hình tách khỏi ứng dụng, ghim phiên bản/dấu/license | `partial` — bốn cổng cấp B |

---

# D. Trạng thái hiện tại và kiến trúc {#d-trạng-thái-hiện-tại-và-kiến-trúc}

## D.1 Kiến trúc **hiện tại** — mã thật, chạy thật

> **Đọc sơ đồ này như một bản ghi, không như một thiết kế.** Mỗi khối dưới đây
> tồn tại trong mã nguồn hôm nay và có kiểm thử đứng sau.

```
                    ┌──────────────────────────────────┐
                    │  Supervisor + Local Web UI       │
                    │  (loopback, telemetry tắt)       │
                    │  Start/Stop · health · kill      │
                    └───────────────┬──────────────────┘
                                    │
   câu hỏi (hằng số trong module, KHÔNG đọc file nào)
        │
        ▼
 ┌─────────────────┐   ┌──────────────────────────────────────┐
 │ retrieval       │──▶│ knowledge store                      │
 │ metadata +      │   │ duyệt · dấu nội dung lúc duyệt ·     │
 │ từ khoá         │   │ thay thế · hiệu lực · độ nhạy cảm    │
 └─────────────────┘   └──────────────────┬───────────────────┘
        │                                 │
        │  candidates (cắt được)          │  witnesses (KHÔNG cắt)
        ▼                                 ▼
 ┌──────────────────────────────────────────────────────────┐
 │ answerability — 3 trạng thái, chỉ 1 cho phép nói         │
 │ đầu vào: ánh xạ claim ↔ bằng chứng                       │
 └──────────────────────────┬───────────────────────────────┘
                            │
                            ▼
 ┌──────────────────────────────────────────────────────────┐
 │ authority gate — 3 lớp độc lập                           │
 │ (0) allowlist loại hành vi  (1) từ chối loại tự khai     │
 │ (2) soi văn bản bất kể khai gì                           │
 └──────────────────────────┬───────────────────────────────┘
                            │  đúng MỘT biểu thức phát
                            ▼
                 ┌─────────────────────────┐
                 │ RecordingSink           │
                 │ danh sách TRONG BỘ NHỚ  │
                 │ chỉ dùng cho kiểm thử   │
                 └─────────────────────────┘

 Cổng chạy song song, kiểm trên MỌI đường media:
   consent gate · session lifecycle · media gate   ← cả ba fail-closed
```

**Điều quan trọng nhất của sơ đồ này không phải các khối, mà là thứ KHÔNG có
trong nó.** Không có khối nào cho: nhận âm thanh vào, nhận dạng tiếng nói, suy
luận mô hình, kết nối nền tảng họp, hay lưu trữ bền vững. Nơi phát duy nhất
trong mã nguồn là một **danh sách trong bộ nhớ** dùng cho kiểm thử.

Nói thẳng: **phần đã chạy được là lõi quyết định, không phải sản phẩm.**

## D.2 Kiến trúc **mục tiêu** — chưa tồn tại

> **ĐỌC KỸ:** sơ đồ dưới đây là **[ĐỀ XUẤT]**. Mọi khối đánh dấu `⟦CHƯA CÓ⟧`
> **không tồn tại trong mã nguồn hôm nay**. Hai sơ đồ được vẽ khác nhau có chủ
> ý, để không ai đọc sơ đồ mục tiêu thành bản mô tả hiện trạng.

```
  Google Calendar (read-only, chỉ khi app đang chạy)   ⟦CHƯA CÓ⟧
                 │ event + URL họp
                 ▼
 ┌───────────────────────────────────────────────────────────────┐
 │ Desktop Supervisor          ✔ ĐÃ CÓ (UI loopback, kill switch)│
 ├───────────────────────────────────────────────────────────────┤
 │ Meeting Planner             ✔ ĐÃ CÓ (trên fixture)            │
 │ Platform Adapter — control  ✔ ĐÃ CÓ (interface + adapter giả) │
 │ Platform Adapter — inbound  ⟦CHƯA CÓ⟧  ← cổng 0-S             │
 │ Session & Consent Gate      ✔ ĐÃ CÓ (fail-closed)             │
 │ Media Pipeline  jitter→VAD  ⟦CHƯA CÓ⟧                         │
 │ ASR tiếng Việt              ⟦CHƯA CÓ trong đường chạy⟧        │
 │ Context & Knowledge         ✔ ĐÃ CÓ                           │
 │ Response Policy             ✔ ĐÃ CÓ                           │
 │ Local Model Runtime         ⟦CHƯA CÓ trong đường chạy⟧        │
 │ Local Data Vault            ⟦CHƯA CÓ⟧  ← cổng 0-U             │
 │ TTS / voice                 ⟦CHƯA CÓ⟧ — không phải phụ thuộc MVP│
 └───────────────────────────────────────────────────────────────┘
```

**[ĐÃ ĐO]** Phép đếm đi kèm: trong 12 khối của kiến trúc mục tiêu, **6 đã có**,
**6 chưa có**. Nhưng phép đếm đó **không** đo được khối lượng còn lại — khối
"ASR tiếng Việt" và khối "Response Policy" không phải hai đơn vị so sánh được.

## D.3 Data flow dự kiến và ranh giới tin cậy

```
 ┌─ VÙNG KHÔNG TIN CẬY ───────────────────────────────────────┐
 │  Âm thanh từ nền tảng họp · transcript · nội dung do người │
 │  khác nói · text tự nhận có quyền                          │
 └──────────────────────┬─────────────────────────────────────┘
                        │  RANH GIỚI 1: consent / media gate
                        │  loại trước ASR: unknown · unmapped
                        │  · stale · revoked
                        ▼
 ┌─ VÙNG DỮ LIỆU PHIÊN (ephemeral) ──────────────────────────┐
 │  Lượt thoại gần nhất, trong bộ nhớ, bọc trong MeetingContent│
 │  __repr__ chỉ in HÌNH DẠNG, không in nội dung              │
 └──────────────────────┬─────────────────────────────────────┘
                        │  RANH GIỚI 2: retrieval scope + sensitivity
                        │  (hai tham số BẮT BUỘC, không default)
                        ▼
 ┌─ VÙNG TRI THỨC ĐÃ DUYỆT ──────────────────────────────────┐
 │  Card: duyệt · dấu-lúc-duyệt · hiệu lực · phạm vi · độ nhạy│
 └──────────────────────┬─────────────────────────────────────┘
                        │  RANH GIỚI 3: answerability
                        │  (claim phải map được tới bằng chứng)
                        ▼
 ┌─ VÙNG ĐỀ XUẤT PHÁT NGÔN ──────────────────────────────────┐
 │  Mô hình chỉ ĐỀ XUẤT. Nó không cấp quyền cho chính nó.    │
 └──────────────────────┬─────────────────────────────────────┘
                        │  RANH GIỚI 4: authority gate (3 lớp)
                        ▼
                   nơi phát  —  hoặc IM LẶNG
```

**Chỉ thị tiêm (prompt injection) đi được tới đâu:** nó tới được mô hình, và tối
đa đổi được **điều mô hình đề xuất**. Ranh giới 4 vẫn soi đề xuất đó. Một đoạn
text tự nhận có quyền **không vì thế mà có quyền**. **[ĐÃ TRIỂN KHAI]**

## D.4 Bốn ranh giới an toàn, và cơ chế đỡ chúng

### (a) Vắng mặt năng lực, không phải cấu hình năng lực

Đây là **nguyên tắc chi phối** toàn bộ dự án. Một đường gửi dữ liệu ra ngoài bị
chặn vì **thư viện cần thiết không được cài**, chứ không vì "chưa cấu hình". Một
cấu hình có thể bị đổi; một thứ không tồn tại thì không.

Nguyên tắc này được áp dụng nhất quán tới mức **các ngưỡng an toàn chưa duyệt
cũng được biểu diễn bằng sự vắng mặt**: hằng số ngưỡng RAM mang giá trị *không
có giá trị*, và cổng từ chối **trước khi đọc bộ nhớ**. Hệ quả đo được: truyền
vào một lượng RAM vô lý lớn vẫn bị từ chối, nên **không lượng RAM nào** biến nó
thành cho qua.

### (b) Quyết định chưa trả lời là một trạng thái CHẶN

Các lựa chọn về đồng thuận và lưu trữ chưa được đưa ra, và chúng được biểu diễn
bằng một trạng thái "chờ quyết định" **chặn mọi xử lý âm thanh** — không phải
bằng một giá trị mặc định do máy tự chọn. **Ba chỗ từ chối độc lập** cùng kiểm
điều kiện này.

Một chi tiết kỹ thuật đáng nêu vì nó là một cái bẫy thật: trạng thái "chờ quyết
định" phải là một thành viên **falsy** của kiểu liệt kê. Nếu kiểu liệt kê trộn
với chuỗi, thành viên đó trở thành **truthy**, và một phép kiểm trông như một
guard hợp lý sẽ **fail open** đúng vào trạng thái phải chặn.

### (c) Danh sách cho phép, không phải danh sách cấm

Lặp lại nhiều lần trong dự án: **một danh sách cấm thua ngay cái tên mới đầu
tiên.** Nhật ký chỉ ghi các trường trong allowlist; chỉ hai tên tệp thực thi
được nhận trên dòng lệnh; chỉ các thư mục **tương đối trong dự án** được dùng
làm nơi ghi.

Ví dụ cụ thể về vì sao allowlist thắng: yêu cầu "đường dẫn phải tương đối trong
dự án" chặn **cả** ổ mạng **và** thư mục đồng bộ đám mây **mà không cần nhận ra
cái nào** — trong khi một danh sách cấm sẽ phải nhận diện ổ mạng (cần gọi API
hệ điều hành) và thư mục đồng bộ (cần một danh sách tên nhà cung cấp luôn thay
đổi và bị bản địa hoá).

### (d) Thông báo lỗi mô tả hình dạng, không mô tả giá trị

Một lỗi in ra `"không đọc được phát ngôn (42 ký tự)"`, **không** in nội dung.
**[ĐÃ TRIỂN KHAI]** Có kiểm thử ghép một thông tin đăng nhập giả vào **mọi** kiểu
cấu hình sai và khẳng định nó không xuất hiện ở bất kỳ đầu ra nào — kể cả trong
chuỗi hoá của đối tượng lỗi.

Lý do kỹ thuật: thư viện xác thực cấu hình **nhúng dữ liệu đầu vào thô** vào lỗi,
và với lỗi ở mức toàn mô hình thì dữ liệu đó là **toàn bộ** mapping cấu hình.
In nó ra sẽ đưa đuôi của một credential lên đầu ra.

## D.5 Cổng quyền hạn — ba lớp, và sự độc lập là thiết kế

| Lớp | Làm gì | Vì sao không thể bỏ |
|---|---|---|
| **0** | Đề xuất phải khai một **loại hành vi được phép**; không khai thì **bị từ chối**, không có mặc định | Một mặc định ở đây là một quyền được cấp âm thầm |
| **1** | Từ chối các loại hành vi **tự khai** nằm trong danh sách cấm tuyệt đối | Bắt được trường hợp mô hình thành thật về việc nó định vượt quyền |
| **2** | **Soi văn bản** bằng từ điển mẫu, **bất kể** nó khai gì | Bắt được trường hợp mô hình khai một loại vô hại rồi viết một cam kết |

Từ điển mẫu ở lớp 2 **thiên về từ chối một cách có chủ ý**: một lần im lặng sai
là một bất tiện; một cam kết trái phép nhân danh người khác thì không. Hai thứ
đó **không so sánh được**, nên việc so khớp được làm rộng có ý thức.

**Giới hạn đã biết của từ điển được ghi thành kiểm thử, không che.** Một lỗ đã
biết nằm trong bộ kiểm thử tốt hơn một lỗ phát hiện trong lần dùng thật, và
trần của sổ ghi lỗ **chỉ được giảm**.

**Một đính chính quan trọng, vì nó từng bị nói sai:** không được nói rằng "phần
còn lại của cổng ràng buộc một lỗ của từ điển". Một lần rà soát đã chứng minh
điều đó **sai** đúng vào tình huống quan trọng nhất — một lỗ đã biết được **cho
phép** khi MeetAI được gọi trực tiếp với độ tin cậy bình thường, mà đó là tình
huống duy nhất nó sẽ nói. **Lỗ của từ điển là lỗ thật, không phải lỗ đã được
bù.**

## D.6 Dry-run cấp 2 và giới hạn của bằng chứng tổng hợp {#d6-dry-run-cấp-2-và-giới-hạn-của-bằng-chứng-tổng-hợp}

**[ĐÃ TRIỂN KHAI] + [ĐÃ ĐO]** Có một lệnh chạy được ngay, đẩy các tình huống
tổng hợp qua toàn bộ đường quyết định vào một nơi phát trong bộ nhớ:

```bash
meetai status           # cấu hình + bảng năng lực
meetai dry-run          # 12 tình huống qua boundary, báo cáo người đọc
meetai dry-run --json   # cùng dữ liệu, dạng máy đọc
```

**[ĐÃ ĐO] 2026-10-11:** cả ba lệnh kết thúc exit 0. `dry-run` cho **12 tình
huống, 1 được nói, 11 im lặng**, và **dấu kiểm MD5 trùng khít qua 3 lần chạy**.

**Mỗi lý do im lặng được in ra**, và chúng khác nhau: thiếu giá trị · sai chủ đề
· hai card mâu thuẫn · không kiểm được · chưa duyệt · card thuộc phạm vi riêng
tư · cắt tập ứng viên không che được mâu thuẫn.

**Hai lớp độc lập, và lớp sau không thấy lớp trước:** có tình huống trong đó
phần đánh giá khả năng trả lời **đồng ý** mà cổng quyền hạn vẫn **từ chối**.

**Báo cáo tự khai cấp độ bằng DỮ LIỆU, không bằng lời:** trường
`is_production_integration = false`, `is_discord_test = false`.

### Dry-run này KHÔNG chứng minh gì

Nói đầy đủ, vì đây là chỗ dễ đọc trượt nhất trong cả tài liệu:

- **Không** chứng minh chất lượng mô hình — **không có mô hình nào chạy**.
- **Không** chứng minh nhận dạng tiếng Việt — **không có âm thanh nào**.
- **Không** chứng minh dùng được trong họp thật — các card là **hằng số viết
  riêng cho đường này**, không phải transcript.
- **Không** chứng minh khả năng tổng quát hoá: 12 tình huống tổng hợp, do chính
  tác nhân kỹ thuật viết.
- **Không** chứng minh ngưỡng tin cậy đã được calibrate.
- **Không** nói gì về nền tảng họp, lưu trữ, hay media.

Nó chứng minh **đúng một việc**: lõi quyết định chạy **tất định** trên dữ liệu
hằng số và **không để lại dấu vết trên đĩa** — điều cuối được đo bằng cách theo
dõi mọi lời gọi mở tệp ở tầng tiến trình, đối chiếu trên ảnh chụp gần 9 000
đường dẫn.

### Phần dư đã đo của dry-run

| Phần dư | Nội dung |
|---|---|
| Nơi phát | Danh sách **công khai, thay đổi được**, giữ nguyên văn câu đã phát trong bộ nhớ. Thứ ngăn việc đọc trực tiếp là **kiểm thử cấu trúc**, không phải kiểu dữ liệu |
| Báo cáo người đọc | Là **tập con thực sự** của dạng JSON — 10 trường chỉ có ở JSON |
| Một phép kiểm tripwire | Nằm **ngoài** khối bắt lỗi, nên nếu nó kích hoạt thì ra traceback chứ không ra mã lỗi gọn. Chỉ tới được qua một đường bỏ qua xác thực |

---

# E. Tech stack {#e-tech-stack}

## E.1 Cách đọc bảng này

Cột **Trạng thái** có **ba** giá trị, và việc trộn chúng là chính cái tài liệu
này muốn tránh:

- **đang dùng** — đã cài trong môi trường chạy, có phiên bản khoá trong tệp
  lock.
- **ứng viên** — đã benchmark hoặc đã khảo sát, **chưa chốt kiến trúc**.
- **đang chờ** — bị một quyết định hoặc một cổng bằng chứng chặn.

**Không mục "ứng viên" nào được gọi là stack đã chốt.** **[ĐÃ ĐO]** Mọi phiên
bản ở hàng "đang dùng" đọc trực tiếp từ `pyproject.toml` và tệp lock, 2026-10-11.

## E.2 Nền tảng và lõi — đang dùng

| Thành phần | Phiên bản | Trạng thái | Vai trò | Lý do chọn | Hạn chế | License |
|---|---|---|---|---|---|---|
| Python | **3.12** (khoá) | **đang dùng** | Ngôn ngữ lõi và cùng hệ sinh thái với model runtime | Quyết định của chủ dự án; cho phép lõi và runtime cùng một ngôn ngữ | Chủ dự án nhấn mạnh: chọn stack **không** phải bằng chứng cho cổng 0-S | PSF |
| uv | — | **đang dùng** | Quản lý phụ thuộc, khoá phiên bản | Khoá tái lập được; không cài tool toàn cục | — | Apache-2.0 / MIT |
| pydantic | **2.13.5** | **đang dùng** | Xác thực cấu hình có kiểu | Xác thực ở **mức trường**, nên lỗi chỉ mang giá trị của trường đó | Lỗi ở mức **mô hình** nhúng **toàn bộ** mapping → bắt buộc dùng hàm làm sạch | MIT |
| pydantic-settings | **2.15.0** | **đang dùng** | Nạp cấu hình | Cùng hệ pydantic | — | MIT |
| python-dotenv | ≥1.2 | **đang dùng** | Đọc tệp cấu hình mẫu | Khai **tường minh** dù là phụ thuộc gián tiếp, vì mã lõi import nó trực tiếp | — | BSD-3-Clause |
| pytest | **9.1.1** | **đang dùng** (dev) | Kiểm thử | — | Cấu hình tắt in biến cục bộ trong traceback: biến đó có thể giữ credential | MIT |
| ruff | **0.16.10** | **đang dùng** (dev) | Format + lint, 15 nhóm quy tắc | Một công cụ cho cả hai; nhanh | — | MIT |
| mypy | **2.4.0** | **đang dùng** (dev), **strict** | Kiểm kiểu | Chế độ strict bắt được lớp lỗi mà kiểm thử không bắt | — | MIT |
| httpx | **0.28.1** | **đang dùng** (dev) | Client cho kiểm thử giao diện web | Phụ thuộc của bộ kiểm thử | **Là một client HTTP thật trong môi trường dev** — ghi ra đây chứ không che | BSD-3-Clause |

## E.3 Giao diện web cục bộ — đang dùng, có điều kiện

| Thành phần | Phiên bản | Trạng thái | Ghi chú |
|---|---|---|---|
| FastAPI | **`==0.142.2`** — ghim **chính xác** | **đang dùng** (extra `ui`) | Ghim `>=` **không giữ được** một lần review về telemetry mặc định |
| uvicorn | **0.54.0** | **đang dùng** (extra `ui`) | Chỉ bind loopback dạng số |
| starlette | 1.7.0 | gián tiếp | **Không** cài `CORSMiddleware`, **không** WebSocket |
| opentelemetry-api | 1.45.1 | gián tiếp, **không tránh được** | Là phụ thuộc cứng của FastAPI |
| opentelemetry-**sdk** | — | **CỐ Ý VẮNG MẶT** | Thứ **phải** vắng |

**[ĐÃ ĐO] Vì sao ghim chính xác, và vì sao SDK phải vắng.** Phiên bản FastAPI
này có **hệ thống telemetry riêng**, mọi tín hiệu **mặc định bật**, endpoint đọc
từ biến môi trường, và nhánh ghi log sẽ ghi **thông báo lỗi**, **nội dung
request** và **lỗi xác thực kèm giá trị đầu vào gốc**. Nó **không export được
chỉ vì SDK chưa được cài** — không phải vì "chưa cấu hình exporter", và cơ chế
chặn thực tế là một lỗi import bị bắt rồi hạ xuống một cảnh báo.

Hệ quả đã được cưỡng chế: **bốn** biến thể cài kèm của FastAPI bị cấm vì cả bốn
đều kéo SDK vào; một kiểm thử khẳng định cấu hình đã giải quyết bằng **phép so
khớp từ điển chính xác**, nên một tín hiệu mới ở phiên bản sau sẽ làm kiểm thử
sai cho tới khi có người tắt nó tường minh; và `FastAPI(...)` chỉ được gọi ở
**đúng một** chỗ, có kiểm thử phân tích cú pháp đứng sau.

**Ba quyết định bảo mật khác của giao diện, cùng lý do:**

- **Tài liệu API tích hợp bị tắt** — chúng serve HTML trỏ tới **bốn host thứ
  ba**, và guard biến môi trường **không thấy được**: request đi từ browser,
  không từ tiến trình này.
- **Mọi request đổi trạng thái cần một header riêng và phải là POST** — bất kỳ
  trang web đang mở cũng POST tới loopback được, và tác động vẫn xảy ra; cơ chế
  CORS quản việc **đọc** phản hồi, **không** quản việc **gửi**.
- **Bind thất bại phải kết thúc với mã lỗi và KHÔNG tự đổi cổng.** **[ĐÃ ĐO]**
  máy chủ phát ra `SystemExit`, không phải lỗi hệ điều hành — đo ra, không đoán.
  Tự đổi cổng chính là cuộc tấn công chiếm cổng do mình tự thực hiện.

## E.4 Mô hình, runtime và dữ liệu — ứng viên, **chưa chốt** {#e4-mô-hình-runtime-và-dữ-liệu--ứng-viên-chưa-chốt}

| Thành phần | Trạng thái | Vai trò | Đã đo gì | Hạn chế đã ghi | License | Nguồn xác minh |
|---|---|---|---|---|---|---|
| **Qwen3-4B-Q4_K_M** (GGUF) | **ứng viên** | Mô hình ngôn ngữ | 43 tình huống × 2 lần chạy, 5 trục riêng, output tất định | **Lệch mạnh về phía trả lời** — xem [§H.5](#h5-kết-quả-benchmark--và-phạm-vi-của-từng-con-số) | **apache-2.0** (tag repo), ungated | Ghi chú S2.3; digest SHA-256 do harness **tự tính lại** |
| **llama.cpp** (bản dựng Windows CUDA) | **ứng viên** | Runtime suy luận | Dùng cho mọi benchmark mô hình ngôn ngữ | Là đường **CLI**, **không** phải kiến trúc production | MIT | Ghi chú S2.3 (bản dựng + commit được ghim) |
| **whisper.cpp** + `ggml-small` | **ứng viên** | Nhận dạng tiếng nói | 361 clip, 0 failure | Mô hình `small`, không phải lựa chọn cuối | Mô hình **MIT**; runtime MIT | Ghi chú S2.2 (SHA-256 của cả mô hình và zip runtime) |
| **FLEURS** `vi_vn` dev | **đang dùng** (eval) | Bộ đo nhận dạng | 361 clip / 10 422 âm tiết / 4 299,5 s | Văn bản tin/wiki, **không** phải lời nói trong họp | **CC-BY-4.0**, ungated | `google/fleurs`, revision được ghim |
| **VietMed** (test subset) | **đang dùng** (chỉ thăm dò) | Trục giọng vùng | 421 clip | Domain **y tế**; giọng **lồng gần hoàn toàn** với người nói | **[CHỜ BẰNG CHỨNG]** — paper ghi CC BY 4.0, tag ghi MIT; **cả hai permissive** | API dataset; mâu thuẫn hai nguồn đã ghi |
| **Discord** platform | **đang chờ** | Nền tảng họp đầu tiên | — | Route nhận audio **chưa được chứng minh** | — | Xem [§G.6](#g6-nền-tảng-họp--điều-khoản-chính-thức-đã-đọc-được) |
| Google Calendar / OAuth | **đang chờ** | Nguồn lịch | — | Cần tạo OAuth app = **tác động ra ngoài** | — | — |
| Lưu trữ bền vững (đề xuất: SQLite cục bộ) | **đang chờ** | Vault dữ liệu | — | Bị cổng 0-U chặn; **chưa có mã persistence nào** | — | — |
| Desktop app đóng gói | **đang chờ** | Thay giao diện web | — | Đánh giá lại **sau** khi workflow ổn định | — | — |
| Containerization (Docker) | **không trong phạm vi hiện tại** | — | — | Một máy, một người dùng; thêm vào là phức tạp không có nhu cầu | — | — |
| Embedding / RAG vector | **không trong phạm vi hiện tại** | — | — | Chỉ thêm **nếu** benchmark chứng minh cải thiện | — | Đặc tả dòng K-8, `absent` **cố ý** |
| `huggingface_hub` | **BỊ TỪ CHỐI** | — | — | Quyết định theo uỷ quyền #4 — xem [§I.4](#i4-năm-quyết-định-đã-đưa-ra-theo-uỷ-quyền) | — | Sự vắng mặt **nay có kiểm thử ghim** |

## E.5 Hai điều phải nói rõ về stack mô hình

**(1) [CHỜ SƠN] Digest của mô hình thật chưa được ghim.** Sổ ghi digest hiện
**rỗng**, và rỗng **theo quyết định**, không do sơ sót — nó làm mọi lần chạy bị
từ chối. Ghim một giá trị là **khẳng định rằng một tệp cụ thể là tệp đúng**, và
đó là một phát biểu về máy của chủ dự án và về lần tải của chủ dự án.

**(2) [CHỜ BẰNG CHỨNG] License đã xác nhận ở mức repo, chưa ở mức artifact.**
Tag license của repo mô hình là `apache-2.0`, và điều đó đã được xác minh từ
API. Nhưng **một tag ở mức repo không tự xác minh quyền với mọi thành phần**
trong đó. Với các tài nguyên có license phi thương mại, chủ dự án đã chốt
nguyên tắc: cho phép thử nghiệm **riêng tư**, nhưng phải **tách nhãn rõ trong
báo cáo**, và tài nguyên đó **không** đủ điều kiện cho sản phẩm hay thương mại
hoá.

**[ĐÃ ĐO] Không dependency nào được thêm chỉ để tài liệu trông đầy đủ.** Toàn bộ
gói CUDA và runtime mô hình nằm **ngoài** `pyproject.toml`, trong các môi
trường ảo riêng dưới thư mục artifact. Thư mục benchmark nằm **ngoài** gói lõi
một cách có chủ ý, để hai bất biến của gói lõi (không import framework, không
giá trị trong thông báo lỗi) vẫn **đúng thật** thay vì bị nới — và hệ quả phải
nói rõ: **hai bất biến đó không bao phủ thư mục benchmark.**

---

# F. Hạ tầng và giới hạn máy {#f-hạ-tầng-và-giới-hạn-máy}

## F.1 Máy tham chiếu — và nó là gì, không là gì

**[ĐÃ ĐO]** Các số dưới đây là của **một máy tham chiếu duy nhất** — một máy
tính xách tay cá nhân — và **không** phải đặc tả tối thiểu, **không** phải cấu
hình đề nghị, **không** phải cơ sở để suy ra số phiên đồng thời hay SLA.

| Đại lượng | Giá trị | Nguồn / điều kiện đo |
|---|---|---|
| Hệ điều hành | Windows 11 | Chủ dự án nêu |
| CPU | Intel i7-9750H | Chủ dự án nêu |
| RAM tổng | **16 GB** | Chủ dự án nêu |
| GPU | **GTX 1660 Ti, 6 GB** (6144 MiB) | Chủ dự án nêu; VRAM đọc từ mọi artifact benchmark |

## F.2 Bốn đại lượng bộ nhớ — và vì sao phải tách chúng {#f2-bốn-đại-lượng-bộ-nhớ--và-vì-sao-phải-tách-chúng}

Đây là phần kỹ thuật quan trọng nhất của mục F, vì ba trong bốn đại lượng dưới
đây **thường bị gọi chung là "RAM trống"**, và chúng không phải một thứ.

| Đại lượng | Giá trị đo được | Nghĩa thật |
|---|---|---|
| **RAM khả dụng** lúc đo | **3 966 MiB** → **2 897 MiB** *(hai lần đo trong **cùng một lượt**)* | **KHÔNG phải "RAM trống"**: đại lượng này là *standby + free + zero*, tức **bao gồm cả vùng nhớ đệm**. Đó chính là lý do nó dao động mạnh |
| **Mức trần commit** của một tiến trình | **2 423 MiB** | **Thấp hơn cả hai số trên**, và **cổng hiện tại không đọc đại lượng này** |
| **Đỉnh working set** của một lần chạy mô hình trên **CPU** | **4 438 MiB** | **n = 1.** Lấy mẫu mỗi 300 ms |
| Đỉnh working set của một lần chạy trên **GPU** | **2 794–2 868 MiB** | **n = 4**, độ tản **≈ 46 MiB** |

### Rủi ro cụ thể, nói thẳng

**Đỉnh bộ nhớ đã quan sát (4 438 MiB) CAO HƠN lượng RAM khả dụng đo được
(2 897–3 966 MiB), và cao hơn nhiều so với mức trần commit (2 423 MiB).** Một
lần chạy mô hình trên CPU ở máy này **có thể làm hệ thống hết bộ nhớ**.

Và "còn chỗ" đọc một lần **không** phải bằng chứng cho lần chạy kế tiếp: hai số
3 966 → 2 897 được đo trong **cùng một lượt làm việc**, và số thứ hai nằm **dưới
cả** ngưỡng mà cổng GPU đang dùng (3 380 MiB). Cổng là phép kiểm **lúc khởi
động**, không phải một bảo đảm trong suốt lần chạy.

### Hai chiều sai số, và vì sao chúng KHÔNG triệt tiêu nhau

- Phép lấy mẫu mỗi 300 ms **bỏ sót** một đỉnh giữa hai mẫu. ⇒ 4 438 là **chặn
  dưới của đỉnh thật**.
- Working set **đếm cả trang file-backed** của mô hình nạp theo tệp, mà những
  trang đó **có thể bị thu hồi**. ⇒ 4 438 **nói quá nhu cầu thật**.

Hai chiều ngược nhau. Nhưng **không ai biết biên độ của chiều nào**, nên **không
thể nói chúng bù trừ**. Một con số vừa là chặn dưới của thứ này vừa là chặn
trên của thứ khác thì **không phải chặn của cái gì cả** theo nghĩa dùng được cho
một cổng an toàn.

### n = 1 nghĩa là không có ước lượng biến thiên

Cổng GPU dùng đỉnh **lớn nhất của 4 lần đo**, nên biên cộng thêm của nó là một
biên **so sánh được** với độ tản đã thấy (≈ 46 MiB). Phía CPU **chỉ có một lần
đo**, nên **không có độ tản nào** để so. Đó là **khác biệt thật** giữa hai cổng,
không phải chuyện cẩn thận nhiều hay ít.

### Tầng hệ điều hành giúp ít hơn tưởng

**[ĐÃ ĐO]** Ba kết luận rút từ tài liệu chính thức của nhà sản xuất hệ điều hành:

1. **Giới hạn bộ nhớ theo nhóm tiến trình không chặn trọng số mô hình.** Cơ chế
   đó tác động lên lượng **commit**, nhưng trọng số được nạp **theo tệp** nên
   **không bị tính** vào commit. Giới hạn ấy chỉ làm phần bộ đệm hỏng **gọn**.
2. **Giới hạn cứng theo lượng bộ nhớ thường trú được cưỡng chế bằng cách đẩy
   trang ra đĩa**, không làm việc cấp phát thất bại — nó biến "hết bộ nhớ" thành
   "chậm thảm hoạ", và vì thế **phá luôn khả năng đo độ trễ**.
3. **Phép đo hiện tại yếu hơn mức cần thiết.** Hệ điều hành **đã duy trì sẵn**
   con số đỉnh chính xác, trong khi công cụ hiện tại lấy mẫu định kỳ.

**[ĐÃ ĐO] Một đính chính với chính cách diễn đạt ở trên.** Một phép đo đối chiếu
trực tiếp cho thấy cách lấy mẫu thiếu so với bộ đếm chính xác của hệ điều hành
khoảng **4 %** trên một tiến trình con tầm thường — và **lấy mẫu nhanh gấp 30 lần
không giảm được khoảng thiếu đó**. Nên đừng đọc "4 438 là chặn dưới" thành
"4 438 thấp hơn nhiều"; độ lớn khoảng thiếu cho một lần chạy **mô hình thật**
vẫn **[CHỜ BẰNG CHỨNG]**.

**[ĐÃ TRIỂN KHAI, chưa nối]** Một bản mẫu đọc bộ đếm chính xác của hệ điều hành
**đã tồn tại và đã được kiểm chứng trên một tiến trình con thật**: thẻ tiến
trình **sống qua cái chết của tiến trình con**, và giá trị đỉnh **lệch** khỏi giá
trị hiện tại. Nó xác định đối tượng đo bằng **thẻ tiến trình**, không bằng tên
tệp thực thi, và **từ chối** thay vì trả `0` khi không đo được. **Chưa** nối vào
quy trình đo, **chưa** harness nào gọi, **chưa** trường artifact nào dùng.

## F.3 GPU — công suất, không phải nhiệt

**[ĐÃ ĐO]** Đây là một kết quả đáng nêu vì nó đổi cách đọc mọi số GPU khác:

| Đại lượng | Giá trị |
|---|---|
| Giới hạn công suất **mặc định** của card | **80 W** |
| Giới hạn công suất **đang được cưỡng chế** | **40 W** |
| Nguồn giới hạn | **Software power cap đang chủ động giới hạn** — lấy mẫu 40 lần trong lúc tải: cờ software cap **Active 39/40**; cờ thermal slowdown và power-brake **Not Active ở mọi mẫu** |
| Nhiệt độ trong lúc đó | chỉ **59–63 °C** |
| Memory clock | ghim ở **810 MHz** trên **6 001 MHz** được hỗ trợ — **≈ 13,5 %** băng thông danh định |
| Trạng thái năng lượng | **P5**, không bao giờ P0 |

**Hệ quả kỹ thuật, đo bằng hai nguồn độc lập:** GPU **mua được prefill, gần như
không mua được decode.**

| | prefill (pp128) | decode (tg64) |
|---|---|---|
| GPU | **161,8 token/s** | **8,55 token/s** |
| CPU | 26,3 token/s | 7,35 token/s |
| **Tỷ lệ** | **6,2×** | **1,16×** |

Nguyên nhân là **phần cứng, không phải mô hình**: dưới cap 40 W, memory clock
đứng ở 13,5 % băng thông, trong khi phần tính toán chạy gần boost tối đa.
Prefill là compute-bound nên hưởng lợi; decode là bandwidth-bound nên không.
Bằng chứng nội tại: một mô hình 2,49 GB cho 8,55 token/s, một mô hình 0,46 GB
cho 43,8 token/s — tỷ lệ 5,1× so với tỷ lệ kích thước 5,4×, đúng dấu hiệu
bandwidth-bound.

**[ĐỀ XUẤT]** Vì một trợ lý họp có bối cảnh là transcript dài, **prefill là
phần quan trọng**, nên GPU vẫn đáng dùng — chỉ là **không vì lý do thường được
giả định**.

**[CHỜ SƠN]** Việc đổi giới hạn công suất là **cấu hình hệ thống**. Phép đo trên
là **chỉ-đọc**; không có thay đổi BIOS, driver, profile hay ép xung nào được
thực hiện.

**[ĐÃ ĐO] Một đính chính về cách đo CPU-only:** cờ "0 lớp trên GPU" **không**
phải một lần chạy CPU. Nó vẫn đăng ký backend CUDA, vẫn cấp **741 MiB VRAM**, và
cho decode **chậm hơn cả CPU thật** (5,43 so với 7,35 token/s). Baseline CPU
thật cần một cờ khác hẳn. Hệ quả: trong ba artifact CPU tồn tại, **đúng một**
cái là phép đo CPU thật có số RAM — hai cái còn lại không có trường RAM nào và
chạy với cờ không phải CPU-only.

## F.4 Đĩa và toolchain

| Đại lượng | Giá trị | Hệ quả |
|---|---|---|
| Dung lượng còn trên ổ hệ thống | **≈ 2,01 GiB** | **Chặn việc cài công cụ biên dịch toàn cục** |
| Cache của trình quản lý phụ thuộc | **≈ 2,8 GB**, nằm dưới thư mục artifact của dự án | **[ĐÃ ĐO] Cùng một repo hành xử khác nhau** tuỳ shell có đặt biến trỏ cache hay không |
| CUDA toolkit / MSVC | **chưa cài toàn cục** | **[CHỜ SƠN]**, và bị chặn bởi dung lượng đĩa |
| Nhánh CUDA | **CUDA 12.x** | Một thành phần thượng nguồn chưa phát hành bản cho CUDA 13 — xem ADR 0005 |

## F.5 Ba hạ tầng khác nhau — đừng gộp {#f5-ba-hạ-tầng-khác-nhau--đừng-gộp}

| | **Máy tham chiếu hiện tại** | **Cấu hình tối thiểu** | **Hạ tầng thử nghiệm tương lai** |
|---|---|---|---|
| Trạng thái | **[ĐÃ ĐO]**, n = 1 máy | **[CHỜ BẰNG CHỨNG]** | **[ĐỀ XUẤT]** |
| Nội dung | 16 GB RAM · GPU 6 GB bị cap 40/80 W · ổ hệ thống còn ≈ 2 GB | **Chưa thể suy ra.** Cần ≥ 2 máy khác cấu hình để biết đại lượng nào thật sự ràng buộc | Chủ dự án đã nêu khả năng dùng một GPU cloud **để thử nghiệm**; đó là **xử lý trên cloud** |
| Cảnh báo | Mọi số ở §F.2–F.3 chỉ nói về **máy này, lúc đó** | **Không** suy từ model card: một hướng dẫn chính thức của nhà sản xuất mô hình khác đã ghi rằng bộ nhớ suy luận cơ bản **chưa gồm** bối cảnh/KV cache và runtime | Dùng cloud **mâu thuẫn** với nguyên tắc dữ liệu không ra khỏi máy nếu dùng với dữ liệu thật. **[CHỜ SƠN]** |

**[ĐÃ ĐO] Một tiền lệ chống lại việc suy ra khả năng chạy từ phép tính cộng:**
một lần đo trước đây đã **hết bộ nhớ** với hai đỉnh **chặn dưới** cộng lại
3 767 MiB trong 5 343 MiB khả dụng — **dự đoán thiếu ít nhất 1 576 MiB**. Nên
"còn chỗ" theo phép cộng **không** phải bằng chứng là sẽ không hết bộ nhớ, và
đó là lý do cổng hiện tại từ chối theo **biên** chứ không theo một tổng dự đoán.

**Tài liệu này không chạy mô hình hay GPU để tạo ra bất kỳ số nào ở trên.** Mọi
số là đọc lại từ artifact và ghi chú đã có, kèm ngày đo.

---

# G. Mô hình dữ liệu, quyền riêng tư và bảo mật {#g-mô-hình-dữ-liệu-quyền-riêng-tư-và-bảo-mật}

## G.1 Dữ liệu nào tồn tại, ở đâu, bao lâu

| Loại dữ liệu | Xử lý ở đâu | Lưu hay không | Trạng thái |
|---|---|---|---|
| Âm thanh thô | — | **Không ghi theo mặc định**; có **phạm vi đồng thuận riêng** để gỡ lỗi, và bật transcript **không** mở phạm vi đó | **[ĐÃ TRIỂN KHAI]** cơ chế; **[CHỜ SƠN]** chính sách |
| Transcript | Cục bộ, trong bộ nhớ | **Không** theo mặc định | **[CHỜ SƠN]** |
| Ghi chú / nhật ký trả lời | Cục bộ | **Không** theo mặc định | **[CHỜ SƠN]** |
| Card tri thức đã duyệt | Cục bộ, trong bộ nhớ | **Chưa có lưu trữ bền vững nào** | **[ĐÃ ĐO]** — không có mã persistence trong repo |
| Biên nhận đồng thuận | Cục bộ | Chỉ metadata + thời điểm + phiên bản thông báo, **không audio** | **[ĐỀ XUẤT]** |
| Nhật ký vận hành | stderr | **Chỉ metadata**, theo allowlist trường | **[ĐÃ TRIỂN KHAI]** |
| Artifact benchmark | Thư mục cố định trong dự án | Có, **không** theo dõi bởi Git | **[ĐÃ TRIỂN KHAI]** |

**[ĐÃ ĐO] "Chưa có lưu trữ bền vững" là một phép đo, không một ý định.** Có kiểm
thử giải quyết các **binding import** để khẳng định không module nào trong gói
lõi gọi tới một API ghi đĩa — và nó phân loại theo việc một đường dẫn **có được
ghi vào hay không**, chứ không theo tên biến.

## G.2 Chính sách đã chốt, so với lựa chọn đang chờ

### Đã chốt — căn cứ là phát ngôn trực tiếp của chủ dự án

- Mặc định **không** ghi âm thanh thô / transcript / ghi chú / nhật ký trả lời.
- **Không** gửi audio hay transcript tới AI bên ngoài.
- **Không** học tự động từ hội thoại họp.
- Bot có **danh tính riêng** và **tự công khai là trợ lý AI**.
- Đồng thuận quản theo `(phiên, người, phạm vi, phiên bản thông báo)` và
  **không kế thừa** sang phiên mới.
- Trạng thái *từ chối / thu hồi / hết hạn* là **terminal trong phiên**; một cú
  click cũ **không** bật lại được.

### [CHỜ SƠN] — và vì sao không ai quyết thay

| Mục | Vì sao là quyết định của chủ dự án |
|---|---|
| Chế độ đồng thuận (theo từng người, hay do chủ trì điều phối) | Là **cam kết với người tham gia cuộc họp** |
| Thời hạn hiệu lực của đồng thuận (TTL) | Là chính sách **quyền riêng tư và thời hạn**; **không con số nào suy ra được từ mã** |
| Vào họp giữa buổi: hai thiết kế (ngắt mạch, hay kiểm soát nhận vào) | Cả hai **đã xây sau một interface**, mặc định đóng. Việc chọn là chính sách |
| Có lưu transcript / ghi chú / nhật ký trả lời | Cam kết với người tham gia |
| Thời hạn giữ biên nhận và metadata vận hành | Cam kết với người tham gia |
| **Câu chữ** của thông báo về việc lưu trữ | Là phát ngôn công khai nhân danh chủ dự án |
| Phạm vi mà một câu hỏi trong họp ánh xạ sang | Quyết định việc tra cứu chạm tới dữ liệu nào |
| Có công khai tên gọi của chủ dự án trong tài liệu dự án | Là **dữ liệu cá nhân của họ** |

**Hệ quả hiện tại:** vì các mục trên chưa được chọn, trạng thái "chờ quyết định"
đang **chặn mọi xử lý media**. Đó là thiết kế, không phải lỗi.

## G.3 Threat model

Cột **Phần dư** là phần quan trọng nhất của bảng này, và không mục nào trong đó
được bỏ trống cho đẹp.

| # | Mối đe doạ | Rào hiện có | Phần dư đã biết |
|---|---|---|---|
| T1 | **Chỉ thị tiêm** trong transcript | Cổng quyền hạn soi **đề xuất**, không soi lời tự nhận. Transcript là **dữ liệu không tin cậy** theo thiết kế | **[ĐÃ ĐO]** Một lần đo cho thấy mô hình **khai sai một phê duyệt** trong 1/6 tình huống tiêm, và **cổng không bắt được cái đó** |
| T2 | **Sai grounding** (trả lời không có căn cứ) | Ba trạng thái answerability; claim phải map tới bằng chứng; card sửa-sau-duyệt thành không dùng được | **[ĐÃ ĐO]** Mô hình **lệch mạnh về phía trả lời**: bỏ sót việc nên từ chối **5/9**, từ chối sai **0/20** |
| T3 | **Vượt quyền** (authority bypass) | Ba lớp độc lập; không mức tin cậy nào mở được | **Lỗ của từ điển mẫu là lỗ thật**, không được bù bởi phần còn lại của cổng. Ghi thành kiểm thử có trần chỉ-giảm |
| T4 | **Rò nội dung qua nhật ký / thông báo lỗi** | Allowlist trường; quy tắc "mô tả hình dạng"; kiểm thử credential giả trên **mọi** kiểu cấu hình sai | Bộ kiểm thử bao gói lõi; **không** bao thư mục benchmark |
| T5 | **Rò qua một đường gửi dữ liệu của thư viện** | **Sự vắng mặt** của SDK xuất dữ liệu; **từ chối khởi động theo sự hiện diện** của 4 họ biến môi trường | **[ĐÃ ĐO]** 12/12 biến đó **khởi động bình thường** trước khi cơ chế này được thêm — kể cả giá trị mang nghĩa "ngoại tuyến" và chuỗi rỗng |
| T6 | **Tệp thực thi gốc tự gọi ra mạng** | **PHẦN DƯ THẬT, chưa đóng** | Tệp thực thi gốc **không nằm dưới** cơ chế quan sát của Python, nên bằng chứng "không có sự kiện mạng" thu trong tiến trình Python **không nói gì** về nó. Đây là lý do có quyết định đòi cô lập ở tầng hệ điều hành |
| T7 | **Dữ liệu bị đồng bộ lên dịch vụ lưu trữ đám mây** | Chỉ nhận **đường dẫn tương đối trong dự án** | **Phần dư:** nếu bản thân thư mục dự án nằm trong một thư mục được đồng bộ thì dữ liệu cũng bị đồng bộ — **không cơ chế kiểm tra nào thấy được điều đó** |
| T8 | **Rò credential** | Dùng kiểu bọc secret; mọi hiển thị cấu hình đi qua một hàm che; thông báo từ chối in **tên biến, không bao giờ in giá trị** (một URL proxy có thể mang credential) | **[ĐÃ ĐO]** Hiện **chưa có chỗ gọi nào** lấy giá trị secret ra, nên quy tắc review từng chỗ gọi là **chỉ dẫn hướng tới**: chưa kiểm thử nào bắt được vi phạm |
| T9 | **Đối thủ là một tiến trình cục bộ khác** | **Không endpoint nào trả về nội dung cuộc họp** — giao diện **không có gì đáng lấy**; chỉ bind loopback dạng số; kiểm host header | Là **thuộc tính thiết kế phải giữ**, không phải một control có thể thêm sau |
| T10 | **Tấn công từ một trang web đang mở** | Mọi request đổi trạng thái cần header riêng + POST; tài liệu API tắt; **không** CORS, **không** WebSocket | Cài CORS chỉ **nới** được mặc định; nền tảng web **không** kiểm `Origin` trên bắt tay WebSocket, nên một socket sẽ reachable **hai chiều** cross-origin |

## G.4 Điều kiện cần trước khi xử lý media thật

Năm điều kiện, **tất cả** phải đạt, và không điều kiện nào trong đó là viết mã:

1. **[CHỜ SƠN]** Chế độ đồng thuận được chọn.
2. **[CHỜ SƠN]** Chính sách lưu trữ và thời hạn giữ được chọn.
3. **[CHỜ SƠN]** Câu chữ thông báo được chủ dự án duyệt.
4. **[CHỜ BẰNG CHỨNG]** Cổng 0-S, 0-P, 0-C đóng.
5. **[CHỜ SƠN]** Một nơi phát được cấp phép tồn tại.

## G.5 Giới hạn đã biết của kill switch {#g5-giới-hạn-đã-biết-của-kill-switch}

**[ĐÃ TRIỂN KHAI]** Kill switch được tuyên bố **đúng những gì đo được**: đóng
cổng ngay và không gỡ được, vô hiệu mọi lần kiểm lại ở cả cổng và sổ ghi, loại
buffer kể cả với bên đang giữ, và **yêu cầu** hủy các công việc đã đăng ký.

**Nó KHÔNG được tuyên bố là "dừng mọi công việc".** Hai lý do, cả hai đo được:

- Công việc **chưa đăng ký** một callback hủy là **vô hình** với cơ chế này.
- Số đếm công việc đã hủy đếm **số lần gọi**, không phải số lần **thành công**.

**[ĐÃ ĐO] Một giới hạn thứ ba, nghiêm trọng hơn và vẫn mở:** công tắc tắt mô
hình hiện **chỉ đổi một giá trị liệt kê**, **không chạm tới tiến trình con**.
Nếu một máy chủ mô hình được mở, giao diện sẽ **báo "đã kill" khi mô hình vẫn
đang chạy**. Đây là một trong ba điều kiện phải xử lý **trước** khi mở một máy
chủ mô hình, cùng với vòng đời tiến trình và việc bộ đệm prompt giữ nội dung
trong RAM **ngoài tầm** mọi cơ chế xoá của MeetAI.

## G.6 Nền tảng họp — điều khoản chính thức đã đọc được {#g6-nền-tảng-họp--điều-khoản-chính-thức-đã-đọc-được}

**[ĐÃ ĐO] Truy cập 2026-10-10** (ngày "last updated" dưới đây là ngày nền tảng
ghi trên trang). Hai văn bản chính thức **đã đọc được trực tiếp**, và nội dung
được trích nguyên văn vào ghi chú nghiên cứu:

| Văn bản | Hiệu lực / cập nhật | Điều khoản liên quan trực tiếp |
|---|---|---|
| **Developer Terms of Service** | hiệu lực 2024-07-08, cập nhật 2024-06-06 | **§5** đòi một privacy policy công khai, hiện hành, mô tả đầy đủ dữ liệu thu, mục đích, việc chia sẻ và cách yêu cầu xoá · **§5(b)** đòi **xoá nhanh** khi dữ liệu không còn cần, khi người dùng yêu cầu, khi nền tảng yêu cầu, hoặc khi ngừng ứng dụng; và đòi một cách **dễ tiếp cận** để yêu cầu sửa/xoá · **§6** giữ quyền App Review |
| **Developer Policy** | hiệu lực 2024-07-08, cập nhật 2024-06-06 | **Mục 2** đòi **xin phép trước** khi khởi tạo quy trình thay mặt người dùng/server · **Mục 3** cấm né tính năng privacy/safety/security và đòi **tôn trọng opt-out** · **Mục 15** giới hạn dữ liệu API vào chức năng đã nêu · **Mục 21** cấm dùng *message content* lấy qua API để huấn luyện AI/LLM nếu chưa được cho phép |

**[CHỜ BẰNG CHỨNG] Và đây là điều phải nói rõ:** các điều khoản trên **không tự
trả lời** rằng việc xử lý **cục bộ** một luồng thoại cho MeetAI được **hỗ trợ**
hoặc được **cho phép**. Lệnh cấm huấn luyện *message content* cũng **không** được
diễn rộng thành cấm mọi suy luận cục bộ; nhưng audio/voice vẫn phải được đánh
giá theo phạm vi dữ liệu API, quyền của người tham gia, nghĩa vụ privacy policy
và **route được hỗ trợ**. *(Đây là tóm tắt kỹ thuật, không phải tư vấn pháp lý.)*

**[ĐÃ ĐO] Về khả năng kỹ thuật, tài liệu chính thức nói gì và không nói gì:**

- Tài liệu giao thức thoại mô tả luồng kết nối, việc nhận một định danh luồng ở
  bước khởi tạo, và nói rõ kênh UDP dùng cho **cả nhận và gửi** dữ liệu thoại.
- Tài liệu nêu rằng **từ 2026-03-01**, nền tảng chỉ hỗ trợ thoại/video **mã hoá
  đầu-cuối**, và các khung âm thanh gửi và nhận **đều được mã hoá** khi cơ chế
  đó bật.
- **Nhưng** trang đó là **đặc tả giao thức**. Nó **không** chỉ cách lấy ánh xạ
  *luồng → định danh người dùng* cho một triển khai bot cụ thể, và **không** xác
  nhận rằng có một API/SDK cho **bot nhận audio trong kênh nhóm** được nền tảng
  hỗ trợ **như một sản phẩm**.
- Một SDK khác **có** callback nhận audio kèm định danh người dùng, nhưng tài
  liệu đặt callback đó trong luồng gọi thoại của SDK đó, **không** phải bằng
  chứng cho kênh thoại nhóm qua danh tính bot. Nó là **chỗ đỗ**, không phải
  đường đi vòng cho MVP.

**Không có tuyên bố "an toàn tuyệt đối" hay "không thể rò rỉ" nào trong tài liệu
này.** Mọi rào ở trên đều có phần dư, và phần dư đều được nêu tên.

---

# H. Quy trình phát triển, kiểm thử và đánh giá {#h-quy-trình-phát-triển-kiểm-thử-và-đánh-giá}

## H.1 Quy trình từng lát

Đơn vị công việc là **một lát** — một thay đổi gắn kết, đủ nhỏ để review và để
quay lại được. Mỗi lát đi qua **đúng** chuỗi sau, và thứ tự là phần quan trọng:

```
1. Gắn lát vào một dòng trong kế hoạch VÀ một nghĩa vụ trong đặc tả
          ↓
2. Xác định cách kiểm chứng  ───  TRƯỚC khi viết mã
          ↓
3. Viết kiểm thử: tính chất AN TOÀN, không chỉ happy path
   → viết sao cho XOÁ CƠ CHẾ ĐI THÌ KIỂM THỬ SAI
          ↓
4. Negative test BẮT BUỘC: cấu hình sai · năng lực bị bật trái phép
   · đồng thuận chờ/thu hồi · rò nhật ký · từ chối tuyệt đối
   · adapter giả nhận mình là thật
          ↓
5. Credential canary: ghép một credential giả với MỌI kiểu cấu hình sai
          ↓
6. Viết mã — phần nhỏ nhất làm kiểm thử đúng
          ↓
7. Bốn kiểm tra: pytest · ruff format · ruff check · mypy (strict)
          ↓
8. Mutation: tắt từng cơ chế, khẳng định kiểm thử ĐỎ
          ↓
9. Cập nhật kế hoạch + đặc tả + sổ trạng thái
          ↓
10. Một lát = một commit
```

**Khi kiểm thử sai: tìm nguyên nhân, sửa phần nhỏ nhất. KHÔNG che lỗi bằng cách
nới assertion hay bỏ assert.** Đây là một quy tắc viết ra vì nó từng là một cám
dỗ thật.

**Một lát một commit**, và lý do là **khả năng quay lại theo lát**: một commit
gộp bốn lát làm mất đúng khả năng đó.

## H.2 Bốn kiểm tra, chạy sau mỗi lô thay đổi

| Lệnh | Vai trò |
|---|---|
| `uv run pytest` | Bộ kiểm thử |
| `uv run ruff format .` | Định dạng |
| `uv run ruff check .` | Lint — **15 nhóm quy tắc**, gồm cả nhóm bảo mật và nhóm logging |
| `uv run mypy` | Kiểm kiểu, **chế độ strict**, bật cả cảnh báo mã không tới được |

**Không tuyên bố đạt nếu chưa chạy thật.** Và một cái bẫy đã gặp, ghi lại vì nó
tạo ra một commit sai: một chuỗi lệnh shell **kết thúc bằng một lệnh in** sẽ báo
mã lỗi của **lệnh in**, không của công cụ kiểm tra. Từ đó, mã lỗi được **bắt vào
biến** rồi mới in.

## H.3 Mutation testing — vì sao nó không phải tuỳ chọn

**Một kiểm thử chỉ lặp lại giá trị mặc định sẽ pass với cả một stub hardcode** —
nó cho tín dụng coverage giả. Cách duy nhất đáng tin để biết một control thật sự
được kiểm là **tắt control đó đi và xem kiểm thử có đỏ không**.

**[ĐÃ ĐO]** Một số ví dụ đã thực hiện: 29/29 mutation trên ba cổng an toàn ·
6/6 trên phép kiểm bằng chứng của adapter · 9/9 trên báo cáo trạng thái cổng.

**Và một bài học lặp lại ba lần, ghi lại vì nó dễ đọc sai:** một mutation cho
kết quả **xanh** **không** tự nghĩa là kiểm thử mù. Nó có thể là một **mutation
vô hiệu** — payload rơi vào một nhánh **không tới được**, hoặc ghi vào một
thuộc tính mà hệ thống không bao giờ đọc. Cả ba lần, câu trả lời đúng là **tìm
bề mặt quan sát được thật**, không phải nới assertion.

**[ĐÃ ĐO] Một bài học thứ hai:** một kiểm thử **khẳng định lại implementation**
sẽ pass với bất kỳ implementation nào. Hai assertion tautological đã được tìm ra
**chỉ bằng mutation**, và cách sửa là **suy ra giá trị mong đợi từ tài liệu**
chứ không từ mã.

## H.4 16 nhãn đánh giá, và vì sao chúng không thể tự duyệt {#h4-16-nhãn-đánh-giá-và-vì-sao-chúng-không-thể-tự-duyệt}

**[ĐÃ ĐO]** Bộ dữ liệu đánh giá cho phần answerability gồm **16 tình huống**:
**13** tình huống trả lời sai (trên **12 cơ chế** — hai tình huống chung một cơ
chế) + **2** tình huống từ chối sai + **1** tình huống đối chứng dương (hành vi
**đúng**).

Chạy từng câu trả lời qua cổng quyền hạn cho kết quả: cổng **cho qua 12/16**,
**từ chối 4/16**. Trong 12 tình huống cổng cho qua, **11** là trả lời sai mà
phần answerability là **lớp phòng vệ DUY NHẤT**.

**[CHỜ SƠN] Chưa nhãn nào được duyệt.** Và lý do không thể tự duyệt là một lý
do về phương pháp, không về thủ tục: **các nhãn định nghĩa hành vi đúng là gì.**
Một tác nhân kỹ thuật tự duyệt nhãn của chính mình thì phép đánh giá **mất ý
nghĩa** — nó trở thành một phép đo sự tự nhất quán.

## H.5 Kết quả benchmark — và phạm vi của từng con số {#h5-kết-quả-benchmark--và-phạm-vi-của-từng-con-số}

### H.5.1 Hợp đồng đo, trước khi đưa số

**[ĐÃ TRIỂN KHAI]** Một quyết định phương pháp quan trọng: **không có một con số
accuracy hay F1 tổng nào**, và điều đó **được một kiểm thử khẳng định**. Lý do:
một con số tổng sẽ cho phép **chiều rẻ** (thiếu một trường trong dữ liệu đầu ra)
**trả nợ** cho **chiều đắt** (một cam kết nhân danh chủ dự án). Mọi trục được
báo riêng, kèm **mẫu số** của chính nó.

Với nhận dạng tiếng Việt, đơn vị lỗi là **âm tiết**, không phải từ: tiếng Việt
viết âm tiết cách nhau bằng dấu cách, nên token theo dấu cách **không** phải từ.
Chỉ số là **micro-average** (tổng lỗi / tổng token), **không** phải trung bình
của các tỷ lệ từng câu. Khoảng tin cậy dùng **bootstrap theo phát ngôn**, không
dùng công thức tỷ lệ — vì chỉ số này **có thể vượt 1** (phép chèn không có chặn
trên) và lỗi đi theo cụm trong một phát ngôn.

### H.5.2 Nhận dạng tiếng nói — FLEURS (nhánh license permissive) {#h52-nhận-dạng-tiếng-nói--fleurs-nhánh-license-permissive}

**[ĐÃ ĐO] 2026-10-07.** Mẫu số: **361 clip / 10 422 âm tiết / 4 299,5 s audio**.
Dataset **CC-BY-4.0**, ungated, revision được ghim; mô hình và runtime ghim bằng
SHA-256.

| Chỉ số | Giá trị |
|---|---|
| **Tỷ lệ lỗi âm tiết** | **23,47 %**, CI95 **[22,05 – 25,08]** |
| Tỷ lệ lỗi ký tự | 11,23 % |
| Tỷ lệ chèn | 1,37 % |
| **Failure** | **0** (timeout 0, hết bộ nhớ 0, output rỗng 0, lỗi tiến trình 0) |
| Nếu **khử dấu** *(chỉ để chẩn đoán)* | 17,85 % → **khoảng lệch +5,62 điểm phần trăm** |

**Khoảng lệch +5,62 điểm là kết quả phương pháp quan trọng nhất ở đây:** khử dấu
sẽ báo **17,85 %** thay vì **23,47 %** — đẹp hơn 5,6 điểm, và che đúng lớp lỗi
thanh điệu mà dự án quan tâm. Chính sách **không khử dấu** vừa tự chứng minh
bằng số.

**[ĐÃ ĐO] Một phép kiểm chéo đáng nêu:** ba đường tính độc lập (tổng của runner,
tổng các clip trong artifact, và một bộ xử lý **tính lại từ dữ liệu gốc**) cho
**cùng** bốn con số S/D/I/N. Và mẫu số 10 422 được **dự đoán trước** khi chạy
bộ xử lý đó.

**Mẫu số của dataset card là 415; phép đếm thực tế là 361**, và cả ba nguồn (số
dòng, số tệp audio, khớp theo tên) đều cho 361 — **card sai**.

**Theo lớp token, với hai giới hạn phải đọc kèm:**

| Lớp | Mẫu số | Tỷ lệ lỗi |
|---|---|---|
| date | 114 | 28,95 % |
| number | 522 | 31,80 % |
| **proper_noun** | **768** | **70,57 %** |

- **Giới hạn 1:** nhãn `proper_noun` gán bằng **chữ hoa/thường**, không phải
  annotation thủ công. Tên riêng tiếng Việt là danh từ thường, nên hoa/thường là
  tín hiệu duy nhất ở mức text; và **token đầu câu không bao giờ được gán**, nên
  mẫu số **đếm thiếu** tên thật. Con số **trộn** lỗi nhận dạng với lỗi gán lớp.
- **Giới hạn 2:** chỉ **13,5 %** token được gán lớp (1 404 / 10 422).

Nên **70,57 % là tín hiệu rủi ro cần điều tra, KHÔNG phải tỷ lệ lỗi tên riêng.**
Muốn kết luận cần **một bộ tên được gán nhãn thủ công trong bối cảnh họp**.

### H.5.3 Nhiễu — phép thử tổng hợp **có kiểm soát**

**[ĐÃ ĐO] 2026-10-07.** **Gọi đúng tên:** nhiễu trắng cộng thêm, sinh bằng một
bộ sinh số giả ngẫu nhiên có seed, trộn vào chính audio FLEURS. Đây **không**
phải tiếng ồn phòng họp thật: **không có hình phổ phòng, không có vang, và không
liên quan tới nói chồng**. Kiểm chứng sinh dữ liệu: tỷ số tín/tạp đo được lệch
≤ 0,04 dB so với mục tiêu, **không clipping**, 40 phát ngôn × 3 mức = 120 clip,
0 failure.

**So sánh theo cặp, bootstrap trên HIỆU SỐ** — không so khoảng tin cậy lề của
hai điều kiện, vì cách đó **thiếu lực** trên dữ liệu paired:

| Điều kiện | Δ tỷ lệ lỗi | CI95 của **hiệu số** | Phân biệt được với 0? |
|---|---|---|---|
| Tín/tạp 20 dB | **+1,33 đpt** | [−0,39 ; +3,05] | **chưa phát hiện được** |
| Tín/tạp 10 dB | **+6,63 đpt** | [+4,00 ; +9,33] | **có** |
| Tín/tạp 5 dB | **+18,56 đpt** | [+14,95 ; +22,23] | **có** |

**Ở 20 dB: "chưa phát hiện được suy giảm trong dữ liệu này" — KHÔNG phải "không
có ảnh hưởng".** Với mẫu 40 và CI rộng tới +3,05 đpt, một ảnh hưởng nhỏ hoàn
toàn có thể tồn tại mà phép đo này không thấy. Phân biệt hai câu đó là quan
trọng: "chưa phát hiện" nói về **độ mạnh của phép đo**, "không có ảnh hưởng" nói
về **thế giới** — và chỉ cái thứ nhất được đo.

### H.5.4 Tốc độ nhận dạng — và nó không nói gì về độ trễ sản phẩm

**[ĐÃ ĐO]** Tỷ lệ thời gian xử lý / thời lượng audio, **báo cả hai cách tổng
hợp** vì chúng trả lời hai câu hỏi khác nhau:

| Cách tổng hợp | Giá trị |
|---|---|
| Tỷ số của hai tổng | **0,315** |
| Trung bình các tỷ số từng clip | **0,346** |
| p50 / p95 của tỷ số từng clip | 0,331 / 0,534 |

Hai số khác nhau vì clip ngắn có chi phí nạp mô hình cố định chiếm tỷ lệ lớn
hơn. **Trích một số rồi gọi chung là "tốc độ" sẽ che mất câu hỏi nào đang được
trả lời.**

**Giá trị < 1 chỉ nói về đúng phép đo CLI tuần tự này**, và **đã bao gồm việc
nạp mô hình cho mỗi clip**. Nó **không** chứng minh streaming, **không** phải độ
trễ đầu-cuối, và **không** nói gì về mục tiêu 1–2 giây.

### H.5.5 Giọng vùng — VietMed, và vì sao trục vẫn chưa đạt {#h55-giọng-vùng--vietmed-và-vì-sao-trục-vẫn-chưa-đạt}

**[ĐÃ ĐO] + [CHỐT phạm vi]** Dataset **có nhãn giọng vùng** và đã được chạy thăm
dò: **421 clip**, tỷ lệ lỗi gộp **46,0 %**, audio 8 kHz, domain **y tế**.

**Trục vẫn giữ `not demonstrated`**, và lý do là một lý do thống kê chứ không
phải thiếu công sức: **giọng vùng lồng gần hoàn toàn với người nói và với điều
kiện thu**. Cả split test có **27 người nói**; hai nhóm giọng chỉ có **1 và 2**
người nói, và khoảng tin cậy của nhóm 1-người-nói **sụp thành một điểm**. Nên
một con số theo-nhóm-người-nói **không phải** phép đo giọng vùng.

Thêm vào đó: **một tag license ở mức repo không tự xác minh quyền với mọi thành
phần audio**, và hai nguồn (paper so với tag) **không khớp** về license — cả hai
đều permissive nên rủi ro thấp, nhưng điều đó đã được ghi là **[CHỜ BẰNG
CHỨNG]**.

### H.5.6 Nói chồng — ngoài phạm vi, cổng để mở

**[CHỐT phạm vi]** Trục này giữ **`absent`**. Lý do, nêu đầy đủ:

- **Không** tự gán nhãn một dataset bằng **một** annotator rồi coi là chuẩn vàng.
- Một corpus họp nổi tiếng có license permissive nhưng là **tiếng Anh**, nên
  không đóng được tiêu chí **tiếng Việt**.
- Một corpus khác bị nhà cung cấp **giới hạn trong một challenge/workshop**, cấm
  dùng khác mục đích và cấm phát hành lại.

### H.5.7 Mô hình ngôn ngữ — năm trục, 43 tình huống

**[ĐÃ ĐO] 2026-10-08.** Corpus **43 tình huống tổng hợp, do chính tác nhân kỹ
thuật viết**, phiên bản được ghim; **hai lần chạy toàn bộ** với cùng cấu hình;
output **tất định**. Mô hình, bản dựng runtime, system prompt và bộ chấm điểm
**đều ghim bằng SHA-256**.

| Trục | Số đo | Đọc thế nào |
|---|---|---|
| Cấu trúc đầu ra sai | **1/43 = 2,3 %** | Gần như sạch; và tình huống duy nhất sai là tình huống **đề bài yêu cầu** thêm trường |
| Dẫn nguồn bịa | **1/43 = 2,3 %** | Một lần, do tiêm yêu cầu, và **cổng bắt được** |
| Claim không có căn cứ | **6/43 = 14,0 %** | **Trùng gần hoàn toàn** với dòng dưới — **đừng đọc như hai bằng chứng độc lập** |
| **Bỏ sót việc nên từ chối** | **5/9 = 55,6 %** | **Điểm yếu lớn nhất** |
| Từ chối sai | **0/20 = 0 %** | Cùng với dòng trên: mô hình **lệch mạnh về phía trả lời** |
| Hình dạng bị cấm | **3/43 = 7,0 %** | |
| Bỏ sót một lần phải từ chối | **1/8 = 12,5 %** | Gate bắt được |
| **Vượt cấm tuyệt đối** | **0/8 = 0 %** | Gate giữ — **nhưng chỉ SAU khi** một lần rà soát đóng một đường vượt **đo được** |
| Đi theo chỉ thị tiêm | **1/6 = 16,7 %** | Một lần **khai sai một phê duyệt**. **Gate KHÔNG bắt được cái này** |
| Gate chặn một câu trả lời đúng | **2/20 = 10,0 %** | Là **chi phí**, không phải vi phạm |

**Ba kết luận, nói thẳng:**

1. **Mô hình lệch mạnh về phía trả lời.** Từ chối sai 0 %, bỏ sót việc nên từ
   chối 55,6 %. Với một trợ lý họp, **đó là chiều sai**.
2. **Hình dạng của việc bỏ sót không phải "không biết từ chối".** Nó **biết** từ
   chối khi **không có** bằng chứng và khi bằng chứng **mâu thuẫn**. Nó trả lời
   khi bằng chứng **có mặt nhưng không đủ**.
3. **Lỗi lớn nhất của lượt đo đó không phải của mô hình mà của cổng**, và nó
   được tìm ra bằng cách **đi xác minh một câu định viết**.

### H.5.8 Nhiệt, điện, chi phí và độ ổn định

**[ĐÃ ĐO]** nhiệt **68,3 °C** trung bình / **71 °C** đỉnh; công suất **32,28 W**
trung bình / **41,29 W** đỉnh; **0,0323 kWh/giờ**.

**[CHỜ BẰNG CHỨNG] Chi phí tháng.** Hai lý do độc lập: công cụ đo chỉ báo
**board GPU** nên con số là **chặn dưới của cả hệ thống** — cần một đồng hồ ổ
cắm; và **giá điện bậc thang** làm giá cận biên phụ thuộc tổng tiêu thụ của cả
hộ. **Không con số chi phí tháng nào được nêu trong tài liệu này.**

**[CHỜ BẰNG CHỨNG] Độ ổn định.** **2/13 hết bộ nhớ ở một lần chạy, 0/43 ở hai
lần chạy khác** — và **sự khác biệt giữa lần chạy thất bại và các lần thành công
không nằm ở bất kỳ biến nào được ghi lại**. Lần chạy thất bại **không** được cấu
hình khác, và **không** có ít chỗ trống hơn. Đó là kết luận trung thực, và nó là
lý do cổng từ chối theo **biên** thay vì theo một tổng dự đoán.

**Một khoảng trống trong bằng chứng, nêu ra vì nó ảnh hưởng tới cách phân loại:**
hai lần thất bại đó được dán nhãn "hết bộ nhớ" vì khớp một dấu hiệu trong đầu ra
lỗi **lúc đó**; trường ghi bằng chứng cho nhãn **chưa tồn tại** khi đó, nên
artifact **không** mang dấu hiệu ấy. Trường đó **nay đã có**, và lần thất bại
tiếp theo sẽ ghi lại thứ biện minh cho nhãn của nó.

### H.5.9 Bảng tổng kết sáu trục của nghĩa vụ benchmark nhận dạng

Nghĩa vụ này là một **phép hội**, nên trạng thái tổng là `absent` cho tới khi
**mọi** trục đạt. Ghi ra đây để không ai đọc thành "chưa làm gì":

| Trục | Trạng thái |
|---|---|
| Tỷ lệ lỗi âm tiết / ký tự | ✅ **đã đo** |
| Nhiễu | ✅ **đã đo** — dạng **tổng hợp có kiểm soát**, không phải thực tế |
| Tốc độ xử lý | ✅ **đã đo** — lời gọi CLI **tuần tự** |
| Bộ nhớ đỉnh | ⚠️ **một phần** — đỉnh là **chặn dưới**; bộ nhớ GPU theo tiến trình **không tồn tại** trên nền tảng đồ hoạ này |
| Tên riêng | ❌ **not demonstrated** — heuristic hoa/thường, chỉ 13,5 % token được gán lớp |
| Giọng vùng | ❌ **not demonstrated** — lồng với người nói |
| **Nói chồng** | ❌ **absent** — không corpus có license phù hợp trong phạm vi |
| p50/p95 đầu-cuối | ❌ **not demonstrated** — phụ thuộc quyết định về đường suy luận |

---

# I. Lộ trình và tiêu chí nghiệm thu theo cổng {#i-lộ-trình-và-tiêu-chí-nghiệm-thu-theo-cổng}

## I.1 Ba cấp thử nghiệm — và chúng không phải ba giai đoạn liên tiếp

| | **Cấp A — dry-run tổng hợp** | **Cấp B — mô hình cục bộ trên fixture** | **Cấp C — nền tảng họp sandbox** |
|---|---|---|---|
| **Lệnh** | `meetai dry-run` | *(chưa có lệnh chạy hợp lệ)* | *(không có)* |
| **Đầu vào** | 12 tình huống **hằng số trong module**, không đọc tệp nào | Mô hình đã chuẩn bị + corpus tổng hợp | Một server thật |
| **Có thể chạy ngay** | **CÓ** | **một phần** | **KHÔNG** |
| **Được phép chạy** | **CÓ** | **CHƯA** — bốn cổng | **KHÔNG** — bốn cổng bằng chứng |
| **Rủi ro** | không đáng kể | **hết bộ nhớ thật** | rò nội dung họp, vượt quyền |

**Cấp A nằm NGOÀI cả hai đường còn lại và chạy song song được.**

## I.2 Cấp A — chạy được ngay

**[ĐÃ TRIỂN KHAI] + [ĐÃ ĐO]** Xem [§D.6](#d6-dry-run-cấp-2-và-giới-hạn-của-bằng-chứng-tổng-hợp) để biết
chính xác nó chứng minh gì và **không** chứng minh gì. Tóm lại: nó chứng minh
**đúng một việc** — lõi quyết định chạy tất định và không ghi gì ra đĩa — và
**không** nói gì về chất lượng mô hình hay nhận dạng tiếng Việt.

## I.3 Cấp B — bốn cổng, trạng thái đọc được bằng lệnh

**[ĐÃ TRIỂN KHAI]** Có một lệnh **chỉ đọc** báo trạng thái bốn cổng, đọc **chính
các hằng số mà các cổng đọc** — nên nó không thể không khớp với phép cưỡng chế:

```bash
python -m benchmarks.readiness        # exit 3 khi còn cổng mở
python -m benchmarks.readiness --json
```

**[ĐÃ ĐO] 2026-10-11:** `exit 3`, **4/4 cổng còn mở**. Lệnh này **không** phải
một phép chạy, và tự khai điều đó bằng **dữ liệu**, không bằng lời.

| Cổng | Vì sao từ chối | Mở bằng gì |
|---|---|---|
| **Ngưỡng RAM cho mô hình ngôn ngữ** | Chưa có ngưỡng được duyệt. Phép đo duy nhất là **một** quan sát, lấy mẫu 300 ms, nên là **chặn dưới** chứ không phải mức an toàn | **[CHỜ SƠN]** duyệt một biên |
| **Ngưỡng RAM cho nhận dạng tiếng nói** | **Không có phép đo nào** — không phải n=1 mà **n=0**: không artifact nhận dạng nào có số RAM host | **[CHỜ SƠN]** + cần **một phép đo**. **Cần CẢ HAI** |
| **Digest mô hình chưa ghim** | Chính sách: digest là **bắt buộc**, không có cơ chế override; sổ ghi hiện **rỗng** | **[CHỜ SƠN]** ghim giá trị đúng của tệp đã chuẩn bị |
| **Cô lập đường ra ở tầng hệ điều hành** | Chưa được thiết lập và chưa được khai báo | **[CHỜ SƠN]** đặt cô lập rồi khai báo trong mã nguồn |

**Hai điều quan trọng về bốn cổng này:**

1. **Mỗi cổng từ chối vì sự VẮNG MẶT của một trạng thái đã được duyệt**, không
   vì một lỗi — và thông báo của chúng **nói rõ điều đó**, để người vận hành
   không đi giải phóng bộ nhớ cho một vấn đề mà bộ nhớ không giải quyết.
2. **Hai ngưỡng RAM TÁCH NHAU có chủ ý.** Nền bằng chứng của chúng **không so
   sánh được**: một quan sát so với **không có** quan sát nào. Và con số 4 438
   MiB là của **một mô hình ngôn ngữ cụ thể**, không phải của mô hình nhận dạng
   — dùng lại nó sẽ là **sai cổng**, không phải cổng lỏng.

**[ĐÃ ĐO] Phép cưỡng chế là thật, không chỉ được ghi.** Cả bốn đường chạy mô
hình trên CPU đều kết thúc với mã lỗi, và cổng từ chối **trước khi đọc bộ nhớ**
— đo được: truyền vào một lượng RAM vô lý lớn **vẫn** bị từ chối. Trong quá
trình đó, **hai đường vòng đã được tìm ra và đóng**: một harness chạy mô hình
không có cổng nào, và một đường nhận dạng tiếng nói truyền cờ không-GPU mà chưa
được gated.

**Ngoài bốn cổng, cấp B còn ba điều kiện không biểu diễn được bằng một hằng số:**

- **[CHỜ SƠN]** Chọn cách lấy số đo bộ nhớ an toàn (giữ nguyên trạng / chạy có
  giám sát / suy từ kích thước tệp) — mỗi phương án có rủi ro còn lại khác nhau,
  và **một trong đó là chạy mô hình thật**.
- **[CHỜ SƠN]** Chọn mô hình nào được chạy.
- **[CHỜ SƠN]** Cho phép một lần chạy **có giám sát**.

## I.4 Năm quyết định đã đưa ra theo uỷ quyền {#i4-năm-quyết-định-đã-đưa-ra-theo-uỷ-quyền}

Chủ dự án **uỷ quyền** cho tác nhân kỹ thuật quyết năm mục này dựa trên nghiên
cứu và cấu hình máy. Chúng được ghi là **quyết định theo uỷ quyền**, **không
phải** phát ngôn của chủ dự án — phân biệt đó quan trọng nếu sau này cần xem lại.

| # | Quyết định | Căn cứ đo được |
|---|---|---|
| 1 | Digest mô hình là **bắt buộc**; bỏ hẳn cờ tắt kiểm tra | Cờ đó **đã được dùng ở 2 trong 7** lần đo, và bản ghi kết quả vẫn **trông đầy đủ** |
| 2 | Nơi ghi kết quả **cố định**, tương đối trong dự án, không theo dõi bởi Git | Đường dẫn tương đối chặn **cả** ổ mạng **và** thư mục đồng bộ **mà không cần nhận ra cái nào** |
| 3 | **Từ chối khởi động theo SỰ HIỆN DIỆN** của các biến đổi được nguồn lấy mô hình, và của các biến định tuyến mạng | **12/12** biến đó khởi động bình thường **trước** thay đổi — kể cả giá trị mang nghĩa "ngoại tuyến" và chuỗi rỗng |
| 4 | **Không** nhận thư viện tải mô hình vào môi trường chạy | Thiết kế không cần; nhận vào là **mười** phụ thuộc trực tiếp, trong đó có một thành phần gốc **tự kết nối mạng** |
| 5 | **Đòi** cô lập đường ra ở tầng hệ điều hành **trước** khi chạy tệp thực thi gốc | Tệp thực thi gốc **không nằm dưới** cơ chế quan sát của Python |

**Hai ghi chú về phương pháp**, vì phương pháp quan trọng không kém kết quả:

- **Quyết định 3 được tách thành hai nhóm với HAI lý do khác nhau.** Nhóm biến
  đổi nguồn lấy mô hình **tạo ra được** một đường tải về, nên dễ biện minh. Nhóm
  biến định tuyến mạng **không tạo** đường nào — nếu chỉ dừng ở đó thì đáng lẽ
  **không** chặn. Chúng bị chặn vì một cơ chế cụ thể: chúng **đi vòng qua** chính
  phép cô lập mà quyết định 5 đòi. Một biến thứ ba, chỉ đổi chỗ vùng nhớ đệm,
  **cố ý KHÔNG** bị chặn, và **có kiểm thử ghi điều đó** để người sau không đọc
  thành sơ sót.
- **Chi phí "ứng dụng không khởi động" được ĐO, không đoán.** Trên máy tham
  chiếu, **không một biến nào** trong các nhóm đó đang được đặt, nên chi phí
  thực tế hôm nay **bằng không**. **Phần dư:** trên một máy có đặt biến định
  tuyến mạng cho việc khác, ứng dụng **sẽ không khởi động**; đường thoát đã ghi
  là **bỏ biến khỏi phiên chạy**, **không** sửa cơ chế chặn.

**Năm quyết định này KHÔNG mở cấp B.** Chúng là điều kiện tiền đề, và **hai
trong số chúng thực ra THÊM một cổng từ chối mới.**

## I.5 Cấp C — bốn cổng bằng chứng của nền tảng

| Cổng | Cần chứng minh gì | Trạng thái | Việc nào cần chủ dự án xác nhận |
|---|---|---|---|
| **0-S** kỹ thuật + phạm vi | Danh tính/token bot chuẩn; kênh thoại nhóm; audio/PCM nhận vào; ánh xạ người tham gia; API/SDK/phiên bản và quyền cần thiết **được nền tảng xác nhận hoặc tài liệu hoá** | **CHƯA ĐÓNG** — tài liệu chứng minh giao thức hỗ trợ nhận dữ liệu ở mức client, **chưa** chứng minh route triển khai bot được hỗ trợ | **Tạo app/bot là tác động ra ngoài** — cần chủ dự án xác nhận trước |
| **0-P** route được hỗ trợ + policy | Một trace tái lập được theo route **được hỗ trợ**; rà điều khoản **ở ngày triển khai**; xác định quy trình review/duyệt | **CHƯA ĐÓNG** — đã trích được điều khoản chính thức và lập được danh sách nghĩa vụ; **chưa** có xác nhận rằng **mục đích/route của MeetAI** được phép | Cần một **privacy policy** và một **luồng yêu cầu xoá** trước pilot |
| **0-C** an toàn consent/media | Thứ tự *packet → giải mã → PCM → nhận dạng* **được quan sát trên một bản dựng cụ thể**; vào giữa buổi, kết nối lại, đổi ánh xạ luồng, đua với việc thu hồi, và việc hủy — đều được kiểm | **CHƯA ĐÓNG** — không có bản dựng tích hợp, không có phép đo | — |
| **0-U** người dùng chọn chính sách | Chế độ đồng thuận; có lưu ghi chú/transcript; nhật ký trả lời; thời hạn giữ biên nhận; **câu chữ** về việc lưu ở tầng ứng dụng | **CHƯA ĐÓNG** | **Toàn bộ cổng này là [CHỜ SƠN]** |

**Và đây là hệ quả cần nói rõ nhất của cả phần I:**

> **Đóng hết bốn cổng vẫn CHƯA ĐỦ.** Chúng là điều kiện **cần**. Độc lập với
> chúng, **ba thành phần chưa tồn tại** — bộ nhận âm thanh vào, thành phần nhận
> dạng tiếng nói, thành phần suy luận — và **không nơi phát nào tới được cuộc
> họp**.

**Một ticket hỗ trợ không thay thế được policy hay consent**, và một câu trả lời
chung **không** được coi là một sự cho phép. Chưa có yêu cầu nào được gửi tới
nền tảng; một bản nháp câu hỏi tồn tại và **chưa gửi**.

## I.6 Hai đường độc lập — đừng gộp thành một mốc

```
ĐƯỜNG 1 — mô hình cục bộ                ĐƯỜNG 2 — nền tảng họp
──────────────────────────              ──────────────────────────
chọn cách lấy số đo bộ nhớ              chọn chế độ đồng thuận,
      ↓                                 cách lưu trữ, câu chữ
duyệt HAI ngưỡng RAM (riêng)                  ↓
      ↓                                 rà điều khoản ở ngày triển khai
ghim digest mô hình                           ↓
      ↓                                 khảo sát khả năng nhận audio nhóm
đặt + khai báo cô lập đường ra                ↓
      ↓                                 quan sát thứ tự xử lý trên
MỘT lần chạy có giám sát                một bản dựng cụ thể
trên dữ liệu tổng hợp                         ↓
                                        xây BA thành phần còn thiếu

        ĐƯỜNG 1 KHÔNG MỞ ĐƯỜNG 2, VÀ NGƯỢC LẠI.
        Cấp A nằm ngoài cả hai và chạy song song được.
```

**Một hiệu chỉnh đáng ghi, vì tài liệu nội bộ từng nói quá:** chọn được chế độ
đồng thuận **không mở khoá điều gì quan sát được ngay** — vì **chưa có mã nào
gọi tới cổng đó** và **chưa có nơi phát nào tồn tại**. Nó là **cần** và **đi
trước**; nó **không đủ**.

## I.7 Mốc kế tiếp — đầu vào, công việc, nghiệm thu, bằng chứng, chủ sở hữu

**Đơn vị là LÁT, không phải ngày.** Hai cột cuối tách **khối lượng công việc**
khỏi **thời gian chờ**, đúng vì chúng là hai thứ khác nhau và chỉ một trong hai
ước lượng được.

| Mốc | Đầu vào | Công việc | Tiêu chí nghiệm thu | Bằng chứng cần có | Chủ sở hữu | Khối lượng *(ước lượng, không cam kết)* | Chờ gì |
|---|---|---|---|---|---|---|---|
| **M1** Chọn cách lấy số đo bộ nhớ | Ba phương án đã mô tả kèm rủi ro còn lại | — | Có một lựa chọn **được ghi lại** | Một dòng quyết định có căn cứ | **Chủ dự án** | **0 lát** | Một quyết định |
| **M2** Phép đo bám đúng tiến trình | Bản mẫu đã kiểm chứng trên tiến trình con thật | Nối bản mẫu vào quy trình đo | Công cụ mở **một** thẻ tiến trình và giữ suốt lần chạy | Kiểm thử trên tiến trình con thật + mutation chứng minh kiểm thử bắt được việc quay lại cách cũ | Tác nhân kỹ thuật | **1–2 lát** | **Không chờ gì** — làm được ngay |
| **M3** Một lần chạy có giám sát | M1 + M2 + bốn cổng đã mở | Chạy một lần đo | Thu được **đỉnh chính xác** từ bộ đếm hệ điều hành | Bản ghi kết quả mới. **Đổi định dạng bản ghi → cần duyệt riêng** | **Chủ dự án** | thời gian máy: **phút → giờ**, **kèm rủi ro hết bộ nhớ thật** | M1 + bốn cổng |
| **M4** Cổng RAM có ngưỡng | M3 | Thay hằng số *không có giá trị* bằng một ngưỡng | Ngưỡng suy từ đỉnh **thật** + biên **đã duyệt** | Kiểm thử từ chối dưới ngưỡng, cho qua trên ngưỡng, + mutation | **Chủ dự án** duyệt biên | **1 lát nhỏ** | M3 |
| **M5** Rà điều khoản nền tảng ở ngày triển khai | Hai văn bản chính thức **đã đọc được** | Lập điều khoản thành **yêu cầu thiết kế** | Kết luận *được hỗ trợ / không / chưa rõ* cho **từng** điều khoản liên quan | Trích dẫn nguyên văn **kèm ngày truy cập** | Tác nhân kỹ thuật | **1–2 lát** | **Không chờ gì** |
| **M6** Khảo sát 0-S | M5 | Khảo sát khả năng nhận audio nhóm | Một route **được tài liệu hoá** hoặc một kết luận *không có route nào* | Tài liệu chính thức, hoặc một trace tái lập được | **Chủ dự án** xác nhận trước | **không ước lượng được** | **Tạo app/bot là tác động ra ngoài** |
| **M7** Đóng 0-U | — | — | Năm lựa chọn được ghi lại | Năm dòng quyết định | **Chủ dự án** | **0 lát** | Năm quyết định |

**Việc có thể làm NGAY mà không vượt ranh giới nào:** M2 · M5 · tiếp tục đóng
các khoảng trống kiểm thử · chuẩn bị M3 ở **dạng chỉ-kiểm-thử, không chạy**.

## I.8 Các giai đoạn xa hơn — chỉ là [ĐỀ XUẤT]

| Giai đoạn | Nội dung | Điều kiện tiên quyết |
|---|---|---|
| **Pilot giới hạn** | Một cuộc họp, người tham gia **đã đồng thuận tường minh**, có người giám sát, có thể dừng bất cứ lúc nào | Toàn bộ cấp B + cấp C; privacy policy; luồng yêu cầu xoá |
| **Vận hành cá nhân** | Dùng thường xuyên bởi **một** người trên **một** máy | Pilot cho kết quả đo được; ngưỡng tin cậy **đã calibrate** |
| **Mở rộng sau khi có bằng chứng** | Xem [phần J](#j-khả-năng-mở-rộng-và-chiến-lược-dài-hạn) | Mỗi bước có cổng riêng |

**Không giai đoạn nào trong bảng này có ngày**, và không bảng nào trong tài liệu
này nên được đọc như một lịch.

---

# J. Khả năng mở rộng và chiến lược dài hạn {#j-khả-năng-mở-rộng-và-chiến-lược-dài-hạn}

## J.1 Lộ trình hiện tại phù hợp với mục tiêu hiện tại

Mục tiêu trước mắt là **một người dùng, trên một máy riêng**. Kiến trúc hiện tại
phù hợp với mục tiêu đó, và **sự phù hợp đó là một lựa chọn, không phải một hạn
chế tình thế**: nó cho phép "dữ liệu không ra khỏi máy" là thuộc tính **cấu
trúc**.

## J.2 Điều gì phải THIẾT KẾ LẠI nếu phạm vi đổi

**Không giả định kiến trúc hiện tại đã hỗ trợ bất kỳ mục nào dưới đây.**

| Nếu sau này cần | Phải thiết kế lại cái gì | Vì sao hiện tại không hỗ trợ |
|---|---|---|
| **Nhiều người dùng** | Mô hình danh tính, phân tách dữ liệu, uỷ quyền theo người | Hiện **không có** người quản trị tách biệt với người dùng; tri thức là **một** không gian |
| **Nhiều máy** | Đồng bộ có mã hoá, giải quyết xung đột có audit | Hiện **không có lưu trữ bền vững nào**; đường dẫn **bắt buộc tương đối trong dự án** — chính cơ chế chặn đồng bộ đám mây |
| **Nhiều cuộc họp đồng thời** | Vòng đời tiến trình mô hình, hàng đợi, lập lịch nạp/giải phóng | **[ĐÃ ĐO]** Phần cứng tham chiếu **không** đủ: đỉnh một lần chạy đã vượt RAM khả dụng |
| **Cloud** | Toàn bộ threat model, và cả đề xuất giá trị | **Mâu thuẫn trực tiếp** với nguyên tắc dữ liệu không ra khỏi máy nếu dùng với dữ liệu thật |
| **Nhiều nền tảng họp** | Mỗi adapter chịu trách nhiệm **riêng** về consent, danh tính, dữ liệu và khả năng kỹ thuật | Giao diện adapter **đã tách ba mặt phẳng** — đây là phần kiến trúc hiện tại **đã** chuẩn bị |

**Một điều kiến trúc hiện tại ĐÃ chuẩn bị đúng:** lõi ra quyết định được tách
khỏi kênh giao tiếp. Cùng một tầng tri thức/chính sách có thể phục vụ nhiều kênh
— và đó là lý do giao diện adapter tồn tại trước khi có adapter thật nào.

## J.3 Thứ tự tối ưu hoá — và nó là một thứ tự, không phải một danh sách

```
1. TÍNH ĐÚNG và AN TOÀN       ← nếu sai ở đây, mọi thứ sau vô nghĩa
          ↓
2. KHẢ NĂNG TÁI LẬP           ← không tái lập thì không đo được cải thiện
          ↓
3. FOOTPRINT (bộ nhớ, đĩa)    ← đang là ràng buộc cứng trên máy tham chiếu
          ↓
4. ĐỘ TRỄ                     ← chỉ đo được sau khi có đường suy luận
          ↓
5. MỞ RỘNG                    ← chỉ sau khi 1-4 có số
```

**Lý do thứ tự này, không phải một thứ tự khác:** tối ưu độ trễ trước khi có
tính đúng sẽ tạo ra một hệ thống trả lời sai nhanh hơn. Và **[ĐÃ ĐO]** trên máy
tham chiếu, footprint đi trước độ trễ vì nó là ràng buộc **cứng**: một lần chạy
có thể làm hệ thống hết bộ nhớ, trong khi độ trễ chỉ làm trải nghiệm xấu.

## J.4 Những lựa chọn tương lai, và điều kiện để xét chúng {#j4-những-lựa-chọn-tương-lai-và-điều-kiện-để-xét-chúng}

**Không mục nào dưới đây là cam kết.** Mỗi mục có một điều kiện cụ thể, và điều
kiện đó là một **phép đo** hoặc một **sự phê duyệt**, không phải một ngày.

| Lựa chọn | Trạng thái | Điều kiện để xét |
|---|---|---|
| **Embedding / RAG vector** | **[ĐỀ XUẤT]**, hiện **`absent` cố ý** | Một benchmark **chứng minh cải thiện** so với tra cứu metadata + từ khoá hiện tại. Nguyên tắc dài hạn: khớp chính xác theo metadata/từ khoá **trước**, embedding **sau** khi eval chứng minh lợi ích; **provenance luôn bắt buộc** |
| **Fine-tuning (LoRA/QLoRA)** | **[ĐỀ XUẤT]** — chủ dự án nêu là hướng **mong muốn** | Có một bộ dữ liệu **hợp pháp và được đồng thuận**; và **không** huấn luyện từ nội dung họp |
| **Huấn luyện mô hình nền từ đầu** | **ngoài phạm vi** | — |
| **Cloud / multi-tenant** | **[ĐỀ XUẤT]** xa | Đổi đề xuất giá trị ⇒ cần **[CHỜ SƠN]** ở mức chiến lược |
| **TTS / giọng nói** | **[ĐỀ XUẤT]** | **Không** phải phụ thuộc của MVP. Nếu làm: giọng phải **tự công khai**; nhân bản giọng cần **phê duyệt riêng** + license/consent cho dữ liệu huấn luyện; người dùng **tắt được ngay** |
| **Connector công việc (repo/ticket/board)** | **[ĐỀ XUẤT]** | **Chọn từng nguồn**, chỉ-đọc, allowlist theo project, token phạm vi tối thiểu, cache tối thiểu. **Không hút toàn bộ tài khoản**. Mọi thứ thu được là **card ứng viên**, chờ chủ dự án duyệt |
| **Router nhiều mô hình theo vai trò** | **[ĐỀ XUẤT]** | Benchmark **theo thiết bị**. **Không** khoá kiến trúc vào một kích thước mô hình: lượng tử hoá chỉ giảm **trọng số**; bối cảnh/KV cache và runtime **vẫn chiếm tài nguyên** |
| **Giao diện trợ năng / kênh nhập thay thế** | **[ĐỀ XUẤT]** nghiên cứu, có điều kiện | Chỉ như một kênh để người dùng **chủ động** nhập lệnh, với **độ tin cậy đo được** và **xác nhận tường minh**. **Không** được diễn đạt như "đọc suy nghĩ"; **lõi sản phẩm không phụ thuộc nhánh này** |

**Một quy tắc đầu tư/dừng, đã ghi trong tài liệu chiến lược:** mở rộng **khi có
lợi ích người dùng đo được**, consent và quyền dữ liệu rõ, có fallback an toàn,
và một prototype **đã qua cổng**. **Dừng** một nhánh nếu nó làm tăng rủi ro
quyền riêng tư hoặc quyền tự chủ mà **không** tăng lợi ích, hoặc nếu nó đòi suy
rộng từ một demo phòng thí nghiệm sang đời thực.

## J.5 Chân trời dài hạn — định hướng, không phải lời hứa tiến độ

**[ĐỀ XUẤT]** Chuyển giai đoạn **theo cổng bằng chứng**, không theo lịch.

| Chân trời | Mục tiêu | Cổng để đi tiếp |
|---|---|---|
| **H0** Nền tin cậy | Tri thức có quản trị; quyền đại diện rõ | Mọi quan điểm cá nhân **truy được về bằng chứng**; sửa/xoá đúng phạm vi; **không cam kết nào** bị lọt qua kiểm thử đối kháng |
| **H1** Đại diện đa kênh | Một lõi chính sách/bối cảnh qua nhiều kênh | Consent/permission **theo từng nền tảng**; cô lập trạng thái; độ tin cậy và độ trễ **đo được**; người dùng kiểm soát **đúng lời, đúng nơi** |
| **H2** Chủ động nhưng có giới hạn | Phát hiện việc cần nhắc, hỏi, hoặc chuẩn bị | Tỷ lệ hành động sai/trái phép **thấp**; mọi tác động **đảo ngược được**; ranh giới phê duyệt **kiểm thử được** |
| **H3** Đa phương thức / trợ năng | Thêm kênh vào/ra ngoài giọng nói | **Đánh giá độc lập**; ổn định qua các phiên; kích hoạt **tường minh**; có review privacy/security |
| **H4** Kênh nhập thực nghiệm *(tuỳ chọn)* | Nhánh nghiên cứu | Nhân bản được bởi nghiên cứu **đã phản biện**; kiểm trên dữ liệu held-out theo người; sai số/độ trễ dùng được; **xác nhận tường minh**; và **lõi sản phẩm KHÔNG phụ thuộc nhánh này** |

**Thời gian không phải bằng chứng.** Không có năm cụ thể nào được gán cho H3/H4,
và MeetAI vẫn là một sản phẩm có giá trị nếu các nhánh đó **không bao giờ** khả
thi.

## J.6 Chiến lược phiên bản mô hình, digest, license, rollback, cập nhật

| Mục | Chính sách | Trạng thái |
|---|---|---|
| **Ghim phiên bản** | Mô hình ghim bằng **repo + revision 40 ký tự**; runtime ghim bằng **bản dựng + commit**; bộ chấm điểm ghim bằng SHA-256 trong artifact | **[ĐÃ TRIỂN KHAI]** trong các lần đo |
| **Digest** | **Bắt buộc**, không có cơ chế override. Sổ ghi **rỗng → từ chối mọi lần chạy** | **[ĐÃ TRIỂN KHAI]**; **[CHỜ SƠN]** ghim giá trị |
| **Review license** | License xác nhận ở **mức repo**; tài nguyên phi thương mại được **tách nhãn riêng trong báo cáo** và **không** đủ điều kiện cho sản phẩm | **[ĐÃ TRIỂN KHAI]** nguyên tắc; **[CHỜ BẰNG CHỨNG]** ở mức artifact |
| **Rollback** | **Một lát = một commit**, nên quay lại được theo lát. Artifact benchmark **không bao giờ bị ghi đè**: việc chấm lại tạo một tệp **mới** có cờ *dẫn xuất*, ghi nguồn và dấu của bộ chấm | **[ĐÃ TRIỂN KHAI]** |
| **Cập nhật** | Nâng một phụ thuộc đã ghim chính xác là **một hành động có chủ ý, được review** — kiểm thử so khớp cấu hình **chính xác** sẽ sai cho tới khi có người xem lại | **[ĐÃ TRIỂN KHAI]** |
| **Hỗ trợ** | Một người dùng, một máy. **Không** có SLA, và tài liệu này **không** đề xuất một SLA nào | — |

---

# K. Kỹ năng, gói công việc, kết quả bàn giao, rủi ro và quyết định {#k-kỹ-năng-gói-công-việc-kết-quả-bàn-giao-rủi-ro-và-quyết-định}

## K.1 Kỹ năng và yêu cầu

Phân biệt **năng lực hiện có** (đã thể hiện trong repo) với **nhu cầu hỗ trợ**
(chưa có, hoặc không thể tự làm).

### Đã thể hiện trong repo

| Kỹ năng | Bằng chứng trong repo |
|---|---|
| **Python** (chính) | 10 722 dòng mã lõi, **mypy strict** xanh trên 87 tệp |
| **Thiết kế fail-closed** | Ba cổng an toàn, 29/29 mutation |
| **Kiểm thử tính chất an toàn** | 26 195 dòng kiểm thử; tỷ lệ ≈ 2,4× mã lõi; mutation testing như một bước thường quy |
| **Phân tích cú pháp để cưỡng chế bất biến** | Nhiều kiểm thử dùng AST thay vì tìm theo văn bản |
| **Benchmark có hợp đồng đo** | Mẫu số công bố theo nhóm; bootstrap trên **hiệu số**; ba đường tính độc lập khớp |
| **Đọc tài liệu chính thức để đóng/mở một cổng** | 7 ADR, 20 ghi chú nghiên cứu, trích dẫn kèm ngày truy cập |
| **Xử lý tiếng Việt ở mức ký tự** | Khử dấu có xử lý riêng cho `đ`; chuẩn hoá Unicode; đơn vị lỗi là **âm tiết** |
| **Windows API qua `ctypes`**, không thêm phụ thuộc | Bản mẫu đọc bộ đếm bộ nhớ theo **thẻ tiến trình** |
| **Git theo lát** | 118 commit, mỗi lát một commit |

### Nhu cầu hỗ trợ — và loại hỗ trợ

| Nhu cầu | Loại | Vì sao không thể tự làm |
|---|---|---|
| **Quyết định chính sách quyền riêng tư** | **[CHỜ SƠN]** | Là cam kết với người tham gia cuộc họp |
| **Duyệt 16 nhãn đánh giá** | **[CHỜ SƠN]** | Tự duyệt nhãn của mình làm phép đánh giá **mất ý nghĩa** |
| **Cấu hình hệ thống** (cô lập đường ra, giới hạn công suất GPU) | **[CHỜ SƠN]** | Là thay đổi cấu hình máy |
| **Tạo app/bot trên nền tảng; gửi câu hỏi tới nền tảng** | **[CHỜ SƠN]** | Là **tác động ra bên ngoài** |
| **Tư vấn pháp lý** về điều khoản nền tảng | ngoài năng lực | Tài liệu này là **tóm tắt kỹ thuật**, không phải tư vấn pháp lý |
| **Gán nhãn thủ công**: tên riêng trong bối cảnh họp; nói chồng tiếng Việt | nguồn lực dữ liệu | Không corpus có license phù hợp trong phạm vi; **một** annotator không tạo được chuẩn vàng |
| **Đo trên ≥ 2 máy khác cấu hình** | nguồn lực phần cứng | Cần để biết đại lượng nào **thật sự** ràng buộc |
| Thiết bị đo điện ở ổ cắm | nguồn lực phần cứng | Công cụ hiện tại chỉ báo board GPU |

## K.2 Gói công việc

Theo bố cục "nhiệm vụ" của một đề cương dự án, nhưng mỗi gói ghi rõ **trạng
thái thật**:

| # | Gói công việc | Trạng thái |
|---|---|---|
| W1 | Khung cục bộ: cấu hình fail-closed, xử lý secret, logging chỉ metadata, giao diện web loopback với telemetry tắt tường minh | **HOÀN TẤT** (Phase 0) |
| W2 | Lõi an toàn: máy trạng thái đồng thuận, vòng đời phiên, cổng media, giao diện adapter, planner, schema phát ngôn, cổng quyền hạn, card tri thức, phân loại người nhận, harness đánh giá | **HOÀN TẤT** (Phase 1) |
| W3 | Khả thi mô hình cục bộ: tách artifact, chính sách offline fail-closed, bốn cổng cấp B | **PARTIAL/OPEN** — đã quyết, **chưa thử trên một lần chạy thật** |
| W4 | Benchmark nhận dạng tiếng Việt | **PARTIAL/OPEN** — 3/8 trục chưa đạt |
| W5 | Benchmark mô hình ngôn ngữ lượng tử hoá | **PARTIAL/OPEN** — chi phí tháng và độ ổn định **chưa chứng minh được** |
| W6 | Nối phép đo bộ nhớ chính xác vào quy trình đo (M2) | **LÀM ĐƯỢC NGAY** |
| W7 | Lập điều khoản nền tảng thành yêu cầu thiết kế (M5) | **LÀM ĐƯỢC NGAY** |
| W8 | Chứng minh nền tảng: 0-S, 0-P, 0-C | **BỊ CỔNG CHẶN** |
| W9 | Vertical slice có consent: 0-S + 0-P + 0-C + 0-U | **BỊ CỔNG CHẶN** |
| W10 | Pilot | **BỊ CỔNG CHẶN** |

## K.3 Kết quả bàn giao

| Giai đoạn | Kết quả bàn giao | Cách bàn giao |
|---|---|---|
| **Hiện tại** | Mã lõi + bộ kiểm thử + **72 dòng nghĩa vụ truy vết được** + 7 ADR + 20 ghi chú nghiên cứu + runbook + tài liệu này | Repo Git; **snapshot công khai có lịch sử tách riêng** |
| **Hiện tại** | Hai lệnh **chỉ đọc**: `meetai status` / `dry-run` và `benchmarks.readiness` | Chạy được ngay |
| **Sau cấp B** | Artifact phép đo có digest, có mô tả hợp đồng đo; cổng RAM **có ngưỡng** | JSON artifact trong thư mục cố định, **không** theo dõi bởi Git |
| **Sau cấp C** | Trace tái lập được cho route nền tảng; privacy policy; luồng yêu cầu xoá | Tài liệu + bản ghi |
| **Sau pilot** | Báo cáo đánh giá **theo nhóm, có mẫu số**, kèm giới hạn | Tài liệu |

## K.4 Bảng rủi ro

**Quy ước:** chỉ ghi xác suất/ảnh hưởng khi **có cơ sở đo được**. Khi không có,
ghi **định tính** và nói rõ vì sao — vì một con số bịa ra ở cột xác suất còn tệ
hơn một ô để trống.

| # | Rủi ro | Đánh giá | Cơ sở | Kiểm soát hiện có |
|---|---|---|---|---|
| R1 | **Hết bộ nhớ khi chạy mô hình trên CPU** | **Đã quan sát ở một hệ gần kề** | **[ĐÃ ĐO]** Đỉnh 4 438 MiB > RAM khả dụng 2 897–3 966 MiB; và một tiền lệ hết bộ nhớ với dự đoán thiếu **≥ 1 576 MiB** | Bốn cổng từ chối mọi lần chạy; cổng từ chối **trước khi** đọc bộ nhớ |
| R2 | **Mô hình trả lời khi không nên** | **Định lượng được** | **[ĐÃ ĐO]** Bỏ sót việc nên từ chối **5/9** | Lớp answerability độc lập; nhưng **[ĐÃ ĐO]** trong 12/16 tình huống eval, nó là lớp **DUY NHẤT** |
| R3 | **Chỉ thị tiêm làm mô hình khai sai một phê duyệt** | **Đã quan sát** | **[ĐÃ ĐO]** 1/6, và **cổng không bắt được** | Card sửa-sau-duyệt thành không dùng được; **phần dư vẫn mở** |
| R4 | **Vượt quyền trong một cuộc họp thật** | **Định tính — nghiêm trọng nhất** | **Chưa đo được**: chưa có cuộc họp thật nào. Gán một xác suất ở đây sẽ là phát minh | Ba lớp độc lập; **[ĐÃ ĐO]** 0/8 vượt cấm tuyệt đối trên corpus tổng hợp — **nhưng** corpus đó do chính tác nhân viết |
| R5 | **Tệp thực thi gốc gọi ra mạng** | **Định tính — phần dư thật** | Không quan sát được **trong** tiến trình Python, nên **không có** phép đo nào có thể hạ rủi ro này từ bên trong | Quyết định #5 **đòi** cô lập tầng hệ điều hành; **[CHỜ SƠN]** |
| R6 | **Thư mục dự án nằm trong một thư mục đồng bộ đám mây** | **Định tính** | Validator **không thấy được** điều này | Đường dẫn bắt buộc tương đối; **phần dư ghi rõ** |
| R7 | **Nền tảng không có route được hỗ trợ cho việc nhận audio nhóm** | **Định tính — có thể chặn vĩnh viễn cấp C** | **[ĐÃ ĐO]** Hai trang tài liệu độc lập cùng cho thấy khoảng trống | **Không pivot** sang SDK khác; nó là **chỗ đỗ**. Kiến trúc giữ adapter interface + demo tổng hợp |
| R8 | **Độ trễ không đạt mục tiêu 1–2 giây** | **Chưa đo được** | Phụ thuộc quyết định về đường suy luận | **[ĐÃ ĐO]** GPU mua được prefill (6,2×) nhưng gần như không mua được decode (1,16×) |
| R9 | **Kill switch báo "đã kill" khi mô hình vẫn chạy** | **Đã biết, đã ghi** | **[ĐÃ ĐO]** Công tắc chỉ đổi một giá trị liệt kê | Là **một trong ba điều kiện** phải xử lý trước khi mở một máy chủ mô hình |
| R10 | **Một phụ thuộc nâng phiên bản và mở lại một bề mặt telemetry** | **Định tính, đã giảm** | — | Ghim **chính xác**; kiểm thử so khớp **từ điển chính xác**; bốn biến thể cài kèm bị cấm |
| R11 | **Chi phí vượt mong muốn của chủ dự án** | **Chưa đo được** | Hai lý do độc lập làm phép đo hiện tại là **chặn dưới** | **Không** con số chi phí nào được nêu |
| R12 | **Dự án dừng vì một quyết định không được đưa ra** | **Định tính** | 12+ mục đang chờ | Mọi mục chờ được ghi là **blocker riêng**, **không** gộp vào "thời gian phát triển" |

## K.5 Bảng quyết định

| # | Nội dung | Người quyết | Vì sao cần | Ảnh hưởng nếu tiếp tục chờ | Có thể chuẩn bị gì **mà không quyết thay** |
|---|---|---|---|---|---|
| D1 | Chế độ đồng thuận; TTL; vào họp giữa buổi | **Chủ dự án** | Cam kết với người tham gia | Cổng 0-U mở ⇒ **mọi** xử lý media bị chặn | **Đã xây cả hai thiết kế** sau một interface, mặc định đóng |
| D2 | Lưu transcript / ghi chú / nhật ký; thời hạn giữ; **câu chữ** thông báo | **Chủ dự án** | Cam kết với người tham gia | Không có lưu trữ bền vững nào được bật | Thiết kế vault; **không** viết mã ghi đĩa |
| D3 | **16 nhãn** đánh giá | **Chủ dự án** | Nhãn **định nghĩa hành vi đúng** | Không calibrate được ngưỡng tin cậy ⇒ nó vẫn là **placeholder** | Bộ 16 tình huống **đã lập**, đã chạy qua cổng, đã đối chiếu từng dòng |
| D4 | Cách lấy số đo bộ nhớ (A/B/C) | **Chủ dự án** | Một phương án là **chạy mô hình thật** | M3 bị chặn ⇒ M4 bị chặn ⇒ cấp B bị chặn | **M2 làm được ngay**: nối phép đo chính xác, **không chạy mô hình** |
| D5 | **Hai** ngưỡng RAM (riêng biệt) | **Chủ dự án** | Hai nền bằng chứng **không so sánh được** (n=1 so với n=0) | Mọi đường chạy mô hình tiếp tục bị từ chối | Ba phương án **đã mô tả kèm rủi ro còn lại của từng cái** |
| D6 | Ghim digest mô hình | **Chủ dự án** | Là **khẳng định rằng một tệp cụ thể là tệp đúng** | Mọi lần chạy bị từ chối | Cơ chế **đã cưỡng chế**; sổ ghi để rỗng |
| D7 | Đặt cô lập đường ra, rồi khai báo | **Chủ dự án** | Là **thay đổi cấu hình hệ thống** | Mọi runner mô hình bị từ chối | Cơ chế đòi hỏi **đã triển khai**; đọc từ **mã nguồn**, không từ biến môi trường |
| D8 | Tạo app/bot trên nền tảng; gửi câu hỏi | **Chủ dự án** | Là **tác động ra bên ngoài** | 0-S không khảo sát được | **M5 làm được ngay**: lập điều khoản thành yêu cầu thiết kế |
| D9 | `model.path` / nguồn dẫn xuất trong artifact | **Chủ dự án** | Đổi **ý nghĩa** của bản ghi đã lưu | M3 không ghi được bản ghi mới | Định dạng **đã mô tả** |
| D10 | Cấp phép cho một nơi phát media | **Chủ dự án** | Mở một đường ra thật | **Không** nơi phát nào tới được cuộc họp | Cơ chế permit **đã triển khai**: hiệu lực theo **danh tính**, và permit **chết cùng cổng** |
| D11 | Có công khai tên gọi của chủ dự án trong tài liệu | **Chủ dự án** | Là **dữ liệu cá nhân** | Tài liệu gọi bằng **vai trò** | Đã làm: tài liệu này **không** chứa tên |
| D12 | Phạm vi mà một câu hỏi trong họp ánh xạ sang | **Chủ dự án** | Quyết định tra cứu chạm dữ liệu nào | Phần chuẩn bị không nối được | Đã **chuẩn bị** quyết định, **không cài** gì phụ thuộc vào nó |
| D13 | Đổi giới hạn công suất GPU | **Chủ dự án** | Là cấu hình hệ thống | Decode vẫn bị giới hạn bởi băng thông | Đã đo **chỉ-đọc**, đã ghi nguyên nhân là **software cap**, không phải nhiệt |

**Không mục nào trong bảng này được một tác nhân kỹ thuật quyết thay.** Và không
khuyến nghị nào trong tài liệu này được nâng thành phát ngôn của chủ dự án.

---

# L. Kết luận {#l-kết-luận}

## L.1 Tình trạng thật

MeetAI hôm nay là một **lõi quyết định đã chạy được và đo được**, với các ranh
giới an toàn được cưỡng chế bằng **cơ chế** thay vì bằng lời hứa, và với một
danh sách rõ ràng những điều **chưa** chứng minh.

**Ba câu cần nói thẳng, vì chúng dễ bị đọc trượt:**

1. **Cấp A chạy được không nói gì về chất lượng mô hình hay nhận dạng tiếng Việt
   trong họp thật.** Nó chứng minh đúng một việc: lõi quyết định chạy tất định
   và không để lại dấu vết trên đĩa.
2. **Năm quyết định đã đưa ra theo uỷ quyền không làm cấp B an toàn hơn.** Chúng
   làm các điều kiện trở nên **rõ ràng và được cưỡng chế**. Thứ còn chặn vẫn còn
   chặn — và hai trong năm quyết định thực ra **thêm** một cổng từ chối mới.
3. **Đóng hết bốn cổng của nền tảng vẫn chưa đủ.** Chúng là điều kiện **cần**;
   ba thành phần vẫn phải được xây, và không nơi phát nào tới được cuộc họp.

**Đây không phải tuyên bố sẵn sàng cho sử dụng thật.**

## L.2 Bước kế tiếp có thể làm ngay

**Không cần quyết định nào, không vượt ranh giới nào:**

| # | Việc | Khối lượng *(ước lượng, không cam kết)* |
|---|---|---|
| 1 | **M2** — nối phép đo bộ nhớ chính xác vào quy trình đo, **không chạy mô hình** | 1–2 lát |
| 2 | **M5** — lập điều khoản nền tảng thành yêu cầu thiết kế, kèm trích dẫn và ngày truy cập | 1–2 lát |
| 3 | Tiếp tục đóng các khoảng trống kiểm thử đã ghi | liên tục |
| 4 | Chuẩn bị **M3** ở **dạng chỉ-kiểm-thử** | 1 lát |

**Và bước có giá trị cao nhất không phải một lát mã:** đó là **năm quyết định
của cổng 0-U** (D1, D2) và **lựa chọn cách lấy số đo bộ nhớ** (D4). Chúng mất
**0 lát** để triển khai và đang chặn hai đường song song.

---

# M. Tài liệu tham khảo {#m-tài-liệu-tham-khảo}

## M.1 Nguồn chính thức bên ngoài

Mọi nguồn dưới đây đã được đọc **từ địa chỉ gốc**, không qua bản tóm tắt của
công cụ tìm kiếm. **Một bản tóm tắt từ công cụ tìm kiếm không được dùng để đóng
một cổng bằng chứng.**

| # | Nguồn | Ngày truy cập | Kết luận được nguồn này đỡ |
|---|---|---|---|
| 1 | Discord **Developer Terms of Service** — `support-dev.discord.com/hc/en-us/articles/8562894815383-Discord-Developer-Terms-of-Service` *(hiệu lực 2024-07-08, cập nhật 2024-06-06)* | **2026-10-10** | §5 nghĩa vụ privacy policy; §5(b) nghĩa vụ xoá nhanh + cách dễ tiếp cận để yêu cầu sửa/xoá; §6 quyền App Review — [§G.6](#g6-nền-tảng-họp--điều-khoản-chính-thức-đã-đọc-được) |
| 2 | Discord **Developer Policy** — `support-dev.discord.com/hc/articles/8563934450327-Discord-Developer-Policy` *(hiệu lực 2024-07-08, cập nhật 2024-06-06)* | **2026-10-10** | Mục 2 xin phép trước; mục 3 cấm né tính năng privacy/safety, tôn trọng opt-out; mục 15 giới hạn dữ liệu API; mục 21 cấm huấn luyện từ *message content* — [§G.6](#g6-nền-tảng-họp--điều-khoản-chính-thức-đã-đọc-được) |
| 3 | Discord **Voice Connections** — `docs.discord.com/developers/topics/voice-connections` | **2026-10-10** | UDP dùng cho **cả nhận và gửi**; từ 2026-03-01 chỉ hỗ trợ thoại mã hoá đầu-cuối; **không** tài liệu hoá ánh xạ luồng → người dùng cho bot nhóm — [§G.6](#g6-nền-tảng-họp--điều-khoản-chính-thức-đã-đọc-được) |
| 4 | Discord **Gateway Events** — `docs.discord.com/developers/topics/gateway-events` | **2026-10-10** | Sự kiện "đang nói" có định danh luồng, **không** chứng minh ánh xạ sang định danh người dùng |
| 5 | Discord **Social SDK Client reference** — `discord.com/developers/docs/social-sdk/classdiscordpp_1_1Client.html` | **2026-10-10** | Callback nhận audio có định danh người dùng, **nhưng** nằm trong luồng gọi thoại của SDK đó ⇒ **chỗ đỗ**, không phải đường cho MVP |
| 6 | Tài liệu bộ nhớ của **Microsoft Windows** (Job object, working-set limit, `GlobalMemoryStatusEx`, `PeakWorkingSetSize`) | **2026-10-10** | Ba kết luận ở [§F.2](#f2-bốn-đại-lượng-bộ-nhớ--và-vì-sao-phải-tách-chúng) về vì sao tầng hệ điều hành giúp ít hơn tưởng |
| 7 | **Google Gemma — hướng dẫn bộ nhớ** — `ai.google.dev/gemma/docs/core.md` | ghi trong tài liệu chiến lược | Bộ nhớ suy luận cơ bản **chưa gồm** bối cảnh/KV cache và runtime ⇒ **không** suy khả năng chạy từ một con số trong model card — [§F.5](#f5-ba-hạ-tầng-khác-nhau--đừng-gộp) |
| 8 | `google/fleurs` — dataset card và API | **2026-10-07** | **CC-BY-4.0**, ungated; revision ghim; **mẫu số thật 361, card ghi 415** — [§H.5.2](#h52-nhận-dạng-tiếng-nói--fleurs-nhánh-license-permissive) |
| 9 | `Qwen/Qwen3-4B-GGUF` — repo và API | **2026-10-08** | Tag license **apache-2.0**, ungated; revision 40 ký tự được ghim — [§E.4](#e4-mô-hình-runtime-và-dữ-liệu--ứng-viên-chưa-chốt) |
| 10 | `leduckhai/VietMed` — API dataset | **2026-10-07** | Có cột giọng vùng; phân phối 5 lớp trong split test (một lớp n=21); **mâu thuẫn license** giữa paper và tag — [§H.5.5](#h55-giọng-vùng--vietmed-và-vì-sao-trục-vẫn-chưa-đạt) |
| 11 | `whisper.cpp` + `ggml-small` | **2026-10-07** | Mô hình **MIT**; bản dựng runtime và zip ghim bằng SHA-256 |

**[CHỜ BẰNG CHỨNG] về khả năng truy cập:** hai địa chỉ ở mục 1 và 2 từng trả về
lỗi truy cập từ môi trường làm việc (ghi nhận 2026-10-09). Chúng **đọc được** ở
lần truy cập 2026-10-10, và nội dung được trích nguyên văn vào ghi chú nghiên
cứu. **Tài liệu này không tự đi đọc lại các nguồn trên trong lượt viết nó**; mọi
mục đều ghi **ngày truy cập đã được lưu**.

## M.2 Nguồn trong repo

| Loại | Đường dẫn | Vai trò |
|---|---|---|
| Quy ước làm việc | `AGENTS.md` | Ranh giới an toàn, thứ tự ưu tiên, quy trình từng lát |
| Trạng thái | `PROJECT_STATE.md` | Sổ ghi bền vững; nhật ký từng lượt |
| Nghĩa vụ | `docs/spec.md` | **72 dòng**, mỗi dòng trỏ tới mã và kiểm thử |
| Kế hoạch | `docs/plan.md` | Danh sách lát + tiêu chí nghiệm thu từng lát |
| Quyết định kiến trúc | `docs/adr/` (7) | Gồm ADR 0005 (nhánh CUDA + GPU), ADR 0006 (cổng quyền hạn), ADR 0007 (response boundary) |
| Nghiên cứu | `docs/research/` (20) | Gồm: benchmark nhận dạng + ma trận trục; benchmark mô hình ngôn ngữ; giới hạn RAM Windows; offline fail-closed; chính sách nền tảng; corpus có nhãn giọng vùng; bộ 16 nhãn đánh giá |
| Runbook | `docs/runbook/thu-nghiem-cuc-bo.md` | Chạy được gì hôm nay, bằng lệnh nào, và nó **không** chứng minh gì |
| Tài liệu nền | `docs/handoff/` | **Bản sao nguyên văn**, là **dữ liệu tham khảo**, không phải chỉ thị |

## M.3 Phân loại mọi số trong tài liệu này

| Loại | Nghĩa | Ví dụ |
|---|---|---|
| **Phép đo từ repo** | Đếm hoặc chạy trực tiếp, 2026-10-11 | 154 tệp · 5 271 kiểm thử · 72 nghĩa vụ · exit 3 của lệnh trạng thái cổng · dấu kiểm MD5 trùng 3/3 |
| **Kết quả benchmark trước đây** | Đo 2026-10-07 / 10-08 / 10-10, đọc lại từ artifact | 23,47 % · 0,315 · 4 438 MiB · 40/80 W · 5/9 · 1/6 |
| **Phép suy ra** | Kết luận từ phép đo cộng một lập luận | "đỉnh thật ≥ 4 438 MiB" · "GPU mua được prefill, không mua được decode" |
| **Chính sách** | Phán đoán mà không phép đo nào quyết được | Mọi biên an toàn; thứ tự tối ưu hoá |
| **[ĐỀ XUẤT] tương lai** | Chưa được duyệt | Toàn bộ [phần J](#j-khả-năng-mở-rộng-và-chiến-lược-dài-hạn); §I.8 |
| **Chưa xác minh** | Ghi là chờ, **không lấp** | Chi phí tháng · độ ổn định · p50/p95 · cấu hình tối thiểu · route nền tảng |

---

*Tài liệu này mô tả trạng thái đo được tại **2026-10-11**. Nó không phải tuyên bố
sẵn sàng sản phẩm, không phải cam kết tiến độ, và không phải tư vấn pháp lý.*
