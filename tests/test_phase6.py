import pytest
from zerqen.adapters import PaperExchangeAdapter
from zerqen.execution_service import ExecutionService
from zerqen.orders import Order, OrderSide, OrderStatus
from zerqen.reconciliation import reconcile_position

def test_paper_adapter_fills_and_is_idempotent():
    service = ExecutionService(PaperExchangeAdapter())
    order = Order("zq-1", "BTC/USDT", OrderSide.BUY, 0.1)
    first = service.submit_once(order, 100.0)
    second = service.submit_once(order, 100.0)
    assert first.event.status == OrderStatus.FILLED
    assert first.event.average_price > 100
    assert second.duplicate
    assert second.event.average_price == first.event.average_price

def test_state_machine_rejects_invalid_transition():
    service = ExecutionService(PaperExchangeAdapter())
    order = Order("zq-2", "BTC/USDT", OrderSide.BUY, 0.1)
    service.submit_once(order, 100.0)
    with pytest.raises(ValueError):
        service.state.transition(order.client_order_id, OrderStatus.CANCELED)

def test_reconciliation():
    assert reconcile_position(1.0, 1.0 + 1e-13).balanced
    assert not reconcile_position(1.0, 1.01, tolerance=1e-6).balanced
