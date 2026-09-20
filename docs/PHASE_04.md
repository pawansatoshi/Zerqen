# Phase 04 — Walk-Forward + Monte Carlo Robustness

## Objective

Evaluate strategy robustness across changing market windows and randomized return paths before any execution phase.

## Implemented

- true peak-to-trough drawdown calculations
- rolling walk-forward parameter selection
- per-window out-of-sample scoring
- deterministic bootstrap-style Monte Carlo resampling
- terminal-return and drawdown quantiles
- explicit robustness gates
- dedicated Phase 04 tests

## Research controls

1. Each walk-forward window selects parameters using its training segment only.
2. The immediately following test segment is evaluated with the selected parameters.
3. Monte Carlo is a robustness diagnostic, not a prediction engine.
4. The random seed is recorded so simulations are reproducible.
5. A negative or unstable robustness profile blocks strategy promotion.
6. The 8% daily research hurdle is not used as a forced trade condition.

## Acceptance criteria

- rolling walk-forward evaluation is available
- each test window is out-of-sample relative to its training window
- true maximum drawdown is measured from the equity peak
- Monte Carlo results are reproducible
- robustness gates return explicit pass/fail reasons
- tests cover the Phase 04 components

## Next phase

Phase 05 will integrate portfolio allocation, compounding, exposure budgets, and risk-aware capital allocation.
