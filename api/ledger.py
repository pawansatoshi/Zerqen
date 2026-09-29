from __future__ import annotations

import csv
import io
import os
from decimal import Decimal

from fastapi import APIRouter, Header, HTTPException, Query
from fastapi.responses import Response

router = APIRouter(prefix="/api/ledger")


def _require(token: str | None) -> None:
    expected = os.environ.get("ZERQEN_DASHBOARD_TOKEN")
    if not expected:
        raise HTTPException(503, "dashboard authentication is not configured")
    if token != expected:
        raise HTTPException(401, "unauthorized")


def _db():
    from api.index import get_db
    return get_db()


def _ensure_schema(conn):
    conn.execute("""
        CREATE TABLE IF NOT EXISTS zerqen_paper_trades (
            trade_id TEXT PRIMARY KEY,
            account_id TEXT NOT NULL,
            signal_id TEXT,
            entry_order_id TEXT,
            exit_order_id TEXT,
            entry_fill_id TEXT,
            exit_fill_id TEXT,
            exchange_id TEXT NOT NULL,
            symbol TEXT NOT NULL,
            timeframe TEXT NOT NULL,
            side TEXT NOT NULL,
            strategy TEXT,
            regime TEXT,
            signal_timestamp TIMESTAMPTZ,
            entry_timestamp TIMESTAMPTZ NOT NULL,
            exit_timestamp TIMESTAMPTZ NOT NULL,
            entry_price NUMERIC NOT NULL,
            exit_price NUMERIC NOT NULL,
            quantity NUMERIC NOT NULL,
            stop_price NUMERIC,
            target_price NUMERIC,
            risk_at_entry NUMERIC,
            gross_pnl NUMERIC NOT NULL,
            fees NUMERIC NOT NULL DEFAULT 0,
            slippage NUMERIC NOT NULL DEFAULT 0,
            funding NUMERIC NOT NULL DEFAULT 0,
            net_pnl NUMERIC NOT NULL,
            r_multiple NUMERIC,
            opening_equity NUMERIC NOT NULL,
            closing_equity NUMERIC NOT NULL,
            status TEXT NOT NULL,
            duration_seconds BIGINT
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS zerqen_paper_decisions (
            decision_id TEXT PRIMARY KEY,
            account_id TEXT NOT NULL,
            signal_id TEXT NOT NULL,
            exchange_id TEXT NOT NULL,
            symbol TEXT NOT NULL,
            timeframe TEXT NOT NULL,
            strategy TEXT,
            regime TEXT,
            signal_timestamp TIMESTAMPTZ NOT NULL,
            signal_direction TEXT,
            ema9 NUMERIC,
            ema21 NUMERIC,
            rsi NUMERIC,
            atr NUMERIC,
            risk_per_trade NUMERIC,
            aggregate_open_risk NUMERIC,
            open_positions INTEGER,
            daily_loss NUMERIC,
            drawdown NUMERIC,
            gross_exposure NUMERIC,
            allocation NUMERIC,
            risk_decision TEXT NOT NULL,
            rejected BOOLEAN NOT NULL DEFAULT FALSE,
            rejection_reason TEXT,
            order_id TEXT
        )
    """)
    for sql in (
        "ALTER TABLE zerqen_paper_orders ADD COLUMN IF NOT EXISTS timeframe TEXT NOT NULL DEFAULT '1h'",
        "ALTER TABLE zerqen_paper_orders ADD COLUMN IF NOT EXISTS risk_at_entry NUMERIC",
        "ALTER TABLE zerqen_paper_orders ADD COLUMN IF NOT EXISTS opening_equity NUMERIC",
        "ALTER TABLE zerqen_paper_orders ADD COLUMN IF NOT EXISTS signal_id TEXT",
        "ALTER TABLE zerqen_paper_orders ADD COLUMN IF NOT EXISTS stop_price NUMERIC",
        "ALTER TABLE zerqen_paper_orders ADD COLUMN IF NOT EXISTS target_price NUMERIC",
        "ALTER TABLE zerqen_paper_orders ADD COLUMN IF NOT EXISTS exchange_id TEXT NOT NULL DEFAULT 'binance'",
        "ALTER TABLE zerqen_paper_fills ADD COLUMN IF NOT EXISTS requested_price NUMERIC",
        "ALTER TABLE zerqen_paper_positions ADD COLUMN IF NOT EXISTS stop_price NUMERIC",
        "ALTER TABLE zerqen_paper_positions ADD COLUMN IF NOT EXISTS target_price NUMERIC",
        "ALTER TABLE zerqen_paper_positions ADD COLUMN IF NOT EXISTS entry_order_id TEXT",
        "ALTER TABLE zerqen_paper_positions ADD COLUMN IF NOT EXISTS entry_fill_id TEXT",
        "ALTER TABLE zerqen_paper_positions ADD COLUMN IF NOT EXISTS opened_at TIMESTAMPTZ",
        "ALTER TABLE zerqen_paper_positions ADD COLUMN IF NOT EXISTS strategy TEXT",
        "ALTER TABLE zerqen_paper_positions ADD COLUMN IF NOT EXISTS regime TEXT",
        "ALTER TABLE zerqen_paper_positions ADD COLUMN IF NOT EXISTS risk_at_entry NUMERIC",
        "ALTER TABLE zerqen_paper_positions ADD COLUMN IF NOT EXISTS opening_equity NUMERIC",
        "ALTER TABLE zerqen_paper_equity_snapshots ADD COLUMN IF NOT EXISTS gross_exposure NUMERIC NOT NULL DEFAULT 0",
        "ALTER TABLE zerqen_paper_equity_snapshots ADD COLUMN IF NOT EXISTS open_risk NUMERIC NOT NULL DEFAULT 0",
        "ALTER TABLE zerqen_paper_equity_snapshots ADD COLUMN IF NOT EXISTS allocation NUMERIC NOT NULL DEFAULT 0",
        "ALTER TABLE zerqen_paper_equity_snapshots ADD COLUMN IF NOT EXISTS cumulative_pnl NUMERIC NOT NULL DEFAULT 0",
    ):
        conn.execute(sql)
    conn.commit()


