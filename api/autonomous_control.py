from __future__ import annotations
import os
from datetime import datetime, timezone
from fastapi import APIRouter,Header,HTTPException
router=APIRouter(prefix="/api/autonomous",tags=["autonomous-control"])
def _auth(token):
    expected=os.environ.get("ZERQEN_DASHBOARD_TOKEN")
    if not expected or token!=expected:raise HTTPException(401,"unauthorized")
def _db():
    import psycopg
    url=os.environ.get("DATABASE_URL")
    if not url:raise HTTPException(503,"database unavailable")
    return psycopg.connect(url,connect_timeout=8)
def _ensure(c):
    c.execute("""CREATE TABLE IF NOT EXISTS zerqen_autonomous_market(
      market TEXT PRIMARY KEY,enabled BOOLEAN NOT NULL DEFAULT FALSE,
      stop_requested BOOLEAN NOT NULL DEFAULT FALSE,stage TEXT NOT NULL DEFAULT 'IDLE',
      stage_message TEXT NOT NULL DEFAULT 'Engine idle',active_symbol TEXT,active_position_id TEXT,
      heartbeat_at TIMESTAMPTZ,last_cycle_at TIMESTAMPTZ,last_error TEXT,updated_at TIMESTAMPTZ NOT NULL)""")
    c.execute("INSERT INTO zerqen_autonomous_market(market,updated_at) VALUES('spot',%s),('futures',%s) ON CONFLICT(market) DO NOTHING",(datetime.now(timezone.utc),datetime.now(timezone.utc)))
    c.commit()
def _rows(c):
    rows=c.execute("SELECT market,enabled,stop_requested,stage,stage_message,active_symbol,active_position_id,heartbeat_at,last_cycle_at,last_error FROM zerqen_autonomous_market ORDER BY market").fetchall()
    return [{"market":r[0],"enabled":bool(r[1]),"stop_requested":bool(r[2]),"stage":r[3],"stage_message":r[4],"active_symbol":r[5],"active_position_id":r[6],"heartbeat_at":r[7].isoformat() if r[7] else None,"last_cycle_at":r[8].isoformat() if r[8] else None,"last_error":r[9],"mobile_independent":True,"live_trading":False} for r in rows]
@router.get("")
def status(x_zerqen_dashboard_token:str|None=Header(default=None)):
    _auth(x_zerqen_dashboard_token)
    with _db() as c:
        try:
            return {"ok":True,"engines":_rows(c)}
        except Exception as exc:
            # A brand-new database has no control table yet. Do not run DDL on every status poll.
            if "does not exist" in str(exc).lower() or "undefinedtable" in type(exc).__name__.lower():
                return {"ok":True,"engines":[
                    {"market":"futures","enabled":False,"stop_requested":False,"stage":"IDLE","stage_message":"Engine idle","active_symbol":None,"active_position_id":None,"heartbeat_at":None,"last_cycle_at":None,"last_error":None,"mobile_independent":True,"live_trading":False},
                    {"market":"spot","enabled":False,"stop_requested":False,"stage":"IDLE","stage_message":"Engine idle","active_symbol":None,"active_position_id":None,"heartbeat_at":None,"last_cycle_at":None,"last_error":None,"mobile_independent":True,"live_trading":False},
                ]
            raise
@router.post("")
def action(payload:dict,x_zerqen_dashboard_token:str|None=Header(default=None)):
    _auth(x_zerqen_dashboard_token); market=str(payload.get("market","")).lower(); name=str(payload.get("action","")).lower()
    if market not in {"spot","futures"}: raise HTTPException(400,"market must be spot or futures")
    with _db() as c:
        now=datetime.now(timezone.utc)
        if name=="start":
            _ensure(c);
            c.execute("UPDATE zerqen_autonomous_market SET enabled=TRUE,stop_requested=FALSE,stage='STARTING',stage_message=%s,last_error=NULL,updated_at=%s WHERE market=%s",("Initializing "+market.upper()+" autonomous engine",now,market))
            try:
                from api.demo_worker import set_enabled
                set_enabled(True)
            except Exception:
                pass
        elif name=="stop":
            c.execute("UPDATE zerqen_autonomous_market SET stop_requested=TRUE,stage='STOP_REQUESTED',stage_message=%s,updated_at=%s WHERE market=%s",("New "+market.upper()+" entries locked; existing positions remain protected",now,market))
        elif name=="stage":
            stage=str(payload.get("stage","RUNNING")).upper();message=str(payload.get("message","Working…"));symbol=payload.get("symbol")
            c.execute("UPDATE zerqen_autonomous_market SET stage=%s,stage_message=%s,active_symbol=COALESCE(%s,active_symbol),heartbeat_at=%s,last_cycle_at=%s,updated_at=%s WHERE market=%s",(stage,message,symbol,now,now,now,market))
        elif name=="finalize_stop":
            c.execute("UPDATE zerqen_autonomous_market SET enabled=FALSE,stop_requested=FALSE,stage='IDLE',stage_message='Engine stopped safely',active_symbol=NULL,active_position_id=NULL,updated_at=%s WHERE market=%s",(now,market))
        else: raise HTTPException(400,"action must be start, stop, stage or finalize_stop")
        c.commit()
        return {"ok":True,"engines":_rows(c)}
