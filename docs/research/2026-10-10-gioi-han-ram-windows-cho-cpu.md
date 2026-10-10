---
title: "Giới hạn RAM trên Windows cho phép chạy CPU — LLM và ASR"
owner: "Sơn"
date: "2026-10-10"
revision: "af92c6e"
last_updated: "2026-10-10 (lượt 34)"
status: "nghiên cứu; không chạy model; chờ Sơn chọn phương án"
access_date: "2026-10-10"
---

# Giới hạn RAM trên Windows cho phép chạy CPU

**Revision đo:** `af92c6e`, 85 commit, tree sạch (`git status --porcelain` exit 0,
không output). **Không chạy model, không benchmark, không allocator stress test,
không gọi binary ASR/LLM, không cài package, không tải artifact, không GPU.**

Mọi link truy cập **2026-10-10**.

## 1. Kết luận một dòng

**Ba đại lượng khác nhau đang bị gọi chung là "RAM", và mỗi cơ chế giới hạn tác
động lên một đại lượng khác nhau.** Con số `4438 MiB` của ta là **Working Set**;
cổng của ta so với **available physical**; còn cơ chế giới hạn mạnh nhất của
Windows (Job object) tác động lên **commit**. Đặt `4438` làm commit limit là **áp
một đại lượng vào một đại lượng khác** — và vì weights GGUF là **file-backed**,
commit limit **không chặn phần lớn footprint**.

## 2. Ba đại lượng, trích nguyên văn

| Đại lượng | Định nghĩa chính thức | Ai dùng nó |
|---|---|---|
| **Working Set** | *"the set of memory pages in the virtual address space of the process that are currently resident in physical memory"* | **phép đo 4438 của ta** (`ram_peak_working_set_mib`) |
| **Commit Charge** | *"The Commit Charge value in bytes for this process. Commit Charge is the total amount of memory that the memory manager has committed for a running process."* | **Job object limit** |
| **Available physical** | *"The amount of physical memory currently available… This is the amount of physical memory that can be immediately reused without having to write its contents to disk first. It is the **sum of the size of the standby, free, and zero lists**."* | **cổng `require_*_preflight` của ta** |

Nguồn: [PROCESS_MEMORY_COUNTERS], [MEMORYSTATUSEX], [SetProcessWorkingSetSizeEx].

**[ĐÃ ĐO — hệ quả cho cổng của ta]** `read_available_ram_mib()` trả `ullAvailPhys`,
tức **standby + free + zero**. Standby list **bao gồm trang cache**, nên con số
cổng đang so **không phải "RAM trống"** — nó bao gồm cả cache có thể thu hồi, kể cả
trang GGUF còn cache từ một lần chạy trước. Đó là lý do hợp lệ (standby *dùng lại
được ngay*), nhưng nó giải thích vì sao số đó **dao động mạnh** (đo được **3966 →
2897 MiB** trong một lượt).

Và `ullAvailPageFile` — *"The maximum amount of memory the current process can
commit"* — là **đại lượng thứ ba**, thứ mà một commit limit tác động lên. Cổng của
ta **không đọc nó**.

## 3. Mỗi cơ chế chặn được gì, KHÔNG chặn được gì

### 3a. Job object, commit limit — **[ĐÃ ĐO từ tài liệu]**

> `ProcessMemoryLimit`: *"this member specifies the limit for the **virtual memory
> that can be committed** by a process"*
> `JOB_OBJECT_LIMIT_PROCESS_MEMORY`: *"causes all processes associated with the job
> to limit their committed memory, and when a process attempts to commit memory
> that would exceed the per-process limit, **it fails**"*

| | |
|---|---|
| **Chặn được** | KV cache, heap, mọi `VirtualAlloc` — và **fail sạch, quy được trách nhiệm** |
| **KHÔNG chặn** | **Weights GGUF đọc qua mmap** |

**Vì sao không chặn weights**, trích `CreateFileMapping` về `SEC_COMMIT`:

> *"If the file mapping object is backed by the operating system paging file (the
> hfile parameter is INVALID_HANDLE_VALUE), specifies that when a view of the file
> is mapped into a process address space, the entire range of pages is committed
> rather than reserved. … **This attribute has no effect for file mapping objects
> that are backed by executable image files or data files** (the hfile parameter is
> a handle to a file)."*

