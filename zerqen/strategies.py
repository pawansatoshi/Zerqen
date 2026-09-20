from __future__ import annotations

import pandas as pd

from .indicators import atr, ema, rsi


def _validate(frame: pd.DataFrame) -> None:
    required = {"open", "high", "low", "close", "volume"}
    missing = required - set(frame.columns)
    if missing:
        raise ValueError(f"Missing columns: {sorted(missing)}")


def add_features(frame: pd.DataFrame, fast: int = 20, slow: int = 50,
                  rsi_period: int = 14, atr_period: int = 14) -> pd.DataFrame:
    _validate(frame)
    out = frame.copy()
    out["ema_fast"] = ema(out["close"], fast)
    out["ema_slow"] = ema(out["close"], slow)
    out["rsi"] = rsi(out["close"], rsi_period)
    out["atr"] = atr(out, atr_period)
    return out


def trend_strategy(frame: pd.DataFrame, fast: int = 20, slow: int = 50,
                   rsi_min: float = 50, rsi_max: float = 75) -> pd.Series:
    x = add_features(frame, fast, slow)
    return (
        (x["ema_fast"] > x["ema_slow"])
        & (x["ema_fast"].shift(1) <= x["ema_slow"].shift(1))
        & x["rsi"].between(rsi_min, rsi_max)
        & (x["close"] > x["ema_fast"])
    ).fillna(False)


def mean_reversion_strategy(frame: pd.DataFrame, period: int = 20,
                            rsi_low: float = 30, rsi_high: float = 40) -> pd.Series:
    x = add_features(frame, fast=period, slow=max(period + 1, period * 2))
    return (
        (x["close"] < x["ema_fast"])
        & x["rsi"].between(rsi_low, rsi_high)
        & (x["rsi"].shift(1) < x["rsi"])
    ).fillna(False)


def breakout_strategy(frame: pd.DataFrame, lookback: int = 20,
                      volume_multiplier: float = 1.2) -> pd.Series:
    _validate(frame)
    prior_high = frame["high"].rolling(lookback, min_periods=lookback).max().shift(1)
    prior_volume = frame["volume"].rolling(lookback, min_periods=lookback).mean().shift(1)
    return (
        (frame["close"] > prior_high)
        & (frame["volume"] >= prior_volume * volume_multiplier)
    ).fillna(False)


def volatility_filter(frame: pd.DataFrame, atr_period: int = 14,
                      min_atr_pct: float = 0.002,
                      max_atr_pct: float = 0.05) -> pd.Series:
    _validate(frame)
    values = atr(frame, atr_period) / frame["close"].replace(0, pd.NA)
    return values.between(min_atr_pct, max_atr_pct).fillna(False)


def higher_timeframe_confirmation(
    frame: pd.DataFrame,
    fast: int = 20,
    slow: int = 50,
    bars_per_higher_candle: int = 4,
) -> pd.Series:
    """Confirm direction using the last completed higher-timeframe block.

    The current block is excluded with shift(1), preventing use of an
    incomplete higher-timeframe candle.
    """
    _validate(frame)
    if bars_per_higher_candle < 2:
        raise ValueError("bars_per_higher_candle must be >= 2")

    close = frame["close"]
    block_id = pd.Series(range(len(frame)), index=frame.index) // bars_per_higher_candle
    completed_close = close.groupby(block_id).last().shift(1)
    completed_close = block_id.map(completed_close)
    fast_line = completed_close.ewm(span=fast, adjust=False, min_periods=fast).mean()
    slow_line = completed_close.ewm(span=slow, adjust=False, min_periods=slow).mean()
    return (fast_line > slow_line).fillna(False)
