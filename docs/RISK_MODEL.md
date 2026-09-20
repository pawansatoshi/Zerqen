# Risk Model

The baseline strategy uses fixed fractional risk per trade.

Default:

- risk per trade: 0.5% of equity
- daily loss limit: 3%
- maximum portfolio drawdown: 20%
- maximum concurrent positions: 3
- stop-loss: 1.5 ATR
- target: 2R

These defaults are deliberately conservative relative to the 8% research hurdle.

The system must not increase leverage or position size merely because the daily target has not been achieved.

## Daily target

The 8% target is informational:

`target_daily_return = 0.08`

It is used for reporting and research evaluation. It is never an execution command.

## Compounding

At the end of a trading day:

`next_equity = current_equity × (1 + realized_daily_return)`

Losses compound too. A -8% day reduces the following day's capital by 8%.

## Capital preservation

Once a global drawdown limit is reached, the research run halts. In live mode, the same event must trigger an independent emergency stop.
