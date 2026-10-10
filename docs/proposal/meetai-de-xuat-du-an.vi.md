---
title: "MeetAI — Đề xuất dự án"
subtitle: "Trợ lý họp cá nhân, chạy cục bộ, tiếng Việt"
date: "2026-10-10"
lang: vi
---

# 0. Tài liệu này viết cho ai, và để làm gì

**Đối tượng đọc:** chủ dự án và bất kỳ người đọc kỹ thuật nào cần hiểu MeetAI
đang ở đâu trước khi bàn bước tiếp. Không giả định người đọc đã xem mã nguồn.

**Mục đích:** nêu vấn đề, phạm vi, trạng thái **có bằng chứng**, và những quyết
định còn phải đưa ra. Đây là tài liệu **có thể được công khai**, nên nó không
chứa định danh cá nhân, đường dẫn máy, thông tin đăng nhập hay nội dung cuộc họp.

**Một quy ước đọc, dùng suốt tài liệu.** Ba cách nói "chạy được" bị tách riêng,
vì gộp chúng là cách dễ nhất để nói quá:

| Cụm từ | Nghĩa |
|---|---|
| **Có thể chạy** | Lệnh tồn tại, phụ thuộc đủ, kết thúc không lỗi |
| **Được phép chạy** | Không vượt ranh giới an toàn nào đã ghi |
| **Đã chứng minh** | Có phép đo, và có kiểm thử mà xoá cơ chế đi thì kiểm thử sai |

Một thứ **có thể chạy** mà **chưa được phép** thì không chạy. Một thứ **được
phép và chạy được** vẫn **chưa chứng minh** gì cho tới khi có phép đo.

Tài liệu này **không** tuyên bố MeetAI sẵn sàng cho sử dụng thật, và **không**
đưa phần trăm tiến độ tổng — không có mẫu số đo được cho phần việc còn lại.

# 1. Vấn đề

Trong một cuộc họp trực tuyến, người chủ trì phải đồng thời nghe, nhớ bối cảnh
của những gì đã thống nhất trước đó, và trả lời. Phần "nhớ bối cảnh" là phần
máy làm tốt hơn người: nó đòi tra lại đúng thông tin đã được duyệt, đúng thời
điểm.

Nhưng một trợ lý nói thay người trong cuộc họp lại tạo ra một rủi ro mới, và đó
là rủi ro định hình toàn bộ thiết kế: **một câu nghe có thẩm quyền, nói nhân
danh người chủ trì, có thể tạo ra cam kết mà người đó không hề đưa ra.** Một
câu trả lời sai về số liệu còn sửa được; một lời hứa trái phép thì không.

MeetAI vì thế được xây quanh một nguyên tắc hẹp hơn "trợ lý thông minh": nó
**chỉ được nói những gì có bằng chứng đã duyệt đỡ phía sau**, và **không bao
giờ** được hứa, xác nhận thay, nhận việc, chốt hạn, bỏ phiếu hay phê duyệt.

# 2. Người dùng mục tiêu

**Một người.** Chủ dự án, trên máy cá nhân của chính họ, trong các cuộc họp mà
họ tham gia. Không phải sản phẩm nhiều người thuê, không phải dịch vụ chạy liên
tục, không có người quản trị tách biệt với người dùng.

Điều đó không phải hạn chế tạm thời mà là một lựa chọn kiến trúc: nó cho phép
"dữ liệu không ra khỏi máy" là một thuộc tính **cấu trúc** thay vì một lời hứa
trong chính sách.

# 3. Phạm vi và ngoài phạm vi

## 3.1 Trong phạm vi

- Nhận diện tiếng nói tiếng Việt, chạy **cục bộ**.
- Tra cứu thông tin đã được duyệt để trả lời đúng bối cảnh.
- Một cổng quyền hạn tất định, chặn mọi phát ngôn vượt quyền.
- Giao diện web **cục bộ** để theo dõi và tắt khẩn cấp.
- Nền tảng đầu tiên: một nền tảng họp có kênh thoại nhóm.

## 3.2 Ngoài phạm vi — và vì sao

