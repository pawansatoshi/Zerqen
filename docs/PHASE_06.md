# Phase 06 — Exchange Execution

## Objective
Create a deterministic execution boundary between research signals and exchange orders, with paper execution as the default.

## Implemented
- explicit order lifecycle state model
- idempotent client order IDs
- exchange adapter protocol
- deterministic paper exchange adapter
- execution service separating signals from order submission
- position reconciliation primitive
- tests for fill behavior, idempotency, lifecycle safety, and reconciliation

## Safety boundary
Phase 06 does not enable live trading or require exchange credentials. The default adapter is PaperExchangeAdapter. A future live adapter must remain behind an explicit operational configuration gate.

## Order lifecycle
NEW -> SUBMITTED -> PARTIALLY_FILLED -> FILLED
Terminal alternatives: NEW -> CANCELED/REJECTED; SUBMITTED -> CANCELED/REJECTED; PARTIALLY_FILLED -> CANCELED/REJECTED.

## Controls
1. Client order IDs are idempotency keys.
2. Duplicate submissions return the original adapter result.
3. Invalid price or quantity is rejected.
4. Research code does not directly call an exchange adapter.
5. Reconciliation compares expected and actual position quantity.
6. Paper fills reuse the fee/slippage execution model.

## Next phase
Phase 07 will add observability, structured execution/audit events, run reports, and operational metrics.
