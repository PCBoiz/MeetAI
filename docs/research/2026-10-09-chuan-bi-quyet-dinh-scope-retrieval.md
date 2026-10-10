# Chuẩn bị quyết định: một câu hỏi trong họp map sang `scope` nào

Lập 2026-10-09 (lượt 20). **Dữ liệu tham khảo + đối chiếu repo để Sơn quyết
định.** Không có quyết định nào trong tài liệu này. Mọi phương án là
**[ĐỀ XUẤT]**; thứ đang chạy trong code là **[GIẢ ĐỊNH]** fail-closed.

**Gate 0-S / 0-P / 0-C / 0-U vẫn mở. S2.2 và S2.3 vẫn `partial/open`.
Consent / persistence / retention vẫn `pending_decision` và lát này không đổi
một flag nào.**

---

## 0. Trước hết: câu hỏi này KHÔNG mới, và tôi đã ghi nó ở lượt 19

Tôi định trình bày đây như một câu hỏi mới. Đối chiếu repo thì **chính tôi đã
ghi nó vào `PROJECT_STATE.md:1728` ở lượt trước**, dưới mục *"Câu hỏi cần Sơn
quyết"*, cùng với `docs/spec.md:182` và ADR 0007 addendum 4. Nên tài liệu này
**không mở một câu hỏi mới** — nó làm rõ câu đã ghi và **gom chung** với Gate
0-U để Sơn trả lời một lượt.

Và quan trọng hơn: **hai trong ba phương án tôi dự định trình bày đã được chốt
hoặc không có khái niệm trong repo.** Chi tiết ở mục 3. Tôi ghi lại cả việc
mình định hỏi sai, vì AGENTS.md nói trước khi hỏi phải tra quyết định cũ, và
đây đúng là thứ việc tra ra.

---

## 1. Ba thứ khác nhau cùng được gọi là "scope" — phải phân biệt trước

Nếu không tách, câu trả lời của Sơn sẽ không dùng được.

| Tên | Là gì | Ở đâu | Trạng thái |
|---|---|---|---|
| **Consent scope** | Bốn thứ tách biệt mà một người đồng ý: nhận/xử lý live media, transcript bền, reply journal, debug raw audio | `policy.ConsentScope`, hồ sơ mục 95 | **[CHỐT]**, đã test |
| **Knowledge-card scope** | Thân tri thức nào được phép trả lời một câu hỏi | `KnowledgeCard.scope`, `retrieval.retrieve_for_question(scope=...)` | **cơ chế [CHỐT], cách chọn [CHỜ BẰNG CHỨNG]** |
| **OAuth scope** | Quyền đọc calendar | System design v0.6.7 | chưa dùng |

**Câu hỏi trong tài liệu này chỉ về loại thứ hai.**

---

## 2. Những gì ĐÃ CHỐT — không hỏi lại

| # | Điều đã chốt | Căn cứ |
|---|---|---|
| 1 | `scope` **bắt buộc**, đến từ **session**, **không bao giờ** từ câu hỏi | ADR 0007 addendum 4, `[CHỐT] về cơ chế` |
| 2 | **Không có đường lexical an toàn nào** từ chữ trong câu hỏi sang scope | cùng trên — nên một bộ chọn scope theo text **đã bị loại** |
| 3 | Trả lời **xuyên scope** là mối nguy mà thiết kế `scope` bắt buộc dựng ra để chặn | cùng trên |
| 4 | `witnesses` **không bao giờ bị cắt**; `candidates ⊆ witnesses`; ranking chỉ tác động `candidates` | ADR 0007 addendum 4, đo được |
| 5 | Ranking chấm trên `evidential_text`, không trên claim thô | lượt 19, đo được |
| 6 | `max_sensitivity` **bắt buộc**; card mặc định `PRIVATE`; một card `PRIVATE` **không ra cuộc họp** (case `D11`) | lượt 19 |
| 7 | **Chỉ retrieval** card riêng khi câu hỏi cần lập trường/thông tin riêng của Sơn. **Không xây RAG cho vô hạn tình huống** | hồ sơ v1.0 dòng 110 |
| 8 | **metadata + exact/lexical**; embeddings **chỉ khi** benchmark trên bộ eval của Sơn chứng minh cải thiện | hồ sơ v1.0 dòng 138, spec `K-8` `absent` cố ý |
| 9 | Không ingest cả account/repo/mailbox/calendar; không gửi cả lịch vào LLM | hồ sơ v1.0, spec `K-2` đã test |
| 10 | Không học từ transcript; candidate/pending **không bao giờ** retrieve như fact đã duyệt | spec `K-7`, `P-8`, đã test |
| 11 | **Không có phân quyền giữa người dùng.** Một người, một máy | `docs/intent.md:21` |
| 12 | Host **không** ghi đè opt-out của participant | hồ sơ v1.0 dòng 216 |
| 13 | Ba thân tri thức tách biệt: năng lực ngôn ngữ ở **model**, tham chiếu gần ở **meeting context**, thông tin riêng về Sơn ở **knowledge card** | System design v0.6.7 — **đây đã là câu trả lời cho "thân nào trả lời cái gì"** |

