from dataclasses import dataclass
import pandas as pd
from .config import ZerqenConfig
from .risk import daily_loss_breached, drawdown_breached, position_size
from .strategy import generate_signals


@dataclass
class Trade:
    entry_time: object
    exit_time: object
    entry: float
    exit: float
    quantity: float
    gross_return: float
    net_return: float
    pnl: float
    reason: str


def run_backtest(frame: pd.DataFrame, cfg: ZerqenConfig) -> tuple[pd.DataFrame, dict]:
    df = frame.copy()
    if "timestamp" in df:
        df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
        df = df.sort_values("timestamp").reset_index(drop=True)
    else:
        df["timestamp"] = pd.RangeIndex(len(df))

    df = generate_signals(df, cfg.strategy)

    equity = float(cfg.starting_capital)
    peak = equity
    max_drawdown = 0.0
    day_start = equity
    current_day = None
    position = None
    pending_signal_exit = False
    trades: list[Trade] = []
    equity_points: list[float] = [equity]

    for i in range(1, len(df)):
        row = df.iloc[i]
        prev = df.iloc[i - 1]
        ts = row["timestamp"]
        day = pd.Timestamp(ts).date() if not isinstance(ts, int) else i
        if current_day != day:
            current_day = day
            day_start = equity

        if drawdown_breached(equity, peak, cfg.risk.max_drawdown):
            break

        # A signal observed on the prior completed candle executes at this candle's open.
        if position is None and bool(prev["entry"]):
            entry = float(row["open"]) * (1 + cfg.costs.slippage_rate)
            stop = entry - float(prev["atr"]) * cfg.strategy.stop_atr
            decision = position_size(
                equity, entry, stop, cfg.risk.risk_per_trade, cfg.strategy.target_rr
            )
            if decision.allowed and not daily_loss_breached(day_start, equity, cfg.risk.max_daily_loss):
                position = {
                    "entry_time": ts,
                    "entry": entry,
                    "qty": decision.quantity,
                    "stop": decision.stop_price,
                    "target": decision.target_price,
                }
                pending_signal_exit = False

        if position is not None:
            exit_price = None
            reason = None

            # Conservative deterministic ambiguity rule: if stop and target both
            # trade through the same candle, assume the stop occurred first.
            if float(row["low"]) <= position["stop"]:
                exit_price = position["stop"] * (1 - cfg.costs.slippage_rate)
                reason = "stop"
            elif float(row["high"]) >= position["target"]:
                exit_price = position["target"] * (1 - cfg.costs.slippage_rate)
                reason = "target"
            elif pending_signal_exit:
                # A signal invalidation observed at the prior close executes here,
                # at the next candle open, never at the same candle close.
                exit_price = float(row["open"]) * (1 - cfg.costs.slippage_rate)
                reason = "signal"

            if exit_price is not None:
                gross_pnl = (exit_price - position["entry"]) * position["qty"]
                fees = (
                    (position["entry"] * position["qty"])
                    + (exit_price * position["qty"])
                ) * cfg.costs.fee_rate
                pnl = gross_pnl - fees
                base_equity = equity
                equity = max(0.0, equity + pnl)
                peak = max(peak, equity)
                max_drawdown = max(max_drawdown, 1.0 - equity / peak if peak else 0.0)
                trades.append(
                    Trade(
                        position["entry_time"], ts, position["entry"], exit_price,
                        position["qty"],
                        gross_pnl / (position["entry"] * position["qty"]),
                        pnl / base_equity if base_equity else -1.0,
                        pnl, reason,
                    )
                )
                position = None
                pending_signal_exit = False

        if position is not None:
            # This signal is known only after the current candle has completed.
            pending_signal_exit = not bool(row["entry"])

        equity_points.append(equity)

    # Never silently discard an open research position. Mark it to the final
    # observed close so the report contains a complete economic outcome.
    if position is not None and len(df):
        row = df.iloc[-1]
        exit_price = float(row["close"]) * (1 - cfg.costs.slippage_rate)
        gross_pnl = (exit_price - position["entry"]) * position["qty"]
        fees = (
            (position["entry"] * position["qty"])
            + (exit_price * position["qty"])
        ) * cfg.costs.fee_rate
        pnl = gross_pnl - fees
        base_equity = equity
        equity = max(0.0, equity + pnl)
        peak = max(peak, equity)
        max_drawdown = max(max_drawdown, 1.0 - equity / peak if peak else 0.0)
        trades.append(
            Trade(
                position["entry_time"], row["timestamp"], position["entry"], exit_price,
                position["qty"],
                gross_pnl / (position["entry"] * position["qty"]),
                pnl / base_equity if base_equity else -1.0,
                pnl, "end_of_test",
            )
        )
        equity_points.append(equity)

    trades_df = pd.DataFrame([t.__dict__ for t in trades])
    if trades_df.empty:
        trades_df = pd.DataFrame(
            columns=["entry_time","exit_time","entry","exit","quantity","gross_return","net_return","pnl","reason"]
        )

    equity_series = pd.Series(equity_points, dtype=float)
    running_peak = equity_series.cummax()
    max_drawdown = float((1.0 - equity_series / running_peak.replace(0, pd.NA)).max())

    total_return = equity / cfg.starting_capital - 1
    wins = int((trades_df["pnl"] > 0).sum()) if len(trades_df) else 0
    metrics = {
        "starting_capital": cfg.starting_capital,
        "final_equity": equity,
        "total_return": total_return,
        "total_return_pct": total_return * 100,
        "trades": len(trades_df),
        "win_rate": wins / len(trades_df) if len(trades_df) else 0.0,
        "peak_equity": peak,
        "max_drawdown": max_drawdown if pd.notna(max_drawdown) else 0.0,
        "target_daily_return": cfg.target_daily_return,
        "execution_model": "next_open_entry / next_open_signal_exit / stop-first candle ambiguity",
    }
    return trades_df, metrics
