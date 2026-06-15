# Rule: Trạng thái hiện tại

- **Domain đã chốt:** chuỗi quán cà phê (coffee shop chain, kiểu Starbucks) — nhiều cửa hàng, mobile order, loyalty, giờ cao điểm.
- **Stack đã chốt:** Python + Polars (sinh/biến đổi) + DuckDB (query/serving) + Parquet (offline) / NDJSON (streaming). Chạy local thuần, không cần service ngoài.
- **Môi trường:** pip + venv (`.venv/`, pin trong `requirements.txt`). _Đã thử conda nhưng không tải nổi repodata trên mạng máy này → chuyển pip+venv._
- **Ngôn ngữ tài liệu:** tiếng Việt.
- **Phase:** mini-coursework. **M0 (scaffolding) xong** — cây thư mục `src/`, `config/generator.yaml`, CLI `src/run.py`, smoke tests pass. Tiếp theo: **M1 — offline batch generator**.
- Cập nhật file này khi tiến độ thay đổi (file đã tạo, generator chạy được, sang Section 02...).