---

## 3. Ba phương án tôi dự định trình bày, và kết quả tra lại

### (a) "Mặc định chỉ scope cuộc họp hiện tại"

**Nửa cơ chế đã chốt; nửa còn lại dùng một từ repo không định nghĩa.**

Phần *"scope đến từ session, không từ câu hỏi"* là mục 1 trong bảng trên — **đã
chốt**, không phải phương án. Phần còn lại là chỗ mơ hồ: **repo không định nghĩa
"scope của cuộc họp"**. Nó biết `scope` là một **chuỗi do caller truyền**, và
câu chưa trả lời là *session lấy chuỗi đó từ đâu*.

Nên (a) chỉ là một phương án **nếu** nó có nghĩa là *"suy scope từ danh tính
cuộc họp"* — và khi đó nó cần một cơ chế chưa tồn tại. Nếu nó có nghĩa là
*"operator chọn một scope mỗi phiên và retrieval không ra khỏi đó"* thì **đã
chốt rồi**.

### (b) "Thêm scope dự án/global khi được gắn và cho phép rõ"

**Không có khái niệm nào đỡ phương án này, và nó xin nới một thứ đã cố ý đóng.**

- **"global scope" không xuất hiện ở đâu trong repo.** Chỗ gần nhất là một ghi
  chú chiến lược dài hạn, mà `docs/intent.md:24` nói rõ **không phải bản vẽ cho
  ứng dụng này**.
- **"cho phép rõ" không có chỗ tham chiếu.** Không có mô hình phân quyền —
  `docs/intent.md:21`: *"không có phân quyền giữa người dùng"*. Hỏi theo cách
  này là nhờ Sơn **phát minh** một mô hình quyền.
- **Cơ chế hiện tại có đúng một giá trị `scope`, không phải một tập.**
- Và **trả lời xuyên scope chính là mối nguy** mục 3 bảng trên ghi là đã đóng.

Nên nếu vẫn muốn hỏi, phải hỏi thẳng: ***"có nới một thứ đã cố ý đóng không"***,
và định nghĩa "global" với "được cho phép" trước. Tôi **không** khuyến nghị hỏi
ở lát này: không có nhu cầu nào trong repo cần tới nó.

### (c) "`PRIVATE` không bao giờ tự thành nội dung `GROUP`"

**Đã chốt về nguyên tắc, có test ghim. Không phải phương án.**

Mục 6 bảng trên: `max_sensitivity` bắt buộc, card mặc định `PRIVATE`, và case
`D11` chứng minh một card `PRIVATE` không ra họp.

Thứ **thực sự còn hở** là **độ sâu enforcement**, và nó đã được ghi thành phần
dư từ lượt 19: `Sensitivity` xuất hiện **0 lần** trong `answerability.py`,
`authority.py`, `boundary.py`. Nó chỉ được enforce ở `KnowledgeStore.retrieve`.
Một caller thật truyền `PRIVATE` thì **không gì bắt**.

Vậy câu đúng không phải *"nguyên tắc này có đúng không"* mà là *"có dành một lát
để enforce nó ở tầng dưới không"* — và đó là một câu về **thứ tự ưu tiên**, không
phải về nguyên tắc.

---

## 4. Câu hỏi thật sự còn hở, thu hẹp lại

Sau khi bỏ những gì đã chốt, còn **một** câu, và nó có một câu con cụ thể hơn
nhiều:

> **Session lấy `scope` từ đâu?**
>
> Câu con, cái này mới dùng được: **một cuộc họp có được gắn với một dự án
> không, và nếu có thì gắn bằng gì** — event trên Calendar, channel Discord, hay
> operator chọn tay trước mỗi phiên?

**Repo không có gì cho câu này.** Không `project_id`, không "cuộc họp này thuộc
dự án nào", không quy tắc từ danh sách người tham gia sang scope. Và tên người
tham gia **cố ý giữ ngoài repo** (`docs/spec.md:148`), nên suy scope từ người
trong họp cũng không có đường.

**Ba hình dạng khả dĩ, trình bày để Sơn cân nhắc, không phải để tôi chọn:**

| | Scope đến từ | Được gì | Mất gì |
|---|---|---|---|
| **S1** | Operator **chọn tay** một scope mỗi phiên | Không cần Calendar, không suy diễn, fail-closed rõ. Chạy được ngay — **đây là [GIẢ ĐỊNH] đang chạy** | Một bước tay mỗi cuộc họp. Chọn sai thì trả lời bằng tri thức sai dự án |
| **S2** | **Calendar event** (trường nào thì Sơn chốt) | Tự động, và hồ sơ đã chốt Calendar là nguồn lịch | Cần connector thật (`M-7`, **là tác động ra ngoài cần Sơn xác nhận**). Event không gắn dự án thì rơi về đâu? |
| **S3** | **Channel/guild Discord** | Có sẵn khi đã có adapter | **Chặn bởi gate 0-S/0-P/0-C**, nên không khảo sát được bây giờ |

