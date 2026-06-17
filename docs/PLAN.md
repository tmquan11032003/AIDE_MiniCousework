# Plan: Hệ thống Data + AI end-to-end — Chuỗi quán cà phê (Lakehouse local)

> File plan sống (living document). Vai trò: Claude = senior Data Engineer góp ý; Bạn = người thực hiện.

## Context

Mini-coursework _Engineering for Data and AI_ (cá nhân, chạy local), domain **chuỗi quán cà phê kiểu
Starbucks**. Mục tiêu học: dựng một **lakehouse end-to-end** sát production với cả **batch + streaming**.

**Thay đổi scope:** nâng từ stack nhẹ (Polars+DuckDB thuần) lên **lakehouse trên Docker**:
**Kafka + Flink + Spark + MinIO + Apache Iceberg** (+ Trino optional). Generator dùng **pandas** (đơn
giản, dễ học) + **DuckDB** (dev/test/serving nhanh). Bổ sung 3 lớp để full end-to-end + đủ Section 02:
**Airflow** (orchestration), **Feast** (feature store), **DataHub** (catalog/lineage).

**Ràng buộc thực tế:** máy 8GB RAM cho Docker + mạng chậm (kéo image lâu) → **phân pha**, không bật tất cả
cùng lúc, pin image tag để tái lập.

## Quyết định đã chốt

| Hạng mục            | Chốt                                             | Ghi chú                                                           |
| ------------------- | ------------------------------------------------ | ----------------------------------------------------------------- |
| Lộ trình            | **Phân pha** (core trước, mở rộng dần)           | Tránh quá tải 8GB                                                 |
| Stream engine chính | **Apache Flink**                                 | Học event-time windowing thật                                     |
| Table format        | **Apache Iceberg** + REST Catalog                | Mượt nhất với Flink/Spark/Trino (Delta + Flink kém mature)        |
| Batch engine        | **Spark** (local mode)                           | Silver/Gold ETL                                                   |
| Object storage      | **MinIO** (S3-compatible)                        | Lưu mọi layer                                                     |
| Serving/query       | **DuckDB** (dev) + **Trino** (optional, Phase C) | DuckDB đọc thẳng Iceberg/Parquet trên MinIO                       |
| Generator           | **pandas + pyarrow** (function thuần, comment)   | Người mới học — dễ đọc/trình bày hơn class+Polars                 |
| Môi trường Python   | **pip + venv** (`requirements.txt`)              | Conda quá chậm trên mạng máy này                                  |
| Orchestration       | **Airflow** LocalExecutor + Postgres             | ~2GB, bật thường trực; điều phối Spark/Flink + Feast              |
| Feature store       | **Feast** (offline feat\_\*, online SQLite)      | ~0 RAM; `get_historical_features` point-in-time (ASOF)            |
| Catalog/lineage     | **DataHub** — compose profile riêng (toggle)     | Nặng ~8GB → bật tách phiên, tắt Spark/Flink trước; giữ Docker 8GB |

## 🔄 Sơ đồ dòng data hoàn chỉnh (end-to-end)

```
┌──────────────────────── SOURCE (Python/pandas — Section 01, M1/M2) ───────────────────────┐
│  Offline batch  : stores, products, customers, employees, orders, order_items, payments    │
│                   → Parquet (seed=42, có skew/dup/schema-evolution)                         │
│  Streaming      : event generator (app_view, add_to_cart, mobile_order, checkout, ...)      │
│                   → NDJSON (event_timestamp vs created_ts, late/out-of-order/burst)         │
└───────────────┬───────────────────────────────────────────────┬───────────────────────────┘
                │ reference Parquet (batch)                       │ events (NDJSON)
                │                                                 v
                │                                          ┌─────────────┐
                │                                          │   KAFKA     │  topic: coffee.events
                │                                          │  (KRaft)    │  (Python producer publish)
                │                                          └──────┬──────┘
                │                                                 │ consume (event-time)
                │                                                 v
                │                                          ┌─────────────┐
                │                                          │   FLINK     │  parse · validate · watermark
                │                                          │ (streaming) │  dedup(event_id) · late handling
                │                                          └──────┬──────┘
                │  Spark batch ingest                             │ Iceberg sink
                v                                                 v
        ┌───────────────────────────────────────────────────────────────────────┐
        │                MinIO (S3)  ·  Apache Iceberg tables                     │
        │   s3a://lakehouse/                          ↑ Iceberg REST Catalog       │
        │     bronze/  raw_*      ← Flink (stream) + Spark (batch reference)       │
        │     silver/  stg_*      ← Spark: dedup, cast, chuẩn hóa                  │
        │     gold/    dim_/fact_/obt_/feat_   ← Spark: model BI + feature         │
        └───────────────┬───────────────────────────────────────┬───────────────┘
                        │ query                                   │ query
                        v                                         v
                  ┌──────────┐                              ┌──────────┐
                  │  DuckDB  │  dev/test/CI, đọc Iceberg     │  TRINO   │  serving/BI (Phase C, optional)
                  │          │  trên MinIO qua httpfs/S3     │          │  ASOF/point-in-time demo
                  └──────────┘                              └──────────┘

Ghi chú vận hành (8GB): KHÔNG bật Spark + Flink đồng thời — Flink nạp Bronze (streaming) trước,
sau đó chạy Spark batch (Silver/Gold). Kafka KRaft (no ZooKeeper). Trino coordinator-only khi cần.
```

