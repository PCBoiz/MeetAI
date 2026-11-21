---
title: "Báo cáo: chuẩn bị fine-tune ASR và thí nghiệm đầu tiên trên Colab"
owner: "Sơn"
created: "2026-11-19"
last_updated: "2026-11-19"
purpose: "Tóm tắt những gì đã làm trong lượt 57-59, kết quả đo, giới hạn, và chỗ lấy mã (notebook Colab). Không chứa dữ liệu họp."
---

# Báo cáo chuẩn bị fine-tune ASR

**Notebook Colab (chứa 10 patch dưới dạng cell base64 đã kiểm checksum):**
<https://colab.research.google.com/drive/1lm7V9qTDRzVYtDkDGjlJ9ZMV03-C_Sa1?usp=sharing>

Mọi việc làm trong **clone công khai** của repo (bản chụp `16f043e`), trên Colab Pro. Không audio, nhãn hay
manifest họp nào được tải lên; chỉ mã công khai, dữ liệu tổng hợp và FLEURS vi_vn (CC-BY-4.0).

## 1. Đã làm (10 commit trên `16f043e`)

| # | Nội dung | Bằng chứng |
|---|---|---|
| 1 | `benchmarks/meeting_intake.py`: codec, tỷ lệ speech, độ dài đoạn; chỉ WAV | 48 test, 11/11 mutation bị bắt |
| 2 | `benchmarks/meeting_manifest.py`: manifest, validator, chia tập theo nhóm có seed | 99 test, 20/20 mutation |
| 3 | `paired_bootstrap_syer`, `label_bias_report`, `benchmarks/paired_ci.py` | 43 test, 20/21 mutation (1 guard dư) |
| 4 | `pin_digest.py`, `ram_probe.py`, `scripts/windows/egress-rule.ps1` (chỉ in) | 45 test, 16/16 mutation; script PowerShell **chưa chạy** |
| 5 | `finetune/prep_data.py`: xuất JSONL chỉ `train`/`dev`, `test` không xuất được | 34 test, 13/13 mutation |
| 6 | `finetune/train_asr_lora.py`: LoRA fp16 sau các cổng, import nặng chỉ sau cổng | 47 test, 20/21 mutation |
| 7 | Phác nhánh LLM (không mã) | — |
| 8 | Runbook Windows, ghi chú REA/Kanzo, plan/spec/state | — |
| 9 | Ghi lần chạy GPU đầu (dữ liệu tổng hợp) | — |
| 10 | Lưu adapter epoch tốt nhất; ghi thí nghiệm công khai; mục YouTube cho Windows | test cấu trúc + mutation |

Bốn kiểm tra (đo ở Colab, CPU): ruff format/check xanh; mypy xanh với `--platform win32`;
pytest **5610 passed, 3 failed, 13 skipped** — ba lỗi y hệt baseline bản chụp, đều do nền tảng/bản chụp
(thiếu `var/bench`, `c_ulong` 8 byte trên Linux, `os.getlogin()` không có tty).

## 2. Thí nghiệm công khai (FLEURS vi_vn, whisper-small, Colab L4)

1000 clip train (3,0 giờ), 361 clip dev (1,2 giờ, N = 10 422). LoRA r=32, alpha=64, lr 5e-4, fp16.

| Hệ thống | SyER | Khoảng 95% | S / D / I |
|---|---|---|---|
| baseline | 27,04% | [23,73; 31,98] | 2302 / 137 / 379 |
| LoRA 3 epoch | 22,68% | [20,87; 24,94] | 2089 / 103 / 172 |
| LoRA 1 epoch | 21,91% | [20,56; 23,42] | 2082 / 97 / 104 |
| 3 epoch + lưu epoch tốt nhất | 22,04% | [20,69; 23,57] | 2095 / 97 / 105 |

So theo cặp: baseline → 3 epoch **+4,36 pp** [+1,11; +9,06]; baseline → 1 epoch **+5,13 pp** [+2,24; +9,84]
(không chứa 0). Phần lớn mức giảm là bớt **phép chèn**. Dev loss thấp nhất ở epoch 1 rồi tăng (quá khớp).

## 3. Giới hạn

- **Cùng miền:** huấn luyện và đo đều là FLEURS (đọc từng câu, một người, sạch). **Không** ngoại suy sang họp.
- Epoch tốt nhất chọn theo dev loss trên chính tập dev rồi đo trên đó nên số hơi lạc quan; chưa đo trên split test.
- Baseline 27,04% **không** so trực tiếp được với 23,47% đã ghi ở S2.2 (khác runtime, cách giải mã).
- L4 không phải GTX 1660 Ti: 5,7 GB đỉnh ở batch 8 là sát giới hạn 6 GB; trên Windows cần batch nhỏ hơn (chưa đo).
- Chưa tái lập hai khoảng đã lưu 3,03 pp và 1,72 pp (artifact `var/asr/` không có ở bản chụp).
- Hai cổng (egress OS, digest base model) **chỉ lật trong harness Colab không commit**; trong repo vẫn đóng.
- Vòng huấn luyện chưa chạy trên audio họp thật, trên Windows hay Turing.

## 4. Hai bất biến đã ghim bị nới đúng một chỗ (cần chủ dự án xác nhận)

- `tests/test_winmem.py`: `ram_probe.py` được miễn khỏi "không benchmark nào import `winmem`".
- `tests/test_llm_boundary.py`: chỉ `scripts/windows/egress-rule.ps1` được miễn khỏi "không file launcher không phải Python nào được track", kèm test nó không khởi chạy tiến trình.

## 5. Cách lấy và áp patch

Chạy cell `# HANDOFF PAYLOAD v3` trong notebook để giải mã `handoff3.tgz` (kiểm sha256), tải về từ panel Files, rồi trên
bản sạch có cây giống `16f043e`:

```bash
git switch -c finetune-handoff
git am --keep-cr --3way patches/*.patch
```

`--keep-cr` cần thiết vì 53 file đang theo dõi dùng CRLF.

## 6. Việc chờ chủ dự án

Hướng cho `huggingface_hub` (một câu hỏi chung cho cả ASR và LLM); ba tỷ lệ chia tập; quyết định ffmpeg;
xác nhận hai nới lỏng ở mục 4; ghim digest và mở attestation egress sau khi có bằng chứng pcap; một dòng văn bản
về phạm vi huấn luyện của người đồng thuận. Audio YouTube được xử lý **trên Windows** (runbook mục 0b), không qua Colab.

**Bước kế tiếp đề xuất:** đo adapter trên split test FLEURS và thử nền khác (PhoWhisper, whisper-medium); trên
Windows chạy lô đo ~30 phút trên audio họp có nhãn mù trước khi quyết định có cần fine-tune hay không.
