# Rule: Trạng thái hiện tại

- **Domain đã chốt:** chuỗi quán cà phê (coffee shop chain, kiểu Starbucks) — nhiều cửa hàng, mobile order, loyalty, giờ cao điểm.
- **Kiến trúc đã chốt:** lakehouse local trên Docker — **Kafka + Flink (stream) + Spark (batch) + MinIO + Apache Iceberg** (+ Trino optional). Generator **pandas** + **DuckDB** (dev/serving). Bổ sung Section 02: **Airflow** (orchestration), **Feast** (feature store), **DataHub** (catalog/lineage — chạy tách phiên, profile riêng, giữ Docker 8GB). Xem [PLAN.md](../../docs/PLAN.md) (sơ đồ + milestone M0–M12; M7=Airflow, M8=Feast, M9=DataHub).
- **Môi trường:** pip + venv (`.venv/`, pin trong `requirements.txt`). _Conda không tải nổi repodata trên mạng máy này → pip+venv._
- **Ngôn ngữ tài liệu:** tiếng Việt.
- **Phase:** mini-coursework. **M0 + M1 + M2 xong** (Section 01 hoàn tất):
  - M1 offline generator (`src/generators/offline.py`) — 7 bảng Parquet, seed=42.
  - M2 streaming generator (`src/generators/stream.py`) — NDJSON events, seed=43, challenge bursty/late/out-of-order/duplicate.
  - Tài liệu [01_data_generator.md](../../docs/01_data_generator.md); quality report (offline+streaming); **16 test pass**.
  - Code style đơn giản: pandas + function thuần, comment tiếng Anh, đánh dấu `# CHALLENGE`.
- **M3 — hạ tầng lakehouse Docker ✅ XONG** (lean: MinIO + Iceberg REST + Spark; Kafka+Flink để M4):
  - `docker/` (compose + .env pin digest + README + smoke_test.sh). 4 service chạy OK.
  - Smoke test PASS: Spark tạo+ghi+đọc bảng Iceberg `coffee.smoke_test` trên MinIO; **DuckDB đọc lại** đúng dữ liệu.
  - Volumes bind vào `/home/mq-ubuntu/data/coffee-lakehouse/` (không đổ vào `/`).
  - Đã fix lỗi pull do **IPv6 hỏng**: `sudo sysctl -w net.ipv6.conf.all.disable_ipv6=1` rồi pull qua IPv4 (xem docker/README troubleshooting).
  - Tiếp theo: **M4 — Kafka + Flink → Bronze Iceberg**.
- **Generator lib:** pandas + pyarrow (đã bỏ Polars/mimesis). Style: thủ tục, comment nhiều.
- Cập nhật file này khi tiến độ thay đổi (generator chạy được, hạ tầng dựng xong, sang milestone mới...).
