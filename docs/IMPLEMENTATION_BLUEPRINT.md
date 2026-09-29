# Zerqen — Implementation Blueprint

Date: 2026-09-29
Audited branch: `main`
Audit branch: `audit/production-hardening-2026-09-29`
Repository: `pawansatoshi/Zerqen`
Production: `https://zerqen.vercel.app/`
Audited production deployment commit: `74bbd066f18a344a2312664c775e37411ba4b787`

## Executive state

Zerqen is currently a research/control-plane codebase with substantial safety primitives already implemented. The repository is **not yet an end-to-end persistent trading system**.

Implemented foundations include deterministic OHLCV research, indicators, a baseline strategy, risk sizing, paper execution, explicit modes, kill switch, live authorization primitives, reconciliation primitives, data-quality validation, walk-forward/Monte Carlo/sensitivity modules, CCXT connectivity primitives, a Vercel dashboard, and encrypted credential storage.

The largest remaining gap is integration: durable state, authoritative position/P&L accounting, complete order lifecycle semantics, real reconciliation, persistent event/audit storage, production realtime workers, robust data-quality enforcement, and evidence-backed testnet/paper operation are not yet one coherent execution pipeline.

Live trading remains **not permitted** by this audit.

## A. Current architecture

Current repository layers:

`data -> indicators/strategies/regime/ensemble -> risk/portfolio primitives -> execution/paper adapter -> guards/kill switch -> reconciliation/audit primitives -> API/dashboard`

The intended production architecture should become:

`market feeds -> normalization -> data quality -> indicators/regime -> strategy registry -> signal -> portfolio risk -> order authorization -> execution worker -> exchange -> order/fill events -> authoritative position/accounting -> P&L -> reconciliation -> durable event store -> dashboard/alerts`

Vercel is currently the control plane/dashboard. It must not become the permanent high-frequency worker.

## B. Current implementation status

### Working / materially present

- Python package and CLI
- deterministic OHLCV loader
- EMA/RSI/ATR indicators
- baseline trend/momentum strategy
- mean-reversion/breakout strategy primitives
- regime classifier primitive
- ensemble scoring primitive
- fixed-fractional position sizing
- daily loss and drawdown primitives
- portfolio-risk budget primitive
- candle execution model
- paper exchange adapter
- order state machine
- client-order idempotency primitive
- CCXT adapter boundary
- explicit backtest/paper/testnet/live modes
- preflight and promotion gates
- kill switch
- live capital/order authorization guard
- reconciliation primitive
- order recovery journal primitive
- walk-forward, Monte Carlo and sensitivity modules
- audit/telemetry primitives
- Vercel API/dashboard
- encrypted exchange credential storage
- CI with Ruff + pytest across Python 3.10–3.13

### Present but incomplete for production

- backtester
- portfolio accounting
- execution lifecycle
- CCXT exchange integration
- reconciliation
- data-quality engine
- regime/ensemble semantics
- live guard
- API/database layer
- dashboard realtime behavior
- authentication
- observability
- research metadata/reproducibility

## C. Completed phases

Repository documentation marks Phases 01–10 as implemented. This is interpreted as **module-level implementation**, not production evidence.

Phase 01: research core.
Phase 02: research integrity primitives.
Phase 03: strategy/regime/ensemble primitives.
Phase 04: walk-forward/Monte Carlo/sensitivity primitives.
Phase 05: portfolio/risk/allocation primitives.
Phase 06: execution/order/reconciliation primitives.
Phase 07: observability/dashboard primitives.
Phase 08: paper/testnet/live mode boundaries and kill switch.
Phase 09: guarded-live control plane.
Phase 10: integration/data-quality/order-recovery hardening.

The documentation itself correctly states that Phase 10 does not prove profitability or live safety.

## D. Incomplete phases

The main incomplete area is the **integration and operational layer**, not the existence of individual modules.

Missing or insufficient:

1. authoritative durable order/fill/position state
2. complete order lifecycle including ACKNOWLEDGED, CANCEL_REQUESTED, EXPIRED, FAILED and UNKNOWN
3. authoritative fill deduplication
4. partial-fill position accounting
5. fee/funding/slippage attribution
6. persistent portfolio/equity snapshots
7. exchange reconciliation beyond quantity primitive
8. durable recovery across worker restart
9. persistent audit event chain
10. private WebSocket/user-stream synchronization
11. persistent trading worker
12. realtime multi-symbol market engine
13. order book/trade tape ingestion
14. market-data freshness/clock/gap validation in the live path
15. complete dashboard truth model
16. authenticated session model beyond shared token
17. CSRF/rate-limit/session expiry controls
18. research run metadata and artifact registry
19. long-duration paper/testnet evidence
20. production readiness gates backed by evidence

## E. Known bugs / correctness defects

### Critical

1. **Backtest exit semantics are inconsistent.**
   The code comments describe exit on next-candle open, but the implementation exits at the current candle close.

2. **Backtest end-of-test position is not explicitly closed or marked.**
   An open position can disappear from the result and its economic state is not represented.

3. **Backtest drawdown metric is terminal-equity based.**
   `max_drawdown_estimate` uses final equity versus peak rather than the maximum intraperiod equity drawdown.

4. **Backtest daily-loss enforcement is incomplete.**
   The check is applied before new entries, but daily loss should be derived from authoritative realized + unrealized portfolio state and enforced continuously.

5. **Intracandle stop/target ordering is ambiguous.**
   When both stop and target are touched in one candle, the implementation chooses stop first. This is a conservative convention, but it must be explicit, tested and shared by research/live simulation.

6. **Order lifecycle is incomplete.**
   Current states omit ACKNOWLEDGED, CANCEL_REQUESTED, EXPIRED, FAILED and UNKNOWN. Submission success is therefore too easily conflated with exchange state.

7. **CCXT submission is not safely recoverable on unknown network outcome.**
   A timeout can leave the exchange order unknown; there is no durable reconcile-before-retry path.

8. **CCXT fill fee accounting is incomplete.**
   The adapter creates a Fill with fee zero.

9. **CCXT cancellation lacks symbol context.**
   `cancel` cannot actually cancel on adapters requiring symbol.

10. **Order state is in-memory only.**
    Restart loses lifecycle state.

11. **Order journal is in-memory only.**
    It cannot provide production recovery.

### High

12. `validate_ohlcv` does not validate OHLC relationships, future timestamps, gaps, or explicit stale-data policy.

13. Regime labels do not match the full required canonical set and do not expose confidence/supporting factors.

14. Ensemble logic treats signals as booleans and cannot represent direction, disagreement, confidence, regime weighting or suppression robustly.

15. Position accounting does not exist as an authoritative fill-driven state machine.

16. Portfolio state has no positions, exposures, realized/unrealized P&L, fees or funding ledger.

17. No durable database schema exists for the required trading entities; credential storage creates only one credential table on demand.

18. API credential endpoints return raw exception type/message in 500 responses, which can leak implementation details.

19. Shared dashboard token is sent as a custom browser header and retained in sessionStorage; this is an interim admin gate, not a hardened session architecture.

20. `api/market.py` and the FastAPI market path duplicate market-data implementation.

21. The dashboard directly computes research signals in browser JavaScript. Those signals are not necessarily identical to the canonical Python strategy engine.

22. Browser realtime market feed currently covers only BTC ticker, not the requested BTC/ETH/SOL/BNB unified market engine.

23. Dashboard candle timeframes currently do not implement the requested 1m/5m/15m/1h/4h/1d set consistently.

24. Dashboard market response does not return complete OHLC fields from the server-side `api/market.py` handler.

25. No server-side persistent worker exists for exchange WebSockets, private streams, continuous execution or reconciliation.

26. The current API account path polls exchange state but is not the authoritative event-driven position/account ledger.

## F. Security risks

