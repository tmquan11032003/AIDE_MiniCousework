# WALKTHROUGH — Giải thích chi tiết từng bước (M1 → M8)

Tài liệu này giải thích: **lệnh nào → chạy file nào → bên trong làm gì → vì sao → ra cái gì**.
Mở kèm file code được trỏ tới để vừa đọc vừa hiểu. (Chạy lệnh thực tế: xem [RUNBOOK.md](RUNBOOK.md).)

---

## M1 — Offline generator

### Lệnh

```bash
python -m src.run offline
```

### Chạy file nào?

`python -m src.run` = chạy **`src/run.py`** như một module (nhờ `src/__init__.py` biến `src` thành package).
Python tìm khối `if __name__ == "__main__":` ở cuối `run.py` → gọi `main()`.

### Bên trong làm gì? (trace)

1. **`src/run.py` → `build_parser()`**: dùng `argparse` định nghĩa 3 lệnh con `offline` / `stream` / `all`
   và tham số `--config` (mặc định `config/generator.yaml`). Vì vậy `offline` được nhận là `args.command`.
2. **`main()`** gọi `load_config(args.config)` (ở **`src/utils/config.py`**) — đọc file YAML, kiểm tra bắt
   buộc có `random_seed`. Trả về `cfg` (dict).
3. Vì `command == "offline"`, `main()` `import` rồi gọi **`src/generators/offline.py` → `run(cfg)`**.
4. Trong `offline.py`:
   - **`build_all(cfg)`**: dòng đầu `np.random.seed(cfg["random_seed"])` → **cố định ngẫu nhiên** (đây là
     chỗ làm cho mọi lần chạy giống nhau). Sau đó gọi lần lượt `gen_stores`, `gen_products`,
     `gen_customers`, `gen_employees`, `gen_orders`, `gen_order_items`, `gen_payments` — mỗi hàm trả về
     một `pandas.DataFrame`. Thứ tự quan trọng vì `gen_orders` cần `stores/customers/employees`, v.v.
   - Mỗi hàm `gen_*` là nơi **chèn thách thức dữ liệu** — tìm comment `# CHALLENGE` trong file:
     `gen_orders` có skew cửa hàng/giờ cao điểm + schema evolution (channel NULL trước ngày ra app);
     `gen_order_items` nhân bản ~2% dòng (duplicates).
   - **`write_all(tables, cfg)`**: ghi mỗi bảng ra Parquet. Riêng `orders` gọi `write_orders_by_month` →
     ghi **mỗi tháng 1 file**, tháng trước ngày ra app **bỏ 2 cột** → đó chính là _schema evolution_.
   - **`write_offline_report`** (ở **`src/utils/quality.py`**):
     tính lại các tỉ lệ và ghi `reports/quality_report.md`.

### Vì sao?

Tách "sinh dữ liệu" thành các hàm thuần để dễ đọc; seed cố định để **tái lập**; chèn lỗi có chủ đích để
tầng sau (Silver) phải xử lý — đúng tinh thần đề bài.

### Ra cái gì?

`data/offline/*.parquet` (+ `data/offline/orders/orders_YYYY-MM.parquet`) và `reports/quality_report.md`.
**Kiểm chứng:** `cat reports/quality_report.md` — các con số khớp `config/generator.yaml`.

---

## M2 — Streaming generator

### Lệnh

```bash
python -m src.run stream
```

### Chạy file nào? Bên trong?

`run.py` → `command == "stream"` → gọi **`src/generators/stream.py` → `run(cfg)`**.

1. **`build_all(cfg)`**: `np.random.seed(cfg["random_seed"] + 1)` (seed khác offline để luồng độc lập).
2. **`gen_events(cfg)`**: sinh ~507k event. Tìm `# CHALLENGE`:
   - **bursty**: trọng số giờ cao điểm `burst_multiplier` → lưu lượng dồn cục.
   - **late arrival**: `created_ts = event_timestamp + delay`, ~12% delay lớn.
   - **duplicates**: nhân bản ~1.5% event (cùng `event_id`).
   - Ghi theo thứ tự `created_ts` (thứ tự ingest) → tự nhiên có _out-of-order_ theo event time.
3. **`write_ndjson`**: ghi `data/streaming/events.ndjson` — mỗi dòng 1 JSON.
4. **`write_stream_report`**: nối phần "Streaming" vào `reports/quality_report.md`.

### Kiểm tra logic bằng test

```bash
pytest tests/ -q
```

Chạy **`tests/test_offline.py`** + **`tests/test_stream.py`** + **`tests/test_smoke.py`**: kiểm
_determinism_ (sinh 2 lần giống nhau), schema, và tỉ lệ challenge.

---

## M3 — Hạ tầng lakehouse (Docker)

### Lệnh

```bash
dc up -d            # dc = docker compose --env-file docker/.env -f docker/docker-compose.yml
bash docker/smoke_test.sh
```

### Chạy file nào? Bên trong?

