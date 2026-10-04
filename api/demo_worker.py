from __future__ import annotations

import os
from datetime import datetime, timezone

RUN_INTERVAL_SECONDS = int(os.getenv("ZERQEN_DEMO_INTERVAL_SECONDS", "60"))


def _db():
    import psycopg

    url = os.environ.get("DATABASE_URL")
    if not url:
        raise RuntimeError("database unavailable")
    return psycopg.connect(url, connect_timeout=8)


def _ensure_schema_once(conn):
    """Explicit migration helper; never run on the hot request path."""
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


def ensure_schema(conn):
    # Compatibility/migration helper for explicit callers and tests.
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
        """SELECT enabled,interval_seconds,heartbeat_at,last_cycle_at,last_error
           FROM zerqen_demo_worker WHERE worker_id='default'"""
    ).fetchone()
    if row is None:
        raise RuntimeError("worker state is not initialized")
    return _status_from_row(row)


def worker_status():
    with _db() as conn:
        return _read_status(conn)


def heartbeat():
    with _db() as conn:
        now = datetime.now(timezone.utc)
        conn.execute(
            "UPDATE zerqen_demo_worker SET heartbeat_at=%s,updated_at=%s WHERE worker_id='default'",
            (now, now),
        )
        conn.commit()
        return _read_status(conn)


def set_enabled(enabled: bool):
    with _db() as conn:
        # Worker control is an explicit lifecycle action; schema creation is allowed here,
        # but never on the recurring status/heartbeat hot path.
        _ensure_schema_once(conn)
        now = datetime.now(timezone.utc)
        conn.execute(
            "UPDATE zerqen_demo_worker SET enabled=%s,updated_at=%s WHERE worker_id='default'",
            (enabled, now),
        )
        conn.commit()
        return _read_status(conn)
