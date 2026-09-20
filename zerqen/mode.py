from __future__ import annotations
from enum import StrEnum

class TradingMode(StrEnum):
    BACKTEST = "backtest"
    PAPER = "paper"
    TESTNET = "testnet"
    LIVE = "live"

def parse_mode(value: str) -> TradingMode:
    try:
        return TradingMode(value.lower())
    except ValueError as exc:
        raise ValueError(f"unsupported trading mode: {value}") from exc