| Ngoài phạm vi | Lý do |
|---|---|
| Gửi âm thanh hoặc bản ghi tới dịch vụ AI bên ngoài | Vi phạm nguyên tắc dữ liệu không ra khỏi máy. Có kiểm thử chặn. |
| Huấn luyện mô hình nền từ đầu | Không khả thi với phần cứng một máy cá nhân. |
| Học tự động từ nội dung họp | Biến mỗi cuộc họp thành dữ liệu huấn luyện là một rủi ro không cần thiết. |
| Tự động hoá tài khoản người dùng trên nền tảng họp | Trái điều khoản nền tảng. |
| Lưu bản ghi, ghi chú, nhật ký trả lời theo mặc định | Mặc định **tắt**; chỉ bật được sau khi có lựa chọn về đồng thuận. |
| Chạy dịch vụ 24/7 | Ứng dụng bật khi cần; mô hình bật/tắt được. |

# 4. Kiến trúc hiện có, và ranh giới an toàn

## 4.1 Đường đi của một câu trả lời

Đường đi dưới đây là **mã thật, chạy thật** hôm nay:

```
câu hỏi
  → tra cứu theo câu hỏi        (từ khoá + siêu dữ liệu, trong bộ nhớ)
  → kho tri thức                (duyệt, dấu nội dung, thay thế, hiệu lực, độ nhạy)
  → tập chứng cứ
  → đánh giá khả năng trả lời   (ba trạng thái, chỉ một trạng thái cho phép nói)
  → cổng quyền hạn              (ba lớp độc lập)
  → nơi phát
```

Điều quan trọng không nằm ở các bước, mà ở **thứ không tồn tại**: hiện **chưa
có** thành phần nào gọi nhận diện tiếng nói, suy luận mô hình, nhận âm thanh,
kết nối nền tảng họp, hay lưu trữ bền vững. Nơi phát duy nhất trong mã nguồn là
một danh sách trong bộ nhớ dùng cho kiểm thử.

Nói cách khác: **phần đã chạy được là lõi quyết định, không phải sản phẩm.**

## 4.2 Bốn ranh giới an toàn, và cơ chế đỡ chúng

**(a) Vắng mặt năng lực, không phải cấu hình năng lực.** Đây là nguyên tắc chi
phối. Một đường gửi dữ liệu ra ngoài bị chặn vì **thư viện cần thiết không được
cài**, chứ không vì "chưa cấu hình". Một cấu hình có thể bị đổi; một thứ không
tồn tại thì không.

**(b) Quyết định chưa trả lời là một trạng thái CHẶN.** Các lựa chọn về đồng
thuận và lưu trữ chưa được đưa ra, và chúng được biểu diễn bằng một trạng thái
"chờ quyết định" **chặn mọi xử lý âm thanh** — không phải bằng một giá trị mặc
định "hợp lý" do máy tự chọn. Ba chỗ từ chối độc lập cùng kiểm điều kiện này.

**(c) Danh sách cho phép, không phải danh sách cấm.** Lặp lại nhiều lần trong
dự án: một danh sách cấm thua ngay cái tên mới đầu tiên. Nhật ký chỉ ghi các
trường trong danh sách cho phép; chỉ hai tên tệp thực thi được nhận trên dòng
lệnh; chỉ các thư mục tương đối trong dự án được dùng làm nơi ghi.

**(d) Thông báo lỗi mô tả hình dạng, không mô tả giá trị.** Một lỗi in ra
"không đọc được phát ngôn (42 ký tự)", không in nội dung. Có kiểm thử ghép một
thông tin đăng nhập giả vào **mọi** kiểu cấu hình sai và khẳng định nó không
xuất hiện ở bất kỳ đầu ra nào.

## 4.3 Cổng quyền hạn — ba lớp, và sự độc lập là thiết kế

| Lớp | Làm gì |
|---|---|
| 0 | Phát ngôn phải khai một **loại hành vi được phép**; không khai thì **bị từ chối**, không mặc định |
| 1 | Từ chối các loại hành vi tự khai nằm trong danh sách cấm tuyệt đối |
| 2 | Soi văn bản bằng từ điển mẫu, **bất kể** nó khai gì |

Không lớp nào được bỏ vì "lớp kia đã lo". Và **không mức độ tin cậy nào, không
lượng bằng chứng nào mở được** các hành vi bị cấm tuyệt đối — chúng là cam kết
quyền hạn của người chủ trì, không phải vấn đề giọng điệu.

Từ điển mẫu ở lớp 2 **thiên về từ chối một cách có chủ ý**: một lần im lặng sai
là một bất tiện, một cam kết trái phép nhân danh người khác thì không. Hai thứ
đó không so sánh được.

