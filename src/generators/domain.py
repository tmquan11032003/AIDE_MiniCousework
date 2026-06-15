"""Hằng số domain cho chuỗi quán cà phê: thành phố (có skew), menu, kênh bán...

Tách riêng để generator chỉ lo logic phân phối, dữ liệu domain ở một chỗ dễ chỉnh.
"""

from __future__ import annotations

# Thành phố + trọng số (skew: vài thành phố lớn chiếm phần lớn cửa hàng/đơn).
CITIES: list[tuple[str, float]] = [
    ("Ho Chi Minh City", 0.34),
    ("Hanoi", 0.24),
    ("Da Nang", 0.10),
    ("Bien Hoa", 0.06),
    ("Hai Phong", 0.05),
    ("Can Tho", 0.04),
    ("Nha Trang", 0.04),
    ("Hue", 0.03),
    ("Vung Tau", 0.03),
    ("Buon Ma Thuot", 0.03),
    ("Da Lat", 0.02),
    ("Quy Nhon", 0.02),
]

REGIONS: dict[str, str] = {
    "Ho Chi Minh City": "South",
    "Bien Hoa": "South",
    "Can Tho": "South",
    "Vung Tau": "South",
    "Hanoi": "North",
    "Hai Phong": "North",
    "Da Nang": "Central",
    "Nha Trang": "Central",
    "Hue": "Central",
    "Buon Ma Thuot": "Central",
    "Da Lat": "Central",
    "Quy Nhon": "Central",
}

STORE_TYPES: list[tuple[str, float]] = [
    ("cafe", 0.6),
    ("kiosk", 0.25),
    ("drive_thru", 0.15),
]

EMPLOYEE_ROLES: list[tuple[str, float]] = [
    ("barista", 0.6),
    ("cashier", 0.25),
    ("shift_lead", 0.1),
    ("manager", 0.05),
]

MEMBERSHIP_TIERS: list[tuple[str, float]] = [
    ("none", 0.5),
    ("green", 0.35),
    ("gold", 0.15),
]

# Kênh bán (chỉ tồn tại từ khi ra mobile app -> dùng cho schema evolution).
CHANNELS: list[tuple[str, float]] = [
    ("in_store", 0.55),
    ("mobile_app", 0.25),
    ("drive_thru", 0.12),
    ("delivery", 0.08),
]

ORDER_STATUSES: list[tuple[str, float]] = [
    ("completed", 0.93),
    ("refunded", 0.04),
    ("cancelled", 0.03),
]

PAYMENT_METHODS: list[tuple[str, float]] = [
    ("card", 0.4),
    ("cash", 0.3),
    ("wallet", 0.2),
    ("giftcard", 0.1),
]

# Menu: (tên, category, giá gốc (nghìn VND), có size hay không, theo mùa hay không)
MENU: list[tuple[str, str, float, bool, bool]] = [
    # coffee (category chiếm tỉ trọng lớn — đặt nhiều món)
    ("Espresso", "coffee", 45, True, False),
    ("Americano", "coffee", 50, True, False),
    ("Cappuccino", "coffee", 60, True, False),
    ("Latte", "coffee", 65, True, False),
    ("Mocha", "coffee", 70, True, False),
    ("Cold Brew", "coffee", 65, True, False),
    ("Flat White", "coffee", 62, True, False),
    ("Caramel Macchiato", "coffee", 72, True, False),
    ("Vietnamese Phin", "coffee", 40, True, False),
    ("Coconut Coffee", "coffee", 68, True, True),
    # tea
    ("Green Tea Latte", "tea", 60, True, False),
    ("Peach Tea", "tea", 55, True, True),
    ("Black Tea", "tea", 45, True, False),
    ("Oolong Milk Tea", "tea", 58, True, False),
    # food
    ("Croissant", "food", 35, False, False),
    ("Tiramisu", "food", 55, False, False),
    ("Cheese Cake", "food", 58, False, False),
    ("Chicken Sandwich", "food", 65, False, False),
    ("Banana Bread", "food", 40, False, False),
    # merch
    ("Ceramic Mug", "merch", 180, False, False),
    ("Tumbler", "merch", 250, False, False),
    ("Coffee Beans 250g", "merch", 220, False, False),
]

SIZES: list[tuple[str, float]] = [("S", 1.0), ("M", 1.2), ("L", 1.4)]
