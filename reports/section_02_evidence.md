# Section 02 — Evidence (lakehouse Bronze → Silver → Gold)

Sinh bằng các Spark job trong `src/spark/` chạy trên stack Docker (MinIO + Iceberg REST + Spark).
Chạy lại: `bronze_load.py` → `silver.py` → `gold.py` → `dq_checks.py`.

## Row counts theo tầng

| Bronze (raw)    | rows    | Silver (stg)    | rows    | Gold                  | rows    |
| --------------- | ------- | --------------- | ------- | --------------------- | ------- |
| raw_stores      | 50      | stg_stores      | 50      | dim_date              | 180     |
| raw_products    | 300     | stg_products    | 300     | dim_customer          | 20,000  |
| raw_customers   | 20,000  | stg_customers   | 20,000  | dim_product           | 300     |
| raw_employees   | 400     | stg_employees   | 400     | dim_store             | 50      |
| raw_orders      | 200,000 | stg_orders      | 200,000 | dim_employee          | 400     |
| raw_order_items | 510,327 | stg_order_items | 500,321 | fact_orders           | 200,000 |
| raw_payments    | 209,579 | stg_payments    | 209,579 | fact_order_items      | 500,321 |
| raw_events      | 507,500 | stg_events      | 500,000 | obt_order_performance | 200,000 |
|                 |         |                 |         | feat_customer_90d     | 19,409  |

**Dedup ở Silver:** order_items 510,327 → 500,321 (bỏ ~2% dup); events 507,500 → 500,000 (bỏ 1.5% dup).

## Data-quality checks (dq_checks.py)

```
[PASS] uniqueness fact_orders.order_id (200,000 rows, 200,000 distinct)
[PASS] referential fact_orders -> dim_customer (0 orphans)
[PASS] null required keys fact_orders (0 nulls)
[PASS] amount reconciliation items vs orders (items=54,734,865 orders=54,734,865)
```

## Schema evolution (channel chỉ có từ khi ra app)

```
channel NULL (pre-app) = 100,293 | NOT NULL (post-app) = 99,707
```

Bronze `raw_orders` đọc bằng `mergeSchema` từ các file Parquet theo tháng; file cũ thiếu cột → NULL.

## Iceberg time-travel (TIMESTAMP AS OF)

```
rows BEFORE append (time-travel) = 50 | AFTER = 55
```

Append 5 dòng vào một bảng, query `TIMESTAMP AS OF <trước khi append>` vẫn thấy 50 dòng cũ.

## Point-in-time feature (feat_customer_90d)

Mỗi dòng feature có `event_timestamp` (snapshot 2025-06-29) để downstream (Feast/ML) join point-in-time
mà không rò rỉ tương lai.

```
C008678  orders90d=14 aov=320.7 cats=4
C018666  orders90d=13 aov=199.2 cats=2
C017653  orders90d=13 aov=335.6 cats=4
```
