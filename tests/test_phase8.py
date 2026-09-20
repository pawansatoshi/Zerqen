import pytest
from zerqen.dry_run import DryRunExecutor
from zerqen.gates import promotion_gate
from zerqen.kill_switch import KillSwitch
from zerqen.mode import TradingMode, parse_mode
from zerqen.orders import Order, OrderSide, OrderStatus
from zerqen.preflight import run_preflight

def test_modes():
    assert parse_mode("paper") == TradingMode.PAPER
    with pytest.raises(ValueError):
        parse_mode("unknown")

def test_live_preflight_requires_explicit_enable():
    result = run_preflight(TradingMode.LIVE, data_available=True, credentials_present=True, explicit_live_enable=False)
    assert not result.ready
    assert "explicit_live_enable" in result.reasons

def test_paper_preflight_does_not_need_credentials():
    result = run_preflight(TradingMode.PAPER, data_available=True, credentials_present=False)
    assert result.ready

def test_dry_run_never_live():
    executor = DryRunExecutor()
    order = Order("dry-1", "BTC/USDT", OrderSide.BUY, 1.0)
    result = executor.submit(order, 100.0)
    assert result.result.status == OrderStatus.FILLED
    assert not executor.is_live()

def test_kill_switch():
    switch = KillSwitch()
    assert switch.allow_orders()
    switch.trip("drawdown limit")
    assert not switch.allow_orders()
    assert switch.reason == "drawdown limit"

def test_live_gate():
    preflight = run_preflight(TradingMode.LIVE, data_available=True, credentials_present=True, explicit_live_enable=True)
    assert not promotion_gate(TradingMode.LIVE, preflight).allowed
    assert promotion_gate(TradingMode.LIVE, preflight, approved=True).allowed
