"""Tiện ích I/O + seed cho generator.

- `child_rngs`: từ một seed gốc, sinh ra các `numpy.random.Generator` độc lập theo tên entity
  (mỗi entity có luồng ngẫu nhiên riêng nhưng vẫn tái lập được từ cùng một seed).
- `write_parquet`: ghi một bảng ra Parquet.
- `write_orders_schema_evolution`: ghi `orders` thành nhiều file để mô phỏng schema evolution
  (file cũ thiếu cột `channel`/`membership_tier_at_order`).
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import polars as pl


def child_rngs(seed: int, names: list[str]) -> dict[str, np.random.Generator]:
    """Sinh các RNG con độc lập, reproducible, mỗi entity một luồng."""
    seqs = np.random.SeedSequence(seed).spawn(len(names))
    return {name: np.random.default_rng(seq) for name, seq in zip(names, seqs)}


def write_parquet(df: pl.DataFrame, out_dir: str | Path, name: str) -> Path:
    """Ghi DataFrame ra `<out_dir>/<name>.parquet`."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{name}.parquet"
    df.write_parquet(path)
    return path


def write_orders_schema_evolution(
    df: pl.DataFrame, out_dir: str | Path, app_launch_date: str
) -> Path:
    """Ghi `orders` thành 2 file mô phỏng schema evolution.

    - File `orders/part-pre_app.parquet`: đơn TRƯỚC ngày ra app -> BỎ cột `channel` và
      `membership_tier_at_order` (giống dữ liệu cũ chưa có khái niệm này).
    - File `orders/part-post_app.parquet`: đơn TỪ ngày ra app -> giữ đủ cột.

    Khi đọc cả thư mục bằng DuckDB/Spark (union by name), cột mới sẽ NULL ở phần dữ liệu cũ.
    """
    out_dir = Path(out_dir) / "orders"
    out_dir.mkdir(parents=True, exist_ok=True)
    launch = pl.lit(app_launch_date).str.to_date()

    pre = df.filter(pl.col("order_date") < launch).drop(
        ["channel", "membership_tier_at_order"]
    )
    post = df.filter(pl.col("order_date") >= launch)

    pre.write_parquet(out_dir / "part-pre_app.parquet")
    post.write_parquet(out_dir / "part-post_app.parquet")
    return out_dir
