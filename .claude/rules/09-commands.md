# Rule: Commands (setup / run / test)

Stack: Python + Polars + DuckDB. Môi trường: **pip + venv** (`.venv/`, pin trong `requirements.txt`).

> Ghi chú: ban đầu định dùng conda nhưng conda không tải nổi repodata trên mạng máy này → chuyển sang pip+venv (cài ~55s).

## Environment / setup

```bash
python -m venv .venv
source .venv/bin/activate            # Linux/macOS
pip install -r requirements.txt
```

## Run

```bash
python -m src.run --help             # xem các lệnh
python -m src.run offline            # sinh dữ liệu offline (Parquet) — M1
python -m src.run stream             # sinh dữ liệu streaming (NDJSON) — M2
python -m src.run all                # sinh cả hai
python -m src.run all --config config/generator.yaml
```

## Test

```bash
python -m pytest tests/ -q           # chạy toàn bộ test
python -m pytest tests/test_smoke.py::test_config_loads_with_seed   # một test đơn lẻ
```

## Lint / format

_(chưa thiết lập linter; prettier tự chạy qua hook PostToolUse cho file được sửa)_
