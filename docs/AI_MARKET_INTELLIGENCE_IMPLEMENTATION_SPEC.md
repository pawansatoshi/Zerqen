# ZERQEN — AI MARKET INTELLIGENCE + SAFE MODE IMPLEMENTATION SPEC
Date: 2026-09-29

## 1. Objective

Upgrade Zerqen from a simple AI BUY/SELL gate into:

MARKET DATA
→ MULTI-TIMEFRAME INDICATOR ENGINE
→ DERIVATIVES / FUTURES / OPTIONS CONTEXT
→ RISK ENGINE
→ STRUCTURED MARKET INTELLIGENCE REPORT
→ FREE-ONLY AI ANALYSIS
→ AI REQUIRED / AI OPTIONAL / SAFE MODE STATE MACHINE
→ PAPER EXECUTION

Real trading remains locked.

## 2. AI quota behavior

Environment:

ZERQEN_AI_MODE=auto
ZERQEN_AI_SAFE_MODE=true
ZERQEN_AI_SAFE_RETRY_SECONDS=1800
ZERQEN_AI_MIN_CONFIDENCE=0.60
ZERQEN_REAL_AI_REQUIRED=true

Modes:

AI_REQUIRED
- used for future real execution
- AI unavailable = reject new entry

AI_OPTIONAL
- paper/demo mode
- deterministic risk engine remains authoritative
- AI enriches/rejects a setup when available

SAFE_MODE
- entered automatically when OpenRouter free inference is unavailable because of quota/rate limit/provider exhaustion/network degradation
- do NOT repeatedly hammer OpenRouter
- deterministic strategy can continue only when every hard risk gate passes
- every safe-mode entry must be audited

Never enter SAFE_MODE for:
- paid-model detection
- non-zero inference cost
- malformed deterministic risk state
- invalid market data
- stop-distance violation
- daily loss breaker
- max drawdown breaker
- portfolio exposure violation
- volatility gate violation

Those remain hard rejects.

When AI recovers:
SAFE_MODE → AI_OPTIONAL
and record AI_SAFE_MODE_EXITED.

## 3. Database state

Add to zerqen_paper_state:

ai_mode TEXT NOT NULL DEFAULT 'auto'
ai_degraded_until TIMESTAMPTZ
ai_last_ok_at TIMESTAMPTZ
ai_last_error TEXT
ai_last_model TEXT
ai_last_confidence NUMERIC
ai_safe_mode_entries INTEGER NOT NULL DEFAULT 0

Also create migration:
db/migrations/003_ai_market_intelligence.sql

Use ALTER TABLE ... ADD COLUMN IF NOT EXISTS for safe upgrades.

## 4. Structured Market Intelligence Report

Create:

zerqen/market_intelligence.py

Function:

build_market_intelligence(
    symbol,
    timeframe,
    exchange_id,
    rows,
    account_context=None
)

The report must be deterministic and JSON serializable.

### A. Multi-timeframe

At minimum:

1h
4h
1d

For each:

- last price
- EMA 9
- EMA 21
- EMA 50
- EMA 200 when enough candles
- RSI 14
- ATR 14
- ATR %
- MACD
- MACD signal
- MACD histogram
- ADX 14
- Bollinger lower/middle/upper
- Bollinger position
- momentum 5/10/20 period
- volume ratio
- recent high/low
- support levels
- resistance levels
- trend direction
- trend strength
- volatility state

### B. Market structure

Return:

- higher_high / higher_low
- lower_high / lower_low
- swing high
- swing low
- nearest support
- nearest resistance
- distance to support %
- distance to resistance %
- breakout state
- breakdown state
- consolidation state

### C. Candle / price action

Return:

- current candle direction
- body %
- upper wick %
- lower wick %
- largest recent candle %
- abnormal candle flag
- gap flag where applicable

### D. Cross-timeframe agreement

Calculate:

bullish_timeframes
bearish_timeframes
neutral_timeframes
agreement_score 0..100

Examples:

1h bullish + 4h bullish + 1d bullish
= strong alignment

1h bullish + 4h bearish
= conflict

No AI should override a major timeframe conflict without explicitly reporting it.

## 5. Futures context

For Binance public data, collect when available:

- mark price
- index price
- premium / basis
- current funding rate
- next funding time
- open interest
- futures contract status
- delivery contracts
- delivery date
- days/hours until expiry
- perpetual vs delivery

Calculate:

funding_bias:
LONG_CROWDED
SHORT_CROWDED
NEUTRAL

basis_state:
PREMIUM
DISCOUNT
NEUTRAL

