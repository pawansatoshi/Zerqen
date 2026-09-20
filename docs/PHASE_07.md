# Phase 07 — Dashboard + Observability

## Objective
Make Zerqen operationally inspectable: important execution events can be audited, portfolio state can be snapshotted, health can be evaluated, and runs can produce structured reports.

## Implemented
- append-only in-memory audit event log
- JSONL export for execution and research events
- portfolio telemetry snapshots
- system health checks
- structured run reports
- Phase 07 tests

## Operational checks
A healthy run requires market data, execution availability, balanced reconciliation, and drawdown below the configured limit. Any failed check produces explicit reasons and should block promotion to a more permissive operating mode.

## Event vocabulary
Recommended events: run_started, signal_generated, risk_rejected, order_submitted, order_filled, order_canceled, reconciliation, run_completed, health_failed.

## Reporting
Run reports separate mode (backtest, paper, testnet, future live), performance metrics, risk metrics, and status. This prevents historical research results from being confused with execution state.

## Next phase
Phase 08 will add explicit dry-run/testnet operating modes, deployment gates, and preflight checks before any capital can be exposed.
