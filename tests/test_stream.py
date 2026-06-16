"""Tests M2 — streaming generator: determinism, schema, tỉ lệ challenge."""

import copy

import pytest

from src.generate_stream import build_all
from src.utils.config import load_config


@pytest.fixture(scope="module")
def small_config():
    cfg = copy.deepcopy(load_config("config/generator.yaml"))
    cfg["volume"]["n_stream_events"] = 30000
    return cfg


@pytest.fixture(scope="module")
def events(small_config):
    return build_all(small_config)


def test_schema(events):
    required = {
        "event_id", "event_type", "event_timestamp", "created_ts",
        "store_id", "session_id", "device_type",
    }
    assert required <= set(events.columns)


def test_deterministic(small_config):
    a = build_all(small_config)
    b = build_all(small_config)
    assert a.equals(b)


def test_event_time_before_ingest_time(events):
    """created_ts (ingest) luôn >= event_timestamp (event time)."""
    assert (events["created_ts"] >= events["event_timestamp"]).all()


def test_late_arrival_rate(events, small_config):
    delay = (events["created_ts"] - events["event_timestamp"]).dt.total_seconds()
    late = (delay > 5).mean()
    assert abs(late - small_config["streaming"]["late_arrival_rate"]) < 0.03


def test_duplicate_rate(events, small_config):
    dup = (len(events) - events["event_id"].nunique()) / len(events)
    assert abs(dup - small_config["streaming"]["duplicate_rate"]) < 0.01


def test_out_of_order_exists(events):
    """Có event out-of-order khi sắp theo created_ts (do late arrival)."""
    running_max = events["event_timestamp"].cummax()
    assert (events["event_timestamp"] < running_max).mean() > 0.05


def test_bursty(events, small_config):
    """Phần lớn event rơi vào giờ cao điểm (bursty)."""
    from src.quality_report import _burst_hours
    burst_h = _burst_hours(small_config["streaming"]["burst_windows"])
    assert events["event_timestamp"].dt.hour.isin(burst_h).mean() > 0.5
