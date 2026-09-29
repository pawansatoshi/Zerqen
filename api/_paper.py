from __future__ import annotations

# Demo execution path: real exchange market data, simulated fills, zero live capital.

import json
import os
import uuid
from decimal import Decimal as D
from http.server import BaseHTTPRequestHandler
from datetime import datetime, timezone

from zerqen.paper_engine import PaperLimits, Position, apply_fill, check_portfolio_risk, compounding_equity, size_for_risk
from zerqen.strategy_registry import eligible_strategies


def send(handler, status, payload):
    body = json.dumps(payload, default=str, separators=(",", ":")).encode()
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json")
    handler.send_header("Cache-Control", "no-store")
    handler.end_headers()
    handler.wfile.write(body)


def auth_ok(handler):
    expected = os.environ.get("ZERQEN_DASHBOARD_TOKEN")
    return bool(expected) and handler.headers.get("x-zerqen-dashboard-token") == expected


def db():
    import psycopg

    url = os.environ.get("DATABASE_URL")
    if not url:
        raise RuntimeError("database unavailable")
    conn = psycopg.connect(url, connect_timeout=8)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS zerqen_paper_state (
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
            flatten_requested BOOLEAN NOT NULL DEFAULT FALSE,
            paused BOOLEAN NOT NULL DEFAULT FALSE,
            exchange_id TEXT NOT NULL DEFAULT 'binance',
            symbol TEXT NOT NULL DEFAULT 'BTC/USDT',
            timeframe TEXT NOT NULL DEFAULT '1h',
            last_marked_at TIMESTAMPTZ,
            updated_at TIMESTAMPTZ NOT NULL
        )
    """)
    conn.execute("ALTER TABLE zerqen_paper_state ADD COLUMN IF NOT EXISTS paused BOOLEAN NOT NULL DEFAULT FALSE")
    conn.execute("ALTER TABLE zerqen_paper_state ADD COLUMN IF NOT EXISTS exchange_id TEXT NOT NULL DEFAULT 'binance'")
    conn.execute("ALTER TABLE zerqen_paper_state ADD COLUMN IF NOT EXISTS symbol TEXT NOT NULL DEFAULT 'BTC/USDT'")
    conn.execute("ALTER TABLE zerqen_paper_state ADD COLUMN IF NOT EXISTS timeframe TEXT NOT NULL DEFAULT '1h'")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS zerqen_paper_orders (
            client_order_id TEXT PRIMARY KEY,
            account_id TEXT NOT NULL,
            symbol TEXT NOT NULL,
            side TEXT NOT NULL,
            order_type TEXT NOT NULL,
            quantity NUMERIC NOT NULL,
            price NUMERIC,
            stop_price NUMERIC,
            target_price NUMERIC,
            status TEXT NOT NULL,
            filled_quantity NUMERIC NOT NULL DEFAULT 0,
            average_price NUMERIC,
            strategy TEXT,
            regime TEXT,
            reason TEXT,
            created_at TIMESTAMPTZ NOT NULL,
            updated_at TIMESTAMPTZ NOT NULL
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS zerqen_paper_fills (
            fill_id TEXT PRIMARY KEY,
            client_order_id TEXT NOT NULL,
            account_id TEXT NOT NULL,
            symbol TEXT NOT NULL,
            side TEXT NOT NULL,
            quantity NUMERIC NOT NULL,
            price NUMERIC NOT NULL,
            fee NUMERIC NOT NULL DEFAULT 0,
            funding NUMERIC NOT NULL DEFAULT 0,
            slippage NUMERIC NOT NULL DEFAULT 0,
            created_at TIMESTAMPTZ NOT NULL
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS zerqen_paper_positions (
            account_id TEXT NOT NULL,
            symbol TEXT NOT NULL,
            side TEXT NOT NULL,
            quantity NUMERIC NOT NULL,
            average_entry NUMERIC NOT NULL,
            fees NUMERIC NOT NULL DEFAULT 0,
            funding NUMERIC NOT NULL DEFAULT 0,
            realized_pnl NUMERIC NOT NULL DEFAULT 0,
            updated_at TIMESTAMPTZ NOT NULL,
            PRIMARY KEY(account_id, symbol)
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS zerqen_paper_equity_snapshots (
            id BIGSERIAL PRIMARY KEY,
            account_id TEXT NOT NULL,
            equity NUMERIC NOT NULL,
            cash NUMERIC NOT NULL,
            realized_pnl NUMERIC NOT NULL,
            unrealized_pnl NUMERIC NOT NULL,
            drawdown NUMERIC NOT NULL,
            daily_pnl NUMERIC NOT NULL,
            created_at TIMESTAMPTZ NOT NULL
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS zerqen_paper_events (
            event_id TEXT PRIMARY KEY,
            account_id TEXT NOT NULL,
            event_type TEXT NOT NULL,
            payload JSONB NOT NULL,
            created_at TIMESTAMPTZ NOT NULL
        )
    """)
    from api.ledger import _ensure_schema
    _ensure_schema(conn)
    conn.commit()
    return conn


