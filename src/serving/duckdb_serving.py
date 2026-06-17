"""
DuckDB serving layer: query the Gold tables (Iceberg/Parquet on MinIO) for BI,
plus a point-in-time feature lookup. Run on the host (needs the stack up):

    python -m src.serving.duckdb_serving

Reads Gold table data files directly from MinIO via httpfs (Gold is clean append-only,
so reading data Parquet matches the Iceberg table). DuckDB is the lightweight dev/serving
engine; Trino can replace it for multi-user BI (optional, Phase C).
"""

import duckdb

GOLD = "s3://warehouse/gold"


def connect():
    con = duckdb.connect()
    con.execute("INSTALL httpfs; LOAD httpfs;")
    con.execute(
        "CREATE SECRET minio (TYPE S3, KEY_ID 'admin', SECRET 'password', "
        "ENDPOINT 'localhost:9000', URL_STYLE 'path', USE_SSL false);"
    )
    for t in ("obt_order_performance", "feat_customer_90d"):
        con.execute(
            f"CREATE VIEW {t} AS "
            f"SELECT * FROM read_parquet('{GOLD}/{t}/data/*.parquet')"
        )
    return con


def show(title, rows, header):
    print(f"\n== {title} ==")
    print("  " + " | ".join(header))
    for r in rows:
        print("  " + " | ".join(str(x) for x in r))


def main():
    con = connect()

    show(
        "Doanh thu theo region (completed)",
        con.execute("""
            SELECT region, count(*) AS orders, round(sum(order_net_amount), 0) AS revenue
            FROM obt_order_performance WHERE status = 'completed'
            GROUP BY region ORDER BY revenue DESC
        """).fetchall(),
        ["region", "orders", "revenue"],
    )

    show(
        "Channel mix (NULL = đơn trước khi ra app — schema evolution)",
        con.execute("""
            SELECT coalesce(channel, '(pre-app)') AS channel, count(*) AS orders
            FROM obt_order_performance GROUP BY channel ORDER BY orders DESC
        """).fetchall(),
        ["channel", "orders"],
    )

    show(
        "Top 5 cửa hàng theo doanh thu",
        con.execute("""
            SELECT store_id, store_city, round(sum(order_net_amount), 0) AS revenue
            FROM obt_order_performance GROUP BY store_id, store_city
            ORDER BY revenue DESC LIMIT 5
        """).fetchall(),
        ["store_id", "city", "revenue"],
    )

    # Point-in-time feature serving: features valid only at/after their event_timestamp.
    label_time = "2025-09-01"
    show(
        f"Point-in-time feature lookup (as of label_time={label_time})",
        con.execute(f"""
            SELECT customer_id, event_timestamp, f_total_orders_90d, f_avg_order_value_90d
            FROM feat_customer_90d
            WHERE event_timestamp <= TIMESTAMP '{label_time}'
            ORDER BY f_total_orders_90d DESC LIMIT 3
        """).fetchall(),
        ["customer_id", "event_timestamp", "orders_90d", "aov_90d"],
    )

    con.close()


if __name__ == "__main__":
    main()