- **`dc up -d`** đọc **`docker/docker-compose.yml`** + **`docker/.env`** (image tag + creds + `HOST_DATA_DIR`).
  Bật 4 container (service không có `profiles` = luôn bật):
  - `minio` (S3 storage), `mc` (tạo bucket `warehouse`), `rest` (Iceberg REST catalog), `spark-iceberg`
    (Spark + Iceberg). Tên service cố định để khớp `spark-defaults` có sẵn trong image
    (catalog `demo` → `rest:8181`, S3 → `minio:9000`).
- **`bash docker/smoke_test.sh`**: chạy `docker exec spark-iceberg spark-sql -e "..."` tạo 1 bảng Iceberg
  nhỏ, insert 3 dòng, đọc lại; rồi `mc ls` liệt kê file trên `s3://warehouse`.

### Vì sao?

Đây là "kho" của lakehouse: dữ liệu mọi tầng (Bronze/Silver/Gold) là bảng Iceberg nằm trên MinIO; REST
catalog giữ metadata để Spark/Flink/DuckDB cùng đọc một bảng.

---

## M4 — Streaming: Kafka + Flink → Bronze

### Lệnh (rút gọn)

```bash
dc --profile stream up -d
docker cp src/flink/bronze_ingest.sql flink-jobmanager:/tmp/bronze_ingest.sql
docker exec flink-jobmanager /opt/flink/bin/sql-client.sh -f /tmp/bronze_ingest.sql
python -m src.streaming.producer
```

### Chạy file nào? Bên trong?

1. **`dc --profile stream up -d`**: bật thêm `kafka` + `flink-jobmanager` + `flink-taskmanager` (các service
   có `profiles: ["stream"]`). Image Flink build từ **`docker/flink/Dockerfile`** (Flink + jar
   Iceberg/Kafka/S3/Hadoop — đây là lý do cần build lần đầu bằng `dc build flink-jobmanager`).
2. **Flink job = `src/flink/bronze_ingest.sql`** (chạy bằng `sql-client.sh -f`). Đọc file đó sẽ thấy 3 phần:
   - `CREATE TEMPORARY TABLE kafka_events (...) WITH ('connector'='kafka', ...)` — bảng nguồn đọc topic
     `coffee.events`, có `WATERMARK FOR event_timestamp` (event-time).
   - `CREATE CATALOG iceberg WITH ('catalog-impl'='...RESTCatalog', ...)` + `CREATE TABLE bronze.raw_events`.
   - `INSERT INTO iceberg.bronze.raw_events SELECT ... FROM kafka_events` — **append-only**, thêm
     `ingest_ts = CURRENT_TIMESTAMP`. Đây là job streaming chạy liên tục, commit vào Iceberg mỗi checkpoint.
3. **Producer = `src/streaming/producer.py`** (`python -m src.streaming.producer`): mở
   `data/streaming/events.ndjson`, mỗi dòng `producer.produce(topic, key=event_id, value=line)` bằng
   thư viện `confluent_kafka`. Đẩy event vào Kafka để Flink consume.

### Kiểm chứng

```bash
docker exec spark-iceberg spark-sql -e "SELECT count(*) FROM demo.bronze.raw_events;"
```

Số dòng = số event đã đẩy (exactly-once). 3 mốc thời gian khác nhau: `event_timestamp` (lúc xảy ra) <
`created_ts` (generator ingest) < `ingest_ts` (Flink ghi).

---

## M5 — Batch: Spark Bronze → Silver → Gold

### Lệnh

```bash
docker exec spark-iceberg spark-submit /workspace/src/spark/bronze_load.py
docker exec spark-iceberg spark-submit /workspace/src/spark/silver.py
docker exec spark-iceberg spark-submit /workspace/src/spark/gold.py
docker exec spark-iceberg spark-submit /workspace/src/spark/dq_checks.py
```

> `/workspace` chính là thư mục project (mount vào container), nên `/workspace/src/spark/...` = `src/spark/...`.

### Bên trong từng file

- **`src/spark/bronze_load.py`**: `spark.read.parquet(...)` 7 bảng → `df.writeTo("demo.bronze.raw_*").using("iceberg").createOrReplace()`.
  Riêng `orders` đọc `option("mergeSchema","true")` để gộp các file tháng có schema khác nhau (schema evolution).
- **`src/spark/silver.py`**: làm sạch + **dedup**. `raw_order_items.dropDuplicates(["order_item_id"])` bỏ
  ~2% trùng; `raw_events.dropDuplicates(["event_id"])` bỏ 1.5% trùng (chỉ chạy nếu `raw_events` tồn tại →
  batch độc lập với streaming). `fillna({"city":"unknown"})` cho missing.
- **`src/spark/gold.py`**: `spark.sql("CREATE OR REPLACE TABLE ... USING iceberg AS SELECT ...")` dựng
  **dim** (SK = `row_number() OVER (ORDER BY <BK>)`), **fact** (join dim + tính measures), **OBT**
  (denormalized 1 dòng/đơn), **feat_customer_90d** (gắn `event_timestamp` để point-in-time).
