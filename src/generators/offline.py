"""Orchestrator sinh toàn bộ dữ liệu offline (7 bảng) và ghi Parquet.

Mỗi entity dùng một RNG con riêng (spawn từ `random_seed`) -> tái lập được & độc lập.
"""

from __future__ import annotations

import time
from pathlib import Path

import polars as pl

from ..utils.io import child_rngs, write_orders_schema_evolution, write_parquet
from ..utils.quality import offline_quality_report
from .customers import CustomersGenerator
from .employees import EmployeesGenerator
from .order_items import OrderItemsGenerator
from .orders import OrdersGenerator
from .payments import PaymentsGenerator
from .products import ProductsGenerator
from .stores import StoresGenerator

ENTITIES = [
    "stores",
    "products",
    "customers",
    "employees",
    "orders",
    "order_items",
    "payments",
]


def generate_offline(config: dict) -> dict[str, pl.DataFrame]:
    """Sinh 7 bảng theo đúng thứ tự phụ thuộc, trả về dict tên -> DataFrame."""
    rngs = child_rngs(config["random_seed"], ENTITIES)

    stores = StoresGenerator(config, rngs["stores"]).generate()
    products = ProductsGenerator(config, rngs["products"]).generate()
    customers = CustomersGenerator(config, rngs["customers"]).generate()
    employees = EmployeesGenerator(
        config, rngs["employees"], stores["store_id"].to_list()
    ).generate()
    orders = OrdersGenerator(
        config, rngs["orders"], stores, customers, employees
    ).generate()
    items = OrderItemsGenerator(
        config, rngs["order_items"], orders, products
    ).generate()
    payments = PaymentsGenerator(config, rngs["payments"], orders, items).generate()

    return {
        "stores": stores,
        "products": products,
        "customers": customers,
        "employees": employees,
        "orders": orders,
        "order_items": items,
        "payments": payments,
    }


def write_all(tables: dict[str, pl.DataFrame], config: dict) -> None:
    """Ghi mọi bảng ra Parquet. `orders` ghi tách file để mô phỏng schema evolution."""
    out = config["paths"]["offline_dir"]
    for name, df in tables.items():
        if name == "orders":
            write_orders_schema_evolution(
                df, out, config["history"]["app_launch_date"]
            )
        else:
            write_parquet(df, out, name)


def run(config: dict) -> dict[str, pl.DataFrame]:
    """Sinh + ghi + in tóm tắt ngắn (dùng cho CLI)."""
    t0 = time.time()
    tables = generate_offline(config)
    write_all(tables, config)

    # Quality report (evidence)
    report = offline_quality_report(tables, config)
    rep_dir = Path(config["paths"]["reports_dir"])
    rep_dir.mkdir(parents=True, exist_ok=True)
    (rep_dir / "quality_report.md").write_text(report, encoding="utf-8")

    dt = time.time() - t0
    print(f"[offline] sinh xong 7 bảng trong {dt:.1f}s -> {config['paths']['offline_dir']}")
    for name in ENTITIES:
        print(f"  - {name:12s}: {tables[name].height:>8,} rows")
    print(f"[offline] quality report -> {rep_dir / 'quality_report.md'}")
    return tables
