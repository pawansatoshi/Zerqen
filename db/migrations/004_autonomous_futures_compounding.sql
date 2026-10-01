-- Zerqen autonomous Futures compounding state
-- Idempotent migration. PostgreSQL is authoritative.

ALTER TABLE zerqen_futures_paper_state
  ADD COLUMN IF NOT EXISTS day_start_date DATE,
  ADD COLUMN IF NOT EXISTS daily_target NUMERIC,
  ADD COLUMN IF NOT EXISTS daily_target_hit BOOLEAN NOT NULL DEFAULT FALSE;

UPDATE zerqen_futures_paper_state
SET day_start_date = COALESCE(day_start_date, CURRENT_DATE),
    daily_target = COALESCE(daily_target, day_start_equity * 1.08)
WHERE day_start_date IS NULL OR daily_target IS NULL;

CREATE TABLE IF NOT EXISTS zerqen_autonomous_engine (
  engine_id TEXT PRIMARY KEY,
  enabled BOOLEAN NOT NULL DEFAULT FALSE,
  stop_requested BOOLEAN NOT NULL DEFAULT FALSE,
  interval_seconds INTEGER NOT NULL DEFAULT 60,
  last_heartbeat TIMESTAMPTZ,
  last_cycle TIMESTAMPTZ,
  last_error TEXT,
  updated_at TIMESTAMPTZ NOT NULL
);

INSERT INTO zerqen_autonomous_engine(engine_id,enabled,updated_at)
VALUES('default',FALSE,NOW())
ON CONFLICT(engine_id) DO NOTHING;