**Chung cho cả ba:** một cuộc họp **không** xác định được scope thì rơi về đâu?
Fail-closed nghĩa là *"không retrieval card nào"* — MeetAI vẫn nói được bằng
năng lực ngôn ngữ của model và meeting context (mục 13 bảng trên), chỉ không dẫn
card riêng của Sơn. **[ĐỀ XUẤT]** đó là mặc định đúng, nhưng tôi không tự chốt.

---

## 5. Gom với Gate 0-U — bốn mục, một lượt trả lời

Thứ tự theo mức chặn, chứ không theo mức thú vị.

| # | Mục | Chặn gì | Ghi ở đâu |
|---|---|---|---|
| **1** | **`consent_mode`** — chế độ nào? (gồm cả A1 circuit-breaker vs A3 admission control) | `require_media_processing_allowed()` kiểm đúng cái này, nên nó chặn **mọi** đường media ở mức code | `PROJECT_STATE.md:212`, §4B B1/B2 |
| **2** | **Persistence** — có lưu nội dung họp không, và nếu có thì **cái gì**: transcript, card, hay chỉ metadata? | 4 switch mặc định OFF, 2 rào tự từ chối khi đặt True | §4B B4/B5 |
| **3** | **Retention wording** — giữ bao lâu, và câu nói với người trong họp là gì? | §4B B6/B7 | `PROJECT_STATE.md:197-198` |
| **4** | **Session lấy `scope` từ đâu** (mục 4 ở trên) — và cuộc họp có gắn dự án không | Chặn việc nối retrieval vào một caller thật. **Không chặn** dry-run cấp 2, đang chạy được | `PROJECT_STATE.md:1728`, `spec.md:182` |

**Mục 1–3 là việc *chọn*, không phải việc *xây*:** FSM và cả hai chiến lược late
join **đã xây xong** sau một interface, mặc định đóng — và lượt 20 vừa thêm
**90 test hành vi + 29 mutation** chứng minh chúng fail-closed.

**Mục 4 cần một cơ chế mới** (nhỏ nếu chọn S1), nên nó khác loại với 1–3.

**Không mục nào chặn phần việc độc lập.** Lát này làm xong việc kiểm chứng gate
mà không cần câu trả lời nào.

---

## 6. Những thứ cũng đang chờ Sơn, liệt kê để không bỏ sót

Không phải để trả lời bây giờ — để Sơn biết danh sách đầy đủ.

- **§4B B1–B10** (`PROJECT_STATE.md:192-201`), cả mười mục vẫn mở.
- **MeetAI được gọi bằng gì** — alias registry **rỗng cố ý** tới khi Sơn chốt
  (ADR 0004).
- **Consent TTL** — `grant_ttl_seconds` mặc định `None`, **[ĐỀ XUẤT]**, là quyết
  định của Sơn.
- **Calendar OAuth app** (`M-7`) — **tác động ra ngoài, cần Sơn xác nhận trước**.
- **Có chạy lại S2.3 để bắt một failure cùng `failure_evidence` không** — hỏi ở
  lượt 17, và lượt 18–19 **không** đề xuất chạy. Vẫn mở, và lát này cũng không
  đề xuất.
- **Sensitivity theo field hay theo card** — hồ sơ nói *field-level*, code làm
  *card-level*. Chưa được hoà giải ở đâu.
- **Chỗ đặt phép kiểm scope** — v0.6.7 nói lọc **trước** search; ghi chú chiến
  lược nói kiểm **sau** model; code lọc trong `KnowledgeStore.retrieve` và
  **không** kiểm sau model. Ba tài liệu, ba chỗ.

---

## 7. Lát này KHÔNG cài gì phụ thuộc vào câu trả lời

Theo đúng chỉ dẫn. Cụ thể là **không** thêm:

- bất kỳ cơ chế suy `scope` từ câu hỏi, từ người tham gia, hay từ Calendar;
- bất kỳ khái niệm multi-scope, scope "global", hay mô hình quyền;
- bất kỳ phép kiểm `scope`/`Sensitivity` ở tầng dưới retrieval — **vì chỗ đặt nó
  phụ thuộc mục 4**, và đặt sai chỗ sẽ phải gỡ.

Phần đã làm xong và **không** phụ thuộc câu trả lời: `scope` bắt buộc,
`max_sensitivity` bắt buộc, `witnesses` không bị cắt, và 90 test hành vi cho ba
gate an toàn.