Một GGUF là **data file**. Nên ngữ nghĩa commit **không áp dụng** cho view của nó.

**[SUY LUẬN — không phải phép đo]** Với Qwen3-4B Q4_K_M (**2382 MiB** trên đĩa),
phần weights là đa số của 4438 MiB Working Set. Một commit limit sẽ bỏ qua phần đó
và chỉ chặn phần còn lại. Tôi **không** đo được tỷ lệ chính xác mà không chạy.

### 3b. Hard working-set maximum — **[ĐÃ ĐO từ tài liệu]**

`SetProcessWorkingSetSizeEx` + `QUOTA_LIMITS_HARDWS_MAX_ENABLE`:
*"The working set will not exceed the maximum working set limit."*

Đây là cơ chế duy nhất tác động lên **đúng đại lượng ta đã đo**. Nhưng:

> *"The virtual memory manager attempts to keep no more than this much memory
> resident in the process whenever the process is active **and available memory is
> low**"*

**Cưỡng chế bằng trim/paging, không phải làm allocation fail.** Nên nó **không
ngăn** hết RAM — nó **biến OOM thành thrashing đĩa**. Tài liệu còn cảnh báo thẳng:

> *"When you increase the working set size of an application, you are taking away
> physical memory from the rest of the system. This can degrade the performance of
> other applications and the system as a whole. It can also lead to failures of
> operations that require physical memory to be present"*

Thêm hai ràng buộc: max phải *"less than the system-wide maximum (number of
available pages minus 512 pages)"*, và *"The operating system allocates working set
sizes on a first-come, first-served basis"*.

**[ĐỀ XUẤT] Không dùng cơ chế này làm cổng an toàn.** Nó đo đúng thứ nhưng cưỡng
chế sai cách: một lần chạy bị trim sẽ **vẫn chạy**, chậm hơn nhiều, và số latency
thu được sẽ **vô nghĩa** — tức nó phá luôn khả năng đo.

### 3c. Notification-only, **không cưỡng chế** — **[ĐÃ ĐO từ tài liệu]**

> *"To register for notifications that a job has exceeded its peak memory limit
> **while allowing processes to continue to commit memory**, use the
> SetInformationJobObject function with the JobObjectNotificationLimitInformation
> information class."*

Đây **không phải** một giới hạn. Nó là một **phép đo** — và nó dẫn tới phát hiện
quan trọng nhất của lát này.

## 4. Phát hiện đáng giá nhất: OS đã duy trì peak thật, ta đang lấy mẫu

**[ĐÃ ĐO từ tài liệu]** Windows duy trì peak **liên tục**, không cần ai lấy mẫu:

| Counter | Trích nguyên văn |
|---|---|
| `PeakWorkingSetSize` | *"The peak working set size, in bytes."* |
| `PeakPagefileUsage` | *"The peak value in bytes of the Commit Charge **during the lifetime of this process**."* |
| `PeakProcessMemoryUsed` (job) | *"The peak memory used by any process **ever** associated with the job."* |
| | Remarks: *"The system tracks the value of PeakProcessMemoryUsed and PeakJobMemoryUsed **constantly**."* |

**[ĐÃ ĐO trong repo]** Còn harness của ta làm thế này: `ProcessRamSampler` chạy một
thread nền, mỗi **300 ms** gọi `peak_working_set_mib()`, mà hàm đó spawn **`tasklist`**
và đọc cột Mem Usage **hiện tại**, rồi lấy `max()` các mẫu.

Nên:

- **4438 MiB là chặn dưới do lấy mẫu — một cách không cần thiết.** Đại lượng ta
  muốn (`PeakWorkingSetSize`) là thứ OS **đã** theo dõi chính xác.
- Tên hàm `peak_working_set_mib` **nói quá**: nó trả **giá trị hiện tại**, và
  docstring *"Peak working set of any running process with this image name"* lẫn
  "max giữa các process" với "peak theo thời gian".

**[ĐỀ XUẤT]** Đây là một cải thiện **chất lượng phép đo**, không phải một lựa chọn
chính sách — nhưng nó **đổi nội dung artifact**, nên nó thuộc protocol ở mục 6 chứ
không phải thứ tôi tự sửa trong lát này. Và nó **không** tạo thêm điểm dữ liệu: nó
chỉ làm lần đo *tiếp theo* chính xác.

