# ZERQEN — SYSTEM ARCHITECTURE

**Last updated:** 2026-10-01  
**Repository:** `pawansatoshi/Zerqen`  
**Default branch:** `main`

> This document is the consolidated architecture reference for the current ZERQEN autonomous paper-trading system. It distinguishes **implemented/current behavior** from **target production architecture** so future agents do not confuse design intent with verified implementation.

---

## 1. Architecture authority

For a fresh agent, read in this order:

1. `AGENTS.md` — agent operating rules.
2. `docs/ZERQEN_MASTER_CONTEXT.md` — product requirements, invariants, current state, issues and next actions.
3. This file — consolidated system architecture.
4. Relevant implementation files and migrations.
5. Older phase/readiness/blueprint documents for historical context.

**Current executable behavior is authoritative for what is implemented.**  
**This architecture document is authoritative for the intended system structure and explicitly labels incomplete target components.**

---

# 2. Product architecture

ZERQEN has two closely related planes:

### Control / observability plane

```
User
  ↓
ZERQEN Dashboard
  ↓
Vercel API / Control Plane
  ↓
Postgres / durable paper state + ledgers
```

### Autonomous execution plane

```
Persistent Voroa / ZERQEN Worker
  ↓
Autonomous engine state
  ↓
Spot cycle / Futures cycle
  ↓
Market data
  ↓
Deterministic filtering
  ↓
AI research / decision
  ↓
Risk authority
  ↓
Paper execution
  ↓
Positions / P&L / ledger
  ↓
Dashboard state
```

The browser is **not** the autonomous runtime.

The persistent worker must continue operating when the user's browser or phone is closed.

---

# 3. Current deployment architecture

## Dashboard / API

The repository contains a Vercel-ready dashboard and FastAPI control/API layer.

Important current modules include:

- `api/index.py`
- `api/autonomous_control.py`
- `api/futures_autonomous.py`
- `api/_paper.py`
- `api/futures_paper.py`
- `api/ledger.py`
- `api/futures_ledger.py`
- `api/futures_chart.py`

## Persistent worker

Current worker entry point:

`python -m zerqen.demo_worker`

Implementation:

`zerqen/demo_worker.py`

The worker communicates with the API/control plane and operates independently from the browser.

Expected infrastructure variables include:

- `ZERQEN_API_BASE_URL`
- `ZERQEN_DASHBOARD_TOKEN`
- `OPENROUTER_API_KEY` where AI review is enabled

Secrets must never be committed.

## Voroa deployment

The current Voroa configuration uses:

- repository: `pawansatoshi/Zerqen`
- branch: `main`
- start command: `python -m zerqen.demo_worker`
- automatic deploy on pushes to `main`
- worker-focused build filters

The worker deployment and Vercel application are related but are separate runtime responsibilities.

---

# 4. Spot/Futures isolation

Spot and Futures are separate autonomous engines.

```
                 ZERQEN
                   │
          ┌────────┴────────┐
          ↓                 ↓
        SPOT             FUTURES
          │                 │
   own engine state    own engine state
   own equity          own equity
   own baseline        own baseline
   own target          own target
   own risk            own risk
   own positions       own positions
   own ledger          own ledger
   own compounding     own compounding
```

Starting Spot must never start Futures.

Starting Futures must never start Spot.

Stopping one engine must not stop the other.

---

# 5. User interaction architecture

The intended UX is:

```
USER
  │
  │ press START
  ↓
Dashboard
  │
  ↓
API control endpoint
  │
  ↓
engine.enabled = true
  │
  ↓
persistent worker observes state
  │
  ↓
autonomous cycle continues
  │
  └──────────────→ user only observes / stops
```

The user should not need to repeatedly trigger scans or trades.

The dashboard is a **control and observability surface**, not a manual trading terminal.

---

# 6. Start lifecycle

## Spot

Current frontend intent:

```
START SPOT
  ↓
dashboard authentication
  ↓
GET /api/paper
  ↓
initialize paper account if necessary
  ↓
POST /api/autonomous
  { action: start, market: spot }
  ↓
Spot engine enabled
  ↓
persistent worker observes state
  ↓
Spot cycle
```

## Futures

```
START FUTURES
  ↓
dashboard authentication
  ↓
GET /api/futures-paper
  ↓
initialize Futures paper account if necessary
  ↓
Futures autonomous start/control path
  ↓
Futures engine enabled
  ↓
persistent worker observes state
  ↓
Futures cycle
```

### Required future hardening

A Start request must have:

- bounded request timeout
- explicit HTTP error handling
- visible failure state
- no silent hanging
- truthful enabled/disabled state

---

# 7. Stop lifecycle

Stop is an **entry-control action**, not an automatic liquidation action.

