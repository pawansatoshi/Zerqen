from decimal import Decimal as D

import pytest

from zerqen.futures_paper import (
    FuturesLimits,
    funding_cashflow,
    initial_margin,
    liquidation_price,
    maintenance_margin,
    mark_position,
    size_futures_position,
    unrealized_pnl,
    validate_leverage,
)


def test_isolated_initial_margin_uses_leverage():
    assert initial_margin(D("1000"), D("5")) == D("200")


def test_liquidation_price_is_side_and_leverage_dependent():
    assert liquidation_price(D("100"), "buy", D("2")) == D("50.5")
    assert liquidation_price(D("100"), "sell", D("2")) == D("149.5")


def test_unrealized_pnl_respects_side():
    assert unrealized_pnl(D("100"), D("110"), D("2"), "buy") == D("20")
    assert unrealized_pnl(D("100"), D("90"), D("2"), "sell") == D("20")


def test_funding_long_pays_positive_rate_and_short_receives():
    assert funding_cashflow(D("1000"), D("0.0001"), "buy") == D("-0.1")
    assert funding_cashflow(D("1000"), D("0.0001"), "sell") == D("0.1")


def test_mark_position_reports_margin_ratio_and_liquidation():
    mark = mark_position(
        D("100"), D("95"), D("10"), "buy", D("500"), D("2")
    )
    assert mark.unrealized_pnl == D("-50")
    assert mark.maintenance_margin == D("4.75")
    assert mark.margin_ratio == D("4.75") / D("450")
    assert not mark.liquidated


def test_mark_position_liquidates_when_boundary_is_crossed():
    mark = mark_position(
        D("100"), D("50"), D("10"), "buy", D("50"), D("2")
    )
    assert mark.liquidated


def test_futures_risk_sizing_is_fixed_fractional():
    result = size_futures_position(
        D("10000"), D("100"), D("97"), "buy", D("2")
    )
    assert result.allowed
    assert result.risk_amount == D("50")
    assert result.quantity > 0
    assert result.initial_margin < result.notional
    assert result.liquidation_price == D("50.5")


def test_stop_cannot_be_beyond_liquidation():
    result = size_futures_position(
        D("10000"), D("100"), D("40"), "buy", D("2")
    )
    assert not result.allowed
    assert "liquidation" in result.reason


def test_leverage_is_hard_capped():
    with pytest.raises(ValueError):
        validate_leverage(D("6"))
