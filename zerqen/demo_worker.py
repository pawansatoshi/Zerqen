from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone

INTERVAL = int(os.getenv("ZERQEN_DEMO_INTERVAL_SECONDS", "60"))
BASE_URL = os.environ["ZERQEN_API_BASE_URL"].rstrip("/")
TOKEN = os.environ["ZERQEN_DASHBOARD_TOKEN"]


def api_call(path: str, payload: dict | None = None) -> dict:
    body = json.dumps(payload).encode() if payload is not None else None
    request = urllib.request.Request(
        BASE_URL + path,
        data=body,
        method="POST" if payload is not None else "GET",
        headers={
            "Content-Type": "application/json",
            "X-Zerqen-Dashboard-Token": TOKEN,
            "User-Agent": "Zerqen-Demo-Worker/1.0",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.loads(response.read().decode())
    except urllib.error.HTTPError as exc:
        return {"ok": False, "status": exc.code, "error": exc.read().decode(errors="replace")[:1000]}


def post_paper_cycle() -> dict:
    return api_call("/api/paper", {"action": "autonomous_cycle"})


def ensure_paper_initialized(cycle: dict) -> dict:
    """Initialize the default paper account once, then retry the cycle."""
    if cycle.get("ok") or cycle.get("status") != 409:
        return cycle
    error = str(cycle.get("error") or "")
    if "initialize PAPER mode first" not in error:
        return cycle
    capital = os.getenv("ZERQEN_DEMO_STARTING_CAPITAL", "1000").strip()
    init = api_call(
        "/api/paper",
        {
            "action": "initialize",
            "starting_capital": capital,
            "exchange_id": os.getenv("ZERQEN_DEMO_EXCHANGE", "binance"),
            "symbol": os.getenv("ZERQEN_DEMO_SYMBOL", "AUTO/TOP50"),
            "timeframe": os.getenv("ZERQEN_DEMO_TIMEFRAME", "1h"),
            "market_type": "spot",
        },
    )
    print(
        datetime.now(timezone.utc).isoformat(),
        "paper auto-initialize",
        json.dumps(init, default=str),
        flush=True,
    )
    if init.get("ok"):
        return post_paper_cycle()
    return {"ok": False, "status": init.get("status"), "error": init.get("error") or init.get("error_type") or "paper initialization failed"}


def execute_approved_signal(cycle: dict) -> dict | None:
    """Convert an AI-approved strategy decision into a simulated paper fill."""
    if not cycle.get("ok"):
        return None
    events = cycle.get("events") or []
    approved = next(
        (
            e for e in events
            if e.get("type") == "STRATEGY_DECISION"
            and (e.get("payload") or {}).get("risk_decision") == "APPROVED"
        ),
        None,
    )
    if not approved:
        return None
    payload = approved.get("payload") or {}
    side = str(payload.get("signal_direction", "")).lower()
    symbol = str(payload.get("symbol", "")).strip()
    if side not in {"buy", "sell"} or not symbol:
        return {"ok": False, "error": "approved signal missing side or symbol"}
    return api_call(
        "/api/paper",
        {"action": "test_order", "symbol": symbol, "side": side, "automatic": True, "scanner": True},
    )


def main() -> None:
    # Enable the server-side demo scheduler state on worker boot.
    # This only enables paper/demo execution; it never enables live trading.
    if os.getenv("ZERQEN_DEMO_WORKER_AUTO_START", "true").strip().lower() in {"1", "true", "yes", "on"}:
        try:
            boot = api_call("/api/demo-worker", {"action": "start"})
            print(
                datetime.now(timezone.utc).isoformat(),
                "worker auto-start",
                json.dumps(boot, default=str),
                flush=True,
            )
        except Exception as exc:  # noqa: BLE001
            print(
                datetime.now(timezone.utc).isoformat(),
                "worker auto-start error",
                repr(exc),
                flush=True,
            )

    print(
        f"zerqen demo worker started at {datetime.now(timezone.utc).isoformat()} "
        f"interval={INTERVAL}s base={BASE_URL}",
        flush=True,
    )
    while True:
        started = time.monotonic()
        try:
            status = api_call("/api/demo-worker")
            if not status.get("enabled"):
                print(datetime.now(timezone.utc).isoformat(), "demo worker disabled", flush=True)
            else:
                heartbeat = api_call("/api/demo-worker", {"action": "heartbeat"})
                result = ensure_paper_initialized(post_paper_cycle())
                execution = execute_approved_signal(result)
                print(
                    datetime.now(timezone.utc).isoformat(),
                    json.dumps(
                        {"heartbeat": heartbeat, "cycle": result, "execution": execution},
                        default=str,
                    )[:5000],
                    flush=True,
                )
        except Exception as exc:  # noqa: BLE001
            print(
                datetime.now(timezone.utc).isoformat(),
                "worker_error",
                repr(exc),
                flush=True,
            )
        elapsed = time.monotonic() - started
        time.sleep(max(1, INTERVAL - elapsed))


if __name__ == "__main__":
    main()
