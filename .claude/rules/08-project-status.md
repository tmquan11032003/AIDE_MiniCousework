# Rule: Trạng thái hiện tại

- **Domain đã chốt:** chuỗi quán cà phê (coffee shop chain, kiểu Starbucks) — nhiều cửa hàng, mobile order, loyalty, giờ cao điểm.
- **Kiến trúc đã chốt:** lakehouse local trên Docker — **Kafka + Flink (stream) + Spark (batch) + MinIO + Apache Iceberg** (+ Trino optional). Giữ **Polars** (generator) + **DuckDB** (dev/serving). Xem [PLAN.md](../../PLAN.md) (có sơ đồ dòng data + milestone M0–M9).
- **Môi trường:** pip + venv (`.venv/`, pin trong `requirements.txt`). _Conda không tải nổi repodata trên mạng máy này → pip+venv._
- **Ngôn ngữ tài liệu:** tiếng Việt.
- **Phase:** mini-coursework. **M0 (scaffolding) xong**. Tiếp theo: **M1 — offline batch generator (Polars → Parquet)**.
- Cập nhật file này khi tiến độ thay đổi (generator chạy được, hạ tầng dựng xong, sang milestone mới...).
