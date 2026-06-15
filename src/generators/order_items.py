"""Generator bảng `order_items` (1 dòng / dòng món).

Chèn challenge **duplicates**: nhân bản ~`duplicate_rate` dòng (trùng y hệt cả order_item_id)
để tầng Silver phải dedup.
"""

from __future__ import annotations

import numpy as np
import polars as pl

from . import domain
from .base import BaseGenerator


class OrderItemsGenerator(BaseGenerator):
    name = "order_items"

    def __init__(self, config, rng, orders_df, products_df) -> None:
        super().__init__(config, rng)
        self.orders = orders_df
        self.products = products_df

    def generate(self) -> pl.DataFrame:
        rng = self.rng
        dup_rate = self.config["offline_issues"]["duplicate_rate"]

        order_ids = self.orders["order_id"].to_numpy()
        order_created = self.orders["created_ts"].to_numpy()
        n_orders = len(order_ids)

        # 1-4 món / đơn
        n_items = rng.integers(1, 5, n_orders)
        oid = np.repeat(order_ids, n_items)
        created = np.repeat(order_created, n_items)
        m = oid.size

        prod_id = self.products["product_id"].to_numpy()
        prod_price = self.products["base_price"].to_numpy()
        prod_hassize = self.products["has_size"].to_numpy()
        pidx = rng.integers(0, len(prod_id), m)

        size_names = np.array([s for s, _ in domain.SIZES], dtype=object)
        size_mult = np.array([mlt for _, mlt in domain.SIZES])
        sidx = rng.integers(0, len(size_names), m)
        has_size = prod_hassize[pidx]
        size_col = np.where(has_size, size_names[sidx], None)
        mult = np.where(has_size, size_mult[sidx], 1.0)

        qty = rng.choice([1, 2, 3], size=m, p=[0.7, 0.22, 0.08])
        unit_price = np.round(prod_price[pidx] * mult, 1)
        has_disc = rng.random(m) < 0.15
        discount = np.where(has_disc, np.round(unit_price * qty * 0.2, 1), 0.0)
        line_amount = np.round(unit_price * qty - discount, 1)

        df = pl.DataFrame(
            {
                "order_item_id": pl.Series(
                    [f"OI{i:09d}" for i in range(1, m + 1)], dtype=pl.String
                ),
                "order_id": pl.Series(oid.tolist(), dtype=pl.String),
                "product_id": pl.Series(prod_id[pidx].tolist(), dtype=pl.String),
                "size": pl.Series(size_col.tolist(), dtype=pl.String),
                "quantity": qty,
                "unit_price": unit_price,
                "discount_amount": discount,
                "line_amount": line_amount,
                "created_ts": pl.Series(created),
            }
        )

        # --- Duplicates: nhân bản y hệt ~dup_rate dòng ---
        n_dup = int(m * dup_rate)
        if n_dup:
            dup_idx = rng.choice(m, size=n_dup, replace=False)
            df = pl.concat([df, df[dup_idx]])
        return df
