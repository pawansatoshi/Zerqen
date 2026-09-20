# Zerqen Roadmap

## Phase 01 — Research Core
Status: **implemented in v0.1**

- [x] package skeleton
- [x] deterministic OHLCV loader
- [x] EMA/RSI/ATR indicators
- [x] baseline trend/momentum strategy
- [x] risk-based position sizing
- [x] stop-loss / take-profit
- [x] fee/slippage model
- [x] equity and compounding primitives
- [x] CLI
- [x] unit tests
- [x] CI

## Phase 02 — Research Integrity
Status: **next**

- [ ] trade-level equity curve
- [ ] daily return aggregation
- [ ] realistic candle execution model
- [ ] funding-rate model for futures
- [ ] spread/order-book model
- [ ] lookahead/recursive bias tests
- [ ] benchmark buy-and-hold
- [ ] parameter sensitivity reports

## Phase 03 — Strategy Lab

- [ ] regime classifier
- [ ] trend strategy
- [ ] mean reversion
- [ ] breakout
- [ ] volatility filter
- [ ] multi-timeframe confirmation
- [ ] ensemble scoring
- [ ] strategy registry
- [ ] parameter search with out-of-sample holdout

## Phase 04 — Validation

- [ ] walk-forward optimization
- [ ] rolling train/test windows
- [ ] Monte Carlo trade-order resampling
- [ ] bootstrap confidence intervals
- [ ] stress tests
- [ ] slippage sensitivity
- [ ] fee sensitivity
- [ ] liquidity constraints
- [ ] drawdown-duration analysis

## Phase 05 — Portfolio & Compounding

- [ ] multi-pair portfolio
- [ ] capital allocator
- [ ] daily realized-equity compounding
- [ ] exposure caps
- [ ] correlation-aware allocation
- [ ] daily loss circuit breaker
- [ ] global drawdown circuit breaker
- [ ] recovery mode
- [ ] no-trade mode when edge is absent

## Phase 06 — Execution

- [ ] exchange abstraction
- [ ] CCXT adapter
- [ ] websocket market data
- [ ] order state machine
- [ ] retry/idempotency
- [ ] partial fills
- [ ] latency metrics
- [ ] paper trading
- [ ] testnet adapter

## Phase 07 — Observability

- [ ] web dashboard
- [ ] equity curve
- [ ] daily target tracking
- [ ] exposure
- [ ] drawdown
- [ ] open orders
- [ ] strategy attribution
- [ ] structured audit log
- [ ] alerts

## Phase 08 — Guarded Live Trading

Only after passing validation gates:

- [ ] dry-run stability gate
- [ ] testnet stability gate
- [ ] live capital hard cap
- [ ] emergency stop
- [ ] API-key safety
- [ ] withdrawal permissions disabled
- [ ] reconciliation
- [ ] incident runbook

## Performance gate

The project must never treat 8% daily as guaranteed.

The 8% figure is an experimental hurdle. A strategy is only considered robust if it survives:

1. fees and slippage
2. out-of-sample data
3. walk-forward testing
4. multiple market regimes
5. drawdown limits
6. Monte Carlo perturbation
7. paper/dry-run execution

A high backtest return with unacceptable drawdown or unstable out-of-sample performance fails the gate.
