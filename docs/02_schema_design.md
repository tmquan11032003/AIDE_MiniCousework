# Section 02 — Schema Design & Pipelines (Lakehouse)

Thiết kế + triển khai tầng lưu trữ và pipeline Bronze → Silver → Gold cho chuỗi quán cà phê, trên
**lakehouse local**: nguồn (Section 01) → Kafka/Flink (streaming) + Spark (batch) → **Apache Iceberg**
trên **MinIO (S3)**, catalog **Iceberg REST**, serving bằng **DuckDB**/Spark. Code: `src/spark/`,
`src/flink/`, `src/streaming/`, `docker/`. Bằng chứng số liệu: [reports/section_02_evidence.md](../reports/section_02_evidence.md).

## 1. Mục tiêu & quy ước

- **Mục tiêu:** Gold zone tin cậy, query nhanh cho BI + làm nền feature cho ML (Section 04).
- **Approach:** medallion Bronze(`raw_`) → Silver(`stg_`) → Gold(`dim_`/`fact_`/`obt_`/`feat_`).
- **Naming:** schema `bronze`/`silver`/`gold` trong catalog Iceberg `demo`. SK = `<entity>_key`
  (warehouse sinh), BK = `<entity>_id` (tự nhiên).
- **Storage (cost-focused):** Bronze/Silver/Gold đều là **Iceberg tables trên MinIO** (object storage),
  format Parquet — rẻ, mở, đọc được bằng Spark/Flink/Trino/DuckDB.

### Input profile (từ Section 01)

- Nguồn offline: `stores, products, customers, employees, orders, order_items, payments` (Parquet).
- Nguồn streaming: 1 topic `coffee.events` (NDJSON → Kafka).
- Volume: ~200k orders, ~510k order_items, ~507k events (≈ 0.94M rows/ lần sinh).
- Velocity: batch (offline 1 lần/ngày) + streaming (event real-time).
- Timestamp: `event_timestamp` (event time) vs `created_ts` (ingest từ generator) vs `ingest_ts` (pipeline ghi).
- Known issues (chèn ở 01): skew, high-cardinality, **schema evolution** (orders pre-app thiếu
  `channel`/`membership_tier_at_order`), **duplicates** (order_items ~2%, events ~1.5%), missing, late/out-of-order.

### Assumptions & SLA (điều chỉnh theo ràng buộc máy 8GB)

- Decision usage: Gold + feature phục vụ BI và training/scoring ML.
- SLA (mục tiêu, local): Bronze ingest ≤ 10’ ; Silver ≤ 30’ ; Gold/OBT ≤ 30’ ; feature ≤ 60’.
- Explainability/governance: ngoài scope phase này (trừ minimum: PII masking + lineage).

## 2. Dimension tables (`gold.dim_*`)

| Dimension      | Grain         | Keys & cột chính                                                                    |
| -------------- | ------------- | ----------------------------------------------------------------------------------- |
| `dim_date`     | 1 / ngày      | date_key (yyyymmdd), calendar_date, year, month, day, day_of_week, is_weekend       |
| `dim_customer` | 1 / khách     | customer_key (SK), customer_id (BK), city, membership_tier, signup_ts, email_masked |
| `dim_product`  | 1 / món       | product_key (SK), product_id (BK), product_name, category, base_price, is_active    |
| `dim_store`    | 1 / cửa hàng  | store_key (SK), store_id (BK), store_name, city, region, store_type                 |
| `dim_employee` | 1 / nhân viên | employee_key (SK), employee_id (BK), role, store_id                                 |

- **SK** sinh bằng `row_number() OVER (ORDER BY <BK>)` (ổn định, tái lập).
- **SCD:** hiện dùng SCD1 (overwrite) cho đơn giản; có thể nâng SCD2 (valid_from/valid_to/is_current) khi cần lịch sử.
- **PII:** `email` được mask ở Gold (`email_masked`), `full_name` không đưa vào Gold dim.

## 3. Fact tables (`gold.fact_*`)

- **`fact_orders`** — grain 1/đơn. Keys: customer_key, store_key, employee_key, order_date_key.
  Measures: item_count, order_net_amount (tổng line_amount). Giữ `channel` (NULL cho đơn pre-app —
  **schema evolution** chảy xuyên suốt).
