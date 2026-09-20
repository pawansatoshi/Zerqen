import pandas as pd

def buy_and_hold_return(frame: pd.DataFrame) -> float:
    if frame.empty:
        return 0.0
    first = float(frame["close"].iloc[0])
    last = float(frame["close"].iloc[-1])
    if first <= 0:
        raise ValueError("first close must be positive")
    return last / first - 1.0

def daily_returns_from_equity(equity: pd.Series) -> pd.Series:
    if equity.empty:
        return pd.Series(dtype=float)
    return equity.resample("1D").last().pct_change().dropna()
