# Plan: Hệ thống Data + AI end-to-end — Chuỗi quán cà phê (Lakehouse local)

> File plan sống (living document). Vai trò: Claude = senior Data Engineer góp ý; Bạn = người thực hiện.

## Context

Mini-coursework _Engineering for Data and AI_ (cá nhân, chạy local), domain **chuỗi quán cà phê kiểu
Starbucks**. Mục tiêu học: dựng một **lakehouse end-to-end** sát production với cả **batch + streaming**.

**Thay đổi scope:** nâng từ stack nhẹ (Polars+DuckDB thuần) lên **lakehouse trên Docker**:
**Kafka + Flink + Spark + MinIO + Apache Iceberg** (+ Trino optional). Generator dùng **pandas** (đơn
giản, dễ học) + **DuckDB** (dev/test/serving nhanh).

**Ràng buộc thực tế:** máy 8GB RAM cho Docker + mạng chậm (kéo image lâu) → **phân pha**, không bật tất cả
cùng lúc, pin image tag để tái lập.

## Quyết định đã chốt

| Hạng mục            | Chốt                                             | Ghi chú                                                    |
| ------------------- | ------------------------------------------------ | ---------------------------------------------------------- |
| Lộ trình            | **Phân pha** (core trước, mở rộng dần)           | Tránh quá tải 8GB                                          |
| Stream engine chính | **Apache Flink**                                 | Học event-time windowing thật                              |
| Table format        | **Apache Iceberg** + REST Catalog                | Mượt nhất với Flink/Spark/Trino (Delta + Flink kém mature) |
| Batch engine        | **Spark** (local mode)                           | Silver/Gold ETL                                            |
| Object storage      | **MinIO** (S3-compatible)                        | Lưu mọi layer                                              |
| Serving/query       | **DuckDB** (dev) + **Trino** (optional, Phase C) | DuckDB đọc thẳng Iceberg/Parquet trên MinIO                |
| Generator           | **pandas + pyarrow** (function thuần, comment)   | Người mới học — dễ đọc/trình bày hơn class+Polars          |
| Môi trường Python   | **pip + venv** (`requirements.txt`)              | Conda quá chậm trên mạng máy này                           |

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
├── requirements.txt                  # Python env (pip+venv): pandas, pyarrow, duckdb...
├── docker/
│   ├── docker-compose.yml            # MinIO + Iceberg REST + Kafka(KRaft) + Flink + Spark (+ Trino)
│   ├── .env                          # pin image tags + cấu hình RAM (heap opts)
│   └── conf/                         # cấu hình từng service (trino catalog, flink, spark-defaults)
├── config/generator.yaml             # seed + tham số sinh + tỉ lệ lỗi (đã có)
├── src/
│   ├── generate_offline.py           # pandas generator (Section 01) — function thuần
│   ├── streaming/producer.py         # đọc NDJSON → publish Kafka
│   ├── flink/                        # Flink jobs: bronze ingest, windowing
│   ├── spark/                        # Spark jobs: bronze(batch), silver, gold, features
│   ├── serving/                      # DuckDB/Trino query scripts
│   └── run.py                        # CLI (đã có)
├── data/ (offline Parquet, streaming NDJSON — gitignored)
├── reports/  · 01_data_generator.md · 02_schema_design.md · tests/
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

**M2 — Section 01: Streaming generator (NDJSON) + design 01**
Event generator (event-time vs ingest-time, late/out-of-order/burst/dup). Viết `01_data_generator.md`

- `reports/quality_report.md`.

**M3 — Section 02 (infra): Lakehouse skeleton trên Docker**
`docker/docker-compose.yml`: MinIO + Iceberg REST Catalog + Kafka(KRaft) + Flink + Spark. Pin image tag,
healthcheck, heap opts cho 8GB. _Done khi:_ `docker compose up` lên được; smoke test ghi/đọc 1 bảng
Iceberg nhỏ trên MinIO bằng Spark **và** đọc lại bằng DuckDB.

**M4 — Section 02 (streaming): Kafka + Flink → Bronze Iceberg**
`producer.py` đẩy NDJSON → Kafka; Flink job consume → `bronze/raw_events` (Iceberg) với watermark
event-time, dedup `event_id`, xử lý late arrival. _Done khi:_ event chảy tới Bronze, query đếm được bằng
DuckDB; chứng minh event-time vs ingest-time.

**M5 — Section 02 (batch): Spark Silver/Gold + design 02**
Spark batch: load reference Parquet → Bronze `raw_*`; Bronze → Silver (`stg_*`: dedup, clean) → Gold
(`dim_/fact_/obt_/feat_`). Demo **Iceberg schema evolution + time-travel**; point-in-time. Viết
`02_schema_design.md` (data contract, SLA, DQ checks, naming).

**M6 — Section 02 (serving + evidence): DuckDB (+Trino optional)**
Query Gold bằng DuckDB; (optional) bật Trino coordinator-only cho serving/BI + demo point-in-time.
DQ checks + run metadata + lineage/evidence. **Kết thúc mini-phase.**

### Final phase (sau)

**M7 — Flink nâng cao (Phase B):** event-time windowing thật (doanh thu real-time theo store), stateful
join order↔payment, streaming feature → `feat_*`.
**M8 — Section 03:** generator drift + `ml_customer_label`/`..._training` + drift report (PSI) + monitoring.
**M9 — Section 04:** chọn 1 AI track (ML hoặc LLM). Trino federated demo (Phase C) nếu còn tài nguyên.

---

## Ngân sách RAM (ước tính, single-node)

MinIO ~256MB · Kafka KRaft ~512MB · Iceberg REST ~256MB · Flink (JM+1 TM) ~1.5GB · Spark local ~1.5GB
· Trino coord ~1.5GB. **Không chạy Spark+Flink+Trino cùng lúc.** Core (MinIO+Kafka+REST+Flink) ≈ 2.5GB;
thêm Spark (tắt Flink) ≈ 2.3GB → vừa 8GB.

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
