from __future__ import annotations

import json
import os
import uuid
from decimal import Decimal as D
from http.server import BaseHTTPRequestHandler
from datetime import datetime, timezone

from zerqen.paper_engine import PaperLimits, Position, apply_fill, check_portfolio_risk, size_for_risk
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
            last_marked_at TIMESTAMPTZ,
            updated_at TIMESTAMPTZ NOT NULL
        )
    """)
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
    conn.commit()
    return conn


def now():
    return datetime.now(timezone.utc)


def get_state(conn):
    row = conn.execute(
        "SELECT account_id, starting_equity, cash, realized_pnl, fees, funding, slippage, peak_equity, day_start_equity, halted, flatten_requested, last_marked_at, updated_at FROM zerqen_paper_state WHERE account_id='default'"
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


def fetch_prices(symbols):
    import urllib.parse
    import urllib.request

    out = {}
    for symbol in symbols:
        params = urllib.parse.urlencode({"symbol": symbol.replace("/", "").upper()})
        with urllib.request.urlopen("https://api.binance.com/api/v3/ticker/price?" + params, timeout=6) as response:
            out[symbol] = D(str(json.loads(response.read().decode())["price"]))
    return out


def fetch_candles(symbol, limit=120):
    import urllib.parse
    import urllib.request

    params = urllib.parse.urlencode({"symbol": symbol.replace("/", "").upper(), "interval": "1h", "limit": limit})
    with urllib.request.urlopen("https://api.binance.com/api/v3/klines?" + params, timeout=7) as response:
        return json.loads(response.read().decode())


def indicators(rows):
    closes = [D(str(r[4])) for r in rows]
    highs = [D(str(r[2])) for r in rows]
    lows = [D(str(r[3])) for r in rows]
    ema9, ema21 = [], []
    k9, k21 = D("0.2"), D("2") / D("22")
    for i, x in enumerate(closes):
        ema9.append(x if i == 0 else x * k9 + ema9[-1] * (1-k9))
        ema21.append(x if i == 0 else x * k21 + ema21[-1] * (1-k21))
    trs = []
    for i, x in enumerate(closes):
        prev = closes[i-1] if i else x
        trs.append(max(highs[i]-lows[i], abs(highs[i]-prev), abs(lows[i]-prev)))
    atr = sum(trs[-14:]) / D("14") if len(trs) >= 14 else D("0")
    rsi = D("50")
    if len(closes) >= 15:
        gains = [max(closes[i]-closes[i-1], D("0")) for i in range(len(closes)-14, len(closes))]
        losses = [max(closes[i-1]-closes[i], D("0")) for i in range(len(closes)-14, len(closes))]
        avg_gain, avg_loss = sum(gains)/D("14"), sum(losses)/D("14")
        rsi = D("100") if avg_loss == 0 else D("100") - D("100")/(D("1") + avg_gain/avg_loss)
    return closes, ema9, ema21, atr, rsi


def equity(conn, prices):
    state = get_state(conn)
    if not state:
        return None
    cash = D(str(state[2]))
    unrealized = D("0")
    gross = D("0")
    for p in fetch_positions(conn):
        mark = prices.get(p.symbol)
        if mark:
            unrealized += (mark - p.average_entry) * p.signed_quantity
            gross += abs(mark * p.quantity)
    market_value = sum(
        (prices[p.symbol] * p.signed_quantity for p in fetch_positions(conn) if p.symbol in prices),
        D("0"),
    )
    eq = cash + market_value
    peak = D(str(state[7]))
    dd = D("0") if peak <= 0 else max(D("0"), (peak-eq)/peak)
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
    conn.execute(
        "INSERT INTO zerqen_paper_equity_snapshots(account_id,equity,cash,realized_pnl,unrealized_pnl,drawdown,daily_pnl,created_at) VALUES('default',%s,%s,%s,%s,%s,%s,%s)",
        (eq, D(str(state[2])), D(str(state[3])), unrealized, dd, daily, t),
    )
    conn.execute(
        "UPDATE zerqen_paper_state SET peak_equity=GREATEST(peak_equity,%s),last_marked_at=%s,updated_at=%s WHERE account_id='default'",
        (eq, t, t),
    )
    return eq, unrealized, gross, dd, daily


def status_payload(conn):
    state = get_state(conn)
    if not state:
        return {"ok": True, "initialized": False, "mode": "PAPER", "live_trading": False}
    symbols = ["BTC/USDT", "ETH/USDT", "SOL/USDT", "BNB/USDT"]
    prices = {}
    try:
        prices = fetch_prices(symbols)
    except Exception:
        pass
    values = equity(conn, prices) if prices else None
    eq = values[0] if values else D(str(state[2]))
    unrealized = values[1] if values else D("0")
    gross = values[2] if values else D("0")
    dd = values[3] if values else D("0")
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


def event(conn, event_type, payload):
    conn.execute(
        "INSERT INTO zerqen_paper_events(event_id,account_id,event_type,payload,created_at) VALUES(%s,'default',%s,%s,%s)",
        (str(uuid.uuid4()), event_type, json.dumps(payload, default=str), now()),
    )


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
                    conn.execute("INSERT INTO zerqen_paper_state(account_id,starting_equity,cash,peak_equity,day_start_equity,updated_at) VALUES('default',%s,%s,%s,%s,%s)",(capital,capital,capital,capital,t))
                    event(conn,"PAPER_INITIALIZED",{"starting_capital":str(capital)})
                    conn.commit()
                    return send(self,200,status_payload(conn))

                if action=="reset":
                    for table in ["zerqen_paper_fills","zerqen_paper_orders","zerqen_paper_positions","zerqen_paper_equity_snapshots","zerqen_paper_events","zerqen_paper_state"]:
                        conn.execute("DELETE FROM "+table+" WHERE account_id='default'" if table!="zerqen_paper_state" else "DELETE FROM zerqen_paper_state WHERE account_id='default'")
                    conn.commit()
                    return send(self,200,{"ok":True,"reset":True,"live_trading":False})

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
                    prices=fetch_prices(["BTC/USDT","ETH/USDT","SOL/USDT","BNB/USDT"])
                    for p in fetch_positions(conn):
                        price=prices.get(p.symbol)
                        if not price: continue
                        side="sell" if p.side=="buy" else "buy"
                        fee=price*p.quantity*D("0.001")
                        _, realized=apply_fill(p,side,p.quantity,price,fee,D("0"))
                        conn.execute("DELETE FROM zerqen_paper_positions WHERE account_id='default' AND symbol=%s",(p.symbol,))
                        conn.execute("UPDATE zerqen_paper_state SET cash=cash+%s,realized_pnl=realized_pnl+%s,fees=fees+%s,updated_at=%s WHERE account_id='default'",(realized,realized,fee,now()))
                    conn.execute("UPDATE zerqen_paper_state SET flatten_requested=FALSE WHERE account_id='default'")
                    event(conn,"POSITIONS_FLATTENED",{"source":"operator"})
                    snapshot(conn,prices)
                    conn.commit()
                    return send(self,200,status_payload(conn))

                if action=="cycle":
                    state=get_state(conn)
                    if not state:
                        return send(self,409,{"ok":False,"error":"initialize PAPER mode first"})
                    prices=fetch_prices(["BTC/USDT","ETH/USDT","SOL/USDT","BNB/USDT"])
                    for symbol in prices:
                        rows=fetch_candles(symbol)
                        closes,e9,e21,atr,rsi=indicators(rows)
                        signal = e9[-1] > e21[-1] and e9[-2] <= e21[-2] and D("50") <= rsi <= D("75")
                        event(conn,"STRATEGY_DECISION",{"symbol":symbol,"strategy":"baseline_trend","regime":"trend_up" if e9[-1]>e21[-1] else "range","signal":signal,"status":"VALIDATED" if eligible_strategies("trend_up" if e9[-1]>e21[-1] else "range") else "INSUFFICIENT_DATA","reason":"no runtime paper order is authorized until a strategy has persisted OOS/walk-forward/Monte Carlo evidence"})
                    snapshot(conn,prices)
                    conn.commit()
                    return send(self,200,status_payload(conn))

                if action=="test_order":
                    state=get_state(conn)
                    if not state: return send(self,409,{"ok":False,"error":"initialize PAPER mode first"})
                    if state[9]: return send(self,409,{"ok":False,"error":"HALT NEW ORDERS is active"})
                    symbol=str(data.get("symbol","BTC/USDT"))
                    side=str(data.get("side","buy")).lower()
                    if side not in {"buy","sell"}: return send(self,400,{"ok":False,"error":"side must be buy or sell"})
                    prices=fetch_prices([symbol])
                    price=prices[symbol]
                    rows=fetch_candles(symbol)
                    _,_,_,atr,_=indicators(rows)
                    state_values=equity(conn,prices)
                    eq=state_values[0] if state_values else D(str(state[2]))
                    risk=size_for_risk(eq,price,atr,PaperLimits(),side)
                    qty=D(str(data.get("quantity",risk.quantity)))
                    if qty<=0: return send(self,400,{"ok":False,"error":"quantity must be positive"})
                    # This is an explicit PAPER execution harness, not a strategy signal.
                    positions=fetch_positions(conn)
                    proposed_risk=size_for_risk(eq,price,atr,PaperLimits(),side)
                    limits=PaperLimits()
                    if qty*price > eq*limits.max_strategy_allocation:
                        return send(self,409,{"ok":False,"error":"strategy allocation cap exceeded"})
                    allowed,reason=check_portfolio_risk(eq,positions,proposed_risk,limits,state_values[4] if state_values else D("0"),D(str(state[7])),proposed_notional=qty*price)
                    if not allowed: return send(self,409,{"ok":False,"error":reason})
                    oid="paper-"+uuid.uuid4().hex
                    t=now()
                    slip=price*D("0.0005")
                    fill_price=price+slip if side=="buy" else price-slip
                    fee=fill_price*qty*D("0.001")
                    conn.execute("INSERT INTO zerqen_paper_orders(client_order_id,account_id,symbol,side,order_type,quantity,price,status,filled_quantity,average_price,strategy,regime,reason,created_at,updated_at) VALUES(%s,'default',%s,%s,'market',%s,%s,'NEW',0,NULL,'PAPER_TEST_HARNESS','TEST','explicit operator execution test',%s,%s)",(oid,symbol,side,qty,price,t,t))
                    conn.execute("UPDATE zerqen_paper_orders SET status='SUBMITTED',updated_at=%s WHERE client_order_id=%s",(now(),oid))
                    conn.execute("UPDATE zerqen_paper_orders SET status='ACKNOWLEDGED',updated_at=%s WHERE client_order_id=%s",(now(),oid))
                    conn.execute("INSERT INTO zerqen_paper_fills(fill_id,client_order_id,account_id,symbol,side,quantity,price,fee,funding,slippage,created_at) VALUES(%s,%s,'default',%s,%s,%s,%s,%s,0,%s,%s)",(str(uuid.uuid4()),oid,symbol,side,qty,fill_price,fee,slip*qty,t))
                    realized=D("0")
                    existing=next((p for p in positions if p.symbol==symbol),None)
                    if existing:
                        newpos,realized=apply_fill(existing,side,qty,fill_price,fee,D("0"))
                        if newpos:
                            conn.execute("UPDATE zerqen_paper_positions SET side=%s,quantity=%s,average_entry=%s,fees=fees+%s,realized_pnl=realized_pnl+%s,updated_at=%s WHERE account_id='default' AND symbol=%s",(newpos.side,newpos.quantity,newpos.average_entry,fee,realized,now(),symbol))
                        else:
                            conn.execute("DELETE FROM zerqen_paper_positions WHERE account_id='default' AND symbol=%s",(symbol,))
                    else:
                        conn.execute("INSERT INTO zerqen_paper_positions(account_id,symbol,side,quantity,average_entry,fees,funding,realized_pnl,updated_at) VALUES('default',%s,%s,%s,%s,%s,0,0,%s)",(symbol,side,qty,fill_price,fee,now()))
                    conn.execute("UPDATE zerqen_paper_orders SET status='FILLED',filled_quantity=%s,average_price=%s,updated_at=%s WHERE client_order_id=%s",(qty,fill_price,now(),oid))
                    cash_delta = (-fill_price * qty - fee) if side == "buy" else (fill_price * qty - fee)
                    conn.execute("UPDATE zerqen_paper_state SET cash=cash+%s,fees=fees+%s,slippage=slippage+%s,realized_pnl=realized_pnl+%s,updated_at=%s WHERE account_id='default'",(cash_delta,fee,slip*qty,realized,now()))
                    event(conn,"PAPER_ORDER_FILLED",{"client_order_id":oid,"symbol":symbol,"side":side,"quantity":str(qty),"price":str(fill_price),"fee":str(fee),"slippage":str(slip*qty)})
                    snapshot(conn,prices)
                    conn.commit()
                    return send(self,200,status_payload(conn))

                return send(self,400,{"ok":False,"error":"unsupported action"})
        except Exception:
            return send(self,502,{"ok":False,"error":"paper operation temporarily unavailable"})

    def log_message(self, format, *args):
        return
