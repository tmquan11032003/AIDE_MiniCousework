"""
Compute data-quality / challenge metrics from the offline tables and write Markdown.

Reproducible evidence for Section 01.
"""

import os


def offline_report_text(tables, cfg):
    """Return the quality report as a Markdown string."""
    orders = tables["orders"]
    items = tables["order_items"]
    products = tables["products"]
    customers = tables["customers"]
    n = len(orders)

    # store skew: share of orders going to the top-N stores
    top_n = cfg["skew"]["n_top_stores"]
    top_share = orders["store_id"].value_counts().head(top_n).sum() / n
    # peak-hour skew
    peak = cfg["skew"]["peak_hours"]
    peak_share = orders["order_timestamp"].dt.hour.isin(peak).mean()
    # coffee category skew
    coffee = (products["category"] == "coffee").mean()
    # schema evolution: pre-app orders have NULL channel
    pre_app = orders["channel"].isna().mean()
    # duplicate rate in order_items
    dup = (len(items) - items["order_item_id"].nunique()) / len(items)
    # missing values
    miss_city = customers["city"].isna().mean()
    # guest orders (no loyalty customer)
    guest = orders["customer_id"].isna().mean()

    sk = cfg["skew"]
    iss = cfg["offline_issues"]
    rows = [
        ("Tổng rows (7 bảng)", f"{sum(len(t) for t in tables.values()):,}", "—"),
        ("Skew cửa hàng (top-N)", f"{top_share:.0%}", f"~{sk['top_store_share']:.0%}"),
        ("Skew giờ cao điểm", f"{peak_share:.0%}", f"~{sk['peak_hour_share']:.0%}"),
        ("Skew category coffee", f"{coffee:.0%}", f"~{sk['coffee_category_share']:.0%}"),
        ("Schema evolution (channel NULL)", f"{pre_app:.0%}", "~50%"),
        ("Duplicates order_items", f"{dup:.1%}", f"~{iss['duplicate_rate']:.0%}"),
        ("Missing customers.city", f"{miss_city:.1%}", f"~{iss['missing_rate']:.0%}"),
        ("Khách vãng lai (NULL)", f"{guest:.0%}", "~30%"),
        ("Cardinality order_id (unique)", f"{orders['order_id'].nunique():,}", f"{n:,}"),
    ]

    lines = [
        "# Quality Report — Section 01 (Offline batch)",
        "",
        f"Seed cố định: `{cfg['random_seed']}`. Chạy lại generator cho ra report y hệt.",
        "",
        "| Chỉ số | Đo được | Mục tiêu |",
        "| --- | --- | --- |",
    ]
    lines += [f"| {k} | {v} | {t} |" for k, v, t in rows]
    return "\n".join(lines) + "\n"


def write_offline_report(tables, cfg):
    out_dir = cfg["paths"]["reports_dir"]
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, "quality_report.md")
    with open(path, "w", encoding="utf-8") as f:
        f.write(offline_report_text(tables, cfg))
    return path