```
STOP
  ↓
stop_requested = true
  ↓
NO NEW ENTRIES
  ↓
existing positions remain managed
  ↓
positions close normally according to management rules
  ↓
engine becomes flat / stopped
```

Do not force-close positions merely because the user pressed Stop unless a future explicit product decision changes this behavior.

---

# 8. Autonomous market pipeline

The intended canonical pipeline is:

```
Market data
    ↓
Data quality / freshness checks
    ↓
Deterministic Top-50 universe
    ↓
Candidate ranking / shortlist
    ↓
AI deep analysis
    ↓
Structured decision
    ↓
Deterministic risk gate
    ↓
Paper execution
    ↓
Position management
    ↓
Ledger / P&L / equity
    ↓
Compounding state
    ↓
Dashboard
```

The AI must not be called unnecessarily for all 50 markets on every cycle.

AI review should be reserved for shortlisted setups and materially changed setups.

---

# 9. AI decision architecture

AI is a **research/decision component**, not the final authority.

Expected structured decision:

```
APPROVE
HOLD
REJECT
```

Supporting fields should include:

- regime
- multi-timeframe structure
- momentum
- volatility
- liquidity
- support/resistance
- entry quality
- stop quality
- target quality
- R:R
- invalidation
- catalysts/risks
- confidence
- reason

Decision flow:

```
Market candidate
    ↓
AI analysis
    ↓
structured recommendation
    ↓
RISK ENGINE
    ↓
allowed / rejected
```

AI cannot override deterministic risk controls.

---

# 10. Risk architecture

Risk is above target-return logic.

```
AI says APPROVE
       ↓
Risk checks
       ↓
  ┌────┴────┐
PASS       FAIL
  ↓          ↓
paper       reject
entry
```

Known baseline controls:

- 0.5% risk/trade
- 3% daily loss breaker
- 20% maximum drawdown
- Futures leverage constrained to 1x–5x

Other portfolio limits documented in the historical trading blueprint must only be treated as active runtime controls when verified in the current implementation.

Examples of target production controls include:

- aggregate open risk
- maximum concurrent positions
- concentration
- exposure
- strategy allocation
- stale data
- abnormal volatility
- exchange health
- reconciliation state
- kill switch

A future agent must verify implementation before claiming any of these are active.

---

# 11. 8% compounding architecture

The 8% number is a **research/compounding hurdle**, never a trade quota.

```
actual daily baseline
       × 1.08
       ↓
daily research target
```

Example:

```
Day N ending equity = $1,034
Day N+1 baseline    = $1,034
Day N+1 target      = $1,116.72
```

If equity falls to $990:

```
next baseline = $990
next target   = $1,069.20
```

The engine must compound losses as well as gains.

### Target-hit behavior

When the daily target is reached:

- lock new entries for that engine/day;
- continue managing existing positions;
- next day's baseline uses actual resulting equity.

Never force a trade because the target is still unmet.

---

# 12. Capital and P&L authority

The authoritative economic path is:

```
starting equity
    ↓
orders
    ↓
fills
    ↓
fees / funding / slippage
    ↓
realized P&L
    ↓
ending equity
    ↓
next compounding baseline
```

Unrealized P&L may be displayed and used for risk monitoring, but must not silently become the compounding base.

The long-term production architecture requires fill-driven authoritative accounting.

---

# 13. Paper execution architecture

Current product work is paper/demo.

```
real public market data
       ↓
strategy / AI
       ↓
risk
       ↓
simulated order
       ↓
simulated fill
       ↓
paper position
       ↓
paper P&L
       ↓
paper ledger
```

Paper execution must remain explicitly labeled.

Paper mode does not require private exchange credentials for public market data.

---

# 14. Testnet and live boundaries

## Testnet

Testnet is a separate environment.

A Live credential working does **not** imply that the same credential is valid for Binance Testnet/Demo or another sandbox.

Testnet validation must be explicit and environment-specific.

## Live

Live trading remains disabled by default.

Before live execution could ever be enabled, the system requires evidence for:

- research correctness
- market-data integrity
- strategy validation
- risk
- portfolio accounting
- execution
- position accounting
- reconciliation
- exchange authentication
- security
- durable database state
- worker reliability
- observability
- truthful dashboard
- long-duration paper evidence
- testnet evidence
- explicit manual approval

---

# 15. Ledger architecture

Separate Spot and Futures ledgers are required.

The durable ledger should represent:

```
decision
  ↓
order
  ↓
order events
  ↓
fill
  ↓
position event
  ↓
position
  ↓
realized/unrealized P&L
  ↓
equity snapshot
  ↓
daily compounding
```

Required accounting concepts:

- decisions
- orders
- fills
- positions
- fees
- funding
- realized P&L
- unrealized P&L
- equity snapshots
- risk events
- audit events

Duplicate/out-of-order events must be handled deterministically.

---

# 16. Order lifecycle target

The production lifecycle documented in the trading blueprint is:

```
CREATED
  ↓
RISK_CHECK
  ↓
APPROVED
  ↓
SUBMITTED
  ↓
ACKNOWLEDGED
  ↓
PARTIALLY_FILLED
  ↓
FILLED
```

Failure/cancellation states:

```
REJECTED
CANCEL_REQUESTED
CANCELLED
EXPIRED
FAILED
UNKNOWN
```

An unknown submission outcome must never trigger blind resubmission.

It must enter UNKNOWN and be reconciled first.

This lifecycle is a target production contract; verify which states are currently implemented before describing it as complete.

---

# 17. Position architecture

Positions should be derived from authoritative fills.

Conceptually:

```
valid signed fills
      ↓
position quantity
      ↓
average / entry state
      ↓
mark
      ↓
unrealized P&L
      ↓
closing fills
      ↓
realized P&L
```

Rejected orders must never create positions.

Partial fills must update position state incrementally.

Duplicate fills must be idempotent.

---

# 18. Reconciliation architecture

Target production reconciliation:

```
internal durable state
        ↕
exchange state
        ↓
balances
positions
open orders
fills
fees
        ↓
MATCH?
 ┌──────┴──────┐
YES            NO
 ↓              ↓
continue       persist mismatch
                ↓
             halt new orders
                ↓
             reconcile
                ↓
             rebuild/validate
                ↓
             resume
```

The system must never silently overwrite a mismatch.

For the current paper engine, durable internal state is the relevant authority; exchange reconciliation becomes critical when testnet/live execution is enabled.

---

# 19. Market-data architecture

Target production:

```
Exchange WebSocket
       ↓
normalization
       ↓
quality/freshness gate
       ↓
canonical market state
       ↓
strategy / AI / chart
```

REST is a fallback/recovery path where appropriate.

Data-quality checks include:

- missing candles
- duplicates
- timestamp ordering
- future timestamps
- interval gaps
- invalid OHLC relationships
- stale ticks
- abnormal gaps
- incomplete order books
- exchange outage
- clock/latency envelope

Invalid market data must block new execution rather than silently producing a trade.

---

# 20. Dashboard architecture

The dashboard should expose truthful state:

### Engine

- Spot status
- Futures status
- stage
- current activity
- worker heartbeat
- last cycle
- errors/blockers

### Portfolio

- equity
- available capital
- realized P&L
- unrealized P&L
- daily P&L
- drawdown
- target/baseline
- positions

### Trading

- symbol
- side
- entry
- mark
- quantity
- notional
- leverage
- stop
- target
- R
- fees
- funding
- strategy
- regime
- decision

### Audit

- decision
- order
- fill
- position
- risk event
- system event
- timestamps

The dashboard must never manufacture data to make the system appear healthy.

Unavailable/unverified state must be explicit.

---

# 21. Futures chart architecture

Futures chart requirements:

### Timeframes

```
1m  3m  5m  15m  30m
1h  2h  4h  6h   8h  12h
1d  3d  1w  1M
```

### Visualization

- candlesticks
- volume
- zoom/pan
- indicators
- signals
- entry markers
- exit markers
- profit/loss markers
- stop line
- target line
- liquidation line

Chart state is observability only. It must not become the authoritative source of account state.

---

# 22. Credential/security architecture

Current intended flow:

```
Browser
  ↓ HTTPS
Vercel API
  ↓
encrypted credential material
  ↓
Postgres / vault
  ↓
server-side decryption
  ↓
exchange adapter
```

Never place exchange secrets in:

- GitHub
- frontend source
- browser local storage
- dashboard responses
- logs

Infrastructure secrets currently include:

- `DATABASE_URL`
- `ZERQEN_DASHBOARD_TOKEN`
- `ZERQEN_VAULT_KEY`

The shared dashboard token is an interim control-plane mechanism, not the final session architecture.

---

# 23. Worker lifecycle

The persistent worker must be restart-safe.

Target lifecycle:

```
BOOT
 ↓
load durable state
 ↓
health/config check
 ↓
read enabled engines
 ↓
heartbeat
 ↓
run Spot cycle if enabled
 ↓
run Futures cycle if enabled
 ↓
persist cycle state
 ↓
sleep
 ↓
repeat
```

On restart:

```
load state
 ↓
recover/reconcile
 ↓
validate risk
 ↓
resume only when safe
```

A worker being alive does not mean an engine is enabled.

These states must remain distinct:

- worker configured
- worker started
- heartbeat observed
- engine enabled
- cycle running
- last cycle completed
- blocked
- stopped