def now():
    return datetime.now(timezone.utc)


def get_state(conn):
    row = conn.execute(
        "SELECT account_id, starting_equity, cash, realized_pnl, fees, funding, slippage, peak_equity, day_start_equity, halted, flatten_requested, paused, exchange_id, symbol, timeframe, last_marked_at, updated_at FROM zerqen_paper_state WHERE account_id='default'"
    ).fetchone()
    return row


def fetch_positions(conn):
    rows = conn.execute(
        "SELECT symbol, side, quantity, average_entry, fees, funding, realized_pnl FROM zerqen_paper_positions WHERE account_id='default' AND quantity > 0"
    ).fetchall()
    return [
        Position(str(r[0]), str(r[1]), D(str(r[2])), D(str(r[3])), D(str(r[4])), D(str(r[5])), D(str(r[6])))
        for r in rows
    ]


def fetch_public_market(exchange_id, symbol, timeframe="1h", limit=120):
    from api.market import public_market_probe
    result = public_market_probe(exchange_id, symbol, timeframe, limit)
    if result.get("connectivity_status") not in {"WORKING", "DEGRADED"}:
        raise RuntimeError(result.get("error_type") or "public market unavailable")
    closes = result.get("closes") or []
    ticker = result.get("ticker_data") or {}
    if not closes or ticker.get("last") is None:
        raise RuntimeError("public market data incomplete")
    rows = [
        [result["times"][i], result["opens"][i], result["highs"][i], result["lows"][i], result["closes"][i], result["volumes"][i]]
        for i in range(len(result["closes"]))
    ]
    return D(str(ticker["last"])), rows


def fetch_prices(exchange_id, symbols, timeframe="1h"):
    return {symbol: fetch_public_market(exchange_id, symbol, timeframe, 60)[0] for symbol in symbols}


def fetch_candles(exchange_id, symbol, timeframe="1h", limit=120):
    return fetch_public_market(exchange_id, symbol, timeframe, limit)[1]


def indicators(rows):
    closes = [D(str(r[4])) for r in rows]
    highs = [D(str(r[2])) for r in rows]
    lows = [D(str(r[3])) for r in rows]
    ema9, ema21 = [], []
    k9, k21 = D("0.2"), D(2) / D(22)
    for i, x in enumerate(closes):
        ema9.append(x if i == 0 else x * k9 + ema9[-1] * (1-k9))
        ema21.append(x if i == 0 else x * k21 + ema21[-1] * (1-k21))
    trs = []
    for i, x in enumerate(closes):
        prev = closes[i-1] if i else x
        trs.append(max(highs[i]-lows[i], abs(highs[i]-prev), abs(lows[i]-prev)))
    atr = sum(trs[-14:]) / D(14) if len(trs) >= 14 else D(0)
    rsi = D(50)
    if len(closes) >= 15:
        gains = [max(closes[i]-closes[i-1], D(0)) for i in range(len(closes)-14, len(closes))]
        losses = [max(closes[i-1]-closes[i], D(0)) for i in range(len(closes)-14, len(closes))]
        avg_gain, avg_loss = sum(gains)/D(14), sum(losses)/D(14)
        rsi = D(100) if avg_loss == 0 else D(100) - D(100)/(D(1) + avg_gain/avg_loss)
    return closes, ema9, ema21, atr, rsi


def equity(conn, prices):
    state = get_state(conn)
    if not state:
        return None
    cash = D(str(state[2]))
    unrealized = D(0)
    gross = D(0)
    for p in fetch_positions(conn):
        mark = prices.get(p.symbol)
        if mark:
            unrealized += (mark - p.average_entry) * p.signed_quantity
            gross += abs(mark * p.quantity)
    market_value = sum(
        (prices[p.symbol] * p.signed_quantity for p in fetch_positions(conn) if p.symbol in prices),
        D(0),
    )
    eq = cash + market_value
    peak = D(str(state[7]))
    dd = D(0) if peak <= 0 else max(D(0), (peak-eq)/peak)
    day_start = D(str(state[8]))
    daily = eq-day_start
    return eq, unrealized, gross, dd, daily


