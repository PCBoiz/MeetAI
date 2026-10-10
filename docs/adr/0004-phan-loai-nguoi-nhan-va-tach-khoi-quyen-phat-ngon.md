# ADR 0004 — Phân loại người nhận, và tách nó khỏi quyền phát ngôn

- **Trạng thái:** [CHỐT] cho bốn quyết định ngữ nghĩa; [ĐỀ XUẤT] cho chi tiết triển khai
- **Ngày:** 2026-10-07 (lượt 7)
- **Lát:** S1.7
- **Liên quan:** [ADR 0002](0002-fail-closed-core-va-chong-ro-ri.md), [spec.md](../spec.md) P-11 và mục 9

## Bối cảnh

Hồ sơ bàn giao yêu cầu phân biệt bốn lớp người nhận — được gọi trực tiếp, nhắc
ngôi ba, alias trùng từ, không rõ — và nói thẳng rằng **alias match một mình
không đủ để chen ngang** (handoff:108). Phần thứ hai là lý do đây là một module
riêng chứ không phải một nhánh trong `authority.py`: gate trả lời "câu này có
được nói không", và gộp hai câu hỏi lại sẽ cho một cái tên trong transcript
quyền nới rộng những gì MeetAI được làm.

Hồ sơ không trả lời năm tình huống ranh giới. Bốn trong số đó được chủ dự án
quyết định trực tiếp ở lượt này; cái thứ năm trả lời được từ `AGENTS.md` nên
không hỏi.

## Quyết định

### 1. Bốn khâu tách rời, và sự tách rời là có tải trọng

| Khâu | Trả lời câu hỏi | Ở đâu |
|---|---|---|
| `AddressClass` | ai đang được nói tới | `addressing.py` |
| `ResponseIntent` | có ai hỏi gì không | `addressing.py` |
| Authority | câu này có được nói không | `authority.py` |
| Confidence | **chưa calibrate**, không dùng như ngưỡng đã đo | — |

### 2. [CHỐT] Vocative không kèm yêu cầu: nhận diện được, không trả lời

Nguyên văn quyết định: *"Tên gọi rõ như 'MeetAI ơi' có thể đánh dấu addressee
là DIRECTED_TO_ME, nhưng chưa phát câu trả lời nếu chưa có yêu cầu/câu hỏi. Chỉ
giữ lượt thoại làm context; không chen ngang."*

Đây là lý do `permits_reply` là một **phép hội**, không phải một lớp:

```python
return bool(self.address_class) and bool(self.response_intent)
```

Gộp hai khâu sẽ buộc chọn giữa (a) mất thông tin người nhận và (b) chen ngang
vào một lời chào. `to_address_context()` do đó ghi `permits_reply` vào
`directly_addressed`, **không** ghi lớp address — vì `permits_speaking` của gate
chính là field đó, nên ghi lớp vào sẽ làm một lời chào đủ để chen ngang. Có test
khẳng định đúng điểm này.

### 3. [CHỐT] Đại từ chung → `UNCLEAR`

*"Đại từ chung như 'bạn/anh/chị' không đủ để nhận diện MeetAI nếu thiếu alias và
ngữ cảnh lượt thoại đáng tin cậy."* Trong phòng họp nhiều người, "anh ơi" gần
như luôn nhắm vào một người.

### 4. [CHỐT] Câu hỏi cho cả nhóm → `NOT_DIRECTED_TO_ME`

*"'Mọi người nghĩ sao?' hoặc 'ai làm phần này?' hướng tới nhóm, không phải
MeetAI."*

Đây là lý do có **lớp thứ năm** ngoài bốn lớp của hồ sơ. Gộp vào `UNCLEAR` sẽ
làm phình UNCLEAR rate bằng những case thực ra **nhận diện được**, mà UNCLEAR
rate chính là con số lát này báo. "Mọi người" là bằng chứng **tích cực** rằng
người nhận là tập thể, không phải sự thiếu bằng chứng.

