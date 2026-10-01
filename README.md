# Zerqen

**Adaptive Quantitative Compounding Engine**

Zerqen is an open-source research and execution framework for systematic crypto trading, risk-controlled position sizing, autonomous paper trading, and daily capital compounding.

> **Research target:** evaluate whether an 8% daily net-return hurdle can be approached under realistic market, fee, slippage, and drawdown assumptions. Zerqen does **not** promise or assume 8% daily returns.

## Current project handoff

**Read these first when joining the project:**

1. `AGENTS.md` — persistent rules for every coding agent.
2. `docs/ZERQEN_MASTER_CONTEXT.md` — living source of truth for product requirements, architecture, invariants, current state, known issues, and next actions.

The master context is maintained in GitHub so a fresh chat/agent can continue without requiring the user to re-explain the project. Every meaningful implementation or product decision must update it.

## Design principles

- research before execution
- deterministic market filtering before expensive AI review
- structured AI analysis with deterministic risk authority
- fees and slippage included
- no look-ahead data
- risk limits before profit targets
- daily compounding from actual equity
- no forced trades to reach the 8% research hurdle
- no martingale recovery logic
- paper/live boundaries remain explicit
- live trading disabled by default
- durable ledger/state must remain auditable

## Autonomous architecture

```
market data
    ↓
deterministic Top-50 scan
    ↓
shortlist
    ↓
AI deep analysis
    ↓
risk engine / safety gates
    ↓
paper execution
    ↓
durable positions + P&L + ledger
    ↓
equity / compounding
    ↓
truthful dashboard + persistent worker
```

The browser is a control/observability surface. The persistent Voroa/ZERQEN worker is responsible for autonomous continuation when the browser is closed.

## Spot + Futures contract

Spot and Futures are independent engines with independent:

- start/stop state
- equity and daily baseline
- 8% research target
- risk state
- positions
- P&L
- compounding history
- paper ledger
- autonomous state

Starting one must never start the other.

Stopping an engine prevents new entries but does not force-close existing positions; existing positions remain managed until flat unless a future explicit product decision changes this.

## Risk contract

Known baseline:

- 0.5% risk/trade
- 3% daily loss breaker
- 20% max drawdown
- Futures leverage constrained to 1x–5x

Risk is authoritative. AI cannot override risk controls.

The 8% objective is a research/compounding hurdle, never a trade quota or guaranteed return.

## Current implementation state

The repository currently contains the autonomous Spot/Futures paper architecture, persistent worker path, durable paper ledgers, dashboard controls/observability, Futures charting, AI review path, and compounding state.

PR #31 was merged into main at:

`d5a8a28f314f883201c944ba42c9e2e1f04b6ef1`

That fix removed a Spot Start bottleneck where paper status attempted remote market-data fetching even with no open positions.

**Do not treat deployment status alone as proof of runtime correctness.** End-to-end Start/Stop and long-duration worker evidence remain verification work.

## Historical research phases

The repository began as a deterministic research/backtesting engine and has evolved into the autonomous paper-trading architecture. Older phase documents remain useful as historical design context.

For the current implementation state and priorities, use `docs/ZERQEN_MASTER_CONTEXT.md`.

## Quick start

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
pytest
zerqen --help
zerqen backtest --csv data/sample_btcusdt_15m.csv --starting-capital 10000
```

On Windows:

```powershell
.venv\Scripts\activate
```

## Data format

CSV columns:

```text
timestamp,open,high,low,close,volume
```

Timestamp must be ISO-8601 or a parseable datetime.

## Safety

Zerqen is research software. Historical backtests are not forecasts. Backtests can differ materially from real execution because of fills, latency, spread, funding, liquidity, exchange rules, and market regime changes. Start with historical validation and paper/dry-run testing before risking capital.

Never commit exchange API keys, dashboard tokens, vault keys, database URLs, or other secrets.

## License

MIT
