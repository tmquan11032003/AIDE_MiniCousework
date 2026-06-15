"""Load + validate config YAML cho generator.

Đảm bảo `random_seed` luôn tồn tại -> mọi lần chạy đều tái lập được.
"""

from __future__ import annotations

from pathlib import Path

import yaml


def load_config(path: str | Path) -> dict:
    """Đọc file YAML config và kiểm tra ràng buộc tối thiểu."""
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Không tìm thấy config: {path}")
    with path.open("r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    if not isinstance(cfg, dict):
        raise ValueError(f"Config không hợp lệ (không phải mapping): {path}")
    if "random_seed" not in cfg:
        raise ValueError("Config thiếu 'random_seed' — bắt buộc để tái lập (reproducibility).")
    return cfg
