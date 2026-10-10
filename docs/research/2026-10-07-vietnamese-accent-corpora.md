# Ứng viên corpus tiếng Việt **có nhãn accent** — dữ liệu tham khảo

Khảo sát 2026-10-07 (lượt 11). **Đây là dữ liệu tham khảo, không phải quyết
định.** Không tải gì, không thêm dependency, không đưa artifact nào vào repo.

Bối cảnh: `spec.md` B-1 yêu cầu WER/CER **theo accent**. Hiện trục đó là
**`absent` vì thiếu NHÃN**, không phải vì thiếu dữ liệu — FLEURS `vi_vn` chỉ có
nhãn `gender`. Tôi sẽ **không** suy ra một trục accent từ audio không có nhãn.

## Phân biệt: cái tôi tự xác minh vs cái còn là claim

Mọi dòng dưới đây đánh dấu rõ. Tôi xác minh lại bằng HF API vì đây là quyết
định về license và phạm vi.

### ✅ Tôi tự xác minh được (HF API, 2026-10-07)

| Hạng mục | Giá trị | Nguồn tôi gọi |
|---|---|---|
| `leduckhai/VietMed` license tag | **`mit`** | `/api/datasets` |
| `leduckhai/VietMed` gated | **False** | `/api/datasets` |
| VietMed có cột `accent` | **CÓ** | `/info` — features: `audio, text, duration, utterance_id, speaker_name, seq_name, audio_name, role, gender, accent, icd10_code, rec_condition` |
| VietMed có cột `text` | **CÓ** → tính được WER | `/info` |
| VietMed split | train 2773 · dev 2912 · **test 3437 (70.0 MB)** · cv 85 | `/info` |
| VietMed phân phối `accent` (test) | **5 lớp**: South West 1164 · South Central Coast 809 · South East 750 · North 693 · **North Central Coast 21** | `/statistics` |
| VietMed `rec_condition` (test) | 7 lớp: Podcast 766 · Talkshow 730 · Tel 607 · Consultation 446 · Lectures 384 · News 312 · Diagnosis 192 | `/statistics` |
| `nguyendv02/ViMD_Dataset` license tag | **`cc-by-nc-nd-4.0`** ← **ND**, không phải SA | `/api/datasets` |
| ViMD gated | False | `/api/datasets` |
| `linhtran92/viet_bud500` license | `cc-by-nc-sa-4.0`, gated **auto** | `/api/datasets` |

### ⚠️ Còn là claim, tôi **chưa** xác minh được

| Claim | Trạng thái |
|---|---|
| VietMed audio là **8 kHz** | **[CHỜ BẰNG CHỨNG]** — feature `Audio` **không khai `sampling_rate`**, nên không đọc được từ metadata. Là claim trong paper. Xác minh cần tải. |
| VietMed license: paper ghi **CC BY 4.0**, HF tag ghi **MIT** | **[CHỜ BẰNG CHỨNG]** — mâu thuẫn giữa hai nguồn. **Cả hai đều permissive** nên rủi ro thấp, nhưng cần hỏi tác giả nếu muốn trích dẫn chắc chắn. |
| ViMD license: paper ghi **CC BY-NC-SA**, HF tag ghi **CC BY-NC-ND** | **[CHỜ BẰNG CHỨNG]**, và **điều này QUAN TRỌNG** — xem dưới. |
| Nhãn accent VietMed do **annotator gán theo cảm nhận** | claim trong paper |
| Nhãn ViMD **suy từ provenance** (đài tỉnh nào phỏng vấn) | claim trong paper |
| VietMed giữ lại overlap nhưng **không gán nhãn** | claim trong paper |
| `VietMed-Dialect` **không tồn tại** | claim — profile `leduckhai` chỉ có 8 dataset, không có cái nào về dialect |

## Hai ứng viên thật

### VietMed — `leduckhai/VietMed`

**Đóng được trục accent.** Permissive (MIT theo tag), **ungated**, có transcript,
nhãn accent **theo từng utterance**, test split chỉ **70 MB**.

**Cho phép nói:** WER/CER theo nhóm accent trên VietMed test (n=3437), **4 nhóm
dùng được** (n ≥ 693) **cộng một nhóm không đủ lực** (North Central Coast
**n=21**); nhãn do annotator gán; speaker không trùng giữa các split.

**KHÔNG cho phép nói:** rằng số đó **so sánh được** với lần chạy FLEURS của tôi
(domain **y tế** khác hẳn, và nếu 8 kHz là đúng thì khác cả băng tần); rằng
`North` đã được phân giải (chính tác giả nói annotator **không** chia nổi
subregion miền Bắc); rằng NCC đã được đo (n=21 là không đo được); rằng overlap
được kiểm soát (có overlap, **không** có nhãn).

