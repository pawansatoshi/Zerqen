# Phase 03 — Strategy Lab

## Objective

Turn Zerqen from a single baseline signal into a controlled strategy research lab without allowing the research process to leak future information.

## Implemented

- causal regime classification: trend up, trend down, range, high volatility
- independent trend, mean-reversion, and breakout strategies
- ATR-based volatility filter
- completed-candle higher-timeframe confirmation
- weighted ensemble scoring
- strategy registry for explicit strategy discovery
- train-only parameter selection followed by one out-of-sample holdout evaluation
- dedicated Phase 03 tests

## Research rules

1. Strategy signals may only use information available at the decision candle.
2. Higher-timeframe confirmation must use the last completed higher-timeframe block.
3. Parameter selection happens on training data only.
4. The holdout set is not inspected while selecting parameters.
5. A strategy is not promoted because it meets the 8% daily research hurdle once; robustness matters more than a single backtest result.
6. No strategy may force a trade to chase the daily target.

## Acceptance criteria

- multiple strategy families are independently callable
- regime and volatility features are causal
- ensemble output is deterministic and weighted
- registry prevents accidental duplicate strategy names
- OOS helper makes train/test separation explicit
- tests cover the above behavior

## Next phase

Phase 04 will add rolling walk-forward evaluation, Monte Carlo trade/equity perturbations, drawdown statistics, and robustness gates.