- **`fact_order_items`** — grain 1/dòng món. Keys: product_key, order_date_key. Measures: quantity,
  unit_price, discount_amount, line_amount. **Dedup ở Silver** trước khi vào fact.

## 4. OBT — `gold.obt_order_performance`

Grain 1/đơn, denormalized cho BI: order + customer (city, tier) + store (city, region) + measures +
trạng thái thanh toán cuối (`payment_status_last`, `payment_method_last` qua `max_by`).

## 5. Refresh & Data Quality

- **Refresh:** dims daily; facts/OBT incremental (ở đây rebuild đơn giản bằng `createOrReplace`);
  feature 60’. Iceberg snapshot cho phép time-travel + rollback.
- **DQ checks** (`src/spark/dq_checks.py`, tất cả PASS): uniqueness (order_id), referential
  (fact→dim, 0 orphan), null required keys, **reconciliation** sum(line_amount)=sum(order_net_amount)
  (54,734,865 khớp tuyệt đối). Xem evidence.

## 6. Feature store — `gold.feat_customer_90d`

- Grain: 1/customer, kèm **`event_timestamp`** (snapshot tham chiếu) để **point-in-time join** (Feast,
  M8) không rò rỉ tương lai.
- Features: `f_total_orders_90d`, `f_avg_order_value_90d`, `f_distinct_categories_90d` (cửa sổ 90 ngày).
- Dedup/point-in-time: feature chỉ hợp lệ cho label có timestamp ≥ `event_timestamp`.

## 7. Pipeline design & triển khai

| Pipeline                  | Engine        | Code                          | Update strategy                                                |
| ------------------------- | ------------- | ----------------------------- | -------------------------------------------------------------- |
| Bronze streaming (events) | **Flink SQL** | `src/flink/bronze_ingest.sql` | append-only, watermark event-time, exactly-once qua checkpoint |
| Bronze batch (7 bảng)     | **Spark**     | `src/spark/bronze_load.py`    | `createOrReplace`; orders đọc `mergeSchema` (schema evolution) |
| Silver                    | **Spark**     | `src/spark/silver.py`         | dedup (order_items/events), clean (fill city), cast            |
| Gold (dim/fact/OBT/feat)  | **Spark**     | `src/spark/gold.py`           | rebuild bằng CTAS Iceberg                                      |

- **Bronze = raw append-only** (giữ cả duplicate); **dedup dồn về Silver** — đúng chuẩn medallion.
- **Controls/monitoring:** DQ gates (`dq_checks.py`); Iceberg commit metrics (Spark log) ghi số
  rows/files mỗi snapshot; Flink web UI (`:8081`) theo dõi throughput/checkpoint.
- **Recovery:** Iceberg time-travel + rollback snapshot; Flink checkpoint exactly-once; rerun idempotent
  (CTAS/createOrReplace).
- **Backfill:** local mặc định không backfill; nếu cần, rerun job (idempotent).
- **Lineage (M9):** DataHub ingest Iceberg + Spark/Airflow lineage (chạy tách phiên — xem PLAN).

## 8. Warehouse optimization

- **Format/layout:** Iceberg + Parquet trên MinIO; cân nhắc partition `fact_orders` theo `order_date_key`
  và sort theo `customer_key` khi dữ liệu lớn.
- **Query path:** DuckDB đọc trực tiếp Parquet/Iceberg trên MinIO cho dev nhanh; Spark cho ETL nặng.
- **Iceberg housekeeping:** `expire_snapshots`, `rewrite_data_files` (compaction) khi nhiều snapshot
  nhỏ (vd Bronze streaming sinh nhiều file mỗi checkpoint).
- _Trade-off:_ rebuild Gold bằng CTAS đơn giản nhưng tốn compute hơn incremental merge — chấp nhận cho
  quy mô coursework; nâng `MERGE INTO` khi cần.

## 9. Cách chạy (tóm tắt)

```bash
# stack: docker compose up -d (xem docker/README.md)
docker exec spark-iceberg spark-submit /workspace/src/spark/bronze_load.py
docker exec spark-iceberg spark-submit /workspace/src/spark/silver.py
docker exec spark-iceberg spark-submit /workspace/src/spark/gold.py
docker exec spark-iceberg spark-submit /workspace/src/spark/dq_checks.py
```

Streaming Bronze (events): xem [01_data_generator.md](01_data_generator.md) + `docker/README.md` (M4).
