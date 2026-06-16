# Coffee Chain — Data + AI Lakehouse (Mini-coursework)

Hệ thống **Data + AI end-to-end** mô phỏng một **chuỗi quán cà phê** (kiểu Starbucks), chạy local.
Bài tập môn _Engineering for Data and AI_. Có cả luồng **batch** và **streaming**, dựng dần thành một
**lakehouse** (Kafka → Flink → MinIO/Iceberg → Spark → DuckDB/Trino).

## Kiến trúc (tóm tắt)

```
Python generator ──> NDJSON/Parquet ──> Kafka ──> Flink ──> MinIO (Iceberg)
                                                    bronze ─> Spark ─> silver/gold ─> DuckDB / Trino
```

Chi tiết + sơ đồ dòng data đầy đủ + lộ trình milestone: xem **[docs/PLAN.md](docs/PLAN.md)**.

## Cấu trúc thư mục

```
config/        # generator.yaml (tham số sinh + random_seed)
docs/          # PLAN.md, tài liệu thiết kế từng section, reference/ (đề bài + ví dụ)
src/
  generators/  # offline.py (batch Parquet) + stream.py (streaming NDJSON)
  pipelines/   # Spark bronze/silver/gold (Section 02)
  streaming/   # Kafka producer (M4)
  utils/       # config.py, quality.py
  run.py       # CLI
docker/        # compose lakehouse (Section 02)
tests/         # pytest
data/          # output sinh ra (gitignored)
reports/       # quality_report.md (evidence)
```

## Cài đặt & chạy (local)

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

python -m src.run offline    # sinh 7 bảng Parquet  -> data/offline/
python -m src.run stream     # sinh events.ndjson   -> data/streaming/
python -m src.run all        # cả hai
pytest tests/ -q             # chạy test
```

Mọi thứ tái lập được nhờ seed cố định trong `config/generator.yaml`.

## Tiến độ

- ✅ **Section 01 (M0–M2)**: generator offline + streaming + tài liệu + 16 test.
  Xem [docs/01_data_generator.md](docs/01_data_generator.md).
- ⏳ **Section 02 (M3–M6)**: hạ tầng lakehouse + pipeline Bronze/Silver/Gold.

Stack: Python (pandas, pyarrow), DuckDB, Kafka, Flink, Spark, MinIO, Apache Iceberg, Docker.