expiry_risk:
LOW
MEDIUM
HIGH

Do not treat funding as a directional signal by itself.

## 6. Options context

For supported underlyings, collect public options metadata:

- nearest expiry
- expiry timestamp
- remaining time
- available calls
- available puts
- strike distribution
- option open interest when endpoint supports it
- option mark price
- implied volatility when available
- bid IV
- ask IV
- put/call open-interest ratio where enough data exists

Calculate:

options_state:
- NO_OPTIONS_DATA
- NORMAL
- EXPIRY_NEAR
- HIGH_CONCENTRATION
- HIGH_IV

The report must clearly distinguish:
AVAILABLE DATA
vs
UNAVAILABLE DATA.

Never invent missing option statistics.

## 7. Trading setup engine

The backend should create candidate setups, not promise outcomes.

Supported setup labels:

LONG_TREND_CONTINUATION
SHORT_TREND_CONTINUATION
BREAKOUT_CONFIRMATION
BREAKDOWN_CONFIRMATION
MEAN_REVERSION
RANGE_TRADE
NO_TRADE

For each candidate:

- direction
- trigger
- entry zone
- structural stop
- maximum stop distance
- target 1
- target 2
- expected R
- invalidation
- required confirmations
- risk flags
- timeframe alignment
- setup quality inputs

Hard rules:

max stop distance <= 8%
ATR <= 5%
largest recent bar <= 8%
minimum R:R >= 2.0
risk per trade <= 0.5%
aggregate open risk <= configured cap
gross exposure <= configured cap
daily loss breaker
max drawdown breaker

8% is a maximum stop-distance cap, NOT an 8% guaranteed profit target.

The existing +8% daily figure remains a research hurdle / daily lock, not a forecast.

## 8. AI input contract

AI receives ONE report:

{
  "report_version": "1.0",
  "market": {...},
  "multi_timeframe": {...},
  "market_structure": {...},
  "price_action": {...},
  "derivatives": {...},
  "options": {...},
  "portfolio": {...},
  "risk": {...},
  "candidate_setups": [...],
  "hard_rejections": [...],
  "data_quality": {...}
}

AI does NOT receive permission to place orders.

AI output must be strict JSON:

{
  "decision": "BUY|SELL|HOLD",
  "selected_setup": "...",
  "confidence": 0.0,
  "market_regime": "...",
  "trend_assessment": "...",
  "timeframe_alignment": "...",
  "evidence": [
    "...",
    "..."
  ],
  "risk_flags": [],
  "derivatives_assessment": "...",
  "options_assessment": "...",
  "entry_condition": "...",
  "stop_condition": "...",
  "target_condition": "...",
  "invalidation": "...",
  "why_not": "...",
  "data_quality": "GOOD|DEGRADED|INSUFFICIENT"
}

AI must choose HOLD when evidence conflicts or required data is insufficient.

## 9. Best-use strategy for limited free AI quota

Do NOT call AI every market refresh.

Call AI only when:

- deterministic signal exists
- setup passes hard risk gates
- no duplicate position exists
- market structure changed materially
- a new scanner candidate crosses the action threshold
- an existing position reaches a decision point

Do NOT spend AI calls on:

- ordinary dashboard refresh
- every ticker update
- every 15-second UI poll
- already rejected high-volatility setups
- symbols failing liquidity
- daily target locked
- daily loss locked
- max drawdown locked

Cache AI analysis using:

symbol + timeframe + report_hash

Suggested cache TTL:
15–30 minutes unless material market change occurs.

This dramatically reduces OpenRouter quota consumption.

## 10. AI fallback behavior

OpenRouter currently provides free models and a free router, but the free tier is rate-limited. Never assume free inference is unlimited.

When free AI fails:

1. classify failure
2. record exact reason
3. enter SAFE_MODE only for transient quota/provider/network unavailability
4. wait until ai_degraded_until
5. do not repeatedly retry
6. resume AI automatically after cooldown
7. audit both transitions

Safe mode paper execution:

deterministic EMA/RSI/ATR/structure/risk engine remains authoritative.

AI cannot be replaced by a paid model.

## 11. Free-only model enforcement

Keep the existing FreeModelRegistry.

Before every AI request:

prompt price == 0
completion price == 0

If usage reports non-zero cost:
raise FreeOnlyViolation

Never silently switch to a paid model.

OpenRouter's openrouter/free router can be used only because it is itself zero-priced, but the system must still verify the request/model metadata and reported cost.

## 12. Dashboard

