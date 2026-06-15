"""
Sinh dữ liệu OFFLINE (batch) cho chuỗi quán cà phê -> Parquet.

Viết theo kiểu ĐƠN GIẢN: mỗi bảng một hàm `gen_*()` trả về một pandas DataFrame,
comment giải thích rõ. Tất cả dùng chung seed cố định để TÁI LẬP (chạy lại ra y hệt).

7 bảng: stores, products, customers, employees, orders, order_items, payments.

Các "thách thức dữ liệu" (data challenges) cố tình chèn vào:
  - Skew         : ~75% đơn rơi vào vài cửa hàng lớn; ~70% sản phẩm là coffee;
                   ~55% đơn vào giờ cao điểm 7-9h sáng.
  - High cardinality : order_id / order_item_id / customer_id gần như unique.
  - Schema evolution : đơn TRƯỚC ngày ra app thiếu cột `channel` + `membership_tier_at_order`
                       (ghi mỗi tháng 1 file parquet; file cũ không có 2 cột này).
  - Duplicates   : ~2% dòng order_items bị nhân bản y hệt.
  - Missing      : ~1% giá trị NULL ở vài cột optional.
  - event-time vs ingest-time : `*_timestamp` (lúc xảy ra) vs `created_ts` (lúc ghi, trễ chút).

Cách chạy:
    python -m src.run offline
"""

import os
import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

# ------------------------------------------------------------------------------
# Hằng số domain (để ở đây cho dễ chỉnh)
# ------------------------------------------------------------------------------

# Thành phố + trọng số (vài thành phố lớn chiếm phần lớn -> tạo skew tự nhiên)
CITIES = ["HCMC", "Hanoi", "Da-Nang", "Bien-Hoa", "Hai-Phong", "Can-Tho",
          "Nha-Trang", "Hue", "Vung-Tau", "Da-Lat"]
CITY_W = [0.34, 0.24, 0.10, 0.06, 0.05, 0.05, 0.04, 0.04, 0.04, 0.04]
REGION = {"HCMC": "South", "Bien-Hoa": "South", "Can-Tho": "South", "Vung-Tau": "South",
          "Hanoi": "North", "Hai-Phong": "North",
          "Da-Nang": "Central", "Nha-Trang": "Central", "Hue": "Central", "Da-Lat": "Central"}

STORE_TYPES = ["cafe", "kiosk", "drive_thru"]
STORE_TYPE_W = [0.6, 0.25, 0.15]

ROLES = ["barista", "cashier", "shift_lead", "manager"]
ROLE_W = [0.6, 0.25, 0.1, 0.05]

TIERS = ["none", "green", "gold"]
TIER_W = [0.5, 0.35, 0.15]

# Kênh bán: chỉ có TỪ KHI ra mobile app -> dùng cho schema evolution
CHANNELS = ["in_store", "mobile_app", "drive_thru", "delivery"]
CHANNEL_W = [0.55, 0.25, 0.12, 0.08]

STATUSES = ["completed", "refunded", "cancelled"]
STATUS_W = [0.93, 0.04, 0.03]

PAY_METHODS = ["card", "cash", "wallet", "giftcard"]
PAY_METHOD_W = [0.4, 0.3, 0.2, 0.1]

# Menu: (tên, category, giá gốc nghìn VND, có size?). Coffee có nhiều món hơn để chiếm tỉ trọng cao.
MENU = [
    ("Espresso", "coffee", 45, True), ("Americano", "coffee", 50, True),
    ("Cappuccino", "coffee", 60, True), ("Latte", "coffee", 65, True),
    ("Mocha", "coffee", 70, True), ("Cold Brew", "coffee", 65, True),
    ("Flat White", "coffee", 62, True), ("Caramel Macchiato", "coffee", 72, True),
    ("Vietnamese Phin", "coffee", 40, True), ("Coconut Coffee", "coffee", 68, True),
    ("Green Tea Latte", "tea", 60, True), ("Peach Tea", "tea", 55, True),
    ("Black Tea", "tea", 45, True), ("Oolong Milk Tea", "tea", 58, True),
    ("Croissant", "food", 35, False), ("Tiramisu", "food", 55, False),
    ("Cheese Cake", "food", 58, False), ("Chicken Sandwich", "food", 65, False),
    ("Ceramic Mug", "merch", 180, False), ("Tumbler", "merch", 250, False),
]

