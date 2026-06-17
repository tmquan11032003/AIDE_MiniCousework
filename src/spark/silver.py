"""
Silver (batch): clean + deduplicate Bronze into demo.silver.stg_* Iceberg tables.

    docker exec spark-iceberg spark-submit /workspace/src/spark/silver.py

Key cleaning steps:
  - stg_order_items : drop the ~2% exact duplicate rows (dedup by order_item_id).
  - stg_events      : drop the ~1.5% duplicate streaming events (dedup by event_id).
  - stg_customers   : fill missing city with 'unknown'.
  - dims            : pass through with light typing.
Orders keep channel / membership_tier_at_order NULL for pre-app months (schema evolution).
"""

from pyspark.sql import SparkSession
from pyspark.sql import functions as F

CATALOG = "demo"
B = f"{CATALOG}.bronze"
S = f"{CATALOG}.silver"


def save(df, name):
    df.writeTo(f"{S}.{name}").using("iceberg").createOrReplace()
    print(f"  silver.{name}: {df.count():,} rows")


def main():
    spark = SparkSession.builder.appName("silver").getOrCreate()
    spark.sql(f"CREATE DATABASE IF NOT EXISTS {S}")

    # Dimensions / reference: light clean.
    save(spark.read.table(f"{B}.raw_stores"), "stg_stores")
    save(spark.read.table(f"{B}.raw_products"), "stg_products")
    save(spark.read.table(f"{B}.raw_employees"), "stg_employees")
    save(
        spark.read.table(f"{B}.raw_customers").fillna({"city": "unknown"}),
        "stg_customers",
    )

    # Orders: keep schema-evolution NULLs; ensure order_date is a date.
    orders = spark.read.table(f"{B}.raw_orders").withColumn(
        "order_date", F.to_date("order_date")
    )
    save(orders, "stg_orders")

    # Order items: dedup exact duplicates by business key.
    save(
        spark.read.table(f"{B}.raw_order_items").dropDuplicates(["order_item_id"]),
        "stg_order_items",
    )

    save(spark.read.table(f"{B}.raw_payments"), "stg_payments")

    # Streaming events: dedup by event_id (keep one). Only if the streaming Bronze
    # table exists (produced by the Flink job, M4) -> batch pipeline stays independent.
    if spark.catalog.tableExists(f"{B}.raw_events"):
        save(spark.read.table(f"{B}.raw_events").dropDuplicates(["event_id"]), "stg_events")
    else:
        print("  skip stg_events (bronze.raw_events not found — run streaming path first)")

    spark.stop()


if __name__ == "__main__":
    main()
