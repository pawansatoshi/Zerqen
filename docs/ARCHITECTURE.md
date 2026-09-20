# Architecture

## Core layers

### Data
Canonical OHLCV ingestion and future exchange adapters.

### Indicators
Pure, deterministic transformations of observed market data.

### Strategies
Generate signals only. Strategies do not size positions or submit orders.

### Risk
Converts equity and stop distance into a bounded position size. Global risk limits can veto trades.

### Execution
Responsible for realistic fill assumptions in research and later exchange adapters.

### Portfolio
Owns equity, realized P&L, exposure, and compounding state.

### Validation
Backtest, walk-forward, Monte Carlo, stress and sensitivity analysis.

## Non-negotiable invariants

- No future candle information may influence a prior signal.
- A strategy cannot override risk limits.
- A target return cannot force an entry.
- Compounding uses realized equity, not hypothetical profit.
- Live execution is opt-in and must have independent kill switches.
- API credentials are never committed.
