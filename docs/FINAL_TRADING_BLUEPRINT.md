# Zerqen — Final Trading Blueprint

Date: 2026-09-29
Repository: pawansatoshi/Zerqen
Production: https://zerqen.vercel.app/
Implementation branch: audit/production-hardening-2026-09-29

## 1. Executive Decision

Zerqen is ready to proceed into an engineering-controlled PAPER demo phase, not live trading.

The repository already contains the ten requested exchange identifiers and adapter registry:
Binance, OKX, Bybit, Bitget, MEXC, KuCoin, Gate, Delta Exchange India, CoinDCX, and WazirX.

The current exchange layer is primarily an adapter/control-plane boundary. It is not evidence that every exchange has passed authenticated testnet/live execution validation.

The immediate objective is:
real market data -> canonical strategy/risk pipeline -> simulated fills -> authoritative positions/P&L -> durable audit -> truthful dashboard.

The 8% daily figure is a research hurdle only. It must never influence order authorization.

Live execution remains OFF until every production gate has evidence.

## 2. Target Architecture

Browser
-> Vercel dashboard
-> Vercel API/control plane
-> Postgres + encrypted credential store

Trading worker
-> exchange WebSocket/REST
-> market normalizer
-> data-quality gate
-> indicators/regime
-> validated strategy registry
-> ensemble
-> portfolio/risk engine
-> execution service
-> exchange
-> order/fill events
-> authoritative position/P&L ledger
-> reconciliation
-> Postgres/event store
-> dashboard/notifications

Vercel is not the permanent high-frequency worker.

## 3. Capital-Preservation Model

Authoritative compounding:

realized net equity(t+1)
= realized net equity(t) + realized net P&L

Realized net P&L includes:
- trading P&L
- fees
- funding
- realized slippage
- other execution costs

Unrealized P&L never increases the compounding base.

Default limits:
- risk/trade: 0.5% equity
- aggregate open risk: 1.5%
- maximum positions: 3
- strategy allocation cap: 60%
- gross exposure/leverage baseline: 1.0x
- daily loss circuit breaker: 3%
- maximum drawdown: 20%
- stop: 1.5 ATR
- baseline target: 2R

No martingale, revenge trading, forced trades, leverage escalation, or target-chasing.

No valid signal means zero allocation and no trade.

## 4. Strategy Architecture

Canonical pipeline:

market data
-> quality
-> regime
-> strategy candidates
-> ensemble
-> allocation
-> position sizing
-> risk gate

Supported strategy families:
- trend
- momentum
- mean reversion
- breakout
- regime-aware selection

Regime state must expose:
label, confidence, supporting factors, timestamp.

Strategy selection requires validated evidence:
historical/OOS performance, drawdown, expectancy, profit factor, R expectancy, stability, sensitivity, regime behavior, walk-forward, Monte Carlo, and execution-cost sensitivity.

Training parameters must never be selected using final OOS data.

## 5. Exchange Architecture

Preserve:
- ADAPTERS
- create_exchange_adapter()

Required exchange IDs:
- binance
- okx
- bybit
- bitget
- mexc
- kucoin
- gate
- delta_india
- coindcx
- wazirx

Adapter contract:
connect/authenticate, ticker, OHLCV, order book, trades, balances, positions, open orders, historical orders, fills, create order, cancel order, fetch order, user stream.

Exchange-specific behavior stays inside adapters.

Every adapter must normalize:
status, timestamps, precision, minimum order size/notional, fees, funding, errors, sandbox/testnet behavior, rate limits.

An exchange card is not considered connected merely because it exists in the registry.

## 6. Credential Security

Flow:

browser
-> HTTPS
-> backend
-> AES-GCM encrypted credentials
-> Postgres/vault
-> server-side decryption only when required
-> exchange

Never expose credentials to browser responses, logs, frontend storage, GitHub, or public APIs.

Infrastructure secrets:
DATABASE_URL
ZERQEN_DASHBOARD_TOKEN
ZERQEN_VAULT_KEY

Exchange API credentials are stored as encrypted application data, not Vercel environment variables.

Prefer read-only keys for monitoring and trading-only permissions where supported. Withdrawals must be disabled.

The current shared dashboard token is an interim control-plane gate and must eventually be replaced with authenticated sessions, secure cookies, expiry, CSRF protection and rate limiting.

## 7. Exchange Connection UI

Each exchange gets a card containing:
- connection state
- required credential fields based on adapter metadata
- mode: PAPER / TESTNET / LIVE
- Test Connection
- Save Securely
- last successful check
- latency
- permission state