## 4b. Prototype đọc counter bằng Windows API — đã kiểm chứng, CHƯA tích hợp

**Lượt 32.** Mục 4 kết luận rằng ta đang **lấy mẫu một đại lượng mà OS đã theo dõi
chính xác**. Lát này viết phần dụng cụ cho kết luận đó — `benchmarks/winmem.py`,
`ctypes`, **không dependency mới** — và **dừng ở đó**: không nối vào `measure.py`,
không harness nào import, không trường artifact nào lấy từ nó, không ngưỡng nào đổi.
Test: `tests/test_winmem.py` (**40 ca**), cộng **3 ca có sẵn** tự động phủ module mới
(`test_llm_boundary.py` parametrise theo `benchmarks/*.py`: không import được mạng,
không `eval`/`exec`, không nêu tên server binary) — tức hàng rào cấu trúc cũ **tự
bao** file mới mà không cần sửa gì, đúng ý đồ của thiết kế allowlist.

### Ba khiếm khuyết nó trả lời, mỗi cái đo trong repo chứ không suy đoán

| | `measure.peak_working_set_mib` hiện tại | Prototype |
|---|---|---|
| Nguồn số | spawn `tasklist` mỗi 300 ms, lấy `max()` các mẫu **hiện tại** | `PeakWorkingSetSize` — OS duy trì liên tục |
| Xác định đối tượng | `IMAGENAME eq llama-cli.exe`, giữ **match lớn nhất** | **handle**, mở một lần từ PID |
| Đại lượng | chỉ working set | working set **và** commit **và** page fault |
| Chi phí khi đo | một process `tasklist` mỗi 300 ms | không spawn gì |

Khiếm khuyết **thứ hai là nghiêm trọng nhất và chưa từng được ghi**: lọc theo tên
ảnh rồi `max()` nghĩa là một process **thứ hai** cùng tên — benchmark khác, tiến
trình sót, công cụ không liên quan — **đổi câu trả lời trong im lặng**, và số đo
**trông đúng** vẫn có thể mô tả sai process. Tài liệu cho lý do nền: handle *"are
valid until closed, **even after** the process or thread they represent has been
terminated"*, còn PID *"is valid from the time the process is created **until the
process has been terminated**"*. Nên handle là identifier duy nhất bám được **một**
process suốt một lần chạy. Prototype vì thế nhận **handle**, không bao giờ nhận tên.

### Đã kiểm chứng trên API thật — **[ĐÃ ĐO]**

Đối tượng đo là **chính tiến trình Python đang chạy test**. Không spawn child,
không cấp phát lớn, không tạo artifact.

| Quan sát | Kết quả |
|---|---|
| `sizeof(PROCESS_MEMORY_COUNTERS_EX)` | **80** = `2*sizeof(DWORD) + 9*sizeof(SIZE_T)` |
| Pseudo-handle | `0xffffffffffffffff` |
| Đọc qua pseudo-handle | working set, peak, commit, peak commit, page fault — đều hợp lệ |
| Đọc qua handle thật từ `os.getpid()` | khớp |
| PID **4** (System) | `access-denied` — đúng tài liệu *"ERROR_ACCESS_DENIED"* |
| PID **0** (Idle) | `no-such-process` — đúng tài liệu *"ERROR_INVALID_PARAMETER"* |

Hai dòng cuối là chỗ đáng giá: **kernel thật** trả đúng hai mã lỗi mà tài liệu nói,
nên mapping lỗi trong test mock không chỉ là tự đồng ý với chính nó.

### Sáu mutation, cả sáu đỏ — **[ĐÃ ĐO]**

Một control là test, chỉ khi xóa cơ chế đi thì test fail:

| Mutation | Kết quả |
|---|---|
| `c_size_t` → `c_ulong` (struct lệch kích thước) | đỏ |
| Bỏ phép kiểm hợp lý (zero thành một phép đo) | đỏ |
| Gộp `no-such-process` vào `access-denied` | đỏ |
| `ceil` → `floor` (báo thiếu một yêu cầu) | đỏ |
| Xin `PROCESS_QUERY_INFORMATION` thay vì limited | đỏ **sau khi sửa** |
| Pseudo-handle lệch một bit | đỏ **sau khi sửa** |