- **`src/spark/dq_checks.py`**: chạy các câu SQL kiểm tra in `[PASS]/[FAIL]` (uniqueness, referential,
  null, reconciliation) + demo schema evolution, **Iceberg time-travel** (`TIMESTAMP AS OF`), point-in-time.

### Vì sao chia 3 tầng?

Medallion: **Bronze** giữ raw (cả lỗi) → **Silver** làm sạch/dedup → **Gold** mô hình hoá cho BI/ML. Mỗi
tầng là bảng Iceberg riêng → truy vết được, chạy lại idempotent.

---

## M6 — Serving: DuckDB

### Lệnh & file

```bash
python -m src.serving.duckdb_serving
```

**`src/serving/duckdb_serving.py`**: `INSTALL/LOAD httpfs` → `CREATE SECRET` trỏ MinIO (localhost:9000) →
`CREATE VIEW` từ `read_parquet('s3://warehouse/gold/obt_order_performance/data/*.parquet')` → chạy vài
câu BI (doanh thu theo region, channel mix, top store) + **point-in-time** trên `feat_customer_90d`.
DuckDB là engine nhẹ chạy ngay trên máy, đọc thẳng file Parquet trên MinIO — tiện cho dev/BI.

---

## M7 — Orchestration: Airflow

### Lệnh & file

```bash
dc --profile orchestration up -d
docker exec airflow airflow dags trigger batch_pipeline
```

- Service `airflow` build từ **`airflow/Dockerfile`** (Airflow + docker CLI). Mount host `docker.sock` +
  `group_add: 984` để **gọi `docker exec` sang container Spark**.
- DAG = **`airflow/dags/dag_batch_pipeline.py`**: 4 `BashOperator`, mỗi cái chạy
  `docker exec spark-iceberg spark-submit /workspace/src/spark/<job>.py`. Dòng cuối
  `bronze >> silver >> gold >> dq` định nghĩa **thứ tự phụ thuộc**.
- Khi `trigger`, Airflow scheduler (LocalExecutor) chạy lần lượt các task; mỗi task gọi đúng job Spark ở M5.

### Vì sao?

Thay vì gõ tay 4 lệnh spark-submit, Airflow điều phối tự động + có lịch + retry + UI theo dõi
(http://localhost:8082). Đây là "nhạc trưởng" của pipeline.

---

## M8 — Feature store: Feast

### Lệnh & file

```bash
python -m src.serving.export_features
cd feast/feature_repo
../../.venv-feast/bin/feast apply
../../.venv-feast/bin/python demo.py
```

1. **`src/serving/export_features.py`**: DuckDB đọc `gold.feat_customer_90d` trên MinIO → ghi
   `feast/feature_repo/data/feat_customer_90d.parquet` (dedup theo customer*id). Đây là \_offline store* của Feast.
2. **`feast apply`** đọc **`feast/feature_repo/definitions.py`** (Entity `customer`, `FileSource` trỏ parquet
   với `timestamp_field=event_timestamp`, `FeatureView customer_90d_stats` gồm 3 feature) + cấu hình
   **`feature_store.yaml`** (offline=file, online=sqlite) → tạo registry + bảng online.
3. **`demo.py`**:
   - `get_historical_features(entity_df, features)` — _point-in-time join_: với mỗi dòng (customer + thời
     điểm label), chỉ lấy feature có `event_timestamp <= label` (label trước feature snapshot bị loại →
     **không rò rỉ tương lai**).
   - `materialize(...)` đẩy feature mới nhất vào online SQLite.
   - `get_online_features(...)` lấy feature tức thời cho serving.

### Vì sao venv riêng?

Feast kén version `pandas/pyarrow`; cài chung sẽ phá môi trường generator → để trong **`.venv-feast`**
(xem `requirements-feast.txt`).

---

## Bản đồ nhanh: lệnh → file

| Lệnh                                   | File thực thi                                       |
| -------------------------------------- | --------------------------------------------------- |
| `python -m src.run offline/stream`     | `src/run.py` → `src/generators/{offline,stream}.py` |
| `bash docker/smoke_test.sh`            | `docker/smoke_test.sh` (+ compose)                  |
| Flink job                              | `src/flink/bronze_ingest.sql`                       |
| `python -m src.streaming.producer`     | `src/streaming/producer.py`                         |
| `spark-submit .../bronze_load.py` ...  | `src/spark/{bronze_load,silver,gold,dq_checks}.py`  |
| `python -m src.serving.duckdb_serving` | `src/serving/duckdb_serving.py`                     |
| DAG `batch_pipeline`                   | `airflow/dags/dag_batch_pipeline.py`                |
| `feast apply` / `demo.py`              | `feast/feature_repo/{definitions.py,demo.py}`       |
