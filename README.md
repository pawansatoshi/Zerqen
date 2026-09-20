# Zerqen

**Adaptive Quantitative Compounding Engine**

Zerqen is an open-source research and execution framework for systematic crypto trading, risk-controlled position sizing, and daily capital compounding.

> **Research target:** evaluate whether an 8% daily net-return hurdle can be approached under realistic market, fee, slippage, and drawdown assumptions. Zerqen does **not** promise or assume 8% daily returns.

## Design principles

- research before execution
- deterministic backtests
- fees and slippage included
- no look-ahead data
- risk limits before profit targets
- daily compounding from realized equity
- walk-forward validation before paper/live deployment
- no martingale recovery logic
- live trading disabled by default

## Architecture

```
market data
    ↓
indicators → regime detection → strategy signals
    ↓
risk engine → position sizing → execution model
    ↓
realized P&L → portfolio equity → compounder
    ↓
validation: backtest → walk-forward → Monte Carlo → dry run
```

## Repository status

**Phase 01 — Research Core:** implemented.

Included:
- OHLCV CSV loader
- EMA / RSI / ATR indicators
- trend + momentum strategy
- fee/slippage-aware backtester
- risk-based position sizing
- stop-loss / take-profit
- daily equity compounding
- drawdown and performance metrics
- CLI
- unit tests
- CI

Planned:
- Phase 02: multi-strategy/regime engine
- Phase 03: walk-forward optimizer
- Phase 04: Monte Carlo robustness
- Phase 05: exchange adapters and paper trading
- Phase 06: dashboard/observability
- Phase 07: guarded live execution

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

```
timestamp,open,high,low,close,volume
```

Timestamp must be ISO-8601 or a parseable datetime.

## Safety

Zerqen is research software. Historical backtests are not forecasts. Backtests can differ materially from real execution because of fills, latency, spread, funding, liquidity, exchange rules, and market regime changes. Start with historical validation and paper/dry-run testing before risking capital.

Freqtrade's documentation similarly recommends dry-run validation after backtesting and notes that past results do not guarantee future performance. https://docs.freqtrade.io/en/stable/strategy-101/

## License

MIT