**Hai mutation ban đầu XANH, và cả hai là lỗ trong *test*, không phải trong code** —
cùng một lớp lỗi, tìm ra nhờ mutation chứ không nhờ đọc lại:

1. Assertion so `api.opened` với **chính hằng số của module**, nên đổi hằng số thì
   test đổi theo. Nay ghim **literal `0x1000`** từ tài liệu và khẳng định `!= 0x0400`.
2. Assertion cho pseudo-handle **lặp lại đúng biểu thức của code**
   (`2 ** (8 * sizeof(c_void_p)) - 1`), nên nó đúng với bất kỳ biểu thức nào code
   trở thành. Nay suy ra **độc lập từ tài liệu**: pseudo-handle là `(HANDLE)-1`, tức
   **mọi bit bật**, viết bằng `int.from_bytes(b"\xff" * sizeof, "little")`.

Đúng cái bẫy `AGENTS.md` bước 3 gọi là tín dụng coverage giả: *một test chỉ lặp lại
giá trị mặc định sẽ pass với cả một stub hardcode*. Bài học rút ra: **so với tài
liệu, không so với implementation** — và chỉ mutation phát hiện được khác biệt đó.

### Vì sao fail-closed có hình dạng này

`MemoryProbeUnavailable` mang một **mã trong tập đóng** (6 mã) và **raise**, không
bao giờ trả `0`, `-1` hay `"?"`. Lý do cụ thể, không phải nguyên tắc chung: repo này
**đã** có đúng lỗi đó một lần, khi VRAM không đọc được thành chuỗi `"?"` rồi tới
`int()`. Một sentinel vừa khít một field `int` sẽ được **lấy trung bình, so sánh và
ghi vào artifact** như thể đã quan sát.

Phép kiểm hợp lý đáng nói riêng: `GetProcessMemoryInfo` **có thể trả nonzero** trong
khi struct sai (`cb` lệch, shim, lớp emulation), và mọi kết cục kiểu đó đến dưới dạng
**số nguyên nhỏ trông hợp lý**. Nên: working set phải `> 0` (một process đang sống
không thể có working set bằng 0) và peak không bao giờ dưới giá trị hiện tại. Nhưng
commit **không** bị đòi `> 0`, vì tài liệu ghi *"Windows 7 ... and earlier:
**PagefileUsage** is always zero"* — đòi nonzero sẽ báo một OS cũ là một OS hỏng.

### 4c. M2 — đo trên child process thật (lượt 34)

Hai điều mục 4b phải để ngỏ nay **đã đo**, trên một **child Python vô hại**
(`sys.executable -c`, script thoát ngay hoặc dựng một list vừa phải rồi xoá). **Không
model, không binary, không GPU, không job limit, không stress test, không ghi đĩa.**

**1. Handle sống qua cái chết của process — [ĐÃ ĐO].** Mở handle theo PID, đọc khi
child còn sống, cho child thoát (`rc=0`), rồi đọc **lại qua cùng handle** → **vẫn
đọc được**. Đúng câu tài liệu *"valid until closed, **even after** the process ...
has been terminated"*. Đây là lý do kỹ thuật để sampler **giữ một handle cho cả lần
chạy**: peak của một lần chạy **không mất** vì đọc muộn một nhịp.

**2. Peak LỆCH khỏi current — [ĐÃ ĐO], và đây là quan sát đầu tiên.** Ngay sau khi
child thoát: `working_set = 0.03 MiB` trong khi `PeakWorkingSetSize = 5.23 MiB`.
Nên **đọc giá trị hiện tại lúc muộn gần như không nói gì**.

**3. Nhưng phép đo đầu-đối-đầu ÔN HOÀ hơn tôi suy luận ở lượt 31 — [ĐÃ ĐO].** Lấy
mẫu `current` qua cả đời child rồi so `max(mẫu)` với counter OS:

