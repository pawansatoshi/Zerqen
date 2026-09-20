import pandas as pd
from .config import StrategyConfig
from .indicators import atr, ema, rsi

def generate_signals(frame: pd.DataFrame, cfg: StrategyConfig) -> pd.DataFrame:
    required = {"open", "high", "low", "close", "volume"}
    missing = required - set(frame.columns)
    if missing:
        raise ValueError(f"Missing columns: {sorted(missing)}")

    out = frame.copy()
    out["ema_fast"] = ema(out["close"], cfg.fast_ema)
    out["ema_slow"] = ema(out["close"], cfg.slow_ema)
    out["rsi"] = rsi(out["close"], cfg.rsi_period)
    out["atr"] = atr(out, cfg.atr_period)

    # Signals use only information available at candle close.
    out["entry"] = (
        (out["ema_fast"] > out["ema_slow"])
        & (out["ema_fast"].shift(1) <= out["ema_slow"].shift(1))
        & (out["rsi"] >= cfg.rsi_min)
        & (out["rsi"] <= cfg.rsi_max)
        & (out["close"] > out["ema_fast"])
    )
    return out