def _dec(v) -> Decimal:
    return Decimal(str(v or 0))


def _iso(v):
    return v.isoformat() if hasattr(v, "isoformat") else v


def _filters(args):
    clauses=["account_id='default'"]
    vals=[]
    for key,col in (("date_from","entry_timestamp"),("date_to","entry_timestamp")):
        value=args.get(key)
        if value:
            clauses.append(f"{col}::date {'>=' if key=='date_from' else '<='} %s")
            vals.append(value)
    for key,col in (("exchange","exchange_id"),("symbol","symbol"),("strategy","strategy"),("side","side"),("status","status")):
        value=args.get(key)
        if value:
            clauses.append(f"{col}=%s")
            vals.append(value)
    q=args.get("q")
    if q:
        clauses.append("(trade_id ILIKE %s OR symbol ILIKE %s OR strategy ILIKE %s)")
        like=f"%{q}%"
        vals.extend([like,like,like])
    return " AND ".join(clauses), vals


def _summary(conn, where, vals):
    row=conn.execute(
        f"""SELECT
            COALESCE(SUM(gross_pnl),0), COALESCE(SUM(fees),0),
            COALESCE(SUM(slippage),0), COALESCE(SUM(funding),0),
            COALESCE(SUM(net_pnl),0), COUNT(*),
            COALESCE(SUM(CASE WHEN net_pnl>0 THEN 1 ELSE 0 END),0),
            COALESCE(SUM(CASE WHEN net_pnl<0 THEN 1 ELSE 0 END),0),
            COALESCE(MAX((opening_equity-closing_equity)/NULLIF(opening_equity,0)),0)
            FROM zerqen_paper_trades WHERE {where}""", vals).fetchone()
    return {
        "gross_pnl":float(row[0]),"fees":float(row[1]),"slippage":float(row[2]),
        "funding":float(row[3]),"net_pnl":float(row[4]),"trades":int(row[5]),
        "winning_trades":int(row[6]),"losing_trades":int(row[7]),
        "win_rate":float(row[6]/row[5]) if row[5] else 0.0,
        "max_drawdown":float(row[8] or 0),
    }


