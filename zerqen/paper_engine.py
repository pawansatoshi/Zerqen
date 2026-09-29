from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, ROUND_DOWN
from typing import Iterable

D = Decimal
ZERO = D("0")
CENT = D("0.01")
RISK_PER_TRADE = D("0.005")
AGGREGATE_OPEN_RISK = D("0.015")
MAX_STRATEGY_ALLOCATION = D("0.60")
MAX_GROSS_EXPOSURE = D("1.0")
DAILY_LOSS = D("0.03")
MAX_DRAWDOWN = D("0.20")
STOP_ATR = D("1.5")
TARGET_R = D("2.0")


@dataclass(frozen=True)
class PaperLimits:
    risk_per_trade: Decimal = RISK_PER_TRADE
    aggregate_open_risk: Decimal = AGGREGATE_OPEN_RISK
    max_positions: int = 3
    max_strategy_allocation: Decimal = MAX_STRATEGY_ALLOCATION
    max_gross_exposure: Decimal = MAX_GROSS_EXPOSURE
    daily_loss: Decimal = DAILY_LOSS
    max_drawdown: Decimal = MAX_DRAWDOWN
    stop_atr: Decimal = STOP_ATR
    target_r: Decimal = TARGET_R


@dataclass(frozen=True)
class RiskResult:
    allowed: bool
    reason: str
    quantity: Decimal
    risk_amount: Decimal
    stop_price: Decimal
    target_price: Decimal


@dataclass
class Position:
    symbol: str
    side: str
    quantity: Decimal
    average_entry: Decimal
    fees: Decimal = ZERO
    funding: Decimal = ZERO
    realized_pnl: Decimal = ZERO

    @property
    def signed_quantity(self) -> Decimal:
        return self.quantity if self.side == "buy" else -self.quantity


def size_for_risk(
    equity: Decimal,
    entry: Decimal,
    atr: Decimal,
    limits: PaperLimits,
    side: str = "buy",
) -> RiskResult:
    if equity <= 0 or entry <= 0 or atr <= 0:
        return RiskResult(False, "invalid market/risk inputs", D("0"), D("0"), D("0"), D("0"))
    stop_distance = atr * limits.stop_atr
    if side == "buy":
        stop = entry - stop_distance
        target = entry + stop_distance * limits.target_r
    else:
        stop = entry + stop_distance
        target = entry - stop_distance * limits.target_r
    if stop <= 0:
        return RiskResult(False, "stop price is non-positive", D("0"), D("0"), stop, target)
    risk_amount = equity * limits.risk_per_trade
    quantity = (risk_amount / stop_distance).quantize(D("0.00000001"), rounding=ROUND_DOWN)
    if quantity <= 0:
        return RiskResult(False, "risk budget produces zero quantity", D("0"), risk_amount, stop, target)
    return RiskResult(True, "risk budget approved", quantity, risk_amount, stop, target)


def check_portfolio_risk(
    equity: Decimal,
    positions: Iterable[Position],
    proposed: RiskResult,
    limits: PaperLimits,
    daily_pnl: Decimal,
    peak_equity: Decimal,
    proposed_notional: Decimal | None = None,
) -> tuple[bool, str]:
    if equity <= 0:
        return False, "non-positive equity"
    positions = list(positions)
    if len(positions) >= limits.max_positions:
        return False, "maximum simultaneous positions reached"
    open_risk = sum((abs(p.quantity * p.average_entry) * limits.risk_per_trade for p in positions), D("0"))
    if open_risk + proposed.risk_amount > equity * limits.aggregate_open_risk:
        return False, "aggregate open risk exceeded"
    gross = sum((abs(p.quantity * p.average_entry) for p in positions), D("0"))
    if proposed_notional is not None and gross + proposed_notional > equity * limits.max_gross_exposure:
        return False, "gross exposure cap exceeded"
    if daily_pnl <= -(equity * limits.daily_loss):
        return False, "daily loss breaker active"
    if peak_equity > 0 and (peak_equity - equity) / peak_equity >= limits.max_drawdown:
        return False, "maximum drawdown breaker active"
    return True, "portfolio risk approved"


def mark_position(position: Position, mark: Decimal) -> Decimal:
    if mark <= 0:
        raise ValueError("mark must be positive")
    return (mark - position.average_entry) * position.signed_quantity


def apply_fill(
    position: Position | None,
    side: str,
    quantity: Decimal,
    price: Decimal,
    fee: Decimal = ZERO,
    funding: Decimal = ZERO,
) -> tuple[Position | None, Decimal]:
    if quantity <= 0 or price <= 0:
        raise ValueError("fill quantity and price must be positive")
    signed = quantity if side == "buy" else -quantity
    if position is None:
        return Position("", side, quantity, price, fee, funding, D("0")), D("0")

    current = position.signed_quantity
    if current == 0 or (current > 0 and signed > 0) or (current < 0 and signed < 0):
        new_qty = abs(current) + quantity
        avg = ((abs(current) * position.average_entry) + quantity * price) / new_qty
        position.quantity = new_qty
        position.average_entry = avg
        position.fees += fee
        position.funding += funding
        return position, D("0")

    closing = min(abs(current), quantity)
    direction = D("1") if current > 0 else D("-1")
    original_qty = abs(current)
    entry_fee_alloc = position.fees * closing / original_qty
    entry_funding_alloc = position.funding * closing / original_qty
    realized = (
        (price - position.average_entry) * closing * direction
        - entry_fee_alloc
        - entry_funding_alloc
        - fee
        - funding
    )
    remaining = quantity - closing
    position.realized_pnl += realized
    position.fees = position.fees - entry_fee_alloc
    position.funding = position.funding - entry_funding_alloc
    if remaining == 0:
        if closing == original_qty:
            return None, realized
        position.quantity = original_qty - closing
        return position, realized
    new_side = "buy" if signed > 0 else "sell"
    return Position(
        position.symbol,
        new_side,
        remaining,
        price,
        fee,
        funding,
        D("0"),
    ), realized


def net_realized_pnl(gross_pnl: Decimal, fees: Decimal, funding: Decimal, slippage: Decimal) -> Decimal:
    return gross_pnl - fees - funding - slippage


def compounding_equity(starting_equity: Decimal, realized_net_pnl: Decimal) -> Decimal:
    """Return the capital base used for compounding; unrealized P&L is excluded."""
    if starting_equity < 0:
        raise ValueError("starting equity cannot be negative")
    return starting_equity + realized_net_pnl
