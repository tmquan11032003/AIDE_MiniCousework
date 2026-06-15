"""BaseGenerator + helper dùng chung cho các generator theo entity.

Mỗi generator nhận `config` (dict từ YAML) và một `numpy.random.Generator` (rng) seed cố định,
để toàn bộ pipeline sinh dữ liệu tái lập được.
"""

from __future__ import annotations

import numpy as np
import polars as pl


def weighted_values(
    rng: np.random.Generator, items: list[tuple], size: int
) -> np.ndarray:
    """Chọn ngẫu nhiên `size` phần tử theo trọng số. `items` = list[(value, weight)]."""
    values = [v for v, _ in items]
    weights = np.array([w for _, w in items], dtype=float)
    weights /= weights.sum()
    idx = rng.choice(len(values), size=size, p=weights)
    return np.array(values, dtype=object)[idx]


def make_ids(prefix: str, n: int, width: int) -> list[str]:
    """Sinh danh sách business key dạng `<prefix><số 0-pad>` (vd S0001)."""
    return [f"{prefix}{i:0{width}d}" for i in range(1, n + 1)]


class BaseGenerator:
    """Lớp cơ sở cho mọi entity generator."""

    name: str = "base"

    def __init__(self, config: dict, rng: np.random.Generator) -> None:
        self.config = config
        self.rng = rng

    def generate(self) -> pl.DataFrame:
        raise NotImplementedError(f"{type(self).__name__}.generate() chưa được triển khai.")
