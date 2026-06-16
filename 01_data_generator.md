# Section 01 — Data Generator (Chuỗi quán cà phê)

Tài liệu thiết kế cho bộ sinh dữ liệu (offline + streaming) của hệ thống Data + AI mô phỏng một
**chuỗi quán cà phê** kiểu Starbucks. Mục tiêu: tạo nguồn dữ liệu **tái lập được** (reproducible) và
**có chủ đích chèn các thách thức dữ liệu thực tế** để downstream (Section 02 trở đi) phải xử lý.

- Code: [src/generate_offline.py](src/generate_offline.py) (batch), [src/generate_stream.py](src/generate_stream.py) (streaming).
- Cấu hình: [config/generator.yaml](config/generator.yaml) (mọi tham số + `random_seed`).
- Bằng chứng: [reports/quality_report.md](reports/quality_report.md) (sinh tự động).

## 1. Tổng quan domain

Một chuỗi quán cà phê gồm nhiều cửa hàng ở nhiều thành phố, bán đồ uống/đồ ăn/merch, có chương trình
khách hàng thân thiết (loyalty) và ứng dụng đặt hàng (mobile app ra mắt giữa kỳ). Generator sinh:

- **Offline (batch)**: dữ liệu lịch sử/tham chiếu, lưu **Parquet**.
- **Streaming (real-time)**: luồng sự kiện hành vi, lưu **NDJSON** (mỗi dòng một event).

Phân biệt 2 mốc thời gian dùng nhất quán toàn hệ thống:

- `event_timestamp` / `*_timestamp` — **event time**: thời điểm việc xảy ra.
- `created_ts` — **ingest time**: thời điểm bản ghi được ghi vào hệ thống (luôn ≥ event time).

## 2. Thiết kế dữ liệu Offline (7 bảng, Parquet)

| Bảng          | Grain            | Khóa & cột chính                                                                                                                         |
| ------------- | ---------------- | ---------------------------------------------------------------------------------------------------------------------------------------- |
| `stores`      | 1 / cửa hàng     | store_id (BK), store_name, city, region, store_type, open_date                                                                           |
| `products`    | 1 / món          | product_id (BK), product_name, category, base_price, has_size, is_active                                                                 |
| `customers`   | 1 / khách        | customer_id (BK), full_name, email (PII), city, membership_tier, marketing_opt_in, signup_ts                                             |
| `employees`   | 1 / nhân viên    | employee_id (BK), full_name, store_id, role, hire_date, is_active                                                                        |
| `orders`      | 1 / đơn          | order_id (BK), store_id, customer_id?, employee_id, order_timestamp, order_date, channel?, membership_tier_at_order?, status, created_ts |
| `order_items` | 1 / dòng món     | order_item_id (BK), order_id, product_id, size?, quantity, unit_price, discount_amount, line_amount, created_ts                          |
| `payments`    | 1 / lần trả tiền | payment_id (BK), order_id, payment_timestamp, payment_method, amount, payment_status, created_ts                                         |

**Quan hệ:** orders → stores/customers/employees; order_items → orders/products; payments → orders.
`customer_id` ở orders có thể NULL (khách vãng lai). `channel` và `membership_tier_at_order` chỉ tồn tại
từ ngày ra app.

### Thách thức chèn vào tầng offline

- **Skew**: ~75% đơn dồn vào 8 cửa hàng đông khách; ~70% sản phẩm thuộc `coffee`; ~55% đơn vào giờ cao
  điểm 7–9h sáng.
- **High cardinality**: order_id / order_item_id / customer_id gần như unique (1 dòng/khóa).
- **Schema evolution**: orders ghi **mỗi tháng một file Parquet**; các tháng **trước ngày ra app**
  (`app_launch_date`) **không có** cột `channel` và `membership_tier_at_order`. Đọc bằng DuckDB
  `union_by_name=true` (hoặc Spark) sẽ tự điền NULL cho phần dữ liệu cũ.
- **Duplicates**: ~2% dòng `order_items` bị nhân bản y hệt (cần dedup ở Silver).
- **Missing values**: ~1% NULL ở `customers.city` và `marketing_opt_in`.
- **event vs ingest time**: `created_ts = order_timestamp + 0..300s`.

