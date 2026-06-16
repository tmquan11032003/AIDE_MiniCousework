# Quality Report — Section 01 (Offline batch)

Seed cố định: `42`. Chạy lại generator cho ra report y hệt.

| Chỉ số | Đo được | Mục tiêu |
| --- | --- | --- |
| Tổng rows (7 bảng) | 940,656 | — |
| Skew cửa hàng (top-N) | 75% | ~75% |
| Skew giờ cao điểm | 55% | ~55% |
| Skew category coffee | 70% | ~70% |
| Schema evolution (channel NULL) | 50% | ~50% |
| Duplicates order_items | 2.0% | ~2% |
| Missing customers.city | 1.0% | ~1% |
| Khách vãng lai (NULL) | 30% | ~30% |
| Cardinality order_id (unique) | 200,000 | 200,000 |

## Streaming (real-time events)

| Chỉ số | Đo được | Mục tiêu |
| --- | --- | --- |
| Tổng events (gồm dup) | 507,500 | — |
| Bursty (giờ cao điểm) | 84% | cao (×burst_multiplier) |
| Late arrival (>5s) | 12% | ~12% |
| Out-of-order theo created_ts | 20% | có (do late) |
| Duplicates event_id | 1.5% | ~1.5% |
| Event ẩn danh (customer NULL) | 40% | ~40% |
