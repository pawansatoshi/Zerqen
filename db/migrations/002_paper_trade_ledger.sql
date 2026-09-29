-- Zerqen paper ledger schema migration 002
-- PostgreSQL is the source of truth. This migration is idempotent.

CREATE TABLE IF NOT EXISTS zerqen_paper_trades (
  trade_id TEXT PRIMARY KEY,
  account_id TEXT NOT NULL,
  signal_id TEXT,
  entry_order_id TEXT,
  exit_order_id TEXT,
  entry_fill_id TEXT,
  exit_fill_id TEXT,
  exchange_id TEXT NOT NULL,
  symbol TEXT NOT NULL,
  timeframe TEXT NOT NULL,
  side TEXT NOT NULL,
  strategy TEXT,
  regime TEXT,
  signal_timestamp TIMESTAMPTZ,
  entry_timestamp TIMESTAMPTZ NOT NULL,
  exit_timestamp TIMESTAMPTZ NOT NULL,
  entry_price NUMERIC NOT NULL,
  exit_price NUMERIC NOT NULL,
  quantity NUMERIC NOT NULL,
  stop_price NUMERIC,
  target_price NUMERIC,
  risk_at_entry NUMERIC,
  gross_pnl NUMERIC NOT NULL,
  fees NUMERIC NOT NULL DEFAULT 0,
  slippage NUMERIC NOT NULL DEFAULT 0,
  funding NUMERIC NOT NULL DEFAULT 0,
  net_pnl NUMERIC NOT NULL,
  r_multiple NUMERIC,
  opening_equity NUMERIC NOT NULL,
  closing_equity NUMERIC NOT NULL,
  status TEXT NOT NULL,
  duration_seconds BIGINT
);

CREATE TABLE IF NOT EXISTS zerqen_paper_decisions (
  decision_id TEXT PRIMARY KEY,
  account_id TEXT NOT NULL,
  signal_id TEXT NOT NULL,
  exchange_id TEXT NOT NULL,
  symbol TEXT NOT NULL,
  timeframe TEXT NOT NULL,
  strategy TEXT,
  regime TEXT,
  signal_timestamp TIMESTAMPTZ NOT NULL,
  signal_direction TEXT,
  ema9 NUMERIC,
  ema21 NUMERIC,
  rsi NUMERIC,
  atr NUMERIC,
  risk_per_trade NUMERIC,
  aggregate_open_risk NUMERIC,
  open_positions INTEGER,
  daily_loss NUMERIC,
  drawdown NUMERIC,
  gross_exposure NUMERIC,
  allocation NUMERIC,
  risk_decision TEXT NOT NULL,
  rejected BOOLEAN NOT NULL DEFAULT FALSE,
  rejection_reason TEXT,
  order_id TEXT
);

ALTER TABLE zerqen_paper_orders ADD COLUMN IF NOT EXISTS timeframe TEXT NOT NULL DEFAULT '1h';
ALTER TABLE zerqen_paper_orders ADD COLUMN IF NOT EXISTS risk_at_entry NUMERIC;
ALTER TABLE zerqen_paper_orders ADD COLUMN IF NOT EXISTS opening_equity NUMERIC;
ALTER TABLE zerqen_paper_orders ADD COLUMN IF NOT EXISTS signal_id TEXT;
ALTER TABLE zerqen_paper_orders ADD COLUMN IF NOT EXISTS stop_price NUMERIC;
ALTER TABLE zerqen_paper_orders ADD COLUMN IF NOT EXISTS target_price NUMERIC;
ALTER TABLE zerqen_paper_orders ADD COLUMN IF NOT EXISTS exchange_id TEXT NOT NULL DEFAULT 'binance';
ALTER TABLE zerqen_paper_fills ADD COLUMN IF NOT EXISTS requested_price NUMERIC;
ALTER TABLE zerqen_paper_positions ADD COLUMN IF NOT EXISTS stop_price NUMERIC;
ALTER TABLE zerqen_paper_positions ADD COLUMN IF NOT EXISTS target_price NUMERIC;
ALTER TABLE zerqen_paper_positions ADD COLUMN IF NOT EXISTS entry_order_id TEXT;
ALTER TABLE zerqen_paper_positions ADD COLUMN IF NOT EXISTS entry_fill_id TEXT;
ALTER TABLE zerqen_paper_positions ADD COLUMN IF NOT EXISTS opened_at TIMESTAMPTZ;
ALTER TABLE zerqen_paper_positions ADD COLUMN IF NOT EXISTS strategy TEXT;
ALTER TABLE zerqen_paper_positions ADD COLUMN IF NOT EXISTS regime TEXT;
ALTER TABLE zerqen_paper_positions ADD COLUMN IF NOT EXISTS risk_at_entry NUMERIC;
ALTER TABLE zerqen_paper_positions ADD COLUMN IF NOT EXISTS opening_equity NUMERIC;
ALTER TABLE zerqen_paper_equity_snapshots ADD COLUMN IF NOT EXISTS gross_exposure NUMERIC NOT NULL DEFAULT 0;
ALTER TABLE zerqen_paper_equity_snapshots ADD COLUMN IF NOT EXISTS open_risk NUMERIC NOT NULL DEFAULT 0;
ALTER TABLE zerqen_paper_equity_snapshots ADD COLUMN IF NOT EXISTS allocation NUMERIC NOT NULL DEFAULT 0;
ALTER TABLE zerqen_paper_equity_snapshots ADD COLUMN IF NOT EXISTS cumulative_pnl NUMERIC NOT NULL DEFAULT 0;

CREATE INDEX IF NOT EXISTS idx_paper_trades_account_exit ON zerqen_paper_trades(account_id, exit_timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_paper_decisions_account_signal ON zerqen_paper_decisions(account_id, signal_timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_paper_events_account_created ON zerqen_paper_events(account_id, created_at DESC);