SIZES = ["S", "M", "L"]
SIZE_MULT = {"S": 1.0, "M": 1.2, "L": 1.4}

# Tên giả đơn giản (không cần thư viện ngoài) -> ghép họ + tên
LAST = ["Nguyen", "Tran", "Le", "Pham", "Hoang", "Vu", "Dang", "Bui", "Do", "Ngo"]
FIRST = ["An", "Binh", "Chi", "Dung", "Giang", "Ha", "Khoa", "Lan", "Minh", "Nam",
         "Oanh", "Phuc", "Quan", "Trang", "Yen"]


# ------------------------------------------------------------------------------
# Generator từng bảng (mỗi hàm trả về 1 DataFrame)
# ------------------------------------------------------------------------------

def gen_stores(n, start_date):
    """Bảng cửa hàng: 1 dòng / cửa hàng."""
    cities = np.random.choice(CITIES, n, p=CITY_W)
    return pd.DataFrame({
        "store_id": [f"S{i:04d}" for i in range(1, n + 1)],
        "store_name": [f"Coffee {c} #{i + 1}" for i, c in enumerate(cities)],
        "city": cities,
        "region": [REGION[c] for c in cities],
        "store_type": np.random.choice(STORE_TYPES, n, p=STORE_TYPE_W),
        # open_date: rải trong ~3 năm trước start_date
        "open_date": start_date - pd.to_timedelta(np.random.randint(30, 365 * 3, n), unit="D"),
    })


def gen_products(n, coffee_share):
    """Bảng sản phẩm: 1 dòng / món. Skew: coffee chiếm ~coffee_share."""
    # Tính trọng số mỗi món sao cho tổng coffee = coffee_share
    cats = [m[1] for m in MENU]
    other = 1.0 - coffee_share
    cat_share = {"coffee": coffee_share, "tea": other * 0.5,
                 "food": other * 0.3, "merch": other * 0.2}
    cat_count = {c: cats.count(c) for c in set(cats)}
    w = np.array([cat_share[m[1]] / cat_count[m[1]] for m in MENU])
    w = w / w.sum()

    idx = np.random.choice(len(MENU), n, p=w)
    names = [f"{MENU[t][0]} v{k % 7 + 1}" for k, t in enumerate(idx)]
    return pd.DataFrame({
        "product_id": [f"P{i:04d}" for i in range(1, n + 1)],
        "product_name": names,
        "category": [MENU[t][1] for t in idx],
        "base_price": [round(MENU[t][2] * np.random.uniform(0.95, 1.05), 1) for t in idx],
        "has_size": [MENU[t][3] for t in idx],
        "is_active": np.random.random(n) > 0.05,  # ~5% ngừng bán
    })


def gen_customers(n, start_date, miss_rate):
    """Bảng khách loyalty: 1 dòng / khách. Có PII (full_name, email). Chèn missing values."""
    df = pd.DataFrame({
        "customer_id": [f"C{i:06d}" for i in range(1, n + 1)],
        "full_name": [f"{np.random.choice(LAST)} {np.random.choice(FIRST)}" for _ in range(n)],
        "email": [f"user{i}@coffee.test" for i in range(1, n + 1)],
        "city": np.random.choice(CITIES, n, p=CITY_W),
        "membership_tier": np.random.choice(TIERS, n, p=TIER_W),
        "marketing_opt_in": np.random.random(n) < 0.6,
        # signup_ts: rải trong ~2 năm trước start
        "signup_ts": start_date - pd.to_timedelta(
            np.random.randint(0, 2 * 365 * 86400, n), unit="s"),
    })
    # Missing values: đục NULL ~miss_rate ở city + marketing_opt_in.
    # (Cột bool không chứa được None nên đổi sang object trước.)
    df["marketing_opt_in"] = df["marketing_opt_in"].astype(object)
    df.loc[np.random.random(n) < miss_rate, "city"] = None
    df.loc[np.random.random(n) < miss_rate, "marketing_opt_in"] = None
    return df


