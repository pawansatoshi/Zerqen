from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, ROUND_DOWN

D = Decimal
ZERO = D("0")

MAX_LEVERAGE = D("5")
DEFAULT_MAINTENANCE_MARGIN = D("0.005")
DEFAULT_FEE_RATE = D("0.001")
DEFAULT_FUNDING_RATE = D("0.0001")
RISK_PER_TRADE = D("0.005")
MAX_MARGIN_ALLOCATION = D("0.60")
MAX_GROSS_EXPOSURE = D("1.00")


@dataclass(frozen=True)
class FuturesLimits:
    max_leverage: Decimal = MAX_LEVERAGE
    maintenance_margin_rate: Decimal = DEFAULT_MAINTENANCE_MARGIN
    fee_rate: Decimal = DEFAULT_FEE_RATE
    funding_rate_per_8h: Decimal = DEFAULT_FUNDING_RATE
    risk_per_trade: Decimal = RISK_PER_TRADE
    max_margin_allocation: Decimal = MAX_MARGIN_ALLOCATION
    max_gross_exposure: Decimal = MAX_GROSS_EXPOSURE


@dataclass(frozen=True)
class FuturesRisk:
    allowed: bool
    reason: str
    quantity: Decimal
    notional: Decimal
    initial_margin: Decimal
    maintenance_margin: Decimal
    liquidation_price: Decimal
    stop_price: Decimal
    target_price: Decimal
    risk_amount: Decimal


@dataclass(frozen=True)
class FuturesMark:
    notional: Decimal
    unrealized_pnl: Decimal
    margin_balance: Decimal
    maintenance_margin: Decimal
    margin_ratio: Decimal
    liquidation_price: Decimal
    liquidated: bool


def validate_leverage(leverage: Decimal, limits: FuturesLimits = FuturesLimits()) -> Decimal:
    if leverage < D("1") or leverage > limits.max_leverage:
        raise ValueError(f"leverage must be between 1x and {limits.max_leverage}x")
    return leverage


def initial_margin(notional: Decimal, leverage: Decimal) -> Decimal:
    validate_leverage(leverage)
    if notional < 0:
        raise ValueError("notional cannot be negative")
    return notional / leverage


def maintenance_margin(notional: Decimal, limits: FuturesLimits = FuturesLimits()) -> Decimal:
    if notional < 0:
        raise ValueError("notional cannot be negative")
    return notional * limits.maintenance_margin_rate


def liquidation_price(
    entry_price: Decimal,
    side: str,
    leverage: Decimal,
    limits: FuturesLimits = FuturesLimits(),
) -> Decimal:
    validate_leverage(leverage, limits)
    if entry_price <= 0:
        raise ValueError("entry price must be positive")
    side = side.lower()
    if side not in {"buy", "sell"}:
        raise ValueError("side must be buy or sell")
    mm = limits.maintenance_margin_rate
    if side == "buy":
        return entry_price * (D("1") - D("1") / leverage + mm)
    return entry_price * (D("1") + D("1") / leverage - mm)


def unrealized_pnl(
    entry_price: Decimal,
    mark_price: Decimal,
    quantity: Decimal,
    side: str,
) -> Decimal:
    if entry_price <= 0 or mark_price <= 0 or quantity < 0:
        raise ValueError("invalid position inputs")
    direction = D("1") if side.lower() == "buy" else D("-1")
    return (mark_price - entry_price) * quantity * direction


def funding_cashflow(
    notional: Decimal,
    funding_rate: Decimal,
    side: str,
) -> Decimal:
    """Cash impact of one funding settlement.

    Positive means cash received by the paper account; negative means paid.
    A positive funding rate is paid by longs and received by shorts.
    """
    if notional < 0:
        raise ValueError("notional cannot be negative")
    direction = D("1") if side.lower() == "buy" else D("-1")
    return -notional * funding_rate * direction


def margin_ratio(margin_balance: Decimal, maintenance: Decimal) -> Decimal:
    if margin_balance <= 0:
        return D("Infinity") if maintenance > 0 else ZERO
    return maintenance / margin_balance


def mark_position(
    entry_price: Decimal,
    mark_price: Decimal,
    quantity: Decimal,
    side: str,
    isolated_margin: Decimal,
    leverage: Decimal,
    limits: FuturesLimits = FuturesLimits(),
) -> FuturesMark:
    notional = mark_price * quantity
    upnl = unrealized_pnl(entry_price, mark_price, quantity, side)
    maintenance = maintenance_margin(notional, limits)
    margin_balance = isolated_margin + upnl
    ratio = margin_ratio(margin_balance, maintenance)
    liq = liquidation_price(entry_price, side, leverage, limits)
    side = side.lower()
    crossed = mark_price <= liq if side == "buy" else mark_price >= liq
    liquidated = crossed or margin_balance <= maintenance
    return FuturesMark(
        notional=notional,
        unrealized_pnl=upnl,
        margin_balance=margin_balance,
        maintenance_margin=maintenance,
        margin_ratio=ratio,
        liquidation_price=liq,
        liquidated=liquidated,
    )


def size_futures_position(
    equity: Decimal,
    entry_price: Decimal,
    stop_price: Decimal,
    side: str,
    leverage: Decimal,
    limits: FuturesLimits = FuturesLimits(),
    target_r: Decimal = D("2"),
) -> FuturesRisk:
    validate_leverage(leverage, limits)
    if equity <= 0 or entry_price <= 0 or stop_price <= 0:
        return FuturesRisk(False, "invalid equity/price inputs", ZERO, ZERO, ZERO, ZERO, ZERO, ZERO, ZERO, ZERO)
    side = side.lower()
    if side not in {"buy", "sell"}:
        return FuturesRisk(False, "side must be buy or sell", ZERO, ZERO, ZERO, ZERO, ZERO, ZERO, ZERO)
    distance = entry_price - stop_price if side == "buy" else stop_price - entry_price
    if distance <= 0:
        return FuturesRisk(False, "stop must be beyond entry", ZERO, ZERO, ZERO, ZERO, ZERO, ZERO, ZERO, ZERO)
    risk_amount = equity * limits.risk_per_trade
    quantity = (risk_amount / distance).quantize(D("0.00000001"), rounding=ROUND_DOWN)
    notional = quantity * entry_price
    margin = initial_margin(notional, leverage)
    if margin > equity * limits.max_margin_allocation:
        max_notional = equity * limits.max_margin_allocation * leverage
        quantity = (max_notional / entry_price).quantize(D("0.00000001"), rounding=ROUND_DOWN)
        notional = quantity * entry_price
        margin = initial_margin(notional, leverage)
    if notional > equity * limits.max_gross_exposure:
        quantity = (equity * limits.max_gross_exposure / entry_price).quantize(D("0.00000001"), rounding=ROUND_DOWN)
        notional = quantity * entry_price
        margin = initial_margin(notional, leverage)
    if quantity <= 0:
        return FuturesRisk(False, "risk budget produces zero quantity", ZERO, ZERO, ZERO, ZERO, ZERO, stop_price, ZERO, risk_amount)
    liq = liquidation_price(entry_price, side, leverage, limits)
    if (side == "buy" and stop_price <= liq) or (side == "sell" and stop_price >= liq):
        return FuturesRisk(False, "stop is beyond liquidation boundary", ZERO, ZERO, ZERO, ZERO, liq, stop_price, ZERO, risk_amount)
    target = entry_price + distance * target_r if side == "buy" else entry_price - distance * target_r
    mm = maintenance_margin(notional, limits)
    return FuturesRisk(True, "futures risk budget approved", quantity, notional, margin, mm, liq, stop_price, target, risk_amount)
