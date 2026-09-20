from __future__ import annotations
from dataclasses import dataclass
from .kill_switch import KillSwitch
from .mode import TradingMode

@dataclass(frozen=True)
class LiveLimits:
    max_capital: float
    max_order_notional: float
    max_daily_loss: float
    max_drawdown: float

    def __post_init__(self) -> None:
        if self.max_capital <= 0 or self.max_order_notional <= 0:
            raise ValueError("capital limits must be positive")
        if not 0 < self.max_daily_loss < 1 or not 0 < self.max_drawdown < 1:
            raise ValueError("loss limits must be between 0 and 1")

@dataclass(frozen=True)
class GuardDecision:
    allowed: bool
    reason: str

def authorize_order(
    mode: TradingMode,
    equity: float,
    order_notional: float,
    daily_loss: float,
    drawdown: float,
    limits: LiveLimits,
    kill_switch: KillSwitch,
) -> GuardDecision:
    if mode != TradingMode.LIVE:
        return GuardDecision(False, "live guard requires live mode")
    if kill_switch.tripped:
        return GuardDecision(False, "kill switch is tripped")
    if equity <= 0 or equity > limits.max_capital:
        return GuardDecision(False, "equity outside live capital limit")
    if order_notional <= 0 or order_notional > limits.max_order_notional:
        return GuardDecision(False, "order exceeds live notional limit")
    if daily_loss >= limits.max_daily_loss:
        return GuardDecision(False, "daily loss limit reached")
    if drawdown >= limits.max_drawdown:
        return GuardDecision(False, "maximum drawdown reached")
    return GuardDecision(True, "live order authorized")
