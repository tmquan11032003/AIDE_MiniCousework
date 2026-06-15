"""Generator bảng `employees` (1 dòng / nhân viên - barista/thu ngân...).

Mỗi nhân viên thuộc một cửa hàng (`store_id`), dùng để gắn vào `orders` (ai phục vụ).
"""

from __future__ import annotations

import numpy as np
import polars as pl
from mimesis import Person
from mimesis.locales import Locale

from . import domain
from .base import BaseGenerator, make_ids, weighted_values


class EmployeesGenerator(BaseGenerator):
    name = "employees"

    def __init__(self, config, rng, store_ids: list[str]) -> None:
        super().__init__(config, rng)
        self.store_ids = store_ids

    def generate(self) -> pl.DataFrame:
        rng = self.rng
        n = self.config["volume"]["n_employees"]
        start = np.datetime64(self.config["history"]["start_date"], "s")

        person = Person(locale=Locale.EN, seed=int(rng.integers(0, 2**31)))
        full_names = [person.full_name() for _ in range(n)]

        store_assign = rng.choice(self.store_ids, size=n)
        roles = weighted_values(rng, domain.EMPLOYEE_ROLES, n).astype(str)
        days_back = rng.integers(30, 365 * 4, n)
        hire = np.datetime64(start, "D") - days_back.astype("timedelta64[D]")
        is_active = rng.random(n) > 0.1  # ~10% đã nghỉ

        return pl.DataFrame(
            {
                "employee_id": make_ids("E", n, 4),
                "full_name": full_names,
                "store_id": store_assign,
                "role": roles,
                "hire_date": pl.Series(hire).cast(pl.Date),
                "is_active": is_active,
                "created_ts": pl.Series(
                    np.full(n, start.astype("datetime64[us]"))
                ),
            }
        )
