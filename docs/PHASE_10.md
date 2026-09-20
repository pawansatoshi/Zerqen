# Phase 10 — Integration + Production Hardening

## Objective
Close the gap between individual modules and a single auditable, recoverable trading pipeline.

## Implemented
- centralized order authorization pipeline
- OHLCV data-quality validation
- deterministic order recovery journal primitive
- portfolio risk and live guard integration
- kill-switch enforcement at the pipeline boundary
- Phase 10 tests

## Integration invariant
No order should be considered executable until it has passed:
data validation -> portfolio risk -> mode/kill-switch controls -> live limits when applicable -> execution.

## Recovery
The order journal provides a deterministic interface for recovering known order state after a process restart. A production deployment should back it with durable storage and reconcile against the exchange before resuming.

## Data controls
OHLCV validation checks required fields, timestamps, duplicates, numeric values, positive prices, and non-negative volume.

## Production boundary
Phase 10 hardens the architecture but does not prove profitability or make live trading safe by itself. Before real capital:
1. use an exchange-specific testnet adapter;
2. run extended paper/testnet periods;
3. verify backtest/paper/testnet execution agreement;
4. use durable storage and independent monitoring;
5. start with very small explicitly capped capital if evidence supports proceeding.

## Acceptance criteria
- order authorization has one integration boundary
- bad market data is rejected
- recovery state is represented
- kill switch is enforced
- tests cover hardening controls