- credential vault architecture exists, but session/auth hardening is incomplete
- credentials must remain server-side and never be passed to browser persistence
- API exception bodies should not expose raw exception strings
- no demonstrated rate limiting
- no demonstrated CSRF/session protection
- no durable audit record for credential access/changes
- live/testnet environment separation is represented in code but not yet demonstrated operationally
- no verified exchange-specific withdrawal-permission enforcement
- no demonstrated secret scanning in CI
- no demonstrated Git-history secret scan
- no persistent worker isolation model
- live execution remains disabled and must stay disabled

## G. Trading correctness risks

- incomplete lifecycle state machine
- no authoritative fill ledger
- partial fills not propagated into position accounting
- no funding ledger
- no complete slippage/fee attribution
- no leverage/margin model
- no liquidation model
- no exchange precision/minimum-notional validation
- no portfolio correlation/concentration enforcement in execution path
- no continuous risk monitor
- no durable high-water mark/day-start state
- no restart-safe state restoration

## H. Data integrity risks

- no complete OHLC validation
- no gap detection
- no future timestamp rejection
- no source/timestamp/latency envelope carried through the entire pipeline
- duplicate market-feed events are not globally deduplicated
- stale feed is not a first-class state in the trading engine
- browser and server indicator implementations can diverge
- no canonical market-event store

## I. Execution risks

- exchange adapter is only partially normalized
- create-order unknown outcome is not reconciled before retry
- client order IDs are not durably persisted
- exchange order IDs are not consistently recorded
- partial fills are not authoritative
- cancellation is not unified
- exchange-specific order rules are not normalized
- no persistent execution worker

## J. Production deployment risks

Current Vercel production deployment is READY for commit `74bbd066...`, but Vercel READY is not equivalent to trading-production readiness.

Production architecture is currently suitable for a dashboard/control plane, not continuous exchange execution.

No production runtime errors were returned in the available grouped Vercel runtime-log query for the last 24 hours, but this is only an absence of recorded runtime log entries, not proof of correctness.

## K. Missing features

Priority missing features:

- authoritative domain state model
- persistent Postgres schema/migrations
- durable event store
- fill ledger
- position engine
- portfolio engine
- execution worker
- exchange user streams
- market-data normalization
- order book and trade tape
- realtime health/latency telemetry
- complete reconciliation
- restart recovery
- session authentication
- rate limiting
- audit trail
- research artifact metadata
- paper-run persistence
- testnet evidence collection
- production scorecard backed by automated evidence

## L. Recommended implementation order

1. Fix backtest semantics and add adversarial execution tests.
2. Create authoritative order/fill/position/P&L domain model.
3. Create durable Postgres schema and migrations.
4. Make order journal/event state durable.
5. Implement complete reconciliation and restart recovery.
6. Expand portfolio risk into the authoritative order gate.
7. Harden data-quality and freshness validation.
8. Unify research/paper/live execution primitives.
9. Harden CCXT/exchange normalization.
10. Build persistent worker architecture.
11. Implement realtime market/private streams with REST fallback.
12. Persist all decision/audit events.
13. Harden authentication/security.
14. Replace browser-only research signal calculations with canonical server outputs.
15. Upgrade dashboard to display only persisted/verified state.
16. Build paper-trading evidence collection.
17. Build testnet evidence collection.
18. Add production-readiness automation.
19. Run long-duration dry run.
20. Deploy only the control plane until all live gates have evidence.
21. Live remains OFF unless every gate passes and explicit manual approval exists.

## M. Test strategy

### Unit

- indicators
- strategies
- regime
- ensemble
- sizing
- portfolio risk
- order transitions
- fill accounting
- P&L
- fees/funding/slippage
- compounding
- data quality

### Integration

- exchange adapter
- order lifecycle
- reconciliation
- persistence
- worker restart
- API auth
- credential vault
- market fallback

### Adversarial

- duplicate order
- unknown submission result
- duplicate fill
- out-of-order fill
- partial fill
- stale feed
- future timestamp
- missing candle
- invalid OHLC
- exchange timeout
- HTTP 429/5xx
- DB outage
- worker restart
- environment mismatch
- kill switch
- risk breach
- reconciliation mismatch

