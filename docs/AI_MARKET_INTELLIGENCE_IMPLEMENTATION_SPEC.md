# ZERQEN — AI MARKET INTELLIGENCE + SAFE MODE IMPLEMENTATION SPEC

Date: 2026-09-29

## Objective

Upgrade Zerqen from a simple AI BUY/SELL gate into:

MARKET DATA -> MULTI-TIMEFRAME INDICATORS -> DERIVATIVES/OPTIONS CONTEXT -> DETERMINISTIC RISK GATE -> STRUCTURED MARKET INTELLIGENCE REPORT -> FREE-ONLY AI SYNTHESIS -> SAFE-MODE STATE MACHINE -> PAPER EXECUTION.

Real trading remains locked.

## Architecture

1. Deterministic engines calculate facts; AI synthesizes them.
2. One normalized MarketIntelligenceReport is supplied to AI rather than separate indicator prompts.
3. Hard risk gates always execute before AI and AI cannot override them.
4. AI may approve/reject/explain only an already risk-eligible setup.
5. Missing market data is explicit; it is never silently treated as zero.
6. Free-only enforcement remains absolute: paid/non-zero-price models are never called.
7. AI analysis is cached by symbol/timeframe/report hash and should not run every cycle.
8. Demo/paper can enter safe mode when AI is unavailable or quota/rate-limited. Real trading must require AI and remains locked.

## Market Intelligence Report

The normalized report should contain:

- symbol, exchange, timestamp, data quality and source status
- spot price and liquidity context
- 1h, 4h and 1d OHLCV-derived state
- EMA 9/21/50/200
- RSI
- MACD and histogram
- ATR and ATR percentage
- ADX/trend strength
- Bollinger Bands and bandwidth
- momentum
- volume ratio
- support/resistance
- market structure and swing direction
- breakout/breakdown state
- candle/price-action context
- volatility and abnormal-bar gates
- current positions, equity, drawdown, daily P&L and exposure
- adaptive stop, target and risk/reward
- candidate setups with entry conditions and invalidation
- futures funding, mark/index basis and open-interest context where public data is available
- futures delivery/expiry context where public data is available
- options expiry, IV/OI/crowding context where public data is available
- explicit data-quality warnings

## AI contract

AI receives exactly one structured report and must return JSON containing:

decision: BUY | SELL | HOLD
selected_setup
confidence
evidence[]
risk_flags[]
market_regime
derivatives_assessment
options_assessment
entry
stop
target
invalidation
why_not
data_quality

AI is advisory synthesis. It must not invent missing values or bypass deterministic gates.

## Safe mode

Environment:

ZERQEN_AI_MODE=auto
ZERQEN_AI_SAFE_MODE=true
ZERQEN_AI_SAFE_RETRY_SECONDS=1800
ZERQEN_AI_MIN_CONFIDENCE=0.60
ZERQEN_REAL_AI_REQUIRED=true

Safe-mode rules:

- AI quota/rate-limit/network/provider failure may enter SAFE_MODE for paper/demo.
- SAFE_MODE uses deterministic strategy/risk logic and records the degradation.
- Paid-model detection, non-zero usage cost, invalid data, volatility rejection, stop-distance rejection, minimum-RR rejection and portfolio breakers NEVER bypass into an order.
- Real trading remains locked and, when eventually enabled, AI must be required.
- Safe mode has an explicit cooldown and recovery check.

## State and audit

Persist AI runtime state:

ai_mode
ai_degraded_until
ai_last_ok_at
ai_last_error
ai_last_model
ai_last_confidence
ai_report_hash

Audit events:

AI_ANALYSIS_STARTED
AI_ANALYSIS_COMPLETED
AI_ANALYSIS_FAILED
AI_SAFE_MODE_ENTERED
AI_SAFE_MODE_EXITED
AI_QUOTA_DEGRADED
AI_MODEL_REJECTED_PAID
AI_DATA_INSUFFICIENT
MARKET_INTELLIGENCE_BUILT

## Hard safety hierarchy

1. invalid/incomplete market data
2. portfolio breakers
3. volatility/liquidity gates
4. stop-distance cap
5. minimum R:R
6. position/exposure limits
7. deterministic strategy eligibility
8. AI synthesis gate
9. simulated execution

The 8% stop requirement is a maximum stop-distance cap, not a guaranteed profit target. The existing 2R target and daily +8% portfolio hurdle remain separate controls.

## Backtest requirements

Support comparison of deterministic-only, AI-required, AI-optional and safe-mode behavior with:

return, final equity, max drawdown, profit factor, win rate, expectancy, Sharpe/Sortino where meaningful, turnover, fees, slippage, funding, trade count, AI calls, AI rejects and safe-mode trades.

## Definition of done

- One normalized market intelligence report is generated.
- AI receives the report rather than scattered indicators.
- Multi-timeframe technical context is included.
- Futures/options context is best-effort and explicitly quality-scored.
- AI calls are cached/throttled.
- Free-only enforcement remains hard.
- Quota/provider degradation cannot crash the paper worker.
- Safe mode is auditable and reversible.
- Missing data produces HOLD/rejection rather than fabricated values.
- Tests cover report construction, hashing/cache, safe-mode transitions, paid-model blocking, missing derivatives/options data and deterministic risk precedence.
- Ruff and pytest pass.
- Real trading remains locked.