Secrets disappear after submission.

Connection testing is read-only:
authentication -> account read -> balance read -> order access -> position access.

No connection test may place an order.

Unsupported sandbox behavior must be shown as NOT SUPPORTED, never simulated as connected.

## 8. Paper Demo

The first user-facing demo must be PAPER.

Paper mode may use real public exchange market data without private credentials.

Flow:

real market data
-> quality gate
-> regime
-> strategies
-> ensemble
-> risk
-> simulated execution
-> fills
-> position ledger
-> realized/unrealized P&L
-> fees/slippage
-> equity
-> reconciliation
-> dashboard

Paper fills must be deterministic and explicitly labeled PAPER.

The paper engine must persist enough state to survive restart.

## 9. Testnet

After paper evidence:
- save encrypted credentials
- verify sandbox endpoint
- read balances
- read positions
- read open orders
- submit controlled test order only when explicitly authorized
- verify acknowledgement
- verify partial/full fill
- cancel
- reconcile
- restart worker
- reconcile again

Every testnet action is auditable.

## 10. Live Gate

Live remains disabled by default.

Required evidence before live:
research integrity
data integrity
strategy validation
risk controls
portfolio accounting
execution correctness
position accounting
reconciliation
exchange authentication
security
database durability
worker reliability
observability
dashboard truthfulness
paper evidence
testnet evidence
manual approval

Passing code tests alone is insufficient.

## 11. Order Lifecycle

Authoritative states:

CREATED
-> RISK_CHECK
-> APPROVED
-> SUBMITTED
-> ACKNOWLEDGED
-> PARTIALLY_FILLED
-> FILLED

Failure/cancellation states:
REJECTED
CANCEL_REQUESTED
CANCELLED
EXPIRED
FAILED
UNKNOWN

Every order stores:
client_order_id, exchange_order_id, exchange, symbol, side, type, quantity, price, status, timestamps, latency, retry count, reason.

Unknown submission outcome always enters UNKNOWN and is reconciled before retry.

Never blindly resubmit after a timeout.

## 12. Position and P&L Ledger

Fills are authoritative.

Position quantity = deterministic signed sum of valid fills.

Persist:
- fills
- fees
- funding
- slippage
- position events
- realized P&L
- unrealized P&L
- equity snapshots

Duplicate and out-of-order events must be handled deterministically.

Rejected orders cannot create positions.

## 13. Portfolio Risk

Risk checks execute before exchange submission.

Required checks:
- trade risk
- aggregate open risk
- daily realized/unrealized/combined loss
- drawdown
- gross/net exposure
- concentration
- strategy allocation
- correlation
- leverage/margin
- stale data
- abnormal volatility
- exchange health
- kill switch
- reconciliation state

Any failed material check blocks new execution.

## 14. Reconciliation

Continuously compare internal state against exchange state:

balances
positions
open orders
fills
fees

Mismatch:
1. persist event
2. halt new orders
3. reconcile
4. rebuild authoritative state if required
5. validate risk
6. resume only when balanced

Never silently overwrite state.

## 15. Kill Switch

Separate controls:
- HALT_NEW_ORDERS
- FLATTEN_POSITIONS

HALT_NEW_ORDERS is the default automatic safety action.

Triggers include:
- daily loss breach
- drawdown breach
- stale/corrupt market data
- exchange disconnect
- database failure
- reconciliation mismatch
- security failure
- leverage/margin failure

Kill-switch state is durable and survives worker restart.

## 16. Data Quality

Before strategy execution validate:
- missing candles
- duplicates
- timestamp order
- future timestamps
- expected interval gaps
- OHLC relationships
- stale ticks
- abnormal gaps
- incomplete order books
- exchange outage
- clock/latency envelope

Materially invalid data blocks strategy execution.

No silent data repair.

## 17. Realtime

Worker-side:
WebSocket primary
REST fallback

Display:
LIVE / STALE / DISCONNECTED

Required dashboard market set:
BTC, ETH, SOL, BNB.

Required streams where supported:
ticker, trades, order book, candles.

The browser is a display surface, not the authoritative trading engine.

## 18. Dashboard

Top-level truthful state:
- system status
- market status
- risk status
- portfolio equity
- available capital
- realized P&L
- unrealized P&L
- daily net P&L
- drawdown
- active positions
- engine health
- exchange connections
- research hurdle

The 8% research hurdle must always be labeled:
"Research hurdle — not a trading requirement."

