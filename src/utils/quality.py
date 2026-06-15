"""Tính các chỉ số chất lượng/challenge từ dữ liệu offline và xuất Markdown.

Dùng làm bằng chứng (evidence) reproducible cho Section 01: chạy lại generator -> report y hệt.
"""

from __future__ import annotations

import polars as pl


def offline_quality_report(tables: dict[str, pl.DataFrame], config: dict) -> str:
    orders = tables["orders"]
    items = tables["order_items"]
    products = tables["products"]
    customers = tables["customers"]
    n_orders = orders.height

    # Skew cửa hàng
    top_n = config["skew"]["n_top_stores"]
    top_share = (
        orders["store_id"].value_counts().sort("count", descending=True).head(top_n)[
            "count"
        ].sum()
        / n_orders
    )
    # Skew giờ cao điểm
    peak_hours = config["skew"]["peak_hours"]
    hr = orders["order_timestamp"].dt.hour()
    peak_share = orders.filter(hr.is_in(peak_hours)).height / n_orders
    # Schema evolution
    pre_app = orders.filter(pl.col("channel").is_null()).height / n_orders
    # Duplicates
    dup = (items.height - items.unique(subset="order_item_id").height) / items.height
    # Loyalty / guest
    guest = orders.filter(pl.col("customer_id").is_null()).height / n_orders
    # Missing
    miss_city = customers["city"].null_count() / customers.height
    # Category skew
    coffee = (products["category"] == "coffee").mean()
    # Cardinality
    card_orders = orders["order_id"].n_unique()
    card_cust = customers["customer_id"].n_unique()

    rows = [
        ("Số bảng / tổng rows", f"{len(tables)} bảng / "
         f"{sum(t.height for t in tables.values()):,} rows", "—"),
        ("Skew cửa hàng (top-8)", f"{top_share:.0%}",
         f"~{config['skew']['top_store_share']:.0%}"),
        ("Skew giờ cao điểm (7-9h)", f"{peak_share:.0%}",
         f"~{config['skew']['peak_hour_share']:.0%}"),
        ("Skew category coffee", f"{coffee:.0%}",
         f"~{config['skew']['coffee_category_share']:.0%}"),
        ("Schema evolution (channel NULL pre-app)", f"{pre_app:.0%}", "~50%"),
        ("Duplicates order_items", f"{dup:.1%}",
         f"~{config['offline_issues']['duplicate_rate']:.0%}"),
        ("Missing customers.city", f"{miss_city:.1%}",
         f"~{config['offline_issues']['missing_rate']:.0%}"),
        ("Khách vãng lai (customer NULL)", f"{guest:.0%}", "~30%"),
        ("Cardinality order_id (unique)", f"{card_orders:,}", f"{n_orders:,}"),
        ("Cardinality customer_id (unique)", f"{card_cust:,}",
         f"{customers.height:,}"),
    ]

    lines = [
        "# Quality Report — Section 01 (Offline batch)",
        "",
        f"Seed cố định: `{config['random_seed']}` · Quy mô từ `config/generator.yaml`.",
        "Chạy lại generator cho ra report y hệt (reproducible).",
        "",
        "| Chỉ số | Đo được | Mục tiêu |",
        "| --- | --- | --- |",
    ]
    lines += [f"| {k} | {v} | {tgt} |" for k, v, tgt in rows]
    lines.append("")
    return "\n".join(lines)
