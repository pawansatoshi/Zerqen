# Phase 05 — Portfolio + Compounding

## Objective

Turn validated strategy outputs into a portfolio-level capital allocator with explicit exposure and aggregate risk budgets.

## Implemented

- score-weighted strategy capital allocation with per-strategy caps
- portfolio-level aggregate risk budget
- gross exposure cap
- auditable daily compounding path
- explicit no-trade/no-target-forcing behavior
- Phase 05 tests

## Default research controls

- per-strategy allocation cap: 60%
- aggregate open risk budget: 1.5% of equity
- gross leverage cap: 1.0x
- existing global max drawdown remains 20%
- strategy allocation is based on validated research scores, not expected profit guarantees

## Compounding rules

1. Realized net returns are compounded; unrealized gains are not treated as daily profit.
2. Losses reduce the next day's available capital.
3. A zero-signal day remains flat.
4. The 8% daily figure remains a research hurdle and never becomes a required return.
5. Portfolio constraints are applied before execution.

## Acceptance criteria

- capital allocation is bounded
- aggregate risk is checked before accepting a portfolio
- gross exposure is capped
- compounding is deterministic and auditable
- zero-signal days do not invent returns
- tests cover Phase 05 behavior

## Next phase

Phase 06 will introduce exchange adapters, order lifecycle handling, reconciliation, and a paper/testnet execution boundary.
