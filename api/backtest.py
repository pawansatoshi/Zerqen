from __future__ import annotations

import urllib.parse
import urllib.request
from datetime import datetime, timezone
from decimal import Decimal as D

from fastapi import APIRouter, HTTPException, Query

router = APIRouter(prefix="/api/backtest", tags=["backtest"])

FEE_RATE = D("0.0005")
SLIPPAGE_RATE = D("0.0005")
RISK_PER_TRADE = D("0.005")
DAILY_TARGET = D("0.08")
DAILY_LOSS_LIMIT = D("0.03")
MAX_DRAWDOWN = D("0.20")
MAX_STOP_DISTANCE = D("0.08")
STOP_ATR = D("1.5")
TARGET_R = D("2.0")
MAX_ALLOCATION = D("0.60")
MAX_FUTURES_LEVERAGE = D(5)
MAINTENANCE_MARGIN = D("0.005")
FUNDING_RATE_ASSUMPTION = D("0.0001")


def _get_json(url: str):
    req = urllib.request.Request(url, headers={"User-Agent": "Zerqen-Backtest/1.0"})
    with urllib.request.urlopen(req, timeout=12) as response:
        return __import__("json").loads(response.read().decode())


def _binance_klines(market_type: str, symbol: str, timeframe: str, limit: int):
    base = "https://api.binance.com/api/v3/klines" if market_type == "spot" else "https://fapi.binance.com/fapi/v1/klines"
    params = {"symbol": symbol.replace("/", "").upper(), "interval": timeframe, "limit": min(limit, 1000)}
    rows = _get_json(base + "?" + urllib.parse.urlencode(params))
    return [[int(r[0]), D(str(r[1])), D(str(r[2])), D(str(r[3])), D(str(r[4])), D(str(r[5]))] for r in rows]


def _ema(values, period):
    k = D(2) / D(period + 1)
    out = []
    for value in values:
        out.append(value if not out else value * k + out[-1] * (D(1) - k))
    return out


def _rsi(values, period=14):
    out = [None] * len(values)
    gains = losses = D(0)
    avg_gain = avg_loss = D(0)
    for i in range(1, len(values)):
        change = values[i] - values[i - 1]
        gain, loss = max(change, D(0)), max(-change, D(0))
        if i <= period:
            gains += gain
            losses += loss
            if i == period:
                avg_gain, avg_loss = gains / D(period), losses / D(period)
        else:
            avg_gain = (avg_gain * D(period - 1) + gain) / D(period)
            avg_loss = (avg_loss * D(period - 1) + loss) / D(period)
        if i >= period:
            out[i] = D(100) if avg_loss == 0 else D(100) - D(100) / (D(1) + avg_gain / avg_loss)
    return out


def _atr(rows, period=14):
    out = [None] * len(rows)
    trs = []
    for i, row in enumerate(rows):
        prev = rows[i - 1][4] if i else row[4]
        trs.append(max(row[2] - row[3], abs(row[2] - prev), abs(row[3] - prev)))
    if len(trs) <= period:
        return out
    value = sum(trs[1:period + 1], D(0)) / D(period)
    out[period] = value
    for i in range(period + 1, len(trs)):
        value = (value * D(period - 1) + trs[i]) / D(period)
        out[i] = value
    return out


def _regime(rows, i, ema9, ema21, rsi):
    if i < 1 or rsi[i] is None:
        return "RANGE", None
    if ema9[i] > ema21[i] and ema9[i - 1] <= ema21[i - 1] and D(50) <= rsi[i] <= D(75):
        return "TREND_UP", "BUY"
    if ema9[i] < ema21[i] and ema9[i - 1] >= ema21[i - 1] and D(25) <= rsi[i] <= D(50):
        return "TREND_DOWN", "SELL"
    return ("TREND_UP" if ema9[i] > ema21[i] else "TREND_DOWN" if ema9[i] < ema21[i] else "RANGE"), None


def _volatility_ok(rows, i, atr):
    if not atr[i] or rows[i][4] <= 0:
        return False
    atr_pct = atr[i] / rows[i][4]
    max_bar = max((abs(r[4] - r[1]) / r[1] for r in rows[max(0, i - 19):i + 1] if r[1] > 0), default=D(0))
    return atr_pct <= D("0.05") and max_bar <= D("0.08")


def _structural_stop(rows, i, side, atr):
    entry = rows[i][4]
    atr_distance = atr[i] * STOP_ATR
    lookback = rows[max(0, i - 5):i + 1]
    if side == "buy":
        structure = min(r[3] for r in lookback)
        stop = min(entry - atr_distance, structure)
        distance = entry - stop
    else:
        structure = max(r[2] for r in lookback)
        stop = max(entry + atr_distance, structure)
        distance = stop - entry
    if distance <= 0 or distance > entry * MAX_STOP_DISTANCE:
        return None
    return stop, entry + (distance * TARGET_R if side == "buy" else -distance * TARGET_R)


def _liq_price(entry, side, leverage):
    if leverage <= D(1):
        return D(0)
    if side == "buy":
        return entry * (D(1) - D(1) / leverage + MAINTENANCE_MARGIN)
    return entry * (D(1) + D(1) / leverage - MAINTENANCE_MARGIN)


