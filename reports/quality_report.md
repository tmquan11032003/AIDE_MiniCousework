# Quality Report — Section 01 (Offline batch)

Seed cố định: `42` · Quy mô từ `config/generator.yaml`.
Chạy lại generator cho ra report y hệt (reproducible).

| Chỉ số | Đo được | Mục tiêu |
| --- | --- | --- |
| Số bảng / tổng rows | 7 bảng / 939,479 rows | — |
| Skew cửa hàng (top-8) | 75% | ~75% |
| Skew giờ cao điểm (7-9h) | 55% | ~55% |
| Skew category coffee | 67% | ~70% |
| Schema evolution (channel NULL pre-app) | 50% | ~50% |
| Duplicates order_items | 2.0% | ~2% |
| Missing customers.city | 1.0% | ~1% |
| Khách vãng lai (customer NULL) | 30% | ~30% |
| Cardinality order_id (unique) | 200,000 | 200,000 |
| Cardinality customer_id (unique) | 20,000 | 20,000 |
