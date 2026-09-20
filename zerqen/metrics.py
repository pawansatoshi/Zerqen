import math
import pandas as pd

def summarize_returns(daily_returns: pd.Series) -> dict:
    r = daily_returns.dropna().astype(float)
    if r.empty:
        return {"days": 0, "geometric_return": 0.0, "mean_daily_return": 0.0, "volatility": 0.0}
    geometric = float((1 + r).prod() - 1)
    volatility = float(r.std(ddof=1)) if len(r) > 1 else 0.0
    sharpe = float((r.mean() / volatility) * math.sqrt(365)) if volatility else 0.0
    return {
        "days": int(len(r)),
        "geometric_return": geometric,
        "mean_daily_return": float(r.mean()),
        "volatility": volatility,
        "sharpe_annualized": sharpe,
        "best_day": float(r.max()),
        "worst_day": float(r.min()),
    }
