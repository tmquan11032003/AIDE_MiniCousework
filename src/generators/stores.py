"""Generator bảng `stores` (1 dòng / cửa hàng)."""

from __future__ import annotations

import numpy as np
import polars as pl

from . import domain
from .base import BaseGenerator, make_ids, weighted_values


class StoresGenerator(BaseGenerator):
    name = "stores"

    def generate(self) -> pl.DataFrame:
        rng = self.rng
        n = self.config["volume"]["n_stores"]
        start = np.datetime64(self.config["history"]["start_date"], "s")

        store_ids = make_ids("S", n, 4)
        cities = weighted_values(rng, domain.CITIES, n).astype(str)
        regions = [domain.REGIONS[c] for c in cities]
        store_types = weighted_values(rng, domain.STORE_TYPES, n).astype(str)

        # open_date: rải trong ~3 năm trước start_date
        days_back = rng.integers(30, 365 * 3, n)
        open_dates = np.datetime64(start, "D") - days_back.astype("timedelta64[D]")

        return pl.DataFrame(
            {
                "store_id": store_ids,
                "store_name": [f"Coffee {c} #{i + 1}" for i, c in enumerate(cities)],
                "city": cities,
                "region": regions,
                "store_type": store_types,
                "open_date": pl.Series(open_dates).cast(pl.Date),
                "created_ts": pl.Series(
                    np.full(n, start.astype("datetime64[us]"))
                ),
            }
        )
