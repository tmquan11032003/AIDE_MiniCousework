"""Tests M1 — offline generator: determinism, schema, tỉ lệ challenge."""

import copy

import pytest

from src.generators.offline import build_all
from src.utils.config import load_config

ENTITIES = ["stores", "products", "customers", "employees",
            "orders", "order_items", "payments"]


@pytest.fixture(scope="module")
def small_config():
    cfg = copy.deepcopy(load_config("config/generator.yaml"))
    cfg["volume"].update(
        n_stores=20, n_products=200, n_customers=2000, n_employees=80, n_orders=8000
    )
    return cfg


@pytest.fixture(scope="module")
def tables(small_config):
    return build_all(small_config)


def test_all_entities_present(tables):
    assert set(tables) == set(ENTITIES)
    for name in ENTITIES:
        assert len(tables[name]) > 0


def test_deterministic(small_config):
    """Cùng seed -> sinh 2 lần ra y hệt."""
    a = build_all(small_config)
    b = build_all(small_config)
    for name in ENTITIES:
        assert a[name].equals(b[name]), f"{name} không tái lập"


def test_business_keys_unique(tables):
    assert tables["orders"]["order_id"].is_unique
    assert tables["stores"]["store_id"].is_unique
    assert tables["customers"]["customer_id"].is_unique


def test_event_time_before_ingest_time(tables):
    """created_ts (ingest) luôn >= order_timestamp (event time)."""
    o = tables["orders"]
    assert (o["created_ts"] >= o["order_timestamp"]).all()


def test_duplicate_rate(tables, small_config):
    items = tables["order_items"]
    dup = (len(items) - items["order_item_id"].nunique()) / len(items)
    assert abs(dup - small_config["offline_issues"]["duplicate_rate"]) < 0.01


def test_store_skew(tables, small_config):
    orders = tables["orders"]
    top_n = small_config["skew"]["n_top_stores"]
    share = orders["store_id"].value_counts().head(top_n).sum() / len(orders)
    assert share > 0.6  # skew rõ rệt (mục tiêu ~0.75)


def test_schema_evolution_pre_app(tables):
    """Đơn trước app launch có channel NULL + tier NULL."""
    orders = tables["orders"]
    pre = orders[orders["channel"].isna()]
    assert len(pre) > 0
    assert pre["membership_tier_at_order"].isna().all()
