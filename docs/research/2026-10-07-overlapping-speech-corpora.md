
# Ứng viên corpus cho trục **nói chồng** (overlapping speech) — dữ liệu tham khảo

Khảo sát 2026-10-07 (lượt 11). **Dữ liệu tham khảo, không phải quyết định.**
Không tải gì, không thêm dependency, không đưa artifact nào vào repo.

Bối cảnh: `spec.md` B-1 yêu cầu WER/CER **theo nói chồng**. Trục đó hiện là
**`absent`** vì không corpus licensed nào trong phạm vi có tiếng nói chồng.

## Kết luận ngắn

**Không tìm được corpus nào thoả đồng thời bốn điều kiện** mà dự án cần:
(a) tiếng Việt, (b) có overlap thật, (c) overlap **được gán nhãn**, (d) có
**transcript do người làm** + license/đường truy cập tương thích với một dự án
riêng tư, offline, không chi phí, **không có cơ quan đứng tên ký**.

Mỗi ứng viên trượt một điều kiện **khác nhau** — và đó là lý do trục này khó,
không phải vì "dữ liệu tiếng Việt khan hiếm".

## ✅ Tôi tự xác minh được

| Hạng mục | Giá trị | Nguồn tôi gọi |
|---|---|---|
| `bsmu/MLC-SLM-Eval` | license `cc-by-sa-4.0`, ungated, **226 file, 0 file audio** → **chỉ có nhãn, không có audio** | `/api/datasets` + liệt kê siblings |
| `edinburghcstr/ami` (AMI) | license **`cc-by-4.0`**, ungated | `/api/datasets` |
| VietMed có cột `accent`/`text`, test 3437 dòng | (xem [khảo sát accent](2026-10-07-vietnamese-accent-corpora.md)) | `/info`, `/statistics` |

## Ba tầng ứng viên

### Tầng 1 — tiếng Việt, có overlap thật

| Corpus | Overlap | Gán nhãn overlap | Transcript | License / truy cập | Trượt ở đâu |
|---|---|---|---|---|---|
| **MLC-SLM** (có subset tiếng Việt: train 100.45 h, dev 2.15 h, eval-1 2.08 h) | có, hội thoại 2 người thật | **có** (oracle segmentation + speaker label + timestamp) | **có, người làm** | **Nexdata Data Use Agreement — chỉ trong phạm vi workshop, CẤM phát hành lại** | **license**. Và chính ban tổ chức nói overlap ở đó *"too brief to be considered significant"* |
| **VietMed** | **có** — paper nói **cố ý giữ lại** segment overlap | **KHÔNG** — không có cột overlap, không RTTM, không nhãn diarization | **có, người làm** | **MIT (tag HF), ungated** ✅ | **thiếu nhãn overlap** |
| `tuanamz/vi-sommelier-v0` | có, podcast 2 người | có `overlap_confidence` nhưng là **heuristic do model sinh**, không phải nhãn người | **pseudo-label ASR**; chỉ **68 turn** có text người sửa | **không có license**, gated | **transcript** (68 turn không đỡ được một claim WER) |
| VietPrism | **loại bỏ overlap theo thiết kế** | — | — | chưa phát hành | mọi mặt |
| `hustep-lab/VieSpeaker-Dataset` | cắt thành single-speaker | không | **không có transcript** | CC-BY-NC-4.0 | transcript |
| VietSuperSpeech | có | không | pseudo-label; **chính tác giả nói nhãn sai đúng ở chỗ overlap** | không rõ | transcript |
| VLSP | **không tìm thấy track diarization/meeting nào** | — | — | ký thoả thuận | không có track |
| CallFriend Vietnamese (LDC96S60) | có, điện thoại thật | — | **không transcribe** (thu cho Language ID) | LDC, có phí | transcript + phí |

### Tầng 2 — không phải tiếng Việt, có overlap **đã gán nhãn**

**Nói thẳng: không cái nào cho ra WER/CER tiếng Việt.** Chúng là tiếng Anh hoặc
tiếng Trung. AliMeeting/AISHELL-4 cùng là ngôn ngữ có thanh điệu nhưng **CER
tiếng Trung không phải CER tiếng Việt**. Dùng chúng để lấp ô "nói chồng" của một
trợ lý **tiếng Việt** là **thay một ngôn ngữ khác vào chỗ điều kiện còn thiếu** —
đúng loại thay thế mà dự án đã từ chối với đọc-câu.

| Corpus | License | Ngôn ngữ | Eval nhỏ nhất | Overlap |
|---|---|---|---|---|
| **AMI** | **CC BY 4.0** ✅ (verify) | English | eval partition | có nhãn |
| ICSI | CC BY 4.0 (bản Edinburgh) | English | eval | có nhãn, overlap cao |
| **AliMeeting** | **CC BY-SA 4.0** ⚠️ ShareAlike | **Mandarin** | **4 h, 3.42 GB** | **overlap ratio eval 34.76%** — cao nhất trong bộ chuẩn |
| AISHELL-4 | CC BY-SA 4.0 (có nguồn ghi BY-4.0 → mâu thuẫn) | Mandarin | eval | overlap eval 9.31% |
| NOTSOFAR-1 | CC BY 4.0 | English | dev 17.5 h | có nhãn; cần HF token |
| CHiME-5/6 | **Sheffield licence — cần đại diện CƠ QUAN ký** | English | — | **chặn: dự án riêng không có cơ quan đứng tên** |
| DIHARD III | **LDC, CÓ PHÍ** | English + Mandarin | eval ~33 h | diarization-oriented |