def snapshot(conn, prices):
    state = get_state(conn)
    if not state:
        return None
    values = equity(conn, prices)
    if not values:
        return None
    eq, unrealized, gross, dd, daily = values
    t = now()
    risk_row = conn.execute("SELECT COALESCE(SUM(risk_at_entry),0) FROM zerqen_paper_positions WHERE account_id='default' AND quantity > 0").fetchone()
    open_risk = D(str(risk_row[0] or 0))
    allocation = D(0) if eq <= 0 else gross / eq
    cumulative = eq - D(str(state[1]))
    snapshot_id=conn.execute(
        "INSERT INTO zerqen_paper_equity_snapshots(account_id,equity,cash,realized_pnl,unrealized_pnl,drawdown,daily_pnl,gross_exposure,open_risk,allocation,cumulative_pnl,created_at) VALUES('default',%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id",
        (eq, D(str(state[2])), D(str(state[3])), unrealized, dd, daily, gross, open_risk, allocation, cumulative, t),
    ).fetchone()[0]
    conn.execute(
        "UPDATE zerqen_paper_state SET peak_equity=GREATEST(peak_equity,%s),last_marked_at=%s,updated_at=%s WHERE account_id='default'",
        (eq, t, t),
    )
    return eq, unrealized, gross, dd, daily, snapshot_id


def status_payload(conn):
    state = get_state(conn)
    if not state:
        return {"ok": True, "initialized": False, "mode": "PAPER", "live_trading": False}
    symbols = [str(state[13])]
    prices = {}
    try:
        prices = fetch_prices(str(state[12]), symbols, str(state[14]))
    except Exception:  # noqa: BLE001
        prices = {}
    values = equity(conn, prices) if prices else None
    eq = values[0] if values else D(str(state[2]))
    unrealized = values[1] if values else D(0)
    gross = values[2] if values else D(0)
    dd = values[3] if values else D(0)
    daily = values[4] if values else D(str(state[2]))-D(str(state[8]))
    positions = conn.execute(
        "SELECT symbol,side,quantity,average_entry,fees,funding,realized_pnl FROM zerqen_paper_positions WHERE account_id='default' AND quantity > 0 ORDER BY symbol"
    ).fetchall()
    orders = conn.execute(
        "SELECT client_order_id,symbol,side,order_type,quantity,price,status,filled_quantity,average_price,strategy,regime,reason,created_at,updated_at FROM zerqen_paper_orders WHERE account_id='default' ORDER BY created_at DESC LIMIT 50"
    ).fetchall()
    events = conn.execute(
        "SELECT event_type,payload,created_at FROM zerqen_paper_events WHERE account_id='default' ORDER BY created_at DESC LIMIT 50"
    ).fetchall()
    return {
        "ok": True,
        "initialized": True,
        "mode": "PAPER",
        "live_trading": False,
        "research_hurdle": 0.08,
        "research_hurdle_label": "Research hurdle — not a trading requirement",
        "equity": float(eq),
        "cash": float(state[2]),
        "realized_pnl": float(state[3]),
        "unrealized_pnl": float(unrealized),
        "fees": float(state[4]),
        "funding": float(state[5]),
        "slippage": float(state[6]),
        "daily_pnl": float(daily),
        "drawdown": float(dd),
        "gross_exposure": float(gross),
        "halted": bool(state[9]),
        "flatten_requested": bool(state[10]),
        "paused": bool(state[11]),
        "exchange_id": str(state[12]),
        "symbol": str(state[13]),
        "timeframe": str(state[14]),
        "prices": {k: float(v) for k,v in prices.items()},
        "positions": [
            {"symbol":r[0],"side":r[1],"quantity":float(r[2]),"average_entry":float(r[3]),"fees":float(r[4]),"funding":float(r[5]),"realized_pnl":float(r[6])}
            for r in positions
        ],
        "orders": [
            {"client_order_id":r[0],"symbol":r[1],"side":r[2],"type":r[3],"quantity":float(r[4]),"price":float(r[5]) if r[5] is not None else None,"status":r[6],"filled_quantity":float(r[7]),"average_price":float(r[8]) if r[8] is not None else None,"strategy":r[9],"regime":r[10],"reason":r[11],"created_at":r[12].isoformat(),"updated_at":r[13].isoformat()}
            for r in orders
        ],
        "events": [{"type":r[0],"payload":r[1],"created_at":r[2].isoformat()} for r in events],
        "limits": {k: float(v) if isinstance(v, D) else v for k,v in PaperLimits().__dict__.items()},
    }


