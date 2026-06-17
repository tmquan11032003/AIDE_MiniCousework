"""
Gold (batch): build the dimensional model + OBT + a feature table from Silver.

    docker exec spark-iceberg spark-submit /workspace/src/spark/gold.py

Tables (demo.gold):
  dim_date, dim_customer, dim_product, dim_store, dim_employee
  fact_orders, fact_order_items
  obt_order_performance  (denormalized, BI-friendly)
  feat_customer_90d      (per customer, with event_timestamp for point-in-time joins)

Convention: surrogate key <entity>_key (warehouse-generated) vs business key <entity>_id.
"""

from pyspark.sql import SparkSession

S = "demo.silver"
G = "demo.gold"


def main():
    spark = SparkSession.builder.appName("gold").getOrCreate()
    spark.sql(f"CREATE DATABASE IF NOT EXISTS {G}")

    # --- Dimensions (surrogate key via row_number over the business key) ---
    spark.sql(f"""
        CREATE OR REPLACE TABLE {G}.dim_date USING iceberg AS
        SELECT DISTINCT
            CAST(date_format(order_date, 'yyyyMMdd') AS INT) AS date_key,
            order_date AS calendar_date,
            year(order_date) AS year, month(order_date) AS month,
            day(order_date) AS day,
            date_format(order_date, 'EEEE') AS day_of_week,
            dayofweek(order_date) IN (1, 7) AS is_weekend
        FROM {S}.stg_orders WHERE order_date IS NOT NULL
    """)

    spark.sql(f"""
        CREATE OR REPLACE TABLE {G}.dim_customer USING iceberg AS
        SELECT row_number() OVER (ORDER BY customer_id) AS customer_key,
            customer_id, city, membership_tier, marketing_opt_in, signup_ts,
            concat(substr(email, 1, 2), '***@', split(email, '@')[1]) AS email_masked
        FROM {S}.stg_customers
    """)

    spark.sql(f"""
        CREATE OR REPLACE TABLE {G}.dim_product USING iceberg AS
        SELECT row_number() OVER (ORDER BY product_id) AS product_key,
            product_id, product_name, category, base_price, is_active
        FROM {S}.stg_products
    """)

    spark.sql(f"""
        CREATE OR REPLACE TABLE {G}.dim_store USING iceberg AS
        SELECT row_number() OVER (ORDER BY store_id) AS store_key,
            store_id, store_name, city, region, store_type
        FROM {S}.stg_stores
    """)

    spark.sql(f"""
        CREATE OR REPLACE TABLE {G}.dim_employee USING iceberg AS
        SELECT row_number() OVER (ORDER BY employee_id) AS employee_key,
            employee_id, role, store_id
        FROM {S}.stg_employees
    """)

    # --- Facts ---
    spark.sql(f"""
        CREATE OR REPLACE TABLE {G}.fact_orders USING iceberg AS
        SELECT o.order_id,
            c.customer_key, s.store_key, e.employee_key,
            CAST(date_format(o.order_date, 'yyyyMMdd') AS INT) AS order_date_key,
            o.status, o.channel, o.order_timestamp, o.created_ts,
            i.item_count, i.order_net_amount
        FROM {S}.stg_orders o
        LEFT JOIN (
            SELECT order_id, count(*) AS item_count,
                   round(sum(line_amount), 1) AS order_net_amount
            FROM {S}.stg_order_items GROUP BY order_id
        ) i ON o.order_id = i.order_id
        LEFT JOIN {G}.dim_customer c ON o.customer_id = c.customer_id
        LEFT JOIN {G}.dim_store s ON o.store_id = s.store_id
        LEFT JOIN {G}.dim_employee e ON o.employee_id = e.employee_id
    """)

    spark.sql(f"""
        CREATE OR REPLACE TABLE {G}.fact_order_items USING iceberg AS
        SELECT oi.order_item_id, oi.order_id, p.product_key,
            CAST(date_format(o.order_date, 'yyyyMMdd') AS INT) AS order_date_key,
            oi.size, oi.quantity, oi.unit_price, oi.discount_amount, oi.line_amount
        FROM {S}.stg_order_items oi
        JOIN {S}.stg_orders o ON oi.order_id = o.order_id
        LEFT JOIN {G}.dim_product p ON oi.product_id = p.product_id
    """)

    # --- OBT: denormalized one-row-per-order for BI ---
    spark.sql(f"""
        CREATE OR REPLACE TABLE {G}.obt_order_performance USING iceberg AS
        SELECT o.order_id, o.order_timestamp, o.order_date, o.channel, o.status,
            c.customer_id, c.city AS customer_city, c.membership_tier,
            s.store_id, s.city AS store_city, s.region,
            i.item_count, i.order_net_amount,
            pay.payment_status_last, pay.payment_method_last
        FROM {S}.stg_orders o
        LEFT JOIN (
            SELECT order_id, count(*) AS item_count,
                   round(sum(line_amount), 1) AS order_net_amount
            FROM {S}.stg_order_items GROUP BY order_id
        ) i ON o.order_id = i.order_id
        LEFT JOIN {S}.stg_customers c ON o.customer_id = c.customer_id
        LEFT JOIN {S}.stg_stores s ON o.store_id = s.store_id
        LEFT JOIN (
            SELECT order_id,
                   max_by(payment_status, payment_timestamp) AS payment_status_last,
                   max_by(payment_method, payment_timestamp) AS payment_method_last
            FROM {S}.stg_payments GROUP BY order_id
        ) pay ON o.order_id = pay.order_id
    """)

    # --- Feature table: 90-day customer features as of a reference snapshot ---
    # event_timestamp lets downstream (Feast) do point-in-time joins.
    ref = spark.sql(f"SELECT max(order_date) FROM {S}.stg_orders").collect()[0][0]
    spark.sql(f"""
        CREATE OR REPLACE TABLE {G}.feat_customer_90d USING iceberg AS
        SELECT o.customer_id,
            TIMESTAMP('{ref}') AS event_timestamp,
            count(DISTINCT o.order_id) AS f_total_orders_90d,
            round(avg(i.order_net_amount), 1) AS f_avg_order_value_90d,
            count(DISTINCT p.category) AS f_distinct_categories_90d
        FROM {S}.stg_orders o
        JOIN (
            SELECT order_id, sum(line_amount) AS order_net_amount
            FROM {S}.stg_order_items GROUP BY order_id
        ) i ON o.order_id = i.order_id
        JOIN {S}.stg_order_items oi ON o.order_id = oi.order_id
        JOIN {S}.stg_products p ON oi.product_id = p.product_id
        WHERE o.customer_id IS NOT NULL
          AND o.order_date > date_sub(DATE('{ref}'), 90)
        GROUP BY o.customer_id
    """)
    print(f"  feat_customer_90d reference snapshot = {ref}")

    spark.stop()


if __name__ == "__main__":
    main()