Add an AI Market Intelligence panel:

AI STATE
- ACTIVE
- SAFE MODE
- OFF
- ERROR

Market Regime
Trend Alignment
Volatility
RSI
MACD
ADX
ATR
Volume
Support
Resistance
Funding
Open Interest
Futures Expiry
Options Expiry
Options IV
Setup
Entry Condition
Stop
Target
R:R
Invalidation
AI Confidence
AI Model
AI Last Updated

Also show:

AI quota/degraded reason
next AI retry time
safe-mode entries
last successful AI call

## 13. Audit events

Add:

AI_ANALYSIS_STARTED
AI_ANALYSIS_COMPLETED
AI_ANALYSIS_FAILED
AI_SAFE_MODE_ENTERED
AI_SAFE_MODE_EXITED
AI_QUOTA_DEGRADED
AI_MODEL_REJECTED_PAID
AI_DATA_INSUFFICIENT
MARKET_INTELLIGENCE_BUILT

Store report hash and model ID so the decision is reproducible.

## 14. Tests

Add:

tests/test_market_intelligence.py

Test:

- multi-timeframe report shape
- EMA/RSI/MACD/ADX/ATR calculations
- support/resistance
- volatility classification
- setup generation
- conflicting timeframe detection
- missing futures data
- missing options data
- expiry parsing
- no fabricated data

Extend:

tests/test_openrouter_agent.py

Test:

- quota/rate-limit classification
- AI_FALLBACK_EXHAUSTED
- safe-mode eligibility
- paid model never allowed
- non-zero reported cost always blocked
- cache prevents unnecessary AI calls

Add paper tests:

- AI unavailable + safe mode enabled → deterministic paper entry allowed when all hard gates pass
- AI unavailable + safe mode disabled → entry rejected
- daily loss breaker still blocks safe mode
- max drawdown still blocks safe mode
- high volatility still blocks safe mode
- 8% stop cap still blocks safe mode
- AI recovery exits safe mode
- real mode remains AI_REQUIRED

## 15. Important safety hierarchy

Highest authority:

1. invalid market data
2. portfolio risk breakers
3. volatility / liquidity gates
4. stop-distance cap
5. minimum R:R
6. position/exposure limits
7. deterministic strategy
8. AI analysis

AI can reduce confidence or reject a setup.

AI must never override a hard deterministic risk rejection.

## 16. Backtesting

Backtest the AI-independent strategy first.

Then separately compare:

A. deterministic only
B. deterministic + AI required
C. deterministic + AI optional
D. deterministic + safe mode

Track:

- return
- max drawdown
- profit factor
- win rate
- expectancy
- Sharpe
- Sortino
- turnover
- fees
- slippage
- funding
- trade count
- AI calls per trade
- rejected setups
- safe-mode trades

Do not claim AI improves performance until out-of-sample testing demonstrates it.

## 17. Current implementation context

Existing Zerqen already has:

- paper trading
- PostgreSQL ledger
- equity snapshots
- risk engine
- adaptive stop
- 8% maximum stop-distance cap
- 2R minimum target
- daily loss breaker
- max drawdown breaker
- top-50 scanner
- historical spot/futures backtest
- persistent demo worker
- free-only OpenRouter registry
- AI status endpoints

This implementation should extend those systems instead of duplicating them.

## 18. Expected execution flow

Every automatic demo cycle:

PUBLIC MARKET DATA
↓
MULTI-TIMEFRAME REPORT
↓
DERIVATIVES / OPTIONS CONTEXT
↓
DETERMINISTIC STRATEGY
↓
HARD RISK GATES
↓
candidate setup?
  NO → HOLD / AUDIT
  YES
↓
AI available?
  YES → AI analysis
  NO → SAFE MODE decision
↓
AI says HOLD / low confidence?
  → NO ENTRY
↓
AI agrees + hard gates pass
  → PAPER TEST ORDER
↓
server-side stop/target monitoring
↓
ledger + equity + audit

AI is advisory intelligence inside the paper system.
The risk engine remains the final execution authority.

## 19. Definition of done

The implementation is complete only when:

- AI quota exhaustion no longer crashes/stops paper execution unnecessarily
- safe mode is automatic and audited
- real mode remains AI-required
- one normalized report contains indicators + market structure + derivatives + futures expiry + options context + risk
- AI sees one coherent report
- AI calls are cached/throttled
- no paid model can ever be selected
- missing data is explicitly represented
- every decision is reproducible from the stored report
- tests pass across Python 3.10–3.13
- CI is green
- deployment status is verified separately from code status