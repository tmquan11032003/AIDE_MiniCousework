"""
Feast feature definitions for the coffee-chain customer features.

Offline store = local Parquet exported from Gold `feat_customer_90d` (on MinIO);
online store = SQLite. Run from this directory:

    feast apply
    feast materialize <start> <end>
"""

from datetime import timedelta

from feast import Entity, FeatureView, Field, FileSource
from feast.types import Float64, Int64

# Entity: a loyalty customer (join key = customer_id).
customer = Entity(name="customer", join_keys=["customer_id"])

# Source: Parquet with event_timestamp (point-in-time) + created_timestamp.
source = FileSource(
    name="feat_customer_90d_source",
    path="data/feat_customer_90d.parquet",
    timestamp_field="event_timestamp",
    created_timestamp_column="created_timestamp",
)

# Feature view: 90-day customer stats.
customer_90d_stats = FeatureView(
    name="customer_90d_stats",
    entities=[customer],
    ttl=timedelta(days=365),
    schema=[
        Field(name="f_total_orders_90d", dtype=Int64),
        Field(name="f_avg_order_value_90d", dtype=Float64),
        Field(name="f_distinct_categories_90d", dtype=Int64),
    ],
    source=source,
    online=True,
)