def gen_employees(n, store_ids, start_date):
    """Bảng nhân viên: 1 dòng / người, thuộc 1 cửa hàng."""
    return pd.DataFrame({
        "employee_id": [f"E{i:04d}" for i in range(1, n + 1)],
        "full_name": [f"{np.random.choice(LAST)} {np.random.choice(FIRST)}" for _ in range(n)],
        "store_id": np.random.choice(store_ids, n),
        "role": np.random.choice(ROLES, n, p=ROLE_W),
        "hire_date": start_date - pd.to_timedelta(np.random.randint(30, 365 * 4, n), unit="D"),
        "is_active": np.random.random(n) > 0.1,
    })


def gen_orders(n, stores, customers, employees, cfg):
    """Bảng đơn hàng: 1 dòng / đơn. Đây là nơi chèn nhiều challenge nhất."""
    skew = cfg["skew"]
    start = pd.Timestamp(cfg["history"]["start_date"])
    app_launch = pd.Timestamp(cfg["history"]["app_launch_date"])
    days = cfg["history"]["days"]

    store_ids = stores["store_id"].to_numpy()

    # --- Skew cửa hàng: chọn vài cửa hàng "đông khách" nhận phần lớn đơn ---
    top_ids = np.random.choice(store_ids, skew["n_top_stores"], replace=False)
    other_ids = np.setdiff1d(store_ids, top_ids)
    is_top = np.random.random(n) < skew["top_store_share"]
    store_col = np.where(
        is_top,
        np.random.choice(top_ids, n),
        np.random.choice(other_ids, n),
    )

    # --- Skew giờ cao điểm: ~peak_hour_share đơn vào giờ 7-9h sáng ---
    peak = skew["peak_hours"]
    non_peak = [h for h in range(6, 23) if h not in peak]
    is_peak = np.random.random(n) < skew["peak_hour_share"]
    hour = np.where(is_peak, np.random.choice(peak, n), np.random.choice(non_peak, n))
    day = np.random.randint(0, days, n)
    sec = day * 86400 + hour * 3600 + np.random.randint(0, 3600, n)
    order_ts = start + pd.to_timedelta(sec, unit="s")
    order_date = order_ts.normalize()  # bỏ phần giờ, còn ngày

    # --- Khách loyalty (70%) vs vãng lai (30%, customer_id = NULL) ---
    cust_ids = customers["customer_id"].to_numpy()
    cust_tiers = customers["membership_tier"].to_numpy()
    has_loyalty = np.random.random(n) < 0.7
    cidx = np.random.randint(0, len(cust_ids), n)
    customer_col = np.where(has_loyalty, cust_ids[cidx], None)
    tier_snapshot = np.where(has_loyalty, cust_tiers[cidx], None)

    # --- Nhân viên phục vụ: phải thuộc đúng cửa hàng của đơn ---
    emp_ids = employees["employee_id"].to_numpy()
    emp_store = employees["store_id"].to_numpy()
    employee_col = np.empty(n, dtype=object)
    for s in store_ids:
        pool = emp_ids[emp_store == s]
        if len(pool) == 0:
            pool = emp_ids
        mask = store_col == s
        employee_col[mask] = np.random.choice(pool, mask.sum())

    # --- Schema evolution: channel + tier chỉ có TỪ ngày ra app ---
    pre_app = order_date < app_launch
    channel = np.random.choice(CHANNELS, n, p=CHANNEL_W).astype(object)
    channel[pre_app] = None
    membership = tier_snapshot.copy()
    membership[pre_app] = None

    # --- ingest time trễ 0-5 phút so với event time ---
    created_ts = order_ts + pd.to_timedelta(np.random.randint(0, 300, n), unit="s")

    return pd.DataFrame({
        "order_id": [f"O{i:08d}" for i in range(1, n + 1)],
        "store_id": store_col,
        "customer_id": customer_col,
        "employee_id": employee_col,
        "order_timestamp": order_ts,
        "order_date": order_date,
        "channel": channel,
        "membership_tier_at_order": membership,
        "status": np.random.choice(STATUSES, n, p=STATUS_W),
        "created_ts": created_ts,
    })


