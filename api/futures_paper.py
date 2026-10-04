from __future__ import annotations

import json
import os
import uuid
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from decimal import Decimal as D

from fastapi import APIRouter, Header, HTTPException

from zerqen.futures_paper import (
    DEFAULT_FUNDING_RATE,
    DEFAULT_FEE_RATE,
    FuturesLimits,
    funding_cashflow,
    mark_position,
    maintenance_margin,
    size_futures_position,
    validate_leverage,
)

router = APIRouter(prefix="/api/futures-paper", tags=["futures-paper"])


def _now():
    return datetime.now(timezone.utc)


def _auth(token: str | None):
    expected = os.environ.get("ZERQEN_DASHBOARD_TOKEN")
    if not expected or token != expected:
        raise HTTPException(401, "unauthorized")


def _db():
    import psycopg

    url = os.environ.get("DATABASE_URL")
    if not url:
        raise HTTPException(503, "database unavailable")
    return psycopg.connect(url, connect_timeout=8)


def ensure_schema(conn):
    """Run Futures schema migrations only during explicit account initialization."""
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS zerqen_futures_paper_state (
            account_id TEXT PRIMARY KEY,
            starting_equity NUMERIC NOT NULL,
            cash NUMERIC NOT NULL,
            realized_pnl NUMERIC NOT NULL DEFAULT 0,
            fees NUMERIC NOT NULL DEFAULT 0,
            funding NUMERIC NOT NULL DEFAULT 0,
            slippage NUMERIC NOT NULL DEFAULT 0,
            peak_equity NUMERIC NOT NULL,
            day_start_equity NUMERIC NOT NULL,
            halted BOOLEAN NOT NULL DEFAULT FALSE,
            updated_at TIMESTAMPTZ NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS zerqen_futures_paper_positions (
            position_id TEXT PRIMARY KEY,
            account_id TEXT NOT NULL,
            symbol TEXT NOT NULL,
            side TEXT NOT NULL,
            quantity NUMERIC NOT NULL,
            entry_price NUMERIC NOT NULL,
            leverage NUMERIC NOT NULL,
            initial_margin NUMERIC NOT NULL,
            maintenance_margin NUMERIC NOT NULL,
            liquidation_price NUMERIC NOT NULL,
            stop_price NUMERIC NOT NULL,
            target_price NUMERIC NOT NULL,
            entry_fee NUMERIC NOT NULL DEFAULT 0,
            funding NUMERIC NOT NULL DEFAULT 0,
            realized_pnl NUMERIC NOT NULL DEFAULT 0,
            opened_at TIMESTAMPTZ NOT NULL,
            updated_at TIMESTAMPTZ NOT NULL,
            UNIQUE(account_id, symbol)
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS zerqen_futures_paper_events (
            event_id TEXT PRIMARY KEY,
            account_id TEXT NOT NULL,
            event_type TEXT NOT NULL,
            payload JSONB NOT NULL,
            created_at TIMESTAMPTZ NOT NULL
        )
        """
    )
    # Keep the Futures compounding fields available even when the latest migration
    # has not yet been applied by the deployment bootstrap.
    conn.execute("ALTER TABLE zerqen_futures_paper_state ADD COLUMN IF NOT EXISTS day_start_date DATE")
    conn.execute("ALTER TABLE zerqen_futures_paper_state ADD COLUMN IF NOT EXISTS daily_target NUMERIC")
    conn.execute("ALTER TABLE zerqen_futures_paper_state ADD COLUMN IF NOT EXISTS daily_target_hit BOOLEAN NOT NULL DEFAULT FALSE")
    conn.execute("UPDATE zerqen_futures_paper_state SET day_start_date=COALESCE(day_start_date,CURRENT_DATE), daily_target=COALESCE(daily_target,day_start_equity*1.08) WHERE account_id='default'")
    conn.commit()
    return conn


def _event(conn, event_type: str, payload: dict):
    conn.execute(
        "INSERT INTO zerqen_futures_paper_events(event_id,account_id,event_type,payload,created_at) VALUES(%s,'default',%s,%s,%s)",
        (str(uuid.uuid4()), event_type, json.dumps(payload, default=str), _now()),
    )


def _rollover_day(conn):
    row=conn.execute("SELECT day_start_date,day_start_equity,daily_target,daily_target_hit FROM zerqen_futures_paper_state WHERE account_id='default'").fetchone()
    if not row:
        return
    today=datetime.now(timezone.utc).date()
    if row[0] != today:
        # Equity is recomputed before rollover so the next trading day compounds
        # from actual account equity, including open-position unrealized P&L.
        cash=D(str(conn.execute("SELECT cash FROM zerqen_futures_paper_state WHERE account_id='default'").fetchone()[0]))
        current=cash
        for pos in _positions(conn):
            mark,_=_mark_price(str(pos[1]))
            m=mark_position(D(str(pos[4])),mark,D(str(pos[3])),str(pos[2]),D(str(pos[6])),D(str(pos[5])))
            current += D(str(pos[6])) + m.unrealized_pnl
        conn.execute("UPDATE zerqen_futures_paper_state SET day_start_date=%s,day_start_equity=%s,daily_target=%s,daily_target_hit=FALSE,updated_at=%s WHERE account_id='default'",
                     (today,current,current*D("1.08"),_now()))
        _event(conn,"FUTURES_DAY_ROLLOVER",{"day_start_equity":str(current),"daily_target":str(current*D("1.08")),"date":str(today)})
        conn.commit()

def _state(conn):
    _rollover_day(conn)
    return conn.execute(
        "SELECT account_id,starting_equity,cash,realized_pnl,fees,funding,slippage,peak_equity,day_start_equity,halted,updated_at,day_start_date,daily_target,daily_target_hit FROM zerqen_futures_paper_state WHERE account_id='default'"
    ).fetchone()


def _positions(conn):
    return conn.execute(
        "SELECT position_id,symbol,side,quantity,entry_price,leverage,initial_margin,maintenance_margin,liquidation_price,stop_price,target_price,entry_fee,funding,realized_pnl,opened_at,updated_at FROM zerqen_futures_paper_positions WHERE account_id='default' ORDER BY opened_at"
    ).fetchall()


def _mark_price(symbol: str) -> tuple[D, D | None]:
    clean = symbol.replace("/", "").upper()
    req = urllib.request.Request(
        "https://fapi.binance.com/fapi/v1/premiumIndex?" + urllib.parse.urlencode({"symbol": clean}),
        headers={"User-Agent": "Zerqen-Futures-Paper/1.0"},
    )
    with urllib.request.urlopen(req, timeout=8) as response:
        payload = json.loads(response.read().decode())
    return D(str(payload["markPrice"])), D(str(payload["lastFundingRate"])) if payload.get("lastFundingRate") is not None else None


def _equity(conn):
    state = _state(conn)
    if not state:
        return None
    cash = D(str(state[2]))
    upnl = D(0)
    gross = D(0)
    metrics = []
    for row in _positions(conn):
        mark, _ = _mark_price(str(row[1]))
        m = mark_position(
            D(str(row[4])), mark, D(str(row[3])), str(row[2]),
            D(str(row[6])), D(str(row[5])),
        )
        upnl += m.unrealized_pnl
        gross += m.notional
        metrics.append((row, mark, m))
    equity = cash + sum((D(str(r[6])) for r in _positions(conn)), D(0)) + upnl
    peak = max(D(str(state[7])), equity)
    drawdown = D(0) if peak <= 0 else (peak - equity) / peak
    daily = equity - D(str(state[8]))
    return equity, upnl, gross, drawdown, daily, metrics


def _payload(conn):
    state = _state(conn)
    if not state:
        return {"ok": True, "initialized": False, "mode": "FUTURES_PAPER", "live_trading": False}
    values = _equity(conn)
    eq, upnl, gross, dd, daily, metrics = values
    positions = []
    for row, mark, m in metrics:
        positions.append({
            "position_id": row[0],
            "symbol": row[1],
            "side": row[2],
            "quantity": float(row[3]),
            "entry_price": float(row[4]),
            "mark_price": float(mark),
            "leverage": float(row[5]),
            "initial_margin": float(row[6]),
            "maintenance_margin": float(m.maintenance_margin),
            "liquidation_price": float(m.liquidation_price),
            "margin_balance": float(m.margin_balance),
            "margin_ratio": float(m.margin_ratio),
            "unrealized_pnl": float(m.unrealized_pnl),
            "stop_price": float(row[9]),
            "target_price": float(row[10]),
            "funding": float(row[12]),
            "liquidated": bool(m.liquidated),
        })
    events = conn.execute(
        "SELECT event_type,payload,created_at FROM zerqen_futures_paper_events WHERE account_id='default' ORDER BY created_at DESC LIMIT 30"
    ).fetchall()
    target_hit=bool(state[13]) or eq >= D(str(state[12]))
    if target_hit and not bool(state[13]):
        conn.execute("UPDATE zerqen_futures_paper_state SET daily_target_hit=TRUE,updated_at=%s WHERE account_id='default'",(_now(),))
        _event(conn,"FUTURES_DAILY_TARGET_REACHED",{"equity":str(eq),"target":str(state[12])})
        conn.commit()
    return {
        "ok": True,
        "initialized": True,
        "mode": "FUTURES_PAPER",
        "live_trading": False,
        "margin_mode": "isolated",
        "equity": float(eq),
        "cash": float(state[2]),
        "realized_pnl": float(state[3]),
        "unrealized_pnl": float(upnl),
        "fees": float(state[4]),
        "funding": float(state[5]),
        "slippage": float(state[6]),
        "daily_pnl": float(daily),
        "day_start_equity": float(state[8]),
        "daily_target": float(state[12]),
        "daily_target_hit": bool(target_hit),
        "drawdown": float(dd),
        "gross_exposure": float(gross),
        "halted": bool(state[9]),
        "limits": {
            "risk_per_trade": float(FuturesLimits().risk_per_trade),
            "max_leverage": float(FuturesLimits().max_leverage),
            "max_margin_allocation": float(FuturesLimits().max_margin_allocation),
            "max_gross_exposure": float(FuturesLimits().max_gross_exposure),
            "daily_loss_limit": float(FuturesLimits().daily_loss),
            "max_drawdown": float(FuturesLimits().max_drawdown),
            "max_stop_distance": float(FuturesLimits().max_stop_distance),
            "maintenance_margin_rate": float(FuturesLimits().maintenance_margin_rate),
            "fee_rate": float(FuturesLimits().fee_rate),
            "funding_rate_assumption_per_8h": float(FuturesLimits().funding_rate_per_8h),
        },
        "positions": positions,
        "events": [{"type":r[0],"payload":r[1],"created_at":r[2].isoformat()} for r in events],
    }


def _apply_marks(conn):
    state = _state(conn)
    if not state:
        raise HTTPException(409, "futures paper account is not initialized")
    closed = []
    for row in _positions(conn):
        symbol, side = str(row[1]), str(row[2])
        mark, _ = _mark_price(symbol)
        metrics = mark_position(D(str(row[4])), mark, D(str(row[3])), side), 
        m = metrics[0]
        stop = D(str(row[9]))
        target = D(str(row[10]))
        reason = None
        if m.liquidated:
            reason = "LIQUIDATION"
        elif (side == "buy" and mark <= stop) or (side == "sell" and mark >= stop):
            reason = "STOP_LOSS"
        elif (side == "buy" and mark >= target) or (side == "sell" and mark <= target):
            reason = "TAKE_PROFIT"
        conn.execute("UPDATE zerqen_futures_paper_positions SET updated_at=%s WHERE position_id=%s", (_now(), row[0]))
        if not reason:
            continue
        fee = mark * D(str(row[3])) * DEFAULT_FEE_RATE
        upnl = m.unrealized_pnl
        margin = D(str(row[6]))
        if reason == "LIQUIDATION":
            # Isolated liquidation consumes the isolated collateral in this paper model;
            # no live liquidation/order is sent to an exchange.
            cash_delta = D(0)
            realized = -margin
        else:
            cash_delta = margin + upnl - fee
            realized = upnl - fee
        conn.execute(
            "UPDATE zerqen_futures_paper_state SET cash=cash+%s,realized_pnl=realized_pnl+%s,fees=fees+%s,updated_at=%s WHERE account_id='default'",
            (cash_delta, realized, fee, _now()),
        )
        conn.execute("DELETE FROM zerqen_futures_paper_positions WHERE position_id=%s", (row[0],))
        _event(conn, "FUTURES_POSITION_CLOSED", {
            "position_id": row[0], "symbol": symbol, "side": side,
            "reason": reason, "quantity": str(row[3]), "mark_price": str(mark),
            "realized_pnl": str(realized), "fee": str(fee),
        })
        closed.append({"symbol": symbol, "reason": reason, "realized_pnl": str(realized)})
    return closed


@router.get("")
def status(x_zerqen_dashboard_token: str | None = Header(default=None)):
    _auth(x_zerqen_dashboard_token)
    try:
        with _db() as conn:
            return _payload(conn)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(503, "futures paper state unavailable") from exc


@router.post("")
def action(payload: dict, x_zerqen_dashboard_token: str | None = Header(default=None)):
    _auth(x_zerqen_dashboard_token)
    action_name = str(payload.get("action", "")).lower()
    try:
        with _db() as conn:
            if action_name == "initialize":
                ensure_schema(conn)
                if _state(conn):
                    raise HTTPException(409, "futures paper account already initialized")
                capital = D(str(payload.get("starting_capital", "1000")))
                if capital <= 0:
                    raise HTTPException(400, "starting capital must be positive")
                t = _now()
                conn.execute(
                    "INSERT INTO zerqen_futures_paper_state(account_id,starting_equity,cash,peak_equity,day_start_equity,updated_at) VALUES('default',%s,%s,%s,%s,%s)",
                    (capital, capital, capital, capital, capital, t),
                )
                _event(conn, "FUTURES_PAPER_INITIALIZED", {
                    "starting_capital": str(capital),
                    "margin_mode": "isolated",
                    "live_trading": False,
                })
                conn.commit()
                return _payload(conn)

            if action_name == "reset":
                for table in ("zerqen_futures_paper_events","zerqen_futures_paper_positions","zerqen_futures_paper_state"):
                    conn.execute(f"DELETE FROM {table} WHERE account_id='default'")
                conn.commit()
                return {"ok": True, "reset": True, "live_trading": False}

            if not _state(conn):
                raise HTTPException(409, "initialize futures paper account first")
            if action_name == "halt":
                conn.execute("UPDATE zerqen_futures_paper_state SET halted=TRUE,updated_at=%s WHERE account_id='default'", (_now(),))
                _event(conn, "FUTURES_HALT", {})
                conn.commit()
                return _payload(conn)
            if action_name == "resume":
                conn.execute("UPDATE zerqen_futures_paper_state SET halted=FALSE,updated_at=%s WHERE account_id='default'", (_now(),))
                _event(conn, "FUTURES_RESUME", {})
                conn.commit()
                return _payload(conn)

            if action_name == "open":
                state = _state(conn)
                if state[9]:
                    raise HTTPException(409, "futures paper halt is active")
                if bool(state[13]) or D(str(_equity(conn)[0])) >= D(str(state[12])):
                    conn.execute("UPDATE zerqen_futures_paper_state SET daily_target_hit=TRUE,updated_at=%s WHERE account_id='default'",(_now(),))
                    conn.commit()
                    raise HTTPException(409, "daily 8% target reached; new futures entries are locked until next trading day")
                symbol = str(payload.get("symbol", "BTC/USDT")).upper()
                side = str(payload.get("side", "buy")).lower()
                leverage = D(str(payload.get("leverage", "2")))
                stop = payload.get("stop_price")
                stop_distance_pct = payload.get("stop_distance_pct")
                target = payload.get("target_price")
                entry, _ = _mark_price(symbol)
                if stop is None and stop_distance_pct is None:
                    raise HTTPException(400, "stop_price or stop_distance_pct is required")
                if stop is None:
                    distance = entry * D(str(stop_distance_pct))
                    stop = entry - distance if side == "buy" else entry + distance
                if target is None:
                    distance = abs(entry - D(str(stop)))
                    target = entry + distance * D("2") if side == "buy" else entry - distance * D("2")
                limits = FuturesLimits()
                equity_values = _equity(conn)
                equity, _, gross, drawdown, daily_pnl, _ = equity_values
                if daily_pnl <= -(equity * limits.daily_loss):
                    raise HTTPException(409, "daily loss breaker active")
                if drawdown >= limits.max_drawdown:
                    raise HTTPException(409, "maximum drawdown breaker active")
                risk = size_futures_position(equity, entry, D(str(stop)), side, leverage, limits)
                if not risk.allowed:
                    raise HTTPException(409, risk.reason)
                if conn.execute("SELECT 1 FROM zerqen_futures_paper_positions WHERE account_id='default' AND symbol=%s", (symbol,)).fetchone():
                    raise HTTPException(409, "position already exists for symbol")
                if len(_positions(conn)) >= 3:
                    raise HTTPException(409, "maximum simultaneous futures positions reached")
                fee = risk.notional * limits.fee_rate
                if risk.initial_margin + fee > D(str(state[2])):
                    raise HTTPException(409, "insufficient free futures cash")
                t = _now()
                pid = "fpos-" + uuid.uuid4().hex
                conn.execute(
                    """INSERT INTO zerqen_futures_paper_positions(
                    position_id,account_id,symbol,side,quantity,entry_price,leverage,initial_margin,
                    maintenance_margin,liquidation_price,stop_price,target_price,entry_fee,funding,
                    realized_pnl,opened_at,updated_at)
                    VALUES(%s,'default',%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,0,0,%s,%s)""",
                    (pid,symbol,side,risk.quantity,entry,leverage,risk.initial_margin,risk.maintenance_margin,
                     risk.liquidation_price,risk.stop_price,risk.target_price,fee,t,t),
                )
                conn.execute(
                    "UPDATE zerqen_futures_paper_state SET cash=cash-%s,fees=fees+%s,updated_at=%s WHERE account_id='default'",
                    (risk.initial_margin + fee, fee, t),
                )
                _event(conn, "FUTURES_POSITION_OPENED", {
                    "position_id": pid, "symbol": symbol, "side": side,
                    "quantity": str(risk.quantity), "entry_price": str(entry),
                    "leverage": str(leverage), "initial_margin": str(risk.initial_margin),
                    "liquidation_price": str(risk.liquidation_price),
                    "stop_price": str(risk.stop_price), "target_price": str(risk.target_price),
                })
                conn.commit()
                return _payload(conn)

            if action_name == "mark":
                closed = _apply_marks(conn)
                values = _equity(conn)
                if values:
                    eq = values[0]
                    peak = max(D(str(_state(conn)[7])), eq)
                    conn.execute("UPDATE zerqen_futures_paper_state SET peak_equity=%s,updated_at=%s WHERE account_id='default'", (peak, _now()))
                conn.commit()
                return {**_payload(conn), "closed": closed}

            if action_name == "funding":
                total = D(0)
                for row in _positions(conn):
                    mark, live_rate = _mark_price(str(row[1]))
                    rate = D(str(payload.get("funding_rate", live_rate if live_rate is not None else DEFAULT_FUNDING_RATE)))
                    cashflow = funding_cashflow(mark * D(str(row[3])), rate, str(row[2]))
                    total += cashflow
                    conn.execute(
                        "UPDATE zerqen_futures_paper_positions SET funding=funding+%s,updated_at=%s WHERE position_id=%s",
                        (cashflow, _now(), row[0]),
                    )
                    conn.execute(
                        "UPDATE zerqen_futures_paper_state SET cash=cash+%s,funding=funding+%s,updated_at=%s WHERE account_id='default'",
                        (cashflow, cashflow, _now()),
                    )
                    _event(conn, "FUNDING_SETTLED", {
                        "position_id": row[0], "symbol": row[1], "rate": str(rate),
                        "cashflow": str(cashflow),
                    })
                conn.commit()
                return {**_payload(conn), "funding_cashflow": str(total)}

            if action_name == "partial_close":
                symbol = str(payload.get("symbol", "")).upper()
                row = conn.execute(
                    "SELECT position_id,symbol,side,quantity,entry_price,initial_margin,entry_fee,funding FROM zerqen_futures_paper_positions WHERE account_id='default' AND symbol=%s",
                    (symbol,),
                ).fetchone()
                if not row:
                    raise HTTPException(404, "futures position not found")
                close_qty = D(str(payload.get("quantity", "0")))
                current_qty = D(str(row[3]))
                if close_qty <= 0 or close_qty >= current_qty:
                    raise HTTPException(400, "partial close quantity must be greater than 0 and less than current quantity")
                mark, _ = _mark_price(symbol)
                fraction = close_qty / current_qty
                allocated_margin = D(str(row[5])) * fraction
                allocated_entry_fee = D(str(row[6])) * fraction
                fee = mark * close_qty * DEFAULT_FEE_RATE
                gross = (mark - D(str(row[4]))) * close_qty * (D("1") if str(row[2]) == "buy" else D("-1"))
                realized = gross - allocated_entry_fee - fee
                remaining_qty = current_qty - close_qty
                remaining_margin = D(str(row[5])) - allocated_margin
                remaining_entry_fee = D(str(row[6])) - allocated_entry_fee
                remaining_funding = D(str(row[7])) * (D("1") - fraction)
                conn.execute(
                    """UPDATE zerqen_futures_paper_positions
                    SET quantity=%s,initial_margin=%s,entry_fee=%s,funding=%s,realized_pnl=realized_pnl+%s,updated_at=%s
                    WHERE position_id=%s""",
                    (remaining_qty, remaining_margin, remaining_entry_fee, remaining_funding, realized, _now(), row[0]),
                )
                conn.execute(
                    "UPDATE zerqen_futures_paper_state SET cash=cash+%s,realized_pnl=realized_pnl+%s,fees=fees+%s,updated_at=%s WHERE account_id='default'",
                    (allocated_margin + gross - fee, realized, fee, _now()),
                )
                _event(conn, "FUTURES_PARTIAL_CLOSE", {
                    "position_id": row[0], "symbol": symbol, "side": row[2],
                    "closed_quantity": str(close_qty), "remaining_quantity": str(remaining_qty),
                    "mark_price": str(mark), "realized_pnl": str(realized), "fee": str(fee),
                })
                conn.commit()
                return _payload(conn)

            if action_name == "close":
                symbol = str(payload.get("symbol", "")).upper()
                row = conn.execute(
                    "SELECT position_id,symbol,side,quantity,entry_price,initial_margin,entry_fee,funding FROM zerqen_futures_paper_positions WHERE account_id='default' AND symbol=%s",
                    (symbol,),
                ).fetchone()
                if not row:
                    raise HTTPException(404, "futures position not found")
                mark, _ = _mark_price(symbol)
                fee = mark * D(str(row[3])) * DEFAULT_FEE_RATE
                upnl = (mark - D(str(row[4]))) * D(str(row[3])) * (D("1") if str(row[2]) == "buy" else D("-1"))
                margin = D(str(row[5]))
                cash_delta = margin + upnl - fee
                realized = upnl - fee
                conn.execute(
                    "UPDATE zerqen_futures_paper_state SET cash=cash+%s,realized_pnl=realized_pnl+%s,fees=fees+%s,updated_at=%s WHERE account_id='default'",
                    (cash_delta, realized, fee, _now()),
                )
                conn.execute("DELETE FROM zerqen_futures_paper_positions WHERE position_id=%s", (row[0],))
                _event(conn, "FUTURES_POSITION_CLOSED", {
                    "position_id": row[0], "symbol": symbol, "reason": "MANUAL_CLOSE",
                    "mark_price": str(mark), "realized_pnl": str(realized), "fee": str(fee),
                })
                conn.commit()
                return _payload(conn)

            raise HTTPException(400, "unsupported futures paper action")
    except HTTPException:
        raise
    except (ValueError, ArithmeticError) as exc:
        raise HTTPException(400, str(exc)) from exc
    except Exception as exc:
        raise HTTPException(503, "futures paper operation failed") from exc