| Nhịp lấy mẫu | Số mẫu | `max(current)` | `PeakWorkingSetSize` | Thiếu |
|---|---|---|---|---|
| **300 ms** (y như `measure.py`) | 2 | 5.02 MiB | 5.23 MiB | **0.21 MiB — 4.0%** |
| **10 ms** (nhanh 30×) | 33 | 5.02 MiB | 5.23 MiB | **0.21 MiB — 4.0%** |

**Hai kết luận, và kết luận thứ hai quan trọng hơn:**

- Chênh **có thật nhưng nhỏ** trên tải này: **4.0%**, không phải một bậc độ lớn.
- **Lấy mẫu nhanh 30× KHÔNG giảm được chênh.** Tức nút cổ chai **không phải** nhịp
  lấy mẫu — mà là việc `max(current)` **về nguyên tắc** không thấy một đỉnh giữa hai
  mẫu, và ở đây đỉnh ấy nằm trong khoảng mà cả hai nhịp đều bỏ qua như nhau.

**Đính chính lượt 31.** Lượt 31 viết `4438` là *"chặn dưới do lấy mẫu một cách KHÔNG
cần thiết"*. Phần **"chặn dưới"** và **"không cần thiết"** vẫn đúng. Nhưng nếu ai đọc
câu đó thành *"nên 4438 thấp hơn đáng kể"* thì **không có bằng chứng nào đỡ**: phép
đo duy nhất tôi có nói **4%** trên một child tầm thường, và **không** suy ra được cho
một lần chạy model 4,4 GiB — profile cấp phát khác hẳn (mmap lớn, plateau dài). Độ
lớn của chênh cho một lần chạy model **vẫn là [CHƯA ĐO]**.

**4. PID mở được KHÔNG có nghĩa process còn sống — [ĐÃ ĐO].** Sau khi child thoát,
mở lại **theo PID** vẫn **THÀNH CÔNG** miễn còn một handle khác (`Popen` giữ một
handle). Chỉ sau khi `Popen` được giải phóng thì mới `no-such-process`. Nên một phép
kiểm "còn sống" bằng `OpenProcess(pid)` là **sai**; và đây cũng là cơ chế khiến PID
**không** bị tái dùng trong khi còn handle. *(Không đưa thành test: nó phụ thuộc GC,
và một assertion phụ thuộc GC là một test chập chờn.)*

**Sáu test mới**, và **3 mutation đều đỏ**: mở PID hai lần thay vì một; không bao giờ
đóng handle; đóng handle trước khi `yield`. Cộng một **hàng rào chống spawn** cho
chính file test — `test_bench_harness.py` chỉ soi chính nó, nên nếu không thêm thì
spawn mới này nằm ngoài mọi hàng rào.

### Điều prototype này **không** chứng minh

- **Không** phải phép đo của bất kỳ model nào. Số lúc smoke-test là của `python.exe`
  chạy test (~17 MiB); số ở mục 4c là của một child Python (~5 MiB). Không ngưỡng
  nào được suy ra từ chúng.
- **Độ lớn chênh giữa `max(mẫu)` và peak thật cho một lần chạy MODEL: [CHƯA ĐO].**
  4% là của một child tầm thường.
- **Chưa** nối vào `measure.py`; schema artifact **chưa đổi**; cả bốn hằng ngưỡng
  vẫn `None`.
- **Không** đổi gì về ngưỡng. `CPU_RAM_MARGIN_MIB`, `REQUIRED_FREE_RAM_CPU_MIB`,
  `ASR_CPU_RAM_MARGIN_MIB`, `REQUIRED_FREE_RAM_ASR_CPU_MIB` đều còn `None`, và có
  test khẳng định — để việc **thêm dụng cụ đo không bao giờ bị đọc thành duyệt**.

### Bước tích hợp tương lai — **[ĐỀ XUẤT]**, cần Sơn duyệt

Theo thứ tự, mỗi bước một lát:

1. Mở handle cho child ngay sau spawn, giữ tới khi nó thoát — **đổi chữ ký**
   `ProcessRamSampler` từ `image_name` sang handle. Cần test cho child thật.
2. Thay thân `peak_working_set_mib` bằng `read_process_memory`, và **đổi tên** hàm
   cho đúng nghĩa.
3. Thêm commit và page fault vào artifact. **Đây là chỗ đổi schema** — nên nó cần
   Sơn duyệt, theo mục 6 phương án B.

