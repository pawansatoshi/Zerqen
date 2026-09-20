import pandas as pd
import pytest

from zerqen.benchmarks import buy_and_hold_return, daily_returns_from_equity
from zerqen.execution import CandleExecutionModel
from zerqen.leakage import assert_chronological
from zerqen.sensitivity import grid_search

def test_execution_costs():
    model = CandleExecutionModel(fee_rate=0.001, slippage_rate=0.001)
    fill = model.buy(100, 2)
    assert fill.price == pytest.approx(100.1)
    assert fill.fee == pytest.approx(0.2002)

def test_chronology_rejects_duplicates():
    frame = pd.DataFrame({"timestamp": ["2026-01-01", "2026-01-01"]})
    with pytest.raises(ValueError):
        assert_chronological(frame)

def test_buy_and_hold():
    frame = pd.DataFrame({"close": [100, 110]})
    assert buy_and_hold_return(frame) == pytest.approx(0.10)

def test_daily_returns():
    idx = pd.date_range("2026-01-01", periods=3, freq="D", tz="UTC")
    equity = pd.Series([100, 110, 121], index=idx)
    result = daily_returns_from_equity(equity)
    assert result.iloc[-1] == pytest.approx(0.10)

def test_grid_search():
    result = grid_search({"x": [1, 2], "y": [10, 20]}, lambda p: p["x"] + p["y"])
    assert result[0].parameters == {"x": 2, "y": 20}