**Những cái này chỉ hỗ trợ được claim độc lập ngôn ngữ**: tỷ lệ phát hiện
overlap, DER, hành vi VAD/segmentation, hay việc transcript assembly có nhân đôi
/ bỏ sót vùng overlap. **Không** hỗ trợ bất kỳ câu nào dạng "WER tiếng Việt của
MeetAI khi nói chồng là X".

### Tầng 3 — trộn tổng hợp từ FLEURS: **sai lệch, không phải "trung thực nhưng giới hạn"**

Đây là phần quan trọng nhất, vì nó là lựa chọn **rẻ và đã có sẵn cục bộ** mà tôi
dễ bị hấp dẫn — tôi **đã** có bộ trộn noise.

**Kết luận: trộn hai utterance FLEURS KHÔNG tương tự phép thử noise của tôi, và
báo nó như trục nói chồng sẽ là SAI LỆCH CHỦ ĐỘNG.**

Bốn lý do, mỗi lý do là một chỗ nó khác hẳn phép thử noise:

1. **Reference trở thành nhập nhằng.** Ground truth là text của speaker A, của
   cả hai, hay text có gán speaker? Mỗi lựa chọn đo **một đại lượng khác**, và
   **không cái nào** là "WER khi nói chồng".
2. **Kết quả bị chi phối bởi một núm tuỳ ý** — mức gain khi trộn. Tài liệu đo
   được rằng đổi cách render (truncate-and-fade vs trộn ngang mức) làm **gấp đôi**
   lỗi vùng overlap, trong khi **thời điểm** trộn gần như không ảnh hưởng. Tức là
   con số sẽ phản ánh **lời gọi `numpy` của tôi**, không phản ánh nói chồng.
3. **Cơ chế thật bị thiếu hoàn toàn theo cấu tạo.** Một phần lớn hình phạt
   overlap thật là **hành vi người nói thay đổi quanh vùng overlap** (Lombard:
   tăng năng lượng/F0, giảm tốc độ nói), và vị trí chen lời **bị cấu trúc bởi
   luân phiên lượt nói** (backchannel, discourse marker, disfluency).
   **Người đọc FLEURS chưa bao giờ ở trong phòng với ai.** Không Lombard, không
   phòng chung, không timing tương tác.
4. **Nó đánh giá THẤP khoảng 30–60 điểm WER**, và **không đơn điệu**: trong một
   nghiên cứu, tăng overlap tổng hợp còn **làm số ASR đẹp hơn**.

**Một ô trống trung thực tốt hơn một con số sai** trong một bảng đánh giá gần
với an toàn — vì con số sai trông như một cổng đã đóng.

Nếu vẫn muốn làm, nó chỉ chấp nhận được khi **đổi tên thành đúng cái nó là**
("CER trên mixture hai người của **đọc câu** ở tỷ lệ gain R, overlap fraction F"),
báo rõ là **chặn dưới** mà tài liệu nói là đánh giá thấp thực tế, và **không**
tính là đã đóng nghĩa vụ nói chồng của spec.

## Hai điểm dừng có thể bảo vệ được

**(A) Ghi là ngoài phạm vi, nêu lý do, giữ cổng bằng chứng MỞ.** Rẻ nhất, trung
thực hoàn toàn. Mất ô đó.

**(B) Phép thử VietMed hẹp, tự gán nhãn.** VietMed-Test 6 h / 3437 câu / 27
speaker, free, ungated, hội thoại bác sĩ–bệnh nhân **thật**, overlap **cố ý được
giữ lại**. Tự tay đánh dấu segment nào nghe được giọng thứ hai, rồi báo: *"CER
trên các segment VietMed-Test được đánh dấu tay là có người nói thứ hai
(n = …, **một annotator duy nhất, không có inter-annotator agreement**,
reference **chỉ transcribe người nói chính**, mức segment không mức frame)"*.

Giá phải trả của (B), nói thẳng: **tôi trở thành người sản xuất nhãn** và phải
khai như vậy; và "reference chỉ có người nói chính" nghĩa là nó đo **độ nghe rõ
của người nói chính khi bị nhiễu bởi người khác**, **không** phải transcription
đa người nói. Nó đóng một nghĩa vụ **hẹp hơn** cái spec đang viết.

## Những thứ còn chưa giải quyết

- **[CHỜ BẰNG CHỨNG]** License dataset MLC-SLM — `[CANNOT VERIFY]`; chỉ xác minh
  được rằng artifact miễn phí duy nhất (`bsmu/MLC-SLM-Eval`) **không có audio**.
- **[CHỜ BẰNG CHỨNG]** VietMed license: paper **CC BY 4.0** vs tag HF **MIT**.
- Xin license ngoài phạm vi workshop từ Nexdata là **tác động ra bên ngoài** —
  theo `AGENTS.md` phải **dừng và xin xác nhận của Sơn** trước.
- **Không corpus tiếng Việt nào** có **đồng thời** nhãn accent **và** nhãn
  overlap → hai trục đó **không chéo được** trên dữ liệu công khai.

**Không mục nào ở đây được ghi [CHỐT].**