### 5. [CHỐT] Tên người được gọi → `UNCLEAR`, không bao giờ `DIRECT`

*"Nếu Sơn cũng đang trong cuộc họp và tên 'Sơn' được gọi, classifier không được
tự kết luận là đang gọi MeetAI. Chỉ dùng alias riêng của MeetAI nếu sau này tôi
chốt cách đặt tên đó."*

Quyết định này cộng với quyết định (2) buộc ra một phân biệt mà thiết kế ban đầu
không có: **alias riêng của MeetAI** được tới `DIRECT`, **tên người** thì không.
Classifier không phân biệt được hai tình huống từ text, nên registry phải mang
phân biệt đó — `AliasKind.DEDICATED` / `HUMAN_NAME` / `AMBIGUOUS_WORD`, và chỉ
`DEDICATED` có `can_reach_direct`.

Hệ quả: **registry mặc định rỗng và không nhận ra ai cả.** Chủ dự án chưa chốt
MeetAI được gọi bằng gì, nên rỗng là trạng thái trung thực. Alias thật cấu hình
cục bộ, không vào repo.

### 6. [CHỐT từ AGENTS.md] Không chắc chắn → `UNCLEAR`

Không hỏi lại vì `AGENTS.md` đã chốt fail-closed. Transcript thiếu, nói chồng,
speaker mapping không tin cậy đều ra `UNCLEAR`. `UNCLEAR` là **mặc định**, không
phải một nhánh — một câu classifier không hiểu không thể tới được reply.

### 7. [ĐỀ XUẤT] Turn context là bằng chứng, không phải quyền

`addressed_to_me_by_turn` chỉ đặt được khi `speaker_mapping_reliable`. Đặt mà
không có nó thì **bị từ chối**, không bị bỏ qua: một input bị âm thầm bỏ qua
trông giống một tính năng đang hoạt động. Gate 0-C còn mở nên đường code này hôm
nay chỉ được test, chưa được dùng. Một người nhận cạnh tranh (tên người trong
câu) **thắng** turn context.

## Những gì đã đo, không phải suy ra

Ba lớp lỗi tìm ra bằng probe trước khi có test, mỗi cái sửa theo lớp:

1. **Yêu cầu khác mệnh đề vẫn triệu hồi được.** `MeetAI thì để sau, giờ mọi
   người tóm tắt giúp mình` **tới được reply** — một câu hoãn MeetAI tường minh
   rồi nhờ cả phòng. Ba false activation đo được. Sửa: đường alias-tới-DIRECT
   giới hạn trong **cùng mệnh đề**.
2. **Động từ yêu cầu không phải là một yêu cầu.** Tiếng Việt không biến hình
   theo thức, nên `Tuấn đang kiểm tra lại số liệu` (báo cáo) và `Kiểm tra lại số
   liệu` (nhờ) chỉ khác vị trí và dấu hiệu. Coi động từ là đủ khiến **mọi** báo
   cáo tiến độ ngôi ba trông như chỉ thị. Sửa: yêu cầu chỉ được nhận ở đầu mệnh
   đề, sau dấu hiệu lịch sự, hoặc có benefactive (`giúp`/`giùm`).
3. **`cùng` và `cũng` fold giống nhau.** `MeetAI cùng rà lại` (hành động chung)
   bị đọc thành câu kể về MeetAI. Sửa: bỏ `cung` khỏi tập dấu hiệu vị ngữ; `sẽ`,
   `đã`, `đang`, `vừa` mang nghĩa đó mà không nhập nhằng. Tương tự bỏ `với` khỏi
   tập giới từ ngôi ba — nó là liên từ cũng thường như giới từ.

