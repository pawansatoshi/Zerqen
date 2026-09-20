import numpy as np
import pandas as pd
import pytest

from zerqen.drawdown import max_drawdown, max_drawdown_from_returns
from zerqen.monte_carlo import monte_carlo_returns, simulate_returns
from zerqen.robustness import evaluate_gate
from zerqen.walkforward import run_walk_forward


def test_drawdown_is_true_peak_to_trough():
    equity = pd.Series([100.0, 120.0, 90.0, 110.0])
    assert max_drawdown(equity) == pytest.approx(-0.25)
    assert max_drawdown_from_returns(pd.Series([0.20, -0.25, 0.2222222])) == pytest.approx(-0.25)


def test_monte_carlo_is_reproducible():
    returns = pd.Series([0.01, -0.005, 0.02, -0.01])
    a = simulate_returns(returns, simulations=25, seed=7, horizon=10)
    b = simulate_returns(returns, simulations=25, seed=7, horizon=10)
    assert np.array_equal(a, b)


def test_monte_carlo_summary_has_ordered_quantiles():
    summary = monte_carlo_returns(pd.Series([0.01, 0.02, -0.005]), simulations=50, seed=1, horizon=12)
    assert summary.terminal_return_p05 <= summary.terminal_return_median
    assert summary.terminal_return_median <= summary.terminal_return_p95
    assert summary.max_drawdown_p05 <= 0


def test_walk_forward_selects_parameters_per_window():
    frame = pd.DataFrame({"x": range(30)})

    def evaluator(data, params):
        return float(params["value"]) + len(data) * 0.001

    result = run_walk_forward(
        frame,
        [{"value": 1}, {"value": 2}],
        evaluator,
        train_size=10,
        test_size=5,
    )
    assert len(result.windows) == 4
    assert all(window.parameters == {"value": 2} for window in result.windows)
    assert result.positive_test_fraction == 1.0


def test_robustness_gate():
    gate = evaluate_gate(
        positive_test_fraction=0.75,
        median_test_score=0.02,
        mc_terminal_p05=0.01,
        mc_max_drawdown_p95=-0.15,
    )
    assert gate.passed
