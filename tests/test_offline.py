"""Tests M1 — offline generator: determinism, schema contract, tỉ lệ challenge."""

import copy

import polars as pl
import pytest

from src.generators.offline import ENTITIES, generate_offline
from src.utils.config import load_config


@pytest.fixture(scope="module")
def small_config():
    cfg = load_config("config/generator.yaml")
    cfg = copy.deepcopy(cfg)
    cfg["volume"].update(
        n_stores=20, n_products=200, n_customers=2000, n_employees=80, n_orders=8000
    )
    return cfg


@pytest.fixture(scope="module")
def tables(small_config):
    return generate_offline(small_config)


def test_all_entities_present(tables):
    assert set(tables) == set(ENTITIES)
    for name in ENTITIES:
        assert tables[name].height > 0


def test_deterministic(small_config):
    """Cùng seed -> sinh 2 lần ra y hệt (reproducibility)."""
    a = generate_offline(small_config)
    b = generate_offline(small_config)
    for name in ENTITIES:
        assert a[name].equals(b[name]), f"{name} không tái lập"


def test_business_keys_unique(tables):
    assert tables["orders"]["order_id"].is_duplicated().sum() == 0
    assert tables["stores"]["store_id"].n_unique() == tables["stores"].height
    assert tables["customers"]["customer_id"].n_unique() == tables["customers"].height


def test_schema_contract_orders(tables):
    cols = set(tables["orders"].columns)
    required = {
        "order_id", "store_id", "customer_id", "employee_id",
        "order_timestamp", "order_date", "channel",
        "membership_tier_at_order", "status", "created_ts",
    }
    assert required <= cols


def test_event_time_vs_ingest_time(tables):
    """created_ts (ingest) luôn >= order_timestamp (event time)."""
    o = tables["orders"]
    assert (o["created_ts"] >= o["order_timestamp"]).all()


def test_duplicate_rate(tables, small_config):
    items = tables["order_items"]
    dup = (items.height - items.unique(subset="order_item_id").height) / items.height
    target = small_config["offline_issues"]["duplicate_rate"]
    assert abs(dup - target) < 0.01


def test_store_skew(tables, small_config):
    orders = tables["orders"]
    top_n = small_config["skew"]["n_top_stores"]
    share = (
        orders["store_id"].value_counts().sort("count", descending=True).head(top_n)[
            "count"
        ].sum()
        / orders.height
    )
    assert share > 0.6  # skew rõ rệt (mục tiêu ~0.75)


def test_schema_evolution_pre_app(tables):
    """Đơn trước app launch phải có channel NULL (schema evolution)."""
    orders = tables["orders"]
    pre = orders.filter(pl.col("channel").is_null())
    assert pre.height > 0
    assert pre["membership_tier_at_order"].is_null().all()
