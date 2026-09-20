# Validation Protocol

Zerqen's 8% daily figure is a research hurdle, not a promised return.

## Required sequence

1. Clean historical data.
2. Freeze a final out-of-sample period.
3. Backtest with fees and slippage.
4. Run lookahead and leakage checks.
5. Compare against buy-and-hold.
6. Run parameter sensitivity.
7. Run rolling walk-forward tests.
8. Perturb trade order with Monte Carlo.
9. Stress fees, spread and slippage.
10. Paper/dry-run.
11. Testnet.
12. Only then consider a tightly capped live allocation.

## Minimum report

- final equity
- geometric return
- average daily return
- volatility
- Sharpe
- maximum drawdown
- worst day
- longest losing streak
- trade count
- win rate
- profit factor
- fees paid
- slippage assumption
- exposure
- target-hit frequency

## Failure conditions

A strategy fails validation if:

- it depends on future data;
- results collapse out-of-sample;
- small parameter changes destroy the edge;
- fees/slippage erase the edge;
- drawdown exceeds the configured limit;
- returns are dominated by a tiny number of trades;
- live/dry-run behavior materially diverges from backtest.

Freqtrade's current documentation explicitly warns that backtests can be distorted and recommends dry-run/forward testing after backtesting. Zerqen adopts the same research discipline. 
