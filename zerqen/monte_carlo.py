from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from .drawdown import max_drawdown_from_returns


@dataclass(frozen=True)
class MonteCarloSummary:
    simulations: int
    horizon: int
    terminal_return_p05: float
    terminal_return_median: float
    terminal_return_p95: float
    max_drawdown_p05: float
    max_drawdown_median: float
    max_drawdown_p95: float


def simulate_returns(
    returns: pd.Series,
    simulations: int = 1000,
    seed: int = 42,
    horizon: int | None = None,
) -> np.ndarray:
    values = returns.dropna().astype(float).to_numpy()
    if len(values) < 2:
        raise ValueError("at least two returns are required")
    if simulations <= 0:
        raise ValueError("simulations must be positive")
    horizon = horizon or len(values)
    if horizon <= 0:
        raise ValueError("horizon must be positive")

    rng = np.random.default_rng(seed)
    return rng.choice(values, size=(simulations, horizon), replace=True)


def monte_carlo_returns(
    returns: pd.Series,
    simulations: int = 1000,
    seed: int = 42,
    horizon: int | None = None,
) -> MonteCarloSummary:
    samples = simulate_returns(returns, simulations, seed, horizon)
    terminal = np.prod(1.0 + samples, axis=1) - 1.0
    drawdowns = np.array([
        max_drawdown_from_returns(pd.Series(path))
        for path in samples
    ])
    return MonteCarloSummary(
        simulations=samples.shape[0],
        horizon=samples.shape[1],
        terminal_return_p05=float(np.quantile(terminal, 0.05)),
        terminal_return_median=float(np.quantile(terminal, 0.50)),
        terminal_return_p95=float(np.quantile(terminal, 0.95)),
        max_drawdown_p05=float(np.quantile(drawdowns, 0.05)),
        max_drawdown_median=float(np.quantile(drawdowns, 0.50)),
        max_drawdown_p95=float(np.quantile(drawdowns, 0.95)),
    )