def gen_order_items(orders, products, dup_rate):
    """Bảng dòng món: 1 dòng / món trong đơn. Chèn duplicates ~dup_rate."""
    order_ids = orders["order_id"].to_numpy()
    order_created = orders["created_ts"].to_numpy()

    # mỗi đơn 1-4 món
    n_items = np.random.randint(1, 5, len(order_ids))
    oid = np.repeat(order_ids, n_items)
    created = np.repeat(order_created, n_items)
    m = len(oid)

    p_id = products["product_id"].to_numpy()
    p_price = products["base_price"].to_numpy()
    p_hassize = products["has_size"].to_numpy()
    pidx = np.random.randint(0, len(p_id), m)

    has_size = p_hassize[pidx]
    size = np.where(has_size, np.random.choice(SIZES, m), None)
    mult = np.array([SIZE_MULT.get(s, 1.0) for s in size])

    qty = np.random.choice([1, 2, 3], m, p=[0.7, 0.22, 0.08])
    unit_price = np.round(p_price[pidx] * mult, 1)
    has_disc = np.random.random(m) < 0.15
    discount = np.where(has_disc, np.round(unit_price * qty * 0.2, 1), 0.0)
    line_amount = np.round(unit_price * qty - discount, 1)

    df = pd.DataFrame({
        "order_item_id": [f"OI{i:09d}" for i in range(1, m + 1)],
        "order_id": oid,
        "product_id": p_id[pidx],
        "size": size,
        "quantity": qty,
        "unit_price": unit_price,
        "discount_amount": discount,
        "line_amount": line_amount,
        "created_ts": created,
    })

    # Duplicates: nhân bản y hệt ~dup_rate dòng (để tầng Silver phải dedup)
    n_dup = int(m * dup_rate)
    if n_dup:
        dup_rows = df.iloc[np.random.choice(m, n_dup, replace=False)]
        df = pd.concat([df, dup_rows], ignore_index=True)
    return df


def gen_payments(orders, items):
    """Bảng thanh toán: 1 dòng / lần trả tiền. ~5% đơn có 1 lần FAIL trước khi success."""
    # amount = tổng line_amount của đơn
    totals = items.groupby("order_id")["line_amount"].sum().round(1)
    base = orders[["order_id", "order_timestamp", "status"]].copy()
    base["amount"] = base["order_id"].map(totals).fillna(0.0)

    n = len(base)
    method = np.random.choice(PAY_METHODS, n, p=PAY_METHOD_W)
    pay_ts = base["order_timestamp"].to_numpy() + pd.to_timedelta(
        np.random.randint(30, 600, n), unit="s")
    status = np.where(base["status"].to_numpy() == "cancelled", "failed", "success")

    success = pd.DataFrame({
        "order_id": base["order_id"].to_numpy(),
        "payment_timestamp": pay_ts,
        "payment_method": method,
        "amount": base["amount"].to_numpy(),
        "payment_status": status,
    })

    # ~5% đơn (không bị huỷ) thêm 1 dòng thất bại TRƯỚC đó
    retry = (np.random.random(n) < 0.05) & (base["status"].to_numpy() != "cancelled")
    fails = pd.DataFrame({
        "order_id": base["order_id"].to_numpy()[retry],
        "payment_timestamp": base["order_timestamp"].to_numpy()[retry]
        + pd.to_timedelta(np.random.randint(5, 25, retry.sum()), unit="s"),
        "payment_method": method[retry],
        "amount": base["amount"].to_numpy()[retry],
        "payment_status": "failed",
    })

    df = pd.concat([fails, success], ignore_index=True)
    df = df.sort_values("payment_timestamp").reset_index(drop=True)
    df.insert(0, "payment_id", [f"PAY{i:09d}" for i in range(1, len(df) + 1)])
    df["created_ts"] = df["payment_timestamp"] + pd.to_timedelta(
        np.random.randint(0, 120, len(df)), unit="s")
    return df