**Giới hạn đã biết của từ điển được ghi thành kiểm thử, không che.** Một lỗ đã
biết nằm trong bộ kiểm thử tốt hơn một lỗ phát hiện trong lần dùng thật.

# 5. Trạng thái ba cấp thử nghiệm — bằng bằng chứng

## 5.1 Cấp A — chạy tổng hợp, không mô hình, không âm thanh

**Đã chứng minh.** Bằng chứng:

- Hoàn tất không lỗi; 12 tình huống, 1 được nói, 11 im lặng.
- **Lặp lại từng byte** qua 3 lần chạy × 4 lệnh.
- **Không ghi gì ra đĩa** — đo bằng cách theo dõi mọi lời gọi mở tệp ở tầng
  tiến trình, đối chiếu trên ảnh chụp gần 9.000 đường dẫn.
- Báo cáo **không chứa** câu đã phát: kiểm bằng chính danh sách khoá của dữ liệu
  đầu ra.
- Báo cáo **tự khai cấp độ bằng dữ liệu**: "không phải tích hợp thật", "không
  phải thử nghiệm trên nền tảng họp".

**Cấp A không chứng minh gì về:** chất lượng mô hình, nhận diện tiếng Việt
trong họp thật, khả năng tổng quát, tên riêng, giọng vùng, nói chồng, độ trễ,
hay khả năng dùng thật. Nó chứng minh **đúng một việc**: lõi quyết định chạy
tất định trên dữ liệu hằng số và không để lại dấu vết trên đĩa.

## 5.2 Cấp B — mô hình cục bộ trên dữ liệu tổng hợp

**Chưa được phép, và theo bằng chứng hiện có thì chưa an toàn.** Hai điều khác
nhau, và cả hai đều đúng.

Hiện có **bốn cổng độc lập cùng từ chối** mọi lần chạy mô hình trên CPU:

| Cổng | Vì sao từ chối |
|---|---|
| Ngưỡng RAM cho mô hình ngôn ngữ | Chưa có ngưỡng được duyệt. Phép đo duy nhất là **một** quan sát |
| Ngưỡng RAM cho nhận diện tiếng nói | **Không có phép đo nào** — kể cả tài liệu thượng nguồn cũng không có số cho đúng mô hình đã chuẩn bị |
| Dấu nội dung mô hình chưa được ghim | Chính sách: dấu nội dung là **bắt buộc**, và chưa ai ghim giá trị đúng |
| Cô lập đường ra ở tầng hệ điều hành | Chưa được thiết lập và khai báo |

Mỗi cổng từ chối vì **sự vắng mặt của một trạng thái đã được duyệt**, không vì
một lỗi — và thông báo của chúng nói rõ điều đó, để người vận hành không đi
giải phóng bộ nhớ cho một vấn đề mà bộ nhớ không giải quyết.

## 5.3 Cấp C — thử nghiệm trên nền tảng họp

**Chưa được phép.** Bốn cổng bằng chứng đều chưa đóng, và **độc lập với các
cổng đó**, ba thành phần chưa tồn tại: bộ nhận âm thanh vào, thành phần nhận
diện tiếng nói, thành phần suy luận. Cộng thêm: **không có nơi phát nào tới
được cuộc họp**.

Hệ quả cần nói rõ: **đóng hết bốn cổng vẫn chưa đủ.** Chúng là điều kiện cần.

# 6. Chiến lược: tới thử nghiệm cục bộ, rồi tới nền tảng họp

Hai lộ trình **độc lập**, không nên gộp thành một mốc:

```
Đường 1 — mô hình cục bộ
  chọn cách lấy số đo bộ nhớ an toàn
    → duyệt hai ngưỡng RAM (riêng biệt)
    → ghim dấu nội dung mô hình
    → thiết lập và khai báo cô lập đường ra
    → một lần chạy có giám sát trên dữ liệu tổng hợp

Đường 2 — nền tảng họp
  chọn cách lấy đồng thuận, cách lưu trữ, câu thông báo lưu trữ
    → rà điều khoản nền tảng
    → khảo sát khả năng nhận âm thanh nhóm
    → quan sát thứ tự xử lý trên một bản dựng cụ thể
    → xây ba thành phần còn thiếu
```

**Đường 1 không mở Đường 2, và ngược lại.** Toàn bộ cấp A nằm ngoài cả hai và
chạy song song được.

