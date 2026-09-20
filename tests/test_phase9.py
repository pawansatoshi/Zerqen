import pytest
from zerqen.approval import approve_live
from zerqen.emergency import emergency_stop
from zerqen.kill_switch import KillSwitch
from zerqen.live_guard import LiveLimits, authorize_order
from zerqen.live_reconciliation import reconcile_live
from zerqen.mode import TradingMode

def limits():
    return LiveLimits(10_000, 1_000, 0.03, 0.20)

def test_live_guard_allows_only_within_limits():
    switch = KillSwitch()
    result = authorize_order(TradingMode.LIVE, 8_000, 500, 0.01, 0.05, limits(), switch)
    assert result.allowed

def test_live_guard_blocks_non_live():
    result = authorize_order(TradingMode.PAPER, 8_000, 500, 0.01, 0.05, limits(), KillSwitch())
    assert not result.allowed

def test_live_guard_blocks_oversized_order():
    result = authorize_order(TradingMode.LIVE, 8_000, 2_000, 0.01, 0.05, limits(), KillSwitch())
    assert not result.allowed

def test_kill_switch_blocks_live():
    switch = KillSwitch()
    emergency_stop(switch, "reconciliation drift")
    result = authorize_order(TradingMode.LIVE, 8_000, 500, 0.01, 0.05, limits(), switch)
    assert not result.allowed

def test_reconciliation():
    assert reconcile_live(1, 1 + 1e-13).balanced
    assert not reconcile_live(1, 1.01, 1e-6).balanced

def test_approval_requires_operator():
    with pytest.raises(ValueError):
        approve_live("", "reason")
    approval = approve_live("operator-1", "manual release")
    assert approval.approved
