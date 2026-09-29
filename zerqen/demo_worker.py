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
    return api_call("/api/paper", {"action": "cycle"})


def main() -> None:
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
                result = post_paper_cycle()
                print(
                    datetime.now(timezone.utc).isoformat(),
                    json.dumps({"heartbeat": heartbeat, "cycle": result}, default=str)[:4000],
                    flush=True,
                )
        except Exception as exc:
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