# ------------------------------------------------------------------------------
# Ghi Parquet
# ------------------------------------------------------------------------------

def write_parquet(df, path):
    pq.write_table(pa.Table.from_pandas(df, preserve_index=False), path)


def write_orders_by_month(orders, out_dir, app_launch_date):
    """Ghi orders thành mỗi tháng 1 file. File TRƯỚC ngày ra app bỏ 2 cột mới
    -> mô phỏng schema evolution (giống dữ liệu lịch sử thật)."""
    os.makedirs(out_dir, exist_ok=True)
    launch_ym = app_launch_date[:7]  # 'YYYY-MM'
    ym = pd.to_datetime(orders["order_date"]).dt.strftime("%Y-%m")
    for month, g in orders.groupby(ym):
        if month < launch_ym:
            g = g.drop(columns=["channel", "membership_tier_at_order"])
        write_parquet(g, os.path.join(out_dir, f"orders_{month}.parquet"))


# ------------------------------------------------------------------------------
# Orchestrator
# ------------------------------------------------------------------------------

def build_all(cfg):
    """Sinh cả 7 bảng. Đặt seed ở đây -> chạy lại ra y hệt."""
    np.random.seed(cfg["random_seed"])
    vol = cfg["volume"]
    start = pd.Timestamp(cfg["history"]["start_date"])
    miss = cfg["offline_issues"]["missing_rate"]
    dup = cfg["offline_issues"]["duplicate_rate"]

    stores = gen_stores(vol["n_stores"], start)
    products = gen_products(vol["n_products"], cfg["skew"]["coffee_category_share"])
    customers = gen_customers(vol["n_customers"], start, miss)
    employees = gen_employees(vol["n_employees"], stores["store_id"].to_numpy(), start)
    orders = gen_orders(vol["n_orders"], stores, customers, employees, cfg)
    items = gen_order_items(orders, products, dup)
    payments = gen_payments(orders, items)

    return {
        "stores": stores, "products": products, "customers": customers,
        "employees": employees, "orders": orders, "order_items": items,
        "payments": payments,
    }


def write_all(tables, cfg):
    out = cfg["paths"]["offline_dir"]
    os.makedirs(out, exist_ok=True)
    for name, df in tables.items():
        if name == "orders":
            write_orders_by_month(df, os.path.join(out, "orders"),
                                  cfg["history"]["app_launch_date"])
        else:
            write_parquet(df, os.path.join(out, f"{name}.parquet"))


def run(cfg):
    """Sinh + ghi + in tóm tắt (dùng cho CLI `python -m src.run offline`)."""
    import time
    t0 = time.time()
    tables = build_all(cfg)
    write_all(tables, cfg)
    from src.quality_report import write_offline_report
    report_path = write_offline_report(tables, cfg)

    print(f"[offline] sinh 7 bảng trong {time.time() - t0:.1f}s -> {cfg['paths']['offline_dir']}")
    for name, df in tables.items():
        print(f"  - {name:12s}: {len(df):>8,} rows")
    print(f"[offline] quality report -> {report_path}")
    return tables
