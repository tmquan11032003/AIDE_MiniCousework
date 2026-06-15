"""BaseGenerator — lớp cơ sở cho các generator theo entity.

Mỗi generator nhận `config` (dict từ YAML) và một `numpy.random.Generator` (rng)
được seed cố định ở entrypoint, để toàn bộ pipeline sinh dữ liệu tái lập được.
"""

from __future__ import annotations

import numpy as np
import polars as pl


class BaseGenerator:
    """Lớp cơ sở cho mọi entity generator."""

    #: Tên entity (override ở lớp con), dùng cho log & tên file output.
    name: str = "base"

    def __init__(self, config: dict, rng: np.random.Generator) -> None:
        self.config = config
        self.rng = rng

    def generate(self) -> pl.DataFrame:
        """Sinh và trả về DataFrame cho entity. Lớp con phải override."""
        raise NotImplementedError(f"{type(self).__name__}.generate() chưa được triển khai.")
