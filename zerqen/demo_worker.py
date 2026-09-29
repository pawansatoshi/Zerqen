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


def post_paper_cycle() -> dict:
    payload = json.dumps({"action": "cycle"}).encode()
    request = urllib.request.Request(
        BASE_URL + "/api/paper",
        data=payload,
        method="POST",
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
        body = exc.read().decode(errors="replace")
        return {"ok": False, "status": exc.code, "error": body[:1000]}


def main() -> None:
    print(
        f"zerqen demo worker started at {datetime.now(timezone.utc).isoformat()} "
        f"interval={INTERVAL}s base={BASE_URL}",
        flush=True,
    )
    while True:
        started = time.monotonic()
        try:
            result = post_paper_cycle()
            print(
                datetime.now(timezone.utc).isoformat(),
                json.dumps(result, default=str)[:4000],
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
