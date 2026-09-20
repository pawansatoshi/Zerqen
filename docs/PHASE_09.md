# Phase 09 — Guarded Live Trading

## Objective
Complete the live-trading control plane without enabling unattended real-money trading by default.

## Implemented
- hard live capital and order-notional limits
- live-only authorization guard
- continuous reconciliation primitive
- explicit operator approval record
- emergency stop integration with the kill switch
- Phase 09 tests

## Live authorization
A live order requires:
1. explicit LIVE mode
2. equity within the configured capital ceiling
3. order notional within the configured order ceiling
4. daily loss below the configured limit
5. drawdown below the configured limit
6. kill switch clear

## Default posture
The repository does not ship exchange credentials and does not automatically enable live trading. Phase 09 provides the control plane; an exchange-specific adapter and operational deployment remain separate concerns.

## Emergency behavior
An emergency stop trips the kill switch and blocks new orders. Existing exchange positions require exchange-specific flattening/reconciliation procedures; this primitive does not falsely claim to close them.

## Operational approval
Live release requires a named operator and a reason. Approval is an auditable record, not a prediction of profitability.

## Acceptance criteria
- live authorization is explicit
- capital and order limits are hard checks
- kill switch blocks new orders
- reconciliation detects drift
- operator approval is represented
- tests cover the guardrails

## Project completion boundary
Zerqen's nine-phase architecture is now implemented. Further work should focus on exchange-specific adapters, deployment, testnet evidence, monitoring, and controlled validation rather than assuming live profitability.
