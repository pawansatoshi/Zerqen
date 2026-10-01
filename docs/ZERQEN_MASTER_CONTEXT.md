# ZERQEN — MASTER CONTEXT / LIVING HANDOFF

**Last updated:** 2026-10-01  
**Repository:** `pawansatoshi/Zerqen`  
**Default branch:** `main`  
**Latest known main commit:** `d5a8a28f314f883201c944ba42c9e2e1f04b6ef1`

> This file is the primary fresh-agent handoff. It must evolve with the project. Read it before making changes.

---

## Architecture reference

The consolidated system architecture is maintained in `docs/ZERQEN_ARCHITECTURE.md`. It covers the control plane, persistent Voroa worker, Spot/Futures isolation, autonomous decision pipeline, AI/risk hierarchy, compounding, paper/testnet/live boundaries, ledger, reconciliation, market data, dashboard, worker lifecycle, failure handling, observability, testing, and the distinction between current implementation and target production architecture.

Any material architecture change must update both this architecture document and this master context.

## 1. Product mission

ZERQEN is an autonomous quantitative crypto **paper-trading and research system** designed to continuously scan markets, perform structured AI analysis, apply deterministic risk controls, simulate trades, maintain durable accounting, and compound from actual equity.

The intended user experience is deliberately simple:

**User starts an engine once → ZERQEN/Voroa continues working autonomously → user observes truthful status/ledger/chart → user stops when desired.**

The browser is a control/observability surface, not the worker runtime.

### Critical framing

The project has an **8% daily net-return research/compounding objective**. It is NOT a guaranteed return, prediction, or trade quota.

ZERQEN must never force a trade because the daily target has not been reached.

---

## 2. Non-negotiable product invariants

### 2.1 Spot and Futures are independent

Spot and Futures must have separate:

- Start/Stop controls
- enabled/stop-requested state
- equity
- daily baseline
- daily target
- P/L
- risk state
- positions
- compounding history
- trade ledger
- AI/decision state where applicable
- safety breakers

Starting Spot must never start Futures. Starting Futures must never start Spot.

### 2.2 Start/Stop behavior

**Start:**

- initializes the relevant paper account if needed;
- enables only the selected market engine;
- persistent worker detects the enabled state;
- worker continues scanning/decision-making independently of browser presence.

**Stop:**

- prevents new entries;
- does not force-close existing positions;
- existing positions remain risk-managed until flat unless a future explicit product decision changes this.

### 2.3 8% compounding

Daily target is calculated from the engine's actual daily baseline/equity.

Example:

- previous realized/effective equity = $1,034
- next daily target = $1,116.72
- target = baseline × 1.08

If the engine ends at $990, the next day's baseline is $990. The system must not pretend the previous target was achieved.

The target is a **hurdle/research objective**, not an instruction to increase risk.

When the daily target is reached:

- lock new entries for that engine/day;
- continue managing existing positions;
- next day starts from the actual resulting equity.

### 2.4 Risk authority

Risk is the final execution authority.

AI can recommend APPROVE/HOLD/REJECT, but cannot override:

- per-trade risk;
- daily loss breaker;
- maximum drawdown;
- exposure/margin/leverage limits;
- position constraints;
- target-hit entry lock;
- stop-requested state;
- other deterministic safety gates.

Known Spot baseline:

- 0.5% risk/trade
- 3% daily loss breaker
- 20% max drawdown

Known Futures baseline:

- 0.5% risk/trade
- 3% daily loss breaker
- 20% max drawdown
- 1x–5x leverage constraint

Futures leverage is an exposure/margin constraint, not a mechanism for forcing 8%.

Position sizing should be risk-based:

**position size ≈ equity × allowed risk ÷ stop distance**, subject to leverage, margin, exposure, liquidity, and liquidation constraints.

---

## 3. Autonomous intelligence pipeline

The intended decision pipeline is:

**Market data → deterministic Top-50 scan → shortlist → structured AI deep analysis → deterministic risk gate → paper execution → ledger/state → dashboard**

### Market scan

- Scan a deterministic Top-50 universe.
- Rank/shortlist candidates using deterministic market features before expensive AI review.
- Do not call the AI model for all 50 symbols every minute.
- Use AI cooldown when the setup has not materially changed.

### AI review

