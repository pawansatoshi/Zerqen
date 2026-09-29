-- Zerqen paper base schema migration 001
-- PostgreSQL is the authoritative paper-trading state.

CREATE TABLE IF NOT EXISTS zerqen_paper_state (
  account_id TEXT PRIMARY KEY,
  starting_equity NUMERIC NOT NULL,
  cash NUMERIC NOT NULL,
  realized_pnl NUMERIC NOT NULL DEFAULT 0,
  fees NUMERIC NOT NULL DEFAULT 0,
  funding NUMERIC NOT NULL DEFAULT 0,
  slippage NUMERIC NOT NULL DEFAULT 0,
  peak_equity NUMERIC NOT NULL,
  day_start_equity NUMERIC NOT NULL,
  halted BOOLEAN NOT NULL DEFAULT FALSE,
  flatten_requested BOOLEAN NOT NULL DEFAULT FALSE,
  paused BOOLEAN NOT NULL DEFAULT FALSE,
  exchange_id TEXT NOT NULL DEFAULT 'binance',
  symbol TEXT NOT NULL DEFAULT 'BTC/USDT',
  timeframe TEXT NOT NULL DEFAULT '1h',
  last_marked_at TIMESTAMPTZ,
  updated_at TIMESTAMPTZ NOT NULL
);

CREATE TABLE IF NOT EXISTS zerqen_paper_orders (
  client_order_id TEXT PRIMARY KEY,
  account_id TEXT NOT NULL,
  symbol TEXT NOT NULL,
  side TEXT NOT NULL,
  order_type TEXT NOT NULL,
  quantity NUMERIC NOT NULL,
  price NUMERIC,
  status TEXT NOT NULL,
  filled_quantity NUMERIC NOT NULL DEFAULT 0,
  average_price NUMERIC,
  strategy TEXT,
  regime TEXT,
  reason TEXT,
  created_at TIMESTAMPTZ NOT NULL,
  updated_at TIMESTAMPTZ NOT NULL
);

CREATE TABLE IF NOT EXISTS zerqen_paper_fills (
  fill_id TEXT PRIMARY KEY,
  client_order_id TEXT NOT NULL,
  account_id TEXT NOT NULL,
  symbol TEXT NOT NULL,
  side TEXT NOT NULL,
  quantity NUMERIC NOT NULL,
  price NUMERIC NOT NULL,
  fee NUMERIC NOT NULL DEFAULT 0,
  funding NUMERIC NOT NULL DEFAULT 0,
  slippage NUMERIC NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL
);

CREATE TABLE IF NOT EXISTS zerqen_paper_positions (
  account_id TEXT NOT NULL,
  symbol TEXT NOT NULL,
  side TEXT NOT NULL,
  quantity NUMERIC NOT NULL,
  average_entry NUMERIC NOT NULL,
  fees NUMERIC NOT NULL DEFAULT 0,
  funding NUMERIC NOT NULL DEFAULT 0,
  realized_pnl NUMERIC NOT NULL DEFAULT 0,
  updated_at TIMESTAMPTZ NOT NULL,
  PRIMARY KEY(account_id, symbol)
);

CREATE TABLE IF NOT EXISTS zerqen_paper_equity_snapshots (
  id BIGSERIAL PRIMARY KEY,
  account_id TEXT NOT NULL,
  equity NUMERIC NOT NULL,
  cash NUMERIC NOT NULL,
  realized_pnl NUMERIC NOT NULL,
  unrealized_pnl NUMERIC NOT NULL,
  drawdown NUMERIC NOT NULL,
  daily_pnl NUMERIC NOT NULL,
  created_at TIMESTAMPTZ NOT NULL
);

CREATE TABLE IF NOT EXISTS zerqen_paper_events (
  event_id TEXT PRIMARY KEY,
  account_id TEXT NOT NULL,
  event_type TEXT NOT NULL,
  payload JSONB NOT NULL,
  created_at TIMESTAMPTZ NOT NULL
);
