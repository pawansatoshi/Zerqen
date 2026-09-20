import pandas as pd
import pytest

from zerqen.allocation import allocate_by_score
from zerqen.compounding import compound_path
from zerqen.exposure import cap_exposure
from zerqen.portfolio_risk import portfolio_risk_check


def test_allocation_is_bounded_and_reproducible():
    result = allocate_by_score(
        10_000,
        {"trend": 3.0, "breakout": 1.0, "mean_reversion": 0.5},
        max_strategy_weight=0.6,
    )
    assert sum(item.weight for item in result) == pytest.approx(1.0)
    assert max(item.weight for item in result) <= 0.6 + 1e-12
    assert sum(item.capital for item in result) == pytest.approx(10_000)


def test_portfolio_risk_budget():
    allowed = portfolio_risk_check(10_000, [25, 25, 50], max_total_risk=0.015)
    blocked = portfolio_risk_check(10_000, [100, 100], max_total_risk=0.015)
    assert allowed.allowed
    assert not blocked.allowed


def test_exposure_cap():
    decision = cap_exposure(10_000, 15_000, max_gross_leverage=1.0)
    assert decision.accepted == 10_000
    assert decision.reason == "exposure capped"


def test_compounding_path():
    path = compound_path(1000, [0.10, -0.05, 0.02])
    assert [round(item.ending_equity, 2) for item in path] == [1100.0, 1045.0, 1065.9]


def test_no_target_forcing():
    path = compound_path(1000, [0.0, 0.0])
    assert path[-1].ending_equity == 1000.0
