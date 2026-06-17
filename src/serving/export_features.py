"""
Export the Gold feature table (feat_customer_90d on MinIO) to a local Parquet file
that Feast uses as its file offline store.

    python -m src.serving.export_features

Needs the stack up (MinIO). Output: feast/feature_repo/data/feat_customer_90d.parquet
"""

import os

import duckdb

OUT = "feast/feature_repo/data/feat_customer_90d.parquet"


def main():
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    con = duckdb.connect()
    con.execute("INSTALL httpfs; LOAD httpfs;")
    con.execute(
        "CREATE SECRET minio (TYPE S3, KEY_ID 'admin', SECRET 'password', "
        "ENDPOINT 'localhost:9000', URL_STYLE 'path', USE_SSL false);"
    )
    # Dedup by customer_id: the raw parquet glob may include data files from older
    # Iceberg snapshots (orphaned until expire_snapshots), so keep one row per customer.
    con.execute(f"""
        COPY (
            SELECT customer_id,
                   CAST(event_timestamp AS TIMESTAMP) AS event_timestamp,
                   CAST(event_timestamp AS TIMESTAMP) AS created_timestamp,
                   f_total_orders_90d, f_avg_order_value_90d, f_distinct_categories_90d
            FROM (
                SELECT *, row_number() OVER (PARTITION BY customer_id) AS rn
                FROM read_parquet('s3://warehouse/gold/feat_customer_90d/data/*.parquet')
            ) WHERE rn = 1
        ) TO '{OUT}' (FORMAT PARQUET)
    """)
    n = con.execute(f"SELECT count(*) FROM read_parquet('{OUT}')").fetchone()[0]
    print(f"[export] {n:,} rows -> {OUT}")
    con.close()


if __name__ == "__main__":
    main()
