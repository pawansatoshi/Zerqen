from __future__ import annotations

import os, uuid
from datetime import datetime, timezone
from decimal import Decimal as D
from fastapi import APIRouter, Header, HTTPException

router = APIRouter(prefix="/api/futures-autonomous", tags=["futures-autonomous"])

def _auth(token):
    expected=os.environ.get("ZERQEN_DASHBOARD_TOKEN")
    if not expected or token != expected: raise HTTPException(401,"unauthorized")

def _now(): return datetime.now(timezone.utc)

@router.post("")
def cycle(payload: dict, x_zerqen_dashboard_token: str | None = Header(default=None)):
    _auth(x_zerqen_dashboard_token)
    from api.futures_paper import _db,_state,_positions,_equity,_event,_mark_price
    from zerqen.autonomous import scan_top50
    from zerqen.openrouter_agent import evaluate_setup, FreeOnlyViolation
    from api.market import public_market_probe
    from zerqen.market_intelligence import build_report, report_for_ai
    from zerqen.futures_paper import FuturesLimits,size_futures_position
    with _db() as conn:
        state=_state(conn)
        if not state: raise HTTPException(409,"initialize futures paper account first")
        values=_equity(conn); eq,upnl,gross,dd,daily,metrics=values
        target=D(str(state[12]))
        if bool(state[13]) or eq>=target:
            conn.execute("UPDATE zerqen_futures_paper_state SET daily_target_hit=TRUE,updated_at=%s WHERE account_id='default'",(_now(),))
            _event(conn,"FUTURES_DAILY_TARGET_REACHED",{"equity":str(eq),"target":str(target)})
            conn.commit()
            return {"ok":True,"autonomous":True,"trade":False,"reason":"DAILY_TARGET_REACHED","equity":float(eq),"daily_target":float(target)}
        if bool(state[9]):
            conn.commit(); return {"ok":True,"autonomous":True,"trade":False,"reason":"NEW_ENTRIES_LOCKED","positions":len(_positions(conn))}
        if daily <= -(eq*FuturesLimits().daily_loss) or dd >= FuturesLimits().max_drawdown:
            conn.execute("UPDATE zerqen_futures_paper_state SET halted=TRUE,updated_at=%s WHERE account_id='default'",(_now(),))
            _event(conn,"FUTURES_RISK_HALT",{"daily_pnl":str(daily),"drawdown":str(dd)})
            conn.commit()
            return {"ok":True,"autonomous":True,"trade":False,"reason":"RISK_HALT"}
        # Protective management is always performed before considering a new entry.
        try:
            from api.futures_paper import _apply_marks
            closed=_apply_marks(conn)
        except Exception as exc:
            closed=[]; _event(conn,"FUTURES_MARK_ERROR",{"error":type(exc).__name__})
        candidates=scan_top50(50)
        eligible=[x for x in candidates if x.get("side") in {"BUY","SELL"} and x.get("volatility_ok") and x.get("liquidity_ok")]
        if not eligible:
            conn.commit(); return {"ok":True,"autonomous":True,"trade":False,"reason":"WAITING_FOR_SETUP","scanned":50,"candidates":0,"closed":closed}
        c=eligible[0]; symbol=c["symbol"]; side="buy" if c["side"]=="BUY" else "sell"
        if any(str(p[1]).upper()==symbol.upper() for p in _positions(conn)):
            conn.commit(); return {"ok":True,"autonomous":True,"trade":False,"reason":"POSITION_ALREADY_OPEN","symbol":symbol,"closed":closed}
        market=public_market_probe("binance",symbol,"1h",120)
        if market.get("connectivity_status") not in {"WORKING","DEGRADED"}:
            conn.commit(); return {"ok":True,"autonomous":True,"trade":False,"reason":"MARKET_DATA_UNAVAILABLE","symbol":symbol}
        closes=market.get("closes") or []; highs=market.get("highs") or []; lows=market.get("lows") or []
        if len(closes)<30: return {"ok":True,"autonomous":True,"trade":False,"reason":"INSUFFICIENT_CANDLES"}
        price=D(str(market["ticker_data"]["last"]))
        tr=[]
        for i in range(len(closes)):
            prev=closes[i-1] if i else closes[i]
            tr.append(max(highs[i]-lows[i],abs(highs[i]-prev),abs(lows[i]-prev)))
        atr=D(str(sum(tr[-14:])/D(14)))
        stop=price-atr*D("1.5") if side=="buy" else price+atr*D("1.5")
        limits=FuturesLimits()
        leverage=D(str(payload.get("leverage","3")))
        risk=size_futures_position(eq,price,stop,side,leverage,limits)
        if not risk.allowed:
            _event(conn,"FUTURES_RISK_BLOCK",{"symbol":symbol,"reason":risk.reason})
            conn.commit(); return {"ok":True,"autonomous":True,"trade":False,"reason":"RISK_BLOCKED","detail":risk.reason}
        report=build_report("binance",symbol,portfolio={"equity":str(eq),"daily_pnl":str(daily),"drawdown":str(dd),"gross_exposure":str(gross),"open_positions":len(_positions(conn))},risk={"volatility_ok":True,"max_stop_distance":str(limits.max_stop_distance),"min_risk_reward":float(limits.min_risk_reward)})
        context=report_for_ai(report)
        context.update({"symbol":symbol,"timeframe":"1h","signal":c["side"],"scanner":c,
                 "portfolio":{"equity":str(eq),"daily_pnl":str(daily),"drawdown":str(dd),"gross_exposure":str(gross),"open_positions":len(_positions(conn))},
                 "futures":{"leverage":str(leverage),"risk_amount":str(risk.risk_amount),"stop":str(risk.stop_price),"target":str(risk.target_price),"liquidation":str(risk.liquidation_price)}})
        context["futures"]["report_hash"]=report.report_hash
        try:
            ai=evaluate_setup(context)
        except FreeOnlyViolation as exc:
            _event(conn,"FUTURES_AI_BLOCKED",{"symbol":symbol,"reason":str(exc)[:200]}); conn.commit()
            return {"ok":True,"autonomous":True,"trade":False,"reason":"AI_BLOCKED"}
        decision=str(ai.get("decision","HOLD")).upper()
        confidence=float(ai.get("confidence",0) or 0)
        min_conf=float(os.getenv("ZERQEN_AI_MIN_CONFIDENCE","0.60"))
        if decision!=c["side"] or confidence<min_conf or ai.get("risk_flags"):
            _event(conn,"FUTURES_AI_REVIEW",{"symbol":symbol,"side":c["side"],"decision":decision,"confidence":confidence,"risk_flags":ai.get("risk_flags"),"reason":ai.get("reason")})
            conn.commit(); return {"ok":True,"autonomous":True,"trade":False,"reason":"AI_HOLD_OR_REJECT","symbol":symbol,"ai":ai}
        fee=risk.notional*limits.fee_rate
        if risk.initial_margin+fee>D(str(state[2])):
            conn.commit(); return {"ok":True,"autonomous":True,"trade":False,"reason":"INSUFFICIENT_FREE_MARGIN"}
        pid="fpos-"+uuid.uuid4().hex; t=_now()
        conn.execute("""INSERT INTO zerqen_futures_paper_positions
            (position_id,account_id,symbol,side,quantity,entry_price,leverage,initial_margin,maintenance_margin,liquidation_price,stop_price,target_price,entry_fee,funding,realized_pnl,opened_at,updated_at)
            VALUES(%s,'default',%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,0,0,%s,%s)""",
            (pid,symbol,side,risk.quantity,price,leverage,risk.initial_margin,risk.maintenance_margin,risk.liquidation_price,risk.stop_price,risk.target_price,fee,t,t))
        conn.execute("UPDATE zerqen_futures_paper_state SET cash=cash-%s,fees=fees+%s,updated_at=%s WHERE account_id='default'",(risk.initial_margin+fee,fee,t))
        _event(conn,"FUTURES_AUTONOMOUS_ENTRY",{"position_id":pid,"symbol":symbol,"side":side,"scanner_score":c["score"],"ai_decision":decision,"ai_confidence":confidence,"risk_amount":str(risk.risk_amount),"leverage":str(leverage),"stop":str(risk.stop_price),"target":str(risk.target_price)})
        conn.commit()
        return {"ok":True,"autonomous":True,"trade":True,"symbol":symbol,"side":side,"ai":ai,"risk_amount":float(risk.risk_amount),"leverage":float(leverage),"stop":float(risk.stop_price),"target":float(risk.target_price),"closed":closed}
