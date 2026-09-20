from dataclasses import dataclass

@dataclass(frozen=True)
class RiskDecision:
    allowed: bool
    quantity: float
    stop_price: float
    target_price: float
    risk_amount: float

def position_size(
    equity: float,
    entry: float,
    stop: float,
    risk_per_trade: float,
    target_rr: float,
) -> RiskDecision:
    if equity <= 0 or entry <= 0 or stop <= 0 or entry <= stop:
        return RiskDecision(False, 0.0, stop, entry, 0.0)

    risk_amount = equity * risk_per_trade
    per_unit_risk = entry - stop
    quantity = risk_amount / per_unit_risk
    target = entry + per_unit_risk * target_rr
    return RiskDecision(True, quantity, stop, target, risk_amount)

def daily_loss_breached(day_start_equity: float, equity: float, max_daily_loss: float) -> bool:
    if day_start_equity <= 0:
        return True
    return (day_start_equity - equity) / day_start_equity >= max_daily_loss

def drawdown_breached(equity: float, peak_equity: float, max_drawdown: float) -> bool:
    if peak_equity <= 0:
        return True
    return (peak_equity - equity) / peak_equity >= max_drawdown