Một hiệu chỉnh đáng ghi, vì tài liệu nội bộ từng nói quá: chọn được cách lấy
đồng thuận **không mở khoá điều gì quan sát được** ngay — vì chưa có mã nào gọi
tới cổng đó và chưa có nơi phát nào tồn tại. Nó là **cần** và **đi trước**; nó
**không đủ**.

# 7. Rủi ro

## 7.1 Phần cứng và bộ nhớ

Các số dưới đây là của **một máy tham chiếu duy nhất** — một máy tính xách tay
cá nhân — và **không** phải đặc tả tối thiểu. Chúng chỉ nêu ở đây vì chúng
quyết định một lựa chọn kỹ thuật.

| Đại lượng | Giá trị đo được | Vì sao nó quan trọng |
|---|---|---|
| RAM tổng | ~16 GB | Giới hạn trên tuyệt đối |
| RAM khả dụng lúc đo | ~3,5 GB | **Không phải "RAM trống"**: nó gồm cả vùng nhớ đệm |
| Mức trần một tiến trình được cấp phát | ~2,4 GB | **Thấp hơn cả hai số trên**, và cổng hiện tại **không đọc** đại lượng này |
| Đỉnh bộ nhớ đã quan sát của một lần chạy CPU | ~4,4 GB | **Một** quan sát, lấy mẫu định kỳ, nên là **chặn dưới** |
| Bộ xử lý đồ hoạ | 6 GB, nhưng **bị giới hạn công suất còn một nửa** | Đo được: giới hạn đến từ phần mềm, không phải nhiệt |
| Dung lượng đĩa còn | ~2 GB ở ổ hệ thống | Chặn việc cài công cụ biên dịch |

**Rủi ro cụ thể:** đỉnh bộ nhớ đã quan sát **cao hơn** lượng RAM khả dụng, và
cao hơn **nhiều** so với mức trần cấp phát. Một lần chạy mô hình trên máy này
có thể làm hệ thống hết bộ nhớ.

**Và tầng hệ điều hành giúp ít hơn tưởng.** Ba kết luận từ tài liệu chính thức:

1. Giới hạn bộ nhớ theo nhóm tiến trình tác động lên lượng **cấp phát**, nhưng
   trọng số mô hình được **nạp theo tệp** nên **không bị tính** vào đó. Giới
   hạn ấy chỉ làm phần bộ đệm hỏng **gọn**, không chặn phần lớn dung lượng.
2. Giới hạn cứng theo lượng bộ nhớ thường trú được cưỡng chế bằng cách **đẩy
   trang ra đĩa**, không làm cấp phát thất bại — nó biến "hết bộ nhớ" thành
   "chậm thảm hoạ", và vì thế **phá luôn khả năng đo** độ trễ.
3. Phép đo của chúng tôi yếu hơn mức cần thiết: hệ điều hành **đã duy trì sẵn**
   con số đỉnh chính xác, trong khi công cụ hiện tại lấy mẫu định kỳ. Đã có bản
   mẫu đọc đúng con số đó, **chưa** nối vào quy trình đo.

Một phép đo đối chiếu trực tiếp cho thấy cách lấy mẫu **thiếu khoảng 4%** so
với con số chính xác trên một tiến trình nhỏ — và **lấy mẫu nhanh gấp 30 lần
không giảm được khoảng thiếu đó**. Độ lớn khoảng thiếu cho một lần chạy mô hình
thật **chưa đo được**.

## 7.2 Dữ liệu

| Rủi ro | Trạng thái |
|---|---|
| Nội dung họp rò qua nhật ký hoặc thông báo lỗi | Chặn bằng danh sách cho phép và quy tắc "mô tả hình dạng", có kiểm thử |
| Nội dung họp rò qua một đường gửi dữ liệu của thư viện | Chặn bằng **sự vắng mặt** của thư viện xuất dữ liệu, cộng từ chối khởi động khi có biến môi trường liên quan |
| Tệp thực thi gốc gọi ra mạng | **Phần dư thật.** Nó không nằm dưới cơ chế quan sát của Python, nên bằng chứng "không có sự kiện mạng" **không nói gì** về nó. Đây là lý do có quyết định đòi cô lập ở tầng hệ điều hành |
| Dữ liệu vận hành bị đồng bộ lên dịch vụ lưu trữ đám mây | Chặn bằng cách **chỉ nhận đường dẫn tương đối trong dự án**. **Phần dư:** nếu bản thân thư mục dự án nằm trong một thư mục được đồng bộ thì dữ liệu cũng bị đồng bộ — không cơ chế kiểm tra nào thấy được điều đó |

