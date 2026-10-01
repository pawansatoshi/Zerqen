from __future__ import annotations
import json, urllib.parse, urllib.request
from fastapi import APIRouter, Query, Header, HTTPException
import os

router=APIRouter(prefix="/api/futures-chart",tags=["futures-chart"])
_ALLOWED={"1m","3m","5m","15m","30m","1h","2h","4h","6h","8h","12h","1d","3d","1w","1M"}

def _auth(token):
    expected=os.environ.get("ZERQEN_DASHBOARD_TOKEN")
    if not expected or token!=expected: raise HTTPException(401,"unauthorized")

def _get(url):
    req=urllib.request.Request(url,headers={"User-Agent":"Zerqen-Futures-Chart/1.0"})
    with urllib.request.urlopen(req,timeout=10) as r: return json.loads(r.read().decode())

def _ema(values,p):
    if not values:return []
    k=2/(p+1); out=[]; v=values[0]
    for x in values:
        v=x if not out else x*k+v*(1-k); out.append(v)
    return out

def _rsi(values,p=14):
    out=[None]*len(values)
    if len(values)<=p:return out
    gains=[];losses=[]
    for i in range(1,len(values)):
        d=values[i]-values[i-1];gains.append(max(d,0));losses.append(max(-d,0))
    ag=sum(gains[:p])/p; al=sum(losses[:p])/p
    out[p]=100 if al==0 else 100-100/(1+ag/al)
    for i in range(p+1,len(values)):
        ag=(ag*(p-1)+gains[i-1])/p; al=(al*(p-1)+losses[i-1])/p
        out[i]=100 if al==0 else 100-100/(1+ag/al)
    return out

def _atr(highs,lows,closes,p=14):
    out=[None]*len(closes); trs=[]
    for i in range(len(closes)):
        prev=closes[i-1] if i else closes[i]
        trs.append(max(highs[i]-lows[i],abs(highs[i]-prev),abs(lows[i]-prev)))
    if len(trs)<=p:return out
    v=sum(trs[1:p+1])/p; out[p]=v
    for i in range(p+1,len(trs)):
        v=(v*(p-1)+trs[i])/p;out[i]=v
    return out

@router.get("")
def chart(symbol:str=Query("BTC/USDT"),timeframe:str=Query("1h"),limit:int=Query(500,ge=50,le=1500),x_zerqen_dashboard_token:str|None=Header(default=None)):
    _auth(x_zerqen_dashboard_token)
    if timeframe not in _ALLOWED: raise HTTPException(400,"unsupported futures chart timeframe")
    clean=symbol.replace("/","").upper()
    url="https://fapi.binance.com/fapi/v1/klines?"+urllib.parse.urlencode({"symbol":clean,"interval":timeframe,"limit":limit})
    try:
        rows=_get(url)
        if not isinstance(rows,list) or len(rows)<20: raise RuntimeError("insufficient candle data")
        times=[int(r[0])//1000 for r in rows]; opens=[float(r[1]) for r in rows]; highs=[float(r[2]) for r in rows]; lows=[float(r[3]) for r in rows]; closes=[float(r[4]) for r in rows]; volumes=[float(r[5]) for r in rows]
        e9,e21=_ema(closes,9),_ema(closes,21);rsi=_rsi(closes);atr=_atr(highs,lows,closes)
        vs=[]
        for i in range(len(volumes)):
            start=max(0,i-19);vs.append(sum(volumes[start:i+1])/max(1,i-start+1))
        signals=[]
        for i in range(22,len(closes)):
            if e9[i]>e21[i] and e9[i-1]<=e21[i-1] and (rsi[i] is None or rsi[i]>=50):
                signals.append({"time":times[i],"side":"BUY","price":closes[i],"reason":"EMA9 crossed above EMA21"})
            elif e9[i]<e21[i] and e9[i-1]>=e21[i-1] and (rsi[i] is None or rsi[i]<=50):
                signals.append({"time":times[i],"side":"SELL","price":closes[i],"reason":"EMA9 crossed below EMA21"})
        trades=[]
        try:
            from api.futures_paper import _db
            with _db() as conn:
                ev=conn.execute("SELECT event_type,payload,created_at FROM zerqen_futures_paper_events WHERE account_id='default' AND event_type IN ('FUTURES_AUTONOMOUS_ENTRY','FUTURES_POSITION_CLOSED') ORDER BY created_at DESC LIMIT 100").fetchall()
                for typ,payload,created in ev:
                    p=payload or {}
                    if str(p.get("symbol","")).upper()!=symbol.upper(): continue
                    trades.append({"time":int(created.timestamp()),"type":typ,"side":p.get("side"),"price":p.get("entry_price") or p.get("mark_price"),"pnl":p.get("realized_pnl"),"reason":p.get("reason") or typ})
        except Exception: pass
        return {"ok":True,"symbol":symbol.upper(),"market":"FUTURES","exchange":"binance","timeframe":timeframe,"times":times,"opens":opens,"highs":highs,"lows":lows,"closes":closes,"volumes":volumes,"ema9":e9,"ema21":e21,"rsi14":rsi,"atr14":atr,"volumeSma20":vs,"signals":signals[-100:],"trades":trades}
    except HTTPException: raise
    except Exception as exc: raise HTTPException(503,"futures chart data unavailable") from exc
