"""CLI entrypoint: sinh dữ liệu offline (batch) + streaming cho chuỗi quán cà phê.

Ví dụ:
    python -m src.run --help
    python -m src.run offline
    python -m src.run stream
    python -m src.run all --config config/generator.yaml
"""

from __future__ import annotations

import argparse

from src.utils.config import load_config


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="src.run",
        description="Sinh dữ liệu offline (Parquet) + streaming (NDJSON) cho chuỗi quán cà phê.",
    )
    parser.add_argument(
        "--config",
        default="config/generator.yaml",
        help="Đường dẫn file config YAML (mặc định: config/generator.yaml)",
    )
    sub = parser.add_subparsers(dest="command")
    sub.add_parser("offline", help="Sinh dữ liệu offline (Parquet) — M1")
    sub.add_parser("stream", help="Sinh dữ liệu streaming (NDJSON) — M2")
    sub.add_parser("all", help="Sinh cả offline + streaming")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if not args.command:
        parser.print_help()
        return 0

    cfg = load_config(args.config)
    print(f"[run] command={args.command} | seed={cfg['random_seed']} | config={args.config}")

    if args.command in ("offline", "all"):
        from src.generate_offline import run as run_offline

        run_offline(cfg)
    if args.command in ("stream", "all"):
        from src.generate_stream import run as run_stream

        run_stream(cfg)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