## Cấu trúc thư mục (bổ sung lớp hạ tầng)

```
AIDE_Minicoursework/
├── README.md
├── requirements.txt  pyproject.toml  setup.cfg   # Python env (pip+venv) + lint
├── config/generator.yaml             # seed + tham số sinh + tỉ lệ lỗi
├── docs/
│   ├── PLAN.md  01_data_generator.md  02_schema_design.md
│   └── reference/                     # đề bài + sample_design (ví dụ)
├── src/
│   ├── generators/  offline.py  stream.py   # pandas generator (Section 01)
│   ├── pipelines/                    # Spark bronze/silver/gold (Section 02)
│   ├── streaming/  producer.py       # Kafka producer (M4)
│   ├── utils/  config.py  quality.py
│   └── run.py                        # CLI
├── docker/                           # compose lakehouse + profiles (core/stream/orchestration/datahub)
├── airflow/  dags/  Dockerfile       # orchestration (M7) — DAG điều phối Spark/Flink/Feast
├── feast/  feature_repo/             # feature store (M8) — offline feat_*, online SQLite
├── datahub/  recipes/                # catalog/lineage (M9) — ingest Iceberg (profile riêng)
├── tests/
├── data/                             # offline Parquet, streaming NDJSON (gitignored)
└── reports/                          # quality_report.md (evidence)
```

## Mô hình dữ liệu (Section 01 — giữ nguyên)

7 bảng offline (stores, products, customers, employees, orders, order_items, payments) quy mô **Vừa**
(~50 stores / 300 products / 20k customers / 180 ngày / ~200k orders / ~500k events). Streaming: 1 topic
hợp nhất theo `event_type`. Challenge: skew, high-cardinality, schema evolution, duplicates, late,
out-of-order, burst, missing. Chi tiết grain/cột chốt khi vào generator.

---

## Milestones (theo kiến trúc lakehouse)

### Mini-coursework phase (Section 01 + 02 — bắt buộc nộp)

**M0 — Scaffolding & môi trường** ✅ **(XONG)** — pip+venv, `src/` skeleton, CLI, smoke tests pass.

**M1 — Section 01: Offline generator (pandas → Parquet)** ✅ **(XONG)**
Sinh 7 bảng + chèn challenge offline (skew, cardinality, schema evolution, duplicates). Reproducible.

**M2 — Section 01: Streaming generator (NDJSON) + design 01** ✅ **(XONG)**
Event generator (event-time vs ingest-time, late/out-of-order/burst/dup). Viết `01_data_generator.md`

- `reports/quality_report.md`.

**M3 — Section 02 (infra): Lakehouse skeleton trên Docker** ✅ **(XONG)**
`docker/`: MinIO + mc + Iceberg REST Catalog + Spark (lean; Kafka+Flink thêm ở M4). Image **pin digest**,
healthcheck, volumes bind vào `/home/mq-ubuntu/data`. Smoke test PASS: Spark ghi/đọc bảng Iceberg trên
MinIO **và** DuckDB đọc lại. (Fix pull IPv6: tắt IPv6 → IPv4.)

**M4 — Section 02 (streaming): Kafka + Flink → Bronze Iceberg** ✅ **(XONG)**
`src/streaming/producer.py` (confluent_kafka) đẩy NDJSON → Kafka; Flink SQL job
(`src/flink/bronze_ingest.sql`, image `docker/flink/`) consume → `bronze.raw_events` (Iceberg) với
watermark event-time. **Bronze append-only (raw, giữ dup); dedup chuyển sang Silver (M5)** — đúng medallion.
Đã verify: 507,500 events → Bronze (exactly-once), 7,500 dup (1.5%) giữ nguyên; 3 mốc thời gian
(event_timestamp / created_ts / ingest_ts); Spark + DuckDB đọc lại được (cross-engine).