---

# 24. Worker safety and AI-cap behavior

The current autonomous path has a daily AI review safety cap.

When the cap is reached, the engine must not keep approving new AI work simply because the 8% target is unmet.

Current hardening item:

```
AI daily cap reached
        ↓
skip expensive new AI/scan work
        ↓
continue required position management
        ↓
continue health/heartbeat
        ↓
wait for next eligible day/reset
```

The exact short-circuit implementation remains a known optimization task and must be verified after implementation.

---

# 25. Failure architecture

A failure should move through:

```
failure detected
     ↓
persist diagnostic event
     ↓
determine whether execution is safe
     ↓
if uncertain → block new entries
     ↓
recover / reconcile
     ↓
validate state
     ↓
resume only when safe
```

Examples:

- market feed timeout
- API timeout
- AI failure
- malformed AI response
- database outage
- worker restart
- stale market data
- risk breach
- reconciliation mismatch
- exchange disconnect

No failure path should silently appear as successful trading.

---

# 26. Observability architecture

Every autonomous cycle should be diagnosable through durable or queryable state.

At minimum:

```
worker heartbeat
engine state
stage
cycle start
cycle end
symbol/candidate
AI decision
risk decision
order/fill
position state
P&L/equity
error/block reason
```

The dashboard should display the latest verified state rather than infer worker health from browser activity.

---

# 27. Testing architecture

## Unit

- indicators
- strategies
- regime
- ensemble
- sizing
- risk
- compounding
- order state
- fills
- P&L
- data quality

## Integration

- API control
- paper engine
- ledger
- persistence
- worker restart
- market fallback
- credentials
- exchange adapters
- reconciliation

## Adversarial

- duplicate order
- duplicate fill
- partial fill
- unknown submission
- timeout
- 429/5xx
- stale feed
- future timestamp
- candle gaps
- invalid OHLC
- database outage
- worker restart
- testnet/live environment mismatch
- daily loss breach
- drawdown breach
- target-hit lock
- stop-requested state
- reconciliation mismatch
- AI malformed response
- AI daily cap

---

# 28. Current implementation vs target

## Implemented/currently present

- Vercel dashboard/API
- Spot paper engine
- Futures paper engine
- autonomous control state
- persistent worker entry point
- Spot/Futures separation
- paper ledgers
- Futures chart endpoint
- AI autonomous decision path
- risk primitives
- compounding state
- dashboard authentication gate
- encrypted credential path
- market fallback logic
- worker heartbeat/diagnostic path

## Still requiring verification or hardening

- complete end-to-end Start/Stop evidence
- long-duration worker evidence
- authoritative production-grade fill-driven ledger
- complete order lifecycle/recovery
- full reconciliation
- production multi-symbol private streams
- complete data-quality enforcement in autonomous runtime
- hardened session/auth architecture
- rate limiting / CSRF/session controls
- complete production observability
- live execution readiness

This distinction is mandatory: **module existence is not operational evidence.**

---

# 29. Historical documentation relationship

Existing documents such as:

- `docs/ARCHITECTURE.md`
- `docs/FINAL_TRADING_BLUEPRINT.md`
- `docs/IMPLEMENTATION_BLUEPRINT.md`
- `docs/RISK_MODEL.md`
- `docs/PRODUCTION_SETUP.md`
- `docs/VERCEL_DASHBOARD.md`
- `docs/PRODUCTION_READINESS.md`
- phase documents

remain useful historical/reference material.

They should not silently override the current master context or executable implementation.

When architecture changes materially:

1. update this document;
2. update `docs/ZERQEN_MASTER_CONTEXT.md`;
3. update the affected technical document;
4. record why the architecture changed;
5. verify code/tests/deployment evidence.

---

# 30. Architecture change protocol

Every future architectural change must record:

- date
- problem
- old behavior
- new behavior
- affected components
- invariants affected
- migration/backward compatibility requirements
- tests
- deployment impact
- verification status

No agent should make a structural change and leave the architecture documentation stale.

---

# 31. One-line canonical architecture

```
USER
→ ZERQEN DASHBOARD
→ VERCEL API / CONTROL PLANE
→ DURABLE STATE / LEDGER
↕
VOROA PERSISTENT WORKER
→ SPOT / FUTURES AUTONOMOUS ENGINE
→ MARKET DATA
→ DETERMINISTIC SCAN
→ AI DEEP ANALYSIS
→ RISK AUTHORITY
→ PAPER EXECUTION
→ POSITIONS / P&L / LEDGER
→ COMPOUNDING
→ TRUTHFUL DASHBOARD
```

The system's core principle is:

**Autonomous operation with deterministic safety authority, durable accounting, truthful observability, and no target-forced trading.**
