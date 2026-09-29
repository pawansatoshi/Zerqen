# Zerqen Production Readiness

Status date: 2026-09-29
Branch: `audit/production-hardening-2026-09-29`

This is an evidence-based readiness snapshot. A PASS requires verified implementation plus tests/operational evidence. Documentation alone is insufficient.

| Area | Status | Evidence / blocker |
|---|---|---|
| RESEARCH | FAIL | Backtest correctness has been hardened, but full reproducibility metadata and execution-equivalence evidence are incomplete. |
| DATA INTEGRITY | FAIL | OHLCV validation is stronger, but live feed normalization/freshness/gap enforcement is not yet a persistent worker concern. |
| STRATEGY | FAIL | Strategy primitives exist; canonical multi-strategy/regime production pipeline is incomplete. |
| RISK | FAIL | Core limits exist, but authoritative portfolio-wide continuous enforcement is incomplete. |
| PORTFOLIO | FAIL | Portfolio primitives exist; fill-driven authoritative accounting is incomplete. |
| EXECUTION | FAIL | Order lifecycle hardened, but durable exchange execution/recovery is incomplete. |
| POSITION ACCOUNTING | FAIL | No authoritative persistent fill-driven position ledger yet. |
| RECONCILIATION | FAIL | Quantity primitive exists; full balance/order/fill/position reconciliation is incomplete. |
| EXCHANGE CONNECTIVITY | FAIL | CCXT adapter exists, but exchange-specific production evidence and user-stream support are incomplete. |
| SECURITY | FAIL | Credential encryption exists; session hardening, rate limiting and full security verification remain. |
| DATABASE | FAIL | Credential table exists; full trading schema/migrations/event store are incomplete. |
| REALTIME | FAIL | Browser BTC public ticker exists; persistent multi-asset market/private worker does not. |
| OBSERVABILITY | FAIL | Telemetry primitives exist; production event/metric pipeline is incomplete. |
| DASHBOARD | FAIL | Dashboard is functional but remains partly browser-computed and lacks the complete authoritative backend state model. |
| PAPER TRADING | FAIL | Paper adapter exists; long-duration evidence has not been demonstrated. |
| TESTNET | FAIL | Testnet control path exists; verified long-duration exchange evidence has not been demonstrated. |
| LIVE GATE | FAIL | Correctly blocked pending all upstream gates and explicit manual approval. |
| DEPLOYMENT | FAIL | Vercel preview deployments are being built; production main remains on the prior verified deployment. |

## Current safety decision

**Live trading: NOT PERMITTED.**

No real trading capital should be used from this branch.

## Immediate gates to close

1. CI green with the hardening tests.
2. Durable order/fill/position/event persistence.
3. Full reconciliation and restart recovery.
4. Persistent trading worker with market/private streams.
5. Paper and testnet evidence.
6. Security/session hardening.
7. Production endpoint verification.
8. Independent manual live approval only after all gates pass.
