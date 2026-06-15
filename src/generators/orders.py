"""Generator bảng `orders` (1 dòng / đơn).

Chèn các challenge:
- **Skew cửa hàng**: `top_store_share` đơn rơi vào `n_top_stores` cửa hàng đông khách.
- **Skew giờ cao điểm**: `peak_hour_share` đơn rơi vào `peak_hours` (giờ sáng).
- **Schema evolution**: đơn TRƯỚC `app_launch_date` không có `channel`/`membership_tier_at_order`
  (set NULL ở đây; lúc ghi Parquet tách file bỏ hẳn 2 cột — xem io.write_orders_schema_evolution).
- **event-time vs ingest-time**: `order_timestamp` (lúc đặt) vs `created_ts` (lúc ghi, trễ chút).
"""

from __future__ import annotations

import numpy as np
import polars as pl

from . import domain
from .base import BaseGenerator, make_ids, weighted_values


class OrdersGenerator(BaseGenerator):
    name = "orders"

    def __init__(self, config, rng, stores_df, customers_df, employees_df) -> None:
        super().__init__(config, rng)
        self.stores = stores_df
        self.customers = customers_df
        self.employees = employees_df

    def generate(self) -> pl.DataFrame:
        rng = self.rng
        vol = self.config["volume"]
        skew = self.config["skew"]
        hist = self.config["history"]
        n = vol["n_orders"]
        days = hist["days"]
        start_us = np.datetime64(hist["start_date"]).astype("datetime64[us]")
        launch = np.datetime64(hist["app_launch_date"]).astype("datetime64[D]")

        store_ids = self.stores["store_id"].to_numpy()
        n_top = skew["n_top_stores"]
        top_ids = rng.choice(store_ids, size=n_top, replace=False)
        other_ids = np.setdiff1d(store_ids, top_ids)

        # --- Skew cửa hàng ---
        store_arr = np.empty(n, dtype=object)
        is_top = rng.random(n) < skew["top_store_share"]
        store_arr[is_top] = rng.choice(top_ids, size=int(is_top.sum()))
        store_arr[~is_top] = rng.choice(other_ids, size=int((~is_top).sum()))

        # --- Thời gian: skew giờ cao điểm ---
        day = rng.integers(0, days, n)
        peak_hours = list(skew["peak_hours"])
        non_peak = [h for h in range(6, 23) if h not in peak_hours]
        is_peak = rng.random(n) < skew["peak_hour_share"]
        hour = np.where(
            is_peak,
            rng.choice(peak_hours, size=n),
            rng.choice(non_peak, size=n),
        )
        minute = rng.integers(0, 60, n)
        second = rng.integers(0, 60, n)
        total_s = (day * 86400 + hour * 3600 + minute * 60 + second).astype("int64")
        order_ts = start_us + (total_s * 1_000_000).astype("timedelta64[us]")
        order_date = order_ts.astype("datetime64[D]")

        # --- Khách loyalty (70%) vs vãng lai (30%) ---
        cust_ids = self.customers["customer_id"].to_numpy()
        cust_tiers = self.customers["membership_tier"].to_numpy()
        has_loy = rng.random(n) < 0.7
        cust_idx = rng.integers(0, len(cust_ids), n)
        customer_id = np.where(has_loy, cust_ids[cust_idx], None)
        tier_snapshot = np.where(has_loy, cust_tiers[cust_idx], None)

        # --- Nhân viên phục vụ: thuộc đúng cửa hàng ---
        emp_id = self.employees["employee_id"].to_numpy()
        emp_store = self.employees["store_id"].to_numpy()
        emp_by_store: dict[str, np.ndarray] = {}
        for s in store_ids:
            pool = emp_id[emp_store == s]
            emp_by_store[s] = pool if len(pool) else emp_id
        employee_arr = np.empty(n, dtype=object)
        for s in store_ids:
            idxs = np.where(store_arr == s)[0]
            if idxs.size:
                employee_arr[idxs] = rng.choice(emp_by_store[s], size=idxs.size)

        # --- Schema evolution: channel & tier chỉ có từ ngày ra app ---
        pre_app = order_date < launch
        channel = weighted_values(rng, domain.CHANNELS, n)
        channel[pre_app] = None
        membership = tier_snapshot.copy()
        membership[pre_app] = None

        status = weighted_values(rng, domain.ORDER_STATUSES, n)

        # --- ingest time trễ 0-300s so với event time ---
        ingest_lag = (rng.integers(0, 300, n) * 1_000_000).astype("timedelta64[us]")
        created_ts = order_ts + ingest_lag

        return pl.DataFrame(
            {
                "order_id": pl.Series(make_ids("O", n, 8), dtype=pl.String),
                "store_id": pl.Series(store_arr.tolist(), dtype=pl.String),
                "customer_id": pl.Series(customer_id.tolist(), dtype=pl.String),
                "employee_id": pl.Series(employee_arr.tolist(), dtype=pl.String),
                "order_timestamp": pl.Series(order_ts),
                "order_date": pl.Series(order_date).cast(pl.Date),
                "channel": pl.Series(channel.tolist(), dtype=pl.String),
                "membership_tier_at_order": pl.Series(
                    membership.tolist(), dtype=pl.String
                ),
                "status": pl.Series(status.tolist(), dtype=pl.String),
                "created_ts": pl.Series(created_ts),
            }
        )
