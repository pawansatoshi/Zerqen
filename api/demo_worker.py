from __future__ import annotations

import os
from datetime import datetime, timezone

RUN_INTERVAL_SECONDS = int(os.getenv("ZERQEN_DEMO_INTERVAL_SECONDS", "60"))

# Vercel/Fluid Compute may reuse a warm Python instance. Avoid running schema DDL
# on every worker request: DDL can contend with concurrent Postgres traffic and
# is unnecessary once this process has initialized the worker table.
_SCHEMA_READY = False


def _db():
    from api._paper import db
    return db()


def _ensure_schema_once(conn):
    global _SCHEMA_READY
    if _SCHEMA_READY:
        return

    conn.execute("""
        CREATE TABLE IF NOT EXISTS zerqen_demo_worker (
            worker_id TEXT PRIMARY KEY,
            enabled BOOLEAN NOT NULL DEFAULT FALSE,
            interval_seconds INTEGER NOT NULL DEFAULT 60,
            heartbeat_at TIMESTAMPTZ,
            last_cycle_at TIMESTAMPTZ,
            last_error TEXT,
            updated_at TIMESTAMPTZ NOT NULL
        )
    """)
    conn.execute(
        """INSERT INTO zerqen_demo_worker(worker_id,enabled,interval_seconds,updated_at)
           VALUES('default',FALSE,%s,%s)
           ON CONFLICT(worker_id) DO NOTHING""",
        (RUN_INTERVAL_SECONDS, datetime.now(timezone.utc)),
    )
    conn.commit()
    _SCHEMA_READY = True


def ensure_schema(conn):
    # Kept as a small compatibility wrapper for callers/tests.
    _ensure_schema_once(conn)


def _status_from_row(row):
    return {
        "enabled": bool(row[0]) if row else False,
        "interval_seconds": int(row[1]) if row else RUN_INTERVAL_SECONDS,
        "heartbeat_at": row[2].isoformat() if row and row[2] else None,
        "last_cycle_at": row[3].isoformat() if row and row[3] else None,
        "last_error": row[4] if row else None,
        "process_alive": None,
        "mobile_independent": True,
        "live_trading": False,
    }


def _read_status(conn):
    row = conn.execute(
        """SELECT enabled,interval_seconds,heartbeat_at,last_cycle_at,last_error,updated_at
           FROM zerqen_demo_worker WHERE worker_id='default'"""
    ).fetchone()
    return _status_from_row(row)


def worker_status():
    with _db() as conn:
        _ensure_schema_once(conn)
        return _read_status(conn)


def heartbeat():
    # One connection + one schema bootstrap + one UPDATE + one SELECT.
    # Do not call worker_status() here: the previous implementation opened a
    # second DB connection and repeated schema DDL on every heartbeat.
    with _db() as conn:
        _ensure_schema_once(conn)
        now = datetime.now(timezone.utc)
        conn.execute(
            "UPDATE zerqen_demo_worker SET heartbeat_at=%s,updated_at=%s WHERE worker_id='default'",
            (now, now),
        )
        conn.commit()
        return _read_status(conn)


def set_enabled(enabled: bool):
    with _db() as conn:
        _ensure_schema_once(conn)
        now = datetime.now(timezone.utc)
        conn.execute(
            "UPDATE zerqen_demo_worker SET enabled=%s,updated_at=%s WHERE worker_id='default'",
            (enabled, now),
        )
        conn.commit()
        return _read_status(conn)
