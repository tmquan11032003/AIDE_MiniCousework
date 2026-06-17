"""
Feast demo: point-in-time historical features + materialize + online serving.
Run from this directory with the feast venv:

    ../../.venv-feast/bin/python demo.py
"""

from datetime import datetime

import pandas as pd
from feast import FeatureStore

FEATURES = [
    "customer_90d_stats:f_total_orders_90d",
    "customer_90d_stats:f_avg_order_value_90d",
    "customer_90d_stats:f_distinct_categories_90d",
]


def main():
    store = FeatureStore(repo_path=".")

    # 1) Point-in-time historical features. Feature snapshot is 2025-06-29.
    #    A label AT/AFTER that date sees the feature; a label BEFORE does not
    #    (no future leakage) -> Feast drops that row.
    entity_df = pd.DataFrame({
        "customer_id": ["C008678", "C018666", "C008678"],
        "event_timestamp": [
            pd.Timestamp("2025-09-01"),  # valid -> feature present
            pd.Timestamp("2025-09-01"),  # valid -> feature present
            pd.Timestamp("2025-05-01"),  # BEFORE feature snapshot -> excluded
        ],
    })
    hist = store.get_historical_features(entity_df=entity_df, features=FEATURES).to_df()
    print("== get_historical_features (point-in-time) ==")
    print(f"  entity_df rows in = {len(entity_df)} | rows out = {len(hist)} "
          f"(label 2025-05-01 bị loại vì feature 2025-06-29 ở tương lai -> no leakage)")
    print(hist.to_string(index=False))

    # 2) Materialize the latest features into the online store (SQLite).
    store.materialize(start_date=datetime(2025, 1, 1), end_date=datetime(2026, 1, 1))

    # 3) Online serving: fetch the latest features for a customer.
    online = store.get_online_features(
        features=FEATURES, entity_rows=[{"customer_id": "C008678"}]
    ).to_dict()
    print("\n== get_online_features (serving) ==")
    print({k: v[0] for k, v in online.items()})


if __name__ == "__main__":
    main()
