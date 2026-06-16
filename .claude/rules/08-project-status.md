# Rule: Trạng thái hiện tại

- **Domain đã chốt:** chuỗi quán cà phê (coffee shop chain, kiểu Starbucks) — nhiều cửa hàng, mobile order, loyalty, giờ cao điểm.
- **Kiến trúc đã chốt:** lakehouse local trên Docker — **Kafka + Flink (stream) + Spark (batch) + MinIO + Apache Iceberg** (+ Trino optional). Giữ **Polars** (generator) + **DuckDB** (dev/serving). Xem [PLAN.md](../../PLAN.md) (có sơ đồ dòng data + milestone M0–M9).
- **Môi trường:** pip + venv (`.venv/`, pin trong `requirements.txt`). _Conda không tải nổi repodata trên mạng máy này → pip+venv._
- **Ngôn ngữ tài liệu:** tiếng Việt.
- **Phase:** mini-coursework. **M0 + M1 + M2 xong** (Section 01 hoàn tất):
  - M1 offline generator (`src/generate_offline.py`) — 7 bảng Parquet, seed=42.
  - M2 streaming generator (`src/generate_stream.py`) — NDJSON events, seed=43, challenge bursty/late/out-of-order/duplicate.
  - Tài liệu [01_data_generator.md](../../01_data_generator.md); quality report (offline+streaming); **16 test pass**.
  - Code style đơn giản: pandas + function thuần, comment tiếng Anh, đánh dấu `# CHALLENGE`.
  - Tiếp theo: **M3 — hạ tầng lakehouse Docker (MinIO + Iceberg REST + Kafka + Flink + Spark)**.
- **Generator lib:** pandas + pyarrow (đã bỏ Polars/mimesis). Style: thủ tục, comment nhiều.
- Cập nhật file này khi tiến độ thay đổi (generator chạy được, hạ tầng dựng xong, sang milestone mới...).
