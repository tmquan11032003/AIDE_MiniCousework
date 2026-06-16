# Lakehouse hạ tầng (Docker) — Section 02

Stack local cho lakehouse. **M3 (hiện tại):** MinIO + Iceberg REST catalog + Spark.
**M4 (sau):** thêm Kafka + Flink cho streaming.

| Service         | Vai trò                           | Cổng                            |
| --------------- | --------------------------------- | ------------------------------- |
| `minio`         | Object storage S3 (lưu mọi layer) | 9000 (API), 9001 (console)      |
| `mc`            | Khởi tạo bucket `warehouse`       | —                               |
| `rest`          | Iceberg REST catalog (metadata)   | 8181                            |
| `spark-iceberg` | Spark + Iceberg (batch ETL)       | 8080 (Spark UI), 8888 (Jupyter) |

Service names (`spark-iceberg`, `rest`, `minio`) khớp với `spark-defaults` có sẵn trong image
`tabulario/spark-iceberg` (catalog `demo` → `http://rest:8181`, S3 → `http://minio:9000`).

## Cách dùng (chạy từ thư mục gốc project)

```bash
# kéo image (lần đầu, lâu vì image lớn)
docker compose --env-file docker/.env -f docker/docker-compose.yml pull

# bật stack
docker compose --env-file docker/.env -f docker/docker-compose.yml up -d

# smoke test: Spark ghi 1 bảng Iceberg lên MinIO rồi đọc lại
bash docker/smoke_test.sh

# mở Spark SQL tương tác
docker compose --env-file docker/.env -f docker/docker-compose.yml exec spark-iceberg spark-sql

# tắt stack (giữ dữ liệu) / xoá sạch
docker compose --env-file docker/.env -f docker/docker-compose.yml down
docker compose --env-file docker/.env -f docker/docker-compose.yml down -v   # xoá cả volume

# MinIO console: http://localhost:9001  (user/pass trong docker/.env)
```

## Ghi chú

- Credentials (`admin`/`password`) chỉ dùng local, không phải secret thật.
- Image đã **pin theo digest** trong `docker/.env` để tái lập.
- Project được mount vào `/workspace` trong container `spark-iceberg` để Spark đọc `data/`.

### Troubleshooting: `docker pull` bị `read: connection timed out` (IPv6)

Nếu pull image treo/đứt giữa chừng do IPv6 của máy hỏng, tắt IPv6 tạm thời rồi pull lại:

```bash
sudo sysctl -w net.ipv6.conf.all.disable_ipv6=1
sudo sysctl -w net.ipv6.conf.default.disable_ipv6=1
docker compose --env-file docker/.env -f docker/docker-compose.yml pull
# bật lại sau khi xong (tuỳ chọn): đổi =1 thành =0
```

## Lưu trữ (volumes)

Dữ liệu bền của container lưu ở **`${HOST_DATA_DIR}`** (mặc định `/home/mq-ubuntu/data/coffee-lakehouse`,
trên partition `/home` rộng — KHÔNG đổ vào `/`). Đổi đường dẫn này trong `docker/.env` nếu cần.

```
/home/mq-ubuntu/data/coffee-lakehouse/
├── minio/   # MinIO object storage (Parquet/Iceberg của mọi layer)
├── kafka/   # (M4) Kafka logs
└── flink/   # (M4) Flink checkpoints/state
```

`down` giữ nguyên thư mục này; `down -v` chỉ xoá named volume của Docker, KHÔNG xoá bind mount —
muốn xoá sạch data thì xoá thủ công thư mục trên.