def _pct(x):
    return float(x * D(100))


@router.get("")
def backtest(
    market_type: str = Query("spot"),
    symbol: str = Query("BTC/USDT"),
    timeframe: str = Query("1h"),
    starting_capital: float = Query(10000, gt=0),
    leverage: float = Query(2, ge=1, le=5),
    limit: int = Query(1000, ge=100, le=1000),
):
    if market_type not in {"spot", "futures"}:
        raise HTTPException(400, "market_type must be spot or futures")
    if timeframe not in {"1h", "4h", "1d", "1w"}:
        raise HTTPException(400, "unsupported timeframe")
    if market_type == "spot":
        leverage = 1.0
    lev = D(str(leverage))
    if lev > MAX_FUTURES_LEVERAGE:
        raise HTTPException(400, "leverage exceeds backtest maximum")
    capital = D(str(starting_capital))

    try:
        rows = _binance_klines(market_type, symbol, timeframe, limit)
    except Exception as exc:
        raise HTTPException(502, "historical market data unavailable") from exc
    if len(rows) < 40:
        raise HTTPException(502, "not enough historical candles")

    closes = [r[4] for r in rows]
    ema9, ema21, rsi, atr = _ema(closes, 9), _ema(closes, 21), _rsi(closes), _atr(rows)
    cash = capital
    peak = capital
    day_start = capital
    day_key = datetime.fromtimestamp(rows[0][0] / 1000, tz=timezone.utc).date()
    daily_locked = False
    position = None
    trades = []
    equity_curve = []
    rejected = {"volatility": 0, "stop_distance": 0, "risk": 0, "daily": 0}
    funding_total = D(0)
    fees_total = D(0)
    slippage_total = D(0)

    def mark(price):
        if not position:
            return cash
        direction = D(1) if position["side"] == "buy" else D(-1)
        return cash + direction * (price - position["entry"]) * position["qty"]

    for i in range(21, len(rows)):
        row = rows[i]
        ts = datetime.fromtimestamp(row[0] / 1000, tz=timezone.utc)
        if ts.date() != day_key:
            day_key = ts.date()
            day_start = mark(rows[i - 1][4])
            daily_locked = False

        current_equity = mark(row[4])
        peak = max(peak, current_equity)
        drawdown = D(0) if peak <= 0 else (peak - current_equity) / peak
        daily_pnl = current_equity - day_start
        if daily_pnl >= day_start * DAILY_TARGET or daily_pnl <= -day_start * DAILY_LOSS_LIMIT or drawdown >= MAX_DRAWDOWN:
            daily_locked = True

        if position:
            # Futures funding is explicitly an assumption because Binance candle history does not contain funding rates.
            if market_type == "futures" and i % 8 == 0:
                funding = position["entry"] * position["qty"] * FUNDING_RATE_ASSUMPTION * (D(1) if position["side"] == "buy" else D(-1))
                cash -= funding
                funding_total += funding
                position["funding"] += funding
            hit = None
            if market_type == "futures":
                liq = position["liq"]
                if (position["side"] == "buy" and row[3] <= liq) or (position["side"] == "sell" and row[2] >= liq):
                    hit = ("LIQUIDATION", liq)
            if not hit and position["side"] == "buy":
                if row[3] <= position["stop"]:
                    hit = ("STOP_LOSS", position["stop"])
                elif row[2] >= position["target"]:
                    hit = ("TAKE_PROFIT", position["target"])
            elif not hit and position["side"] == "sell":
                if row[2] >= position["stop"]:
                    hit = ("STOP_LOSS", position["stop"])
                elif row[3] <= position["target"]:
                    hit = ("TAKE_PROFIT", position["target"])
            if hit:
                reason, exit_price = hit
                fill = exit_price * (D(1) - SLIPPAGE_RATE if position["side"] == "buy" else D(1) + SLIPPAGE_RATE)
                gross = (fill - position["entry"]) * position["qty"] * (D(1) if position["side"] == "buy" else D(-1))
                exit_fee = fill * position["qty"] * FEE_RATE
                cash += gross - exit_fee
                fees_total += exit_fee
                slippage_total += abs(fill - exit_price) * position["qty"]
                net = gross - position["entry_fee"] - exit_fee - position["funding"]
                trades.append({
                    "entry_time": position["time"].isoformat(),
                    "exit_time": ts.isoformat(),
                    "side": position["side"].upper(),
                    "entry": float(position["entry"]),
                    "exit": float(fill),
                    "quantity": float(position["qty"]),
                    "gross_pnl": float(gross),
                    "net_pnl": float(net),
                    "reason": reason,
                    "r_multiple": float(net / position["risk"] if position["risk"] else D(0)),
                    "leverage": float(lev),
                })
                position = None
                current_equity = cash

        if not position and not daily_locked:
            _, signal = _regime(rows, i, ema9, ema21, rsi)
            if signal and not _volatility_ok(rows, i, atr):
                rejected["volatility"] += 1
            elif signal:
                stop_target = _structural_stop(rows, i, signal.lower(), atr)
                if not stop_target:
                    rejected["stop_distance"] += 1
                else:
                    stop, target = stop_target
                    entry = row[4] * (D(1) + SLIPPAGE_RATE if signal == "BUY" else D(1) - SLIPPAGE_RATE)
                    risk_cash = current_equity * RISK_PER_TRADE
                    distance = abs(entry - stop)
                    qty = risk_cash / distance if distance > 0 else D(0)
                    max_notional = current_equity * (MAX_ALLOCATION if market_type == "spot" else lev)
                    qty = min(qty, max_notional / entry if entry else D(0))
                    margin = entry * qty / lev
                    if qty <= 0 or (market_type == "futures" and margin > current_equity):
                        rejected["risk"] += 1
                    else:
                        entry_fee = entry * qty * FEE_RATE
                        cash -= entry_fee
                        fees_total += entry_fee
                        liquidation = _liq_price(entry, signal.lower(), lev)
                        position = {
                            "side": signal.lower(),
                            "entry": entry,
                            "qty": qty,
                            "stop": stop,
                            "target": target,
                            "liq": liquidation,
                            "risk": risk_cash,
                            "entry_fee": entry_fee,
                            "funding": D(0),
                            "time": ts,
                        }

        eq = mark(row[4])
        peak = max(peak, eq)
        equity_curve.append({"time": ts.isoformat(), "equity": float(eq)})

    if position:
        exit_price = rows[-1][4]
        gross = (exit_price - position["entry"]) * position["qty"] * (D(1) if position["side"] == "buy" else D(-1))
        fee = exit_price * position["qty"] * FEE_RATE
        cash += gross - fee
        fees_total += fee
        trades.append({
            "entry_time": position["time"].isoformat(),
            "exit_time": datetime.fromtimestamp(rows[-1][0] / 1000, tz=timezone.utc).isoformat(),
            "side": position["side"].upper(),
            "entry": float(position["entry"]),
            "exit": float(exit_price),
            "quantity": float(position["qty"]),
            "gross_pnl": float(gross),
            "net_pnl": float(gross - position["entry_fee"] - fee - position["funding"]),
            "reason": "END_OF_TEST",
            "r_multiple": float((gross - position["entry_fee"] - fee) / position["risk"] if position["risk"] else D(0)),
            "leverage": float(lev),
        })

    final_equity = cash
    net_pnl = final_equity - capital
    wins = sum(1 for t in trades if t["net_pnl"] > 0)
    losses = sum(1 for t in trades if t["net_pnl"] < 0)
    gross_wins = sum(t["net_pnl"] for t in trades if t["net_pnl"] > 0)
    gross_losses = abs(sum(t["net_pnl"] for t in trades if t["net_pnl"] < 0))
    profit_factor = float(gross_wins / gross_losses) if gross_losses else (float("inf") if gross_wins else 0.0)
    running_peak = capital
    max_drawdown = D(0)
    for point in equity_curve:
        eq_point = D(str(point["equity"]))
        running_peak = max(running_peak, eq_point)
        if running_peak > 0:
            max_drawdown = max(max_drawdown, (running_peak - eq_point) / running_peak)

    return {
        "ok": True,
        "mode": "BACKTEST",
        "market_type": market_type,
        "exchange": "binance",
        "symbol": symbol.upper(),
        "timeframe": timeframe,
        "candles": len(rows),
        "from": datetime.fromtimestamp(rows[0][0] / 1000, tz=timezone.utc).isoformat(),
        "to": datetime.fromtimestamp(rows[-1][0] / 1000, tz=timezone.utc).isoformat(),
        "starting_equity": float(capital),
        "final_equity": float(final_equity),
        "net_pnl": float(net_pnl),
        "return_pct": _pct(net_pnl / capital),
        "trades": len(trades),
        "wins": wins,
        "losses": losses,
        "win_rate_pct": float(D(wins) / D(len(trades)) * D(100)) if trades else 0.0,
        "profit_factor": profit_factor,
        "max_drawdown_pct": _pct(max_drawdown),
        "fees": float(fees_total),
        "funding": float(funding_total),
        "slippage": float(slippage_total),
        "leverage": float(lev),
        "assumptions": {
            "risk_per_trade": float(RISK_PER_TRADE),
            "daily_target": float(DAILY_TARGET),
            "daily_loss_limit": float(DAILY_LOSS_LIMIT),
            "max_drawdown": float(MAX_DRAWDOWN),
            "max_stop_distance": float(MAX_STOP_DISTANCE),
            "target_r": float(TARGET_R),
            "fee_rate_each_side": float(FEE_RATE),
            "slippage_rate_each_side": float(SLIPPAGE_RATE),
            "futures_maintenance_margin": float(MAINTENANCE_MARGIN),
            "futures_funding_rate_assumption_per_8h": float(FUNDING_RATE_ASSUMPTION),
        },
        "rejected": rejected,
        "equity_curve": equity_curve[-250:],
        "recent_trades": trades[-50:],
        "warning": "Historical backtest is a research simulation, not a guarantee of future performance. Futures funding is modeled as an explicit assumption rather than historical funding data.",
    }
