# Phase 08 — Testnet / Dry Run

## Objective
Create an explicit operating-mode boundary and make dry-run/testnet promotion require deterministic preflight checks.

## Implemented
- explicit backtest, paper, testnet, and live modes
- preflight validation
- dry-run executor that always uses paper execution
- kill switch
- promotion gate
- Phase 08 tests

## Safety boundary
Paper and dry-run execution cannot contact a live exchange. Live mode requires credentials, valid risk controls, balanced reconciliation, and an explicit live-enable approval.

## Promotion sequence
backtest -> paper -> testnet -> guarded live

A mode change must not be treated as proof of profitability. Each stage exists to validate a different class of failure.

## Preflight checks
- market data available
- risk limits valid
- reconciliation balanced
- credentials present for testnet/live
- explicit live enable for live

## Kill switch
The kill switch blocks new orders after a critical condition such as a drawdown breach, reconciliation drift, execution failure, or operator stop.

## Acceptance criteria
- modes are explicit
- dry-run cannot become live accidentally
- live requires explicit approval
- preflight failures are machine-readable
- kill switch blocks orders
- tests cover Phase 08

## Next phase
Phase 09 will define guarded live execution with exchange-specific controls, hard capital limits, operational approval, and continuous reconciliation.