Bước 1–2 làm phép đo chính xác hơn mà **không** đổi nghĩa trường đã lưu; bước 3 thì
đổi. Không bước nào được chạy khi chưa có quyết định ở mục 6.

## 5. ASR: bằng chứng là n=0, kể cả ở upstream

**[ĐÃ ĐO]** `var/bench/` **không có artifact ASR nào**; cả 4 artifact có
`ram_peak_working_set_mib` đều là llama.cpp.

**[ĐÃ ĐO từ upstream]** Bảng memory requirements của whisper.cpp, nguyên văn:

| Model | Disk | Mem |
|---|---|---|
| tiny | 75 MiB | ~273 MB |
| base | 142 MiB | ~388 MB |
| small | 466 MiB | ~852 MB |
| medium | 1.5 GiB | ~2.1 GB |
| large | 2.9 GiB | ~3.9 GB |

**`large-v3-turbo` KHÔNG có trong bảng này** — mà đó chính là model ta đã staged
(`ggml-large-v3-turbo.bin`, 1549 MiB). Nên **ngay cả upstream cũng không có số cho
model của ta**.

whisper.cpp khai *"Zero memory allocations at runtime"*. **[SUY LUẬN]** Nếu đúng với
build của ta, footprint ASR sẽ **ổn định hơn** LLM (nơi KV cache lớn theo context) —
nhưng đó là một suy luận từ một dòng marketing trong README, **không phải phép đo**,
và tôi **không** dùng nó làm căn cứ cho ngưỡng.

**Kết luận mục này:** `ggml-small.bin` (465 MiB đĩa) khớp hàng `small` (~852 MB
mem) về bậc độ lớn; `large-v3-turbo` thì **không có hàng nào**. Hai điều này cùng
nói: **ngưỡng ASR phải theo từng model**, và **không được vay 4438** — đó là số của
Qwen3-4B.

## 6. Phương án — tối đa ba, Sơn chọn

### A. **Giữ fail-closed** *(đang áp dụng — [CHỐT] của Sơn)*

| | |
|---|---|
| **Dữ liệu cần thu** | không |
| **Rủi ro còn lại** | **không** rủi ro OOM; nhưng cấp B **không tiến** |
| **Phạm vi code** | **không đổi gì** |
| **Sơn cần duyệt** | không — đây là trạng thái hiện tại |

### B. **[ĐỀ XUẤT] Một lần chạy có giám sát, trong Job object, chế độ ĐO không CƯỠNG CHẾ**

Không dùng limit để "bảo vệ" — vì mục 3a cho thấy commit limit **không chặn
weights**. Dùng Job object để **lấy peak thật**, cộng một commit limit đặt **cao**
làm lưới cuối chỉ cho KV cache/heap.

| | |
|---|---|
| **Dữ liệu cần thu** | `PeakWorkingSetSize` (peak thật, không lấy mẫu) · `PeakPagefileUsage` (peak commit) · `PeakJobMemoryUsed` · `ullAvailPhys` **và** `ullAvailPageFile` trước/sau · page-fault count |
| **Rủi ro còn lại** | **thrashing và treo máy vẫn có thật**: không cơ chế nào ở mục 3 chặn được trang file-backed của GGUF. Lưới duy nhất là **chọn model nhỏ** và **đóng bớt process**. |
| **Phạm vi code** | `benchmarks/measure.py`: thay sampling bằng counter của OS (đổi nội dung artifact) · một helper Job object mới (`ctypes`, **không dependency mới**) · `benchmarks/preflight.py`: ghi cả hai `ullAvail*` |
| **Sơn cần duyệt** | (1) cho phép **một** lần chạy có giám sát; (2) chạy model **nào**; (3) chấp nhận artifact **đổi schema** |

### C. **Không dùng Windows limit làm cổng; cổng theo kích thước file + biên, đo bằng counter OS**

Nếu Sơn không muốn một lần chạy có giám sát, phương án còn lại là **không giả vờ
rằng OS giúp được**. Cổng vẫn `pending`, nhưng ngưỡng khi được duyệt sẽ dựa trên
**một đại lượng đo được mà không cần chạy**: kích thước file model, cộng một biên
chính sách.

