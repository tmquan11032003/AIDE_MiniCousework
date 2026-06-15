"""Generator bảng `payments` (1 dòng / lần thanh toán).

- `amount` = tổng `line_amount` của đơn (tính từ order_items).
- ~5% đơn có 1 lần thanh toán THẤT BẠI trước khi thành công (2 dòng cho 1 order).
- Đơn `cancelled` -> thanh toán `failed`.
"""

from __future__ import annotations

import numpy as np
import polars as pl

from . import domain
from .base import BaseGenerator, weighted_values


class PaymentsGenerator(BaseGenerator):
    name = "payments"

    def __init__(self, config, rng, orders_df, items_df) -> None:
        super().__init__(config, rng)
        self.orders = orders_df
        self.items = items_df

    def generate(self) -> pl.DataFrame:
        rng = self.rng

        totals = self.items.group_by("order_id").agg(
            pl.col("line_amount").sum().round(1).alias("amount")
        )
        base = (
            self.orders.select("order_id", "order_timestamp", "status")
            .join(totals, on="order_id", how="left")
            .with_columns(pl.col("amount").fill_null(0.0))
        )

        order_ids = base["order_id"].to_numpy()
        order_ts = base["order_timestamp"].to_numpy()
        status = base["status"].to_numpy()
        amount = base["amount"].to_numpy()
        n = len(order_ids)

        method = weighted_values(rng, domain.PAYMENT_METHODS, n).astype(str)
        pay_lag = (rng.integers(30, 600, n) * 1_000_000).astype("timedelta64[us]")
        pay_ts = order_ts + pay_lag
        pay_status = np.where(status == "cancelled", "failed", "success")

        rows = {
            "order_id": order_ids,
            "payment_timestamp": pay_ts,
            "payment_method": method,
            "amount": amount,
            "payment_status": pay_status,
        }

        # ~5% đơn: thêm 1 lần thất bại TRƯỚC đó
        retry_mask = (rng.random(n) < 0.05) & (status != "cancelled")
        r_idx = np.where(retry_mask)[0]
        if r_idx.size:
            fail = {
                "order_id": order_ids[r_idx],
                "payment_timestamp": order_ts[r_idx]
                + (rng.integers(5, 25, r_idx.size) * 1_000_000).astype(
                    "timedelta64[us]"
                ),
                "payment_method": method[r_idx],
                "amount": amount[r_idx],
                "payment_status": np.full(r_idx.size, "failed"),
            }
            for k in rows:
                rows[k] = np.concatenate([rows[k], fail[k]])

        m = len(rows["order_id"])
        # sắp theo thời gian để payment_id tăng dần hợp lý
        order_sort = np.argsort(rows["payment_timestamp"], kind="stable")
        df = pl.DataFrame(
            {
                "payment_id": pl.Series(
                    [f"PAY{i:09d}" for i in range(1, m + 1)], dtype=pl.String
                ),
                "order_id": pl.Series(
                    rows["order_id"][order_sort].tolist(), dtype=pl.String
                ),
                "payment_timestamp": pl.Series(rows["payment_timestamp"][order_sort]),
                "payment_method": pl.Series(
                    rows["payment_method"][order_sort].tolist(), dtype=pl.String
                ),
                "amount": rows["amount"][order_sort],
                "payment_status": pl.Series(
                    rows["payment_status"][order_sort].tolist(), dtype=pl.String
                ),
            }
        )
        ingest = (rng.integers(0, 120, m) * 1_000_000).astype("timedelta64[us]")
        df = df.with_columns(
            (pl.col("payment_timestamp") + pl.Series(ingest)).alias("created_ts")
        )
        return df
