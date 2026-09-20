import pandas as pd

def compound_daily(equity: float, realized_return: float) -> float:
    """Apply a realized net return to equity. No target forcing is performed."""
    return max(0.0, equity * (1.0 + realized_return))

def equity_curve(daily_returns: pd.Series, starting_capital: float) -> pd.Series:
    if starting_capital <= 0:
        raise ValueError("starting_capital must be positive")
    return starting_capital * (1.0 + daily_returns.fillna(0.0)).cumprod()