AI review should be structured, auditable, and machine-readable.

Expected fields include:

- decision: APPROVE / HOLD / REJECT
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

AI is a decision component, not the final risk authority.

### Current known AI safety behavior

The current autonomous path has a daily AI review safety cap of **40**. When reached, the cycle returns a no-trade state such as:

`reason: "AI daily safety cap reached"`

and records an `AI_DAILY_CAP` review event.

Important improvement identified on 2026-10-01:

> Once the daily AI cap is already reached, the worker should avoid repeatedly performing expensive Top-50/AI work merely to rediscover the same cap state. Existing positions still need management. This is a hardening/optimization item, not yet confirmed implemented.

---

## 4. Paper trading boundaries

Current project work is **paper/demo execution**.

- Live trading is disabled by default.
- Testnet connectivity is not required for the paper engine.
- Live read-only credential validation and Testnet/Demo credential validation are separate exchange environments.
- A Live key working does not prove that the same key is valid for Binance Testnet/Demo.
- Never submit live orders as part of normal paper-engine testing.

---

## 5. Worker architecture

### Dashboard

The Vercel dashboard is the user-facing control and observability layer.

It must show truthful:

- engine status
- stage
- worker heartbeat
- activity
- symbol
- positions
- P/L/equity
- charts
- ledger
- errors/blockers

### Control plane

Relevant current routes/modules include:

- `api/autonomous_control.py`
- `api/futures_autonomous.py`
- `api/_paper.py`
- `api/futures_paper.py`
- `api/ledger.py`
- `api/futures_ledger.py`
- `api/futures_chart.py`
- `api/index.py`

### Persistent worker

Current worker implementation:

- `zerqen/demo_worker.py`

The worker uses:

- `ZERQEN_API_BASE_URL`
- `ZERQEN_DASHBOARD_TOKEN`
- persistent loop
- approximately 60-second cycle interval by default

It is intended to run independently of the browser.

Current Voroa diagnostics have shown:

- worker auto-start succeeds;
- worker heartbeat succeeds;
- `mobile_independent=true`;
- `live_trading=false`.

However, diagnostic logs have also shown repeated:

`all autonomous engines disabled`

This means the worker was alive but had no engine enabled at those moments; it is not evidence that the worker itself was dead.

---

## 6. Market data / Start-button hardening history

A significant Start-button failure was traced to Spot paper status fetching remote public market data even when there were no open positions.

That caused the Start flow to appear frozen when a public market-data request was slow.

### Fix

PR #31 / merged main commit:

`d5a8a28f314f883201c944ba42c9e2e1f04b6ef1`

changed Spot paper status behavior so remote mark-price fetching is skipped when there are no open positions. Existing open positions can still receive marks.

The dashboard chart has its own market-data endpoint.

### Deployment

As of the 2026-10-01 verification:

- PR #31 is merged.
- Vercel deployment for the merged commit was shown as **Live** in the Voroa deployment screen.

Do not claim the complete runtime Start flow is proven merely from deployment status. It still needs an end-to-end user test showing:

**button → API start → enabled state → worker observes engine → cycle/stage update.**

---

## 7. Current dashboard Start flow

Current frontend intent:

`startMarketAutonomous("spot")`

does approximately:

1. authenticate dashboard access;
2. GET `/api/paper`;
3. initialize Spot paper account if needed;
4. POST `/api/autonomous` with `action=start, market=spot`;
5. refresh autonomous status.

Futures follows the equivalent `/api/futures-paper` → `/api/futures-autonomous` path.

The Start button must never silently hang. Future hardening should add explicit request timeouts and visible error states where appropriate.

---

## 8. Charts

Futures chart requirements:

- 1m, 3m, 5m, 15m, 30m
- 1h, 2h, 4h, 6h, 8h, 12h
- 1d, 3d, 1w, 1M
- candlesticks
- zoom/pan
- volume
- indicators
- signals
- entry/exit/profit markers
- stop/target/liquidation lines

The chart must not be the source of truth for account state; durable backend state/ledger is authoritative.

---

## 9. Ledger and accounting

There are separate Spot and Futures paper ledgers.

The durable ledger should support auditable:

- decisions
- orders
- fills
- positions
- realized P&L
- unrealized P&L
- fees
- equity snapshots
- daily compounding
- audit events

