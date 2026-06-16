"""
Streaming (real-time) event generator for the coffee-chain dataset -> NDJSON.

One unified event topic. Fixed seed -> reproducible. The same event-building logic
is reused by the Kafka producer in M4 (live publish).

Event types: app_view, add_to_cart, mobile_order_placed, store_checkin,
             order_picked_up, payment_failed.

Injected data challenges:
  - Bursty traffic   : event hours are weighted by burst_multiplier inside burst windows
                       (e.g. 07:00-09:00, 12:00-13:00) -> heavy peaks.
  - Late arrival     : ~late_arrival_rate of events have created_ts far AFTER event_timestamp
                       (delay in late_delay_seconds), the rest only a few seconds.
  - Out-of-order     : when sorted by created_ts (ingest order), event_timestamp is not
                       monotonic (caused by late arrivals) -> reported, not forced.
  - Duplicates       : ~duplicate_rate of events are exact duplicates (same event_id).
  - event vs ingest  : event_timestamp (when it happened) vs created_ts (when ingested).

Run: python -m src.run stream
"""

import json
import os
import numpy as np
import pandas as pd

EVENT_TYPES = ["app_view", "add_to_cart", "mobile_order_placed",
               "store_checkin", "order_picked_up", "payment_failed"]
EVENT_TYPE_W = [0.40, 0.20, 0.15, 0.12, 0.08, 0.05]

DEVICE_TYPES = ["app", "web", "kiosk"]
DEVICE_TYPE_W = [0.6, 0.25, 0.15]
CHANNELS = ["mobile_app", "web", "in_store"]

# Which event types carry which optional fields.
HAS_PRODUCT = ["app_view", "add_to_cart"]
HAS_ORDER = ["mobile_order_placed", "order_picked_up", "payment_failed"]
HAS_QTY_PRICE = ["add_to_cart", "mobile_order_placed", "payment_failed"]


def _burst_hours(burst_windows):
    """Parse ['07:00-09:00', ...] -> set of integer hours covered (end exclusive)."""
    hours = set()
    for w in burst_windows:
        start, end = w.split("-")
        hours.update(range(int(start[:2]), int(end[:2])))
    return hours


def gen_events(cfg):
    """Build the full streaming event table (pandas DataFrame) with challenges injected."""
    st = cfg["streaming"]
    vol = cfg["volume"]
    n = vol["n_stream_events"]
    start = pd.Timestamp(cfg["history"]["start_date"])
    days = cfg["history"]["days"]

    etype = np.random.choice(EVENT_TYPES, n, p=EVENT_TYPE_W)

    # CHALLENGE Bursty: weight operating hours; burst-window hours get burst_multiplier weight.
    burst_h = _burst_hours(st["burst_windows"])
    op_hours = np.arange(6, 23)
    hour_w = np.array([st["burst_multiplier"] if h in burst_h else 1.0 for h in op_hours])
    hour_w = hour_w / hour_w.sum()
    hour = np.random.choice(op_hours, n, p=hour_w)
    day = np.random.randint(0, days, n)
    sec = day * 86400 + hour * 3600 + np.random.randint(0, 3600, n)
    event_ts = start + pd.to_timedelta(sec, unit="s")

    # CHALLENGE Late arrival: late events get a large ingest delay; others a few seconds.
    lo, hi = st["late_delay_seconds"]
    is_late = np.random.random(n) < st["late_arrival_rate"]
    delay = np.where(is_late,
                     np.random.randint(lo, hi, n),
                     np.random.randint(0, 5, n))
    created_ts = event_ts + pd.to_timedelta(delay, unit="s")

    # Entity references (same id scheme/range as the offline tables).
    store_id = np.array([f"S{i:04d}" for i in np.random.randint(1, vol["n_stores"] + 1, n)])
    has_cust = np.random.random(n) < 0.6
    cust_num = np.random.randint(1, vol["n_customers"] + 1, n)
    customer_id = np.where(has_cust, [f"C{i:06d}" for i in cust_num], None)

    in_product = np.isin(etype, HAS_PRODUCT)
    prod_num = np.random.randint(1, vol["n_products"] + 1, n)
    product_id = np.where(in_product, [f"P{i:04d}" for i in prod_num], None)

    in_order = np.isin(etype, HAS_ORDER)
    ord_num = np.random.randint(1, vol["n_orders"] + 1, n)
    order_id = np.where(in_order, [f"O{i:08d}" for i in ord_num], None)

    in_qp = np.isin(etype, HAS_QTY_PRICE)
    quantity = np.where(in_qp, np.random.randint(1, 4, n), None)
    price = np.where(in_qp, np.round(np.random.uniform(40, 120, n), 1), None)

    df = pd.DataFrame({
        "event_id": [f"EV{i:010d}" for i in range(1, n + 1)],
        "event_type": etype,
        "event_timestamp": event_ts,
        "created_ts": created_ts,
        "customer_id": customer_id,
        "store_id": store_id,
        "session_id": [f"sess_{i:08x}" for i in np.random.randint(0, 16**8, n)],
        "device_type": np.random.choice(DEVICE_TYPES, n, p=DEVICE_TYPE_W),
        "channel": np.random.choice(CHANNELS, n),
        "product_id": product_id,
        "order_id": order_id,
        "quantity": quantity,
        "price": price,
    })

    # CHALLENGE Duplicates: append exact copies of ~duplicate_rate of the rows.
    n_dup = int(n * st["duplicate_rate"])
    if n_dup:
        dup_rows = df.iloc[np.random.choice(n, n_dup, replace=False)]
        df = pd.concat([df, dup_rows], ignore_index=True)

    # Write in ingest order (sorted by created_ts) -> out-of-order event_timestamp appears.
    df = df.sort_values("created_ts").reset_index(drop=True)
    return df


def write_ndjson(df, path):
    """Write one JSON object per line. Timestamps as ISO strings."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    out = df.copy()
    for col in ("event_timestamp", "created_ts"):
        out[col] = out[col].dt.strftime("%Y-%m-%dT%H:%M:%S")
    with open(path, "w", encoding="utf-8") as f:
        for rec in out.to_dict(orient="records"):
            # drop None fields to keep events compact
            rec = {k: v for k, v in rec.items() if v is not None and not pd.isna(v)}
            f.write(json.dumps(rec) + "\n")


def build_all(cfg):
    np.random.seed(cfg["random_seed"] + 1)  # different from offline seed -> independent stream
    return gen_events(cfg)


def run(cfg):
    import time
    t0 = time.time()
    events = build_all(cfg)
    path = os.path.join(cfg["paths"]["streaming_dir"], "events.ndjson")
    write_ndjson(events, path)

    from src.quality_report import write_stream_report
    report_path = write_stream_report(events, cfg)

    print(f"[stream] generated {len(events):,} events in {time.time() - t0:.1f}s -> {path}")
    print(f"[stream] quality report -> {report_path}")
    return events