def _rows(conn, sql, vals):
    return [dict(zip([d.name for d in conn.execute(sql, vals).description], row)) for row in conn.execute(sql, vals).fetchall()]


def _daily(conn, date_from=None, date_to=None):
    rows=conn.execute("""
        SELECT created_at::date AS day,
               (array_agg(equity ORDER BY created_at ASC))[1] AS first_equity,
               (array_agg(equity ORDER BY created_at DESC))[1] AS last_equity,
               MAX(drawdown) AS drawdown, MAX(daily_pnl) AS daily_pnl
        FROM zerqen_paper_equity_snapshots
        WHERE account_id='default' AND (%s IS NULL OR created_at::date >= %s)
          AND (%s IS NULL OR created_at::date <= %s)
        GROUP BY created_at::date ORDER BY day
    """,(date_from,date_from,date_to,date_to)).fetchall()
    out=[]
    for day,opening,closing,dd,daily_pnl in rows:
        tr=conn.execute("""SELECT COUNT(*), COUNT(*) FILTER(WHERE net_pnl>0), COUNT(*) FILTER(WHERE net_pnl<0),
                                  COALESCE(SUM(gross_pnl),0),COALESCE(SUM(fees),0),
                                  COALESCE(SUM(slippage),0),COALESCE(SUM(net_pnl),0)
                           FROM zerqen_paper_trades WHERE account_id='default' AND exit_timestamp::date=%s""",(day,)).fetchone()
        trades,wins,losses,gross,fees,slippage,net=tr
        op=_dec(opening); close=_dec(closing)
        out.append({
            "date":str(day),"trading_day":len(out)+1,"opening_equity":float(op),
            "research_hurdle_amount":float(op*Decimal("0.08")),
            "actual_gross_pnl":float(gross),"fees":float(fees),"slippage":float(slippage),
            "net_pnl":float(net),"closing_equity":float(close),
            "actual_return":float((close-op)/op) if op else 0,
            "drawdown":float(dd or 0),"trades":int(trades),"winning_trades":int(wins),
            "losing_trades":int(losses),"status":"TRADED" if trades else "NO VALID SETUP",
        })
    return out


def _trade_dict(row):
    names=["trade_id","signal_id","entry_order_id","exit_order_id","entry_fill_id","exit_fill_id",
           "exchange_id","symbol","timeframe","side","strategy","regime","signal_timestamp",
           "entry_timestamp","exit_timestamp","entry_price","exit_price","quantity","stop_price",
           "target_price","risk_at_entry","gross_pnl","fees","slippage","funding","net_pnl",
           "r_multiple","opening_equity","closing_equity","status","duration_seconds"]
    d=dict(zip(names,row))
    for k,v in list(d.items()):
        if hasattr(v,"isoformat"): d[k]=v.isoformat()
        elif isinstance(v,Decimal): d[k]=float(v)
    return d


