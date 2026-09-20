import pandas as pd
from zerqen.data_quality import validate_ohlcv
from zerqen.kill_switch import KillSwitch
from zerqen.live_guard import LiveLimits
from zerqen.mode import TradingMode
from zerqen.order_journal import JournalRecord, OrderJournal
from zerqen.orders import Order, OrderSide
from zerqen.integration import authorize_pipeline

def frame():
    return pd.DataFrame({
        "timestamp": pd.date_range("2026-01-01", periods=2, freq="h"),
        "open": [100, 101], "high": [102, 103], "low": [99, 100],
        "close": [101, 102], "volume": [10, 12],
    })

def test_data_quality():
    assert validate_ohlcv(frame())[0]
    bad = frame()
    bad.loc[1, "close"] = -1
    assert not validate_ohlcv(bad)[0]

def test_journal_recovery():
    journal = OrderJournal()
    journal.append(JournalRecord("z1", "filled", 1.0, 100.0))
    assert journal.recover("z1").average_price == 100.0

def test_pipeline_blocks_kill_switch():
    switch = KillSwitch()
    switch.trip("operator stop")
    order = Order("z2", "BTC/USDT", OrderSide.BUY, 1.0)
    result = authorize_pipeline(
        TradingMode.PAPER, order, 10000, 0.02, 0.01,
        open_risk_amounts=[25], max_total_risk=0.015,
        live_limits=LiveLimits(10000, 1000, 0.03, 0.20),
        kill_switch=switch,
    )
    assert not result.allowed

def test_pipeline_rejects_bad_quantity():
    order = Order("z3", "BTC/USDT", OrderSide.BUY, 0)
    result = authorize_pipeline(
        TradingMode.PAPER, order, 10000, 0.0, 0.0,
        open_risk_amounts=[], max_total_risk=0.015,
        live_limits=LiveLimits(10000, 1000, 0.03, 0.20),
        kill_switch=KillSwitch(),
    )
    assert not result.allowed
