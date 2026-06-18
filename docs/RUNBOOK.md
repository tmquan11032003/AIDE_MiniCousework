# RUNBOOK — Chạy thử toàn bộ M1 → M8

Hướng dẫn chạy lại cả hệ thống để quan sát hoạt động. Chạy lệnh từ **thư mục gốc** project.

> **Thứ tự phụ thuộc:** M1/M2 (sinh data) → M3 (hạ tầng) → M4 (streaming Bronze) → M5 (batch Silver/Gold)
> → M6 (serving) → M7 (orchestration) → M8 (feature store).
> **RAM 8GB:** đừng bật `stream` + `orchestration` cùng lúc nếu máy yếu — chạy theo pha.

## 0. Chuẩn bị môi trường (một lần)

```bash
cd ~/Downloads/AIDE_Minicoursework
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# Gõ tắt lệnh docker compose cho gọn (dùng suốt runbook):
alias dc='docker compose --env-file docker/.env -f docker/docker-compose.yml'
```

> Nếu `docker pull` bị treo do IPv6: `sudo sysctl -w net.ipv6.conf.all.disable_ipv6=1` rồi pull lại.

---

## M1 — Offline generator (pandas → Parquet)

```bash
python -m src.run offline
```

**Xem gì:** `ls data/offline/` (7 bảng Parquet, orders là thư mục theo tháng) ·
`cat reports/quality_report.md` (tỉ lệ skew/dup/schema-evolution khớp config).

## M2 — Streaming generator (NDJSON)

```bash
python -m src.run stream         # hoặc: python -m src.run all  (cả offline + stream)
head -2 data/streaming/events.ndjson
pytest tests/ -q                 # 16 test: determinism + schema + tỉ lệ challenge
```

**Xem gì:** mỗi dòng là 1 event JSON có `event_timestamp` vs `created_ts`.

---

## M3 — Hạ tầng lakehouse (MinIO + Iceberg REST + Spark)

```bash
dc pull                          # lần đầu (image lớn, lâu)
dc up -d                         # bật core (minio, mc, rest, spark-iceberg)
bash docker/smoke_test.sh        # Spark ghi/đọc 1 bảng Iceberg trên MinIO
```

**Xem gì:** smoke test in `n_rows=3` + danh sách file trên `s3://warehouse`.
**UI:** MinIO console http://localhost:9001 (user `admin` / pass `password`).

---

## M4 — Streaming: Kafka + Flink → Bronze Iceberg

```bash
dc --profile stream up -d                 # thêm kafka + flink
dc build flink-jobmanager                 # nếu chưa build image flink

# tạo topic
docker exec kafka /opt/kafka/bin/kafka-topics.sh --bootstrap-server localhost:9092 \
  --create --if-not-exists --topic coffee.events --partitions 3 --replication-factor 1

# submit Flink job (Kafka -> bronze.raw_events, append-only, event-time watermark)
docker cp src/flink/bronze_ingest.sql flink-jobmanager:/tmp/bronze_ingest.sql
docker exec flink-jobmanager /opt/flink/bin/sql-client.sh -f /tmp/bronze_ingest.sql

# đẩy events vào Kafka
python -m src.streaming.producer           # toàn bộ; hoặc --limit 1000 / --rate 500

# đếm Bronze (đọc đúng bảng Iceberg)
docker exec spark-iceberg spark-sql -e "SELECT count(*) FROM demo.bronze.raw_events;"
```

**Xem gì:** count Bronze = số events đã đẩy (exactly-once). **Flink UI:** http://localhost:8081.

---

## M5 — Batch: Spark Bronze → Silver → Gold

```bash
docker exec spark-iceberg spark-submit /workspace/src/spark/bronze_load.py   # 7 Parquet -> Bronze
docker exec spark-iceberg spark-submit /workspace/src/spark/silver.py        # dedup + clean
docker exec spark-iceberg spark-submit /workspace/src/spark/gold.py          # dim/fact/obt/feat
docker exec spark-iceberg spark-submit /workspace/src/spark/dq_checks.py     # DQ + demos
```

**Xem gì:** `dq_checks` in `[PASS]` cho uniqueness/referential/null/reconciliation, schema evolution,
Iceberg time-travel (50→55), point-in-time feature.

## M6 — Serving: DuckDB query Gold

```bash
python -m src.serving.duckdb_serving
```

**Xem gì:** doanh thu theo region (South áp đảo = skew), channel mix (pre-app NULL = schema evolution),
top stores, point-in-time feature lookup.

---

## M7 — Orchestration: Airflow

```bash
dc --profile orchestration build airflow   # lần đầu (image lớn)
dc --profile orchestration up -d
sleep 150                                   # đợi airflow khởi tạo DB (~2-3 phút)

docker exec airflow airflow dags unpause batch_pipeline
docker exec airflow airflow dags trigger batch_pipeline
watch -n 10 "docker exec airflow airflow dags list-runs -d batch_pipeline | head"
```

**Xem gì:** DAG `batch_pipeline` chạy bronze→silver→gold→dq tuần tự, state `success`.
**UI:** http://localhost:8082 (admin/admin) — xem graph + log từng task.

---

## M8 — Feature store: Feast

```bash
# venv riêng cho Feast (tránh xung đột deps)
python -m venv .venv-feast && .venv-feast/bin/pip install -r requirements-feast.txt

python -m src.serving.export_features       # Gold feat_customer_90d -> Parquet

cd feast/feature_repo
../../.venv-feast/bin/feast apply
../../.venv-feast/bin/python demo.py         # point-in-time + materialize + online
cd ../..
```

**Xem gì:** `get_historical_features` (3 vào → 2 ra, label sớm bị loại = no leakage) +
`get_online_features` (C008678 → 14 orders).

---

## Tắt / dọn

```bash
dc --profile stream --profile orchestration down   # tắt tất cả, GIỮ data (volume trên /home)
# dc ... down -v                                   # xoá cả named volume (bind mount vẫn còn)
```

## Cổng dịch vụ

| UI            | URL                   | Đăng nhập        |
| ------------- | --------------------- | ---------------- |
| MinIO console | http://localhost:9001 | admin / password |
| Flink         | http://localhost:8081 | —                |
| Spark         | http://localhost:8080 | —                |
| Airflow       | http://localhost:8082 | admin / admin    |

## Bằng chứng tổng hợp

- `reports/quality_report.md` — challenges Section 01.
- `reports/section_02_evidence.md` — Bronze/Silver/Gold counts, DQ, time-travel, serving, Airflow, Feast.
- Tài liệu thiết kế: `docs/01_data_generator.md`, `docs/02_schema_design.md`, `docs/PLAN.md`.