## 7.3 Nền tảng họp

- **Khả năng nhận âm thanh nhóm bằng danh tính ứng dụng chuẩn: chưa chứng
  minh.** Tài liệu chính thức có đặc tả **gửi** âm thanh, nhưng **không có mục
  nào** cho việc nhận và giải mã, và **không tài liệu hoá** cách ánh xạ một
  luồng âm thanh về đúng người nói. Hai trang tài liệu độc lập cùng cho thấy
  khoảng trống này.
- **Điều khoản nhà phát triển: chưa đọc được từ nguồn gốc.** Cả hai địa chỉ
  chính thức đều trả về lỗi truy cập từ môi trường làm việc hiện tại. Có bản
  tóm tắt từ công cụ tìm kiếm, nhưng tóm tắt **không** dùng để đóng một cổng
  bằng chứng, nên kết luận là **chưa rõ**.
- **Rủi ro vượt quyền** là rủi ro nghiêm trọng nhất của cấp C, và là thứ cổng
  quyền hạn tồn tại để chặn. Nó **chưa** được thử trong một cuộc họp thật.

# 8. Quyết định

## 8.1 Năm quyết định vừa được đưa ra theo uỷ quyền

Chủ dự án uỷ quyền cho tác nhân kỹ thuật quyết năm mục này dựa trên nghiên cứu
và cấu hình máy. Chúng được ghi là **quyết định theo uỷ quyền**, không phải
phát ngôn của chủ dự án — phân biệt đó quan trọng nếu sau này cần xem lại.

| # | Quyết định | Căn cứ |
|---|---|---|
| 1 | Dấu nội dung mô hình là **bắt buộc**, bỏ hẳn cờ tắt kiểm tra | Cờ đó **đã được dùng ở 2 trong 7** lần đo, và bản ghi kết quả vẫn **trông đầy đủ** |
| 2 | Nơi ghi kết quả **cố định**, tương đối trong dự án, không theo dõi bởi quản lý mã | Đường dẫn tương đối chặn **cả** ổ mạng **và** thư mục đồng bộ mà **không cần nhận ra** cái nào |
| 3 | **Từ chối khởi động theo sự hiện diện** của các biến môi trường đổi được nguồn lấy mô hình, và của các biến định tuyến mạng | Đo được: **12 trên 12** biến đó khởi động bình thường trước thay đổi, kể cả giá trị mang nghĩa "ngoại tuyến" và giá trị rỗng |
| 4 | **Không** nhận thư viện tải mô hình vào môi trường chạy | Thiết kế không cần; nhận vào là mười phụ thuộc trực tiếp, trong đó có một thành phần gốc **tự kết nối mạng**, nằm ngoài mọi cơ chế kiểm soát ở tầng Python |
| 5 | **Đòi** cô lập đường ra ở tầng hệ điều hành trước khi chạy tệp thực thi gốc | Tệp thực thi gốc không nằm dưới cơ chế quan sát của Python |

**Hai ghi chú về cách năm quyết định này được đưa ra**, vì phương pháp quan
trọng không kém kết quả:

- **Quyết định 3 được tách thành hai nhóm với hai lý do khác nhau.** Nhóm biến
  đổi nguồn lấy mô hình **tạo ra được** một đường tải về, nên dễ biện minh.
  Nhóm biến định tuyến mạng **không tạo** đường nào — nếu chỉ dừng ở đó thì
  đáng lẽ **không** chặn. Chúng bị chặn vì một cơ chế cụ thể: chúng **đi vòng
  qua** chính phép cô lập mà quyết định 5 đòi. Một biến thứ ba, chỉ đổi chỗ
  vùng nhớ đệm, **cố ý không** bị chặn, và có kiểm thử ghi điều đó để người sau
  không đọc thành sơ sót.
- **Chi phí "ứng dụng không khởi động" được đo, không đoán.** Trên máy tham
  chiếu, **không một biến nào** trong các nhóm đó đang được đặt, nên chi phí
  thực tế hôm nay bằng không. Phần dư: trên một máy có đặt biến định tuyến mạng
  cho việc khác, ứng dụng **sẽ không khởi động**; đường thoát đã ghi trong tài
  liệu mẫu cấu hình là bỏ biến khỏi phiên chạy, **không** sửa cơ chế chặn.