## 3. Thiết kế dữ liệu Streaming (NDJSON)

Một topic sự kiện hợp nhất, phân biệt bằng `event_type` ∈
{`app_view`, `add_to_cart`, `mobile_order_placed`, `store_checkin`, `order_picked_up`, `payment_failed`}.

**Cột:** `event_id`, `event_type`, `event_timestamp`, `created_ts`, `customer_id?`, `store_id`,
`session_id`, `device_type` (app/web/kiosk), `channel`, `product_id?`, `order_id?`, `quantity?`, `price?`.
Các cột optional chỉ xuất hiện đúng loại event (vd `product_id` cho app_view/add_to_cart). Tham chiếu
id (store/customer/product/order) dùng **cùng id scheme** với offline để join được về sau.

### Thách thức chèn vào tầng streaming

- **Bursty traffic**: giờ trong cửa sổ cao điểm (`burst_windows`) được nhân trọng số ×`burst_multiplier`
  → lưu lượng dồn cục mạnh.
- **Late arrival**: ~12% event có `created_ts` trễ xa event time (delay trong `late_delay_seconds`),
  phần còn lại chỉ trễ vài giây.
- **Out-of-order**: file ghi theo thứ tự `created_ts` (thứ tự ingest) → `event_timestamp` không còn tăng
  đơn điệu (do late arrival). Không ép buộc, chỉ đo và báo cáo.
- **Duplicates**: ~1.5% event trùng (cùng `event_id`).

## 4. Cấu hình & tái lập (reproducibility)

Mọi tham số nằm trong [config/generator.yaml](config/generator.yaml): quy mô (`volume`), tỉ lệ skew,
tỉ lệ lỗi (`offline_issues`, `streaming`), mốc thời gian, và quan trọng nhất là `random_seed: 42`.

- Offline dùng seed `42`; streaming dùng seed `43` (để hai luồng độc lập) — cả hai cố định.
- Chạy lại generator cho ra **kết quả y hệt** (đã có test `test_deterministic`).

Quy mô mặc định (mức Vừa): ~50 stores · 300 products · 20k customers · 400 employees · 180 ngày ·
~200k orders · ~510k order_items · ~507k streaming events.

## 5. Cách chạy (local)

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

python -m src.run offline   # sinh 7 bảng Parquet -> data/offline/
python -m src.run stream    # sinh events.ndjson  -> data/streaming/
python -m src.run all       # cả hai
pytest tests/ -q            # 16 test (determinism, schema, tỉ lệ challenge)
```

Output: `data/offline/*.parquet` (orders là thư mục nhiều file theo tháng), `data/streaming/events.ndjson`,
và [reports/quality_report.md](reports/quality_report.md).

## 6. Bằng chứng (Quality Report)

Generator tự tính và ghi các chỉ số challenge vào `reports/quality_report.md`. Tóm tắt (đo được vs mục tiêu):

**Offline:** skew cửa hàng 75% (~75%), giờ cao điểm 55% (~55%), coffee 70% (~70%), schema evolution
(channel NULL) 50% (~50%), duplicates 2.0% (~2%), missing city 1.0% (~1%), khách vãng lai 30% (~30%).

**Streaming:** bursty 84% (cao do ×25), late arrival 12% (~12%), out-of-order 20% (do late),
duplicates 1.5% (~1.5%), event ẩn danh 40% (~40%).

## 7. Deliverables

1. Code generator có tham số hóa qua YAML, seed cố định.
2. Dữ liệu: Parquet (offline) + NDJSON (streaming).
3. Quality report (CSV/MD) đo các tỉ lệ challenge.
4. Bộ test kiểm determinism + schema + tỉ lệ challenge.

> Bước tiếp theo (Section 02): nạp dữ liệu này vào lakehouse (Kafka → Flink → MinIO/Iceberg → Spark),
> xử lý dedup/schema-evolution/late-arrival và xây Gold + feature. Xem [PLAN.md](PLAN.md).
