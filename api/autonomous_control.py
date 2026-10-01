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
    c.execute("""CREATE TABLE IF NOT EXISTS zerqen_autonomous_engine(
      engine_id TEXT PRIMARY KEY, enabled BOOLEAN NOT NULL DEFAULT FALSE,
      stop_requested BOOLEAN NOT NULL DEFAULT FALSE, interval_seconds INTEGER NOT NULL DEFAULT 60,
      last_heartbeat TIMESTAMPTZ,last_cycle TIMESTAMPTZ,last_error TEXT,updated_at TIMESTAMPTZ NOT NULL)""")
    c.execute("INSERT INTO zerqen_autonomous_engine(engine_id,updated_at) VALUES('default',%s) ON CONFLICT(engine_id) DO NOTHING",(datetime.now(timezone.utc),))
    c.commit()
def _status(c):
    r=c.execute("SELECT enabled,stop_requested,interval_seconds,last_heartbeat,last_cycle,last_error FROM zerqen_autonomous_engine WHERE engine_id='default'").fetchone()
    return {"enabled":bool(r[0]),"stop_requested":bool(r[1]),"interval_seconds":int(r[2]),"last_heartbeat":r[3].isoformat() if r[3] else None,"last_cycle":r[4].isoformat() if r[4] else None,"last_error":r[5],"mobile_independent":True,"live_trading":False}
@router.get("")
def status(x_zerqen_dashboard_token:str|None=Header(default=None)):
    _auth(x_zerqen_dashboard_token)
    with _db() as c:_ensure(c);return {"ok":True,**_status(c)}
@router.post("")
def action(payload:dict,x_zerqen_dashboard_token:str|None=Header(default=None)):
    _auth(x_zerqen_dashboard_token);name=str(payload.get("action","")).lower()
    with _db() as c:
        _ensure(c);now=datetime.now(timezone.utc)
        if name=="start":
            c.execute("UPDATE zerqen_autonomous_engine SET enabled=TRUE,stop_requested=FALSE,last_error=NULL,updated_at=%s WHERE engine_id='default'",(now,))
            try:
                from api._paper import db as spotdb
                with spotdb() as p:
                    p.execute("UPDATE zerqen_paper_state SET halted=FALSE,paused=FALSE,updated_at=%s WHERE account_id='default'",(now,));p.commit()
            except Exception: pass
            try:
                from api.futures_paper import _db as fdb
                with fdb() as p:
                    p.execute("UPDATE zerqen_futures_paper_state SET halted=FALSE,updated_at=%s WHERE account_id='default'");p.commit()
            except Exception: pass
        elif name=="stop":
            c.execute("UPDATE zerqen_autonomous_engine SET stop_requested=TRUE,updated_at=%s WHERE engine_id='default'",(now,))

            try:
                from api._paper import db as spotdb
                with spotdb() as p:
                    p.execute("UPDATE zerqen_paper_state SET halted=TRUE,updated_at=%s WHERE account_id='default'");p.commit()
            except Exception: pass
            try:
                from api.futures_paper import _db as fdb
                with fdb() as p:
                    p.execute("UPDATE zerqen_futures_paper_state SET halted=TRUE,updated_at=%s WHERE account_id='default'");p.commit()
            except Exception: pass
        elif name=="finalize_stop":
            c.execute("UPDATE zerqen_autonomous_engine SET enabled=FALSE,stop_requested=FALSE,updated_at=%s WHERE engine_id='default'",(now,))
        else: raise HTTPException(400,"action must be start, stop or finalize_stop")
        c.commit();return {"ok":True,**_status(c)}
