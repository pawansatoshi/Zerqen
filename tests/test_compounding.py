from decimal import Decimal

import pytest

from zerqen.paper_engine import compounding_equity, net_realized_pnl


def test_compounding_uses_realized_net_only():
    starting = Decimal(10000)
    realized_net = net_realized_pnl(
        Decimal(150),
        Decimal(20),
        Decimal(5),
        Decimal(10),
    )
    unrealized = Decimal(900)
    assert realized_net == Decimal(115)
    assert compounding_equity(starting, realized_net) == Decimal(10115)
    assert compounding_equity(starting, realized_net) != starting + realized_net + unrealized


def test_compounding_can_reduce_after_a_realized_loss():
    assert compounding_equity(Decimal(10000), Decimal(-250)) == Decimal(9750)


def test_compounding_rejects_negative_starting_equity():
    with pytest.raises(ValueError):
        compounding_equity(Decimal(-1), Decimal(10))