| | |
|---|---|
| **Dữ liệu cần thu** | không cần chạy gì: kích thước file đã biết (2382 / 469 / 1549 / 465 MiB) |
| **Rủi ro còn lại** | **cao hơn B**: kích thước file **không** cho biết KV cache, và với LLM phần đó phụ thuộc `--ctx-size`. Một ngưỡng từ kích thước file là **chặn dưới của nhu cầu**, không phải chặn trên |
| **Phạm vi code** | `preflight.py`: ngưỡng dẫn xuất từ kích thước file + biên |
| **Sơn cần duyệt** | **biên** — vẫn là đúng câu hỏi chính sách đang chờ, chỉ dựa trên một cơ sở khác |

**[ĐỀ XUẤT] B, nếu Sơn muốn cấp B tiến.** Lý do: nó là phương án duy nhất biến
`4438` từ **chặn dưới do lấy mẫu** thành **peak thật**, và nó làm thế bằng counter
OS **đã có**, không dependency mới. Nhưng nó **cần** một lần chạy, mà Sơn đã chốt
chưa cho phép — nên **A vẫn là trạng thái hiện hành** và tôi không tự đổi.

## 7. Protocol riêng — LLM và ASR không dùng chung

**Tôi không chạy protocol nào.** Đây là thứ sẽ chạy *nếu* Sơn duyệt B.

### 7a. LLM CPU

1. Đóng bớt process tới khi `ullAvailPhys` **≥ 2× kích thước file model**; ghi lại số.
2. Tạo Job object: `JobObjectNotificationLimitInformation` (**đo, không cưỡng chế**),
   cộng `JOB_OBJECT_LIMIT_PROCESS_MEMORY` đặt **cao** (chỉ bắt KV cache chạy loạn).
3. Chạy **`qwen2.5-0.5b` trước** (469 MiB — nhỏ nhất đã staged), `--device none`,
   **`--only` một case**, `--ctx-size` mặc định.
4. Thu: `PeakWorkingSetSize`, `PeakPagefileUsage`, `PeakJobMemoryUsed`, cả hai
   `ullAvail*` trước/sau, page faults.
5. **Dừng. Báo cáo. Không tự chuyển sang Qwen3-4B** — đó là một lần duyệt riêng.
6. Lặp **≥3 lần** cùng cấu hình: đó là thứ cho **độ tản**, thiếu chính xác ở n=1.

### 7b. ASR CPU

1. Giống bước 1-2.
2. Chạy **`ggml-small.bin`** (465 MiB) — **không phải** `large-v3-turbo`: upstream có
   hàng `small` để đối chiếu bậc độ lớn, và **không có hàng nào** cho turbo.
3. Clip **ngắn nhất** có trong manifest. Vấn đề đã biết của upstream là bộ nhớ tăng
   theo **audio dài**, nên một clip dài là biến số sai để bắt đầu.
4. Thu cùng tập counter.
5. **Dừng.** `large-v3-turbo` là một lần duyệt riêng, và nó là model **không có số
   upstream nào**.

**Ngưỡng của 7a KHÔNG được dùng cho 7b, và ngược lại.** Hai cổng đã tách trong code
(`require_cpu_preflight` vs `require_asr_cpu_preflight`) đúng vì lý do này, và có
test khẳng định chúng **không phải cùng một hàm**.

## 8. Phần dư — ghi thẳng

- **Không cơ chế Windows nào chặn được trang file-backed của GGUF.** Commit limit
  không thấy chúng; hard working-set max chỉ **trim** chúng. Nên "giới hạn ở tầng
  OS" **không** loại bỏ rủi ro OOM/thrashing — nó chỉ làm phần commit fail sạch.
- **Bề mặt flag của llama.cpp phụ thuộc version.** README upstream hiện tài liệu
  hoá *loading modes* `auto|none|mmap|mlock|mmap+mlock|dio` và **không** còn
  `--no-mmap`. Build của ta pin **b11464**. **[CHỜ BẰNG CHỨNG]** tôi **không** xác
  minh build đó nhận flag nào, vì làm thế phải gọi binary. Kiểm được bằng
  `llama-cli.exe --help` nếu Sơn cho phép chạy binary ở chế độ help.
