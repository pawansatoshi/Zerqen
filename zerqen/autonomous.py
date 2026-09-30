from __future__ import annotations

import json
import os
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from decimal import Decimal as D

from zerqen.openrouter_agent import FreeOnlyViolation


def _get_json(url: str, timeout: float = 7.0):
    req = urllib.request.Request(url, headers={"User-Agent": "Zerqen-Autonomous-Scanner/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as response:
        return json.loads(response.read().decode())


def scan_top50(limit: int = 50) -> list[dict]:
    info = _get_json("https://api.binance.com/api/v3/exchangeInfo", timeout=8)
    tickers = _get_json("https://api.binance.com/api/v3/ticker/24hr", timeout=8)
    markets = {str(m.get("symbol","")).upper(): m for m in info.get("symbols", [])
               if m.get("status") == "TRADING" and m.get("quoteAsset") == "USDT"
               and m.get("isSpotTradingAllowed", True)}
    ranked = sorted((t for t in tickers if str(t.get("symbol","")).upper() in markets),
                    key=lambda t: float(t.get("quoteVolume") or 0), reverse=True)[:limit]

    def analyze(t):
        symbol = str(t["symbol"]).upper()
        q = urllib.parse.urlencode({"symbol": symbol, "interval": "1h", "limit": 80})
        rows = _get_json("https://api.binance.com/api/v3/klines?" + q, timeout=7)
        if len(rows) < 30:
            return None
        closes=[float(r[4]) for r in rows]; highs=[float(r[2]) for r in rows]
        lows=[float(r[3]) for r in rows]; vols=[float(r[5]) for r in rows]
        def ema(values,p):
            k=2/(p+1); out=[]; v=values[0]
            for x in values:
                v=x if not out else x*k+v*(1-k); out.append(v)
            return out
        e9,e21=ema(closes,9),ema(closes,21)
        gains=[]; losses=[]
        for i in range(max(1,len(closes)-14),len(closes)):
            ch=closes[i]-closes[i-1]; gains.append(max(ch,0)); losses.append(max(-ch,0))
        ag=sum(gains)/max(1,len(gains)); al=sum(losses)/max(1,len(losses))
        rsi=100 if al==0 else 100-100/(1+ag/al)
        trs=[]
        for i,c in enumerate(closes):
            prev=closes[i-1] if i else c
            trs.append(max(highs[i]-lows[i],abs(highs[i]-prev),abs(lows[i]-prev)))
        atr_pct=(sum(trs[-14:])/14)/closes[-1]
        max_bar_pct=max(((highs[i]-lows[i])/closes[i] for i in range(max(1,len(closes)-20),len(closes))),default=0)
        avgvol=sum(vols[-21:-1])/max(1,len(vols[-21:-1])); volratio=vols[-1]/avgvol if avgvol else 0
        momentum=(closes[-1]/closes[-6]-1)*100
        trend=1 if e9[-1]>e21[-1] else -1
        volatility_ok=atr_pct<=0.05 and max_bar_pct<=0.08
        liquidity_ok=0.5<=volratio<=3.0
        side="BUY" if trend>0 and 50<=rsi<=72 and momentum>0 else "SELL" if trend<0 and 28<=rsi<=50 and momentum<0 else "WATCH"
        if not volatility_ok or not liquidity_ok: side="WATCH"
        trend_score=min(25,abs(e9[-1]-e21[-1])/closes[-1]*100*18)
        momentum_score=max(0,min(25,50+momentum*4 if trend>0 else 50-momentum*4))
        rsi_score=max(0,25-abs(rsi-(60 if trend>0 else 40))*0.9)
        volume_score=min(25,max(0,(volratio-0.5)*25))
        score=round(min(100,trend_score+momentum_score+rsi_score+volume_score),1)
        return {"symbol":symbol.replace("USDT","/USDT"),"side":side,"score":score,
                "price":closes[-1],"rsi":round(rsi,2),"momentum":round(momentum,2),
                "volume_ratio":round(volratio,2),"atr_pct":round(atr_pct*100,2),
                "max_bar_pct":round(max_bar_pct*100,2),"change24h":float(t.get("priceChangePercent") or 0),
                "quote_volume":float(t.get("quoteVolume") or 0),"volatility_ok":volatility_ok,
                "liquidity_ok":liquidity_ok}
    results=[]
    with ThreadPoolExecutor(max_workers=12) as pool:
        futures=[pool.submit(analyze,t) for t in ranked]
        for f in as_completed(futures):
            try:
                x=f.result()
                if x: results.append(x)
            except Exception:
                continue
    results.sort(key=lambda x:x["score"], reverse=True)
    return results


def run_autonomous_cycle(conn, state):
    from api._paper import (PaperLimits, ai_gate_for_setup, dynamic_structural_stop,
                            equity, event, fetch_candles, fetch_positions, indicators,
                            now, record_decision, snapshot, volatility_profile)
    from zerqen.paper_engine import size_for_risk, check_portfolio_risk

    if not os.getenv("OPENROUTER_API_KEY"):
        event(conn,"AUTONOMOUS_AI_REQUIRED",{"status":"BLOCKED","reason":"OPENROUTER_API_KEY is not configured"})
        conn.commit()
        return {"ok":True,"autonomous":True,"trade":False,"reason":"AI is required for autonomous mode"}

    candidates=scan_top50(50)
    event(conn,"AUTONOMOUS_MARKET_SCAN",{"scanned":50,"usable_candidates":len(candidates),
        "shortlist":[{"symbol":x["symbol"],"side":x["side"],"score":x["score"],"rsi":x["rsi"],
                      "momentum":x["momentum"],"atr_pct":x["atr_pct"]} for x in candidates[:10]]})

    positions=fetch_positions(conn); existing={p.symbol for p in positions}
    marks={}
    for p in positions:
        try:
            from api._paper import fetch_public_market
            marks[p.symbol]=fetch_public_market("binance",p.symbol,"1h",20)[0]
        except Exception:
            pass
    values=equity(conn,marks)
    current_equity=values[0] if values else D(str(state[1]))
    daily_pnl=values[4] if values else D(0); drawdown=values[3] if values else D(0)
    gross=values[2] if values else D(0); limits=PaperLimits()
    reviewed=[]; approved=[]

    for c in [x for x in candidates if x["side"] in {"BUY","SELL"}][:5]:
        symbol=c["symbol"]; side=c["side"]
        if symbol in existing:
            reviewed.append({"symbol":symbol,"side":side,"status":"SKIP_EXISTING_POSITION"}); continue
        try:
            rows=fetch_candles("binance",symbol,"1h",120)
            closes,e9,e21,atr,rsi=indicators(rows); price=closes[-1]
            vol=volatility_profile(rows)
            if not vol.get("ok") or vol["atr_pct"]>limits.max_atr_pct or vol["max_bar_pct"]>limits.max_bar_pct:
                reviewed.append({"symbol":symbol,"side":side,"status":"RISK_BLOCKED","reason":"volatility"}); continue
            stop=dynamic_structural_stop(rows,side.lower(),price,atr)
            risk=size_for_risk(current_equity,price,atr,limits,side.lower(),stop)
            if not risk.approved:
                reviewed.append({"symbol":symbol,"side":side,"status":"RISK_BLOCKED","reason":risk.reason}); continue
            allowed,reason=check_portfolio_risk(current_equity,positions,risk,limits,daily_pnl,D(str(state[7])),
                                                proposed_notional=risk.quantity*price)
            if not allowed:
                reviewed.append({"symbol":symbol,"side":side,"status":"RISK_BLOCKED","reason":reason}); continue
            regime="trend_up" if e9[-1]>e21[-1] else "trend_down"
            ai_result,safe_mode,report=ai_gate_for_setup(
                conn,"binance",symbol,"1h",side,price,regime,e9[-1],e21[-1],rsi,atr,
                vol.get("atr_pct"),vol.get("max_bar_pct"),True,
                {"equity":str(current_equity),"daily_pnl":str(daily_pnl),"drawdown":str(drawdown),
                 "gross_exposure":str(gross),"open_positions":len(positions),"autonomous":True})
            decision=str(ai_result.get("decision","HOLD")).upper()
            confidence=float(ai_result.get("confidence",0) or 0); flags=ai_result.get("risk_flags") or []
            item={"symbol":symbol,"side":side,"status":"AI_REVIEWED","score":c["score"],
                  "ai_decision":decision,"confidence":confidence,"report_hash":report.report_hash,
                  "setup":report.setup_candidates[:2],"risk_flags":flags,"safe_mode":safe_mode}
            reviewed.append(item)
            if not safe_mode and decision==side and confidence>=float(os.getenv("ZERQEN_AI_MIN_CONFIDENCE","0.60")) and not flags:
                approved.append((confidence,c["score"],c,risk,report,ai_result,e9,e21,rsi,atr,regime))
        except FreeOnlyViolation as exc:
            reviewed.append({"symbol":symbol,"side":side,"status":"AI_BLOCKED","reason":str(exc)[:180]})
        except Exception as exc:
            reviewed.append({"symbol":symbol,"side":side,"status":"ANALYSIS_ERROR","reason":type(exc).__name__})

    if not approved:
        event(conn,"AUTONOMOUS_AI_REVIEW",{"status":"NO_TRADE","reviewed":reviewed,
            "reason":"No candidate passed deterministic risk gates and AI confirmation"})
        conn.commit()
        return {"ok":True,"autonomous":True,"trade":False,"reviewed":reviewed,"reason":"NO_TRADE"}

    _,_,c,risk,report,ai_result,e9,e21,rsi,atr,regime=max(approved,key=lambda x:(x[0],x[1]))
    signal_id="auto-signal-"+__import__("uuid").uuid4().hex
    eq,_,gross,dd,daily=equity(conn,{c["symbol"]:D(str(c["price"]))}) or (current_equity,D(0),gross,drawdown,daily_pnl)
    open_risk=D(0)
    for p in positions:
        row=conn.execute("SELECT COALESCE(risk_at_entry,0) FROM zerqen_paper_positions WHERE account_id='default' AND symbol=%s",(p.symbol,)).fetchone()
        open_risk+=D(str(row[0] or 0))
    allocation=D(0) if eq<=0 else (risk.quantity*D(str(c["price"])))/eq
    decision_state=list(state); decision_state[13]=c["symbol"]
    record_decision(conn,decision_state,signal_id=signal_id,strategy="autonomous_top50_ai",regime=regime,
                    signal_timestamp=now(),signal_direction=c["side"],ema9=e9[-1],ema21=e21[-1],
                    rsi=rsi,atr=atr,risk_per_trade=limits.risk_per_trade,aggregate_open_risk=open_risk,
                    open_positions=len(positions),daily_loss=daily,drawdown=dd,gross_exposure=gross,
                    allocation=allocation,risk_decision="APPROVED",rejected=False)
    event(conn,"AUTONOMOUS_AI_REVIEW",{"status":"APPROVED","symbol":c["symbol"],"side":c["side"],
        "scanner_score":c["score"],"ai_decision":ai_result.get("decision"),
        "ai_confidence":ai_result.get("confidence"),"ai_model":ai_result.get("model"),
        "ai_reason":ai_result.get("reason"),"ai_risk_flags":ai_result.get("risk_flags"),
        "report_hash":report.report_hash,"setup":report.setup_candidates[:3],
        "invalidation":ai_result.get("invalidation"),"reviewed":reviewed})
    event(conn,"STRATEGY_DECISION",{"signal_id":signal_id,"symbol":c["symbol"],"strategy":"autonomous_top50_ai",
        "regime":regime,"signal":True,"signal_direction":c["side"],"risk_decision":"APPROVED","rejected":False,
        "reason":"Top-50 scan + full market-intelligence report + AI approval",
        "ai_enabled":True,"ai_decision":ai_result.get("decision"),"ai_confidence":ai_result.get("confidence"),
        "ai_model":ai_result.get("model"),"ai_reason":ai_result.get("reason"),
        "ai_risk_flags":ai_result.get("risk_flags"),"ai_report_hash":report.report_hash,
        "stop":str(risk.stop),"target":str(risk.target),"risk_amount":str(risk.risk_amount)})
    marks[c["symbol"]]=D(str(c["price"]))
    snapshot(conn,marks); conn.commit()
    return {"ok":True,"autonomous":True,"trade":True,"selected":{"symbol":c["symbol"],"side":c["side"],
        "scanner_score":c["score"],"ai_confidence":ai_result.get("confidence"),"stop":str(risk.stop),
        "target":str(risk.target),"risk_amount":str(risk.risk_amount),"report_hash":report.report_hash},
        "reviewed":reviewed}