### Compounding authority

Compounding is based on actual/realized equity semantics defined by the engine. Unrealized P&L must not silently inflate the compounding base.

The dashboard should expose enough information to reconcile:

**starting equity → trades/fills → fees/P&L → ending equity → next baseline/target.**

---

## 10. UX contract

The user should not need to operate the system continuously.

Desired interaction:

**Start once.**

Then ZERQEN should:

- research;
- scan;
- wait for the right setup;
- perform AI analysis;
- apply risk;
- execute paper trades when justified;
- manage open positions;
- record every meaningful decision;
- compound from actual equity;
- continue until the user stops the engine.

No forced trade exists merely to satisfy the 8% objective.

The dashboard is primarily for:

- starting/stopping;
- observing;
- auditing;
- investigating;
- reviewing performance.

---

## 11. Known issues / hardening queue

### A. AI-cap short-circuit — OPEN

Current logs show repeated full market scans followed by:

`AI daily safety cap reached`

Once the cap is reached, the worker should short-circuit expensive AI/scan work while continuing required position management and health checks.

### B. Start-flow end-to-end verification — OPEN

PR #31 fixed the identified Spot market-feed blocking path and is deployed.

Still required:

- Start Spot from the actual dashboard;
- verify enabled state;
- verify worker consumes the state;
- verify stage/heartbeat/cycle updates;
- verify Stop behavior;
- separately verify Futures.

### C. Frontend timeout/error visibility — OPEN

A slow API request should never look like a dead button.

Add bounded request timeouts and explicit UI error states for Start/Stop/status calls.

### D. Worker state truthfulness — OPEN

`process_alive` can be null in diagnostics. The system should distinguish:

- worker configured;
- worker heartbeat observed;
- last cycle completed;
- process liveness proven.

Do not use a null/unknown liveness field as proof of failure or success.

### E. Long-duration evidence — OPEN

Paper trading needs sustained evidence across many cycles before any consideration of live execution.

---

## 12. Important historical fixes

- Fixed missing `async` on `loadMarket()`.
- Fixed accidental `async async function loadMarket()`.
- Fixed missing `async` on `saveDashboardToken()` where `await loadPaper()` was used.
- Fixed remaining dashboard JavaScript parse issue in PR #30.
- Fixed Spot Start blocking on remote market feed in PR #31.

These fixes are historical context. Do not reintroduce the same classes of syntax/runtime errors.

---

## 13. Development workflow for every future task

### Before coding

1. Read this file.
2. Inspect current code, not only old docs.
3. Identify which invariant(s) the change touches.
4. Identify whether Spot/Futures state must remain isolated.
5. Identify tests and runtime evidence needed.

### During coding

- Make the smallest coherent change.
- Preserve safety gates.
- Avoid hidden browser-only dependencies for autonomous work.
- Keep paper/live boundaries explicit.
- Keep durable state authoritative.

### After coding

1. Run relevant tests/checks.
2. Inspect the actual diff.
3. Update this master context.
4. Record the change and rationale.
5. Update known issues/next actions.
6. Commit to GitHub.
7. If Vercel deployment is relevant, verify deployment status.
8. Do not report unverified runtime behavior as proven.

---

## 14. Current next actions

1. End-to-end test Spot Start after PR #31 deployment.
2. End-to-end test Futures Start independently.
3. Verify worker state changes from disabled → enabled after Start.
4. Verify stage/cycle/heartbeat updates in the dashboard.
5. Verify Stop prevents new entries while preserving management of open positions.
6. Implement AI-cap short-circuit so the worker does not repeatedly rescan/review after the daily cap is reached.
7. Add explicit frontend API timeouts/error visibility.
8. Continue strengthening durable ledger reconciliation and long-duration paper evidence.

---

## 15. Fresh-agent instruction

If you are a new agent joining this repository:

**Do not ask the user to explain ZERQEN from scratch.**

Start by reading:

- `AGENTS.md`
- `docs/ZERQEN_MASTER_CONTEXT.md`
- relevant files under `docs/`
- the current implementation and tests

Then state the exact current task, inspect the relevant code path, make the change, verify it, and update this master context before handing back.

If a new user instruction conflicts with this document, treat the user's latest explicit requirement as a potential product change: implement it only after identifying the affected invariants and update this document to record the new decision.
