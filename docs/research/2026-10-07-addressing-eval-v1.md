# Danh gia direct-address classifier (S1.7), corpus v1

Corpus **synthetic**, alias **gia**. Do logic, **khong** phai bang chung classifier chay tot tren tieng Viet thuc te, va **khong** calibrate duoc nguong nao. Moi ty le kem denominator.

## Chi so dau bao

| Chi so | Gia tri | Y nghia khi sai |
|---|---|---|
| False activation | 0/48 = 0.0% [95% CI 0.0-7.4%] | MeetAI noi khi khong duoc goi |
| False non-address | 0/8 = 0.0% [95% CI 0.0-32.4%] | MeetAI im khi duoc hoi |
| UNCLEAR rate | 21/56 = 37.5% [95% CI 26.0-50.6%] | khong phai diem; UNCLEAR la dap an dung cho phan lon corpus |
| Sai lop address | 0/56 = 0.0% [95% CI 0.0-6.4%] | |
| Sai intent | 1/56 = 1.8% [95% CI 0.3-9.4%] | |

## Theo nhom rui ro

| Nhom | n | false activation | false non-address | UNCLEAR | sai lop |
|---|---|---|---|---|---|
| P_direct_request | 8 | 0/8 | 0/8 | 0/8 | 0/8 |
| Q_vocative_only | 6 | 0/6 | 0/6 | 0/6 | 0/6 |
| R_third_person | 8 | 0/8 | 0/8 | 1/8 | 0/8 |
| S_word_collision | 8 | 0/8 | 0/8 | 0/8 | 0/8 |
| T_no_addressee | 8 | 0/8 | 0/8 | 4/8 | 0/8 |
| U_quote_negation | 8 | 0/8 | 0/8 | 8/8 | 0/8 |
| V_ambiguous_speaker | 10 | 0/10 | 0/10 | 8/10 | 0/10 |

## Vi du sai

- `U.quote.06` (U_quote_negation): intent nhan `request`, code tra `question` **[known gap]**

## Gioi han

- Corpus do chinh tac gia viet ra. No kiem tra logic va bat lop loi, **khong** do duoc phan phoi cau noi thuc te.
- Alias `MeetAI` la gia tri fixture, **khong** phai quyet dinh ve ten goi cua MeetAI. Registry mac dinh rong.
- Turn context (`addressed_to_me_by_turn`) chi dat duoc khi participant mapping dang tin cay. **Gate 0-C con mo**, nen duong code do hom nay chi duoc test, chua duoc dung.
- Khong co confidence tren assessment. `MINIMUM_CONFIDENCE` van la placeholder chua calibrate va corpus synthetic khong calibrate duoc.