@router.get("")
def ledger(
    x_zerqen_dashboard_token: str | None = Header(default=None),
    date_from: str | None = Query(None), date_to: str | None = Query(None),
    exchange: str | None = Query(None), symbol: str | None = Query(None),
    strategy: str | None = Query(None), side: str | None = Query(None),
    status: str | None = Query(None), q: str | None = Query(None),
):
    _require(x_zerqen_dashboard_token)
    try:
        with _db() as conn:
            _ensure_schema(conn)
            where,vals=_filters(locals())
            trades=_rows(conn,f"""SELECT trade_id,signal_id,entry_order_id,exit_order_id,entry_fill_id,exit_fill_id,
                exchange_id,symbol,timeframe,side,strategy,regime,signal_timestamp,entry_timestamp,exit_timestamp,
                entry_price,exit_price,quantity,stop_price,target_price,risk_at_entry,gross_pnl,fees,slippage,
                funding,net_pnl,r_multiple,opening_equity,closing_equity,status,duration_seconds
                FROM zerqen_paper_trades WHERE {where} ORDER BY exit_timestamp DESC LIMIT 1000""",vals)
            decisions=_rows(conn,"""SELECT decision_id,signal_id,exchange_id,symbol,timeframe,strategy,regime,
                signal_timestamp,signal_direction,ema9,ema21,rsi,atr,risk_per_trade,aggregate_open_risk,
                open_positions,daily_loss,drawdown,gross_exposure,allocation,risk_decision,rejected,rejection_reason,order_id
                FROM zerqen_paper_decisions WHERE account_id='default' ORDER BY signal_timestamp DESC LIMIT 1000""",[])
            orders=_rows(conn,"""SELECT client_order_id,symbol,side,order_type,quantity,price,stop_price,target_price,
                status,filled_quantity,average_price,strategy,regime,reason,created_at,updated_at,exchange_id,timeframe,
                risk_at_entry,opening_equity,signal_id FROM zerqen_paper_orders WHERE account_id='default' ORDER BY created_at DESC LIMIT 1000""",[])
            fills=_rows(conn,"""SELECT fill_id,client_order_id,symbol,side,quantity,price,requested_price,fee,funding,
                slippage,created_at FROM zerqen_paper_fills WHERE account_id='default' ORDER BY created_at DESC LIMIT 1000""",[])
            positions=_rows(conn,"""SELECT symbol,side,quantity,average_entry,stop_price,target_price,fees,funding,
                realized_pnl,entry_order_id,entry_fill_id,opened_at,strategy,regime,risk_at_entry,opening_equity,updated_at
                FROM zerqen_paper_positions WHERE account_id='default' ORDER BY updated_at DESC""",[])
            equity=_rows(conn,"""SELECT created_at,equity,cash,realized_pnl,unrealized_pnl,drawdown,daily_pnl,
                gross_exposure,open_risk,allocation,cumulative_pnl FROM zerqen_paper_equity_snapshots
                WHERE account_id='default' ORDER BY created_at ASC LIMIT 5000""",[])
            audit=_rows(conn,"""SELECT event_id,event_type,payload,created_at FROM zerqen_paper_events
                WHERE account_id='default' ORDER BY created_at DESC LIMIT 2000""",[])
            state=conn.execute("""SELECT starting_equity,cash,realized_pnl,fees,funding,slippage,halted,paused,exchange_id,symbol,timeframe FROM zerqen_paper_state WHERE account_id='default'""").fetchone()
            latest=conn.execute("SELECT equity,unrealized_pnl,drawdown,gross_exposure,open_risk,allocation FROM zerqen_paper_equity_snapshots WHERE account_id='default' ORDER BY created_at DESC LIMIT 1").fetchone()
            max_dd=conn.execute("SELECT COALESCE(MAX(drawdown),0) FROM zerqen_paper_equity_snapshots WHERE account_id='default'").fetchone()[0]
            max_dd=conn.execute("SELECT COALESCE(MAX(drawdown),0) FROM zerqen_paper_equity_snapshots WHERE account_id='default'").fetchone()[0]
            account={
                "initialized":bool(state),
                "starting_capital":float(state[0]) if state else 0,
                "current_equity":float(latest[0]) if latest else float(state[1]) if state else 0,
                "available_capital":float(state[1]) if state else 0,
                "reserved_capital":float(latest[3]) if latest else 0,
                "realized_pnl":float(state[2]) if state else 0,
                "unrealized_pnl":float(latest[1]) if latest else 0,
                "fees":float(state[3]) if state else 0,
                "funding":float(state[4]) if state else 0,
                "slippage":float(state[5]) if state else 0,
                "net_pnl":float(latest[0]-state[0]) if state and latest else 0,
                "actual_return":float((latest[0]-state[0])/state[0]) if state and latest and state[0] else 0,
                "drawdown":float(latest[2]) if latest else 0,
                "max_drawdown":float(max_dd or 0),
                "gross_exposure":float(latest[3]) if latest else 0,
                "open_risk":float(latest[4]) if latest else 0,
                "allocation":float(latest[5]) if latest else 0,
                "exchange_id":state[8] if state else None,"symbol":state[9] if state else None,"timeframe":state[10] if state else None,
                "halted":bool(state[6]) if state else False,"paused":bool(state[7]) if state else False,
            }
            return {"ok":True,"mode":"PAPER","live_capital":False,
                    "account":account,
                    "research_hurdle":0.08,"research_hurdle_label":"Research hurdle — not a trading requirement",
                    "summary":_summary(conn,where,vals),"daily_compounding":_daily(conn,date_from,date_to),
                    "trades":[_trade_dict(tuple(d.values())) for d in trades],
                    "decisions":decisions,"orders":orders,"fills":fills,"positions":positions,
                    "equity_snapshots":equity,"audit_log":audit}
    except HTTPException:
        raise
    except Exception:  # noqa: BLE001
        raise HTTPException(503,"ledger data temporarily unavailable")