**Confound tôi tự thấy trong số liệu:** `accent` đi kèm `rec_condition` 7 lớp
(Podcast/Talkshow/Tel/Consultation/Lectures/News/Diagnosis). Với ~700–1200 mẫu
mỗi ô accent, **không tách được** ảnh hưởng của accent khỏi ảnh hưởng của điều
kiện thu. Một bảng "WER theo accent" ở đây đo **accent + điều kiện thu**, và
phải nói thế.

### ViMD — `nguyendv02/ViMD_Dataset`

**Trục accent tốt hơn** (3 vùng / 63 tỉnh, 12 955 speaker, spontaneous, đã lọc
bỏ phát thanh viên) **nhưng bị chặn bởi license.**

**HF tag là `cc-by-nc-nd-4.0`** — tôi xác minh trực tiếp. **ND lan rất xa hơn
người ta tưởng:** ViMD **không chuẩn hoá sample rate** (paper nói giữ nguyên
rate gốc), nên để dùng với whisper.cpp tôi **buộc phải resample** — và resample
**là một derivative**. Dưới ND, tôi có thể dùng cục bộ nhưng **không được phát
hành** tập eval đã resample, nên **reproducibility-bằng-cách-phát-hành bị loại**.

Và **NC dưới cả hai cách đọc**, nên theo **A13** mọi số từ ViMD thuộc **nhánh
NC tách riêng**, không đủ điều kiện cho sản phẩm/phát hành.

## Một nhận xét cấu trúc đi ngược cách tôi từng khung vấn đề

Tôi từng nghĩ phương án yếu sẽ là *"đọc câu nhưng có nhãn accent"*. **Phương án
đó không tồn tại cho tiếng Việt.** Các corpus **đọc câu** (VIVOS, FOSD, FLEURS
vi, Common Voice vi scripted) đúng là những cái **không có** nhãn accent; còn
các corpus **có** nhãn accent (VietMed, ViMD, VietPrism) đúng là những cái
**spontaneous**.

Nên đánh đổi thật **không phải** đọc-câu-vs-spontaneous. Nó là:
**permissive + domain y tế + một ô n=21 (VietMed)** đối lại
**NC + ND chưa giải quyết + nhãn suy từ provenance + sample rate không đồng nhất
(ViMD)**.

## Những thứ bị loại, và vì sao

| Corpus | Lý do loại cho trục accent |
|---|---|
| `hr16/ViSpeech-Gender-Dialect-Classification` | Có 4 lớp dialect nhưng **không có cột transcript** → đo *nhận dạng dialect*, **không** đo được WER. Không phục vụ được nghĩa vụ. |
| `linhtran92/viet_bud500` | Card nói "spans accents from North/South/Central" nhưng **không có cột accent/region** — features chỉ `audio` + `transcription`. Claim đó là marketing, không phải metadata. Thêm nữa: NC-SA và **gated auto**. |
| `capleaf/viVoice`, VietSuperSpeech, GigaSpeech2-vi, PhoAudioBook | **không có nhãn accent** |
| VLSP / VinBigData | **không có nhãn accent**, **và** cần **ký thoả thuận**, research-only, **không được phát hành lại** |
| Common Voice vi (scripted) | Trường `accents` tồn tại nhưng **self-reported và chỉ khi speaker opt-in**; với `vi` gần như rỗng. Và phân phối đã chuyển sang Mozilla Data Collective, **cần tạo account + đồng ý ToS mới**. |
| VietPrism | 993 h spontaneous, 5 nhóm dialect, nhưng **chưa phát hành**, **chưa có license**, và **không nói nhãn do người gán hay model đoán** → tự loại cho tới khi trả lời được. |
| VDSPEC, VNSC, LSVSC, VN-Celeb, ViASR | **[CANNOT VERIFY]** — không tìm được trang phát hành, license hay repo công khai |

## Residual quan trọng: accent và overlap **không chéo được**

**Không corpus tiếng Việt nào tìm được có đồng thời nhãn accent VÀ nhãn
overlapping speech.** ViMD và VietPrism loại bỏ hoặc không nói tới overlap;
VietMed giữ overlap ngẫu nhiên nhưng **không gán nhãn** nó.

Nên trục "nói chồng" của spec **không thể chéo với trục accent** trên bất kỳ dữ
liệu công khai nào — nó cần một nguồn riêng, hoặc ghi là `absent` **vì thiếu
nhãn**, đúng cách trục accent đang được ghi hôm nay.
