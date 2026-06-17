"""
Bronze load (batch): read the 7 reference Parquet tables and write them as
Iceberg tables under demo.bronze. Run inside the spark-iceberg container:

    docker exec spark-iceberg spark-submit /workspace/src/spark/bronze_load.py

Note: bronze.raw_events is produced separately by the Flink streaming job (M4).
The orders dataset has per-month files where pre-app months lack the
channel / membership_tier_at_order columns -> read with mergeSchema (schema evolution).
"""

from pyspark.sql import SparkSession

CATALOG = "demo"
DATA = "/workspace/data/offline"


def main():
    spark = SparkSession.builder.appName("bronze_load").getOrCreate()
    spark.sql(f"CREATE DATABASE IF NOT EXISTS {CATALOG}.bronze")

    # Simple one-file tables.
    tables = {
        "raw_stores": "stores.parquet",
        "raw_products": "products.parquet",
        "raw_customers": "customers.parquet",
        "raw_employees": "employees.parquet",
        "raw_order_items": "order_items.parquet",
        "raw_payments": "payments.parquet",
    }
    for name, fname in tables.items():
        df = spark.read.parquet(f"{DATA}/{fname}")
        df.writeTo(f"{CATALOG}.bronze.{name}").using("iceberg").createOrReplace()
        print(f"  bronze.{name}: {df.count():,} rows")

    # orders: monthly files, schema evolution -> mergeSchema fills missing columns with NULL.
    orders = spark.read.option("mergeSchema", "true").parquet(f"{DATA}/orders/")
    orders.writeTo(f"{CATALOG}.bronze.raw_orders").using("iceberg").createOrReplace()
    print(f"  bronze.raw_orders: {orders.count():,} rows (mergeSchema)")

    spark.stop()


if __name__ == "__main__":
    main()
