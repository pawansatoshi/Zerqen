# Phase 02 — Research Integrity

## Objective

Make backtests harder to fool.

Phase 02 adds deterministic execution costs, chronology/leakage guards, a buy-and-hold benchmark, daily-return aggregation, and parameter sensitivity tooling.

## Completed

- deterministic candle execution model
- fee + slippage at fills
- chronological timestamp validation
- duplicate timestamp detection
- future/lead column guard
- buy-and-hold benchmark
- daily equity return aggregation
- parameter grid sensitivity primitive
- dedicated tests

## Execution assumptions

The candle model is deliberately conservative:

- buys pay positive slippage
- sells receive negative slippage
- fees apply to both sides
- fills are deterministic

It does **not** model order-book depth, latency, funding, partial fills, queue position or liquidation. Those belong to later execution phases.

## Research rule

A strategy cannot be called robust because one parameter combination performs well. Phase 02 therefore introduces parameter sensitivity so the research process can inspect whether nearby parameter values also work.

The benchmark must always be reported alongside strategy results.

## Acceptance criteria

Phase 02 is complete when:

- the test suite passes;
- malformed/duplicated chronology is rejected;
- execution costs are explicit;
- benchmark return is available;
- daily returns can be measured;
- sensitivity analysis is reproducible;
- no future-looking columns are accepted by the leakage guard.

## Next

Phase 03 expands the strategy laboratory with multiple strategy families and regime classification.
