from __future__ import annotations
from dataclasses import dataclass
from .kill_switch import KillSwitch
from .mode import TradingMode
from .orders import Order, OrderSide
from .portfolio_risk import portfolio_risk_check
from .live_guard import LiveLimits, authorize_order

@dataclass(frozen=True)
class OrderAuthorization:
    allowed: bool
    reason: str

def authorize_pipeline(
    mode: TradingMode,
    order: Order,
    equity: float,
    current_drawdown: float,
    daily_loss: float,
    *,
    open_risk_amounts: list[float],
    max_total_risk: float,
    live_limits: LiveLimits,
    kill_switch: KillSwitch,
) -> OrderAuthorization:
    if order.quantity <= 0:
        return OrderAuthorization(False, "quantity must be positive")
    if not order.symbol.strip():
        return OrderAuthorization(False, "symbol is required")
    portfolio = portfolio_risk_check(
        equity,
        open_risk_amounts,
        max_total_risk=max_total_risk,
        current_drawdown=current_drawdown,
        max_drawdown=live_limits.max_drawdown,
    )
    if not portfolio.allowed:
        return OrderAuthorization(False, portfolio.reason)
    notional = equity if order.order_type == "market" else 0.0
    if mode == TradingMode.LIVE:
        decision = authorize_order(
            mode, equity, notional, daily_loss, current_drawdown,
            live_limits, kill_switch,
        )
        return OrderAuthorization(decision.allowed, decision.reason)
    if kill_switch.tripped:
        return OrderAuthorization(False, "kill switch is tripped")
    return OrderAuthorization(True, "order passed integration controls")
