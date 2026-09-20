from __future__ import annotations
from dataclasses import dataclass
from .adapters import ExchangeAdapter
from .orders import Order, OrderEvent, OrderStateMachine

@dataclass(frozen=True)
class ExecutionResult:
    event: OrderEvent
    duplicate: bool = False

class ExecutionService:
    """Execution boundary: signals become orders only through this service."""
    def __init__(self, adapter: ExchangeAdapter):
        self.adapter = adapter
        self.state = OrderStateMachine()

    def submit_once(self, order: Order, reference_price: float) -> ExecutionResult:
        duplicate = False
        try:
            self.state.register(order)
        except ValueError as exc:
            if "already registered" not in str(exc):
                raise
            duplicate = True
        result = self.adapter.submit(order, reference_price)
        current = self.state.status(order.client_order_id)
        if current != result.status:
            self.state.transition(order.client_order_id, result.status)
        fill = result.fill
        return ExecutionResult(OrderEvent(order.client_order_id, result.status, fill.quantity if fill else 0.0, fill.price if fill else 0.0, result.message), duplicate)
