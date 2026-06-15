"""Generator bảng `customers` (1 dòng / khách loyalty).

Có cột PII (full_name, email) để Section 02 minh hoạ xử lý dữ liệu nhạy cảm.
Chèn **missing values** vào vài cột optional theo `offline_issues.missing_rate`.
"""

from __future__ import annotations

import numpy as np
import polars as pl
from mimesis import Person
from mimesis.locales import Locale

from . import domain
from .base import BaseGenerator, make_ids, weighted_values


class CustomersGenerator(BaseGenerator):
    name = "customers"

    def generate(self) -> pl.DataFrame:
        rng = self.rng
        n = self.config["volume"]["n_customers"]
        miss = self.config["offline_issues"]["missing_rate"]
        start = np.datetime64(self.config["history"]["start_date"], "s")

        person = Person(locale=Locale.EN, seed=int(rng.integers(0, 2**31)))
        full_names = [person.full_name() for _ in range(n)]
        emails = [person.email() for _ in range(n)]

        cities = weighted_values(rng, domain.CITIES, n).astype(str)
        tiers = weighted_values(rng, domain.MEMBERSHIP_TIERS, n).astype(str)
        opt_in = rng.random(n) < 0.6

        # signup_ts: rải trong ~2 năm trước start
        secs_back = rng.integers(0, 2 * 365 * 86400, n)
        signup = (start - secs_back.astype("timedelta64[s]")).astype(
            "datetime64[us]"
        )

        df = pl.DataFrame(
            {
                "customer_id": make_ids("C", n, 6),
                "full_name": full_names,
                "email": emails,
                "city": cities,
                "membership_tier": tiers,
                "marketing_opt_in": opt_in,
                "signup_ts": pl.Series(signup),
                "created_ts": pl.Series(
                    np.full(n, start.astype("datetime64[us]"))
                ),
            }
        )

        # Missing values: đục lỗ NULL ở city + marketing_opt_in
        for col in ("city", "marketing_opt_in"):
            mask = rng.random(n) < miss
            df = df.with_columns(
                pl.when(pl.Series(mask)).then(None).otherwise(pl.col(col)).alias(col)
            )
        return df