**Năm quyết định này không mở cấp B.** Chúng là điều kiện tiền đề. Hai trong số
chúng thực ra **thêm** một cổng từ chối mới.

## 8.2 Quyết định vẫn chờ chủ dự án

| Mục | Vì sao không thể quyết thay |
|---|---|
| Cách lấy số đo bộ nhớ an toàn — giữ nguyên trạng, chạy có giám sát, hay suy từ kích thước tệp | Mỗi phương án có rủi ro còn lại khác nhau, và một trong đó là **chạy mô hình thật** |
| **Hai** ngưỡng RAM riêng biệt | Hai nền bằng chứng **không so sánh được**: một quan sát so với **không có** quan sát nào |
| Ghim giá trị dấu nội dung mô hình | Ghim một giá trị là **khẳng định rằng một tệp cụ thể là tệp đúng**. Không suy luận nào thay được điều đó |
| Thiết lập cô lập đường ra, rồi khai báo | Là thay đổi cấu hình hệ thống |
| **16** nhãn trong bộ dữ liệu đánh giá | Chúng định nghĩa **hành vi đúng là gì**. Một tác nhân kỹ thuật tự duyệt nhãn của chính mình thì phép đánh giá mất ý nghĩa |
| Cách lấy đồng thuận, phạm vi lưu trữ, thời hạn giữ, câu thông báo | Là cam kết với người tham gia cuộc họp |
| Có công khai tên gọi của chủ dự án trong tài liệu dự án hay không | Là dữ liệu cá nhân của họ |

# 9. Mốc kế tiếp và tiêu chí nghiệm thu

Đơn vị là **lát** — một thay đổi gắn kết, có đủ bốn phép kiểm tra sạch.
**Không có ngày lịch**: thời gian chờ quyết định không phải khối lượng công
việc, và không có dữ kiện để ước lượng nó.

| Mốc | Tiêu chí nghiệm thu | Bằng chứng cần có | Chờ ai |
|---|---|---|---|
| **M1** Chọn cách lấy số đo bộ nhớ | Có một lựa chọn được ghi lại | Một dòng quyết định có căn cứ | Chủ dự án |
| **M2** Phép đo bám đúng tiến trình | Công cụ đo mở một thẻ tiến trình **một lần** và giữ suốt lần chạy | Kiểm thử trên tiến trình con thật, kèm biến đổi mã chứng minh kiểm thử bắt được việc quay lại cách cũ | *(đã làm — bản mẫu)* |
| **M3** Một lần chạy có giám sát | Thu được đỉnh bộ nhớ **chính xác** từ bộ đếm hệ điều hành | Bản ghi kết quả mới; **đổi định dạng bản ghi**, nên cần duyệt riêng | Chủ dự án |
| **M4** Cổng RAM có ngưỡng | Ngưỡng suy từ đỉnh **thật** cộng biên đã duyệt | Kiểm thử từ chối dưới ngưỡng, cho qua trên ngưỡng, kèm biến đổi mã làm kiểm thử sai | Chủ dự án |
| **M5** Rà điều khoản nền tảng | Kết luận **được hỗ trợ / không / chưa rõ** cho từng điều khoản liên quan | Trích dẫn nguyên văn kèm ngày truy cập | Tác nhân, khi truy cập được |

**Việc có thể làm song song mà không vượt ranh giới nào:** rà điều khoản nền
tảng khi truy cập được; tiếp tục đóng các khoảng trống kiểm thử; chuẩn bị M3 ở
dạng chỉ-kiểm-thử, không chạy.

# 10. Kết

MeetAI hôm nay là một **lõi quyết định đã chạy được và đo được**, với các ranh
giới an toàn được cưỡng chế bằng cơ chế thay vì bằng lời hứa, và với một danh
sách rõ ràng những điều **chưa** chứng minh.

Hai câu cần nói thẳng, vì chúng dễ bị đọc trượt:

- **Cấp A chạy được không nói gì về chất lượng mô hình hay nhận diện tiếng Việt
  trong họp thật.**
- **Năm quyết định vừa đưa ra không làm cấp B an toàn hơn.** Chúng làm các điều
  kiện trở nên rõ ràng và được cưỡng chế. Thứ còn chặn vẫn còn chặn.

Đây **không** phải tuyên bố sẵn sàng cho sử dụng thật.
