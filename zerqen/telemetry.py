from __future__ import annotations
from dataclasses import dataclass

@dataclass(frozen=True)
class PortfolioSnapshot:
    equity: float
    peak_equity: float
    drawdown: float
    daily_return: float
    open_positions: int
    gross_exposure: float

def snapshot(equity: float, peak_equity: float, day_start_equity: float, open_positions: int, gross_exposure: float) -> PortfolioSnapshot:
    if equity < 0 or peak_equity <= 0 or day_start_equity <= 0:
        raise ValueError("equity values must be positive")
    return PortfolioSnapshot(
        equity, peak_equity, 1.0 - equity / peak_equity,
        equity / day_start_equity - 1.0, open_positions, gross_exposure,
    )
