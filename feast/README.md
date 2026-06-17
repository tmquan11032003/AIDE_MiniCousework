# Feast — Feature Store (M8)

Feature store cho `feat_customer_90d`: offline = Parquet (export từ Gold trên MinIO),
online = SQLite, registry = file. Point-in-time join chống rò rỉ tương lai.

Cài Feast vào **venv riêng** (tránh xung đột deps với generator env):

```bash
python -m venv .venv-feast
.venv-feast/bin/pip install -r requirements-feast.txt
```

Chạy (cần stack core đang chạy để export từ MinIO):

```bash
# 1) export Gold feat_customer_90d -> feast/feature_repo/data/*.parquet
.venv/bin/python -m src.serving.export_features

# 2) đăng ký feature + demo (chạy trong feature_repo/)
cd feast/feature_repo
../../.venv-feast/bin/feast apply
../../.venv-feast/bin/python demo.py     # historical (point-in-time) + materialize + online
```

- `feature_repo/definitions.py` — Entity `customer`, FeatureView `customer_90d_stats` (3 features).
- `feature_repo/feature_store.yaml` — provider local, offline=file, online=sqlite.
- Point-in-time: label trước feature snapshot (2025-06-29) bị loại → no leakage.
- Materialize đẩy feature mới nhất vào online store để serving (`get_online_features`).
