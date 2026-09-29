from decimal import Decimal as D

from api.backtest import _liq_price, _structural_stop


def test_futures_liquidation_distance_is_leverage_dependent():
    entry = D(100)
    assert _liq_price(entry, "buy", D(2)) == D("50.5")
    assert _liq_price(entry, "sell", D(2)) == D("149.5")


def test_structural_stop_respects_eight_percent_cap():
    rows = []
    for i in range(21):
        close = D(100)
        rows.append([i, close, D(101), D(99), close, D(1000)])
    atr = D(10)
    assert _structural_stop(rows, 20, "buy", [atr] * 21) is None
