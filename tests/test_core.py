import pandas as pd
from zerqen.compound import compound_daily, equity_curve
from zerqen.config import ZerqenConfig
from zerqen.risk import position_size
from zerqen.strategy import generate_signals

def test_compound_daily():
    assert compound_daily(1000, 0.08) == 1080

def test_equity_curve():
    result = equity_curve(pd.Series([0.08, 0.08]), 1000)
    assert round(result.iloc[-1], 2) == 1166.40

def test_position_size():
    decision = position_size(1000, 100, 95, 0.01, 2)
    assert decision.allowed
    assert decision.quantity == 2
    assert decision.target_price == 110

def test_strategy_no_lookahead_shape():
    frame = pd.DataFrame({
        "timestamp": pd.date_range("2026-01-01", periods=100, freq="15min"),
        "open": range(100, 200),
        "high": range(101, 201),
        "low": range(99, 199),
        "close": range(100, 200),
        "volume": [1000] * 100,
    })
    result = generate_signals(frame, ZerqenConfig().strategy)
    assert len(result) == len(frame)
    assert {"ema_fast", "ema_slow", "rsi", "atr", "entry"} <= set(result.columns)
