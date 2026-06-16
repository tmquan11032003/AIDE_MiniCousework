# Rule: Trạng thái hiện tại

- **Domain đã chốt:** chuỗi quán cà phê (coffee shop chain, kiểu Starbucks) — nhiều cửa hàng, mobile order, loyalty, giờ cao điểm.
- **Kiến trúc đã chốt:** lakehouse local trên Docker — **Kafka + Flink (stream) + Spark (batch) + MinIO + Apache Iceberg** (+ Trino optional). Generator **pandas** + **DuckDB** (dev/serving). Xem [PLAN.md](../../docs/PLAN.md) (có sơ đồ dòng data + milestone M0–M9).
- **Môi trường:** pip + venv (`.venv/`, pin trong `requirements.txt`). _Conda không tải nổi repodata trên mạng máy này → pip+venv._
- **Ngôn ngữ tài liệu:** tiếng Việt.
- **Phase:** mini-coursework. **M0 + M1 + M2 xong** (Section 01 hoàn tất):
  - M1 offline generator (`src/generators/offline.py`) — 7 bảng Parquet, seed=42.
  - M2 streaming generator (`src/generators/stream.py`) — NDJSON events, seed=43, challenge bursty/late/out-of-order/duplicate.
  - Tài liệu [01_data_generator.md](../../docs/01_data_generator.md); quality report (offline+streaming); **16 test pass**.
  - Code style đơn giản: pandas + function thuần, comment tiếng Anh, đánh dấu `# CHALLENGE`.
- **M3 (đang làm) — hạ tầng lakehouse Docker** (lean: MinIO + Iceberg REST + Spark; Kafka+Flink để M4):
  - Đã viết `docker/` (compose, .env, README, smoke_test.sh). Chạy lệnh từ thư mục gốc.
  - Image: **minio + mc đã pull xong**; **spark-iceberg + rest CHƯA pull** — bị chặn do **IPv6 hỏng** (timeout tới CloudFront) và đang dùng **4G dung lượng hạn chế**. Layer 127MB của spark tải tới ~126MB rồi đứt.
  - **Việc cần làm khi có mạng tốt/không giới hạn:** `docker compose --env-file docker/.env -f docker/docker-compose.yml pull` → `up -d` → `bash docker/smoke_test.sh`. (Cân nhắc tắt IPv6 cho Docker nếu vẫn timeout.)
  - ⚠️ `docker/docker-compose.yml` hiện **bị hỏng cú pháp** (biến `${SPARK_ICEBERG_I}` cắt cụt + mất khối `depends_on`) — cần sửa trước khi `up`.
- **Generator lib:** pandas + pyarrow (đã bỏ Polars/mimesis). Style: thủ tục, comment nhiều.
- Cập nhật file này khi tiến độ thay đổi (generator chạy được, hạ tầng dựng xong, sang milestone mới...).
