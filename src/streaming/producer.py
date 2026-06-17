"""
Kafka producer: replay the generated NDJSON events into a Kafka topic.

Reads data/streaming/events.ndjson (one JSON event per line) and publishes each
event to the topic, keyed by event_id. The event already carries event_timestamp
and created_ts, so Flink downstream can build event-time watermarks from the payload.

Usage:
    python -m src.streaming.producer                       # all events, as fast as possible
    python -m src.streaming.producer --rate 500            # ~500 events/sec
    python -m src.streaming.producer --limit 1000          # only first 1000
    python -m src.streaming.producer --broker localhost:29092 --topic coffee.events
"""

import argparse
import time

from confluent_kafka import Producer

DEFAULT_BROKER = "localhost:29092"
DEFAULT_TOPIC = "coffee.events"
DEFAULT_FILE = "data/streaming/events.ndjson"


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--broker", default=DEFAULT_BROKER, help="Kafka bootstrap server")
    p.add_argument("--topic", default=DEFAULT_TOPIC, help="Target topic")
    p.add_argument("--file", default=DEFAULT_FILE, help="NDJSON file to replay")
    p.add_argument("--rate", type=float, default=0.0, help="Events/sec (0 = unthrottled)")
    p.add_argument("--limit", type=int, default=0, help="Stop after N events (0 = all)")
    args = p.parse_args()

    producer = Producer({"bootstrap.servers": args.broker})
    delay = 1.0 / args.rate if args.rate > 0 else 0.0
    sent = 0

    with open(args.file, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            # key by event_id (between '"event_id": "' and the next '"') for partition + dedup
            key = line.split('"event_id": "', 1)[1].split('"', 1)[0]
            producer.produce(args.topic, key=key, value=line.encode("utf-8"))
            producer.poll(0)  # serve delivery callbacks / avoid queue buildup
            sent += 1
            if sent % 10000 == 0:
                print(f"  ... {sent:,} events", flush=True)
            if delay:
                time.sleep(delay)
            if args.limit and sent >= args.limit:
                break

    producer.flush()
    print(f"[producer] sent {sent:,} events -> topic '{args.topic}'")


if __name__ == "__main__":
    main()