def record_decision(conn, state, *, signal_id, strategy, regime, signal_timestamp, signal_direction, ema9, ema21, rsi, atr, risk_per_trade, aggregate_open_risk, open_positions, daily_loss, drawdown, gross_exposure, allocation, risk_decision, rejected, rejection_reason=None, order_id=None):
    decision_id=str(uuid.uuid4())
    conn.execute(
        """INSERT INTO zerqen_paper_decisions(decision_id,account_id,signal_id,exchange_id,symbol,timeframe,strategy,regime,signal_timestamp,signal_direction,ema9,ema21,rsi,atr,risk_per_trade,aggregate_open_risk,open_positions,daily_loss,drawdown,gross_exposure,allocation,risk_decision,rejected,rejection_reason,order_id)
        VALUES(%s,'default',%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
        (decision_id,signal_id,str(state[12]),str(state[13]),str(state[14]),strategy,regime,signal_timestamp,signal_direction,ema9,ema21,rsi,atr,risk_per_trade,aggregate_open_risk,open_positions,daily_loss,drawdown,gross_exposure,allocation,risk_decision,rejected,rejection_reason,order_id),
    )
    return decision_id


def event(conn, event_type, payload):
    event_id=str(uuid.uuid4())
    conn.execute(
        "INSERT INTO zerqen_paper_events(event_id,account_id,event_type,payload,created_at) VALUES(%s,'default',%s,%s,%s)",
        (event_id, event_type, json.dumps(payload, default=str), now()),
    )
    return event_id


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if not auth_ok(self):
            return send(self, 401, {"ok":False,"error":"unauthorized"})
        try:
            with db() as conn:
                return send(self, 200, status_payload(conn))
        except Exception:  # noqa: BLE001
            return send(self, 503, {"ok":False,"error":"paper state unavailable"})

    def do_POST(self):
        if not auth_ok(self):
            return send(self, 401, {"ok":False,"error":"unauthorized"})
        try:
            length=int(self.headers.get("Content-Length","0"))
            data=json.loads(self.rfile.read(length) or b"{}")
            action=data.get("action")
            with db() as conn:
                if action=="initialize":
                    capital=D(str(data.get("starting_capital","0")))
                    if capital <= 0:
                        return send(self,400,{"ok":False,"error":"starting capital must be explicitly set and positive"})
                    existing=get_state(conn)
                    if existing:
                        return send(self,409,{"ok":False,"error":"paper account already initialized; reset before reinitializing"})
                    t=now()
                    exchange_id=str(data.get("exchange_id","binance"))
                    symbol=str(data.get("symbol","BTC/USDT"))
                    timeframe=str(data.get("timeframe","1h"))
                    if exchange_id not in {"binance","okx","bybit","bitget","mexc","kucoin","gate","delta_india","coindcx","wazirx"}:
                        return send(self,400,{"ok":False,"error":"unsupported paper market exchange"})
                    if timeframe not in {"1h","4h","1d","1w"}:
                        return send(self,400,{"ok":False,"error":"unsupported paper timeframe"})
                    fetch_public_market(exchange_id, symbol, timeframe, 60)
                    conn.execute("INSERT INTO zerqen_paper_state(account_id,starting_equity,cash,peak_equity,day_start_equity,exchange_id,symbol,timeframe,updated_at) VALUES('default',%s,%s,%s,%s,%s,%s,%s,%s)",(capital,capital,capital,capital,exchange_id,symbol,timeframe,t))
                    event(conn,"PAPER_INITIALIZED",{"starting_capital":str(capital),"exchange_id":exchange_id,"symbol":symbol,"timeframe":timeframe})
                    snapshot(conn,{symbol: fetch_public_market(exchange_id,symbol,timeframe,20)[0]})
                    conn.commit()
                    return send(self,200,status_payload(conn))

                if action=="reset":
                    for table in ["zerqen_paper_trades","zerqen_paper_decisions","zerqen_paper_fills","zerqen_paper_orders","zerqen_paper_positions","zerqen_paper_equity_snapshots","zerqen_paper_events","zerqen_paper_state"]:
                        conn.execute("DELETE FROM "+table+" WHERE account_id='default'" if table!="zerqen_paper_state" else "DELETE FROM zerqen_paper_state WHERE account_id='default'")
                    conn.commit()
                    return send(self,200,{"ok":True,"reset":True,"live_trading":False})

                if action=="pause":
                    conn.execute("UPDATE zerqen_paper_state SET paused=TRUE,updated_at=%s WHERE account_id='default'",(now(),))
                    event(conn,"PAPER_PAUSED",{"source":"operator"})
                    conn.commit()
                    return send(self,200,status_payload(conn))

                if action=="resume":
                    conn.execute("UPDATE zerqen_paper_state SET paused=FALSE,updated_at=%s WHERE account_id='default'",(now(),))
                    event(conn,"PAPER_RESUMED",{"source":"operator"})
                    conn.commit()
                    return send(self,200,status_payload(conn))

                if action=="halt":
                    conn.execute("UPDATE zerqen_paper_state SET halted=TRUE,updated_at=%s WHERE account_id='default'",(now(),))
                    event(conn,"HALT_NEW_ORDERS",{"source":"operator"})
                    conn.commit()
                    return send(self,200,status_payload(conn))

                if action=="clear_halt":
                    conn.execute("UPDATE zerqen_paper_state SET halted=FALSE,updated_at=%s WHERE account_id='default'",(now(),))
                    event(conn,"HALT_CLEARED",{"source":"operator"})
                    conn.commit()
                    return send(self,200,status_payload(conn))

                if action=="flatten":
                    state=get_state(conn)
                    if not state:
                        return send(self,409,{"ok":False,"error":"paper account is not initialized"})
                    prices=fetch_prices(str(state[12]), [str(p.symbol) for p in fetch_positions(conn)], str(state[14]))
                    for p in fetch_positions(conn):
                        price=prices.get(p.symbol)
                        if not price: continue
                        side="sell" if p.side=="buy" else "buy"
                        fee=price*p.quantity*D("0.001")
                        _, realized=apply_fill(p,side,p.quantity,price,fee,D(0))
                        conn.execute("DELETE FROM zerqen_paper_positions WHERE account_id='default' AND symbol=%s",(p.symbol,))
                        cash_delta = (price*p.quantity-fee) if p.side=="buy" else (-price*p.quantity-fee)
                        conn.execute("UPDATE zerqen_paper_state SET cash=cash+%s,realized_pnl=realized_pnl+%s,fees=fees+%s,updated_at=%s WHERE account_id='default'",(cash_delta,realized,fee,now()))
                    conn.execute("UPDATE zerqen_paper_state SET flatten_requested=FALSE WHERE account_id='default'")
                    event(conn,"POSITIONS_FLATTENED",{"source":"operator"})
                    snapshot(conn,prices)
                    conn.commit()
                    return send(self,200,status_payload(conn))

                if action=="cycle":
                    state=get_state(conn)
                    if not state:
                        return send(self,409,{"ok":False,"error":"initialize PAPER mode first"})
                    if bool(state[11]):
                        return send(self,409,{"ok":False,"error":"PAPER SESSION IS PAUSED"})
                    if bool(state[9]):
                        return send(self,409,{"ok":False,"error":"HALT NEW ORDERS is active"})
                    exchange_id=str(state[12])
                    symbol=str(state[13])
                    timeframe=str(state[14])
                    prices=fetch_prices(exchange_id,[symbol],timeframe)
                    for symbol in prices:
                        rows=fetch_candles(exchange_id,symbol,timeframe)
                        _,e9,e21,atr,rsi=indicators(rows)
                        regime="trend_up" if e9[-1]>e21[-1] else "range"
                        signal=e9[-1]>e21[-1] and e9[-2]<=e21[-2] and D(50)<=rsi<=D(75)
                        signal_id="signal-"+uuid.uuid4().hex
                        values=equity(conn,prices)
                        eq,_,gross,dd,daily=values if values else (D(str(state[2])),D(0),D(0),D(0),D(0))
                        open_positions=len(fetch_positions(conn))
                        allocation=D(0) if eq<=0 else gross/eq
                        candidates=eligible_strategies(regime)
                        if not signal:
                            risk_decision="REJECTED"
                            reason="no valid setup"
                        elif not candidates:
                            risk_decision="REJECTED"
                            reason="insufficient evidence"
                        else:
                            risk_decision="APPROVED"
                            reason="strategy signal passed demo risk gate"
                        record_decision(conn,state,signal_id=signal_id,strategy="baseline_trend",regime=regime,
                                        signal_timestamp=now(),signal_direction="BUY" if signal else "NONE",
                                        ema9=e9[-1],ema21=e21[-1],rsi=rsi,atr=atr,
                                        risk_per_trade=PaperLimits().risk_per_trade,
                                        aggregate_open_risk=PaperLimits().aggregate_open_risk,
                                        open_positions=open_positions,daily_loss=daily,drawdown=dd,
                                        gross_exposure=gross,allocation=allocation,risk_decision=risk_decision,
                                        rejected=(risk_decision != "APPROVED"),rejection_reason=None if risk_decision == "APPROVED" else reason)
                        event(conn,"STRATEGY_DECISION",{"signal_id":signal_id,"symbol":symbol,"strategy":"baseline_trend",
                                                       "regime":regime,"signal":signal,"risk_decision":risk_decision,
                                                       "rejected":risk_decision != "APPROVED","reason":reason})
                    snapshot(conn,prices)
                    conn.commit()
                    return send(self,200,status_payload(conn))

                if action=="test_order":
                    state=get_state(conn)
                    if not state:
                        return send(self,409,{"ok":False,"error":"initialize PAPER mode first"})
                    if state[9]:
                        return send(self,409,{"ok":False,"error":"HALT NEW ORDERS is active"})
                    symbol=str(data.get("symbol",state[13]))
                    side=str(data.get("side","buy")).lower()
                    exchange_id=str(state[12])
                    timeframe=str(state[14])
                    if symbol != str(state[13]):
                        return send(self,400,{"ok":False,"error":"paper session symbol is fixed; reset and initialize with the desired symbol"})
                    if side not in {"buy","sell"}:
                        return send(self,400,{"ok":False,"error":"side must be buy or sell"})
                    if bool(state[11]):
                        return send(self,409,{"ok":False,"error":"PAPER SESSION IS PAUSED"})
                    prices=fetch_prices(exchange_id,[symbol],timeframe)
                    price=prices[symbol]
                    rows=fetch_candles(exchange_id,symbol,timeframe)
                    _,e9,e21,atr,rsi=indicators(rows)
                    values=equity(conn,prices)
                    eq=values[0] if values else D(str(state[2]))
                    realized_net_base=compounding_equity(D(str(state[1])), D(str(state[3])))
                    risk=size_for_risk(realized_net_base,price,atr,PaperLimits(),side)
                    qty=D(str(data.get("quantity",risk.quantity)))
                    if qty<=0:
                        return send(self,400,{"ok":False,"error":"quantity must be positive"})
                    positions=fetch_positions(conn)
                    limits=PaperLimits()
                    proposed_notional=qty*price
                    if proposed_notional > realized_net_base*limits.max_strategy_allocation:
                        return send(self,409,{"ok":False,"error":"strategy allocation cap exceeded"})
                    allowed,reason=check_portfolio_risk(eq,positions,risk,limits,values[4] if values else D(0),D(str(state[7])),proposed_notional=proposed_notional)
                    signal_id="signal-"+uuid.uuid4().hex
                    regime="trend_up" if e9[-1]>e21[-1] else "range"
                    open_risk=D(0)
                    for p in positions:
                        raw=conn.execute("SELECT COALESCE(risk_at_entry,0) FROM zerqen_paper_positions WHERE account_id='default' AND symbol=%s",(p.symbol,)).fetchone()
                        open_risk += D(str(raw[0] or 0))
                    if not allowed:
                        record_decision(conn,state,signal_id=signal_id,strategy="PAPER_TEST_HARNESS",regime=regime,
                                        signal_timestamp=now(),signal_direction=side.upper(),ema9=e9[-1],ema21=e21[-1],rsi=rsi,atr=atr,
                                        risk_per_trade=limits.risk_per_trade,aggregate_open_risk=open_risk,
                                        open_positions=len(positions),daily_loss=values[4] if values else D(0),
                                        drawdown=values[3] if values else D(0),gross_exposure=values[2] if values else D(0),
                                        allocation=D(0) if eq<=0 else proposed_notional/eq,risk_decision="REJECTED",
                                        rejected=True,rejection_reason=reason)
                        event(conn,"PAPER_ORDER_REJECTED",{"signal_id":signal_id,"symbol":symbol,"side":side,"reason":reason})
                        conn.commit()
                        return send(self,409,{"ok":False,"error":reason,"rejected":True,"signal_id":signal_id})
                    oid="paper-"+uuid.uuid4().hex
                    signal_time=now()
                    slip=price*D("0.0005")
                    fill_price=price+slip if side=="buy" else price-slip
                    fee=fill_price*qty*D("0.001")
                    fill_id=str(uuid.uuid4())
                    conn.execute("INSERT INTO zerqen_paper_orders(client_order_id,account_id,symbol,side,order_type,quantity,price,stop_price,target_price,status,filled_quantity,average_price,strategy,regime,reason,created_at,updated_at,timeframe,risk_at_entry,opening_equity,signal_id,exchange_id) VALUES(%s,'default',%s,%s,'market',%s,%s,%s,%s,'NEW',0,NULL,'PAPER_TEST_HARNESS',%s,'explicit operator execution test',%s,%s,%s,%s,%s,%s,%s)",
                                  (oid,symbol,side,qty,price,risk.stop_price,risk.target_price,regime,signal_time,signal_time,timeframe,risk.risk_amount,eq,signal_id,exchange_id))
                    conn.execute("UPDATE zerqen_paper_orders SET status='SUBMITTED',updated_at=%s WHERE client_order_id=%s",(now(),oid))
                    conn.execute("UPDATE zerqen_paper_orders SET status='ACKNOWLEDGED',updated_at=%s WHERE client_order_id=%s",(now(),oid))
                    conn.execute("INSERT INTO zerqen_paper_fills(fill_id,client_order_id,account_id,symbol,side,quantity,price,requested_price,fee,funding,slippage,created_at) VALUES(%s,%s,'default',%s,%s,%s,%s,%s,%s,0,%s,%s)",
                                  (fill_id,oid,symbol,side,qty,fill_price,price,fee,slip*qty,signal_time))
                    existing_raw=conn.execute("""SELECT position_id,side,quantity,average_entry,fees,funding,realized_pnl,stop_price,target_price,
                                                       entry_order_id,entry_fill_id,opened_at,strategy,regime,risk_at_entry,opening_equity
                                                FROM zerqen_paper_positions WHERE account_id='default' AND symbol=%s""",(symbol,)).fetchone()
                    existing=next((p for p in positions if p.symbol==symbol),None)
                    realized=D(0)
                    closing_trade=None
                    position_id=None
                    if existing:
                        position_id=str(existing_raw[0]) if existing_raw and existing_raw[0] else None
                        newpos,realized=apply_fill(existing,side,qty,fill_price,fee,D(0))
                        if newpos:
                            conn.execute("""UPDATE zerqen_paper_positions SET side=%s,quantity=%s,average_entry=%s,fees=fees+%s,realized_pnl=realized_pnl+%s,updated_at=%s WHERE account_id='default' AND symbol=%s""",
                                         (newpos.side,newpos.quantity,newpos.average_entry,fee,realized,now(),symbol))
                        else:
                            conn.execute("DELETE FROM zerqen_paper_positions WHERE account_id='default' AND symbol=%s",(symbol,))
                        if existing_raw and side != existing_raw[1]:
                            entry_side=str(existing_raw[1])
                            entry_qty=D(str(existing_raw[2]))
                            close_qty=min(entry_qty,qty)
                            direction=D(1) if entry_side=="buy" else D(-1)
                            entry_fill=conn.execute(
                                "SELECT fill_id,slippage,created_at,price,requested_price FROM zerqen_paper_fills WHERE fill_id=%s",
                                (existing_raw[10],)
                            ).fetchone() if existing_raw[10] else None
                            entry_requested=D(str(entry_fill[4])) if entry_fill and entry_fill[4] is not None else D(str(existing_raw[3]))
                            gross_pnl=(price-entry_requested)*close_qty*direction
                            entry_fee=D(str(existing_raw[4]))*(close_qty/entry_qty) if entry_qty else D(0)
                            entry_funding=D(str(existing_raw[5]))*(close_qty/entry_qty) if entry_qty else D(0)
                            entry_slip_total=D(str(entry_fill[1] or 0)) if entry_fill else D(0)
                            entry_slip_alloc=entry_slip_total*(close_qty/entry_qty) if entry_qty else D(0)
                            exit_slip=slip*close_qty
                            total_fees=entry_fee+fee
                            total_slippage=entry_slip_alloc+exit_slip
                            net_pnl=gross_pnl-total_fees-entry_funding-total_slippage
                            risk_at_entry=D(str(existing_raw[14] or 0))
                            r_mult=net_pnl/risk_at_entry if risk_at_entry>0 else D(0)
                            trade_id="trade-"+uuid.uuid4().hex
                            exit_time=now()
                            duration=int((exit_time-existing_raw[11]).total_seconds()) if existing_raw[11] else None
                            closing_trade={
                                "trade_id":trade_id,"position_id":position_id,"signal_id":signal_id,
                                "entry_order_id":existing_raw[9],"exit_order_id":oid,
                                "entry_fill_id":existing_raw[10],"exit_fill_id":fill_id,
                                "exchange_id":exchange_id,"symbol":symbol,"timeframe":timeframe,
                                "side":entry_side,"strategy":existing_raw[12],"regime":existing_raw[13],
                                "signal_timestamp":signal_time,"entry_timestamp":existing_raw[11] or exit_time,
                                "exit_timestamp":exit_time,"entry_price":D(str(entry_fill[3])) if entry_fill else D(str(existing_raw[3])),
                                "exit_price":fill_price,"quantity":close_qty,"stop_price":existing_raw[7],
                                "target_price":existing_raw[8],"risk_at_entry":risk_at_entry,"gross_pnl":gross_pnl,
                                "fees":total_fees,"slippage":total_slippage,"funding":entry_funding,
                                "net_pnl":net_pnl,"r_multiple":r_mult,"opening_equity":D(str(existing_raw[15] or eq)),
                                "closing_equity":eq,"status":"CLOSED","duration_seconds":duration,
                            }
                    else:
                        position_id=str(uuid.uuid4())
                        conn.execute("""INSERT INTO zerqen_paper_positions(account_id,symbol,side,quantity,average_entry,stop_price,target_price,fees,funding,realized_pnl,entry_order_id,entry_fill_id,opened_at,strategy,regime,risk_at_entry,opening_equity,position_id,updated_at)
                                        VALUES('default',%s,%s,%s,%s,%s,%s,%s,0,0,%s,%s,%s,'PAPER_TEST_HARNESS',%s,%s,%s,%s,%s)""",
                                     (symbol,side,qty,fill_price,risk.stop_price,risk.target_price,fee,oid,fill_id,signal_time,regime,risk.risk_amount,eq,position_id,signal_time))
                    decision_id=record_decision(conn,state,signal_id=signal_id,strategy="PAPER_TEST_HARNESS",regime=regime,signal_timestamp=signal_time,
                                    signal_direction=side.upper(),ema9=e9[-1],ema21=e21[-1],rsi=rsi,atr=atr,
                                    risk_per_trade=limits.risk_per_trade,aggregate_open_risk=open_risk,open_positions=len(positions),
                                    daily_loss=values[4] if values else D(0),drawdown=values[3] if values else D(0),
                                    gross_exposure=values[2] if values else D(0),allocation=D(0) if eq<=0 else proposed_notional/eq,
                                    risk_decision="APPROVED",rejected=False,order_id=oid)
                    if closing_trade:
                        conn.execute("""INSERT INTO zerqen_paper_trades(
                            trade_id,account_id,decision_id,position_id,equity_snapshot_id,audit_event_id,signal_id,
                            entry_order_id,exit_order_id,entry_fill_id,exit_fill_id,exchange_id,symbol,timeframe,side,
                            strategy,regime,signal_timestamp,entry_timestamp,exit_timestamp,entry_price,exit_price,quantity,
                            stop_price,target_price,risk_at_entry,gross_pnl,fees,slippage,funding,net_pnl,r_multiple,
                            opening_equity,closing_equity,status,duration_seconds
                        ) VALUES(
                            %s,'default',%s,%s,NULL,NULL,%s,
                            %s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s
                        )""",(
                            closing_trade["trade_id"],decision_id,closing_trade["position_id"],closing_trade["signal_id"],
                            closing_trade["entry_order_id"],closing_trade["exit_order_id"],closing_trade["entry_fill_id"],
                            closing_trade["exit_fill_id"],closing_trade["exchange_id"],closing_trade["symbol"],
                            closing_trade["timeframe"],closing_trade["side"],closing_trade["strategy"],closing_trade["regime"],
                            closing_trade["signal_timestamp"],closing_trade["entry_timestamp"],closing_trade["exit_timestamp"],
                            closing_trade["entry_price"],closing_trade["exit_price"],closing_trade["quantity"],
                            closing_trade["stop_price"],closing_trade["target_price"],closing_trade["risk_at_entry"],
                            closing_trade["gross_pnl"],closing_trade["fees"],closing_trade["slippage"],closing_trade["funding"],
                            closing_trade["net_pnl"],closing_trade["r_multiple"],closing_trade["opening_equity"],
                            closing_trade["closing_equity"],closing_trade["status"],closing_trade["duration_seconds"],
                        ))
                    conn.execute("UPDATE zerqen_paper_orders SET status='FILLED',filled_quantity=%s,average_price=%s,updated_at=%s WHERE client_order_id=%s",(qty,fill_price,now(),oid))
                    cash_delta=(-fill_price*qty-fee) if side=="buy" else (fill_price*qty-fee)
                    conn.execute("UPDATE zerqen_paper_state SET cash=cash+%s,fees=fees+%s,slippage=slippage+%s,realized_pnl=realized_pnl+%s,updated_at=%s WHERE account_id='default'",(cash_delta,fee,slip*qty,realized,now()))
                    event(conn,"PAPER_ORDER_FILLED",{"client_order_id":oid,"signal_id":signal_id,"symbol":symbol,"side":side,
                                                     "quantity":str(qty),"price":str(fill_price),"fee":str(fee),"slippage":str(slip*qty)})
                    post_prices=fetch_prices(exchange_id,[symbol],timeframe)
                    snapshot_values=snapshot(conn,post_prices)
                    if closing_trade and snapshot_values:
                        audit_id=event(conn,"PAPER_TRADE_CLOSED",{"trade_id":closing_trade["trade_id"],"decision_id":decision_id,
                                                                    "position_id":closing_trade["position_id"],"order_id":oid,
                                                                    "entry_fill_id":closing_trade["entry_fill_id"],"exit_fill_id":fill_id,
                                                                    "equity_snapshot_id":snapshot_values[5],"net_pnl":str(closing_trade["net_pnl"])})
                        conn.execute("UPDATE zerqen_paper_trades SET equity_snapshot_id=%s,audit_event_id=%s,closing_equity=%s WHERE trade_id=%s",
                                     (snapshot_values[5],audit_id,snapshot_values[0],closing_trade["trade_id"]))
                    conn.commit()
                    return send(self,200,status_payload(conn))

                return send(self,400,{"ok":False,"error":"unsupported action"})
        except Exception:  # noqa: BLE001
            return send(self,502,{"ok":False,"error":"paper operation temporarily unavailable"})

    def log_message(self, format, *args):
        return
