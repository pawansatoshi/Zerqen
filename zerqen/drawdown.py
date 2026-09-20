from __future__ import annotations

import pandas as pd


def equity_drawdown(equity: pd.Series) -> pd.Series:
    values = equity.astype(float)
    peak = values.cummax()
    return values / peak - 1.0


def max_drawdown(equity: pd.Series) -> float:
    if equity.empty:
        return 0.0
    return float(equity_drawdown(equity).min())


def max_drawdown_from_returns(returns: pd.Series, starting_equity: float = 1.0) -> float:
    if starting_equity <= 0:
        raise ValueError("starting_equity must be positive")
    equity = starting_equity * (1.0 + returns.astype(float)).cumprod()
    return max_drawdown(equity)