- **`--mlock` làm mọi phân tích trên sai.** Upstream: *"requiring more RAM to run"*.
  Nếu mlock bật, trang mmap thành **non-pageable** và bài toán đổi hẳn. Protocol ở
  mục 7 giả định **không mlock**.
- **Peak của Job là high-water mark theo đời job**, *"any process **ever**
  associated"* — nên một job tái dùng cho nhiều case sẽ báo peak của **case tệ
  nhất**, không phải của case cuối. Đó là thứ ta muốn, nhưng phải biết để không đọc
  sai.
- **Prototype `winmem.py` chưa chạy trên child process** và **chưa thấy một quan sát
  nào mà peak lệch khỏi giá trị hiện tại** (xem mục 4b). Nó chứng minh struct, lời
  gọi và mapping lỗi hoạt động — không chứng minh nó bắt được peak của một tải thật.
- **`ctypes.get_last_error()` đọc mã lỗi lưu theo thread của lời gọi ctypes gần
  nhất** có `use_last_error=True`. Trong prototype, lời gọi đó đứng ngay trước khi
  đọc, nên hiện không có khe hở; nhưng nếu sau này có lời gọi ctypes chen vào giữa,
  mã lỗi có thể **cũ**. **[CHỜ BẰNG CHỨNG]** chưa có test nào bắt được tình huống đó.
- **Tôi không đo được tỷ lệ weights/KV trong 4438 MiB** mà không chạy. Mọi phát biểu
  về "phần weights là đa số" là **[SUY LUẬN]** từ kích thước file.

## Nguồn

Tất cả truy cập **2026-10-10**.

- [JOBOBJECT_EXTENDED_LIMIT_INFORMATION](https://learn.microsoft.com/en-us/windows/win32/api/winnt/ns-winnt-jobobject_extended_limit_information)
- [JOBOBJECT_BASIC_LIMIT_INFORMATION](https://learn.microsoft.com/en-us/windows/win32/api/winnt/ns-winnt-jobobject_basic_limit_information)
- [MEMORYSTATUSEX](https://learn.microsoft.com/en-us/windows/win32/api/sysinfoapi/ns-sysinfoapi-memorystatusex)
- [PROCESS_MEMORY_COUNTERS](https://learn.microsoft.com/en-us/windows/win32/api/psapi/ns-psapi-process_memory_counters)
- [PROCESS_MEMORY_COUNTERS_EX](https://learn.microsoft.com/en-us/windows/win32/api/psapi/ns-psapi-process_memory_counters_ex)
- [GetProcessMemoryInfo](https://learn.microsoft.com/en-us/windows/win32/api/psapi/nf-psapi-getprocessmemoryinfo)
- [OpenProcess](https://learn.microsoft.com/en-us/windows/win32/api/processthreadsapi/nf-processthreadsapi-openprocess)
- [Process Handles and Identifiers](https://learn.microsoft.com/en-us/windows/win32/procthread/process-handles-and-identifiers)
- [Process Security and Access Rights](https://learn.microsoft.com/en-us/windows/win32/procthread/process-security-and-access-rights)
- [CreateFileMappingA](https://learn.microsoft.com/en-us/windows/win32/api/winbase/nf-winbase-createfilemappinga)
- [SetProcessWorkingSetSizeEx](https://learn.microsoft.com/en-us/windows/win32/api/memoryapi/nf-memoryapi-setprocessworkingsetsizeex)
- [Introduction to the page file](https://learn.microsoft.com/en-us/troubleshoot/windows-client/performance/introduction-to-the-page-file)
- [llama.cpp — tools/completion/README.md](https://github.com/ggml-org/llama.cpp/blob/master/tools/completion/README.md)
- [whisper.cpp — README](https://github.com/ggml-org/whisper.cpp)

[PROCESS_MEMORY_COUNTERS]: https://learn.microsoft.com/en-us/windows/win32/api/psapi/ns-psapi-process_memory_counters
[MEMORYSTATUSEX]: https://learn.microsoft.com/en-us/windows/win32/api/sysinfoapi/ns-sysinfoapi-memorystatusex
[SetProcessWorkingSetSizeEx]: https://learn.microsoft.com/en-us/windows/win32/api/memoryapi/nf-memoryapi-setprocessworkingsetsizeex
