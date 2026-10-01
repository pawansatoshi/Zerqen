from __future__ import annotations
import os
from fastapi import APIRouter,Header,HTTPException
router=APIRouter(prefix="/api/futures-ledger",tags=["futures-ledger"])
def _auth(token):
    expected=os.environ.get("ZERQEN_DASHBOARD_TOKEN")
    if not expected or token!=expected:raise HTTPException(401,"unauthorized")
@router.get("")
def ledger(x_zerqen_dashboard_token:str|None=Header(default=None)):
    _auth(x_zerqen_dashboard_token)
    from api.futures_paper import _db,_state,_equity,_positions
    with _db() as conn:
        state=_state(conn)
        if not state:return {"ok":True,"initialized":False,"trades":[],"events":[]}
        eq,upnl,gross,dd,daily,_=_equity(conn)
        events=conn.execute("SELECT event_id,event_type,payload,created_at FROM zerqen_futures_paper_events WHERE account_id='default' ORDER BY created_at DESC LIMIT 300").fetchall()
        return {"ok":True,"initialized":True,"account":{"starting_equity":float(state[1]),"day_start_equity":float(state[8]),"daily_target":float(state[12]),"current_equity":float(eq),"daily_pnl":float(daily),"drawdown":float(dd),"realized_pnl":float(state[3]),"fees":float(state[4]),"funding":float(state[5]),"halted":bool(state[9]),"daily_target_hit":bool(state[13])},"positions":[{"position_id":p[0],"symbol":p[1],"side":p[2],"quantity":float(p[3]),"entry_price":float(p[4]),"leverage":float(p[5]),"initial_margin":float(p[6]),"liquidation_price":float(p[9]),"stop_price":float(p[10]),"target_price":float(p[11]),"funding":float(p[13]),"realized_pnl":float(p[14]),"opened_at":p[15].isoformat()} for p in _positions(conn)],"events":[{"id":e[0],"type":e[1],"payload":e[2],"created_at":e[3].isoformat()} for e in events]}