**Một phát hiện về chính corpus.** Bản đầu ghi `Lan` và `Tuấn` là tên "không
trùng từ nào". Harness bác bỏ ngay: `để tuần sau xử lý` khớp tên Tuấn, vì `tuần`
và `Tuấn` cùng fold thành `tuan`. Đo lại thì **gần như mọi tên riêng tiếng Việt
đều fold trùng một từ thường** — dấu mang phần lớn độ tương phản giữa các âm
tiết, nên bỏ dấu đi là tên rơi vào từ vựng. Tên **không** trùng là trường hợp
hiếm, không phải thường. Đó là lý do **đo được** cho việc đòi một alias riêng
trước khi coi bất cứ thứ gì là lời gọi.

## Fold collision: đóng ở đâu, và cố ý không đóng ở đâu

`spec.md` mục 9 ghi `Minh`/`mình` với điều kiện đóng là "cần truyền một tập
alias đã biết vào detection". `AliasRegistry` là tập đó.

**Đóng cho `addressing.py`, bằng cấu trúc chứ không bằng pattern.** Không pattern
nào được làm thông minh hơn: tên người hoặc tên trùng từ **không bao giờ** tới
được `DIRECTED_TO_ME` ở bất kỳ framing nào, nên không collision nào trong tên
người gây được false activation — kể cả tên chưa gặp. Một bản sửa pattern không
có tính chất đó.

**Cố ý không đóng trong `authority.py`.** Ở đó cùng cái fold làm `Minh sẽ làm
xong` đọc thành cam kết ngôi thứ nhất, tức **over-refusal** — hướng rẻ, một lần
im lặng. Truyền kết luận "đây là người thứ ba" từ classifier vào gate sẽ mua lại
chỗ đó bằng cách cho text tự dàn khung ngôi ba để thoát refusal — hướng đắt. Có
test ghi rằng đây là **lựa chọn**, không phải sơ suất.

**Giá đã đo của việc đóng.** Đăng ký một tên trùng với từ chức năng tần số cao
làm giảm chất lượng các case khác: với `Minh` trong registry, `giúp mình nhé`
parse thành *lời gọi một người tên Minh*, vì particle vocative đứng ngay sau
`minh`. Không mất an toàn — reply vẫn bị chặn — nhưng lớp address sai. Đó là lý
do registry do chủ dự án cấu hình cho cuộc họp của mình, mặc định rỗng, không
ship tên nào.

## Hệ quả

- `AddressContext` không đổi shape, nên `authority.py` không phải sửa gì.
- Registry rỗng ⇒ `DIRECTED_TO_ME` **không tới được** qua đường alias. Đo trên
  toàn corpus cộng các dạng triệu hồi: 0 leak.
- Đường duy nhất tới `DIRECTED_TO_ME` mà không cần alias là turn context, và nó
  cần `speaker_mapping_reliable` — tức Gate 0-C. Test phát biểu đúng tập ngoại
  lệ đó chứ không nới lỏng khẳng định.

## Giới hạn

- **Corpus synthetic.** Kiểm tra logic, bắt lớp lỗi. **Không** phải bằng chứng
  classifier chạy tốt trên tiếng Việt thực tế, và **không** calibrate được ngưỡng
  nào. `MINIMUM_CONFIDENCE` vẫn là placeholder; assessment cố ý **không** có
  field confidence, để không ai so sánh nó với một ngưỡng chưa đo.
- `M e e t A I ơi` (viết rời) và `MeetAIơi` (dính liền) không khớp — thất bại ở
  word boundary. Hướng rẻ. Chưa đóng vì chưa có bằng chứng ASR thật sinh ra dạng
  nào.
- `response_intent` tính trên toàn phát ngôn trong khi đường alias-tới-DIRECT đã
  giới hạn trong cùng mệnh đề, nên `MeetAI ơi, bạn Khuê gửi link giúp mình` vẫn
  ra reply. Chấp nhận có ghi: vocative là bằng chứng mạnh về người nhận.
- Classifier **không** thay `authority`, **không** khẳng định consent, **không**
  mở live Discord. Gate 0-S/0-P/0-C/0-U vẫn OPEN.
