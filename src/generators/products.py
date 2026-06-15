"""Generator bảng `products` (1 dòng / món).

Sinh `n_products` SKU từ các template menu, có **skew theo category**: coffee chiếm
`coffee_category_share` (mặc định 0.70), phần còn lại chia cho tea/food/merch.
"""

from __future__ import annotations

import numpy as np
import polars as pl

from . import domain
from .base import BaseGenerator, make_ids


class ProductsGenerator(BaseGenerator):
    name = "products"

    def _template_weights(self) -> np.ndarray:
        """Trọng số cho từng template để coffee đạt đúng tỉ trọng mong muốn."""
        coffee_share = self.config["skew"]["coffee_category_share"]
        other_share = 1.0 - coffee_share
        # tea/food/merch chia phần còn lại theo tỉ lệ 0.5/0.3/0.2
        cat_share = {
            "coffee": coffee_share,
            "tea": other_share * 0.5,
            "food": other_share * 0.3,
            "merch": other_share * 0.2,
        }
        counts: dict[str, int] = {}
        for _, cat, *_ in domain.MENU:
            counts[cat] = counts.get(cat, 0) + 1
        weights = np.array(
            [cat_share[cat] / counts[cat] for _, cat, *_ in domain.MENU]
        )
        return weights / weights.sum()

    def generate(self) -> pl.DataFrame:
        rng = self.rng
        n = self.config["volume"]["n_products"]
        start = np.datetime64(self.config["history"]["start_date"], "s")

        weights = self._template_weights()
        tpl_idx = rng.choice(len(domain.MENU), size=n, p=weights)

        names, categories, base_prices, has_sizes, seasonal = [], [], [], [], []
        for k, t in enumerate(tpl_idx):
            tpl_name, cat, price, has_size, is_seasonal = domain.MENU[t]
            jitter = 1.0 + rng.uniform(-0.05, 0.05)
            names.append(f"{tpl_name} v{k % 7 + 1}")
            categories.append(cat)
            base_prices.append(round(price * jitter, 1))
            has_sizes.append(has_size)
            seasonal.append(is_seasonal)

        is_active = rng.random(n) > 0.05  # ~5% ngừng bán

        return pl.DataFrame(
            {
                "product_id": make_ids("P", n, 4),
                "product_name": names,
                "category": categories,
                "base_price": base_prices,
                "has_size": has_sizes,
                "is_seasonal": seasonal,
                "is_active": is_active,
                "created_ts": pl.Series(
                    np.full(n, start.astype("datetime64[us]"))
                ),
            }
        )
