from decimal import Decimal as D

from zerqen.paper_engine import (
    PaperLimits,
    Position,
    apply_fill,
    check_portfolio_risk,
    mark_position,
    net_realized_pnl,
    size_for_risk,
)


def test_risk_sizing_is_fixed_fractional():
    limits = PaperLimits()
    result = size_for_risk(D("10000"), D("100"), D("2"), limits)
    assert result.allowed
    assert result.risk_amount == D("50.000")
    assert result.quantity > 0
    assert result.stop_price == D("97.0")
    assert result.target_price == D("106.0")


def test_daily_loss_breaker_blocks_new_risk():
    limits = PaperLimits()
    result = size_for_risk(D("10000"), D("100"), D("2"), limits)
    allowed, reason = check_portfolio_risk(
        D("10000"), [], result, limits, D("-300"), D("10000")
    )
    assert not allowed
    assert "daily loss" in reason


def test_drawdown_breaker_blocks_new_risk():
    limits = PaperLimits()
    result = size_for_risk(D("10000"), D("100"), D("2"), limits)
    allowed, reason = check_portfolio_risk(
        D("7900"), [], result, limits, D("0"), D("10000")
    )
    assert not allowed
    assert "drawdown" in reason


def test_gross_exposure_cap_blocks_new_risk():
    limits = PaperLimits()
    result = size_for_risk(D("10000"), D("100"), D("2"), limits)
    allowed, reason = check_portfolio_risk(
        D("10000"),
        [Position("BTC/USDT", "buy", D("95"), D("100"))],
        result,
        limits,
        D("0"),
        D("10000"),
        proposed_notional=D("100"),
    )
    assert not allowed
    assert "gross exposure" in reason


def test_partial_fill_then_close_realizes_net_pnl():
    position, realized = apply_fill(None, "buy", D("1"), D("100"), D("0.10"))
    position.symbol = "BTC/USDT"
    assert position.quantity == D("1")
    position, realized2 = apply_fill(position, "sell", D("0.4"), D("110"), D("0.05"))
    assert position is not None
    assert position.quantity == D("0.6")
    assert realized2 == D("3.85")
    position, realized3 = apply_fill(position, "sell", D("0.6"), D("90"), D("0.05"))
    assert position is None
    assert realized3 == D("-6.05")
    assert mark_position(Position("BTC/USDT", "buy", D("1"), D("100")), D("105")) == D("5")


def test_net_pnl_excludes_unrealized_profit_from_compounding():
    assert net_realized_pnl(D("100"), D("2"), D("1"), D("3")) == D("94")


def test_invalid_market_data_cannot_size():
    limits = PaperLimits()
    assert not size_for_risk(D("10000"), D("100"), D("0"), limits).allowed
