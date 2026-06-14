# Rule: Cấu trúc các section & phasing

| Section | File design | Nội dung |
| --- | --- | --- |
| 01 | `01_data_generator.md` | Sinh dữ liệu offline (batch) + streaming. Định nghĩa schema, grain, tham số sinh; chủ động chèn lỗi/thách thức dữ liệu thực tế. |
| 02 | `02_schema_design.md` | Storage/schema + pipeline (Bronze→Silver→Gold + feature). Data quality, SLA, update policy, backfill. Bảng/view phục vụ business + naming convention. |
| 03 | `03_data_generator_improvement.md` | Nâng độ thực của generator. Thêm kịch bản **drift/thay đổi** + bảng label/training cho ML. Giải thích vì sao drift ảnh hưởng downstream AI. |
| 04 | `04.1_ml_design.md` **hoặc** `04.2_llm_design.md` | Chọn **ít nhất một** AI track. ML: training/inference/monitoring/retraining. LLM: RAG + tool-call + serving + safety + eval. |

## Phasing
- **Mini-coursework phase (hiện tại):** hoàn thành **Section 01 + 02** kèm code evidence.
- **Final phase (sau):** thêm Section 03 + một AI track (04.1 hoặc 04.2).

> Nền dữ liệu (01+02) phải ổn định trước khi làm AI. Tập trung vào 01 và 02 trước.