@router.get("/trade/{trade_id}")
def trade_detail(trade_id: str, x_zerqen_dashboard_token: str | None = Header(default=None)):
    _require(x_zerqen_dashboard_token)
    with _db() as conn:
        _ensure_schema(conn)
        row=conn.execute("""SELECT trade_id,signal_id,entry_order_id,exit_order_id,entry_fill_id,exit_fill_id,
            exchange_id,symbol,timeframe,side,strategy,regime,signal_timestamp,entry_timestamp,exit_timestamp,
            entry_price,exit_price,quantity,stop_price,target_price,risk_at_entry,gross_pnl,fees,slippage,funding,
            net_pnl,r_multiple,opening_equity,closing_equity,status,duration_seconds
            FROM zerqen_paper_trades WHERE account_id='default' AND trade_id=%s""",(trade_id,)).fetchone()
        if not row: raise HTTPException(404,"trade not found")
        trade=_trade_dict(row)
        decision=conn.execute("SELECT * FROM zerqen_paper_decisions WHERE signal_id=%s ORDER BY signal_timestamp DESC LIMIT 1",(trade["signal_id"],)).fetchone()
        entry_fill=conn.execute("SELECT fill_id,client_order_id,requested_price,price,quantity,fee,slippage,created_at FROM zerqen_paper_fills WHERE fill_id=%s",(trade["entry_fill_id"],)).fetchone()
        exit_fill=conn.execute("SELECT fill_id,client_order_id,requested_price,price,quantity,fee,slippage,created_at FROM zerqen_paper_fills WHERE fill_id=%s",(trade["exit_fill_id"],)).fetchone()
        events=conn.execute("""SELECT event_id,event_type,payload,created_at FROM zerqen_paper_events
                               WHERE account_id='default' AND created_at BETWEEN %s AND %s ORDER BY created_at""",
                            (row[13],row[14])).fetchall()
        def fill_payload(row):
            if not row:
                return None
            return {"fill_id":row[0],"order_id":row[1],"requested_price":float(row[2]) if row[2] is not None else None,
                    "actual_price":float(row[3]),"quantity":float(row[4]),"fee":float(row[5]),"slippage":float(row[6]),"created_at":_iso(row[7])}
        return {"ok":True,"trade":trade,
                "risk_decision":dict(zip([d.name for d in conn.execute("SELECT * FROM zerqen_paper_decisions WHERE signal_id=%s LIMIT 1",(trade["signal_id"],)).description],decision)) if decision else None,
                "entry_fill":fill_payload(entry_fill),"exit_fill":fill_payload(exit_fill),
                "audit_events":[{"event_id":e[0],"event_type":e[1],"payload":e[2],"created_at":_iso(e[3])} for e in events]}


def _flat_rows(data):
    sheets={
      "Daily Compounding":data["daily_compounding"],"Trade Ledger":data["trades"],
      "Orders":data["orders"],"Fills":data["fills"],"Positions":data["positions"],
      "P&L":[{k:t[k] for k in ("trade_id","gross_pnl","fees","slippage","funding","net_pnl","r_multiple","opening_equity","closing_equity")} for t in data["trades"]],
      "Risk Events":[d for d in data["decisions"] if d.get("rejected")],
      "Equity Snapshots":data["equity_snapshots"],"Audit Log":data["audit_log"],
    }
    return sheets


