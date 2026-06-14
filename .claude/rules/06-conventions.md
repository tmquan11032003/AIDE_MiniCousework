# Rule: Quy ước (naming, reproducibility, storage)

- **Naming layer:** Bronze = `raw_`, Silver = `stg_`, Gold = `dim_`/`fact_`/`obt_`/`feat_`. Schema Gold ví dụ: `gold_<domain>`.
- **Surrogate vs business key:** `_key` (SK do warehouse sinh) vs `_id` (BK tự nhiên).
- **Reproducible:** luôn dùng seed cố định (ví dụ `random_seed: 42`); tham số generator để trong file config (YAML).
- **Dedup keys:** offline theo business key (vd order_id/product_id); streaming theo `event_id` + `created_ts` (giữ row mới nhất).
- **Lakehouse cho Bronze/Silver:** ưu tiên định dạng tiết kiệm chi phí (vd Delta/Parquet trên object/local storage). Offline output thường Parquet; streaming output JSON/Avro.
- File design viết bằng tiếng Việt hoặc tiếng Anh đều được — **bám theo lựa chọn của người dùng**, không tự đổi.
