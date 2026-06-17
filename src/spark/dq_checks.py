"""
Data-quality checks + Section 02 demos (run after gold.py):

    docker exec spark-iceberg spark-submit /workspace/src/spark/dq_checks.py

Checks: uniqueness, referential integrity, null keys, amount reconciliation.
Demos: schema evolution (channel NULL pre-app), Iceberg time-travel, point-in-time feature.
"""

from pyspark.sql import SparkSession

G = "demo.gold"
S = "demo.silver"
B = "demo.bronze"


def main():
    spark = SparkSession.builder.appName("dq_checks").getOrCreate()

    def scalar(sql):
        return spark.sql(sql).collect()[0][0]

    def check(name, ok, detail=""):
        print(f"  [{'PASS' if ok else 'FAIL'}] {name} {detail}")

    print("== DATA QUALITY ==")
    # Uniqueness: fact_orders one row per order_id
    n = scalar(f"SELECT count(*) FROM {G}.fact_orders")
    d = scalar(f"SELECT count(DISTINCT order_id) FROM {G}.fact_orders")
    check("uniqueness fact_orders.order_id", n == d, f"({n:,} rows, {d:,} distinct)")

    # Referential: loyalty orders must map to a dim_customer.
    orphans = scalar(f"""
        SELECT count(*) FROM {G}.fact_orders f
        WHERE f.customer_key IS NULL AND EXISTS (
            SELECT 1 FROM {S}.stg_orders o
            WHERE o.order_id = f.order_id AND o.customer_id IS NOT NULL)
    """)
    check("referential fact_orders -> dim_customer", orphans == 0, f"({orphans} orphans)")

    # Null check: required keys
    nulls = scalar(
        f"SELECT count(*) FROM {G}.fact_orders "
        f"WHERE order_id IS NULL OR order_date_key IS NULL"
    )
    check("null required keys fact_orders", nulls == 0, f"({nulls} nulls)")

    # Reconciliation: sum(line_amount) ~= sum(order_net_amount)
    a = scalar(f"SELECT round(sum(line_amount),0) FROM {G}.fact_order_items")
    b = scalar(f"SELECT round(sum(order_net_amount),0) FROM {G}.fact_orders")
    ok = abs((a or 0) - (b or 0)) < 10
    check("amount reconciliation items vs orders", ok, f"(items={a:,.0f} orders={b:,.0f})")

    print("\n== SCHEMA EVOLUTION (channel only exists from app launch) ==")
    pre = scalar(f"SELECT count(*) FROM {G}.fact_orders WHERE channel IS NULL")
    post = scalar(f"SELECT count(*) FROM {G}.fact_orders WHERE channel IS NOT NULL")
    print(f"  channel NULL (pre-app) = {pre:,} | NOT NULL (post-app) = {post:,}")

    print("\n== ICEBERG TIME-TRAVEL (controlled: TIMESTAMP AS OF) ==")
    import time as _t
    spark.sql(f"CREATE OR REPLACE TABLE {G}._tt_demo USING iceberg AS SELECT * FROM {G}.dim_store")
    before = str(spark.sql("SELECT current_timestamp() AS ts").collect()[0]["ts"])
    _t.sleep(2)
    spark.sql(f"INSERT INTO {G}._tt_demo SELECT * FROM {G}.dim_store LIMIT 5")  # append 5
    now_n = scalar(f"SELECT count(*) FROM {G}._tt_demo")
    old_n = scalar(f"SELECT count(*) FROM {G}._tt_demo TIMESTAMP AS OF '{before}'")
    print(f"  rows BEFORE append (time-travel to {before[:19]}) = {old_n} | AFTER = {now_n}")
    spark.sql(f"DROP TABLE {G}._tt_demo")

    print("\n== POINT-IN-TIME FEATURE (feat_customer_90d has event_timestamp) ==")
    ref = scalar(f"SELECT max(event_timestamp) FROM {G}.feat_customer_90d")
    # A feature is only valid for labels at or after its event_timestamp (no future leakage).
    sample = spark.sql(f"""
        SELECT customer_id, event_timestamp, f_total_orders_90d,
               f_avg_order_value_90d, f_distinct_categories_90d
        FROM {G}.feat_customer_90d ORDER BY f_total_orders_90d DESC LIMIT 3
    """).collect()
    print(f"  feature snapshot event_timestamp = {ref}")
    for r in sample:
        print(f"   {r['customer_id']}  orders90d={r['f_total_orders_90d']} "
              f"aov={r['f_avg_order_value_90d']} cats={r['f_distinct_categories_90d']}")

    spark.stop()


if __name__ == "__main__":
    main()
