"""Smoke tests cho M0: config nạp được + CLI parser dựng được."""

from src.run import build_parser
from src.utils.config import load_config


def test_config_loads_with_seed():
    cfg = load_config("config/generator.yaml")
    assert cfg["random_seed"] == 42
    assert cfg["volume"]["n_stores"] == 50


def test_parser_accepts_subcommands():
    parser = build_parser()
    for cmd in ("offline", "stream", "all"):
        args = parser.parse_args([cmd])
        assert args.command == cmd