**M5 — Section 02 (batch): Spark Silver/Gold + design 02** ✅ **(XONG)**
Spark jobs (`src/spark/`): `bronze_load.py` (7 Parquet → Bronze, orders mergeSchema) → `silver.py`
(dedup order_items/events + clean) → `gold.py` (5 dim + 2 fact + OBT + feat_customer_90d) → `dq_checks.py`.
DQ tất cả PASS (uniqueness/referential/null/reconciliation khớp 54,734,865). Demo: schema evolution,
**Iceberg time-travel** (TIMESTAMP AS OF 50→55), point-in-time feature. Viết [02_schema_design.md](02_schema_design.md)

- [evidence](../reports/section_02_evidence.md).

**M6 — Section 02 (serving + evidence): DuckDB** ✅ **(XONG)**
`src/serving/duckdb_serving.py`: DuckDB đọc Gold (Iceberg/Parquet trên MinIO) — BI queries (doanh thu
theo region/store, channel mix) + **point-in-time feature lookup**. Evidence: [reports/section_02_evidence.md](../reports/section_02_evidence.md).
Trino để optional (DuckDB đã đủ serving). **Kết thúc Section 02 core / mini-phase data.**

**M7 — Section 02 (orchestration): Airflow** ✅ **(XONG)** (`airflow/`, LocalExecutor + Postgres, profile `orchestration`)
DAG `batch_pipeline` điều phối Spark `bronze_load → silver → gold → dq_checks` qua `docker exec spark-submit`
(Airflow image có docker CLI + mount host socket, `group_add: 984`). _Done:_ DAG trigger → tất cả task
**success** tuần tự, Gold dựng lại (fact_orders 200k). Compose profiles core/stream/orchestration để bật-tắt RAM.

**M8 — Section 02 (feature store): Feast** (`feast/feature_repo/`)
Offline đọc `feat_*` (Parquet/Iceberg trên MinIO), online SQLite, registry file. `get_historical_features`
point-in-time; `materialize` qua Airflow. _Done:_ training df point-in-time đúng (feature_ts ≤ label_ts).

**M9 — Section 02 (lineage): DataHub** (`datahub/`, compose profile riêng — toggle)
Bật DataHub (tắt Spark/Flink trước), ingest Iceberg recipe (+Spark/Airflow lineage nếu kịp) → UI hiện
catalog + lineage graph; screenshot evidence; tắt. **Kết thúc Section 02 / mini-phase.**

### Final phase (sau)

**M10 — Flink nâng cao (Phase B):** event-time windowing thật (doanh thu real-time theo store), stateful
join order↔payment, streaming feature → `feat_*`.
**M11 — Section 03:** generator drift + `ml_customer_label`/`..._training` + drift report (PSI) + monitoring.
**M12 — Section 04:** chọn 1 AI track (ML hoặc LLM). Trino federated demo (Phase C) nếu còn tài nguyên.

---

## Ngân sách RAM (ước tính, single-node)

MinIO ~256MB · Kafka KRaft ~512MB · Iceberg REST ~256MB · Flink (JM+1 TM) ~1.5GB · Spark local ~1.5GB
· Trino coord ~1.5GB · Airflow (web+sched+PG) ~2GB · Feast ~0 (lib) · **DataHub ~8GB (14 container)**.
**Không chạy Spark+Flink+Trino cùng lúc.** Core+Airflow ≈ 4-5GB (vừa 8GB). **DataHub chạy tách phiên** —
bật riêng (tắt Spark/Flink), ingest lineage xong thì tắt. Dùng `docker compose --profile <p> up` để bật-tắt.

## Verification

- **Infra (M3):** `docker compose up` khỏe; Spark ghi + DuckDB đọc cùng 1 bảng Iceberg trên MinIO.
- **Streaming (M4):** số event vào Kafka = số row Bronze (sau dedup); kiểm event-time vs created_ts.
- **Batch (M5):** uniqueness/referential/null trên Gold; Iceberg time-travel trả đúng snapshot cũ.
- **Reproducibility:** generator seed=42 chạy 2 lần ra y hệt; image tag pinned; `docker compose up` 1 lệnh.

## Còn để ngỏ

- Grain/cột chính xác từng bảng (chốt ở M1).
- Iceberg REST backend (sqlite vs postgres) — chọn nhẹ nhất ở M3.
- Có dùng PyFlink (Python) hay Flink SQL cho job streaming — chốt ở M4 (ưu tiên Flink SQL cho gọn).
- Repo docker-compose nền tham khảo: `tabular-io/docker-spark-iceberg` (Spark+Iceberg REST+MinIO) rồi thêm Kafka+Flink.
