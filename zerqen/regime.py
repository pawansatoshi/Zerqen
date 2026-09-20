from __future__ import annotations

import pandas as pd

from .indicators import atr, ema


def classify_regime(
    frame: pd.DataFrame,
    fast_period: int = 20,
    slow_period: int = 50,
    atr_period: int = 14,
    volatility_window: int = 50,
    trend_threshold: float = 1.0,
    high_vol_percentile: float = 0.8,
) -> pd.Series:
    """Classify each candle using causal trend and volatility features.

    Labels are: trend_up, trend_down, range, high_volatility.
    Thresholds are research parameters, not trading guarantees.
    """
    required = {"high", "low", "close"}
    missing = required - set(frame.columns)
    if missing:
        raise ValueError(f"Missing columns: {sorted(missing)}")
    if not 0 < high_vol_percentile < 1:
        raise ValueError("high_vol_percentile must be between 0 and 1")

    fast = ema(frame["close"], fast_period)
    slow = ema(frame["close"], slow_period)
    atr_values = atr(frame, atr_period)
    normalized_atr = atr_values / frame["close"].replace(0, pd.NA)
    vol_rank = normalized_atr.rolling(
        volatility_window, min_periods=volatility_window
    ).rank(pct=True)

    result = pd.Series("unknown", index=frame.index, dtype="object")
    result.loc[vol_rank >= high_vol_percentile] = "high_volatility"

    trend_score = (fast - slow).abs() / atr_values.replace(0, pd.NA)
    up = (fast > slow) & (trend_score >= trend_threshold)
    down = (fast < slow) & (trend_score >= trend_threshold)

    result.loc[up & (result != "high_volatility")] = "trend_up"
    result.loc[down & (result != "high_volatility")] = "trend_down"
    result.loc[(~up & ~down) & (result != "high_volatility")] = "range"
    return result
