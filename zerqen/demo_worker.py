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

HTTP_TIMEOUT = float(os.getenv("ZERQEN_WORKER_HTTP_TIMEOUT_SECONDS", "30"))
DIAGNOSTICS = os.getenv("ZERQEN_WORKER_DIAGNOSTICS", "true").strip().lower() in {"1", "true", "yes", "on"}
DIAGNOSTIC_ONLY = os.getenv("ZERQEN_WORKER_DIAGNOSTIC_ONLY", "false").strip().lower() in {"1", "true", "yes", "on"}


def api_call(label: str, path: str, payload: dict | None = None) -> dict:
    """Call Zerqen and return structured transport diagnostics instead of raising timeouts."""
    started = time.monotonic()
    body = json.dumps(payload).encode() if payload is not None else None
    request = urllib.request.Request(
        BASE_URL + path,
        data=body,
        method="POST" if payload is not None else "GET",
        headers={
            "Content-Type": "application/json",
            "X-Zerqen-Dashboard-Token": TOKEN,
            "User-Agent": "Zerqen-Demo-Worker/1.2",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=HTTP_TIMEOUT) as response:
            raw = response.read().decode()
            elapsed_ms = round((time.monotonic() - started) * 1000)
            try:
                result = json.loads(raw)
            except json.JSONDecodeError:
                result = {
                    "ok": False,
                    "status": response.status,
                    "error": "invalid JSON response",
                    "body_preview": raw[:500],
                }
            if isinstance(result, dict):
                result.setdefault("_worker", {})
                result["_worker"].update({
                    "stage": label,
                    "path": path,
                    "elapsed_ms": elapsed_ms,
                    "http_status": response.status,
                })
                return result
            return {
                "ok": False,
                "error": "non-object JSON response",
                "_worker": {
                    "stage": label,
                    "path": path,
                    "elapsed_ms": elapsed_ms,
                    "http_status": response.status,
                },
            }
    except urllib.error.HTTPError as exc:
        elapsed_ms = round((time.monotonic() - started) * 1000)
        return {
            "ok": False,
            "status": exc.code,
            "error": exc.read().decode(errors="replace")[:1000],
            "_worker": {
                "stage": label,
                "path": path,
                "elapsed_ms": elapsed_ms,
                "http_status": exc.code,
            },
        }
    except (TimeoutError, urllib.error.URLError, OSError) as exc:
        elapsed_ms = round((time.monotonic() - started) * 1000)
        reason = getattr(exc, "reason", None)
        return {
            "ok": False,
            "transport_error": type(exc).__name__,
            "error": str(reason or exc)[:500],
            "_worker": {
                "stage": label,
                "path": path,
                "elapsed_ms": elapsed_ms,
            },
        }


def post_paper_cycle() -> dict:
    return api_call("paper_cycle", "/api/paper", {"action": "autonomous_cycle"})

def post_futures_cycle() -> dict:
    return api_call("futures_autonomous_cycle", "/api/futures-autonomous", {})
def post_futures_mark() -> dict:
    return api_call("futures_mark", "/api/futures-paper", {"action":"mark"})

def autonomous_status() -> dict:
    return api_call("autonomous_status", "/api/autonomous")
def autonomous_action(action: str) -> dict:
    return api_call("autonomous_action", "/api/autonomous", {"action":action})


def ensure_paper_initialized(cycle: dict) -> dict:
    """Initialize the default paper account once, then retry the cycle."""
    if cycle.get("ok") or cycle.get("status") != 409:
        return cycle
    error = str(cycle.get("error") or "")
    if "initialize PAPER mode first" not in error:
        return cycle
    capital = os.getenv("ZERQEN_DEMO_STARTING_CAPITAL", "1000").strip()
    init = api_call(
        "paper_initialize",
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
    return {
        "ok": False,
        "status": init.get("status"),
        "error": init.get("error") or init.get("error_type") or "paper initialization failed",
    }


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
        "paper_test_order",
        "/api/paper",
        {
            "action": "test_order",
            "symbol": symbol,
            "side": side,
            "automatic": True,
            "scanner": True,
            "autonomous_approved": True,
        },
    )


def main() -> None:
    # Dedicated worker services resume the persisted paper/autonomous scheduler on boot.
    # This never enables live trading.
    if os.getenv("ZERQEN_DEMO_WORKER_AUTO_START", "true").strip().lower() in {"1", "true", "yes", "on"}:
        boot = api_call("worker_auto_start", "/api/demo-worker", {"action": "start"})
        print(
            datetime.now(timezone.utc).isoformat(),
            "worker auto-start",
            json.dumps(boot, default=str)[:2500],
            flush=True,
        )

    print(
        f"zerqen demo worker started at {datetime.now(timezone.utc).isoformat()} "
        f"interval={INTERVAL}s timeout={HTTP_TIMEOUT}s diagnostics={DIAGNOSTICS} "
        f"diagnostic_only={DIAGNOSTIC_ONLY} base={BASE_URL}",
        flush=True,
    )

    while True:
        started = time.monotonic()
        try:
            stages: dict[str, dict] = {}

            if DIAGNOSTICS:
                stages["health"] = api_call("health", "/api/health")
                print(
                    datetime.now(timezone.utc).isoformat(),
                    "probe health",
                    json.dumps(stages["health"], default=str)[:1800],
                    flush=True,
                )

            stages["status"] = api_call("demo_worker_get", "/api/demo-worker")
            stages["autonomous"] = autonomous_status()
            print(
                datetime.now(timezone.utc).isoformat(),
                "probe demo-worker GET",
                json.dumps(stages["status"], default=str)[:1800],
                flush=True,
            )

            if stages["status"].get("transport_error"):
                print(
                    datetime.now(timezone.utc).isoformat(),
                    "probe failed at demo_worker_get",
                    json.dumps(stages["status"], default=str),
                    flush=True,
                )
                continue

            auto=stages["autonomous"]
            if not auto.get("enabled") and not auto.get("stop_requested"):
                print(
                    datetime.now(timezone.utc).isoformat(),
                    "demo worker disabled",
                    flush=True,
                )
                continue

            stages["heartbeat"] = api_call(
                "demo_worker_heartbeat",
                "/api/demo-worker",
                {"action": "heartbeat"},
            )
            print(
                datetime.now(timezone.utc).isoformat(),
                "probe demo-worker heartbeat",
                json.dumps(stages["heartbeat"], default=str)[:1800],
                flush=True,
            )

            if DIAGNOSTIC_ONLY:
                print(
                    datetime.now(timezone.utc).isoformat(),
                    "diagnostic-only: skipping autonomous_cycle and execution",
                    flush=True,
                )
                continue

            stages["cycle"] = ensure_paper_initialized(post_paper_cycle())
            print(
                datetime.now(timezone.utc).isoformat(),
                "probe paper autonomous_cycle",
                json.dumps(stages["cycle"], default=str)[:3500],
                flush=True,
            )

            stages["execution"] = execute_approved_signal(stages["cycle"])
            if os.getenv("ZERQEN_FUTURES_AUTONOMOUS","true").strip().lower() in {"1","true","yes","on"}:
                stages["futures_mark"] = post_futures_mark()
                if not auto.get("stop_requested"):
                    stages["futures_cycle"] = post_futures_cycle()
            if auto.get("stop_requested"):
                spot=stages.get("cycle") or {}
                fut=stages.get("futures_mark") or {}
                if int(spot.get("positions_remaining",0) or 0)==0 and not (fut.get("positions") or []):
                    stages["autonomous_finalize_stop"]=autonomous_action("finalize_stop")
            print(
                datetime.now(timezone.utc).isoformat(),
                "probe paper execution",
                json.dumps(stages["execution"], default=str)[:1800],
                flush=True,
            )

            print(
                datetime.now(timezone.utc).isoformat(),
                "worker cycle complete",
                json.dumps(stages, default=str)[:7000],
                flush=True,
            )
        except Exception as exc:  # noqa: BLE001
            print(
                datetime.now(timezone.utc).isoformat(),
                "worker_error_unexpected",
                repr(exc),
                flush=True,
            )
        finally:
            elapsed = time.monotonic() - started
            time.sleep(max(1, INTERVAL - elapsed))


if __name__ == "__main__":
    main()
