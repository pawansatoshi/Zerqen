from __future__ import annotations

import os
import threading
import time
import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

RUN_INTERVAL_SECONDS = int(os.getenv("ZERQEN_DEMO_INTERVAL_SECONDS", "60"))
LOCK_KEY = 81429371
_worker: threading.Thread | None = None
_stop = threading.Event()


def _db():
    from api._paper import get_db
    return get_db()


def ensure_schema(conn):
    conn.execute("""
        CREATE TABLE IF NOT EXISTS zerqen_demo_worker (
            worker_id TEXT PRIMARY KEY,
            enabled BOOLEAN NOT NULL DEFAULT FALSE,
            interval_seconds INTEGER NOT NULL DEFAULT 60,
            lease_until TIMESTAMPTZ,
            heartbeat_at TIMESTAMPTZ,
            last_cycle_at TIMESTAMPTZ,
            last_error TEXT,
            updated_at TIMESTAMPTZ NOT NULL
        )
    """)
    conn.execute("""
        INSERT INTO zerqen_demo_worker(worker_id,enabled,interval_seconds,updated_at)
        VALUES('default',FALSE,%s,%s)
        ON CONFLICT(worker_id) DO NOTHING
    """, (RUN_INTERVAL_SECONDS, datetime.now(timezone.utc)))
    conn.commit()


def _claim_lease(conn) -> bool:
    # PostgreSQL advisory lock prevents duplicate demo workers on multiple instances.
    row = conn.execute("SELECT pg_try_advisory_lock(%s)", (LOCK_KEY,)).fetchone()
    return bool(row and row[0])


def _release_lease(conn):
    try:
        conn.execute("SELECT pg_advisory_unlock(%s)", (LOCK_KEY,))
        conn.commit()
    except Exception:
        pass


def _enabled(conn) -> bool:
    row = conn.execute("SELECT enabled FROM zerqen_demo_worker WHERE worker_id='default'").fetchone()
    return bool(row and row[0])


def run_cycle_once():
    from api._paper import get_state, cycle
    with _db() as conn:
        ensure_schema(conn)
        state = get_state(conn)
        if not state:
            return {"ok": False, "status": "NOT_INITIALIZED"}
        if not _enabled(conn):
            return {"ok": True, "status": "DISABLED"}
        # Reuse the exact paper cycle/risk/ledger path instead of duplicating strategy logic.
        result = cycle()
        return {"ok": True, "status": "CYCLE_COMPLETE", "result": result}


def worker_loop():
    while not _stop.is_set():
        conn = None
        try:
            conn = _db()
            ensure_schema(conn)
            if not _claim_lease(conn):
                time.sleep(RUN_INTERVAL_SECONDS)
                continue
            if not _enabled(conn):
                _release_lease(conn)
                time.sleep(RUN_INTERVAL_SECONDS)
                continue
            now = datetime.now(timezone.utc)
            conn.execute(
                "UPDATE zerqen_demo_worker SET heartbeat_at=%s,updated_at=%s WHERE worker_id='default'",
                (now, now),
            )
            conn.commit()
            _release_lease(conn)
            result = run_cycle_once()
            with _db() as update_conn:
                now = datetime.now(timezone.utc)
                update_conn.execute(
                    """UPDATE zerqen_demo_worker
                       SET last_cycle_at=%s,last_error=NULL,heartbeat_at=%s,updated_at=%s
                       WHERE worker_id='default'""",
                    (now, now, now),
                )
                update_conn.commit()
            logger.info("demo worker cycle: %s", result.get("status"))
        except Exception as exc:
            logger.exception("demo worker cycle failed")
            try:
                with _db() as err_conn:
                    now = datetime.now(timezone.utc)
                    err_conn.execute(
                        "UPDATE zerqen_demo_worker SET last_error=%s,heartbeat_at=%s,updated_at=%s WHERE worker_id='default'",
                        (str(exc)[:1000], now, now),
                    )
                    err_conn.commit()
            except Exception:
                pass
        finally:
            if conn:
                try:
                    conn.close()
                except Exception:
                    pass
        _stop.wait(RUN_INTERVAL_SECONDS)


def start_worker():
    global _worker
    if _worker and _worker.is_alive():
        return
    _stop.clear()
    _worker = threading.Thread(target=worker_loop, name="zerqen-demo-worker", daemon=True)
    _worker.start()


def stop_worker():
    _stop.set()


def worker_status():
    with _db() as conn:
        ensure_schema(conn)
        row = conn.execute(
            """SELECT enabled,interval_seconds,lease_until,heartbeat_at,last_cycle_at,last_error,updated_at
               FROM zerqen_demo_worker WHERE worker_id='default'"""
        ).fetchone()
    return {
        "enabled": bool(row[0]) if row else False,
        "interval_seconds": int(row[1]) if row else RUN_INTERVAL_SECONDS,
        "lease_until": row[2].isoformat() if row and row[2] else None,
        "heartbeat_at": row[3].isoformat() if row and row[3] else None,
        "last_cycle_at": row[4].isoformat() if row and row[4] else None,
        "last_error": row[5] if row else None,
        "updated_at": row[6].isoformat() if row and row[6] else None,
        "process_alive": bool(_worker and _worker.is_alive()),
        "mobile_independent": True,
        "live_trading": False,
    }


def set_enabled(enabled: bool):
    with _db() as conn:
        ensure_schema(conn)
        now = datetime.now(timezone.utc)
        conn.execute(
            "UPDATE zerqen_demo_worker SET enabled=%s,updated_at=%s WHERE worker_id='default'",
            (enabled, now),
        )
        conn.commit()
    if enabled:
        start_worker()
    return worker_status()