@router.get("/export")
def export_ledger(
    format: str = Query("csv"), x_zerqen_dashboard_token: str | None = Header(default=None),
    date_from: str | None = Query(None), date_to: str | None = Query(None),
    exchange: str | None = Query(None), symbol: str | None = Query(None),
    strategy: str | None = Query(None), side: str | None = Query(None), status: str | None = Query(None),
    q: str | None = Query(None),
):
    _require(x_zerqen_dashboard_token)
    with _db() as conn:
        _ensure_schema(conn)
        where,vals=_filters(locals())
        trades=_rows(conn,f"""SELECT trade_id,signal_id,entry_order_id,exit_order_id,entry_fill_id,exit_fill_id,
            exchange_id,symbol,timeframe,side,strategy,regime,signal_timestamp,entry_timestamp,exit_timestamp,
            entry_price,exit_price,quantity,stop_price,target_price,risk_at_entry,gross_pnl,fees,slippage,funding,
            net_pnl,r_multiple,opening_equity,closing_equity,status,duration_seconds
            FROM zerqen_paper_trades WHERE {where} ORDER BY exit_timestamp DESC LIMIT 5000""",vals)
        # Reuse the JSON endpoint shape without an internal HTTP call.
        decisions=_rows(conn,"SELECT decision_id,signal_id,exchange_id,symbol,timeframe,strategy,regime,signal_timestamp,signal_direction,ema9,ema21,rsi,atr,risk_per_trade,aggregate_open_risk,open_positions,daily_loss,drawdown,gross_exposure,allocation,risk_decision,rejected,rejection_reason,order_id FROM zerqen_paper_decisions WHERE account_id='default' ORDER BY signal_timestamp DESC LIMIT 5000",[])
        data={"trades":[_trade_dict(tuple(d.values())) for d in trades],"daily_compounding":_daily(conn,date_from,date_to),"decisions":decisions,
              "orders":_rows(conn,"SELECT * FROM zerqen_paper_orders WHERE account_id='default' ORDER BY created_at DESC LIMIT 5000",[]),
              "fills":_rows(conn,"SELECT * FROM zerqen_paper_fills WHERE account_id='default' ORDER BY created_at DESC LIMIT 5000",[]),
              "positions":_rows(conn,"SELECT * FROM zerqen_paper_positions WHERE account_id='default' ORDER BY updated_at DESC",[]),
              "equity_snapshots":_rows(conn,"SELECT * FROM zerqen_paper_equity_snapshots WHERE account_id='default' ORDER BY created_at ASC LIMIT 10000",[]),
              "audit_log":_rows(conn,"SELECT * FROM zerqen_paper_events WHERE account_id='default' ORDER BY created_at DESC LIMIT 10000",[])}
    if format.lower()=="csv":
        buf=io.StringIO(); w=csv.writer(buf)
        w.writerow(["Trade ID","Timestamp","Exchange","Symbol","Timeframe","Side","Strategy","Entry","Exit","Quantity","Gross P&L","Fees","Slippage","Net P&L","R Multiple","Opening Equity","Closing Equity","Status"])
        for t in data["trades"]:
            w.writerow([t.get("trade_id"),t.get("exit_timestamp"),t.get("exchange_id"),t.get("symbol"),t.get("timeframe"),t.get("side"),t.get("strategy"),t.get("entry_price"),t.get("exit_price"),t.get("quantity"),t.get("gross_pnl"),t.get("fees"),t.get("slippage"),t.get("net_pnl"),t.get("r_multiple"),t.get("opening_equity"),t.get("closing_equity"),t.get("status")])
        return Response(buf.getvalue(),media_type="text/csv",headers={"Content-Disposition":"attachment; filename=zerqen-trade-ledger.csv"})
    if format.lower()!="xlsx": raise HTTPException(400,"format must be csv or xlsx")
    try:
        from openpyxl import Workbook
    except ImportError as exc:
        raise HTTPException(503,"Excel export dependency unavailable") from exc
    wb=Workbook(); wb.remove(wb.active)
    for name,rows in _flat_rows(data).items():
        ws=wb.create_sheet(name)
        if not rows: ws.append(["No records"])
        else:
            headers=list(rows[0].keys()); ws.append(headers)
            for row in rows: ws.append([row.get(h) for h in headers])
        ws.freeze_panes="A2"; ws.auto_filter.ref=ws.dimensions
    out=io.BytesIO(); wb.save(out)
    return Response(out.getvalue(),media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    headers={"Content-Disposition":"attachment; filename=zerqen-trade-ledger.xlsx"})