### Property/invariants

- fills are idempotent
- position quantity equals signed fill sum
- realized P&L is deterministic
- duplicate events do not alter state
- rejected orders cannot create positions
- risk breach blocks new orders
- kill switch blocks new orders
- unknown order state blocks blind retry
- persisted and reconstructed state are equivalent

## N. Production-readiness gates

A gate is PASS only when code, tests and operational evidence all exist.

1. research integrity
2. data integrity
3. strategy correctness
4. risk controls
5. portfolio accounting
6. execution correctness
7. position accounting
8. reconciliation
9. exchange connectivity
10. security
11. database durability
12. realtime worker
13. observability
14. dashboard truthfulness
15. paper trading evidence
16. testnet evidence
17. manual live approval
18. deployment verification

No gate should be inferred from documentation alone.

## O. Rollback strategy

- deploy immutable Vercel builds
- keep previous production deployment as rollback candidate
- never promote a deployment with failing health/configuration gates
- disable execution before rollback if a worker is active
- reconcile exchange state after any execution-service rollback
- restore durable event/position state from Postgres
- never replay order submission blindly after rollback
- investigate UNKNOWN orders before resuming

## P. Recovery strategy

For any critical failure:

`detect -> persist event -> stop new orders if safety is uncertain -> reconcile exchange -> rebuild authoritative state -> validate risk -> resume only if gates pass`

For unknown order submission:

`persist UNKNOWN -> query exchange by client/exchange order ID -> reconcile -> transition -> account fills -> resume`

For worker restart:

`load durable state -> replay events -> reconcile exchange -> compare -> mark mismatch -> keep execution halted until balanced`

## Q. Realtime architecture

`Exchange WS/REST -> Normalizer -> Data Quality -> Event Bus -> Market State -> Indicators -> Regime -> Strategies -> Signal -> Risk -> Portfolio -> Execution -> Exchange`

Public dashboard data may use browser WebSocket for display only. Trading decisions must come from the canonical worker market state.

Private account streams remain server-side.

## R. Exchange architecture

Use a stable adapter contract covering:

- connect/authenticate
- ticker
- OHLCV
- order book
- trades
- balances
- positions
- open orders
- historical orders
- trades/fills
- create order
- cancel order
- fetch order
- user stream

Normalize exchange-specific status, precision, fees, timestamps and error classes into Zerqen domain types.

## S. Database architecture

Use Postgres with migrations.

Core tables:

- users
- exchange_connections
- encrypted_credentials
- accounts
- balances
- market_snapshots
- candles
- signals
- orders
- order_events
- fills
- positions
- position_events
- portfolio_snapshots
- equity_snapshots
- risk_events
- strategy_runs
- strategy_versions
- system_events
- audit_events
- notifications

All critical records use UTC timestamps and immutable event identifiers.

## T. Final end-to-end event flow

`MARKET EVENT`
-> source normalization
-> timestamp/quality validation
-> market state
-> indicators
-> regime
-> strategy signals
-> ensemble/suppression
-> signal persistence
-> portfolio risk
-> order authorization
-> client order ID
-> durable order CREATED
-> RISK_CHECK
-> APPROVED
-> SUBMITTED
-> exchange acknowledgement
-> ACKNOWLEDGED
-> fills
-> PARTIALLY_FILLED/FILLED
-> position event
-> realized/unrealized P&L
-> fees/funding/slippage
-> portfolio snapshot
-> reconciliation
-> audit event
-> notification
-> dashboard

At every failure boundary the system must either recover deterministically or enter a visible safe state.

## Current conclusion

Zerqen has a meaningful research/control-plane foundation, but the repository does not yet demonstrate an end-to-end production trading system. The next engineering work should focus on correctness and durable integration rather than adding more dashboard features or optimizing return targets.

Live trading status: **OFF / NOT PERMITTED**.
