import pandas as pd
import pytest

from zerqen.ensemble import ensemble_entry, ensemble_score
from zerqen.oos import select_on_train_only
from zerqen.regime import classify_regime
from zerqen.strategies import (
    breakout_strategy,
    higher_timeframe_confirmation,
    mean_reversion_strategy,
    trend_strategy,
    volatility_filter,
)
from zerqen.strategy_registry import default_registry


def sample_frame(n: int = 240) -> pd.DataFrame:
    idx = pd.date_range("2026-01-01", periods=n, freq="15min")
    close = pd.Series(range(100, 100 + n), index=idx, dtype=float)
    return pd.DataFrame({
        "timestamp": idx,
        "open": close,
        "high": close + 1,
        "low": close - 1,
        "close": close,
        "volume": 1000.0,
    })


def test_regime_is_causal_shape():
    frame = sample_frame()
    regimes = classify_regime(frame)
    assert len(regimes) == len(frame)
    assert set(regimes.dropna().unique()) <= {
        "unknown", "trend_up", "trend_down", "range", "high_volatility"
    }


def test_strategies_return_boolean_series():
    frame = sample_frame()
    for fn in (trend_strategy, mean_reversion_strategy, breakout_strategy, volatility_filter):
        result = fn(frame)
        assert len(result) == len(frame)
        assert result.dtype == bool


def test_higher_timeframe_uses_completed_blocks():
    frame = sample_frame()
    signal = higher_timeframe_confirmation(frame, fast=3, slow=5, bars_per_higher_candle=4)
    changed = frame.copy()
    changed.loc[changed.index[-1], "close"] = 1_000_000
    changed_signal = higher_timeframe_confirmation(
        changed, fast=3, slow=5, bars_per_higher_candle=4
    )
    assert signal.iloc[-1] == changed_signal.iloc[-1]


def test_ensemble():
    frame = sample_frame(3)
    a = pd.Series([True, False, True], index=frame.index)
    b = pd.Series([True, True, False], index=frame.index)
    score = ensemble_score(frame, {"a": a, "b": b})
    assert score["score"].tolist() == [1.0, 0.5, 0.5]
    assert ensemble_entry(frame, {"a": a, "b": b}, threshold=0.5).all()


def test_registry():
    registry = default_registry()
    assert registry.names() == ("breakout", "mean_reversion", "trend")
    assert registry.run("trend", sample_frame()).dtype == bool
    with pytest.raises(KeyError):
        registry.get("missing")


def test_oos_selects_on_train_and_evaluates_holdout():
    frame = pd.DataFrame({"x": range(10)})
    calls = []

    def evaluator(data, params):
        calls.append((len(data), params["value"]))
        return float(params["value"]) if len(data) == 7 else float(-params["value"])

    result = select_on_train_only(
        frame,
        [{"value": 1}, {"value": 2}],
        evaluator,
        train_fraction=0.7,
    )
    assert result.params == {"value": 2}
    assert result.train_score == 2
    assert result.test_score == -2
    assert calls == [(7, 1), (7, 2), (3, 2)]