No fake balances, P&L, prices, candles, order-book rows, trade tape, or health states.

Unavailable data renders:
— / NOT CONNECTED / NO VERIFIED DATA.

## 19. Position Detail

Show:
exchange, symbol, side, entry, mark, quantity, notional, leverage, stop, target, R, unrealized P&L, realized P&L, fees, funding, opened time, strategy, regime, signal score.

Timeline:
SIGNAL -> RISK APPROVED -> ORDER CREATED -> SUBMITTED -> ACKNOWLEDGED -> FILLED -> POSITION OPEN -> EXIT -> REALIZED.

## 20. Performance Analytics

Show daily/weekly/monthly/YTD/inception:
net return, equity, drawdown, volatility, downside deviation, win rate, average win/loss, profit factor, expectancy, R expectancy, holding time.

Sharpe/Sortino/Calmar appear only after sufficient observations.

No statistically meaningless manufactured metrics.

## 21. Database

Postgres migrations and durable schema:

users
exchange_connections
encrypted_credentials
accounts
balances
market_snapshots
candles
signals
orders
order_events
fills
positions
position_events
portfolio_snapshots
equity_snapshots
risk_events
strategy_runs
strategy_versions
system_events
audit_events
notifications

All critical timestamps UTC.

Audit events are append-only.

## 22. Worker Recovery

On startup:
load durable state
-> replay/reconstruct
-> reconcile exchange
-> compare
-> remain halted if mismatch
-> resume only after risk validation.

Critical failure:
detect -> persist -> halt if uncertain -> reconcile -> rebuild -> validate -> resume.

## 23. UI/UX Principles

Premium quantitative terminal:
- restrained Apple-like visual hierarchy
- strong typography
- subtle borders
- high information density
- responsive
- desktop-first
- mobile usable
- dark/light architecture where supported

Avoid casino aesthetics, excessive gradients, flashing effects, fake counters, meaningless badges and decorative charts.

## 24. Testing

Unit:
strategy, regime, ensemble, sizing, risk, order state, fills, P&L, compounding, data quality.

Integration:
exchange adapters, persistence, order lifecycle, reconciliation, worker restart, credential vault, API auth, market fallback.

Adversarial:
duplicate order/fill, unknown order, partial fill, stale feed, future timestamp, gaps, invalid OHLC, timeout, 429/5xx, DB outage, restart, environment mismatch, kill switch, risk breach, reconciliation mismatch.

Invariants:
- duplicate events are idempotent
- fill sum reconstructs position
- realized P&L is deterministic
- rejected orders create no positions
- risk breach blocks execution
- kill switch blocks execution
- UNKNOWN blocks blind retry
- reconstructed state equals persisted state

## 25. Implementation Order

Phase A — foundation:
1. authoritative domain state
2. Postgres migrations
3. durable event/order/fill/position ledger
4. portfolio/P&L accounting
5. complete reconciliation

Phase B — exchange:
6. adapter metadata/capabilities
7. read-only connection testing
8. credentials hardening
9. exchange precision/rate-limit/error normalization
10. testnet execution harness

Phase C — worker:
11. market normalizer
12. WebSocket/REST fallback
13. strategy/risk execution pipeline
14. persistent worker
15. restart recovery

Phase D — UI:
16. exchange connection center
17. portfolio/risk dashboard
18. realtime market terminal
19. order/position detail
20. performance analytics
21. engine monitor

Phase E — evidence:
22. paper runs
23. testnet runs
24. reconciliation/failure injection
25. security audit
26. production-readiness report

## 26. Immediate Demo Acceptance

The first demo is accepted only when all are true:

- PAPER mode is selectable
- real public market data is visible
- no exchange order is possible in PAPER
- strategy output is canonical server/worker output
- risk checks execute before simulated orders
- simulated fills create positions
- fees/slippage are recorded
- realized net P&L drives subsequent risk capital
- zero-signal periods remain flat
- 8% does not alter trade authorization
- kill switch blocks new paper orders
- restart does not lose paper state
- dashboard numbers come from authoritative state
- no secrets reach frontend/logs
- unavailable data is visibly unavailable

## 27. Final Safety Principle

Zerqen protects capital before seeking returns.

A missed trade is acceptable.
A zero-return day is acceptable.
A losing day within defined limits is acceptable.
A disabled strategy is acceptable.
A system refusing to trade because conditions are unsafe is correct behavior.

The system must never sacrifice capital-preservation controls to approach the 8% research hurdle.
